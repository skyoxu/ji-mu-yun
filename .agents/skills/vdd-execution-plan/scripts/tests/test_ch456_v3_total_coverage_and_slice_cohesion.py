from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_feasibility_patch  # noqa: F401
import semantic_slice_cohesion_patch as cohesion
import semantic_worker_v3_execution_contract_patch as execution_contract
import semantic_worker_v3_explicit_path_contract_patch as path_contract
import semantic_worker_v3_group_repair_patch as grouped
import semantic_worker_v3_total_coverage_patch as total
import semantic_worker_v4_domain_patch as v4_domain


def _obligation(oid: str, *, state_before: str = "entry absent", state_after: str = "entry recorded", depends_on: list[str] | None = None) -> dict:
    return {
        "obligation_id": oid, "requirement_id": "FR-1", "source_refs": ["req.md#FR-1"],
        "subject": "idempotency ledger", "trigger": "when the ledger is updated",
        "state_before": state_before, "state_after": state_after,
        "expected_behavior": f"preserve behavior for {oid}", "observable_result": f"observable {oid}",
        "forbidden_result": [], "requirement_type": "Product", "obligation_kind": "behavior",
        "unresolved_fragments": [], "status": "active", "depends_on": depends_on or [],
    }


def _acceptance(oid: str, aid: str) -> dict:
    return {
        "obligation_ids": [oid], "source_refs": ["req.md#FR-1"], "given": "a ledger operation",
        "when": "the operation is repeated", "then": f"{oid} remains satisfied",
        "oracle": {"observable": f"observable {oid}", "expected": "stable", "forbidden": []},
        "assertion_ids": [f"ASSERT-{oid}"], "acceptance_id": aid, "red_intent_ids": [f"FI-{oid}"],
    }


def _hint(snapshot: str, *, transition: str = "unimplemented->implemented") -> dict:
    return {
        "obligation_ids": [], "production_owners": ["src/ledger.py"], "verification_lane": "unit",
        "behavior_change": "implement idempotent ledger behavior", "affected_subjects": ["idempotency ledger"],
        "state_transition": transition,
        "rollback_scope": {"production_paths": ["src/ledger.py"], "state_or_schema_compatibility": "backward-compatible"},
        "allowed_write_paths": ["src/ledger.py", snapshot], "execution_snapshot_paths": [snapshot],
        "planned_new_files": [snapshot], "terminal_predicate": f"{snapshot} passes", "forbidden_paths": [],
        "validation_commands": [[sys.executable, "-m", "pytest", snapshot, "-q"]],
    }


def _raw_group(ids: list[str], *, snapshot: str = "tests/test_ledger.py") -> dict:
    return {
        "obligation_ids": ids,
        "acceptance": {
            "source_refs": ["req.md#FR-1"], "given": "a ledger operation", "when": "the operation is repeated",
            "then": "the grouped behavior remains satisfied",
            "oracle": {"observable": "ledger state", "expected": "stable", "forbidden": []},
            "assertion_ids": ["ASSERT-LEDGER"],
        },
        "failure_intents": [{"failure_family": "expected-red", "selector_intent": snapshot, "expected_outcome": "fail", "failure_id": "RED-LEDGER"}],
        "slice_hint": _hint(snapshot),
    }


def _raw_v3(ids: list[str], *, snapshot: str = "tests/test_ledger.py") -> dict:
    group = _raw_group(ids, snapshot=snapshot)
    return {
        "acceptances": [{"obligation_ids": ids, **group["acceptance"]}],
        "failure_intents": [{"obligation_ids": ids, **group["failure_intents"][0]}],
        "slice_hints": [{**group["slice_hint"], "obligation_ids": ids}],
    }


