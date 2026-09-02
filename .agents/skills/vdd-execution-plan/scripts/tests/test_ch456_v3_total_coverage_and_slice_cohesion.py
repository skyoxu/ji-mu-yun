from __future__ import annotations

from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_feasibility_patch  # noqa: F401  # installs stable composition
import semantic_slice_cohesion_patch as cohesion
import semantic_worker_v3_execution_contract_patch as execution_contract
import semantic_worker_v3_explicit_path_contract_patch as path_contract
import semantic_worker_v3_group_repair_patch as grouped
import semantic_worker_v3_total_coverage_patch as total
import semantic_worker_v4_domain_patch as v4_domain


def _obligation(
    oid: str,
    *,
    subject: str = "idempotency ledger",
    state_before: str = "entry absent",
    state_after: str = "entry recorded",
) -> dict:
    return {
        "obligation_id": oid,
        "requirement_id": "FR-1",
        "source_refs": ["req.md#FR-1"],
        "subject": subject,
        "trigger": "when the ledger is updated",
        "state_before": state_before,
        "state_after": state_after,
        "expected_behavior": f"preserve behavior for {oid}",
        "observable_result": f"observable {oid}",
        "forbidden_result": [],
        "requirement_type": "Product",
        "obligation_kind": "behavior",
        "unresolved_fragments": [],
        "status": "active",
        "depends_on": [],
    }


def _acceptance(oid: str, aid: str) -> dict:
    return {
        "obligation_ids": [oid],
        "source_refs": ["req.md#FR-1"],
        "given": "a ledger operation",
        "when": "the operation is repeated",
        "then": f"{oid} remains satisfied",
        "oracle": {"observable": f"observable {oid}", "expected": "stable", "forbidden": []},
        "assertion_ids": [f"ASSERT-{oid}"],
        "acceptance_id": aid,
        "red_intent_ids": [f"FI-{oid}"],
    }


def _raw_group(oid: str, *, snapshot: str = "tests/test_ledger.py") -> dict:
    return {
        "obligation_ids": [oid],
        "acceptance": {
            "source_refs": ["req.md#FR-1"],
            "given": "a ledger operation",
            "when": "the operation is repeated",
            "then": f"{oid} remains satisfied",
            "oracle": {"observable": f"observable {oid}", "expected": "stable", "forbidden": []},
            "assertion_ids": [f"ASSERT-{oid}"],
        },
        "failure_intents": [{
            "failure_family": "expected-red",
            "selector_intent": snapshot,
            "expected_outcome": "fail",
            "failure_id": f"RED-{oid}",
        }],
        "slice_hint": {
            "production_owners": ["src/ledger.py"],
            "verification_lane": "unit",
            "behavior_change": f"implement {oid}",
            "affected_subjects": ["idempotency ledger"],
            "state_transition": "unimplemented->implemented",
            "rollback_scope": {
                "production_paths": ["src/ledger.py"],
                "state_or_schema_compatibility": "backward-compatible",
            },
            "allowed_write_paths": ["src/ledger.py", snapshot],
            "execution_snapshot_paths": [snapshot],
            "planned_new_files": [snapshot],
            "terminal_predicate": f"{oid} passes",
            "forbidden_paths": [],
            "validation_commands": [[sys.executable, "-m", "pytest", snapshot, "-q"]],
        },
    }


def test_v3_repair_completes_only_missing_active_obligations(monkeypatch, tmp_path: Path) -> None:
    payload = {
        "input": {"obligations": [_obligation("O-1"), _obligation("O-2")]},
        "original_stage": "v3",
        "validator_findings": ["v3-contract:hard-uncovered:O-2"],
    }
    base = {
        "acceptances": [{
            "obligation_ids": ["O-1"],
            "source_refs": ["req.md#FR-1"],
            "given": "g",
            "when": "w",
            "then": "t",
            "oracle": {"observable": "o", "expected": "e", "forbidden": []},
            "assertion_ids": ["ASSERT-O-1"],
        }],
        "failure_intents": [{
            "obligation_ids": ["O-1"],
            "failure_family": "expected-red",
            "selector_intent": "tests/test_ledger.py",
            "expected_outcome": "fail",
            "failure_id": "RED-O-1",
        }],
        "slice_hints": [_raw_group("O-1")["slice_hint"] | {"obligation_ids": ["O-1"]}],
    }

    monkeypatch.setattr(
        total,
        "_complete_missing",
        lambda **kwargs: grouped._project({"groups": [_raw_group(next(iter(kwargs["missing"]))) ]}),
    )
    monkeypatch.setattr(
        total.path_contract,
        "normalize_explicit_path_contracts",
        lambda _root, _stage, _payload, value: value,
    )

    result = total.complete_total_coverage(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v3-schema-repair",
        payload=payload,
        value=base,
        worker_cache=None,
    )
    covered = {
        oid
        for acceptance in result["acceptances"]
        for oid in acceptance["obligation_ids"]
    }
    assert covered == {"O-1", "O-2"}
    assert len(result["acceptances"]) == 2


