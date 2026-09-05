"""ADR-0041: command guards share execution context without losing proof."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import semantic_feasibility_patch  # noqa: F401
import semantic_compiler_gate as gate
import semantic_worker_v3_execution_contract_patch as execution
import semantic_worker_v3_group_repair_patch as grouped
import semantic_worker_v3_explicit_path_contract_patch as paths


@pytest.fixture(autouse=True)
def no_live_repair(monkeypatch):
    def reject(**kwargs):
        pytest.fail("unexpected live repair: " + str(kwargs["payload"].get("validator_findings")))
    monkeypatch.setattr(grouped, "_live_group_repair", reject)


def _fixture():
    return json.loads((SCRIPTS / "fixtures/ch456-v3-harness-lane.json").read_text(encoding="utf-8"))


def _guard(fixture):
    hint = next(h for h in fixture["v3"]["slice_hints"] if h["verification_lane"] == "runtime")
    oid = hint["obligation_ids"][0]
    failure = next(f for f in fixture["v3"]["failure_intents"] if f["obligation_ids"] == [oid])
    assert failure["failure_family"] == "test-harness-failure"
    obligation = next(o for o in fixture["obligations"] if o["obligation_id"] == oid)
    return oid, obligation, hint, failure


def _root(tmp_path, fixture):
    # Only existence/source reads occur in this offline compiler replay.
    for hint in fixture["v3"]["slice_hints"]:
        for name in hint["production_owners"]:
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Offline owner existence fixture.\n", encoding="utf-8")
    for entry in fixture["source_index"]["entries"]:
        path = tmp_path / entry["repository_relative_source_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry["source_text"], encoding="utf-8")
        for name in paths._source_facts(entry)["existing_fixtures"]:
            existing = tmp_path / name
            existing.parent.mkdir(parents=True, exist_ok=True)
            existing.write_text("{}\n", encoding="utf-8")
    index = gate.sc.build_source_index(tmp_path, path)
    assert gate.sc.source_preflight(tmp_path, index)["valid"]


def test_captured_live_input_keeps_all_contracts_in_one_slice(tmp_path):
    fixture = _fixture()
    original = deepcopy(fixture)
    _root(tmp_path, fixture)
    acceptances, failures, hints = gate.sc.compile_acceptances(
        root=tmp_path, out_dir=tmp_path / "plan", obligations=fixture["obligations"],
        worker_cache={"v3": fixture["v3"]})
    edges = gate.sc.exact_cover(fixture["obligations"], acceptances, failures)
    slices, _ = gate.sc.partition_slices(fixture["obligations"], acceptances, failures, hints)
    assert len(slices) == 1
    assert len(acceptances) == len(slices[0]["acceptance_ids"]) == 15
    assert {e["acceptance_id"] for e in edges} == set(slices[0]["acceptance_ids"])
    oid, _, _, _ = _guard(fixture)
    guard = next(a for a in acceptances if a["obligation_ids"] == [oid])
    assert guard["verification_lane"] == slices[0]["verification_lane"] == "unit"
    raw = next(a for a in fixture["v3"]["acceptances"] if a["obligation_ids"] == [oid])
    assert guard["oracle"] == raw["oracle"] and guard["assertion_ids"] == raw["assertion_ids"]
    assert next(f for f in failures if guard["acceptance_id"] in f["acceptance_ids"])["failure_family"] == "test-harness-failure"
    assert fixture == original


def test_captured_input_reproduces_two_slices_without_normalization(tmp_path, monkeypatch):
    fixture = _fixture()
    _root(tmp_path, fixture)
    monkeypatch.setattr(execution, "_normalize_harness_lanes", lambda stage, payload, value: value)
    a, f, h = gate.sc.compile_acceptances(root=tmp_path, out_dir=tmp_path / "plan",
        obligations=fixture["obligations"], worker_cache={"v3": fixture["v3"]})
    slices, _ = gate.sc.partition_slices(fixture["obligations"], a, f, h)
    assert len(slices) == 2
    assert {s["verification_lane"] for s in slices} == {"unit", "runtime"}


@pytest.mark.parametrize("difference", ["command", "owner", "source", "product", "behavior", "failure-family", "ambiguous-lane"])
def test_no_lane_inheritance_without_unambiguous_same_harness_execution(difference):
    fixture = _fixture()
    oid, obligation, hint, failure = _guard(fixture)
    if difference == "command":
        hint["validation_commands"][0].append("--different-environment")
    elif difference == "owner":
        hint["production_owners"] = ["src/other.py"]
    elif difference == "source":
        obligation["source_refs"] = ["other.md#FR-1"]
    elif difference == "product":
        obligation["requirement_type"] = "Product"
    elif difference == "behavior":
        obligation["obligation_kind"] = "behavior"
    elif difference == "failure-family":
        failure["failure_family"] = "expected-red"
    else:
        product = next(o for o in fixture["obligations"] if o["obligation_kind"] == "behavior")
        next(h for h in fixture["v3"]["slice_hints"] if h["obligation_ids"] == [product["obligation_id"]])["verification_lane"] = "integration"
    result = execution._normalize_harness_lanes("v3", {"obligations": fixture["obligations"]}, fixture["v3"])
    assert next(h for h in result["slice_hints"] if h["obligation_ids"] == [oid])["verification_lane"] == "runtime"


def test_repair_path_inherits_lane_and_preserves_dependency_split(tmp_path):
    fixture = _fixture()
    oid, obligation, _, _ = _guard(fixture)
    product = next(o for o in fixture["obligations"] if o["obligation_kind"] == "behavior")
    obligation["depends_on"] = [product["obligation_id"]]
    normalized = execution._normalize_harness_lanes("v3-schema-repair", {"input": {"obligations": fixture["obligations"]}}, fixture["v3"])
    assert next(h for h in normalized["slice_hints"] if h["obligation_ids"] == [oid])["verification_lane"] == "unit"
    _root(tmp_path, fixture)
    a, f, h = gate.sc.compile_acceptances(root=tmp_path, out_dir=tmp_path / "plan",
        obligations=fixture["obligations"], worker_cache={"v3": fixture["v3"]})
    slices, _ = gate.sc.partition_slices(fixture["obligations"], a, f, h)
    assert len(slices) == 2
