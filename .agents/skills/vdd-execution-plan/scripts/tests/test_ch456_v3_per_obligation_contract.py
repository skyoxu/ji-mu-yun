"""ADR-0041: shared implementation context never substitutes for atomic proof."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_feasibility_patch  # noqa: F401  # exercise the public patch stack
import semantic_compiler_gate as gate
import semantic_worker_v3_domain_patch as domain
import semantic_worker_v3_group_repair_patch as grouped
import semantic_worker_transport_patch as transport
from test_ch456_v3_total_coverage_and_slice_cohesion import _hint, _obligation, _raw_group


def _repair():
    hint = _hint("tests/test_ledger.py")
    hint.pop("obligation_ids")
    contracts = {}
    for oid, expected in (("O-1", "duplicate"), ("O-2", "not-found")):
        raw = _raw_group([oid])
        a = raw["acceptance"]
        a["given"] = "an active key" if oid == "O-1" else "an inactive key"
        a["when"] = "claim is repeated" if oid == "O-1" else "release is requested"
        a["then"] = f"the result is {expected}"
        a["oracle"] = {"observable": "operation result", "expected": expected, "forbidden": ["accepted"]}
        a["assertion_ids"] = [f"ASSERT-{oid}"]
        raw["failure_intents"][0]["failure_id"] = f"FAIL-{oid}"
        contracts[oid] = {"acceptance": a, "failure_intents": raw["failure_intents"]}
    return {"groups": [{"group_id": "O-1", "slice_hint": hint}],
            "obligation_group_assignments": {"O-1": "O-1", "O-2": "O-1"},
            "obligation_contracts": contracts}


def test_actual_v4_input_clone_is_rejected_before_semantic_alignment():
    fixture = json.loads((SCRIPTS / "fixtures/ch456-v3-cloned-oracle.json").read_text(encoding="utf-8"))
    obligations = fixture["obligations"]
    assert len(obligations) == 2
    for stage in ("v3", "v3-schema-repair"):
        payload = {"obligations": obligations}
        if stage != "v3":
            payload = {"input": payload}
        findings = domain._domain_findings(stage, payload, fixture)
        assert any("cloned-oracle-across-obligations" in finding for finding in findings)
    boundary = next(o for o in obligations if o["obligation_kind"] == "constraint")
    assert "one bounded stateful slice" in boundary["expected_behavior"]


def test_shared_context_preserves_each_oracle_and_failure_intent():
    raw = _repair()
    projected = grouped._project(raw, refs_by_oid={"O-1": ["req.md#FR-1"], "O-2": ["req.md#FR-1"]})
    assert [a["oracle"]["expected"] for a in projected["acceptances"]] == ["duplicate", "not-found"]
    assert [f["failure_id"] for f in projected["failure_intents"]] == ["FAIL-O-1", "FAIL-O-2"]
    assert projected["slice_hints"][0]["production_owners"] == projected["slice_hints"][1]["production_owners"]
    mutated = deepcopy(raw)
    mutated["obligation_contracts"]["O-2"]["acceptance"]["oracle"]["expected"] = "changed"
    after = grouped._project(mutated)
    assert after["acceptances"][0] == projected["acceptances"][0]
    assert after["acceptances"][1]["oracle"]["expected"] == "changed"


@pytest.mark.parametrize("mutation", ["missing", "extra", "null"])
def test_contracts_must_cover_exact_assignment_domain(mutation):
    raw = _repair()
    if mutation == "missing":
        del raw["obligation_contracts"]["O-2"]
    elif mutation == "extra":
        raw["obligation_contracts"]["O-extra"] = raw["obligation_contracts"]["O-1"]
    else:
        raw["obligation_contracts"] = None
    with pytest.raises(ValueError, match="exactly cover assigned obligations"):
        grouped._project(raw)


@pytest.mark.parametrize("exact", [False, True])
def test_legacy_multi_obligation_oracle_cannot_be_cloned(exact):
    group = _raw_group(["O-1", "O-2"])
    raw = {"groups": [group]}
    if exact:
        group.pop("obligation_ids")
        group["group_id"] = "O-1"
        raw["obligation_group_assignments"] = {"O-1": "O-1", "O-2": "O-1"}
    with pytest.raises(ValueError, match="per-obligation contracts"):
        grouped._project(raw)


def test_worker_schema_requires_contracts_for_active_domain_only():
    obligations = [_obligation("O-1"), _obligation("O-2"), {**_obligation("O-3"), "status": "deferred"}]
    schema = grouped._group_schema({"input": {"obligations": obligations}})
    assert set(schema["properties"]["obligation_contracts"]["required"]) == {"O-1", "O-2"}
    assert set(schema["properties"]["obligation_group_assignments"]["required"]) == {"O-1", "O-2"}
    assert set(schema["properties"]["groups"]["items"]["properties"]) == {"group_id", "slice_hint"}
    normal = transport._worker_output_schema("v3")
    assert normal["properties"]["acceptances"]["items"]["properties"]["obligation_ids"]["maxItems"] == 1


def test_invalid_shared_oracle_uses_one_repair_then_v5_v6_keep_atomic_proof(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/ledger.py").write_text("VALUE = 0\n", encoding="utf-8")
    obligations = [_obligation("O-1"), _obligation("O-2")]
    group = _raw_group(["O-1", "O-2"])
    initial = {"acceptances": [{**group["acceptance"], "obligation_ids": ["O-1", "O-2"]}],
               "failure_intents": [{**f, "obligation_ids": ["O-1", "O-2"]} for f in group["failure_intents"]],
               "slice_hints": [{**group["slice_hint"], "obligation_ids": ["O-1", "O-2"]}]}
    worker_cache = {"v3": initial, "v3-schema-repair": _repair()}
    # No live call may replace a missing fixture or a failed semantic repair.
    monkeypatch.syspath_prepend(str(SCRIPTS.parents[3] / "scripts/sc"))
    import _llm_backend
    monkeypatch.setattr(_llm_backend, "run_llm_exec", lambda **kwargs: pytest.fail("unexpected live worker"))
    acceptances, failures, hints = gate.sc.compile_acceptances(
        root=tmp_path, out_dir=tmp_path / "plan", obligations=obligations, worker_cache=worker_cache)
    assert len(acceptances) == 2
    assert {a["obligation_ids"][0]: a["oracle"]["expected"] for a in acceptances} == {
        "O-1": "duplicate", "O-2": "not-found"}
    edges = gate.sc.exact_cover(obligations, acceptances, failures)
    assert {e["acceptance_id"] for e in edges} == {a["acceptance_id"] for a in acceptances}
    slices, _ = gate.sc.partition_slices(obligations, acceptances, failures, hints)
    assert len(slices) == 1
    assert len(slices[0]["acceptance_ids"]) == 2
    receipts = [json.loads(p.read_text(encoding="utf-8")) for p in
                (tmp_path / "plan/.compiler-work/worker-receipts").glob("*.json")]
    v3_receipts = [r for r in receipts if r["stage"] == "v3"]
    assert len(v3_receipts) == 1 and v3_receipts[0]["schema_repair_attempted"] is True


def test_cloned_repair_is_terminal_and_never_reaches_v4(tmp_path, monkeypatch):
    raw = _repair()
    raw["obligation_contracts"]["O-2"] = deepcopy(raw["obligation_contracts"]["O-1"])
    payload = {"obligations": [_obligation("O-1"), _obligation("O-2")]}
    # A rejected supplied repair must propagate; no extra repair/recheck budget.
    with pytest.raises(ValueError, match="cloned-oracle-across-obligations"):
        gate.normative_invoke_worker(root=tmp_path, out_dir=tmp_path / "plan", stage="v3",
            payload=payload, prompt="Compile contracts.",
            worker_cache={"v3": {"acceptances": []}, "v3-schema-repair": raw})