def test_repair_group_schema_and_projection_are_atomic() -> None:
    payload = {"input": {"obligations": [_obligation("O-1"), _obligation("O-2")]}}
    schema = grouped._group_schema(payload)
    ids_schema = schema["properties"]["groups"]["items"]["properties"]["obligation_ids"]
    assert ids_schema["minItems"] == 1
    assert ids_schema["maxItems"] == 1
    assert ids_schema["uniqueItems"] is True
    with pytest.raises(ValueError, match="exactly one obligation"):
        grouped._project({"groups": [{**_raw_group("O-1"), "obligation_ids": ["O-1", "O-2"]}]})


def test_execution_contract_catches_same_subject_independent_state_shapes(tmp_path: Path) -> None:
    obligations = [
        _obligation("O-1", state_before="absent", state_after="present"),
        _obligation("O-2", state_before="present", state_after="archived"),
    ]
    value = {
        "acceptances": [{"obligation_ids": ["O-1", "O-2"]}],
        "failure_intents": [],
        "slice_hints": [],
    }
    findings = execution_contract._findings(tmp_path, "v3", {"obligations": obligations}, value)
    assert "v3-contract:acceptances[0]:overbroad-independent-behavior" in findings


def test_total_coverage_preserves_transport_composition() -> None:
    assert execution_contract._BASE_TRANSPORT is path_contract.explicit_path_contract_transport
    assert v4_domain._BASE_TRANSPORT is execution_contract.execution_contract_transport


def _hint(snapshot: str, *, owner: str = "src/ledger.py", forbidden: list[str] | None = None) -> dict:
    return {
        "obligation_ids": [],
        "production_owners": [owner],
        "verification_lane": "unit",
        "behavior_change": "implement idempotent ledger behavior",
        "affected_subjects": ["idempotency ledger"],
        "state_transition": "unimplemented->implemented",
        "rollback_scope": {
            "production_paths": [owner],
            "state_or_schema_compatibility": "backward-compatible",
        },
        "allowed_write_paths": [owner, snapshot],
        "execution_snapshot_paths": [snapshot],
        "planned_new_files": [snapshot],
        "terminal_predicate": f"{snapshot} passes",
        "forbidden_paths": forbidden or [],
        "validation_commands": [[sys.executable, "-m", "pytest", snapshot, "-q"]],
    }


def test_cohesive_partition_unions_compatible_same_root_hints() -> None:
    acceptances = [_acceptance("O-1", "A-1"), _acceptance("O-2", "A-2")]
    failures = [
        {"failure_intent_id": "FI-O-1", "acceptance_ids": ["A-1"], "failure_family": "expected-red", "selector_intent": "tests/test_ledger_a.py"},
        {"failure_intent_id": "FI-O-2", "acceptance_ids": ["A-2"], "failure_family": "expected-red", "selector_intent": "tests/test_ledger_b.py"},
    ]
    hint1 = _hint("tests/test_ledger_a.py") | {"obligation_ids": ["O-1"]}
    hint2 = _hint("tests/test_ledger_b.py") | {"obligation_ids": ["O-2"]}

    slices, _ = cohesion.cohesive_partition_slices(
        [_obligation("O-1"), _obligation("O-2")],
        acceptances,
        failures,
        [hint1, hint2],
    )

    assert len(slices) == 1
    assert slices[0]["acceptance_ids"] == ["A-1", "A-2"]
    assert slices[0]["execution_snapshot_paths"] == ["tests/test_ledger_a.py", "tests/test_ledger_b.py"]
    assert " AND " in slices[0]["terminal_predicate"]


def test_cohesive_partition_keeps_real_boundary_separate() -> None:
    acceptances = [_acceptance("O-1", "A-1"), _acceptance("O-2", "A-2")]
    failures = [
        {"failure_intent_id": "FI-O-1", "acceptance_ids": ["A-1"], "failure_family": "expected-red", "selector_intent": "tests/unit/test_a.py"},
        {"failure_intent_id": "FI-O-2", "acceptance_ids": ["A-2"], "failure_family": "expected-red", "selector_intent": "tests/integration/test_b.py"},
    ]
    hint1 = _hint("tests/unit/test_a.py") | {"obligation_ids": ["O-1"]}
    hint2 = _hint("tests/integration/test_b.py") | {"obligation_ids": ["O-2"]}

    slices, _ = cohesion.cohesive_partition_slices(
        [_obligation("O-1"), _obligation("O-2")],
        acceptances,
        failures,
        [hint1, hint2],
    )
    assert len(slices) == 2
