from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_compiler_gate as gate
import semantic_feasibility_patch  # noqa: F401  # installs stable V3 repair chain
from semantic_worker_v3_execution_contract_patch import (
    _authorized_planned_test_paths,
    _findings,
    _normalize_production_write_sets,
)
from semantic_worker_v3_path_grounding_patch import ground_v3_paths
from semantic_worker_v3_write_set_projection_patch import project_with_owner_write_set


def _obligation(oid: str, *, subject: str = "ledger") -> dict:
    return {
        "obligation_id": oid,
        "requirement_id": "FR-1",
        "source_refs": ["req.md#FR-1"],
        "subject": subject,
        "trigger": "operation",
        "state_before": "before",
        "state_after": "after",
        "expected_behavior": f"behavior {oid}",
        "observable_result": f"observable {oid}",
        "forbidden_result": [],
        "requirement_type": "Product",
        "obligation_kind": "behavior",
        "unresolved_fragments": [],
        "status": "active",
        "depends_on": [],
    }


def _acceptance(ids: list[str]) -> dict:
    return {
        "obligation_ids": ids,
        "source_refs": ["req.md#FR-1"],
        "given": "ledger state",
        "when": "the operation runs",
        "then": "the required behavior is observable",
        "oracle": {"observable": "result", "expected": "required", "forbidden": ["wrong"]},
        "assertion_ids": ["ASSERT-LEDGER"],
    }


def _failure(ids: list[str]) -> dict:
    return {
        "obligation_ids": ids,
        "failure_family": "expected-red",
        "selector_intent": "tests/test_owner.py",
        "expected_outcome": "fail",
        "failure_id": "LEDGER-RED",
    }


def _hint(ids: list[str], *, allowed: list[str], planned: list[str], forbidden: list[str] | None = None) -> dict:
    return {
        "obligation_ids": ids,
        "production_owners": ["src/owner.py"],
        "verification_lane": "unit",
        "behavior_change": "implement ledger behavior",
        "affected_subjects": ["ledger"],
        "state_transition": "before->after",
        "rollback_scope": {
            "production_paths": ["src/owner.py"],
            "state_or_schema_compatibility": "backward-compatible",
        },
        "allowed_write_paths": allowed,
        "execution_snapshot_paths": ["tests/test_owner.py"],
        "planned_new_files": planned,
        "terminal_predicate": "all bound assertions pass",
        "forbidden_paths": list(forbidden or []),
        "validation_commands": [[sys.executable, "-m", "pytest", "tests/test_owner.py", "-q"]],
    }


def test_v3_contract_routes_missing_coverage_and_path_defects_through_one_grouped_repair(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "owner.py").write_text("VALUE = 1\n", encoding="utf-8")
    obligations = [_obligation("O-1"), _obligation("O-2")]
    initial = {
        "acceptances": [_acceptance(["O-1"])],
        "failure_intents": [_failure(["O-1"])],
        "slice_hints": [_hint(["O-1"], allowed=[], planned=[])],
    }
    # ADR-0041: each obligation owns its oracle; only execution context is shared.
    contracts = {}
    for obligation in obligations:
        oid = obligation["obligation_id"]
        acceptance = _acceptance([oid])
        acceptance["then"] = obligation["expected_behavior"]
        acceptance["oracle"]["expected"] = obligation["observable_result"]
        acceptance["assertion_ids"] = [f"ASSERT-{oid}"]
        failure = _failure([oid])
        failure["failure_id"] = f"FAIL-{oid}"
        # Keep the original defect: owner declared but omitted from the write set.
        hint = _hint([oid], allowed=[], planned=["tests/test_owner.py"])
        contracts[oid] = {
            "acceptance": {key: value for key, value in acceptance.items() if key != "obligation_ids"},
            "failure_intents": [{key: value for key, value in failure.items() if key != "obligation_ids"}],
            "slice_hint": {key: value for key, value in hint.items() if key != "obligation_ids"},
        }
    repaired = {"obligation_contracts": contracts}
    result = gate.normative_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v3",
        payload={"obligations": obligations},
        prompt="Compile Acceptance, RED intent and slice hints.",
        worker_cache={"v3": initial, "v3-schema-repair": repaired},
    )
    assert [item["obligation_ids"] for item in result["acceptances"]] == [["O-1"], ["O-2"]]
    assert [item["obligation_ids"] for item in result["failure_intents"]] == [["O-1"], ["O-2"]]
    assert [item["obligation_ids"] for item in result["slice_hints"]] == [["O-1"], ["O-2"]]
    assert [item["oracle"]["expected"] for item in result["acceptances"]] == ["observable O-1", "observable O-2"]
    assert all(item["allowed_write_paths"] == ["src/owner.py"] for item in result["slice_hints"])
    assert all(item["planned_new_files"] == ["tests/test_owner.py"] for item in result["slice_hints"])


