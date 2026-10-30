from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_compiler_gate as gate
import semantic_feasibility_patch  # noqa: F401  # installs stable V3 repair chain
import semantic_worker_v3_explicit_path_contract_patch as explicit_path
from semantic_worker_v3_execution_contract_patch import (
    _authorized_planned_test_paths,
    _findings,
    _normalize_expected_red_for_product_behavior,
    _normalize_production_write_sets,
    normalize_v3_cached_result,
    _selector_file_path,
    _PACKAGE_A_PLANNED_PRODUCTION,
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


def test_pytest_node_selector_uses_file_path_for_planned_target_check(tmp_path: Path) -> None:
    owner = tmp_path / "src" / "owner.py"
    owner.parent.mkdir(parents=True)
    owner.write_text("VALUE = 1\n", encoding="utf-8")
    value = {"slice_hints": [{
        **_hint(["O-1"], allowed=["src/owner.py", "scripts/sc/tests/test_quality.py"],
                planned=["scripts/sc/tests/test_quality.py"]),
        "production_owners": ["src/owner.py"],
        "execution_snapshot_paths": ["scripts/sc/tests/test_quality.py::test_a04"],
    }]}
    assert _selector_file_path("scripts/sc/tests/test_quality.py::test_a04") == "scripts/sc/tests/test_quality.py"
    findings = _findings(tmp_path, "v3", {"obligations": [_obligation("O-1")]}, value)
    assert not any("selector-target-missing-not-planned" in item for item in findings)


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


def test_planned_non_test_production_owner_is_valid_when_write_authorized(tmp_path: Path) -> None:
    obligations = [_obligation("O-1")]
    owner = "scripts/sc/new_validator.py"
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=[owner], planned=[owner, "tests/test_owner.py"]),
        "production_owners": [owner],
    }]}
    findings = _findings(tmp_path, "v3", {"obligations": obligations}, candidate)
    assert not any("no-real-production-entry" in item for item in findings)


def test_package_a_declared_future_owner_is_projected_as_planned(tmp_path: Path) -> None:
    owner = "scripts/sc/validate_skill_quality.py"
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=[owner], planned=["tests/test_owner.py"]),
        "production_owners": [owner],
    }]}
    projected = _normalize_production_write_sets(tmp_path, candidate)
    hint = projected["slice_hints"][0]
    assert owner in hint["planned_new_files"]
    assert not any("no-real-production-entry" in item for item in _findings(
        tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected
    ))


def test_grouped_repair_preserves_explicit_package_a_test_only_hint(tmp_path: Path) -> None:
    candidate = {"slice_hints": [{
        **_hint(
            ["O-1"],
            allowed=["scripts/sc/tests/test_skill_quality_core.py"],
            planned=["scripts/sc/tests/test_skill_quality_core.py"],
        ),
        "production_owners": [],
        "execution_snapshot_paths": ["scripts/sc/tests/test_skill_quality_core.py"],
    }]}
    projected = _normalize_production_write_sets(
        tmp_path, candidate, promote_package_a_selectors=True
    )
    hint = projected["slice_hints"][0]
    assert hint["production_owners"] == []
    assert hint["allowed_write_paths"] == ["scripts/sc/tests/test_skill_quality_core.py"]
    assert hint["planned_new_files"] == ["scripts/sc/tests/test_skill_quality_core.py"]
    assert not any("no-real-production-entry" in item for item in _findings(
        tmp_path, "v3-schema-repair-group-v7", {"obligations": [_obligation("O-1")]}, projected
    ))


def test_known_package_a_contract_test_selector_maps_to_its_real_validator_owner(tmp_path: Path) -> None:
    (tmp_path / "scripts/sc").mkdir(parents=True)
    scripts = tmp_path / ".agents/skills/vdd-execution-plan/scripts"
    scripts.mkdir(parents=True)
    (scripts / "validate_skill_contract.py").write_text("VALUE = 1\n", encoding="utf-8")
    snapshot = ".agents/skills/vdd-execution-plan/scripts/tests/test_validate_skill_contract.py"
    candidate = {"slice_hints": [{
        "obligation_ids": ["O-1"],
        "production_owners": [snapshot],
        "allowed_write_paths": [snapshot],
        "execution_snapshot_paths": [snapshot],
        "planned_new_files": [],
    }]}

    projected = _normalize_production_write_sets(tmp_path, candidate)
    hint = projected["slice_hints"][0]
    owner = ".agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py"
    assert hint["production_owners"] == [owner]
    assert owner in hint["allowed_write_paths"]
    assert not any("no-real-production-entry" in item for item in _findings(
        tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected
    ))


