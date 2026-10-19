"""Validate and narrow-repair V3 semantics before the expensive global repair lane.

The canonical compiler still owns every truth gate. This wrapper only performs
deterministic/bounded normalizations before emitting V3 execution-contract
findings:

* one-obligation contracts remain unchanged; shared multi-obligation oracles
  are rejected for the existing schema-repair lane rather than cloned;
* genuinely uncovered obligations use the existing missing-only semantic
  completion lane.
* redundant singleton snapshot spelling may be projected from the same hint's
  single existing direct-script target, with an explicit projection receipt.

If the candidate is relationally ambiguous, references unknown obligations, or
still violates owner/path/semantic contracts after those steps, it is left to
the existing fail-closed schema-repair path. No finding is suppressed.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
from typing import Any, Mapping

import semantic_compiler_gate as gate
import semantic_worker_v3_group_repair_patch  # noqa: F401  # relation-safe repair first
import semantic_worker_v3_total_coverage_patch as total_coverage
from semantic_selector_path_projection import project_selector_paths
from semantic_worker_v3_path_grounding_patch import ground_v3_paths

_BASE_TRANSPORT = gate._ORIGINAL_INVOKE_WORKER

# The repair input names these five test classes as future Quick Dev work. They
# are not current evidence, so the only deterministic help V3 may provide is
# recording the exact authored path as planned. Authorization still comes from
# the frozen source text for the current obligation; arbitrary test paths and
# directories remain invalid.

_CANONICAL_TEST_PRODUCTION = {
    "IdentityBoundaryTests": ["PhaseA.Platform/Program.cs", "PhaseA.Platform/Data/PhaseAMetadataStore.cs"],
    "RunnerBoundaryTests": ["PhaseA.Platform/Runs/HostedProcessRunner.cs", "PhaseA.Platform/Security/RunnerIsolationPolicy.cs"],
    "SnapshotBoundaryTests": ["PhaseA.Platform/Workspaces/WorkspaceStorageService.cs", "PhaseA.Platform/Workspaces/SnapshotManifest.cs"],
    "RestoreBoundaryTests": ["PhaseA.Platform/Workspaces/RestoreService.cs"],
    # S11 is the existing bounded substitute-root drill selector.  It exercises
    # both the snapshot storage and restore publication boundaries, so the
    # selector is not itself a production owner.
    "S11BoundaryTests": [
        "PhaseA.Platform/Workspaces/WorkspaceStorageService.cs",
        "PhaseA.Platform/Workspaces/RestoreService.cs",
    ],
    "OperationsBoundaryTests": ["PhaseA.Platform/Program.cs", "PhaseA.Platform/Data/PhaseAMetadataStore.cs"],
    # Existing A08 evidence tests exercise the production evidence pipeline;
    # they are selectors, not production write owners.
    "RouteOperationGovernanceTests": [
        "PhaseA.Platform/Workflow/RouteOperationPreflight.cs",
        "PhaseA.Platform/Workflow/SecretRedactionPolicy.cs",
    ],
    # This existing HTTP integration selector exercises the mapped admin queue
    # routes and their private-response headers.  The selector is not a
    # production owner; the routes and their server-owned state live here.
    "AdminReviewQueueHttpIntegrationTests": [
        "PhaseA.Platform/Program.cs",
        "PhaseA.Platform/Data/PhaseAMetadataStore.cs",
    ],
}

_AUTHORIZED_REPAIR_TESTS = {
    "IdentityBoundaryTests": "PhaseA.Platform.Tests/PhaseB/Repair/IdentityBoundaryTests.cs",
    "RunnerBoundaryTests": "PhaseA.Platform.Tests/PhaseB/Repair/RunnerBoundaryTests.cs",
    "SnapshotBoundaryTests": "PhaseA.Platform.Tests/PhaseB/Repair/SnapshotBoundaryTests.cs",
    "RestoreBoundaryTests": "PhaseA.Platform.Tests/PhaseB/Repair/RestoreBoundaryTests.cs",
    "S11BoundaryTests": "PhaseA.Platform.Tests/PhaseB/Repair/S11BoundaryTests.cs",
    "OperationsBoundaryTests": "PhaseA.Platform.Tests/PhaseB/Repair/OperationsBoundaryTests.cs",
    "RouteOperationGovernanceTests": "PhaseA.Platform.Tests/Workflow/RouteOperationGovernanceTests.cs",
}

_EXISTING_AUTHORIZED_TESTS = {
    "PhaseA.Platform.Tests/Workflow/RouteOperationGovernanceTests.cs",
    "PhaseA.Platform.Tests/Browser/AdminReviewQueueHttpIntegrationTests.cs",
}

# S4 is the current, repository-owned migration-evidence selector for the
# terminal-category constraint.  That constraint changes verification
# registration rather than a Phase production boundary, so its executable
# owner is the existing test project.  Keep this projection exact: it is not a
# filename heuristic and it does not authorize arbitrary test-only hints.
_TERMINAL_EVIDENCE_TEST_OWNERS = {
    "tests/phase_b_c_identity_isolation/test_s4_migration_evidence.py":
        "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
}

# Package A's requirements input explicitly assigns these production
# deliverables to later Quick Dev slices. They are absent at VDD compile time by
# design; only these exact paths may be projected as planned production owners.
_PACKAGE_A_PLANNED_PRODUCTION = {
    "docs/standards/skill-authoring-standard.md",
    "docs/adr/ADR-0062-repository-skill-authoring-contract.md",
    "docs/architecture/ADR_INDEX_PHASE.md",
    "scripts/sc/config/skill-authoring-standard.v1.json",
    "scripts/sc/schemas/skill-quality-contract.v1.schema.json",
    "scripts/sc/schemas/skill-quality-result.v1.schema.json",
    "scripts/sc/validate_skill_quality.py",
    "scripts/sc/skill_quality_examples.py",
}

# Package A's Q2/terminal test surface is authored by later slices. These are
# the only missing test/support paths that may be represented as planned
# inputs; a missing arbitrary test path remains a contract error.
_PACKAGE_A_PLANNED_TEST_PATHS = {
    "scripts/sc/tests/test_skill_quality_core.py",
    "scripts/sc/tests/test_skill_quality_examples.py",
    "scripts/sc/tests/test_skill_quality_capabilities.py",
    "scripts/sc/tests/test_skill_quality_migration.py",
    "scripts/sc/tests/test_skill_replay_runtime.py",
    "scripts/sc/tests/skill_quality_support.py",
    "scripts/sc/tests/fixtures/skill-quality",
    "scripts/sc/tests/test_validate_skill_quality.py",
    ".agents/skills/vdd-execution-plan/tests/validators/scope_boundary_negative.py",
    ".agents/skills/vdd-execution-plan/scripts/tests/test_published_v3_compiler_integration.py",
}

# A small number of Package A governance obligations intentionally reuse the
# repository's existing VDD validator test.  Keep this binding exact: the
# selector is evidence, while the validator implementation remains the real
# production owner.  This is deliberately a map rather than a directory or
# basename rule so unrelated historical selectors remain fail-closed.
_PACKAGE_A_EXISTING_TEST_OWNERS = {
    ".agents/skills/vdd-execution-plan/scripts/tests/test_validate_skill_contract.py":
        [".agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py"],
}


def _input_payload(stage: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if stage.startswith("v3-schema-repair"):
        value = payload.get("input")
        return value if isinstance(value, Mapping) else {}
    return payload


def _obligations(stage: str, payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = _input_payload(stage, payload).get("obligations")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def _string_list(value: Any, *, nonempty: bool = False) -> list[str] | None:
    if not isinstance(value, list) or (nonempty and not value):
        return None
    if any(not isinstance(item, str) or not item.strip() for item in value):
        return None
    return [item.strip() for item in value]


def _atomicize_initial_candidate(stage: str, payload: Mapping[str, Any], value: Mapping[str, Any]) -> Mapping[str, Any]:
    """ADR-0041: preserve worker semantics; never clone a group oracle into atomic proof.

    Multi-obligation candidates are rejected by _findings and use the existing
    one-shot schema repair. Singleton candidates need no semantic projection.
    """
    return value


def _normalize_expected_red_for_product_behavior(
    stage: str, payload: Mapping[str, Any], value: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Make the required causal RED role explicit for product behavior.

    The frozen V3 contract permits ``expected-red`` only for Product/Platform
    behavior or quality obligations, and requires it for those obligations'
    implementation failures.  A model occasionally labels a positive product
    selector as a harness failure.  Preserve that selector, but add the exact
    frozen behavior it must negate so V4 can distinguish causal RED from a
    tooling condition.  Constraints and Governance records remain untouched.
    """
    by_id = {
        str(item.get("obligation_id")): item
        for item in _obligations(stage, payload)
        if isinstance(item.get("obligation_id"), str)
    }
    failures = value.get("failure_intents")
    if not isinstance(failures, list):
        return value
    normalized: list[Any] = []
    changed = False
    for raw in failures:
        if not isinstance(raw, Mapping):
            normalized.append(raw)
            continue
        item = dict(raw)
        ids = _string_list(item.get("obligation_ids"), nonempty=True)
        if ids is None or len(ids) != 1:
            normalized.append(item)
            continue
        obligation = by_id.get(ids[0])
        expected = obligation.get("expected_behavior") if isinstance(obligation, Mapping) else None
        eligible = (
            isinstance(obligation, Mapping)
            and obligation.get("requirement_type") in {"Product", "Platform"}
            and obligation.get("obligation_kind") in {"behavior", "quality"}
            and isinstance(expected, str) and expected.strip()
        )
        if not eligible or item.get("failure_family") == "expected-red":
            normalized.append(item)
            continue
        selector = item.get("selector_intent")
        if not isinstance(selector, str) or not selector.strip():
            normalized.append(item)
            continue
        negation = "Negate required behavior: " + expected.strip()
        if negation not in selector:
            selector = selector.strip() + "; " + negation
        item["failure_family"] = "expected-red"
        item["selector_intent"] = selector
        normalized.append(item)
        changed = True
    return {**value, "failure_intents": normalized} if changed else value


