"""ADR-0041: exact frozen contracts do not depend on worker-authored group joins.

These are synthetic reproduction fixtures, not the uncollected live output.
"""
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
import semantic_worker_v3_group_repair_patch as grouped
import semantic_worker_v3_total_coverage_patch as total
from test_ch456_v3_total_coverage_and_slice_cohesion import _obligation, _raw_group


def _inline(count=2):
    contracts = {}
    for number in range(count):
        oid = f"O-{number:03d}"
        raw = _raw_group([oid])
        del raw["obligation_ids"], raw["slice_hint"]["obligation_ids"]
        raw["acceptance"]["oracle"]["observable"] = f"observable {oid}"
        raw["acceptance"]["assertion_ids"] = [f"ASSERT-{oid}"]
        raw["failure_intents"][0]["failure_id"] = f"FAIL-{oid}"
        contracts[oid] = raw
    return {"obligation_contracts": contracts}


def _refs(raw):
    return {oid: ["req.md#FR-1"] for oid in raw["obligation_contracts"]}


def test_inline_schema_requires_proof_and_context_without_reference_targets():
    obligations = [_obligation(oid) for oid in _refs(_inline(37))]
    schema = grouped._group_schema({"input": {"obligations": obligations}})
    assert set(schema["properties"]) == set(schema["required"]) == {"obligation_contracts"}
    contracts = schema["properties"]["obligation_contracts"]
    assert set(contracts["properties"]) == set(contracts["required"]) == set(_refs(_inline(37)))
    assert contracts["additionalProperties"] is False
    for contract in contracts["properties"].values():
        assert set(contract["properties"]) == set(contract["required"]) == {
            "acceptance", "failure_intents", "slice_hint"}
        assert contract["additionalProperties"] is False


def test_37_inline_contracts_compile_once_and_keep_one_cohesive_slice(tmp_path, monkeypatch):
    raw = _inline(37)
    (tmp_path / "src").mkdir()
    (tmp_path / "src/ledger.py").write_text("VALUE = 0\n", encoding="utf-8")
    obligations = [_obligation(oid) for oid in _refs(raw)]
    monkeypatch.syspath_prepend(str(SCRIPTS.parents[3] / "scripts/sc"))
    import _llm_backend
    monkeypatch.setattr(_llm_backend, "run_llm_exec", lambda **kw: pytest.fail("unexpected live call"))
    acceptances, failures, hints = gate.sc.compile_acceptances(
        root=tmp_path, out_dir=tmp_path / "plan", obligations=obligations,
        worker_cache={"v3": {"acceptances": []}, "v3-schema-repair": raw})
    assert len(acceptances) == len(failures) == len(hints) == 37
    assert {a["obligation_ids"][0] for a in acceptances} == set(_refs(raw))
    assert len({a["oracle"]["observable"] for a in acceptances}) == 37
    edges = gate.sc.exact_cover(obligations, acceptances, failures)
    assert {e["acceptance_id"] for e in edges} == {a["acceptance_id"] for a in acceptances}
    slices, _ = gate.sc.partition_slices(obligations, acceptances, failures, hints)
    assert len(slices) == 1 and len(slices[0]["acceptance_ids"]) == 37
    receipts = [json.loads(p.read_text(encoding="utf-8")) for p in
                (tmp_path / "plan/.compiler-work/worker-receipts").glob("*.json")]
    assert len(receipts) == 1 and receipts[0]["schema_repair_attempted"] is True


@pytest.mark.parametrize("mutation", ["missing", "extra", "no-context", "mixed-format", "null"])
def test_inline_invalid_domain_or_context_fails_before_projection(mutation):
    raw = _inline()
    refs = _refs(raw)
    if mutation == "missing":
        del raw["obligation_contracts"]["O-001"]
    elif mutation == "extra":
        raw["obligation_contracts"]["O-extra"] = deepcopy(raw["obligation_contracts"]["O-000"])
    elif mutation == "no-context":
        del raw["obligation_contracts"]["O-001"]["slice_hint"]
    elif mutation == "mixed-format":
        raw["obligation_group_assignments"] = {"O-000": "not-returned"}
    else:
        raw["obligation_contracts"] = None
    with pytest.raises(ValueError, match="V3 inline repair"):
        grouped._project(raw, refs_by_oid=refs)


