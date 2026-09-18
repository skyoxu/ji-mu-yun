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



def _normalize_production_write_sets(root: Path, value: Mapping[str, Any]) -> Mapping[str, Any]:
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
        if allowed is None:
            normalized.append(hint)
            continue
        # A missing worker owner remains invalid unless the exact selector has
        # an existing, repository-owned canonical owner below.  Represent it
        # as empty here so the finite selector mappings can repair it; an
        # unrecognized selector still reaches `_findings` as a hard failure.
        if owners is None:
            owners = []
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
        future_test_artifacts = [
            snapshot for snapshot in (snapshots or [])
            if snapshot in expanded
            and not (root / snapshot).is_file()
            and (
                snapshot.startswith("tests/phase_b_c_identity_isolation/current/")
                or snapshot.startswith("PhaseA.Platform.Tests/PhaseB/Repair/")
            )
        ]
        if real_owners and future_test_artifacts:
            next_planned = list(dict.fromkeys([*planned, *future_test_artifacts]))
            if next_planned != planned:
                hint["planned_new_files"] = next_planned
                changed = True
        normalized.append(hint)
    return {**value, "slice_hints": normalized} if changed else value


def _findings(root: Path, stage: str, payload: Mapping[str, Any], value: Mapping[str, Any]) -> list[str]:
    if stage != "v3" and not stage.startswith("v3-schema-repair"):
        return []
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
            owners = _string_list(raw.get("production_owners"), nonempty=True)
            allowed = _string_list(raw.get("allowed_write_paths"))
            planned = _string_list(raw.get("planned_new_files"))
            snapshots = _string_list(raw.get("execution_snapshot_paths"), nonempty=True)
            if owners is None:
                findings.append(f"v3-contract:slice_hints[{index}]:no-real-production-entry:obligations={raw.get('obligation_ids', [])}:snapshots={raw.get('execution_snapshot_paths', [])}")
                continue
            if allowed is None or planned is None or snapshots is None:
                continue
            allowed_set = set(allowed)
            planned_set = set(planned)
            existing_owner = False
            for owner in owners:
                path = _safe_path(root, owner)
                if path is not None and path.is_file() and not path.is_symlink():
                    existing_owner = True
                    if owner not in allowed_set:
                        findings.append(f"v3-contract:slice_hints[{index}]:owner-outside-write-set:{owner}")
            if not existing_owner:
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
                if not test_only:
                    findings.append(f"v3-contract:slice_hints[{index}]:no-real-production-entry:obligations={raw.get('obligation_ids', [])}:owners={owners}:allowed={allowed}:snapshots={snapshots}")
            for snapshot in snapshots:
                path = _safe_path(root, snapshot)
                exists = path is not None and path.is_file() and not path.is_symlink()
                if not exists and snapshot not in planned_set:
                    findings.append(f"v3-contract:slice_hints[{index}]:selector-target-missing-not-planned:{snapshot}:obligations={raw.get('obligation_ids', [])}")
    return findings


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
        value = _normalize_production_write_sets(Path(root), value)
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
        value = _normalize_production_write_sets(Path(root), value)
    findings = _findings(Path(root), stage, payload, value)
    if findings:
        raise ValueError("V3 execution-contract validation failed: " + "; ".join(findings))
    return value


def install() -> None:
    gate._ORIGINAL_INVOKE_WORKER = execution_contract_transport


install()
