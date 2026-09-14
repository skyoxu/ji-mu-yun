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


def test_aggregated_group_result_grounds_legacy_restore_owner(tmp_path):
    canonical = tmp_path / "PhaseA.Platform/Workspaces/RestoreService.cs"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("class RestoreService {}\\n", encoding="utf-8")
    oid = "O-restore"
    obligation = {"obligation_id": oid, "source_refs": ["req.md#FR-1"]}
    payload = {"input": {"obligations": [obligation], "source_contracts": [{
        "source_ref": "req.md#FR-1", "source_text": "RestoreBoundaryTests"
    }]}}
    value = {"slice_hints": [{
        "obligation_ids": [oid],
        "production_owners": ["PhaseA.Platform/Services/RestoreService.cs"],
        "execution_snapshot_paths": ["PhaseA.Platform.Tests/Repair/RestoreBoundaryTests.cs"],
        "planned_new_files": [],
    }]}
    grounded = grouped._ground_group_result(tmp_path, payload, value)
    hint = grounded["slice_hints"][0]
    assert hint["production_owners"] == ["PhaseA.Platform/Workspaces/RestoreService.cs"]
    assert hint["execution_snapshot_paths"] == ["PhaseA.Platform.Tests/PhaseB/Repair/RestoreBoundaryTests.cs"]


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
    raw = _inline(1)
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


def test_live_repair_chunks_large_frozen_obligation_sets(tmp_path: Path, monkeypatch) -> None:
    obligations = [_obligation(f"O-{index:03d}") for index in range(17)]
    calls: list[list[str]] = []

    def live_chunk(*, root, out_dir, payload, prompt, **_kwargs):
        chunk = grouped._repair_obligations(payload)
        calls.append([item["obligation_id"] for item in chunk])
        contracts = {}
        for item in chunk:
            oid = item["obligation_id"]
            contracts[oid] = _raw_group([oid])
            contracts[oid].pop("obligation_ids", None)
        return grouped._project_current_output(
            {"obligation_contracts": contracts}, grouped._obligation_refs(payload)
        )

    monkeypatch.setattr(grouped, "_MAX_OBLIGATIONS_PER_CALL", 8)
    monkeypatch.setattr(grouped, "_live_group_repair_one", live_chunk)
    combined = grouped._live_group_repair(
        root=tmp_path,
        out_dir=tmp_path,
        payload={"input": {"obligations": obligations}},
        prompt="p",
    )

    assert [len(call) for call in calls] == [8, 8, 1]
    assert len(combined["acceptances"]) == 17


def test_large_v3_call_uses_bounded_transport_before_full_worker(tmp_path: Path, monkeypatch) -> None:
    obligations = [_obligation(f"O-{index:03d}") for index in range(5)]
    projected = {
        "acceptances": [{"obligation_ids": [item["obligation_id"]]} for item in obligations],
        "failure_intents": [{"obligation_ids": [item["obligation_id"]]} for item in obligations],
        "slice_hints": [{"obligation_ids": [item["obligation_id"]]} for item in obligations],
    }
    calls: list[dict] = []

    def bounded(**kwargs):
        calls.append(kwargs["payload"])
        return projected

    monkeypatch.setattr(grouped, "_MAX_OBLIGATIONS_PER_CALL", 4)
    monkeypatch.setattr(grouped, "_live_group_repair", bounded)
    monkeypatch.setattr(grouped.v3_domain, "_domain_findings", lambda *args: [])

    result = grouped.group_repair_transport(
        root=tmp_path,
        out_dir=tmp_path,
        stage="v3",
        payload={"obligations": obligations},
        prompt="compile",
    )

    assert result == projected
    assert calls[0]["original_stage"] == "v3"
    assert calls[0]["input"]["obligations"] == obligations


def test_default_group_size_bounds_schema_without_single_obligation_serialization() -> None:
    assert grouped._MAX_OBLIGATIONS_PER_CALL == 4


def test_live_group_repair_retries_transient_worker_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(SCRIPTS.parents[3] / "scripts/sc"))
    import _llm_backend
    raw = _inline(1)
    attempts = []

    def fake_exec(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            return 124, "temporary transport timeout", []
        kwargs["output_last_message"].write_text(json.dumps(raw), encoding="utf-8")
        return 0, "OK", []

    monkeypatch.setattr(_llm_backend, "resolve_llm_backend", lambda _: "codex-cli")
    monkeypatch.setattr(_llm_backend, "run_llm_exec", fake_exec)
    result = grouped._live_group_repair(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        prompt="Repair.",
        payload={"input": {"obligations": [_obligation(oid) for oid in _refs(raw)]}},
    )
    assert result == grouped._project(raw, refs_by_oid=_refs(raw))
    assert len(attempts) == 2


def test_transient_multi_obligation_group_degrades_to_smaller_exact_groups(tmp_path: Path, monkeypatch) -> None:
    obligations = [_obligation("O-001"), _obligation("O-002")]
    calls: list[tuple[list[str], int | None]] = []

    def fake_one(*, root, out_dir, payload, prompt, max_attempts=None):
        chunk = grouped._repair_obligations(payload)
        ids = [item["obligation_id"] for item in chunk]
        calls.append((ids, max_attempts))
        if len(ids) > 1:
            raise grouped.TransientV3WorkerFailure("timeout")
        raw = {"obligation_contracts": {ids[0]: _raw_group(ids)}}
        raw["obligation_contracts"][ids[0]].pop("obligation_ids", None)
        return grouped._project_current_output(raw, grouped._obligation_refs(payload))

    monkeypatch.setattr(grouped, "_live_group_repair_one", fake_one)
    result = grouped._live_group_repair(
        root=tmp_path, out_dir=tmp_path, prompt="p",
        payload={"input": {"obligations": obligations}}, max_obligations=2,
    )
    assert [item["obligation_ids"] for item in result["slice_hints"]] == [["O-001"], ["O-002"]]
    assert calls[0] == (["O-001", "O-002"], 2)
    assert [ids for ids, _ in calls[1:]] == [["O-001"], ["O-002"]]


def test_group_cache_identity_ignores_discovery_context_and_repair_wrapper() -> None:
    semantic = {"obligations": [_obligation("O-001")], "source_contracts": [{"source_ref": "req.md#1"}]}
    direct = {**semantic, "repository_path_context": {"files": [{"path": "a.cs", "sha256": "one"}]}}
    repaired = {
        "original_stage": "v3",
        "validator_findings": ["path spelling"],
        "input": {**semantic, "repository_path_context": {"files": [{"path": "a.cs", "sha256": "two"}]}},
    }
    direct_identity = grouped.group_cache_identity_payload(direct)
    repaired_identity = grouped.group_cache_identity_payload(repaired)
    assert direct_identity == repaired_identity
    assert direct_identity["projection_contract"] == "vdd-v3-path-grounding-v2"
    assert {
        key: value for key, value in direct_identity.items() if key != "projection_contract"
    } == semantic


def test_group_cache_identity_changes_when_frozen_obligation_changes() -> None:
    first = {"obligations": [_obligation("O-001")]}
    second = {"obligations": [_obligation("O-002")]}
    assert grouped.group_cache_identity_payload(first) != grouped.group_cache_identity_payload(second)
