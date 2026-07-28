"""Consumer-side immutable bindings for Bootstrap-owned companion capability."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any


class BootstrapBindingError(ValueError):
    pass


_HASH = re.compile(r"sha256:[a-f0-9]{64}$")
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
    scope = sorted({path for paths in context_classes.values() for path in paths})
    closure = {
        "schemaVersion": "implementation-acceptance-bootstrap-scope.v1",
        "profile": "bootstrap-implementation-conformance",
        "strategy": "minimal-complete-closure",
        "scope": scope,
        "contextClasses": context_classes,
        "directoryScopeAttestation": None,
        "authorizes": [],
    }
    closure["scopeHash"] = _canonical_hash(closure)
    return closure


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
    if not isinstance(scope, dict) or not _HASH.fullmatch(str(scope.get("scopeHash"))):
        raise BootstrapBindingError("attestation scope is invalid")
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


def validate_import_envelope(envelope: Any, expected_hashes: Any) -> None:
    """Reject partial or drifted Bootstrap imports before they reach acceptance calculation."""
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