def test_v3_contract_catches_overbroad_subject_before_v3a(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "owner.py").write_text("VALUE = 1\n", encoding="utf-8")
    obligations = [_obligation("O-1", subject="ledger"), _obligation("O-2", subject="unrelated audit")]
    candidate = {
        "acceptances": [_acceptance(["O-1", "O-2"])],
        "failure_intents": [_failure(["O-1", "O-2"])],
        "slice_hints": [_hint(["O-1", "O-2"], allowed=["src/owner.py"], planned=["tests/test_owner.py"])],
    }
    findings = _findings(tmp_path, "v3", {"obligations": obligations}, candidate)
    assert any("overbroad-subject" in item for item in findings)


def test_repaired_owner_overlap_is_removed_from_forbidden() -> None:
    raw = {
        "groups": [
            {
                "obligation_ids": ["O-1"],
                "acceptance": {key: value for key, value in _acceptance(["O-1"]).items() if key != "obligation_ids"},
                "failure_intents": [{key: value for key, value in _failure(["O-1"]).items() if key != "obligation_ids"}],
                "slice_hint": {
                    key: value
                    for key, value in _hint(
                        ["O-1"],
                        allowed=[],
                        planned=["tests/test_owner.py"],
                        forbidden=["src/owner.py"],
                    ).items()
                    if key != "obligation_ids"
                },
            }
        ]
    }
    result = project_with_owner_write_set(raw)
    assert result["slice_hints"][0]["allowed_write_paths"] == ["src/owner.py"]
    assert result["slice_hints"][0]["forbidden_paths"] == []


def _repair_payload(*, source_text: str = "PhaseB.Repair.IdentityBoundaryTests", snapshot: str = "PhaseA.Platform.Tests/PhaseB/Repair/IdentityBoundaryTests.cs") -> tuple[dict, dict]:
    obligation = _obligation("O-1")
    obligation["source_refs"] = ["repair.md#S0"]
    payload = {
        "obligations": [obligation],
        "source_contracts": [{"source_ref": "repair.md#S0", "source_text": source_text}],
    }
    value = {"slice_hints": [{**_hint(["O-1"], allowed=["src/owner.py"], planned=[]), "execution_snapshot_paths": [snapshot]}]}
    return payload, value


def test_authorized_future_repair_test_is_planned_but_not_treated_as_evidence() -> None:
    payload, value = _repair_payload()
    projected = _authorized_planned_test_paths("v3", payload, value)
    hint = projected["slice_hints"][0]
    assert hint["planned_new_files"] == ["PhaseA.Platform.Tests/PhaseB/Repair/IdentityBoundaryTests.cs"]
    assert hint["execution_snapshot_paths"] == ["PhaseA.Platform.Tests/PhaseB/Repair/IdentityBoundaryTests.cs"]


def test_unlisted_or_directory_repair_paths_are_not_authorized() -> None:
    for snapshot in (
        "PhaseA.Platform.Tests/",
        "PhaseA.Platform.Tests/Workspaces/RestoreServiceTests.cs",
        "PhaseA.Platform.Tests/PhaseB/Repair/OtherBoundaryTests.cs",
    ):
        payload, value = _repair_payload(snapshot=snapshot)
        projected = _authorized_planned_test_paths("v3", payload, value)
        assert projected == value


def test_matching_path_without_frozen_lane_authority_is_not_authorized() -> None:
    payload, value = _repair_payload(source_text="PhaseB.Repair.OtherTests")
    projected = _authorized_planned_test_paths("v3", payload, value)
    assert projected == value


def test_missing_production_owner_remains_a_contract_failure(tmp_path: Path) -> None:
    obligations = [_obligation("O-1")]
    candidate = {"slice_hints": [_hint(["O-1"], allowed=["src/owner.py"], planned=["tests/test_owner.py"])]}
    findings = _findings(tmp_path, "v3", {"obligations": obligations}, candidate)
    assert any(item.startswith("v3-contract:slice_hints[0]:no-real-production-entry") for item in findings)