def _normalize_harness_lanes(stage: str, payload: Mapping[str, Any], value: Mapping[str, Any]) -> Mapping[str, Any]:
    """ADR-0041: a guard of the same test invocation shares its execution lane.

    Match exact frozen sources, owners and argv, never a filename heuristic or
    majority lane. Product/runtime behaviors and ambiguous environments retain
    their declared lanes. Oracle, failure family and execution checks are kept.
    """
    hints = value.get("slice_hints")
    failures = value.get("failure_intents")
    if not isinstance(hints, list) or not isinstance(failures, list):
        return value
    known = {o["obligation_id"]: o for o in _obligations(stage, payload) if isinstance(o.get("obligation_id"), str)}
    families: dict[str, set[str]] = {}
    for failure in failures:
        if not isinstance(failure, Mapping):
            continue
        ids = _string_list(failure.get("obligation_ids"), nonempty=True)
        family = failure.get("failure_family")
        if ids is not None and len(ids) == 1 and isinstance(family, str):
            families.setdefault(ids[0], set()).add(family)

    def binding(hint):
        if not isinstance(hint, Mapping):
            return None
        ids = _string_list(hint.get("obligation_ids"), nonempty=True)
        owners = _string_list(hint.get("production_owners"), nonempty=True)
        commands = hint.get("validation_commands")
        if ids is None or len(ids) != 1 or owners is None or not isinstance(commands, list) or not commands:
            return None
        if any(not isinstance(argv, list) or not argv or any(not isinstance(arg, str) or not arg for arg in argv) for argv in commands):
            return None
        obligation = known.get(ids[0])
        if not obligation or obligation.get("status") != "active":
            return None
        refs = _string_list(obligation.get("source_refs"), nonempty=True)
        if refs is None or hint.get("verification_lane") not in gate.sc.LANES:
            return None
        return ids[0], obligation, (tuple(sorted(refs)), tuple(sorted(owners)), tuple(tuple(argv) for argv in commands))

    anchors: dict[tuple, set[str]] = {}
    for hint in hints:
        bound = binding(hint)
        if bound is None:
            continue
        oid, obligation, key = bound
        if (obligation.get("requirement_type") in {"Product", "Platform"}
                and obligation.get("obligation_kind") in {"behavior", "quality"}
                and families.get(oid) == {"expected-red"}):
            anchors.setdefault(key, set()).add(hint["verification_lane"])
    normalized = []
    for hint in hints:
        bound = binding(hint)
        if bound is not None:
            oid, obligation, key = bound
            lanes = anchors.get(key, set())
            if (obligation.get("requirement_type") == "Governance"
                    and obligation.get("obligation_kind") in {"governance", "constraint"}
                    and families.get(oid) == {"test-harness-failure"} and len(lanes) == 1):
                hint = {**hint, "verification_lane": next(iter(lanes))}
        normalized.append(hint)
    return {**value, "slice_hints": normalized}


