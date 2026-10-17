"""Deterministic closure for a repaired Bootstrap manual-pause lineage."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from acceptance_core import InputError, canonical_hash
from bootstrap_integration import (
    BootstrapBindingError,
    build_minimal_review_scope,
    load_current_lineage_state,
    project_bootstrap_execution_state,
    project_bounded_review_route,
    replay_finalized_bootstrap_run,
)
from repair_completeness import audit_repair_completeness


_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_REQUIRED_AUTHORITIES = {
    ".agents/skills/run-refactor-implementation-acceptance/SKILL.md",
    "docs/adr/ADR-0054-refactor-acceptance-manual-pause-closure.md",
    "docs/standards/bootstrap-review-control-plane.md",
}
_PROTOCOL_REVIEW_REQUIRED_PATHS = _REQUIRED_AUTHORITIES | {
    ".agents/skills/run-phase-bootstrap-review/SKILL.md",
    ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py",
    ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-hard-limit-focused-recovery.v1.schema.json",
    ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-hard-limit-focused-repair-validation-envelope.v1.schema.json",
    ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-hard-limit-protocol-repair-authority.v1.schema.json",
    ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-focused-repair-verifier-output.v1.schema.json",
    ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py",
    ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_core.py",
    ".agents/skills/run-refactor-implementation-acceptance/scripts/bootstrap_integration.py",
    ".agents/skills/run-refactor-implementation-acceptance/scripts/execution_control.py",
    ".agents/skills/run-refactor-implementation-acceptance/scripts/manual_pause_closure.py",
    ".agents/skills/run-refactor-implementation-acceptance/scripts/repair_completeness.py",
    ".agents/skills/run-refactor-implementation-acceptance/scripts/review_cycle_policy.py",
    ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-manual-pause-closure-request.v1.schema.json",
    ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-manual-pause-closure-challenge.v1.schema.json",
    ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-manual-pause-closure.v1.schema.json",
    ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-repair-completeness.v1.schema.json",
}
_CLOSURE_SCHEMA_PATH = (
    ".agents/skills/run-refactor-implementation-acceptance/schemas/"
    "acceptance-manual-pause-closure.v1.schema.json"
)
_CLOSURE_SCHEMA_HASH = "sha256:78bf1168bb08bc52fc43e63647c02cd6cdda6f59798796b7329d8623c884ef0e"
_RUN_ARTIFACTS = {
    "reviewInput": "review-input.json",
    "preflightResult": "preflight-result.json",
    "gateState": "review-gate-state.json",
    "candidates": "review-candidates.json",
    "rejections": "review-rejections.json",
    "finalResult": "review-gate-result.json",
    "dispositions": "review-dispositions.json",
    "metrics": "review-metrics.json",
    "verifierOutput": "verifier-output.json",
}
_MANUAL_PAUSE_PROFILES = {
    "bootstrap-implementation-conformance",
    "bootstrap-upstream-plan",
}


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise InputError(f"{label} is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise InputError(f"{label} is invalid")
    return value


def _resolve(root: Path, relative: Any, label: str) -> Path:
    normalized = _relative(relative, label)
    path = (root / normalized).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise InputError(f"{label} escapes repository root") from exc
    return path


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"{label} is unreadable") from exc


def _binding(root: Path, value: Any, label: str) -> tuple[str, Path]:
    if (
        not isinstance(value, dict)
        or set(value) != {"path", "sha256"}
        or _HASH.fullmatch(str(value.get("sha256"))) is None
    ):
        raise InputError(f"{label} binding is invalid")
    relative = _relative(value["path"], label)
    path = _resolve(root, relative, label)
    if not path.is_file() or _file_hash(path) != value["sha256"]:
        raise InputError(f"{label} binding is stale")
    return relative, path


def _replay_manual_pause_route(
    root: Path,
    value: Any,
    target: str,
    family: str,
    lineage: dict[str, Any],
    repair_projection: Any,
) -> tuple[str, dict[str, Any]]:
    request_relative, request_path = _binding(root, value, "manual-pause route request")
    request = _read_json(request_path, "manual-pause route request")
    required = {"decision", "binding", "launch_authorization", "repository_root", "scope_inputs", "lineage_state", "repair_completeness", "repair_completeness_request"}
    if not isinstance(request, dict) or set(request) != required:
        raise InputError("manual-pause route request is invalid")
    repository_value = request.get("repository_root")
    if not isinstance(repository_value, str) or not repository_value.strip():
        raise InputError("manual-pause route repository root is invalid")
    repository_path = Path(repository_value)
    resolved_repository = (
        repository_path.resolve()
        if repository_path.is_absolute()
        else (root / repository_path).resolve()
    )
    if resolved_repository != root:
        raise InputError("manual-pause route repository root is invalid")
    if request.get("decision", {}).get("requirement") != "required":
        raise InputError("manual-pause route requirement decision is invalid")
    try:
        decision_profile = request["decision"].get(
            "profile", "bootstrap-implementation-conformance"
        )
        scope = build_minimal_review_scope(
            request["scope_inputs"],
            profile=decision_profile,
            lineage_paths=[target] if decision_profile == "bootstrap-skill-route" else None,
        )
        if scope.get("lineageAnchor") != target or scope.get("lineageFamilyId") != family:
            raise InputError("manual-pause route target lineage is invalid")
        if request.get("lineage_state") != lineage:
            raise InputError("manual-pause route lineage state is stale")
        replayed_repair = audit_repair_completeness(request["repair_completeness_request"])
        if replayed_repair != repair_projection or request.get("repair_completeness") != repair_projection:
            raise InputError("manual-pause route repair completeness is stale")
        state = project_bootstrap_execution_state(
            request["decision"],
            binding=request["binding"],
            launch_authorization=request["launch_authorization"],
        )
        bounded = project_bounded_review_route(
            request["decision"], scope, lineage, repair_projection
        )
    except BootstrapBindingError as exc:
        raise InputError("manual-pause route request cannot be replayed") from exc
    route = {
        "schemaVersion": "implementation-acceptance-bootstrap-route.v1",
        "bootstrapExecutionState": state,
        "reviewScope": scope,
        **bounded,
        "repairCompletenessRequest": request["repair_completeness_request"],
        "repairCompletenessRequestHash": canonical_hash(
            request["repair_completeness_request"]
        ),
        "nextAction": "manual-pause",
        "authorizes": [],
    }
    if route.get("routeKind") != "manual_pause":
        raise InputError("manual-pause route request does not project manual pause")
    return request_relative, route


def _validate_authorities(root: Path, values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        raise InputError("manual-pause protocol authorities are invalid")
    normalized: list[dict[str, str]] = []
    for value in values:
        relative, path = _binding(root, value, "protocol authority")
        normalized.append({"path": relative, "sha256": _file_hash(path)})
    if [item["path"] for item in normalized] != sorted(_REQUIRED_AUTHORITIES):
        raise InputError("manual-pause protocol authority set is incomplete")
    return normalized


def _validate_protocol_review(
    root: Path,
    value: Any,
    authorities: list[dict[str, str]],
) -> dict[str, str]:
    legacy_fields = {"runDirectory", "envelopePath", "envelopeSha256"}
    recovery_fields = legacy_fields | {"hardLimitAuthorityPath", "hardLimitAuthoritySha256"}
    if not isinstance(value, dict) or frozenset(value) not in {
        frozenset(legacy_fields), frozenset(recovery_fields)
    }:
        raise InputError("manual-pause protocol review binding is invalid")
    run_relative = _relative(value.get("runDirectory"), "protocol review run")
    run_dir = _resolve(root, run_relative, "protocol review run")
    envelope_relative = _relative(value.get("envelopePath"), "protocol review envelope")
    is_hard_limit_recovery = set(value) == recovery_fields
    expected_envelope_name = (
        "focused-repair-validation-envelope.json"
        if is_hard_limit_recovery
        else "finalized-run-validation.v3.json"
    )
    if envelope_relative != f"{run_relative}/{expected_envelope_name}":
        raise InputError("manual-pause protocol review envelope path is invalid")
    envelope_path = _resolve(root, envelope_relative, "protocol review envelope")
    if (
        _HASH.fullmatch(str(value.get("envelopeSha256"))) is None
        or not envelope_path.is_file()
        or _file_hash(envelope_path) != value["envelopeSha256"]
    ):
        raise InputError("manual-pause protocol review envelope is stale")
    envelope = _read_json(envelope_path, "protocol review envelope")
    try:
        replayed = replay_finalized_bootstrap_run(root, run_relative)
    except BootstrapBindingError as exc:
        raise InputError("manual-pause protocol review cannot be replayed") from exc
    rotating = {"generatedAt", "validatorHash"}
    if (
        not isinstance(envelope, dict)
        or set(envelope) != set(replayed)
        or {key: item for key, item in envelope.items() if key not in rotating}
        != {key: item for key, item in replayed.items() if key not in rotating}
    ):
        raise InputError("manual-pause protocol review is not an eligible passed review")
    if is_hard_limit_recovery:
        authority_relative = _relative(
            value.get("hardLimitAuthorityPath"), "hard-limit protocol repair authority"
        )
        if authority_relative != f"{run_relative}/hard-limit-protocol-repair-authority.json":
            raise InputError("hard-limit protocol repair authority path is invalid")
        authority_path = _resolve(root, authority_relative, "hard-limit protocol repair authority")
        if (
            _HASH.fullmatch(str(value.get("hardLimitAuthoritySha256"))) is None
            or not authority_path.is_file()
            or _file_hash(authority_path) != value["hardLimitAuthoritySha256"]
        ):
            raise InputError("hard-limit protocol repair authority is stale")
        authority = _read_json(authority_path, "hard-limit protocol repair authority")
        blocked = authority.get("blockedPredecessorEnvelope") if isinstance(authority, dict) else None
        blocked_path = _resolve(
            root,
            _relative(blocked.get("path"), "blocked protocol review envelope")
            if isinstance(blocked, dict)
            else "",
            "blocked protocol review envelope",
        )
        if (
            replayed.get("schemaVersion")
            != "bootstrap-hard-limit-focused-repair-validation-envelope.v1"
            or replayed.get("status") != "passed"
            or replayed.get("nextAction") != "deterministic-closure"
            or replayed.get("authorizes") != []
            or not isinstance(authority, dict)
            or authority.get("schemaVersion")
            != "bootstrap-hard-limit-protocol-repair-authority.v1"
            or authority.get("status") != "passed"
            or authority.get("maintenanceMode") != "ai-native-single-maintainer"
            or authority.get("fullReviewRound") != 3
            or authority.get("focusedRun") != run_relative
            or authority.get("focusedInputHash") != replayed.get("inputHash")
            or authority.get("lineageFamilyId") != replayed.get("lineageFamilyId")
            or authority.get("findingIds") != replayed.get("findingIds")
            or authority.get("hardLimitRecoveryHash") != replayed.get("hardLimitRecoveryHash")
            or authority.get("deterministicRepairClosureHash")
            != replayed.get("deterministicRepairClosureHash")
            or authority.get("verifierOutputHash") != replayed.get("outputHash")
            or authority.get("gateHash") != replayed.get("gateHash")
            or authority.get("focusedValidationEnvelope")
            != {"path": envelope_relative, "sha256": _file_hash(envelope_path)}
            or authority.get("authorizes") != ["manual-pause-protocol-review"]
            or authority.get("doesNotAuthorize")
            != ["acceptance-passed", "round-4", "finding-discovery", "commit", "release"]
            or not isinstance(blocked, dict)
            or set(blocked) != {"path", "sha256", "finalStatus"}
            or blocked.get("finalStatus") != "blocked"
            or not blocked_path.is_file()
            or _file_hash(blocked_path) != blocked.get("sha256")
        ):
            raise InputError("hard-limit protocol repair authority is invalid")
        blocked_envelope = _read_json(blocked_path, "blocked protocol review predecessor")
        if (
            blocked_envelope.get("schemaVersion") != "bootstrap-finalized-run-validation.v3"
            or blocked_envelope.get("validationStatus") != "passed"
            or blocked_envelope.get("profileName") != "bootstrap-skill-route"
            or blocked_envelope.get("fullReviewRound") != 3
            or blocked_envelope.get("finalStatus") != "blocked"
            or blocked_envelope.get("findingClosure", {}).get("unverifiedCount") != 0
        ):
            raise InputError("blocked protocol review predecessor is ineligible")
    elif (
        replayed.get("schemaVersion") != "bootstrap-finalized-run-validation.v3"
        or replayed.get("validationStatus") != "passed"
        or replayed.get("profileName") != "bootstrap-skill-route"
        or replayed.get("finalStatus") not in {"clean", "advisory"}
        or replayed.get("authorizes") != []
    ):
        raise InputError("manual-pause protocol review is not an eligible passed review")
    review_input_path = run_dir / "review-input.json"
    artifact_hashes = replayed.get("artifactHashes")
    if not review_input_path.is_file() or (
        not is_hard_limit_recovery
        and (
            not isinstance(artifact_hashes, dict)
            or artifact_hashes.get("reviewInput") != _file_hash(review_input_path)
        )
    ):
        raise InputError("manual-pause protocol review input binding is stale")
    review_input = _read_json(review_input_path, "protocol review input")
    artifacts = review_input.get("artifacts") if isinstance(review_input, dict) else None
    if not isinstance(artifacts, list):
        raise InputError("manual-pause protocol review artifact coverage is invalid")
    reviewed = {
        item.get("artifact"): item.get("sha256")
        for item in artifacts
        if isinstance(item, dict)
    }
    current = {item["path"]: item["sha256"] for item in authorities}
    for relative in sorted(_PROTOCOL_REVIEW_REQUIRED_PATHS):
        path = _resolve(root, relative, "protocol review required artifact")
        expected = current.get(relative, _file_hash(path) if path.is_file() else None)
        if expected is None or reviewed.get(relative) != expected:
            raise InputError("manual-pause protocol review does not cover current protocol bytes")
    result = {
        "runDirectory": run_relative,
        "envelopePath": envelope_relative,
        "envelopeSha256": _file_hash(envelope_path),
    }
    if is_hard_limit_recovery:
        result.update(
            {
                "hardLimitAuthorityPath": authority_relative,
                "hardLimitAuthoritySha256": _file_hash(authority_path),
            }
        )
    return result


def _validate_finalized_run(
    root: Path,
    value: Any,
    family: str,
    last_run: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    required = {"runDirectory", "envelopePath", "envelopeSha256"}
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("runDirectory") != last_run.get("runDirectory")
        or _HASH.fullmatch(str(value.get("envelopeSha256"))) is None
    ):
        raise InputError("manual-pause finalized run binding is invalid")
    run_relative = _relative(value["runDirectory"], "finalized run")
    run_dir = _resolve(root, run_relative, "finalized run")
    envelope_relative = _relative(value["envelopePath"], "finalized envelope")
    if envelope_relative != f"{run_relative}/finalized-run-validation.v3.json":
        raise InputError("manual-pause finalized envelope path is invalid")
    envelope_path = _resolve(root, envelope_relative, "finalized envelope")
    if not envelope_path.is_file() or _file_hash(envelope_path) != value["envelopeSha256"]:
        raise InputError("manual-pause finalized envelope binding is stale")
    envelope = _read_json(envelope_path, "finalized envelope")
    try:
        replayed_envelope = replay_finalized_bootstrap_run(root, run_relative)
    except BootstrapBindingError as exc:
        raise InputError("manual-pause finalized run cannot be replayed") from exc
    rotating_fields = {"generatedAt", "validatorHash"}
    envelope_stable = {
        key: item for key, item in envelope.items() if key not in rotating_fields
    }
    replayed_stable = {
        key: item for key, item in replayed_envelope.items() if key not in rotating_fields
    }
    if (
        set(envelope) != set(replayed_envelope)
        or _HASH.fullmatch(str(envelope.get("validatorHash"))) is None
        or envelope_stable != replayed_stable
    ):
        raise InputError("manual-pause finalized envelope does not match canonical replay")
    envelope = replayed_envelope
    legacy_family = last_run.get("changeId")
    eligible_envelope_families = {family}
    if isinstance(legacy_family, str) and legacy_family:
        eligible_envelope_families.add(legacy_family)
    if (
        not isinstance(envelope, dict)
        or envelope.get("schemaVersion") != "bootstrap-finalized-run-validation.v3"
        or envelope.get("validationStatus") != "passed"
        or envelope.get("finalStatus") != "blocked"
        or envelope.get("profileName") not in _MANUAL_PAUSE_PROFILES
        or envelope.get("lineageFamilyId") not in eligible_envelope_families
        or envelope.get("changeId") != last_run.get("changeId")
        or envelope.get("fullReviewRound") != 3
        or envelope.get("reviewId") != last_run.get("reviewId")
        or envelope.get("inputHash") != last_run.get("inputHash")
        or envelope.get("authorizes") != []
    ):
        raise InputError("manual-pause finalized envelope is invalid")
    artifact_hashes = envelope.get("artifactHashes")
    if not isinstance(artifact_hashes, dict):
        raise InputError("manual-pause finalized artifact bindings are invalid")
    for key, filename in _RUN_ARTIFACTS.items():
        expected = artifact_hashes.get(key)
        path = run_dir / filename
        if _HASH.fullmatch(str(expected)) is None or not path.is_file() or _file_hash(path) != expected:
            raise InputError("manual-pause finalized artifact bindings are stale")
    if artifact_hashes.get("p2Dispositions") is not None:
        p2_path = run_dir / "p2-dispositions.json"
        if not p2_path.is_file() or _file_hash(p2_path) != artifact_hashes["p2Dispositions"]:
            raise InputError("manual-pause P2 disposition binding is stale")
    candidates = _read_json(run_dir / "review-candidates.json", "review candidates")
    verifier = _read_json(run_dir / "verifier-output.json", "verifier output")
    findings = candidates.get("findings") if isinstance(candidates, dict) else None
    decisions = verifier.get("decisions") if isinstance(verifier, dict) else None
    if not isinstance(findings, list) or not isinstance(decisions, list):
        raise InputError("manual-pause finding evidence is invalid")
    finding_ids = {item.get("findingId") for item in findings if isinstance(item, dict)}
    confirmed = sorted(
        item.get("findingId")
        for item in decisions
        if isinstance(item, dict) and item.get("decision") == "confirmed"
    )
    unverified = sorted(
        item.get("findingId")
        for item in decisions
        if isinstance(item, dict) and item.get("decision") == "unverified"
    )
    if (
        not confirmed
        or len(confirmed) != len(set(confirmed))
        or not set(confirmed).issubset(finding_ids)
        or unverified
        or envelope.get("findingClosure", {}).get("confirmedCount") != len(confirmed)
    ):
        raise InputError("manual-pause confirmed finding set is invalid")
    return envelope, confirmed


def _validate_repairs(
    value: Any,
    confirmed: list[str],
    repair: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise InputError("manual-pause finding repairs are invalid")
    changed = set(repair["changedPaths"])
    tests = {item["path"] for item in repair["targetedTests"]}
    validations = {item["path"] for item in repair["validationRefs"]}
    checks_by_receipt = {
        item["receipt"]["path"]: item
        for item in repair["compositionChecks"]
        if isinstance(item, dict) and isinstance(item.get("receipt"), dict)
    }
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "findingId", "changedPaths", "targetedTests", "validationRefs",
        }:
            raise InputError("manual-pause finding repair fields are invalid")
        lists = {}
        for field in ("changedPaths", "targetedTests", "validationRefs"):
            items = item.get(field)
            if (
                not isinstance(items, list)
                or not items
                or items != sorted(set(items))
                or any(not isinstance(path, str) or not path for path in items)
            ):
                raise InputError("manual-pause finding repair coverage is invalid")
            lists[field] = items
        if not set(lists["changedPaths"]).issubset(changed):
            raise InputError("manual-pause finding repair changed paths are unbound")
        if not set(lists["targetedTests"]).issubset(tests):
            raise InputError("manual-pause finding repair tests are unbound")
        if not set(lists["validationRefs"]).issubset(validations):
            raise InputError("manual-pause finding repair validation is unbound")
        selected_checks = [
            checks_by_receipt[path]
            for path in lists["validationRefs"]
            if path in checks_by_receipt
        ]
        if not selected_checks:
            raise InputError("manual-pause finding repair lacks composition validation")
        covered_paths = {
            binding["path"] for check in selected_checks for binding in check["bindings"]
        }
        covered_tests = {
            path for check in selected_checks for path in check["targetedTests"]
        }
        if not set(lists["changedPaths"]).issubset(covered_paths):
            raise InputError("manual-pause finding repair validation does not cover its changed paths")
        if not set(lists["targetedTests"]).issubset(covered_tests):
            raise InputError("manual-pause finding repair validation does not cover its tests")
        normalized.append({"findingId": item.get("findingId"), **lists})
    normalized.sort(key=lambda item: item["findingId"])
    if [item["findingId"] for item in normalized] != confirmed:
        raise InputError("manual-pause finding repairs do not cover the exact confirmed set")
    return normalized


def prepare_manual_pause_closure(request: Any, source_request_path: str) -> dict[str, Any]:
    required = {
        "schemaVersion", "repositoryRoot", "acceptanceTarget", "lineageFamilyId",
        "manualPauseRoute", "manualPauseRouteRequest", "finalizedRun", "repairCompletenessRequest",
        "repairCompleteness", "findingRepairs", "protocolAuthorities", "protocolReview", "authorizes",
    }
    if (
        not isinstance(request, dict)
        or set(request) != required
        or request.get("schemaVersion") != "acceptance-manual-pause-closure-request.v1"
        or request.get("authorizes") != []
    ):
        raise InputError("manual-pause closure request is invalid")
    root = Path(request["repositoryRoot"]).resolve()
    target = _relative(request["acceptanceTarget"], "acceptance target")
    family = request.get("lineageFamilyId")
    if not isinstance(family, str) or not family:
        raise InputError("manual-pause lineage family is invalid")
    lineage = load_current_lineage_state(root, family)
    if (
        lineage.get("semanticRoundsConsumed") != 3
        or lineage.get("state") != "manual_pause"
        or lineage.get("nextFullReviewRound") is not None
        or len(lineage.get("runs", [])) != 3
    ):
        raise InputError("manual-pause lineage has not reached the hard limit")
    replayed_repair = audit_repair_completeness(request["repairCompletenessRequest"])
    if replayed_repair != request["repairCompleteness"]:
        raise InputError("manual-pause repair completeness is stale or not reproducible")
    if (
        replayed_repair.get("acceptanceTarget") != target
        or replayed_repair.get("lineageFamilyId") != family
        or replayed_repair.get("semanticRoundsConsumed") != 3
        or replayed_repair.get("predecessorRun") != lineage["runs"][-1]["runDirectory"]
    ):
        raise InputError("manual-pause repair completeness lineage is invalid")
    route_request_relative, replayed_route = _replay_manual_pause_route(
        root, request["manualPauseRouteRequest"], target, family, lineage, replayed_repair
    )
    route_relative, route_path = _binding(root, request["manualPauseRoute"], "manual-pause route")
    route = _read_json(route_path, "manual-pause route")
    if route != replayed_route:
        raise InputError("manual-pause route is invalid because it does not match canonical producer replay")
    envelope, confirmed = _validate_finalized_run(root, request["finalizedRun"], family, lineage["runs"][-1])
    repairs = _validate_repairs(request["findingRepairs"], confirmed, replayed_repair)
    authorities = _validate_authorities(root, request["protocolAuthorities"])
    protocol_review = _validate_protocol_review(root, request["protocolReview"], authorities)
    source_relative = _relative(source_request_path, "manual-pause source request")
    source_path = _resolve(root, source_relative, "manual-pause source request")
    if not source_path.is_file() or _read_json(source_path, "manual-pause source request") != request:
        raise InputError("manual-pause source request is stale")
    projection = {
        "schemaVersion": "acceptance-manual-pause-closure-challenge.v1",
        "status": "awaiting-maintainer-ack",
        "acceptanceTarget": target,
        "lineageFamilyId": family,
        "semanticRoundsConsumed": 3,
        "lineageStateHash": lineage["lineageStateHash"],
        "manualPauseRoute": {"path": route_relative, "sha256": _file_hash(route_path)},
        "manualPauseRouteRequest": {
            "path": route_request_relative,
            "sha256": _file_hash(_resolve(root, route_request_relative, "manual-pause route request")),
        },
        "finalizedRun": request["finalizedRun"],
        "finalizedEnvelopeCoreHash": canonical_hash({
            key: value for key, value in envelope.items() if key != "generatedAt"
        }),
        "confirmedFindingIds": confirmed,
        "findingRepairs": repairs,
        "repairCompletenessHash": canonical_hash(replayed_repair),
        "protocolAuthorities": authorities,
        "protocolReview": protocol_review,
        "sourceRequestPath": source_relative,
        "sourceRequestHash": _file_hash(source_path),
        "authorizes": [],
    }
    return {**projection, "closureBindingHash": canonical_hash(projection)}


def finalize_manual_pause_closure(root: Path, challenge_path: str, acknowledgement: Any) -> dict[str, Any]:
    repository_root = root.resolve()
    challenge_relative = _relative(challenge_path, "manual-pause challenge")
    challenge_file = _resolve(repository_root, challenge_relative, "manual-pause challenge")
    try:
        challenge_bytes = challenge_file.read_bytes()
        challenge = json.loads(challenge_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError("manual-pause challenge is unreadable") from exc
    challenge_hash = "sha256:" + hashlib.sha256(challenge_bytes).hexdigest()
    if not isinstance(challenge, dict) or challenge.get("schemaVersion") != "acceptance-manual-pause-closure-challenge.v1":
        raise InputError("manual-pause challenge is invalid")
    source = _resolve(repository_root, challenge.get("sourceRequestPath"), "manual-pause source request")
    if _file_hash(source) != challenge.get("sourceRequestHash"):
        raise InputError("manual-pause source request binding is stale")
    request = _read_json(source, "manual-pause source request")
    recomputed = prepare_manual_pause_closure(request, challenge["sourceRequestPath"])
    if recomputed != challenge:
        raise InputError("manual-pause challenge is stale")
    required_ack = {
        "schemaVersion", "decision", "closureBindingHash", "acknowledgedFindingIds",
        "authorityRole", "rationale", "recordedAt", "authorizes",
    }
    if (
        not isinstance(acknowledgement, dict)
        or set(acknowledgement) != required_ack
        or acknowledgement.get("schemaVersion") != "acceptance-manual-pause-maintainer-ack.v1"
        or acknowledgement.get("decision") != "accept-repaired-target"
        or acknowledgement.get("closureBindingHash") != challenge.get("closureBindingHash")
        or acknowledgement.get("acknowledgedFindingIds") != challenge.get("confirmedFindingIds")
        or acknowledgement.get("authorityRole") != "maintainer"
        or not isinstance(acknowledgement.get("rationale"), str)
        or not acknowledgement["rationale"].strip()
        or not isinstance(acknowledgement.get("recordedAt"), str)
        or not acknowledgement["recordedAt"].endswith("Z")
        or acknowledgement.get("authorizes") != ["manual-pause-closure"]
    ):
        raise InputError("manual-pause maintainer acknowledgement is invalid")
    result = {
        "schemaVersion": "acceptance-manual-pause-closure.v1",
        "status": "passed",
        "acceptanceTarget": challenge["acceptanceTarget"],
        "lineageFamilyId": challenge["lineageFamilyId"],
        "semanticRoundsConsumed": 3,
        "confirmedFindingIds": challenge["confirmedFindingIds"],
        "repairCompletenessHash": challenge["repairCompletenessHash"],
        "challengePath": challenge_relative,
        "challengeHash": challenge_hash,
        "closureBindingHash": challenge["closureBindingHash"],
        "maintainerAcknowledgement": acknowledgement,
        "lifecycleTransition": "acceptance-passed",
        "authorizes": ["acceptance-passed"],
        "doesNotAuthorize": ["commit", "release", "archived"],
    }
    schema_path = _resolve(repository_root, _CLOSURE_SCHEMA_PATH, "manual-pause closure schema")
    required = {
        "schemaVersion", "status", "acceptanceTarget", "lineageFamilyId",
        "semanticRoundsConsumed", "confirmedFindingIds", "repairCompletenessHash",
        "challengePath", "challengeHash", "closureBindingHash",
        "maintainerAcknowledgement", "lifecycleTransition", "authorizes",
        "doesNotAuthorize",
    }
    if (
        not schema_path.is_file()
        or _file_hash(schema_path) != _CLOSURE_SCHEMA_HASH
        or set(result) != required
        or result["schemaVersion"] != "acceptance-manual-pause-closure.v1"
        or result["status"] != "passed"
        or result["semanticRoundsConsumed"] != 3
        or not result["confirmedFindingIds"]
        or result["confirmedFindingIds"] != sorted(set(result["confirmedFindingIds"]))
        or any(
            _HASH.fullmatch(str(result[field])) is None
            for field in ("repairCompletenessHash", "challengeHash", "closureBindingHash")
        )
        or result["lifecycleTransition"] != "acceptance-passed"
        or result["authorizes"] != ["acceptance-passed"]
        or result["doesNotAuthorize"] != ["commit", "release", "archived"]
    ):
        raise InputError("manual-pause closure result violates its reviewed schema")
    return result