def test_path_grounding_projects_only_explicit_legacy_repair_test_path(tmp_path: Path) -> None:
    payload, value = _repair_payload(
        source_text="PhaseB.Repair.RestoreBoundaryTests",
        snapshot="PhaseA.Platform.Tests/Workspaces/RestoreServiceTests.cs",
    )
    value["slice_hints"][0]["planned_new_files"] = ["PhaseA.Platform.Tests/Repair/RestoreBoundaryTests.cs"]
    grounded, changes = ground_v3_paths(tmp_path, payload, value)
    hint = grounded["slice_hints"][0]
    expected = "PhaseA.Platform.Tests/PhaseB/Repair/RestoreBoundaryTests.cs"
    assert hint["execution_snapshot_paths"] == [expected]
    assert hint["planned_new_files"] == [expected]
    assert changes


def test_path_grounding_does_not_guess_by_basename_or_map_directory_without_authority(tmp_path: Path) -> None:
    payload, value = _repair_payload(
        source_text="unrelated source",
        snapshot="PhaseA.Platform.Tests/",
    )
    grounded, changes = ground_v3_paths(tmp_path, payload, value)
    assert grounded == value
    assert changes == []
    payload, value = _repair_payload(snapshot="PhaseA.Platform.Tests/Other/RestoreBoundaryTests.cs")
    grounded, changes = ground_v3_paths(tmp_path, payload, value)
    assert grounded == value
    assert changes == []


def test_path_grounding_drops_test_owner_but_never_invents_production_owner(tmp_path: Path) -> None:
    payload, value = _repair_payload()
    hint = value["slice_hints"][0]
    hint["production_owners"] = ["PhaseA.Platform.Tests/PhaseB/Repair/IdentityBoundaryTests.cs"]
    value = _authorized_planned_test_paths("v3", payload, value)
    value = _normalize_production_write_sets(tmp_path, value)
    grounded, _ = ground_v3_paths(tmp_path, payload, value)
    assert grounded["slice_hints"][0]["production_owners"] == []
    assert any(item.startswith("v3-contract:slice_hints[0]:no-real-production-entry") for item in _findings(tmp_path, "v3", payload, grounded))


def test_existing_route_operation_governance_test_uses_real_evidence_owners(tmp_path: Path) -> None:
    for path in (
        "PhaseA.Platform/Workflow/RouteOperationPreflight.cs",
        "PhaseA.Platform/Workflow/SecretRedactionPolicy.cs",
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("class ProductionEntry {}\n", encoding="utf-8")
    payload, value = _repair_payload(
        source_text="SM-A08 Evidence_CorrelatesAndRedactsAllOperations",
        snapshot="PhaseA.Platform.Tests/Workflow/RouteOperationGovernanceTests.cs",
    )
    value["slice_hints"][0]["production_owners"] = [
        "PhaseA.Platform.Tests/Workflow/RouteOperationGovernanceTests.cs"
    ]
    value = _authorized_planned_test_paths("v3", payload, value)
    value = _normalize_production_write_sets(tmp_path, value)
    grounded, _ = ground_v3_paths(tmp_path, payload, value)
    hint = grounded["slice_hints"][0]
    assert hint["production_owners"] == [
        "PhaseA.Platform/Workflow/RouteOperationPreflight.cs",
        "PhaseA.Platform/Workflow/SecretRedactionPolicy.cs",
    ]
    assert hint["planned_new_files"] == []


def test_path_grounding_only_maps_explicit_stale_production_path(tmp_path: Path) -> None:
    production = tmp_path / "PhaseA.Platform" / "Workspaces"
    production.mkdir(parents=True)
    (production / "RestoreService.cs").write_text("class RestoreService {}\n", encoding="utf-8")
    payload, value = _repair_payload()
    value["slice_hints"][0]["production_owners"] = ["PhaseA.Platform/Services/RestoreService.cs"]
    grounded, _ = ground_v3_paths(tmp_path, payload, value)
    assert grounded["slice_hints"][0]["production_owners"] == ["PhaseA.Platform/Workspaces/RestoreService.cs"]


def test_path_grounding_maps_restore_recovery_selector_only_for_sm_r07(tmp_path: Path) -> None:
    payload, value = _repair_payload(
        source_text="SM-R07 RestoreBoundaryTests",
        snapshot="PhaseA.Platform.Tests/Security/RestoreRecoveryTests.cs",
    )
    grounded, changes = ground_v3_paths(tmp_path, payload, value)
    assert grounded["slice_hints"][0]["execution_snapshot_paths"] == [
        "PhaseA.Platform.Tests/PhaseB/Repair/RestoreBoundaryTests.cs"
    ]
    assert changes