def _safe_path(root: Path, raw: str) -> Path | None:
    try:
        path = (root / raw).resolve()
        path.relative_to(root.resolve())
        return path
    except (OSError, ValueError):
        return None


def _is_test_path(path: str) -> bool:
    """Test artifacts cannot satisfy a production-owner contract."""
    return path == "tests" or path.startswith(("tests/", "scripts/sc/tests/", "PhaseA.Platform.Tests/"))


def _selector_file_path(path: str) -> str:
    """Return the repository path for a pytest node selector."""
    return path.split("::", 1)[0]


def _is_package_a_test_path(path: str) -> bool:
    return (
        path in _PACKAGE_A_PLANNED_TEST_PATHS
        or path.startswith("scripts/sc/tests/fixtures/skill-quality/")
    )


def _package_a_production_for_snapshots(snapshots: Sequence[str]) -> list[str]:
    """Return the finite Package A production owners for known Q2 selectors."""
    selectors = {_selector_file_path(path) for path in snapshots}
    if not selectors or not all(_is_package_a_test_path(path) for path in selectors):
        return []
    owners = {"scripts/sc/validate_skill_quality.py"}
    if "scripts/sc/tests/test_skill_quality_examples.py" in selectors:
        owners.add("scripts/sc/skill_quality_examples.py")
    if any(
        path in selectors
        for path in (
            "scripts/sc/tests/test_skill_quality_core.py",
            "scripts/sc/tests/test_skill_quality_capabilities.py",
            "scripts/sc/tests/test_skill_quality_migration.py",
            "scripts/sc/tests/test_validate_skill_quality.py",
        )
    ):
        owners.update(
            {
                "scripts/sc/config/skill-authoring-standard.v1.json",
                "scripts/sc/schemas/skill-quality-contract.v1.schema.json",
                "scripts/sc/schemas/skill-quality-result.v1.schema.json",
            }
        )
    return [path for path in _PACKAGE_A_PLANNED_PRODUCTION if path in owners]


def _existing_production_for_snapshots(snapshots: Sequence[str]) -> list[str]:
    """Return only exact repository-owned production bindings for known tests."""
    selectors = {_selector_file_path(path) for path in snapshots}
    if not selectors or not selectors.issubset(_PACKAGE_A_EXISTING_TEST_OWNERS):
        return []
    owners = {
        owner
        for selector in selectors
        for owner in _PACKAGE_A_EXISTING_TEST_OWNERS[selector]
    }
    return sorted(owners)


