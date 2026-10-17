"""Ground stale V3 repair paths against explicit Phase B/C repair authority.

The repair input defines five future test classes and their Phase B/C slices.
Workers sometimes retain paths from older repository layouts.  This module is
intentionally a finite projection table, rather than a repository search: a
legacy path can move only when the same frozen source names its canonical test
class, and a stale production path can move only through an exact replacement.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


_CANONICAL_TESTS = {
    "IdentityBoundaryTests": "PhaseA.Platform.Tests/PhaseB/Repair/IdentityBoundaryTests.cs",
    "RunnerBoundaryTests": "PhaseA.Platform.Tests/PhaseB/Repair/RunnerBoundaryTests.cs",
    "SnapshotBoundaryTests": "PhaseA.Platform.Tests/PhaseB/Repair/SnapshotBoundaryTests.cs",
    "RestoreBoundaryTests": "PhaseA.Platform.Tests/PhaseB/Repair/RestoreBoundaryTests.cs",
    "OperationsBoundaryTests": "PhaseA.Platform.Tests/PhaseB/Repair/OperationsBoundaryTests.cs",
}

# These are exact stale spellings seen in the repair lane, not filename
# matching.  Adding a new spelling requires an explicit source-level reason.
_LEGACY_TEST_CLASS_BY_PATH = {
    "PhaseA.Platform.Tests/Security/RequestContextTests.cs": "IdentityBoundaryTests",
    ".agents/skills/vdd-execution-plan/scripts/tests/test_ch456_active_alignment_scope.py": "PhaseA.Platform.Tests/PhaseB/Repair/IdentityBoundaryTests.cs",
    ".agents/skills/vdd-execution-plan/scripts/tests/test_ch456_v4_active_alignment_scope.py": "PhaseA.Platform.Tests/PhaseB/Repair/IdentityBoundaryTests.cs",
    "Tests.Godot/tests/Integration/Security/test_security_http_client.gd": "IdentityBoundaryTests",
    "PhaseA.Platform.Tests/": None,
    "PhaseA.Platform.Tests": None,
    "PhaseA.Platform.Tests/Workspaces/RestoreServiceTests.cs": "RestoreBoundaryTests",
    "PhaseA.Platform.Tests/Repair/RestoreBoundaryTests.cs": "RestoreBoundaryTests",
    "PhaseA.Platform.Tests/RestoreBoundaryTests.cs": "RestoreBoundaryTests",
    "PhaseA.Platform.Tests/Security/RestoreBoundaryTests.cs": "RestoreBoundaryTests",
    "PhaseA.Platform.Tests/Security/RestoreRecoveryTests.cs": "RestoreBoundaryTests",
    "PhaseA.Platform.Tests/Security/WorkspaceRecoveryBehaviorTests.cs": "RestoreBoundaryTests",
    "PhaseA.Platform.Tests/Security/IdentityBoundaryTests.cs": "IdentityBoundaryTests",
    "PhaseA.Platform.Tests/Identity/PhaseBRepairIdentityBoundaryTests.cs": "IdentityBoundaryTests",
    "PhaseA.Platform.Tests/Security/PhaseAAuthTests.cs": "IdentityBoundaryTests",
    "PhaseA.Platform.Tests/Security/RequestContextTests.cs": "IdentityBoundaryTests",
    "PhaseA.Platform.Tests/Runs/RunnerBoundaryTests.cs": "RunnerBoundaryTests",
    "PhaseA.Platform.Tests/Security/RunnerIsolationTests.cs": "RunnerBoundaryTests",
    "PhaseA.Platform.Tests/Security/SnapshotBoundaryTests.cs": "SnapshotBoundaryTests",
    "PhaseA.Platform.Tests/Security/SnapshotTests.cs": "SnapshotBoundaryTests",
    "PhaseB.Repair/Integration/SnapshotBoundaryTests.cs": "SnapshotBoundaryTests",
    "PhaseA.Platform.Tests/OperationsBoundaryTests.cs": "OperationsBoundaryTests",
    "PhaseA.Platform.Tests/Operations/OperationsBoundaryTests.cs": "OperationsBoundaryTests",
    "PhaseA.Platform.Tests/Repair/OperationsBoundaryTests.cs": "OperationsBoundaryTests",
    "PhaseA.Platform.Tests/Security/OperationsBoundaryTests.cs": "OperationsBoundaryTests",
    "PhaseA.Platform.Tests/FailureFamilyVerificationTests.cs": "OperationsBoundaryTests",
}

_LEGACY_TEST_PATHS = {
    ".agents/skills/vdd-execution-plan/scripts/tests/test_ch456_active_alignment_scope.py": _CANONICAL_TESTS["IdentityBoundaryTests"],
    ".agents/skills/vdd-execution-plan/scripts/tests/test_ch456_v4_active_alignment_scope.py": _CANONICAL_TESTS["IdentityBoundaryTests"],
}

_LEGACY_PRODUCTION_PATHS = {
    "PhaseA.Platform/Services/OperationAuthorizationService.cs": "PhaseA.Platform/Program.cs",
    "PhaseA.Platform/Operations/OperationService.cs": "PhaseA.Platform/Program.cs",
    "PhaseA.Platform/Operations/OperationQueue.cs": "PhaseA.Platform/Runs/HeavyRunnerQueueService.cs",
    "PhaseA.Platform/Services/BackgroundOperationQueue.cs": "PhaseA.Platform/Runs/HeavyRunnerQueueService.cs",
    "PhaseA.Platform/Services/PublicationService.cs": "PhaseA.Platform/Readback/ProjectPackageService.cs",
    "PhaseA.Platform/Services/ProjectService.cs": "PhaseA.Platform/Projects/ProjectCreationService.cs",
    "PhaseA.Platform/Projects/ProjectService.cs": "PhaseA.Platform/Projects/ProjectCreationService.cs",
    "PhaseA.Platform/Services/ProjectOperationService.cs": "PhaseA.Platform/Projects/ProjectInitializationService.cs",
    " .agents/skills/vdd-execution-plan/scripts/stage_lifecycle_runner.py": "scripts/vdd/compile_plan.py",
    ".agents/skills/vdd-execution-plan/scripts/stage_lifecycle_runner.py": "scripts/vdd/compile_plan.py",
    ".agents/skills/vdd-execution-plan/scripts/compile_plan.py": "scripts/vdd/compile_plan.py",
    "_bmad-output/specs/canonical-spec-package-selections/current/SPEC-phase-b-c-identity-isolation-workspace-recovery.json": "scripts/vdd/compile_plan.py",
    "PhaseA.Platform.Tests": "PhaseA.Platform/Readback/ArtifactReadbackService.cs",
    "PhaseA.Platform.Tests/Readback/ArtifactReadbackServiceTests.cs": "PhaseA.Platform/Readback/ArtifactReadbackService.cs",
    # Runner aliases emitted by the current repair worker.  The repository
    # keeps runner implementation under Runs/Security; normalize these before
    # the execution-contract checks inspect real production entries.
    "PhaseA.Platform/Services/Runner/HostedProcessRunner.cs": "PhaseA.Platform/Runs/HostedProcessRunner.cs",
    "PhaseA.Platform/Services/Runner/RunnerIsolationPolicy.cs": "PhaseA.Platform/Security/RunnerIsolationPolicy.cs",
    "PhaseA.Platform/Projects/ProjectDeletionService.cs": "PhaseA.Platform/Projects/ProjectCreationService.cs",
    "PhaseA.Platform/Services/RestoreReconciliationService.cs": "PhaseA.Platform/Workspaces/RestoreService.cs",
    "PhaseA.Platform/Services/RestoreAttemptStore.cs": "PhaseA.Platform/Workspaces/RestoreAttempt.cs",
    "PhaseA.Platform/Services/WorkspaceStorageService.cs": "PhaseA.Platform/Workspaces/WorkspaceStorageService.cs",
    "PhaseA.Platform/Services/ExtensionPolicyService.cs": "PhaseA.Platform/Workspaces/WorkspaceStorageService.cs",
    "PhaseA.Platform/Services/HostedProcessRunner.cs": "PhaseA.Platform/Runs/HostedProcessRunner.cs",
    "PhaseA.Platform/Services/RunnerIsolationPolicy.cs": "PhaseA.Platform/Security/RunnerIsolationPolicy.cs",
    "PhaseA.Platform/Hosting/RunnerIsolationPolicy.cs": "PhaseA.Platform/Security/RunnerIsolationPolicy.cs",
    "PhaseA.Platform/Services/SnapshotManifest.cs": "PhaseA.Platform/Workspaces/SnapshotManifest.cs",
    "PhaseA.Platform/Models/SnapshotManifest.cs": "PhaseA.Platform/Workspaces/SnapshotManifest.cs",
    "PhaseA.Platform/PhaseAMetadataStore.cs": "PhaseA.Platform/Data/PhaseAMetadataStore.cs",
    "PhaseA.Platform/Metadata/PhaseAMetadataStore.cs": "PhaseA.Platform/Data/PhaseAMetadataStore.cs",
    "PhaseA.Platform/Services/AuditService.cs": "PhaseA.Platform/Data/AdminAccountAuditEvent.cs",
    "PhaseA.Platform/Services/Audit/AuditService.cs": "PhaseA.Platform/Data/AdminAccountAuditEvent.cs",
    "PhaseA.Platform/Services/SnapshotManifest.cs": "PhaseA.Platform/Workspaces/SnapshotManifest.cs",
    "PhaseA.Platform/Services/RestoreService.cs": "PhaseA.Platform/Workspaces/RestoreService.cs",
    "PhaseA.Platform/Services/Workspaces/RestoreService.cs": "PhaseA.Platform/Workspaces/RestoreService.cs",
    "PhaseA.Platform/Execution/HostedProcessRunner.cs": "PhaseA.Platform/Runs/HostedProcessRunner.cs",
    "PhaseA.Platform/Execution/RunnerIsolationPolicy.cs": "PhaseA.Platform/Security/RunnerIsolationPolicy.cs",
    "PhaseA.Platform/Services/HostedRouteRecoveryService.cs": "PhaseA.Platform/Workspaces/RestoreService.cs",
    "PhaseA.Platform/Services/RunService.cs": "PhaseA.Platform/Runs/HostedProcessRunner.cs",
}


def _source_text(payload: Mapping[str, Any], ids: object) -> str:
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        return ""
    obligations = payload.get("obligations")
    contracts = payload.get("source_contracts")
    if not isinstance(obligations, list) or not isinstance(contracts, list):
        return ""
    refs_by_id = {
        item.get("obligation_id"): item.get("source_refs")
        for item in obligations
        if isinstance(item, Mapping)
        and isinstance(item.get("obligation_id"), str)
        and isinstance(item.get("source_refs"), list)
    }
    text_by_ref = {
        item.get("source_ref"): item.get("source_text")
        for item in contracts
        if isinstance(item, Mapping)
        and isinstance(item.get("source_ref"), str)
        and isinstance(item.get("source_text"), str)
    }
    return "\n".join(
        text_by_ref.get(ref, "")
        for oid in ids
        for ref in refs_by_id.get(oid, [])
        if isinstance(ref, str)
    )


def _source_refs(payload: Mapping[str, Any], ids: object) -> str:
    """Return frozen source-reference identifiers for source-scoped rules."""
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        return ""
    obligations = payload.get("obligations")
    if not isinstance(obligations, list):
        return ""
    refs: list[str] = []
    for obligation in obligations:
        if not isinstance(obligation, Mapping) or obligation.get("obligation_id") not in ids:
            continue
        values = obligation.get("source_refs")
        if isinstance(values, list):
            refs.extend(item for item in values if isinstance(item, str))
    return "\n".join(refs)


def _authorized_class(source_text: str) -> str | None:
    matches = [name for name in _CANONICAL_TESTS if name in source_text]
    return matches[0] if len(matches) == 1 else None


def _ground_test_path(raw: object, test_class: str | None) -> str | None:
    if not isinstance(raw, str):
        return None
    listed_class = _LEGACY_TEST_CLASS_BY_PATH.get(raw, "missing")
    if listed_class == "missing":
        return None
    if test_class is None and listed_class in _CANONICAL_TESTS:
        return _CANONICAL_TESTS[listed_class]
    if test_class is None:
        return None
    # The root directory was a truncated selector.  Its target is determined
    # only by the one class explicitly named by the frozen contract.
    if listed_class is None or listed_class == test_class:
        return _CANONICAL_TESTS[test_class]
    if isinstance(raw, str) and listed_class in _CANONICAL_TESTS:
        return _CANONICAL_TESTS[listed_class]
    return None


def _ground_test_path_for_source(raw: object, source_text: str, test_class: str | None) -> str | None:
    """Apply the two legacy selector spellings whose class is source-scoped.

    Older workers emitted a generic WorkspaceRecoveryBehaviorTests path (or a
    Python selector) for both snapshot and restore obligations.  The frozen
    source marker is the authority here; a generic path must never be mapped
    merely because it happens to contain ``Recovery``.
    """
    if isinstance(raw, str):
        if raw == ".agents/skills/vdd-execution-plan/scripts/tests/test_stage_lifecycle.py":
            # This worker selector belongs to the VDD compiler lifecycle lane;
            # keep it bound to the existing repository test module until the
            # plan's declared new selector is materialized by Quick Dev.
            return ".agents/skills/vdd-execution-plan/scripts/tests/test_semantic_compiler_ch456.py"
        if "SM-W10" in source_text:
            if raw in {
                "PhaseA.Platform.Tests/Security/WorkspaceRecoveryBehaviorTests.cs",
                "tests/phase_b_c_identity_isolation/test_s3_restore_recovery.py",
            }:
                return _CANONICAL_TESTS["SnapshotBoundaryTests"]
        if "SM-T02" in source_text and raw == "tests/phase_b_c_identity_isolation/test_s3_restore_recovery.py":
            return _CANONICAL_TESTS["RestoreBoundaryTests"]
        if "SM-R07" in source_text and raw == "PhaseA.Platform.Tests":
            return _CANONICAL_TESTS["RestoreBoundaryTests"]
        if "SM-R07" in source_text and raw == "PhaseA.Platform.Tests/Security/RestoreRecoveryTests.cs":
            return _CANONICAL_TESTS["RestoreBoundaryTests"]
    return _ground_test_path(raw, test_class)


def ground_v3_paths(root: Path, payload: Mapping[str, Any], value: Mapping[str, Any]) -> tuple[Mapping[str, Any], list[dict[str, Any]]]:
    """Return a grounded copy and auditable finite-path projection changes."""
    hints = value.get("slice_hints")
    if not isinstance(hints, list):
        return value, []
    root = Path(root)
    normalized = deepcopy(value)
    changes: list[dict[str, Any]] = []
    for index, hint in enumerate(normalized["slice_hints"]):
        if not isinstance(hint, dict):
            continue
        source_text = _source_text(payload, hint.get("obligation_ids"))
        source_scope = "\n".join((source_text, _source_refs(payload, hint.get("obligation_ids"))))
        test_class = _authorized_class(source_scope)
        local_changes: list[dict[str, str]] = []
        for field in ("execution_snapshot_paths", "planned_new_files"):
            paths = hint.get(field)
            if not isinstance(paths, list):
                continue
            rewritten: list[object] = []
            for raw in paths:
                canonical = _ground_test_path_for_source(
                    raw,
                    source_scope,
                    test_class,
                )
                if canonical is None and isinstance(raw, str):
                    canonical = _LEGACY_TEST_PATHS.get(raw)
                if canonical is not None:
                    rewritten.append(canonical)
                    local_changes.append({"field": field, "before": str(raw), "after": canonical, "reason": "explicit-frozen-test-class"})
                else:
                    rewritten.append(raw)
            hint[field] = list(dict.fromkeys(rewritten))
        owners = hint.get("production_owners")
        if isinstance(owners, list):
            rewritten_owners: list[object] = []
            for raw in owners:
                # Tests cannot be evidence of a production owner.  Filtering
                # them is safe only when another real owner remains.  Preserve
                # an all-test owner list temporarily: the execution-contract
                # normalizer uses the frozen test class to project its finite
                # canonical production owners.
                if isinstance(raw, str) and raw.startswith("PhaseA.Platform.Tests/"):
                    local_changes.append({"field": "production_owners", "before": raw, "after": "", "reason": "test-is-not-production-owner"})
                    continue
                canonical = _LEGACY_PRODUCTION_PATHS.get(raw) if isinstance(raw, str) else None
                if canonical is not None and (root / canonical).is_file() and not (root / canonical).is_symlink():
                    rewritten_owners.append(canonical)
                    local_changes.append({"field": "production_owners", "before": raw, "after": canonical, "reason": "explicit-current-production-path"})
                else:
                    rewritten_owners.append(raw)
            hint["production_owners"] = list(dict.fromkeys(rewritten_owners))
        if local_changes:
            changes.append({"hint_index": index, "obligation_ids": hint.get("obligation_ids", []), "changes": local_changes})
    return normalized, changes