def test_shared_group_projects_exact_assignments_to_atomic_acceptances() -> None:
    payload = {"input": {"obligations": [_obligation("O-1"), _obligation("O-2")]}}
    schema = grouped._group_schema(payload)
    assignment_schema = schema["properties"]["obligation_contracts"]
    assert set(assignment_schema["properties"]) == {"O-1", "O-2"}
    assert set(assignment_schema["required"]) == {"O-1", "O-2"}
    assert assignment_schema["additionalProperties"] is False
    assert "uniqueItems" not in str(schema)

    shared = _raw_group(["O-1", "O-2"])
    del shared["obligation_ids"]
    shared["group_id"] = "O-1"
    del shared["acceptance"], shared["failure_intents"]
    contracts = {}
    for oid in ("O-1", "O-2"):
        raw = _raw_group([oid])
        raw["acceptance"]["oracle"]["observable"] = f"observable {oid}"
        raw["acceptance"]["assertion_ids"] = [f"ASSERT-{oid}"]
        contracts[oid] = {"acceptance": raw["acceptance"], "failure_intents": raw["failure_intents"]}
    shared["slice_hint"]["allowed_write_paths"] = []
    projected = grouped._project(
        {
            "groups": [shared],
            "obligation_group_assignments": {"O-1": "O-1", "O-2": "O-1"},
            "obligation_contracts": contracts,
        },
        refs_by_oid={"O-1": ["req.md#FR-1"], "O-2": ["req.md#FR-1"]},
    )
    assert [a["obligation_ids"] for a in projected["acceptances"]] == [["O-1"], ["O-2"]]
    assert projected["slice_hints"][0]["production_owners"] == projected["slice_hints"][1]["production_owners"] == ["src/ledger.py"]
    assert projected["slice_hints"][0]["allowed_write_paths"] == projected["slice_hints"][1]["allowed_write_paths"] == ["src/ledger.py"]


def test_grouped_repair_rejects_duplicate_ids_deterministically() -> None:
    duplicate = _raw_group(["O-1", "O-1"])
    try:
        grouped._project({"groups": [duplicate]})
    except ValueError as exc:
        assert str(exc) == "V3 group repair group 0 has duplicate obligation_ids"
    else:
        raise AssertionError("duplicate obligation ids must fail closed")


def test_exact_assignments_reject_missing_frozen_obligation() -> None:
    shared = _raw_group(["O-1"])
    del shared["obligation_ids"]
    shared["group_id"] = "O-1"
    try:
        grouped._project(
            {
                "groups": [shared],
                "obligation_group_assignments": {"O-1": "O-1"},
            },
            refs_by_oid={"O-1": ["req.md#FR-1"], "O-2": ["req.md#FR-1"]},
        )
    except ValueError as exc:
        assert str(exc) == "V3 group repair assignments differ from frozen obligations: missing=O-2"
    else:
        raise AssertionError("missing exact assignment must fail closed")


def test_exact_assignments_reject_unknown_group_reference() -> None:
    shared = _raw_group(["O-1"])
    del shared["obligation_ids"]
    shared["group_id"] = "O-1"
    try:
        grouped._project({
            "groups": [shared],
            "obligation_group_assignments": {"O-1": "O-1", "O-2": "O-2"},
        })
    except ValueError as exc:
        assert str(exc) == "V3 group repair assignments reference unknown groups: O-2"
    else:
        raise AssertionError("unknown group reference must fail closed")


def test_legacy_conflicting_cross_group_duplicate_remains_rejected() -> None:
    first = _raw_group(["O-1"])
    second = _raw_group(["O-1"])
    second["slice_hint"]["behavior_change"] = "conflicting behavior"
    try:
        grouped._project({"groups": [first, second]})
    except ValueError as exc:
        assert str(exc) == "V3 group repair obligation appears in multiple groups: O-1"
    else:
        raise AssertionError("legacy cross-group duplicate must fail closed")


def test_initial_v3_shared_oracle_requires_semantic_repair_before_atomic_binding() -> None:
    # ADR-0041: changing IDs alone cannot make a shared oracle atomic.
    payload = {"obligations": [_obligation("O-1", state_before="absent", state_after="present"), _obligation("O-2", state_before="present", state_after="stable")]}
    raw = _raw_v3(["O-1", "O-2"])
    projected = execution_contract._atomicize_initial_candidate("v3", payload, raw)
    assert projected is raw
    findings = execution_contract._findings(Path("."), "v3", payload, projected)
    assert any("per-obligation-contract-required" in item for item in findings)
    assert any("overbroad-independent-behavior" in item for item in findings)