def test_unknown_agents_test_selector_is_not_promoted_to_a_production_owner(tmp_path: Path) -> None:
    snapshot = ".agents/skills/other-skill/scripts/tests/test_unknown.py"
    candidate = {"slice_hints": [{
        "obligation_ids": ["O-1"],
        "production_owners": [snapshot],
        "allowed_write_paths": [snapshot],
        "execution_snapshot_paths": [snapshot],
        "planned_new_files": [],
    }]}

    projected = _normalize_production_write_sets(tmp_path, candidate)
    assert projected["slice_hints"][0]["production_owners"] == [snapshot]
    assert any("no-real-production-entry" in item for item in _findings(
        tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected
    ))


def test_explicit_frozen_owner_is_projected_as_planned_when_missing(tmp_path: Path) -> None:
    source_ref = "requirements.md#FR-1"
    payload = {
        "obligations": [{"obligation_id": "O-1", "source_refs": [source_ref]}],
        "source_contracts": [{
            "source_ref": source_ref,
            "source_text": "Production owner: `scripts/sc/new_validator.py`\n",
        }],
    }
    value = {"slice_hints": [{
        **_hint(["O-1"], allowed=["scripts/sc/new_validator.py"], planned=[]),
        "production_owners": ["scripts/sc/new_validator.py"],
    }]}
    projected = explicit_path.normalize_explicit_path_contracts(tmp_path, "v3", payload, value)
    hint = projected["slice_hints"][0]
    assert hint["planned_new_files"] == ["scripts/sc/new_validator.py"]


def test_planned_test_file_cannot_be_a_production_owner(tmp_path: Path) -> None:
    obligations = [_obligation("O-1")]
    owner = "scripts/sc/tests/test_new_validator.py"
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=[owner], planned=[owner]),
        "production_owners": [owner],
    }]}
    findings = _findings(tmp_path, "v3", {"obligations": obligations}, candidate)
    assert any("no-real-production-entry" in item for item in findings)


def test_package_a_test_only_hint_projects_declared_missing_snapshots(tmp_path: Path) -> None:
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=[
            "scripts/sc/tests/test_skill_quality_core.py",
            "scripts/sc/tests/test_skill_quality_examples.py",
            "scripts/sc/tests/test_skill_replay_runtime.py",
        ], planned=[]),
        "production_owners": [],
        "execution_snapshot_paths": [
            "scripts/sc/tests/test_skill_quality_core.py",
            "scripts/sc/tests/test_skill_quality_examples.py",
            "scripts/sc/tests/test_skill_replay_runtime.py",
        ],
    }]}
    projected = _normalize_production_write_sets(tmp_path, candidate)
    hint = projected["slice_hints"][0]
    assert set(hint["planned_new_files"]) == {
        "scripts/sc/tests/test_skill_quality_core.py",
        "scripts/sc/tests/test_skill_quality_examples.py",
        "scripts/sc/tests/test_skill_replay_runtime.py",
    }
    assert not any("no-real-production-entry" in item for item in _findings(
        tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected
    ))


def test_package_a_test_only_hint_with_omitted_write_set_is_recovered(tmp_path: Path) -> None:
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=[], planned=[]),
        "production_owners": None,
        "allowed_write_paths": None,
        "execution_snapshot_paths": ["scripts/sc/tests/test_skill_quality_examples.py"],
    }]}
    projected = _normalize_production_write_sets(tmp_path, candidate)
    hint = projected["slice_hints"][0]
    assert hint["production_owners"] == []
    assert hint["allowed_write_paths"] == ["scripts/sc/tests/test_skill_quality_examples.py"]
    assert hint["planned_new_files"] == ["scripts/sc/tests/test_skill_quality_examples.py"]
    assert not any("no-real-production-entry" in item for item in _findings(
        tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected
    ))


def test_package_a_test_only_hint_with_empty_write_set_is_recovered(tmp_path: Path) -> None:
    test_path = "scripts/sc/tests/test_skill_quality_examples.py"
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=[], planned=[]),
        "production_owners": [test_path],
        "execution_snapshot_paths": [test_path],
    }]}

    projected = _normalize_production_write_sets(tmp_path, candidate)
    hint = projected["slice_hints"][0]
    assert hint["production_owners"] == []
    assert hint["allowed_write_paths"] == [test_path]
    assert hint["planned_new_files"] == [test_path]
    assert not any("no-real-production-entry" in item for item in _findings(
        tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected
    ))