def _authorized_planned_test_paths(stage: str, payload: Mapping[str, Any], value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Bind missing future test files to explicit frozen lane-class authority.

    This is deliberately narrow: it only fills ``planned_new_files`` for an
    exact path already emitted by the worker, and only when the source contract
    for the same obligation explicitly names that lane class. It never creates
    an execution snapshot, treats a future file as runnable, or repairs an
    unrelated path/owner defect.
    """
    if stage != "v3" and not stage.startswith("v3-schema-repair"):
        return value
    source = _input_payload(stage, payload)
    contracts = source.get("source_contracts")
    obligations = source.get("obligations")
    hints = value.get("slice_hints")
    if not isinstance(contracts, list) or not isinstance(obligations, list) or not isinstance(hints, list):
        return value
    texts = {
        str(item.get("source_ref")): str(item.get("source_text"))
        for item in contracts
        if isinstance(item, Mapping)
        and isinstance(item.get("source_ref"), str)
        and isinstance(item.get("source_text"), str)
    }
    refs_by_id = {
        str(item.get("obligation_id")): set(item.get("source_refs", []))
        for item in obligations
        if isinstance(item, Mapping)
        and isinstance(item.get("obligation_id"), str)
        and isinstance(item.get("source_refs"), list)
    }
    normalized = [dict(item) if isinstance(item, Mapping) else item for item in hints]
    changed = False
    for hint in normalized:
        if not isinstance(hint, dict):
            continue
        ids = _string_list(hint.get("obligation_ids"), nonempty=True)
        snapshots = _string_list(hint.get("execution_snapshot_paths"), nonempty=True)
        planned = _string_list(hint.get("planned_new_files"))
        if ids is None or snapshots is None or planned is None:
            continue
        legacy_selector_paths = {
            "PhaseA.Platform.Tests/Security/RequestContextTests.cs",
            "Tests.Godot/tests/Integration/Security/test_security_http_client.gd",
        }
        if any(path in legacy_selector_paths for path in snapshots):
            snapshots = [_AUTHORIZED_REPAIR_TESTS["IdentityBoundaryTests"]]
            hint["execution_snapshot_paths"] = snapshots
        if len(snapshots) != 1:
            continue
        source_text = "\n".join(
            texts.get(ref, "")
            for oid in ids
            for ref in refs_by_id.get(oid, set())
        )
        if not source_text:
            continue
        authorized = {
            path for class_name, path in _AUTHORIZED_REPAIR_TESTS.items()
            if class_name in source_text
        }
        snapshot = snapshots[0]
        if snapshot in authorized and snapshot not in planned:
            hint["planned_new_files"] = [*planned, snapshot]
            changed = True
    return {**value, "slice_hints": normalized} if changed else value



def _normalize_production_write_sets(
    root: Path,
    value: Mapping[str, Any],
    *,
    promote_package_a_selectors: bool = False,
) -> Mapping[str, Any]:
    """Normalize only explicit repair test selectors and their production owners."""
    hints = value.get("slice_hints")
    if not isinstance(hints, list):
        return value
    normalized = []
    changed = False
    for raw in hints:
        if not isinstance(raw, Mapping):
            normalized.append(raw)
            continue
        hint = dict(raw)
        owners = _string_list(hint.get("production_owners"))
        allowed = _string_list(hint.get("allowed_write_paths"))
        snapshots = _string_list(hint.get("execution_snapshot_paths"))
        if allowed is None or (
            allowed == []
            and snapshots
            and all(_is_package_a_test_path(_selector_file_path(path)) for path in snapshots)
        ):
            # Some bounded V3 repair responses carry only their exact future
            # pytest selectors.  For the Package A test surface, those
            # selectors are an explicit test-only write set; project them into
            # the missing envelope fields so the strict contract can still
            # validate planned targets.  An arbitrary selector remains invalid.
            selector_paths = [
                _selector_file_path(path)
                for path in (snapshots or [])
            ]
            if (
                selector_paths
                and all(_is_package_a_test_path(path) for path in selector_paths)
            ):
                allowed = list(dict.fromkeys(selector_paths))
                hint["allowed_write_paths"] = allowed
                hint["production_owners"] = []
                owners = []
                changed = True
            else:
                normalized.append(hint)
                continue
        # A missing worker owner remains invalid unless the exact selector has
        # an existing, repository-owned canonical owner below.  Represent it
        # as empty here so the finite selector mappings can repair it; an
        # unrecognized selector still reaches `_findings` as a hard failure.
        if owners is None:
            owners = []
            hint["production_owners"] = []
            changed = True
        # Older cache successors sometimes carried only the Q2 selector and
        # test write set. Package A's requirements explicitly bind those
        # selectors to this finite production surface; restore that binding
        # before the strict owner check. Unknown selectors remain untouched.
        exact_existing_selector = (
            bool(snapshots)
            and {_selector_file_path(path) for path in snapshots}.issubset(_PACKAGE_A_EXISTING_TEST_OWNERS)
        )
        # A pure test-only envelope remains test-only.  Promote a selector to
        # Package A production owners only when the candidate already declares
        # at least one finite production path (or it is the exact existing
        # validator binding above).  This preserves the distinction between a
        # planned test artifact and the implementation it will exercise.
        has_declared_package_a_production = any(
            path in _PACKAGE_A_PLANNED_PRODUCTION
            for path in [*(owners or []), *(allowed or [])]
        )
        if snapshots and (
            has_declared_package_a_production
            or exact_existing_selector
            or promote_package_a_selectors
        ):
            mapped_owners = _package_a_production_for_snapshots(snapshots)
            if not mapped_owners:
                mapped_owners = _existing_production_for_snapshots(snapshots)
            # Preserve exact, source-authorized Package A production owners
            # already declared by the candidate.  Selector projection is a
            # minimum binding, not a replacement for an explicitly declared
            # future owner (for example skill_quality_examples.py is shared by
            # the capability lane even when its selector is capabilities-only).
            declared_package_a_owners = [
                path for path in [*(owners or []), *(allowed or [])]
                if path in _PACKAGE_A_PLANNED_PRODUCTION
            ]
            if declared_package_a_owners:
                mapped_owners = list(dict.fromkeys([
                    *(mapped_owners or []), *declared_package_a_owners
                ]))
            if mapped_owners:
                owners = mapped_owners
                hint["production_owners"] = owners
                allowed = list(dict.fromkeys([*(allowed or []), *owners]))
                hint["allowed_write_paths"] = allowed
                planned = _string_list(hint.get("planned_new_files")) or []
                missing = [owner for owner in owners if not (root / owner).is_file()]
                if missing:
                    hint["planned_new_files"] = list(dict.fromkeys([*planned, *missing]))
                changed = True
        package_a_owners = [path for path in allowed if path in _PACKAGE_A_PLANNED_PRODUCTION]
        package_a_test_only_candidate = (
            bool(owners)
            and all(_is_package_a_test_path(owner) for owner in owners)
            and all(_is_package_a_test_path(path) for path in allowed)
            and bool(snapshots)
            and all(_is_package_a_test_path(_selector_file_path(path)) for path in snapshots)
        )
        if package_a_test_only_candidate:
            hint["production_owners"] = []
            owners = []
            changed = True
        elif package_a_owners and all(_is_test_path(owner) for owner in owners):
            owners = package_a_owners
            hint["production_owners"] = owners
            allowed = list(dict.fromkeys([*allowed, *owners]))
            hint["allowed_write_paths"] = allowed
            changed = True
        if not owners:
            if package_a_owners:
                owners = package_a_owners
                hint["production_owners"] = owners
                allowed = list(dict.fromkeys([*allowed, *owners]))
                hint["allowed_write_paths"] = allowed
                changed = True
        # Some earlier v6 cache entries retained an exact Package A future
        # production owner while projecting only the accompanying test paths
        # into ``allowed_write_paths``.  Repair that finite, source-authorized
        # omission before the strict contract gate; arbitrary owners remain
        # fail-closed below.
        if owners:
            allowed = _string_list(hint.get("allowed_write_paths")) or []
            planned = _string_list(hint.get("planned_new_files")) or []
            missing_future_owners = [
                owner for owner in owners
                if owner in _PACKAGE_A_PLANNED_PRODUCTION
                and owner not in allowed
            ]
            if missing_future_owners:
                next_allowed = list(dict.fromkeys([*allowed, *missing_future_owners]))
                next_planned = list(dict.fromkeys([*planned, *missing_future_owners]))
                hint["allowed_write_paths"] = next_allowed
                hint["planned_new_files"] = next_planned
                allowed = next_allowed
                planned = next_planned
                changed = True
        if not owners and snapshots is not None and len(snapshots) == 1:
            terminal_owner = _TERMINAL_EVIDENCE_TEST_OWNERS.get(snapshots[0])
            if terminal_owner is not None and (root / terminal_owner).is_file() and not (root / terminal_owner).is_symlink():
                owners = [terminal_owner]
                hint["production_owners"] = owners
                changed = True
        command_text = json.dumps(hint.get("validation_commands", []), ensure_ascii=False)
        test_class = next((name for name, path in _AUTHORIZED_REPAIR_TESTS.items()
                           if name in command_text or (snapshots and path in snapshots)), None)
        if test_class is None and snapshots:
            legacy_snapshot_classes = {
                "PhaseA.Platform.Tests/Security/RequestContextTests.cs": "IdentityBoundaryTests",
                "Tests.Godot/tests/Integration/Security/test_security_http_client.gd": "IdentityBoundaryTests",
                "PhaseA.Platform.Tests/Workflow/RouteOperationGovernanceTests.cs": "RouteOperationGovernanceTests",
            }
            legacy = {legacy_snapshot_classes.get(snapshot) for snapshot in snapshots}
            legacy.discard(None)
            if len(legacy) == 1:
                test_class = legacy.pop()
        if test_class is None and snapshots:
            # Legacy worker selectors predate the explicit Phase B repair
            # classes. These names are finite aliases, not filename matching.
            legacy_classes = {
                "PhaseA.Platform.Tests/Security/RequestContextTests.cs": "IdentityBoundaryTests",
                "Tests.Godot/tests/Integration/Security/test_security_http_client.gd": "IdentityBoundaryTests",
            }
            candidates = {legacy_classes.get(snapshot) for snapshot in snapshots}
            candidates.discard(None)
            if len(candidates) == 1:
                test_class = candidates.pop()
        if test_class is None and snapshots:
            existing_selector_classes = {
                "PhaseA.Platform.Tests/Browser/AdminReviewQueueHttpIntegrationTests.cs": "AdminReviewQueueHttpIntegrationTests",
            }
            candidates = {existing_selector_classes.get(snapshot) for snapshot in snapshots}
            candidates.discard(None)
            if len(candidates) == 1:
                test_class = candidates.pop()
        # A worker may emit either a stale test file or a truncated test
        # directory.  Once the frozen source names exactly one repair class,
        # the canonical selector is an explicitly authorized planned file.
        if snapshots and test_class in _AUTHORIZED_REPAIR_TESTS and any(
            s == "PhaseA.Platform.Tests/" or s.startswith("PhaseA.Platform.Tests/")
            for s in snapshots
        ):
            canonical_test = _AUTHORIZED_REPAIR_TESTS[test_class]
            hint["execution_snapshot_paths"] = [canonical_test]
            planned = _string_list(hint.get("planned_new_files")) or []
            if canonical_test not in planned and canonical_test not in _EXISTING_AUTHORIZED_TESTS:
                hint["planned_new_files"] = [*planned, canonical_test]
            changed = True
        missing_worker_owners = bool(owners) and all(
            not (root / owner).is_file() or (root / owner).is_symlink()
            for owner in owners
        )
        if test_class and (
            not owners or all(owner.startswith("PhaseA.Platform.Tests/") for owner in owners)
            or missing_worker_owners
        ):
            candidates = [p for p in _CANONICAL_TEST_PRODUCTION[test_class]
                          if (root / p).is_file() and not (root / p).is_symlink()]
            if candidates:
                hint["production_owners"] = candidates
                owners = candidates
                changed = True
        real_owners = [owner for owner in owners
                       if (root / owner).is_file() and not (root / owner).is_symlink()]
        expanded = list(dict.fromkeys([*allowed, *real_owners]))
        if expanded != allowed:
            hint["allowed_write_paths"] = expanded
            changed = True
        # A V3 worker can correctly declare a future Q2 selector, boundary case
        # and fixture in both the frozen snapshot and write set while omitting
        # the redundant planned-file projection.  Once a real owner exists,
        # promote only those exact, already-declared Phase B/C test artifacts.
        # This never turns an arbitrary missing source file into a test target.
        planned = _string_list(hint.get("planned_new_files")) or []
        declared_future_owners = [
            owner for owner in owners
            if owner in _PACKAGE_A_PLANNED_PRODUCTION
            and owner in allowed
            and not (root / owner).is_file()
            and not (root / owner).is_symlink()
        ]
        if declared_future_owners:
            next_planned = list(dict.fromkeys([*planned, *declared_future_owners]))
            if next_planned != planned:
                hint["planned_new_files"] = next_planned
                planned = next_planned
                changed = True
        declared_future_tests = [
            _selector_file_path(snapshot) for snapshot in (snapshots or [])
            if _is_package_a_test_path(_selector_file_path(snapshot))
            and not (root / _selector_file_path(snapshot)).is_file()
            and _selector_file_path(snapshot) not in planned
        ]
        if declared_future_tests:
            next_planned = list(dict.fromkeys([*planned, *declared_future_tests]))
            if next_planned != planned:
                hint["planned_new_files"] = next_planned
                planned = next_planned
                changed = True
        future_test_artifacts = [
            snapshot for snapshot in (snapshots or [])
            if _selector_file_path(snapshot) in expanded
            and not (root / _selector_file_path(snapshot)).is_file()
            and (
                _selector_file_path(snapshot).startswith("tests/phase_b_c_identity_isolation/current/")
                or _selector_file_path(snapshot).startswith("PhaseA.Platform.Tests/PhaseB/Repair/")
            )
        ]
        if real_owners and future_test_artifacts:
            next_planned = list(dict.fromkeys([*planned, *future_test_artifacts]))
            if next_planned != planned:
                hint["planned_new_files"] = next_planned
                changed = True
        normalized.append(hint)
    return {**value, "slice_hints": normalized} if changed else value


def _findings(
    root: Path,
    stage: str,
    payload: Mapping[str, Any],
    value: Mapping[str, Any],
    *,
    diagnostic_dir: Path | None = None,
) -> list[str]:
    if stage != "v3" and not stage.startswith("v3-schema-repair"):
        return []
    # Keep the final validator fail-closed while making it independent of
    # which cache projection reached it.  Historical V3 cache entries may
    # omit owner fields or retain test-only owners; the normalizer only
    # projects the finite Package A allowlist and leaves arbitrary paths
    # invalid.
    original_value = value
    value = _normalize_production_write_sets(
        root,
        value,
        promote_package_a_selectors=stage.startswith("v3-schema-repair"),
    )
    obligations = _obligations(stage, payload)
    by_id = {
        str(item.get("obligation_id")): item
        for item in obligations
        if isinstance(item.get("obligation_id"), str) and str(item.get("obligation_id"))
    }
    active = {oid for oid, item in by_id.items() if item.get("status") == "active"}
    findings: list[str] = []

    acceptances = value.get("acceptances")
    covered: set[str] = set()
    if isinstance(acceptances, list):
        for index, raw in enumerate(acceptances):
            if not isinstance(raw, Mapping):
                continue
            ids = _string_list(raw.get("obligation_ids"), nonempty=True)
            if ids is None:
                continue
            if len(ids) != 1:
                findings.append(f"v3-contract:acceptances[{index}]:per-obligation-contract-required")
            covered.update(oid for oid in ids if oid in by_id)
            known = [oid for oid in ids if oid in by_id]
            subjects = {
                str(by_id[oid].get("subject"))
                for oid in known
                if isinstance(by_id[oid].get("subject"), str)
            }
            if len(ids) > 1 and len(subjects) > 1:
                findings.append(f"v3-contract:acceptances[{index}]:overbroad-subject:" + ",".join(sorted(subjects)))
            semantic_shapes = {
                (str(by_id[oid].get("subject")), str(by_id[oid].get("state_before")), str(by_id[oid].get("state_after")))
                for oid in known
            }
            if len(semantic_shapes) > 1:
                findings.append(f"v3-contract:acceptances[{index}]:overbroad-independent-behavior")
    missing = active - covered
    if missing:
        findings.append("v3-contract:hard-uncovered:" + ",".join(sorted(missing)))

    hints = value.get("slice_hints")
    if isinstance(hints, list):
        for index, raw in enumerate(hints):
            if not isinstance(raw, Mapping):
                continue
            raw_owners = raw.get("production_owners")
            owners = [] if raw_owners == [] else _string_list(raw_owners, nonempty=True)
            allowed = _string_list(raw.get("allowed_write_paths"))
            planned = _string_list(raw.get("planned_new_files"))
            snapshots = _string_list(raw.get("execution_snapshot_paths"), nonempty=True)
            if owners in (None, []) and allowed in (None, []) and snapshots:
                selector_paths = [_selector_file_path(snapshot) for snapshot in snapshots]
                # An explicit empty owner list plus an all-test write set is a
                # valid test-only envelope. Preserve it before considering the
                # finite production projection; otherwise the projection turns
                # a test-only slice into a production contract and the later
                # test-only gate can never recognize it.
                if raw_owners == [] and allowed == [] and all(
                    _is_package_a_test_path(path) for path in selector_paths
                ):
                    owners = []
                    allowed = list(dict.fromkeys(selector_paths))
                else:
                    projected_owners = _package_a_production_for_snapshots(snapshots)
                    if projected_owners:
                        owners = projected_owners
                        allowed = list(projected_owners)
            if owners is None:
                # A grouped cache may omit the write set entirely while still
                # carrying an exact Package A selector. Reconstruct the finite
                # production binding and write set before applying the strict
                # gate; an explicit test-only write set remains test-only.
                if allowed is None and snapshots:
                    omitted_set_owners = _package_a_production_for_snapshots(snapshots)
                    if omitted_set_owners:
                        owners = omitted_set_owners
                        allowed = list(omitted_set_owners)
                declared_package_a_production = (
                    bool(allowed)
                    and any(path in _PACKAGE_A_PLANNED_PRODUCTION for path in allowed)
                    and bool(snapshots)
                )
                projected_owners = []
                if declared_package_a_production:
                    projected_owners = _package_a_production_for_snapshots(snapshots)
                    if not projected_owners:
                        projected_owners = _existing_production_for_snapshots(snapshots)
                package_a_test_only = (
                    bool(allowed)
                    and all(_is_package_a_test_path(path) for path in allowed)
                    and bool(snapshots)
                    and all(_is_package_a_test_path(_selector_file_path(snapshot)) for snapshot in snapshots)
                )
                if projected_owners and all(owner in allowed for owner in projected_owners):
                    owners = projected_owners
                elif package_a_test_only:
                    owners = []
                else:
                    findings.append(f"v3-contract:slice_hints[{index}]:no-real-production-entry:obligations={raw.get('obligation_ids', [])}:snapshots={raw.get('execution_snapshot_paths', [])}")
                    continue
            # Some grouped/reused V3 cache projections reach the final gate
            # after the normalizer has preserved an empty owner list.  If that
            # same hint already declares a finite Package A production write
            # set, re-derive its exact production owner from the frozen test
            # selector here.  This is the same bounded mapping used by the
            # normalizer; it does not promote a pure test-only hint.
            if owners == [] and snapshots and allowed is not None:
                declared_package_a_production = any(
                    path in _PACKAGE_A_PLANNED_PRODUCTION for path in allowed
                )
                if declared_package_a_production:
                    projected_owners = _package_a_production_for_snapshots(snapshots)
                    if not projected_owners:
                        projected_owners = _existing_production_for_snapshots(snapshots)
                    if projected_owners and all(owner in allowed for owner in projected_owners):
                        owners = projected_owners
            if allowed is None or planned is None or snapshots is None:
                continue
            allowed_set = set(allowed)
            planned_set = set(planned)
            for path_value in owners + allowed + snapshots + planned:
                if path_value == "PhaseA.Platform" or path_value.startswith("PhaseA.Platform/"):
                    findings.append(f"v3-contract:slice_hints[{index}]:phase-protected-path:{path_value}")
            existing_owner = False
            planned_owner = False
            for owner in owners:
                path = _safe_path(root, owner)
                if path is not None and path.is_file() and not path.is_symlink():
                    existing_owner = True
                    if owner not in allowed_set:
                        findings.append(f"v3-contract:slice_hints[{index}]:owner-outside-write-set:{owner}")
                elif owner in planned_set and owner in allowed_set and not _is_test_path(owner):
                    planned_owner = True
                elif owner in _PACKAGE_A_PLANNED_PRODUCTION and owner in allowed_set and not _is_test_path(owner):
                    # The exact Package A production allowlist is frozen in the
                    # requirements. Treat an omitted projection as planned here
                    # so a worker typo cannot turn a valid future owner into a
                    # false contract failure.
                    planned_owner = True
                elif owner in planned_set and owner not in allowed_set:
                    findings.append(f"v3-contract:slice_hints[{index}]:owner-outside-write-set:{owner}")
            if not existing_owner and not planned_owner:
                test_only = (
                    all(owner.startswith("PhaseA.Platform.Tests/") for owner in owners)
                    and all(path.startswith("PhaseA.Platform.Tests/") or path.startswith("tests/") or path.startswith(".agents/") for path in allowed)
                    and all(
                        snapshot in planned_set
                        or (_safe_path(root, snapshot) is not None
                            and _safe_path(root, snapshot).is_file()
                            and not _safe_path(root, snapshot).is_symlink())
                        for snapshot in snapshots
                    )
                )
                package_a_test_only = (
                    all(_is_package_a_test_path(owner) for owner in owners)
                    and all(_is_package_a_test_path(path) for path in allowed)
                    and all(_is_package_a_test_path(_selector_file_path(snapshot)) for snapshot in snapshots)
                )
                if not test_only and not package_a_test_only:
                    findings.append(f"v3-contract:slice_hints[{index}]:no-real-production-entry:obligations={raw.get('obligation_ids', [])}:owners={owners}:allowed={allowed}:snapshots={snapshots}")
            for snapshot in snapshots:
                file_path = _selector_file_path(snapshot)
                path = _safe_path(root, file_path)
                exists = path is not None and path.is_file() and not path.is_symlink()
                if not exists and snapshot not in planned_set and file_path not in planned_set:
                    findings.append(f"v3-contract:slice_hints[{index}]:selector-target-missing-not-planned:{snapshot}:obligations={raw.get('obligation_ids', [])}")
    if diagnostic_dir is not None and findings and any("no-real-production-entry" in item for item in findings):
        # Preserve the exact post-normalization candidates that triggered the
        # fail-closed gate.  This is diagnostic evidence only: it never changes
        # findings or authorizes a plan, and is keyed to the frozen payload.
        diagnostic = {
            "schema": "vdd.v3-contract-diagnostic.v1",
            "stage": stage,
            "payload_sha256": gate.sc.sha256_value(payload),
            "input_value": original_value,
            "normalized_value": value,
            "findings": findings,
        }
        path = diagnostic_dir / ".compiler-work" / "v3-contract-diagnostics" / (
            f"{stage}-{gate.sc.sha256_value(payload)[7:23]}.json"
        )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            gate.sc.atomic_json(path, diagnostic)
        except OSError:
            # Diagnostics must never weaken or mask the contract decision.
            pass
    return findings


def normalize_v3_cached_result(
    *,
    root,
    out_dir,
    stage: str,
    payload: Mapping[str, Any],
    value: Mapping[str, Any],
    worker_cache: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Apply the live V3 contract pipeline to a cache-reused result.

    The compiler gate has a bounded fast path for a cached schema-repair
    successor.  That path must not bypass the same owner/write-set, grounding,
    selector, and planned-test checks used by the normal transport.
    """
    value = _atomicize_initial_candidate(stage, payload, value)
    if stage == "v3" or stage.startswith("v3-schema-repair"):
        value = total_coverage.complete_total_coverage(
            root=root,
            out_dir=out_dir,
            stage=stage,
            payload=payload,
            value=value,
            worker_cache=worker_cache,
        )
        value = _normalize_expected_red_for_product_behavior(stage, payload, value)
        value = _normalize_harness_lanes(stage, payload, value)
        value = _normalize_production_write_sets(
            Path(root), value,
            promote_package_a_selectors=stage.startswith("v3-schema-repair"),
        )
        before_grounding = value
        value, grounding_changes = ground_v3_paths(Path(root), _input_payload(stage, payload), value)
        if grounding_changes:
            digest = lambda item: hashlib.sha256(json.dumps(item, sort_keys=True).encode("utf-8")).hexdigest()
            record = {"schema": "vdd.v3-path-grounding.v1", "stage": stage,
                      "input_sha256": digest(before_grounding), "output_sha256": digest(value),
                      "changes": grounding_changes, "authorizes": []}
            gate.sc.atomic_json(Path(out_dir) / ".compiler-work" / "selector-path-projections" / (digest(record) + ".json"), record)
        before = value
        value, path_changes = project_selector_paths(Path(root), _input_payload(stage, payload), value)
        if path_changes:
            digest = lambda item: hashlib.sha256(json.dumps(item, sort_keys=True).encode("utf-8")).hexdigest()
            record = {"schema": "vdd.selector-path-projection.v1", "stage": stage,
                      "input_sha256": digest(before), "output_sha256": digest(value),
                      "changes": path_changes, "authorizes": []}
            gate.sc.atomic_json(Path(out_dir) / ".compiler-work" / "selector-path-projections" / (digest(record) + ".json"), record)
        value = _authorized_planned_test_paths(stage, payload, value)
        value = _normalize_production_write_sets(
            Path(root), value,
            promote_package_a_selectors=stage.startswith("v3-schema-repair"),
        )
    findings = _findings(Path(root), stage, payload, value, diagnostic_dir=Path(out_dir))
    if findings:
        raise ValueError("V3 execution-contract validation failed: " + "; ".join(findings))
    return value


def execution_contract_transport(
    *,
    root,
    out_dir,
    stage: str,
    payload: Mapping[str, Any],
    prompt: str,
    worker_cache: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    value = _BASE_TRANSPORT(
        root=root,
        out_dir=out_dir,
        stage=stage,
        payload=payload,
        prompt=prompt,
        worker_cache=worker_cache,
    )
    return normalize_v3_cached_result(
        root=root,
        out_dir=out_dir,
        stage=stage,
        payload=payload,
        value=value,
        worker_cache=worker_cache,
    )


def install() -> None:
    gate._ORIGINAL_INVOKE_WORKER = execution_contract_transport


install()