def test_initial_v3_overlapping_sets_are_not_silently_atomicized() -> None:
    payload = {"obligations": [_obligation("O-1"), _obligation("O-2"), _obligation("O-3")]}
    first = _raw_v3(["O-1", "O-2"])
    second = _raw_v3(["O-2", "O-3"])
    raw = {key: [*first[key], *second[key]] for key in first}
    assert execution_contract._atomicize_initial_candidate("v3", payload, raw) is raw


def test_v3_completion_runs_for_initial_stage_without_global_schema_repair(monkeypatch, tmp_path: Path) -> None:
    payload = {"obligations": [_obligation("O-1"), _obligation("O-2")]}
    base = _raw_v3(["O-1"])
    monkeypatch.setattr(total, "_complete_missing", lambda **kwargs: grouped._project({"groups": [_raw_group([next(iter(kwargs["missing"]))])]}))
    monkeypatch.setattr(total.path_contract, "normalize_explicit_path_contracts", lambda _root, _stage, _payload, value: value)
    result = total.complete_total_coverage(root=tmp_path, out_dir=tmp_path / "plan", stage="v3", payload=payload, value=base, worker_cache=None)
    assert {oid for a in result["acceptances"] for oid in a["obligation_ids"]} == {"O-1", "O-2"}


def test_v3_repair_completes_only_missing_active_obligations(monkeypatch, tmp_path: Path) -> None:
    payload = {"input": {"obligations": [_obligation("O-1"), _obligation("O-2")]}, "original_stage": "v3", "validator_findings": ["v3-contract:hard-uncovered:O-2"]}
    base = _raw_v3(["O-1"])
    monkeypatch.setattr(total, "_complete_missing", lambda **kwargs: grouped._project({"groups": [_raw_group([next(iter(kwargs["missing"]))])]}))
    monkeypatch.setattr(total.path_contract, "normalize_explicit_path_contracts", lambda _root, _stage, _payload, value: value)
    result = total.complete_total_coverage(root=tmp_path, out_dir=tmp_path / "plan", stage="v3-schema-repair", payload=payload, value=base, worker_cache=None)
    assert {oid for a in result["acceptances"] for oid in a["obligation_ids"]} == {"O-1", "O-2"}


def test_execution_contract_catches_same_acceptance_independent_state_shapes(tmp_path: Path) -> None:
    obligations = [_obligation("O-1", state_before="absent", state_after="present"), _obligation("O-2", state_before="present", state_after="archived")]
    findings = execution_contract._findings(tmp_path, "v3", {"obligations": obligations}, {"acceptances": [{"obligation_ids": ["O-1", "O-2"]}], "failure_intents": [], "slice_hints": []})
    assert "v3-contract:acceptances[0]:overbroad-independent-behavior" in findings


def test_total_coverage_preserves_transport_composition() -> None:
    assert execution_contract._BASE_TRANSPORT is path_contract.explicit_path_contract_transport
    assert v4_domain._BASE_TRANSPORT is execution_contract.execution_contract_transport


def test_cohesive_partition_ignores_model_transition_wording_for_same_real_boundary() -> None:
    acceptances = [_acceptance("O-1", "A-1"), _acceptance("O-2", "A-2")]
    failures = [
        {"failure_intent_id": "FI-O-1", "acceptance_ids": ["A-1"], "failure_family": "expected-red", "selector_intent": "tests/test_ledger_a.py"},
        {"failure_intent_id": "FI-O-2", "acceptance_ids": ["A-2"], "failure_family": "expected-red", "selector_intent": "tests/test_ledger_b.py"},
    ]
    hints = [{**_hint("tests/test_ledger_a.py", transition="absent->present"), "obligation_ids": ["O-1"]}, {**_hint("tests/test_ledger_b.py", transition="present->stable"), "obligation_ids": ["O-2"]}]
    slices, _ = cohesion.cohesive_partition_slices([_obligation("O-1"), _obligation("O-2")], acceptances, failures, hints)
    assert len(slices) == 1
    assert " AND " in slices[0]["state_transition"]


