from __future__ import annotations

import hashlib
import json
from typing import Any


HASH_RE = "sha256:"
DECISION_VERSION = "v11"
POLICY_SCHEMA = "acceptance-semantic-review-trigger-policy.v1"
WORKFLOW_PROFILE = "bootstrap-skill-route"
IMPLEMENTATION_PROFILE = "bootstrap-implementation-conformance"
TRIGGERS = {
    "workflow_control_plane_changed",
    "protected_high_risk_boundary_changed",
    "public_api_contract_changed",
    "database_schema_or_migration_changed",
    "runtime_or_deployment_boundary_changed",
    "shared_execution_entrypoint_changed",
    "explicit_maintainer_review_request",
    "deterministic_evidence_incomplete",
    "risk_classification_unknown",
}
TYPED_PATH_TRIGGERS = {
    "public_api_contract_changed",
    "database_schema_or_migration_changed",
    "runtime_or_deployment_boundary_changed",
    "shared_execution_entrypoint_changed",
}
COMPANION_EXPECTATIONS = [{
    "capabilityId": "acceptance-inventory-attestation",
    "capabilityVersion": "1.0",
    "producerRole": "acceptance_auditor",
}]


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return HASH_RE + hashlib.sha256(payload).hexdigest()


def _require_repository_bound_inputs(inputs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    candidate = inputs.get("candidateIdentity")
    evidence = inputs.get("deterministicEvidence")
    policy = inputs.get("policy")
    if not isinstance(candidate, dict) or not isinstance(evidence, dict) or not isinstance(policy, dict):
        raise ValueError("repository-bound candidateIdentity, deterministicEvidence, and policy are required")
    if "workflowControlPlaneChange" in candidate or "highRiskBoundary" in candidate or "protectedFacts" in inputs:
        raise ValueError("caller-authored semantic risk facts are not accepted")
    paths = candidate.get("changedPaths")
    if not isinstance(paths, list) or any(not isinstance(path, str) or not path for path in paths):
        raise ValueError("candidateIdentity changedPaths must be a non-empty string list")
    if policy.get("schemaVersion") != POLICY_SCHEMA or policy.get("authorizes") != []:
        raise ValueError("repository-owned trigger policy is invalid")
    if set(policy.get("hardTriggers", [])) != TRIGGERS:
        raise ValueError("repository-owned trigger policy enum is invalid")
    for key in ("workflowControlPlanePrefixes", "protectedHighRiskPrefixes", "knownLowRiskPrefixes"):
        if not isinstance(policy.get(key), list) or any(not isinstance(item, str) or not item for item in policy[key]):
            raise ValueError("repository-owned trigger policy prefixes are invalid")
    typed = policy.get("typedRiskPrefixes")
    if (
        not isinstance(typed, dict)
        or set(typed) != TYPED_PATH_TRIGGERS
        or any(
            not isinstance(prefixes, list)
            or any(not isinstance(item, str) or not item for item in prefixes)
            for prefixes in typed.values()
        )
    ):
        raise ValueError("repository-owned typed risk policy is invalid")
    return candidate, evidence, policy


def _prefix_match(path: str, prefixes: list[Any]) -> bool:
    return any(
        isinstance(prefix, str)
        and prefix
        and (path.startswith(prefix) if prefix.endswith("/") else path == prefix)
        for prefix in prefixes
    )


def _classify_changed_paths(paths: list[str], policy: dict[str, Any]) -> tuple[dict[str, list[str]], list[str]]:
    hits = {trigger: [] for trigger in ("workflow_control_plane_changed", "protected_high_risk_boundary_changed", *sorted(TYPED_PATH_TRIGGERS))}
    unknown: list[str] = []
    for path in paths:
        matched = False
        if _prefix_match(path, policy["workflowControlPlanePrefixes"]):
            hits["workflow_control_plane_changed"].append(path)
            matched = True
        if _prefix_match(path, policy["protectedHighRiskPrefixes"]):
            hits["protected_high_risk_boundary_changed"].append(path)
            matched = True
        for trigger in sorted(TYPED_PATH_TRIGGERS):
            if _prefix_match(path, policy["typedRiskPrefixes"][trigger]):
                hits[trigger].append(path)
                matched = True
        if not matched and not _prefix_match(path, policy["knownLowRiskPrefixes"]):
            unknown.append(path)
    return hits, unknown


def decide_review_requirement(inputs: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(inputs, dict):
        raise ValueError("review requirement inputs must be an object")
    candidate, evidence, policy = _require_repository_bound_inputs(inputs)
    path_hits, unknown_paths = _classify_changed_paths(candidate["changedPaths"], policy)
    workflow_change = bool(path_hits["workflow_control_plane_changed"])
    intent = inputs.get("maintainerIntent", "default")
    if intent not in {"default", "request"}:
        raise ValueError("maintainerIntent is invalid")
    evidence_status = evidence.get("status")
    reason_codes: list[str] = []
    sources: list[str] = []
    if evidence_status != "passed":
        reason_codes.append("deterministic_evidence_incomplete")
        sources.append("deterministicEvidence.status")
    for trigger in (
        "workflow_control_plane_changed",
        "protected_high_risk_boundary_changed",
        *sorted(TYPED_PATH_TRIGGERS),
    ):
        if path_hits[trigger]:
            reason_codes.append(trigger)
            sources.append("candidateIdentity.changedPaths")
    if unknown_paths:
        reason_codes.append("risk_classification_unknown")
        sources.append("candidateIdentity.changedPaths")
    if intent == "request":
        reason_codes.append("explicit_maintainer_review_request")
        sources.append("maintainerIntent")
    if not reason_codes:
        reason_codes.append("deterministic_low_risk")
        sources.append("candidateIdentity.changedPaths")

    blocked = evidence_status != "passed" or bool(unknown_paths)
    requirement = None if blocked else ("required" if intent == "request" else "not_required")
    profile = None if blocked or requirement == "not_required" else (WORKFLOW_PROFILE if workflow_change else IMPLEMENTATION_PROFILE)
    document: dict[str, Any] = {
        "schemaVersion": "acceptance-semantic-review-requirement-decision.v1",
        "decisionVersion": DECISION_VERSION,
        "producer": "refactor-implementation-acceptance",
        "decisionStatus": "blocked" if blocked else "ready",
        "requirement": requirement,
        "profile": profile,
        "reasonCodes": reason_codes,
        "requirementSources": sources,
        "inputHashes": {
            "candidateIdentity": _hash(candidate),
            "deterministicEvidence": _hash(evidence),
            "policy": _hash(policy),
        },
        "policyHash": _hash(policy),
        "candidateIdentityHash": _hash(candidate),
        "deterministicEvidenceHash": _hash(evidence),
        "maintainerIntent": intent,
        "requiredCompanionCapabilityExpectations": COMPANION_EXPECTATIONS if requirement == "required" else [],
        "authorizes": [],
    }
    document["decisionHash"] = _hash(document)
    return document

