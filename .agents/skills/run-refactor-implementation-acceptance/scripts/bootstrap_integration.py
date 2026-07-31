"""Consumer-side immutable bindings for Bootstrap-owned companion capability."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from acceptance_core import InputError
from repair_completeness import validate_repair_completeness_projection
from review_cycle_policy import (
    DEFAULT_FULL_REVIEW_ROUND_LIMIT,
    HARD_FULL_REVIEW_ROUND_LIMIT,
)


class BootstrapBindingError(ValueError):
    pass


_HASH = re.compile(r"sha256:[a-f0-9]{64}$")
_LINEAGE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{2,63}$")
_EXACT_REUSE_PROFILE = "bootstrap-implementation-conformance"
_EXACT_REUSE_REVIEW_PROFILE = "review-policy://bootstrap-implementation-conformance/v1"
_FINALIZED_EXCLUSIONS = {
    "plan-acceptance", "implementation-acceptance", "protected-handoff",
    "release", "commit", "done",
}
_REVIEW_SCOPE_INPUTS = {
    "implementation_plan": "implementation-plan",
    "changed_production_code": "changed-production-code",
    "affected_consumers": "affected-consumers",
    "tests_and_acceptance": "tests-and-acceptance",
    "runtime_evidence": "runtime-evidence",
    "repository_rules": "repository-rules",
    "referenced_standards": "referenced-standards",
}


def _canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_bootstrap_module(repository_root: Path) -> Any:
    root = repository_root.resolve()
    module_path = root / ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py"
    scripts_path = str(module_path.parent)
    spec = importlib.util.spec_from_file_location("ria_bootstrap_review", module_path)
    if spec is None or spec.loader is None:
        raise BootstrapBindingError("Bootstrap control plane is unavailable")
    module = importlib.util.module_from_spec(spec)
    original_path = list(sys.path)
    displaced = {
        name: sys.modules.pop(name)
        for name in ("_control_plane", "knowledge_context")
        if name in sys.modules
    }
    try:
        sys.path.insert(0, scripts_path)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_path
        for name in ("_control_plane", "knowledge_context"):
            sys.modules.pop(name, None)
        sys.modules.update(displaced)
    return module


def load_current_lineage_state(
    repository_root: Path, lineage_family_id: str
) -> dict[str, Any]:
    module = _load_bootstrap_module(repository_root)
    try:
        return module.build_lineage_state(repository_root.resolve(), lineage_family_id)
    except (OSError, ValueError, module.BootstrapError) as exc:
        raise BootstrapBindingError("Bootstrap lineage state cannot be reconstructed") from exc


def _normalize_review_paths(values: Any, label: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise BootstrapBindingError(f"{label} review scope must be a non-empty list")
    normalized: list[str] = []
    for raw in values:
        if not isinstance(raw, str) or not raw.strip():
            raise BootstrapBindingError(f"{label} review scope contains an invalid path")
        path = raw.strip().replace("\\", "/")
        parts = PurePosixPath(path).parts
        if (
            path.startswith("/")
            or re.match(r"^[A-Za-z]:", path)
            or path.endswith("/")
            or any(part in {"", ".", ".."} for part in parts)
            or any(character in path for character in "*?[]")
        ):
            raise BootstrapBindingError(
                f"{label} review scope must contain explicit repository-relative files"
            )
        normalized.append(PurePosixPath(path).as_posix())
    if len(normalized) != len(set(normalized)):
        raise BootstrapBindingError(f"{label} review scope contains duplicate paths")
    return sorted(normalized)


def build_minimal_review_scope(scope_inputs: Any) -> dict[str, Any]:
    """Build the exact Bootstrap implementation-conformance closure."""
    if not isinstance(scope_inputs, dict) or set(scope_inputs) != set(_REVIEW_SCOPE_INPUTS):
        raise BootstrapBindingError("bootstrap review scope inputs are incomplete")
    context_classes = {
        context_class: _normalize_review_paths(scope_inputs[source], context_class)
        for source, context_class in _REVIEW_SCOPE_INPUTS.items()
    }
    lineage = derive_acceptance_lineage(context_classes["implementation-plan"])
    scope = sorted({path for paths in context_classes.values() for path in paths})
    closure = {
        "schemaVersion": "implementation-acceptance-bootstrap-scope.v1",
        "profile": "bootstrap-implementation-conformance",
        "strategy": "minimal-complete-closure",
        "scope": scope,
        "contextClasses": context_classes,
        "directoryScopeAttestation": None,
        **lineage,
        "authorizes": [],
    }
    closure["scopeHash"] = _canonical_hash(closure)
    return closure


def derive_acceptance_lineage(implementation_plan_paths: Any) -> dict[str, str]:
    """Derive one stable review-budget family from the original plan target."""
    normalized = _normalize_review_paths(implementation_plan_paths, "implementation-plan")
    anchors: set[str] = set()
    for value in normalized:
        parts = PurePosixPath(value).parts
        if len(parts) < 2 or parts[0].casefold() != "execution-plans":
            raise BootstrapBindingError(
                "implementation-plan review scope must be under execution-plans"
            )
        anchor = (
            PurePosixPath(*parts).as_posix()
            if len(parts) == 2
            else PurePosixPath(*parts[:2]).as_posix()
        )
        anchors.add(anchor)
    if len(anchors) != 1:
        raise BootstrapBindingError(
            "implementation-plan review scope must resolve to one acceptance target"
        )
    anchor = next(iter(anchors))
    digest = hashlib.sha256(
        ("refactor-implementation-acceptance:" + anchor.casefold()).encode("utf-8")
    ).hexdigest()[:32]
    return {"lineageAnchor": anchor, "lineageFamilyId": "ria-" + digest}


def _validate_minimal_review_scope(value: Any) -> None:
    required = {
        "schemaVersion", "profile", "strategy", "scope", "contextClasses",
        "directoryScopeAttestation", "lineageAnchor", "lineageFamilyId",
        "authorizes", "scopeHash",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("schemaVersion") != "implementation-acceptance-bootstrap-scope.v1"
        or value.get("profile") != "bootstrap-implementation-conformance"
        or value.get("strategy") != "minimal-complete-closure"
        or value.get("directoryScopeAttestation") is not None
        or value.get("authorizes") != []
        or value.get("scopeHash")
        != _canonical_hash({key: item for key, item in value.items() if key != "scopeHash"})
    ):
        raise BootstrapBindingError("bootstrap review scope is invalid")
    context = value.get("contextClasses")
    if not isinstance(context, dict) or set(context) != set(_REVIEW_SCOPE_INPUTS.values()):
        raise BootstrapBindingError("bootstrap review context classes are invalid")
    normalized_context: dict[str, list[str]] = {}
    for context_class, paths in context.items():
        normalized = _normalize_review_paths(paths, context_class)
        if paths != normalized:
            raise BootstrapBindingError("bootstrap review context paths are not canonical")
        normalized_context[context_class] = normalized
    expected_scope = sorted({path for paths in normalized_context.values() for path in paths})
    if value.get("scope") != expected_scope:
        raise BootstrapBindingError("bootstrap review scope does not match its context classes")
    lineage = derive_acceptance_lineage(normalized_context["implementation-plan"])
    if any(value.get(key) != expected for key, expected in lineage.items()):
        raise BootstrapBindingError("bootstrap review scope lineage is invalid")


def _validate_lineage_state(value: Any, family_id: str) -> int:
    required = {
        "schemaVersion", "lineageFamilyId", "semanticRoundsConsumed",
        "consumedRoundNumbers", "defaultFullReviewRoundLimit",
        "hardFullReviewRoundLimit", "nextFullReviewRound", "state", "runs",
        "authorizes", "lineageStateHash",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("schemaVersion") != "bootstrap-review-lineage-state.v1"
        or value.get("lineageFamilyId") != family_id
        or value.get("defaultFullReviewRoundLimit") != DEFAULT_FULL_REVIEW_ROUND_LIMIT
        or value.get("hardFullReviewRoundLimit") != HARD_FULL_REVIEW_ROUND_LIMIT
        or value.get("authorizes") != []
        or value.get("lineageStateHash")
        != _canonical_hash({key: item for key, item in value.items() if key != "lineageStateHash"})
    ):
        raise BootstrapBindingError("bootstrap lineage state is invalid")
    rounds = value.get("semanticRoundsConsumed")
    consumed = value.get("consumedRoundNumbers")
    runs = value.get("runs")
    if (
        not isinstance(rounds, int)
        or isinstance(rounds, bool)
        or not 0 <= rounds <= HARD_FULL_REVIEW_ROUND_LIMIT
        or consumed != list(range(1, rounds + 1))
        or not isinstance(runs, list)
        or len(runs) != rounds
    ):
        raise BootstrapBindingError("bootstrap lineage round history is invalid")
    seen_runs: set[str] = set()
    seen_reviews: set[str] = set()
    for expected_round, run in enumerate(runs, start=1):
        run_fields = {"runDirectory", "reviewId", "changeId", "fullReviewRound", "inputHash"}
        if (
            not isinstance(run, dict)
            or set(run) != run_fields
            or run.get("fullReviewRound") != expected_round
            or not isinstance(run.get("reviewId"), str)
            or _LINEAGE_ID.fullmatch(run["reviewId"]) is None
            or not isinstance(run.get("changeId"), str)
            or _LINEAGE_ID.fullmatch(run["changeId"]) is None
            or _HASH.fullmatch(str(run.get("inputHash"))) is None
        ):
            raise BootstrapBindingError("bootstrap lineage run history is invalid")
        try:
            run_directory = _normalize_review_paths(
                [run.get("runDirectory")], "bootstrap lineage run"
            )[0]
        except BootstrapBindingError as exc:
            raise BootstrapBindingError("bootstrap lineage run history is invalid") from exc
        if run_directory in seen_runs or run["reviewId"] in seen_reviews:
            raise BootstrapBindingError("bootstrap lineage run history is duplicated")
        seen_runs.add(run_directory)
        seen_reviews.add(run["reviewId"])
    expected_next = None if rounds == HARD_FULL_REVIEW_ROUND_LIMIT else rounds + 1
    expected_state = "manual_pause" if rounds == HARD_FULL_REVIEW_ROUND_LIMIT else "available"
    if value.get("nextFullReviewRound") != expected_next or value.get("state") != expected_state:
        raise BootstrapBindingError("bootstrap lineage next-round projection is invalid")
    return rounds


def _validate_repair_completeness(
    value: Any,
    family_id: str,
    lineage_anchor: str,
    rounds: int,
    review_scope: dict[str, Any],
) -> None:
    try:
        validate_repair_completeness_projection(value)
    except InputError as exc:
        raise BootstrapBindingError("repair completeness projection is invalid") from exc
    if (
        value.get("lineageFamilyId") != family_id
        or value.get("acceptanceTarget") != lineage_anchor
        or value.get("semanticRoundsConsumed") != rounds
    ):
        raise BootstrapBindingError("repair completeness projection is invalid")
    closure = set(review_scope["scope"])
    context = review_scope["contextClasses"]
    changed = set(value["changedPaths"])
    consumers = {item["path"] for item in value["directConsumers"]}
    tests = {item["path"] for item in value["targetedTests"]}
    validation = {item["path"] for item in value["validationRefs"]}
    inventory_paths = {
        item["path"]
        for inventory in value["rootCauseInventories"]
        for item in inventory["matches"]
    }
    composition_paths = {
        binding["path"]
        for check in value["compositionChecks"]
        for binding in check["bindings"]
    } | {
        check[field]["path"]
        for check in value["compositionChecks"]
        for field in ("commandRegistry", "receipt")
    }
    if not (
        changed
        | consumers
        | tests
        | validation
        | inventory_paths
        | composition_paths
    ).issubset(closure):
        raise BootstrapBindingError(
            "repair completeness artifacts are outside the bootstrap review scope"
        )
    if not consumers.issubset(set(context["affected-consumers"])):
        raise BootstrapBindingError(
            "repair completeness consumers are outside the affected-consumer scope"
        )
    if not tests.issubset(set(context["tests-and-acceptance"])):
        raise BootstrapBindingError(
            "repair completeness tests are outside the tests-and-acceptance scope"
        )
    evidence_scope = set(context["tests-and-acceptance"]) | set(context["runtime-evidence"])
    if not validation.issubset(evidence_scope):
        raise BootstrapBindingError(
            "repair completeness validation references are outside the evidence scope"
        )


def project_bounded_review_route(
    decision: Any,
    scope: dict[str, Any] | None,
    lineage_state: Any,
    repair_completeness: Any,
) -> dict[str, Any]:
    """Choose the bounded semantic-review lane without authorizing a launch."""
    if not isinstance(decision, dict) or decision.get("requirement") not in {
        "required", "not_required",
    }:
        raise BootstrapBindingError("bootstrap requirement decision is invalid")
    if decision["requirement"] == "not_required":
        if lineage_state is not None or repair_completeness is not None:
            raise BootstrapBindingError(
                "deterministic-only acceptance cannot attach review lineage evidence"
            )
        return {
            "routeKind": "deterministic_only",
            "lineageAnchor": None,
            "lineageFamilyId": None,
            "semanticRoundsConsumed": 0,
            "nextFullReviewRound": None,
            "roundEntryReason": None,
            "lineageStateHash": None,
            "repairCompletenessHash": None,
        }
    if not isinstance(scope, dict):
        raise BootstrapBindingError("required Bootstrap route needs a review scope")
    _validate_minimal_review_scope(scope)
    family_id = scope.get("lineageFamilyId")
    anchor = scope.get("lineageAnchor")
    if not isinstance(family_id, str) or _LINEAGE_ID.fullmatch(family_id) is None:
        raise BootstrapBindingError("review scope lineage family is invalid")
    if not isinstance(anchor, str) or not anchor:
        raise BootstrapBindingError("review scope lineage anchor is invalid")
    if lineage_state is None:
        raise BootstrapBindingError(
            "required Bootstrap route needs a current inspect-lineage projection"
        )
    rounds = _validate_lineage_state(lineage_state, family_id)
    if rounds == 0:
        if repair_completeness is not None:
            raise BootstrapBindingError("initial review cannot attach repair completeness")
        route_kind = "full_implementation_conformance"
        entry_reason = None
        repair_hash = None
    elif rounds == HARD_FULL_REVIEW_ROUND_LIMIT:
        if repair_completeness is not None:
            _validate_repair_completeness(
                repair_completeness, family_id, anchor, rounds, scope
            )
        route_kind = "manual_pause"
        entry_reason = None
        repair_hash = (
            _canonical_hash(repair_completeness)
            if repair_completeness is not None
            else None
        )
    else:
        _validate_repair_completeness(
            repair_completeness, family_id, anchor, rounds, scope
        )
        repair_hash = _canonical_hash(repair_completeness)
        novel = repair_completeness["novelP0P1FindingIds"]
        authority_changed = repair_completeness["authorityGraphChanged"]
        boundary_changed = repair_completeness["highRiskBoundaryChanged"]
        if rounds == 1:
            route_kind = "focused_repair_review"
            entry_reason = None
        elif novel:
            route_kind = "full_implementation_conformance"
            entry_reason = "novel_p0_p1"
        elif authority_changed:
            route_kind = "full_implementation_conformance"
            entry_reason = "authority_context_graph_changed"
        elif boundary_changed:
            route_kind = "full_implementation_conformance"
            entry_reason = "high_risk_boundary_changed"
        else:
            route_kind = "deterministic_only"
            entry_reason = None
    return {
        "routeKind": route_kind,
        "lineageAnchor": anchor,
        "lineageFamilyId": family_id,
        "semanticRoundsConsumed": rounds,
        "nextFullReviewRound": (
            rounds + 1
            if route_kind in {"focused_repair_review", "full_implementation_conformance"}
            else None
        ),
        "roundEntryReason": entry_reason,
        "lineageStateHash": lineage_state.get("lineageStateHash"),
        "repairCompletenessHash": repair_hash,
    }


def _required_capability(binding: Any) -> dict[str, Any]:
    if not isinstance(binding, dict) or binding.get("schemaVersion") != "bootstrap-capability-binding.v1" or binding.get("status") != "bound" or binding.get("authorizes") != []:
        raise BootstrapBindingError("bootstrap capability binding is invalid")
    capabilities = binding.get("requiredCompanionCapabilities")
    if not isinstance(capabilities, list) or len(capabilities) != 1 or not isinstance(capabilities[0], dict):
        raise BootstrapBindingError("bootstrap companion capability is invalid")
    capability = capabilities[0]
    expected = {
        "capabilityId": "acceptance-inventory-attestation",
        "capabilityVersion": "1.0",
        "producerRole": "acceptance_auditor",
    }
    if any(capability.get(key) != value for key, value in expected.items()) or not isinstance(capability.get("schemaPath"), str) or not _HASH.fullmatch(str(capability.get("schemaHash"))):
        raise BootstrapBindingError("bootstrap companion capability is invalid")
    return capability


def bind_capabilities(decision: Any, profile: Any) -> dict[str, Any]:
    if not isinstance(decision, dict) or not isinstance(profile, dict):
        raise BootstrapBindingError("decision or profile is invalid")
    requirement = decision.get("requirement")
    expected = decision.get("requiredCompanionCapabilityExpectations")
    if requirement not in {"required", "not_required"} or not isinstance(expected, list):
        raise BootstrapBindingError("bootstrap requirement decision is invalid")
    if requirement == "not_required":
        if expected:
            raise BootstrapBindingError("not-required decision cannot name a companion")
        return {"schemaVersion": "bootstrap-capability-binding.v1", "status": "not_applicable", "requiredCompanionCapabilities": [], "authorizes": []}
    if len(expected) != 1 or not isinstance(profile.get("companionCapabilities"), list):
        raise BootstrapBindingError("required companion capability is missing")
    wanted = expected[0]
    matches = [item for item in profile["companionCapabilities"] if isinstance(item, dict) and all(item.get(key) == wanted.get(key) for key in ("capabilityId", "capabilityVersion", "producerRole"))]
    if len(matches) != 1:
        raise BootstrapBindingError("profile companion capability does not match immutable decision")
    capability = matches[0]
    if not isinstance(capability.get("schemaPath"), str) or not isinstance(capability.get("schemaHash"), str):
        raise BootstrapBindingError("companion schema binding is invalid")
    required_profile = ("controlPlaneRevision", "routeVersion", "reviewProfile", "policyRevision")
    if any(not isinstance(profile.get(key), str) or not profile[key] for key in required_profile):
        raise BootstrapBindingError("profile identity is incomplete")
    return {"schemaVersion": "bootstrap-capability-binding.v1", "status": "bound", **{key: profile[key] for key in required_profile}, "requiredCompanionCapabilities": [{**wanted, "schemaPath": capability["schemaPath"], "schemaHash": capability["schemaHash"]}], "authorizes": []}


def build_attestation_scope(
    decision: Any,
    binding: Any,
    source_inventory: Any,
    source_clauses: Any,
    base_matrix: Any,
    artifact_view_manifest_hash: Any,
) -> dict[str, Any]:
    """Freeze consumer-owned inputs that the Bootstrap companion must attest."""
    if not isinstance(decision, dict) or decision.get("requirement") != "required":
        raise BootstrapBindingError("attestation scope requires a required bootstrap decision")
    _required_capability(binding)
    if not _HASH.fullmatch(str(artifact_view_manifest_hash)):
        raise BootstrapBindingError("Artifact View manifest hash is invalid")
    for value, label in ((source_inventory, "source inventory"), (source_clauses, "source clauses"), (base_matrix, "base matrix")):
        if not isinstance(value, dict):
            raise BootstrapBindingError(label + " is invalid")
    consumer_scope = {
        "schemaVersion": "bootstrap-inventory-attestation-scope.v1",
        "decisionHash": _canonical_hash(decision),
        "bindingHash": _canonical_hash(binding),
        "sourceInventoryHash": _canonical_hash(source_inventory),
        "sourceClausesHash": _canonical_hash(source_clauses),
        "baseMatrixHash": _canonical_hash(base_matrix),
        "authorizes": [],
    }
    return {
        **consumer_scope,
        "consumerScopeHash": _canonical_hash(consumer_scope),
        # Bootstrap Review binds the companion attestation to its immutable Artifact View.
        "scopeHash": artifact_view_manifest_hash,
    }


def validate_inventory_attestation(attestation: Any, binding: Any, scope: Any) -> None:
    """Validate a Bootstrap-produced attestation without treating it as local output."""
    capability = _required_capability(binding)
    scope_fields = {
        "schemaVersion", "decisionHash", "bindingHash", "sourceInventoryHash",
        "sourceClausesHash", "baseMatrixHash", "consumerScopeHash", "scopeHash",
        "authorizes",
    }
    if (
        not isinstance(scope, dict)
        or set(scope) != scope_fields
        or scope.get("schemaVersion") != "bootstrap-inventory-attestation-scope.v1"
        or scope.get("authorizes") != []
        or any(not _HASH.fullmatch(str(scope.get(key))) for key in scope_fields - {"schemaVersion", "authorizes", "consumerScopeHash", "scopeHash"})
        or not _HASH.fullmatch(str(scope.get("consumerScopeHash")))
        or not _HASH.fullmatch(str(scope.get("scopeHash")))
    ):
        raise BootstrapBindingError("attestation scope is invalid")
    consumer_scope = {
        key: scope[key]
        for key in ("schemaVersion", "decisionHash", "bindingHash", "sourceInventoryHash", "sourceClausesHash", "baseMatrixHash", "authorizes")
    }
    if scope["consumerScopeHash"] != _canonical_hash(consumer_scope):
        raise BootstrapBindingError("attestation consumer scope hash is stale")
    if scope["bindingHash"] != _canonical_hash(binding):
        raise BootstrapBindingError("attestation binding is stale")
    required = {
        "schemaVersion", "reviewId", "attemptId", "inputHash", "capabilityId", "capabilityVersion",
        "producerRole", "status", "scopeHash", "coverage",
    }
    if not isinstance(attestation, dict) or set(attestation) != required:
        raise BootstrapBindingError("inventory attestation fields are invalid")
    if attestation.get("schemaVersion") != "bootstrap-acceptance-inventory-attestation.v1" or attestation.get("status") != "complete":
        raise BootstrapBindingError("inventory attestation is incomplete")
    for key in ("reviewId", "attemptId"):
        if not isinstance(attestation.get(key), str) or not attestation[key]:
            raise BootstrapBindingError("inventory attestation identity is invalid")
    if not _HASH.fullmatch(str(attestation.get("inputHash"))) or attestation.get("scopeHash") != scope["scopeHash"]:
        raise BootstrapBindingError("inventory attestation scope is stale")
    if not isinstance(attestation.get("coverage"), list):
        raise BootstrapBindingError("inventory attestation coverage is invalid")
    for key in ("capabilityId", "capabilityVersion", "producerRole"):
        if attestation.get(key) != capability[key]:
            raise BootstrapBindingError("inventory attestation capability is invalid")


def _validate_finalized_reuse_envelope(value: Any) -> None:
    fields = {
        "schemaVersion", "validationStatus", "reviewId", "changeId", "lineageFamilyId",
        "fullReviewRound", "profileName", "reviewProfile", "routeVersion",
        "controlPlaneRevision", "policyRevision", "profileHash", "authorityRevision",
        "inputHash", "authorityContextHash", "candidateBindingHash",
        "reviewEntryDecisionHash", "repairReviewDeltaHash", "artifactHashes",
        "finalStatus", "findingClosure", "validatorRevision", "validatorHash",
        "authorizes", "doesNotAuthorize", "generatedAt",
    }
    hash_fields = {
        "policyRevision", "profileHash", "inputHash", "authorityContextHash",
        "candidateBindingHash", "validatorHash",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schemaVersion") != "bootstrap-finalized-run-validation.v3"
        or value.get("validationStatus") != "passed"
        or value.get("finalStatus") != "clean"
        or value.get("profileName") != _EXACT_REUSE_PROFILE
        or value.get("reviewProfile") != _EXACT_REUSE_REVIEW_PROFILE
        or value.get("controlPlaneRevision") != "bootstrap-control-plane.v2"
        or value.get("validatorRevision") != "bootstrap-finalized-run-validator.v4"
        or value.get("authorizes") != []
        or not isinstance(value.get("doesNotAuthorize"), list)
        or len(value["doesNotAuthorize"]) != len(_FINALIZED_EXCLUSIONS)
        or any(not isinstance(item, str) for item in value["doesNotAuthorize"])
        or set(value["doesNotAuthorize"]) != _FINALIZED_EXCLUSIONS
        or any(not _HASH.fullmatch(str(value.get(field))) for field in hash_fields)
        or not isinstance(value.get("reviewId"), str)
        or not value["reviewId"]
        or not isinstance(value.get("changeId"), str)
        or not value["changeId"]
        or _LINEAGE_ID.fullmatch(str(value.get("lineageFamilyId"))) is None
        or not isinstance(value.get("fullReviewRound"), int)
        or isinstance(value.get("fullReviewRound"), bool)
        or not 1 <= value["fullReviewRound"] <= HARD_FULL_REVIEW_ROUND_LIMIT
        or not isinstance(value.get("routeVersion"), str)
        or not value["routeVersion"]
        or not isinstance(value.get("authorityRevision"), str)
        or not value["authorityRevision"]
    ):
        raise BootstrapBindingError("Bootstrap finalized reuse envelope is invalid")
    for field in ("reviewEntryDecisionHash", "repairReviewDeltaHash"):
        if value.get(field) is not None and not _HASH.fullmatch(str(value[field])):
            raise BootstrapBindingError("Bootstrap finalized reuse envelope hash is invalid")

    artifact_fields = {
        "reviewInput", "preflightResult", "gateState", "candidates", "rejections",
        "finalResult", "dispositions", "metrics", "verifierOutput", "p2Dispositions",
    }
    artifact_hashes = value.get("artifactHashes")
    if (
        not isinstance(artifact_hashes, dict)
        or set(artifact_hashes) != artifact_fields
        or any(
            not _HASH.fullmatch(str(artifact_hashes.get(field)))
            for field in artifact_fields - {"p2Dispositions"}
        )
        or (
            artifact_hashes.get("p2Dispositions") is not None
            and not _HASH.fullmatch(str(artifact_hashes["p2Dispositions"]))
        )
    ):
        raise BootstrapBindingError("Bootstrap finalized artifact bindings are invalid")

    closure_fields = {
        "candidateCount", "visibleFindingCount", "confirmedCount", "advisoryCount",
        "unverifiedCount", "refutedCount", "p2FixedCount", "p2DeferredCount",
        "p2RefutedCount",
    }
    closure = value.get("findingClosure")
    if (
        not isinstance(closure, dict)
        or set(closure) != closure_fields
        or any(
            not isinstance(closure.get(field), int)
            or isinstance(closure.get(field), bool)
            or closure[field] < 0
            for field in closure_fields
        )
    ):
        raise BootstrapBindingError("Bootstrap finalized finding closure is invalid")
    try:
        generated_at = datetime.fromisoformat(str(value.get("generatedAt")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise BootstrapBindingError("Bootstrap finalized timestamp is invalid") from exc
    if generated_at.tzinfo is None:
        raise BootstrapBindingError("Bootstrap finalized timestamp must be timezone-aware")


def validate_import_envelope(envelope: Any, expected_hashes: Any) -> None:
    """Reject partial or drifted Bootstrap imports before they reach acceptance calculation."""
    if isinstance(envelope, dict) and envelope.get("schemaVersion") == "bootstrap-import-envelope.v2":
        required = {
            "schemaVersion", "controlPlaneRevision", "bootstrapRunDir", "finalizedRun",
            "finalizedRunCoreHash", "inventoryAttestation", "inventoryAttestationHash",
            "bindingHash", "scopeHash", "authorizes",
        }
        if not isinstance(expected_hashes, dict) or set(expected_hashes) != {"binding", "scope"}:
            raise BootstrapBindingError("v2 import envelope expectations are invalid")
        binding, scope = expected_hashes["binding"], expected_hashes["scope"]
        finalized = envelope.get("finalizedRun")
        attestation = envelope.get("inventoryAttestation")
        if (
            set(envelope) != required
            or envelope.get("controlPlaneRevision") != "bootstrap-control-plane.v2"
            or envelope.get("authorizes") != []
            or not isinstance(envelope.get("bootstrapRunDir"), str)
            or not envelope["bootstrapRunDir"]
            or not isinstance(finalized, dict)
            or finalized.get("schemaVersion") not in {
                "bootstrap-finalized-run-validation.v1",
                "bootstrap-finalized-run-validation.v2",
            }
            or finalized.get("validationStatus") != "passed"
            or finalized.get("finalStatus") != "clean"
            or finalized.get("controlPlaneRevision") != envelope.get("controlPlaneRevision")
            or not isinstance(attestation, dict)
        ):
            raise BootstrapBindingError("bootstrap import envelope v2 is invalid")
        finalized_core = {key: value for key, value in finalized.items() if key != "generatedAt"}
        if (
            envelope.get("finalizedRunCoreHash") != _canonical_hash(finalized_core)
            or envelope.get("inventoryAttestationHash") != _canonical_hash(attestation)
            or envelope.get("bindingHash") != _canonical_hash(binding)
            or envelope.get("scopeHash") != _canonical_hash(scope)
        ):
            raise BootstrapBindingError("bootstrap import envelope v2 hash is stale")
        validate_inventory_attestation(attestation, binding, scope)
        return
    if isinstance(envelope, dict) and envelope.get("schemaVersion") == "bootstrap-import-envelope.v3":
        required = {
            "schemaVersion", "controlPlaneRevision", "bootstrapRunDir", "finalizedRun",
            "finalizedRunCoreHash", "inventoryAttestation", "inventoryAttestationHash",
            "bindingHash", "scopeHash", "candidateIdentity", "candidateIdentityHash",
            "bootstrapRoutePath", "bootstrapRouteFileHash", "bootstrapRouteHash",
            "authorizes",
        }
        if not isinstance(expected_hashes, dict) or set(expected_hashes) != {
            "bootstrapRunDir", "binding", "scope", "candidateIdentity", "bootstrapRoute"
        }:
            raise BootstrapBindingError("v3 import envelope expectations are invalid")
        binding, scope = expected_hashes["binding"], expected_hashes["scope"]
        candidate_identity = expected_hashes["candidateIdentity"]
        _validate_candidate_identity(candidate_identity)
        bootstrap_route = expected_hashes["bootstrapRoute"]
        _validate_bootstrap_route_binding(bootstrap_route)
        expected_run_dir = _normalize_review_paths(
            [expected_hashes["bootstrapRunDir"]], "Bootstrap run directory"
        )[0]
        finalized = envelope.get("finalizedRun")
        attestation = envelope.get("inventoryAttestation")
        if (
            set(envelope) != required
            or envelope.get("controlPlaneRevision") != "bootstrap-control-plane.v2"
            or envelope.get("authorizes") != []
            or envelope.get("bootstrapRunDir") != expected_run_dir
            or not isinstance(finalized, dict)
            or finalized.get("controlPlaneRevision") != envelope.get("controlPlaneRevision")
            or not isinstance(attestation, dict)
        ):
            raise BootstrapBindingError("bootstrap import envelope v3 is invalid")
        _validate_finalized_reuse_envelope(finalized)
        finalized_core = {key: value for key, value in finalized.items() if key != "generatedAt"}
        if (
            envelope.get("finalizedRunCoreHash") != _canonical_hash(finalized_core)
            or envelope.get("inventoryAttestationHash") != _canonical_hash(attestation)
            or envelope.get("bindingHash") != _canonical_hash(binding)
            or envelope.get("scopeHash") != _canonical_hash(scope)
            or envelope.get("candidateIdentity") != candidate_identity
            or envelope.get("candidateIdentityHash") != _canonical_hash(candidate_identity)
            or envelope.get("bootstrapRoutePath") != bootstrap_route["path"]
            or envelope.get("bootstrapRouteFileHash") != bootstrap_route["fileHash"]
            or envelope.get("bootstrapRouteHash") != bootstrap_route["routeHash"]
        ):
            raise BootstrapBindingError("bootstrap import envelope v3 hash is stale")
        validate_inventory_attestation(attestation, binding, scope)
        if (
            attestation.get("reviewId") != finalized.get("reviewId")
            or attestation.get("inputHash") != finalized.get("inputHash")
        ):
            raise BootstrapBindingError(
                "bootstrap inventory attestation does not bind the finalized run"
            )
        return
    required_hashes = {
        "decisionHash", "bindingHash", "launchAuthorizationHash", "localReceiptHash", "reviewInputHash",
        "artifactViewHash", "roleBundleHash", "attestationHash", "candidateHash", "baseMatrixHash", "findingPolicyHash",
        "profileHash", "policyHash", "routeHash", "companionSchemaHash", "finalResultHash", "verifierHash",
        "p2DispositionsHash",
    }
    if not isinstance(expected_hashes, dict) or set(expected_hashes) != required_hashes or any(not _HASH.fullmatch(str(value)) for value in expected_hashes.values()):
        raise BootstrapBindingError("import envelope expectations are invalid")
    required = {"schemaVersion", "controlPlaneRevision", "authorizes", *required_hashes}
    if not isinstance(envelope, dict) or set(envelope) != required:
        raise BootstrapBindingError("bootstrap import envelope fields are invalid")
    if envelope.get("schemaVersion") != "bootstrap-import-envelope.v1" or envelope.get("controlPlaneRevision") != "bootstrap-control-plane.v2" or envelope.get("authorizes") != []:
        raise BootstrapBindingError("bootstrap import envelope is invalid")
    if any(envelope[key] != expected_hashes[key] for key in required_hashes):
        raise BootstrapBindingError("bootstrap import envelope hash is stale")


def _validate_candidate_identity(value: Any) -> None:
    fields = {
        "schemaVersion", "acceptanceRunInputPath", "acceptanceRunInputFileHash",
        "candidateContentManifestPath", "candidateContentManifestFileHash",
        "candidateContentManifestHash", "candidateCustodyHash", "changedPaths",
        "changedPathBindings", "knowledgeArtifacts", "authorizes", "identityHash",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schemaVersion") != "acceptance-bootstrap-reuse-candidate.v2"
        or value.get("authorizes") != []
        or any(
            not _HASH.fullmatch(str(value.get(field)))
            for field in (
                "acceptanceRunInputFileHash", "candidateContentManifestFileHash",
                "candidateContentManifestHash", "candidateCustodyHash", "identityHash",
            )
        )
    ):
        raise BootstrapBindingError("Acceptance candidate identity is invalid")
    stable = {key: item for key, item in value.items() if key != "identityHash"}
    if value["identityHash"] != _canonical_hash(stable):
        raise BootstrapBindingError("Acceptance candidate identity hash is stale")
    _normalize_review_paths(
        [value["acceptanceRunInputPath"], value["candidateContentManifestPath"]],
        "Acceptance candidate identity path",
    )
    changed = _normalize_review_paths(value.get("changedPaths"), "Acceptance changed path")
    if value["changedPaths"] != changed:
        raise BootstrapBindingError("Acceptance changed paths are not canonical")
    changed_bindings = value.get("changedPathBindings")
    if not isinstance(changed_bindings, list) or not changed_bindings:
        raise BootstrapBindingError("Acceptance changed path bindings are invalid")
    binding_paths: list[str] = []
    for binding in changed_bindings:
        if (
            not isinstance(binding, dict)
            or set(binding) != {"path", "state", "sha256"}
            or binding.get("state") not in {"present", "deleted"}
            or not _HASH.fullmatch(str(binding.get("sha256")))
        ):
            raise BootstrapBindingError("Acceptance changed path bindings are invalid")
        binding_paths.append(binding.get("path"))
    normalized_bindings = _normalize_review_paths(
        binding_paths, "Acceptance changed path binding"
    )
    if binding_paths != normalized_bindings or binding_paths != changed:
        raise BootstrapBindingError("Acceptance changed path bindings are not canonical")
    knowledge = value.get("knowledgeArtifacts")
    if not isinstance(knowledge, list) or not knowledge:
        raise BootstrapBindingError("Acceptance knowledge artifact binding is invalid")
    knowledge_paths: list[str] = []
    for artifact in knowledge:
        if (
            not isinstance(artifact, dict)
            or set(artifact) != {"path", "sha256"}
            or not _HASH.fullmatch(str(artifact.get("sha256")))
        ):
            raise BootstrapBindingError("Acceptance knowledge artifact binding is invalid")
        knowledge_paths.append(artifact.get("path"))
    normalized_knowledge = _normalize_review_paths(
        knowledge_paths, "Acceptance knowledge artifact"
    )
    if knowledge_paths != normalized_knowledge:
        raise BootstrapBindingError("Acceptance knowledge artifact paths are not canonical")


def _validate_bootstrap_route_binding(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"path", "fileHash", "route", "routeHash"}
        or not _HASH.fullmatch(str(value.get("fileHash")))
        or not _HASH.fullmatch(str(value.get("routeHash")))
        or value.get("routeHash") != _canonical_hash(value.get("route"))
    ):
        raise BootstrapBindingError("Bootstrap route binding is invalid")
    if _normalize_review_paths([value.get("path")], "Bootstrap route")[0] != value["path"]:
        raise BootstrapBindingError("Bootstrap route path is not canonical")
    route = value["route"]
    required = {
        "schemaVersion", "bootstrapExecutionState", "reviewScope", "routeKind",
        "lineageAnchor", "lineageFamilyId", "semanticRoundsConsumed",
        "nextFullReviewRound", "roundEntryReason", "lineageStateHash",
        "repairCompletenessHash", "nextAction", "authorizes",
    }
    if (
        not isinstance(route, dict)
        or set(route) != required
        or route.get("schemaVersion") != "implementation-acceptance-bootstrap-route.v1"
        or route.get("routeKind") not in {
            "full_implementation_conformance", "focused_repair_review"
        }
        or route.get("nextAction") != "run-phase-bootstrap-review"
        or route.get("authorizes") != []
    ):
        raise BootstrapBindingError("Bootstrap route is not eligible for exact reuse")
    _validate_minimal_review_scope(route.get("reviewScope"))


def _validate_exact_reuse_lineage(
    repository_root: Path,
    bootstrap_route: dict[str, Any],
    finalized: dict[str, Any],
) -> None:
    route = bootstrap_route["route"]
    family_id = route["lineageFamilyId"]
    if (
        family_id != route["reviewScope"]["lineageFamilyId"]
        or route["lineageAnchor"] != route["reviewScope"]["lineageAnchor"]
        or finalized.get("lineageFamilyId") != family_id
    ):
        raise BootstrapBindingError("Bootstrap exact-reuse lineage family is invalid")
    current = load_current_lineage_state(repository_root, family_id)
    rounds = _validate_lineage_state(current, family_id)
    finalized_round = finalized.get("fullReviewRound")
    prior_rounds = route.get("semanticRoundsConsumed")
    if (
        rounds != finalized_round
        or prior_rounds != finalized_round - 1
        or route.get("nextFullReviewRound") != finalized_round
        or not current["runs"]
    ):
        raise BootstrapBindingError(
            "Bootstrap route does not describe the current lineage transition"
        )
    current_run = current["runs"][-1]
    for run_field, finalized_field in (
        ("reviewId", "reviewId"), ("changeId", "changeId"),
        ("fullReviewRound", "fullReviewRound"), ("inputHash", "inputHash"),
    ):
        if current_run[run_field] != finalized.get(finalized_field):
            raise BootstrapBindingError("Bootstrap finalized run is not the current lineage head")
    predecessor = {
        "schemaVersion": "bootstrap-review-lineage-state.v1",
        "lineageFamilyId": family_id,
        "semanticRoundsConsumed": prior_rounds,
        "consumedRoundNumbers": list(range(1, prior_rounds + 1)),
        "defaultFullReviewRoundLimit": DEFAULT_FULL_REVIEW_ROUND_LIMIT,
        "hardFullReviewRoundLimit": HARD_FULL_REVIEW_ROUND_LIMIT,
        "nextFullReviewRound": finalized_round,
        "state": "available",
        "runs": current["runs"][:-1],
        "authorizes": [],
    }
    predecessor["lineageStateHash"] = _canonical_hash(predecessor)
    if route.get("lineageStateHash") != predecessor["lineageStateHash"]:
        raise BootstrapBindingError("Bootstrap route lineage state is stale")


def load_verified_bootstrap_import(
    repository_root: Path, bootstrap_run_dir: str, binding: Any, scope: Any,
    candidate_identity: Any, bootstrap_route: Any,
) -> dict[str, Any]:
    """Load and revalidate Bootstrap-owned evidence before consumer import."""
    root = repository_root.resolve()
    normalized_run_dir = _normalize_review_paths(
        [bootstrap_run_dir], "Bootstrap run directory"
    )[0]
    run_dir = (root / normalized_run_dir).resolve()
    try:
        run_dir.relative_to(root)
    except ValueError as exc:
        raise BootstrapBindingError("bootstrap run directory escapes repository root") from exc
    if run_dir.relative_to(root).as_posix() != normalized_run_dir:
        raise BootstrapBindingError("bootstrap run directory is not canonical")
    _validate_candidate_identity(candidate_identity)
    _validate_bootstrap_route_binding(bootstrap_route)
    module = _load_bootstrap_module(root)
    try:
        loaded_dir, manifest, loaded_root = module.load_run(str(run_dir))
        envelope = module.validate_finalized_run_evidence(run_dir, manifest, root)
        bundle = module.read_json(
            run_dir / "reviewer-outputs" / "acceptance_auditor.role-bundle.json"
        )
    except Exception as exc:
        raise BootstrapBindingError("Bootstrap finalized evidence is missing or invalid") from exc
    if loaded_dir.resolve() != run_dir or loaded_root.resolve() != root:
        raise BootstrapBindingError("Bootstrap run resolved to another repository identity")
    if (
        manifest.get("profileName") != _EXACT_REUSE_PROFILE
        or manifest.get("reviewProfile") != _EXACT_REUSE_REVIEW_PROFILE
    ):
        raise BootstrapBindingError(
            "Bootstrap exact reuse requires the implementation-conformance profile"
        )
    _validate_finalized_reuse_envelope(envelope)
    seal_path = run_dir / "run-seal.json"
    if seal_path.is_file():
        raise BootstrapBindingError("Bootstrap exact reuse requires an active finalized run")
    _validate_exact_reuse_lineage(root, bootstrap_route, envelope)
    if envelope.get("finalStatus") != "clean":
        raise BootstrapBindingError("Bootstrap run is not clean")
    candidate_binding_hash = envelope.get("candidateBindingHash")
    if (
        not _HASH.fullmatch(str(candidate_binding_hash))
        or manifest.get("candidateBindingHash") != candidate_binding_hash
    ):
        raise BootstrapBindingError("Bootstrap run is not eligible for exact candidate reuse")
    artifact_hashes: dict[str, str] = {}
    for artifact in manifest.get("artifacts", []):
        if (
            not isinstance(artifact, dict)
            or not isinstance(artifact.get("artifact"), str)
            or artifact["artifact"] in artifact_hashes
            or not _HASH.fullmatch(str(artifact.get("sha256")))
        ):
            raise BootstrapBindingError("Bootstrap candidate artifact binding is invalid")
        artifact_hashes[artifact["artifact"]] = artifact["sha256"]
    review_scope = bootstrap_route["route"]["reviewScope"]
    if manifest.get("contextClassArtifacts") != review_scope["contextClasses"]:
        raise BootstrapBindingError(
            "Bootstrap run context classes do not match the Acceptance route"
        )
    finalized_round = envelope["fullReviewRound"]
    repair_route_binding = manifest.get("acceptanceRepairRoute")
    if finalized_round > 1:
        if repair_route_binding != {
            "path": bootstrap_route["path"],
            "sha256": bootstrap_route["fileHash"],
        }:
            raise BootstrapBindingError(
                "Bootstrap run was launched by another Acceptance repair route"
            )
    elif repair_route_binding is not None:
        raise BootstrapBindingError("Bootstrap Round 1 has an unexpected repair route binding")
    changed_scope = set(review_scope["contextClasses"]["changed-production-code"])
    if not set(candidate_identity["changedPaths"]).issubset(changed_scope):
        raise BootstrapBindingError(
            "Acceptance changed paths are outside the Bootstrap changed-production scope"
        )
    required_candidate_artifacts = {
        candidate_identity["acceptanceRunInputPath"]: candidate_identity["acceptanceRunInputFileHash"],
        candidate_identity["candidateContentManifestPath"]: candidate_identity["candidateContentManifestFileHash"],
        **{
            item["path"]: item["sha256"]
            for item in candidate_identity["knowledgeArtifacts"]
        },
    }
    if any(artifact_hashes.get(path) != digest for path, digest in required_candidate_artifacts.items()):
        raise BootstrapBindingError("Bootstrap run does not bind the current Acceptance candidate")
    deleted_hashes: dict[str, str] = {}
    repair_delta = manifest.get("repairReviewDelta")
    removed_snapshots = (
        repair_delta.get("removedArtifactSnapshots", [])
        if isinstance(repair_delta, dict)
        else []
    )
    for artifact in removed_snapshots:
        if (
            not isinstance(artifact, dict)
            or not isinstance(artifact.get("artifact"), str)
            or artifact["artifact"] in deleted_hashes
            or not _HASH.fullmatch(str(artifact.get("sha256")))
        ):
            raise BootstrapBindingError("Bootstrap deleted artifact binding is invalid")
        deleted_hashes[artifact["artifact"]] = artifact["sha256"]
    for binding in candidate_identity["changedPathBindings"]:
        source = artifact_hashes if binding["state"] == "present" else deleted_hashes
        if source.get(binding["path"]) != binding["sha256"]:
            raise BootstrapBindingError(
                "Bootstrap reviewed bytes do not match the Acceptance candidate"
            )
    if not set(review_scope["scope"]).issubset(artifact_hashes):
        raise BootstrapBindingError("Bootstrap run does not bind the complete review scope")
    candidate_context_paths = {
        candidate_identity["acceptanceRunInputPath"],
        candidate_identity["candidateContentManifestPath"],
        *[item["path"] for item in candidate_identity["knowledgeArtifacts"]],
    }
    if not candidate_context_paths.issubset(set(review_scope["scope"])):
        raise BootstrapBindingError(
            "Acceptance candidate context is outside the Bootstrap review scope"
        )
    if not isinstance(bundle, dict) or not isinstance(bundle.get("inventoryAttestation"), dict):
        raise BootstrapBindingError("Bootstrap Acceptance Auditor bundle is invalid")
    attestation = bundle["inventoryAttestation"]
    validate_inventory_attestation(attestation, binding, scope)
    if (
        attestation.get("reviewId") != envelope.get("reviewId")
        or attestation.get("inputHash") != envelope.get("inputHash")
    ):
        raise BootstrapBindingError(
            "Bootstrap Acceptance Auditor attestation is bound to another run"
        )
    finalized_core = {key: value for key, value in envelope.items() if key != "generatedAt"}
    result = {
        "controlPlaneRevision": envelope["controlPlaneRevision"],
        "bootstrapRunDir": normalized_run_dir,
        "finalizedRun": envelope,
        "finalizedRunCoreHash": _canonical_hash(finalized_core),
        "inventoryAttestation": attestation,
        "inventoryAttestationHash": _canonical_hash(attestation),
        "bindingHash": _canonical_hash(binding),
        "scopeHash": _canonical_hash(scope),
        "candidateIdentity": candidate_identity,
        "candidateIdentityHash": _canonical_hash(candidate_identity),
        "bootstrapRoutePath": bootstrap_route["path"],
        "bootstrapRouteFileHash": bootstrap_route["fileHash"],
        "bootstrapRouteHash": bootstrap_route["routeHash"],
    }
    validate_import_envelope(
        {"schemaVersion": "bootstrap-import-envelope.v3", **result, "authorizes": []},
        {
            "bootstrapRunDir": normalized_run_dir,
            "binding": binding,
            "scope": scope,
            "candidateIdentity": candidate_identity,
            "bootstrapRoute": bootstrap_route,
        },
    )
    return result


def project_bootstrap_execution_state(
    decision: Any,
    *,
    launch_authorization: Any,
    binding: Any,
) -> dict[str, Any]:
    """Derive consumer state from immutable inputs without becoming launch authority."""
    if not isinstance(decision, dict) or decision.get("requirement") not in {"required", "not_required"}:
        raise BootstrapBindingError("bootstrap requirement decision is invalid")
    actions = (
        "bind-bootstrap-capabilities",
        "prepare-attestation",
        "prepare-bootstrap",
        "import-bootstrap-result",
        "map-findings",
        "import-mapping-approval",
        "project-impact",
        "finalize",
    )
    if decision["requirement"] == "not_required":
        return {
            "schemaVersion": "bootstrap-execution-state.v1",
            "state": "not_applicable",
            "actionStates": {action: "not_applicable" for action in actions},
            "authorizes": [],
        }
    authorization_valid = (
        isinstance(launch_authorization, dict)
        and launch_authorization.get("status") == "authorized"
        and _HASH.fullmatch(str(launch_authorization.get("authorizationHash"))) is not None
    )
    if not authorization_valid:
        return {
            "schemaVersion": "bootstrap-execution-state.v1",
            "state": "awaiting_authorization",
            "actionStates": {
                "bind-bootstrap-capabilities": "ready",
                **{action: "waiting-external" for action in actions if action != "bind-bootstrap-capabilities"},
            },
            "authorizes": [],
        }
    try:
        _required_capability(binding)
    except BootstrapBindingError:
        return {
            "schemaVersion": "bootstrap-execution-state.v1",
            "state": "prepared",
            "actionStates": {
                "bind-bootstrap-capabilities": "ready",
                **{action: "blocked" for action in actions if action != "bind-bootstrap-capabilities"},
            },
            "authorizes": [],
        }
    return {
        "schemaVersion": "bootstrap-execution-state.v1",
        "state": "awaiting_external",
        "actionStates": {
            "bind-bootstrap-capabilities": "completed",
            "prepare-attestation": "ready",
            "prepare-bootstrap": "waiting-external",
            "import-bootstrap-result": "waiting-external",
            "map-findings": "blocked",
            "import-mapping-approval": "not_applicable",
            "project-impact": "blocked",
            "finalize": "blocked",
        },
        "authorizes": [],
    }


def validate_finding_mapping(mapping: Any, live_check_ids: Any, tombstoned_check_ids: Any) -> None:
    """Validate a consumer-side sidecar without changing the source Bootstrap finding."""
    if not isinstance(live_check_ids, set) or not isinstance(tombstoned_check_ids, set) or any(not isinstance(value, str) or not value for value in live_check_ids | tombstoned_check_ids):
        raise BootstrapBindingError("finding mapping lineage is invalid")
    common = {"schemaVersion", "findingId", "findingHash", "mappingKind", "authorizes"}
    if not isinstance(mapping, dict) or mapping.get("schemaVersion") != "bootstrap-finding-acceptance-map.v1" or mapping.get("authorizes") != []:
        raise BootstrapBindingError("finding mapping is invalid")
    if not isinstance(mapping.get("findingId"), str) or not mapping["findingId"] or not _HASH.fullmatch(str(mapping.get("findingHash"))):
        raise BootstrapBindingError("finding mapping identity is invalid")
    kind = mapping.get("mappingKind")
    if kind == "check":
        if set(mapping) != common | {"checkId"} or not isinstance(mapping.get("checkId"), str):
            raise BootstrapBindingError("check finding mapping fields are invalid")
        check_id = mapping["checkId"]
        if check_id in tombstoned_check_ids:
            raise BootstrapBindingError("finding mapping check is tombstoned")
        if check_id not in live_check_ids:
            raise BootstrapBindingError("finding mapping check is unknown")
        return
    if kind == "cross_cutting":
        required = common | {"affectedPhaseIds", "gateRegistryHash", "phaseGraphHash"}
        if set(mapping) != required or not isinstance(mapping.get("affectedPhaseIds"), list) or not mapping["affectedPhaseIds"] or any(not isinstance(value, str) or not value for value in mapping["affectedPhaseIds"]) or not _HASH.fullmatch(str(mapping.get("gateRegistryHash"))) or not _HASH.fullmatch(str(mapping.get("phaseGraphHash"))):
            raise BootstrapBindingError("cross-cutting finding mapping fields are invalid")
        return
    raise BootstrapBindingError("finding mapping kind is invalid")


def validate_mapping_approval(
    approval: Any,
    required_approver_role: str,
    finding_hash: str,
    matrix_hash: str,
    lineage_hash: str,
    import_envelope_hash: str,
) -> None:
    """Validate a formally imported human mapping approval; free-text approval is not accepted."""
    expected_hashes = {
        "findingHash": finding_hash,
        "matrixHash": matrix_hash,
        "lineageHash": lineage_hash,
        "importEnvelopeHash": import_envelope_hash,
    }
    if not isinstance(required_approver_role, str) or not required_approver_role or any(not _HASH.fullmatch(value) for value in expected_hashes.values()):
        raise BootstrapBindingError("mapping approval expectations are invalid")
    required = {
        "schemaVersion", "approverRole", "identityEvidenceHash", "expiresAtUtc", "findingHash", "mappingHash",
        "matrixHash", "lineageHash", "importEnvelopeHash", "authorizes",
    }
    if not isinstance(approval, dict) or set(approval) != required:
        raise BootstrapBindingError("mapping approval fields are invalid")
    if approval.get("schemaVersion") != "bootstrap-finding-mapping-approval.v1" or approval.get("authorizes") != [] or approval.get("approverRole") != required_approver_role:
        raise BootstrapBindingError("mapping approval is unauthorized")
    if not _HASH.fullmatch(str(approval.get("identityEvidenceHash"))) or not _HASH.fullmatch(str(approval.get("mappingHash"))):
        raise BootstrapBindingError("mapping approval identity is invalid")
    if any(approval[key] != value for key, value in expected_hashes.items()):
        raise BootstrapBindingError("mapping approval lineage is stale")
    try:
        expiry = datetime.fromisoformat(str(approval.get("expiresAtUtc")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise BootstrapBindingError("mapping approval expiry is invalid") from exc
    if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
        raise BootstrapBindingError("mapping approval is expired")