def test_cohesive_partition_ignores_evidence_fields_for_same_real_boundary() -> None:
    acceptances = [_acceptance("O-1", "A-1"), _acceptance("O-2", "A-2")]
    failures = [
        {"failure_intent_id": "FI-O-1", "acceptance_ids": ["A-1"], "failure_family": "expected-red", "selector_intent": "tests/unit/test_ledger_a.py"},
        {"failure_intent_id": "FI-O-2", "acceptance_ids": ["A-2"], "failure_family": "timeout-no-observation", "selector_intent": "tests/integration/test_ledger_b.py"},
    ]
    hints = [
        {**_hint("tests/unit/test_ledger_a.py", transition="absent->present"), "obligation_ids": ["O-1"]},
        {**_hint("tests/integration/test_ledger_b.py", transition="present->stable"), "obligation_ids": ["O-2"]},
    ]
    slices, _ = cohesion.cohesive_partition_slices(
        [_obligation("O-1"), _obligation("O-2")],
        acceptances,
        failures,
        hints,
    )
    assert len(slices) == 1
    assert slices[0]["failure_intent_ids"] == ["FI-O-1", "FI-O-2"]
    assert slices[0]["execution_snapshot_paths"] == [
        "tests/integration/test_ledger_b.py",
        "tests/unit/test_ledger_a.py",
    ]


def test_frozen_planned_red_authorization_removes_false_conflict_for_ten_atomic_acceptances() -> None:
    snapshot = "tests/test_ledger.py"
    obligations = [_obligation(f"O-{number}") for number in range(1, 11)]
    acceptances = [_acceptance(f"O-{number}", f"A-{number}") for number in range(1, 11)]
    failures = [
        {
            "failure_intent_id": f"FI-O-{number}",
            "acceptance_ids": [f"A-{number}"],
            "failure_family": "expected-red",
            "selector_intent": snapshot,
        }
        for number in range(1, 11)
    ]
    hints = [
        {
            **_hint(snapshot),
            "obligation_ids": [f"O-{number}"],
            "forbidden_paths": [snapshot, "requirements.md"],
        }
        for number in range(1, 11)
    ]
    raw_slices, _ = cohesion.cohesive_partition_slices(
        obligations,
        acceptances,
        failures,
        hints,
    )
    assert len(raw_slices) == 10

    source_text = f"""# FR-1
Production owner: `src/ledger.py`.
The RED author must create `{snapshot}`.
The production implementation may modify only the production owner above.
"""
    normalized = path_contract.normalize_explicit_path_contracts(
        Path("."),
        "v3",
        {
            "obligations": obligations,
            "source_contracts": [{"source_ref": "req.md#FR-1", "source_text": source_text}],
        },
        {"slice_hints": hints},
    )
    normalized_hints = normalized["slice_hints"]
    assert all(snapshot not in hint["forbidden_paths"] for hint in normalized_hints)
    assert all("requirements.md" in hint["forbidden_paths"] for hint in normalized_hints)

    slices, _ = cohesion.cohesive_partition_slices(
        obligations,
        acceptances,
        failures,
        normalized_hints,
    )
    assert len(slices) == 1
    assert len(slices[0]["acceptance_ids"]) == 10


def test_cohesive_partition_keeps_dependency_boundary_separate() -> None:
    acceptances = [_acceptance("O-1", "A-1"), _acceptance("O-2", "A-2")]
    failures = [
        {"failure_intent_id": "FI-O-1", "acceptance_ids": ["A-1"], "failure_family": "expected-red", "selector_intent": "tests/test_ledger_a.py"},
        {"failure_intent_id": "FI-O-2", "acceptance_ids": ["A-2"], "failure_family": "expected-red", "selector_intent": "tests/test_ledger_b.py"},
    ]
    hints = [{**_hint("tests/test_ledger_a.py"), "obligation_ids": ["O-1"]}, {**_hint("tests/test_ledger_b.py"), "obligation_ids": ["O-2"]}]
    slices, _ = cohesion.cohesive_partition_slices([_obligation("O-1"), _obligation("O-2", depends_on=["O-1"])], acceptances, failures, hints)
    assert len(slices) == 2