def test_inline_contract_does_not_guess_missing_owner_from_other_context(tmp_path):
    raw = _inline()
    (tmp_path / "src").mkdir()
    (tmp_path / "src/ledger.py").write_text("VALUE = 0\n", encoding="utf-8")
    raw["obligation_contracts"]["O-001"]["slice_hint"]["production_owners"] = ["missing.py"]
    raw["obligation_contracts"]["O-001"]["slice_hint"]["rollback_scope"]["production_paths"] = ["missing.py"]
    with pytest.raises(ValueError, match="no-real-production-entry"):
        gate.normative_invoke_worker(
            root=tmp_path, out_dir=tmp_path / "plan", stage="v3",
            payload={"obligations": [_obligation(oid) for oid in _refs(raw)]}, prompt="Compile.",
            worker_cache={"v3": {"acceptances": []}, "v3-schema-repair": raw})


def test_inline_cloned_oracles_still_fail_domain_validation(tmp_path):
    raw = _inline()
    raw["obligation_contracts"]["O-001"]["acceptance"] = deepcopy(raw["obligation_contracts"]["O-000"]["acceptance"])
    with pytest.raises(ValueError, match="cloned-oracle-across-obligations"):
        grouped.group_repair_transport(
            root=tmp_path, out_dir=tmp_path / "plan", stage="v3-schema-repair", prompt="Repair.",
            payload={"input": {"obligations": [_obligation(oid) for oid in _refs(raw)]}},
            worker_cache={"v3-schema-repair": raw})


def test_missing_only_completion_consumes_inline_contract_without_rewriting_existing(tmp_path):
    raw = _inline()
    initial_raw = {"obligation_contracts": {"O-000": raw["obligation_contracts"]["O-000"]}}
    missing_raw = {"obligation_contracts": {"O-001": raw["obligation_contracts"]["O-001"]}}
    initial = grouped._project(initial_raw)
    result = total.complete_total_coverage(
        root=tmp_path, out_dir=tmp_path / "plan", stage="v3",
        payload={"obligations": [_obligation(oid) for oid in _refs(raw)]}, value=initial,
        worker_cache={"v3-coverage-completion": missing_raw})
    assert len(result["acceptances"]) == 2
    assert result["acceptances"][0] == initial["acceptances"][0]
    assert result["acceptances"][1]["obligation_ids"] == ["O-001"]


def test_live_transport_uses_inline_schema_then_reuses_cache_without_backend(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS.parents[3] / "scripts/sc"))
    import _llm_backend
    raw = _inline()
    calls = []
    def fake_exec(**kwargs):
        calls.append(kwargs)
        schema = json.loads(Path(kwargs["codex_extra_args"][1]).read_text(encoding="utf-8"))
        assert set(schema["properties"]) == {"obligation_contracts"}
        assert "Each value must reference one returned group_id" not in kwargs["prompt"]
        kwargs["output_last_message"].write_text(json.dumps(raw), encoding="utf-8")
        return 0, "OK", []
    monkeypatch.setattr(_llm_backend, "resolve_llm_backend", lambda _: "codex-cli")
    monkeypatch.setattr(_llm_backend, "run_llm_exec", fake_exec)
    args = dict(root=tmp_path, out_dir=tmp_path / "plan", prompt="Repair.",
                payload={"input": {"obligations": [_obligation(oid) for oid in _refs(raw)]}})
    first = grouped._live_group_repair(**args)
    second = grouped._live_group_repair(**args)
    assert first == second == grouped._project(raw, refs_by_oid=_refs(raw))
    assert len(calls) == 1


def test_historical_dangling_assignments_still_fail_closed():
    # Same failure class reported by the user; no invented copy of their raw output.
    raw = _inline(38)
    contracts = deepcopy(raw["obligation_contracts"])
    hint = contracts["O-000"]["slice_hint"]
    for contract in contracts.values():
        del contract["slice_hint"]
    legacy = {"groups": [{"group_id": "O-000", "slice_hint": hint}],
              "obligation_contracts": contracts,
              "obligation_group_assignments": {oid: oid for oid in contracts}}
    with pytest.raises(ValueError, match="assignments reference unknown groups"):
        grouped._project(legacy, refs_by_oid=_refs(raw))


def test_current_wire_cannot_fall_back_to_legacy_group_contract():
    with pytest.raises(ValueError, match="requires inline obligation_contracts"):
        grouped._project_current_output({"groups": [_raw_group(["O-000"])]}, {"O-000": ["req.md#FR-1"]})