def test_package_a_test_only_hint_with_null_owner_and_empty_write_set_is_recovered(tmp_path: Path) -> None:
    test_path = "scripts/sc/tests/test_skill_quality_examples.py"
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=[], planned=[]),
        "production_owners": None,
        "execution_snapshot_paths": [test_path],
    }]}

    projected = _normalize_production_write_sets(tmp_path, candidate)
    hint = projected["slice_hints"][0]
    assert hint["production_owners"] == []
    assert hint["allowed_write_paths"] == [test_path]
    assert hint["planned_new_files"] == [test_path]
    assert not any("no-real-production-entry" in item for item in _findings(
        tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected
    ))


def test_package_a_test_only_hint_rewrites_null_production_owners(tmp_path: Path) -> None:
    test_path = "scripts/sc/tests/test_skill_quality_examples.py"
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=[test_path], planned=[test_path]),
        "production_owners": None,
        "execution_snapshot_paths": [test_path],
    }]}
    projected = _normalize_production_write_sets(tmp_path, candidate)
    hint = projected["slice_hints"][0]
    assert hint["production_owners"] == []
    assert not any("no-real-production-entry" in item for item in _findings(
        tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected
    ))


def test_package_a_test_only_findings_require_normalized_empty_owners(tmp_path: Path) -> None:
    test_path = "scripts/sc/tests/test_skill_quality_examples.py"
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=[test_path], planned=[test_path]),
        "production_owners": None,
        "execution_snapshot_paths": [test_path],
    }]}
    projected = _normalize_production_write_sets(tmp_path, candidate)
    assert projected["slice_hints"][0]["production_owners"] == []
    findings = _findings(tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected)
    assert not any("no-real-production-entry" in item for item in findings)


def test_v3_contract_failure_persists_normalized_diagnostic(tmp_path: Path) -> None:
    invalid_path = "src/unmapped_owner.py"
    obligation = _obligation("O-1")
    hint = {
        **_hint(["O-1"], allowed=[invalid_path], planned=[]),
        "production_owners": [invalid_path],
        "execution_snapshot_paths": [invalid_path],
    }
    value = {
        "acceptances": [_acceptance(["O-1"])],
        "failure_intents": [_failure(["O-1"])],
        "slice_hints": [hint],
    }
    try:
        normalize_v3_cached_result(
            root=tmp_path,
            out_dir=tmp_path,
            stage="v3-schema-repair",
            payload={"input": {"obligations": [obligation]}},
            value=value,
        )
    except ValueError as exc:
        assert "no-real-production-entry" in str(exc)
    else:
        raise AssertionError("invalid production owner unexpectedly passed the contract")
    diagnostics = list((tmp_path / ".compiler-work" / "v3-contract-diagnostics").glob("*.json"))
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0].read_text(encoding="utf-8")
    assert "vdd.v3-contract-diagnostic.v1" in diagnostic
    assert "src/unmapped_owner.py" in diagnostic


def test_cached_v3_successor_runs_owner_normalization_before_gate(tmp_path: Path) -> None:
    test_path = "scripts/sc/tests/test_skill_quality_examples.py"
    obligation = _obligation("O-1")
    cached = {
        "acceptances": [{
            "obligation_ids": ["O-1"],
            "source_refs": obligation["source_refs"],
            "given": "a package",
            "when": "validated",
            "then": "the result is structured",
            "assertion_ids": ["A-1"],
            "oracle": {"observable": "structured", "expected": "pass", "forbidden": []},
        }],
        "failure_intents": [{
            "obligation_ids": ["O-1"],
            "expected_outcome": "fail",
            "failure_family": "expected-red",
            "failure_id": "F-1",
            "selector_intent": "test",
        }],
        "slice_hints": [{
            **_hint(["O-1"], allowed=[test_path], planned=[test_path]),
            "production_owners": None,
            "execution_snapshot_paths": [test_path],
        }],
    }
    # ADR-0041: a missing owner for product RED is not a test-only guard.
    import pytest
    with pytest.raises(ValueError, match="unowned-production-behavior"):
        normalize_v3_cached_result(root=tmp_path, out_dir=tmp_path, stage="v3",
            payload={"obligations": [obligation]}, value=cached)


