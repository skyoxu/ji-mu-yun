"""Acceptance-owned semantic route, Bootstrap import, and finalization checks."""

from __future__ import annotations

from typing import Any

from acceptance_core import InputError, canonical_hash


_MODES = {"supervised", "unattended"}
_ROUTES = {
    "deterministic_only",
    "focused_repair_verification",
    "full_implementation_conformance",
    "manual_pause",
}
_TRIGGER_UPGRADE = {
    "explicit_request",
    "unresolved_advisory_high_risk",
    "security_permission_data_corruption",
    "lifecycle_authority_control_change",
    "independent_adversarial_review",
}
_COMPLETE_REVIEW_ROLES = {"blind_hunter", "edge_case_hunter", "acceptance_auditor"}


def project_route(acceptance_mode: str, requested_route: str, trigger_ids: Any = None) -> dict[str, Any]:
    """Project the fixed mode x route matrix without authorizing execution."""
    if acceptance_mode not in _MODES or requested_route not in _ROUTES:
        raise InputError("acceptance mode or route is invalid")
    triggers = [] if trigger_ids is None else trigger_ids
    if not isinstance(triggers, list) or any(not isinstance(item, str) or not item for item in triggers):
        raise InputError("registered trigger ids are invalid")
    if len(triggers) != len(set(triggers)) or any(item not in _TRIGGER_UPGRADE for item in triggers):
        raise InputError("registered trigger ids are unsupported")
    route = requested_route
    if route == "deterministic_only" and triggers:
        route = "full_implementation_conformance"
    if route == "manual_pause":
        return {"acceptanceMode": acceptance_mode, "route": route, "triggerIds": sorted(triggers), "authorizes": []}
    bootstrap_required = route in {"focused_repair_verification", "full_implementation_conformance"}
    return {
        "acceptanceMode": acceptance_mode,
        "route": route,
        "triggerIds": sorted(triggers),
        "bootstrapRequired": bootstrap_required,
        "authorizes": [],
    }


def validate_supervised_decision(decision: Any, expected: dict[str, str]) -> dict[str, Any]:
    """Validate the maintainer-only legal deterministic fast-path decision."""
    required = {
        "schemaVersion", "decision", "owner", "acceptanceMode", "route", "triggerIds",
        "baselineIdentityHash", "candidateIdentityHash", "consumerClosureHash",
        "requiredChecksHash", "policyHash", "specSelectionHash", "authorizes", "decisionHash",
    }
    if not isinstance(decision, dict) or set(decision) != required:
        raise InputError("supervised decision fields are incomplete")
    if (
        decision["schemaVersion"] != "acceptance-supervised-decision.v1"
        or decision["decision"] != "semantic_review_satisfied"
        or decision["owner"] != "maintainer"
        or decision["acceptanceMode"] != "supervised"
        or decision["route"] != "deterministic_only"
        or decision["triggerIds"] != []
        or decision["authorizes"] != []
    ):
        raise InputError("supervised decision is not a legal fast path")
    for key in ("baselineIdentityHash", "candidateIdentityHash", "consumerClosureHash", "requiredChecksHash", "policyHash", "specSelectionHash"):
        if decision[key] != expected.get(key) or not isinstance(decision[key], str) or not decision[key].startswith("sha256:"):
            raise InputError("supervised decision identity binding is stale")
    if decision["decisionHash"] != canonical_hash({key: value for key, value in decision.items() if key != "decisionHash"}):
        raise InputError("supervised decision hash is stale")
    return decision


def validate_bootstrap_import(imported: Any, expected: dict[str, str]) -> dict[str, Any]:
    """Require current finalized Bootstrap evidence for semantic routes."""
    if not isinstance(imported, dict) or imported.get("authorizes") != []:
        raise InputError("Bootstrap import is not non-authorizing evidence")
    if imported.get("schemaVersion") != "bootstrap-import-envelope.v3":
        raise InputError("Bootstrap import schema is invalid")
    for key in ("candidateIdentityHash", "scopeHash", "bootstrapRouteHash", "finalizedRunCoreHash"):
        value = imported.get(key)
        if not isinstance(value, str) or not value.startswith("sha256:"):
            raise InputError("Bootstrap import identity is incomplete")
        expected_value = expected.get(key)
        if expected_value is not None and value != expected_value:
            raise InputError("Bootstrap import identity is stale")
    finalized = imported.get("finalizedRun")
    if not isinstance(finalized, dict) or finalized.get("validationStatus") != "passed" or finalized.get("finalStatus") not in {"clean", "advisory"}:
        raise InputError("Bootstrap finalized evidence is not passed")
    roles = imported.get("completedRoles")
    if not isinstance(roles, list) or set(roles) != _COMPLETE_REVIEW_ROLES:
        raise InputError("Bootstrap Complete Review role coverage is incomplete")
    return imported


def finalize_acceptance(request: Any) -> dict[str, Any]:
    """Publish the only lifecycle transition owned by this module."""
    required = {"acceptanceMode", "route", "triggerIds", "identities", "supervisedDecision", "bootstrapImport"}
    if not isinstance(request, dict) or set(request) != required:
        raise InputError("Acceptance finalization request is incomplete")
    route = project_route(request["acceptanceMode"], request["route"], request["triggerIds"])
    identities = request["identities"]
    if not isinstance(identities, dict) or any(not isinstance(value, str) or not value.startswith("sha256:") for value in identities.values()):
        raise InputError("Acceptance identity set is invalid")
    if route["route"] == "manual_pause":
        raise InputError("manual pause cannot finalize acceptance")
    if route["route"] == "deterministic_only":
        if request["acceptanceMode"] == "supervised":
            validate_supervised_decision(request["supervisedDecision"], identities)
        elif request["supervisedDecision"] is not None:
            raise InputError("unattended deterministic-only cannot consume maintainer decision")
        if request["bootstrapImport"] is not None:
            raise InputError("deterministic-only route cannot import Bootstrap evidence")
    else:
        if request["bootstrapImport"] is None:
            raise InputError("semantic route requires Bootstrap evidence")
        validate_bootstrap_import(request["bootstrapImport"], identities)
        if request["supervisedDecision"] is not None:
            raise InputError("Bootstrap route cannot use fast-path decision")
    result = {
        "schemaVersion": "acceptance-passed.v1",
        "acceptanceMode": route["acceptanceMode"],
        "route": route["route"],
        "triggerIds": route["triggerIds"],
        "identityHash": canonical_hash(identities),
        "lifecycleTransition": "acceptance-passed",
        "authorizes": ["acceptance-passed"],
    }
    return result