def test_package_a_test_support_owner_is_planned_without_becoming_product_owner(tmp_path: Path) -> None:
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=["scripts/sc/tests/skill_quality_support.py"], planned=[]),
        "production_owners": ["scripts/sc/tests/skill_quality_support.py"],
        "execution_snapshot_paths": ["scripts/sc/tests/skill_quality_support.py"],
    }]}
    projected = _normalize_production_write_sets(tmp_path, candidate)
    hint = projected["slice_hints"][0]
    assert hint["planned_new_files"] == ["scripts/sc/tests/skill_quality_support.py"]
    findings = _findings(tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected)
    assert not any("no-real-production-entry" in item for item in findings)


def test_package_a_owner_allowlist_is_planned_even_when_worker_omits_projection(tmp_path: Path) -> None:
    owner = "scripts/sc/validate_skill_quality.py"
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=[owner], planned=[]),
        "production_owners": [owner],
    }]}
    projected = _normalize_production_write_sets(tmp_path, candidate)
    assert owner in projected["slice_hints"][0]["planned_new_files"]
    findings = _findings(tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected)
    assert not any("no-real-production-entry" in item for item in findings)


def test_package_a_test_paths_are_not_retained_as_production_owners(tmp_path: Path) -> None:
    test_path = "scripts/sc/tests/test_skill_quality_core.py"
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=[test_path], planned=[test_path]),
        "production_owners": [test_path],
        "execution_snapshot_paths": [test_path],
    }]}
    projected = _normalize_production_write_sets(tmp_path, candidate)
    hint = projected["slice_hints"][0]
    assert hint["production_owners"] == []
    assert not any("no-real-production-entry" in item for item in _findings(
        tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected
    ))


def test_package_a_test_only_cannot_hide_a_mixed_production_write_set(tmp_path: Path) -> None:
    test_path = "scripts/sc/tests/test_skill_quality_core.py"
    production_path = "scripts/sc/validate_skill_quality.py"
    candidate = {"slice_hints": [{
        **_hint(["O-1"], allowed=[test_path, production_path], planned=[test_path]),
        "production_owners": [test_path],
        "execution_snapshot_paths": [test_path],
    }]}
    projected = _normalize_production_write_sets(tmp_path, candidate)
    assert production_path in projected["slice_hints"][0]["production_owners"]
    assert all(
        owner in _PACKAGE_A_PLANNED_PRODUCTION
        for owner in projected["slice_hints"][0]["production_owners"]
    )
    assert not any("no-real-production-entry" in item for item in _findings(
        tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected
    ))


def test_s4_terminal_evidence_selector_gets_only_its_existing_test_project_owner(tmp_path: Path) -> None:
    project = tmp_path / "PhaseA.Platform.Tests" / "PhaseA.Platform.Tests.csproj"
    project.parent.mkdir(parents=True)
    project.write_text("<Project />\n", encoding="utf-8")
    selector = tmp_path / "tests" / "phase_b_c_identity_isolation" / "test_s4_migration_evidence.py"
    selector.parent.mkdir(parents=True)
    selector.write_text("def test_evidence(): pass\n", encoding="utf-8")
    value = {"slice_hints": [{
        **_hint(["O-1"], allowed=["tests/phase_b_c_identity_isolation/test_s4_migration_evidence.py"], planned=[]),
        "production_owners": [],
        "execution_snapshot_paths": ["tests/phase_b_c_identity_isolation/test_s4_migration_evidence.py"],
    }]}
    projected = _normalize_production_write_sets(tmp_path, value)
    hint = projected["slice_hints"][0]
    assert hint["production_owners"] == ["PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"]
    assert "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj" in hint["allowed_write_paths"]
    assert not any("no-real-production-entry" in item for item in _findings(tmp_path, "v3", {"obligations": [_obligation("O-1")]}, projected))


def test_known_operations_selector_repairs_a_missing_owner_only_from_its_canonical_mapping(tmp_path: Path) -> None:
    for path in ("PhaseA.Platform/Program.cs", "PhaseA.Platform/Data/PhaseAMetadataStore.cs"):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("class Entry {}\n", encoding="utf-8")
    value = {"slice_hints": [{
        **_hint(["O-1"], allowed=[], planned=[]),
        "production_owners": [],
        "execution_snapshot_paths": ["PhaseA.Platform.Tests/PhaseB/Repair/OperationsBoundaryTests.cs"],
    }]}
    projected = _normalize_production_write_sets(tmp_path, value)
    assert projected["slice_hints"][0]["production_owners"] == [
        "PhaseA.Platform/Program.cs", "PhaseA.Platform/Data/PhaseAMetadataStore.cs"
    ]


def test_product_behavior_failure_is_a_causal_expected_red_with_frozen_negation() -> None:
    obligation = _obligation("O-1")
    obligation["expected_behavior"] = "protected administrator change creates an auditable new active policy version"
    value = {"failure_intents": [{
        "obligation_ids": ["O-1"], "failure_family": "task-implementation-failure",
        "selector_intent": "select policy boundary test", "expected_outcome": "fail", "failure_id": "OLD",
    }]}
    result = _normalize_expected_red_for_product_behavior("v3", {"obligations": [obligation]}, value)
    failure = result["failure_intents"][0]
    assert failure["failure_family"] == "expected-red"
    assert "Negate required behavior: protected administrator change creates an auditable new active policy version" in failure["selector_intent"]


def test_constraint_failure_family_is_not_promoted_to_expected_red() -> None:
    obligation = _obligation("O-1")
    obligation["obligation_kind"] = "constraint"
    value = {"failure_intents": [{
        "obligation_ids": ["O-1"], "failure_family": "test-harness-failure",
        "selector_intent": "select evidence test", "expected_outcome": "fail", "failure_id": "OLD",
    }]}
    assert _normalize_expected_red_for_product_behavior("v3", {"obligations": [obligation]}, value) == value


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


def test_existing_admin_review_queue_http_selector_uses_route_and_metadata_owners(tmp_path: Path) -> None:
    for path in (
        "PhaseA.Platform/Program.cs",
        "PhaseA.Platform/Data/PhaseAMetadataStore.cs",
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("class ProductionEntry {}\n", encoding="utf-8")
    payload, value = _repair_payload(
        source_text="SM-A01 private admin review queue API authorization and no-store behavior",
        snapshot="PhaseA.Platform.Tests/Browser/AdminReviewQueueHttpIntegrationTests.cs",
    )
    value["slice_hints"][0]["production_owners"] = [
        "PhaseA.Platform.Tests/Browser/AdminReviewQueueHttpIntegrationTests.cs"
    ]
    value = _normalize_production_write_sets(tmp_path, value)
    grounded, _ = ground_v3_paths(tmp_path, payload, value)
    hint = grounded["slice_hints"][0]
    assert hint["production_owners"] == [
        "PhaseA.Platform/Program.cs",
        "PhaseA.Platform/Data/PhaseAMetadataStore.cs",
    ]
    assert hint["planned_new_files"] == []


def test_declared_missing_phase_b_test_artifacts_become_planned_with_real_owner(tmp_path: Path) -> None:
    owner = tmp_path / "PhaseA.Platform/Workspaces/WorkspaceStorageService.cs"
    owner.parent.mkdir(parents=True)
    owner.write_text("class ProductionEntry {}\n", encoding="utf-8")
    paths = [
        "tests/phase_b_c_identity_isolation/current/test_s74.py",
        "PhaseA.Platform.Tests/PhaseB/Repair/S74BoundaryTests.cs",
        "tests/phase_b_c_identity_isolation/current/s74_fixture.py",
    ]
    value = {"slice_hints": [{
        **_hint(["O-1"], allowed=["PhaseA.Platform/Workspaces/WorkspaceStorageService.cs", *paths], planned=[]),
        "production_owners": ["PhaseA.Platform/Workspaces/WorkspaceStorageService.cs"],
        "execution_snapshot_paths": paths,
    }]}
    result = _normalize_production_write_sets(tmp_path, value)
    assert result["slice_hints"][0]["planned_new_files"] == paths


def test_existing_s11_substitute_root_selector_uses_real_storage_and_restore_owners(tmp_path: Path) -> None:
    for path in (
        "PhaseA.Platform/Workspaces/WorkspaceStorageService.cs",
        "PhaseA.Platform/Workspaces/RestoreService.cs",
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("class ProductionEntry {}\n", encoding="utf-8")
    payload, value = _repair_payload(
        source_text="SM-T11 SubstituteRootDrill_RecordsBoundedRto",
        snapshot="PhaseA.Platform.Tests/PhaseB/Repair/S11BoundaryTests.cs",
    )
    value["slice_hints"][0]["production_owners"] = [
        "PhaseA.Platform.Tests/PhaseB/Repair/S11BoundaryTests.cs"
    ]
    value = _normalize_production_write_sets(tmp_path, value)
    hint = value["slice_hints"][0]
    assert hint["production_owners"] == [
        "PhaseA.Platform/Workspaces/WorkspaceStorageService.cs",
        "PhaseA.Platform/Workspaces/RestoreService.cs",
    ]
    assert set(hint["production_owners"]).issubset(hint["allowed_write_paths"])


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


# ADR-0041: repair projections preserve declared execution roles and raw history.
def test_group_cache_projects_future_owner_before_refresh_check(tmp_path: Path) -> None:
    import json
    import semantic_worker_v3_group_repair_patch as grouped

    oid = "O-CAFE"
    owner = "scripts/sc/validate_skill_quality.py"
    test = "scripts/sc/tests/test_skill_quality_core.py"
    payload = {"input": {"obligations": [_obligation(oid)]}}
    hint = {**_hint([oid], allowed=[owner], planned=[test]),
            "production_owners": [owner], "execution_snapshot_paths": [test]}
    raw = {"obligation_contracts": {oid: {
        "acceptance": {k: v for k, v in _acceptance([oid]).items() if k != "obligation_ids"},
        "failure_intents": [{k: v for k, v in _failure([oid]).items() if k != "obligation_ids"}],
        "slice_hint": {k: v for k, v in hint.items() if k != "obligation_ids"},
    }}}
    cache = tmp_path / "plan/.compiler-cache" / grouped.sc._worker_cache_key(
        grouped._GROUP_STAGE, grouped.group_cache_identity_payload(payload))
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps(raw), encoding="utf-8")
    original = cache.read_bytes()

    projected = grouped._cached_group_result(root=tmp_path, out_dir=tmp_path / "plan", payload=payload)

    assert projected is not None, "A repairable redundant planned field must not force another model call"
    result = projected["slice_hints"][0]
    assert set(result["production_owners"]) <= set(result["allowed_write_paths"])
    assert owner in result["planned_new_files"]
    assert cache.read_bytes() == original


def test_schema_repair_keeps_test_only_and_production_candidates_separate(tmp_path: Path) -> None:
    test = "scripts/sc/tests/test_skill_quality_core.py"
    owner = "scripts/sc/validate_skill_quality.py"
    obligations = [_obligation("O-CAFE"), _obligation("O-BEEF")]
    obligations[0]["obligation_kind"] = "constraint"
    acceptances = [_acceptance([item["obligation_id"]]) for item in obligations]
    for acceptance, obligation in zip(acceptances, obligations):
        acceptance["oracle"]["expected"] = obligation["observable_result"]
        acceptance["assertion_ids"] = ["ASSERT-" + obligation["obligation_id"]]
    failures = [_failure([item["obligation_id"]]) for item in obligations]
    failures[0]["failure_family"] = "test-harness-failure"
    value = {"acceptances": acceptances, "failure_intents": failures, "slice_hints": [
        {**_hint(["O-CAFE"], allowed=[test], planned=[test]),
         "production_owners": [], "execution_snapshot_paths": [test],
         "rollback_scope": {"production_paths": [], "state_or_schema_compatibility": "unchanged"}},
        {**_hint(["O-BEEF"], allowed=[], planned=[test]),
         "production_owners": [owner], "allowed_write_paths": None,
         "execution_snapshot_paths": [test]},
    ]}

    result = normalize_v3_cached_result(root=tmp_path, out_dir=tmp_path / "plan",
        stage="v3-schema-repair", payload={"input": {"obligations": obligations}}, value=value)

    tests_only, production = result["slice_hints"]
    assert tests_only["production_owners"] == []
    assert tests_only["allowed_write_paths"] == [test]
    assert owner in production["production_owners"]
    assert set(production["production_owners"]) <= set(production["allowed_write_paths"])
    assert set(production["production_owners"]) <= set(production["planned_new_files"])
    assert value["slice_hints"][1]["allowed_write_paths"] is None


def test_initial_normalization_preserves_declared_owner_when_write_set_is_omitted(tmp_path: Path) -> None:
    owner = "scripts/sc/skill_quality_examples.py"
    test = "scripts/sc/tests/test_skill_quality_examples.py"
    value = {"slice_hints": [{**_hint(["O-CAFE"], allowed=[], planned=[test]),
        "production_owners": [owner], "allowed_write_paths": None,
        "execution_snapshot_paths": [test]}]}

    result = _normalize_production_write_sets(tmp_path, value)["slice_hints"][0]

    assert owner in result["production_owners"]
    assert owner in result["allowed_write_paths"]
    assert owner in result["planned_new_files"]


def test_final_findings_cannot_accept_owner_planned_only_in_validator_copy(tmp_path: Path) -> None:
    owner = "scripts/sc/validate_skill_quality.py"
    test = "scripts/sc/tests/test_skill_quality_core.py"
    hint = {**_hint(["O-CAFE"], allowed=[owner], planned=[test]),
            "production_owners": [owner], "execution_snapshot_paths": [test]}

    findings = _findings(tmp_path, "v3", {"obligations": [_obligation("O-CAFE")]},
        {"acceptances": [_acceptance(["O-CAFE"])], "slice_hints": [hint]})

    assert any("no-real-production-entry" in item for item in findings)
    assert owner not in hint["planned_new_files"]


def test_group_safety_does_not_promote_explicit_test_only_rollback(tmp_path: Path) -> None:
    import semantic_worker_v3_group_safety_patch as safety

    (tmp_path / "src").mkdir()
    (tmp_path / "src/owner.py").write_text("VALUE = 1\n", encoding="utf-8")
    test = "scripts/sc/tests/test_skill_quality_core.py"
    value = {"slice_hints": [{**_hint(["O-CAFE"], allowed=[test], planned=[test]),
        "production_owners": [], "execution_snapshot_paths": [test]}]}

    result = safety._normalize_repaired_value(tmp_path, value)["slice_hints"][0]

    assert result["production_owners"] == []
    assert result["allowed_write_paths"] == [test]


def test_group_projection_agrees_for_inline_and_already_projected_planned_owner(tmp_path: Path) -> None:
    import semantic_worker_v3_group_repair_patch as grouped

    oid = "O-CAFE"
    owner = "src/new_quality_rule.py"
    test = "scripts/sc/tests/test_skill_quality_core.py"
    payload = {"input": {"obligations": [_obligation(oid)]}}
    hint = {**_hint([oid], allowed=[], planned=[owner, test]),
            "production_owners": [owner], "execution_snapshot_paths": [test]}
    acceptance = _acceptance([oid])
    failure = _failure([oid])
    forms = [
        {"acceptances": [acceptance], "failure_intents": [failure], "slice_hints": [hint]},
        {"obligation_contracts": {oid: {
            "acceptance": {k: v for k, v in acceptance.items() if k != "obligation_ids"},
            "failure_intents": [{k: v for k, v in failure.items() if k != "obligation_ids"}],
            "slice_hint": {k: v for k, v in hint.items() if k != "obligation_ids"},
        }}},
    ]
    results = []
    for raw in forms:
        result = grouped._project_execution_output(tmp_path, payload, raw)
        projected_hint = result["slice_hints"][0]
        assert projected_hint["production_owners"] == [owner]
        assert owner in projected_hint["allowed_write_paths"]
        assert owner in projected_hint["planned_new_files"]
        assert grouped._project_execution_output(tmp_path, payload, result) == result
        results.append(result)
    assert results[0] == results[1]
    assert hint["allowed_write_paths"] == []


def test_pytest_node_snapshot_projects_only_declared_file_for_v7(tmp_path):
    """ADR-0041: preserve selector identity in argv, file identity in snapshots."""
    owner = 'src/subject.py'
    test = 'tests/test_subject.py'
    node = test + '::test_value[boundary]'
    hint = {'production_owners': [owner], 'allowed_write_paths': [owner],
            'execution_snapshot_paths': [node], 'planned_new_files': [owner, test],
            'validation_commands': [['python', '-m', 'pytest', node]]}
    value = {'slice_hints': [hint]}
    result = _normalize_production_write_sets(tmp_path, value)
    assert result['slice_hints'][0]['execution_snapshot_paths'] == [test]
    assert result['slice_hints'][0]['validation_commands'][0][-1] == node
    assert hint['execution_snapshot_paths'] == [node]
    unplanned = {'slice_hints': [{**hint, 'planned_new_files': [owner]}]}
    denied = _normalize_production_write_sets(tmp_path, unplanned)
    assert denied['slice_hints'][0]['execution_snapshot_paths'] == [node]
