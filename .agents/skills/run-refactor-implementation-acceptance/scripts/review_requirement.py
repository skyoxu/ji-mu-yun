from __future__ import annotations

import hashlib
import json
from typing import Any


HASH_RE = "sha256:"
DECISION_VERSION = "v10"
POLICY_SCHEMA = "acceptance-semantic-review-trigger-policy.v1"
WORKFLOW_PROFILE = "bootstrap-skill-route"
IMPLEMENTATION_PROFILE = "bootstrap-implementation-conformance"
TRIGGERS = {
    "workflow_control_plane_changed",
    "protected_high_risk_boundary_changed",
    "explicit_maintainer_review_request",
    "deterministic_evidence_incomplete",
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
    for key in ("workflowControlPlanePrefixes", "protectedHighRiskPrefixes"):
        if not isinstance(policy.get(key), list) or any(not isinstance(item, str) or not item for item in policy[key]):
            raise ValueError("repository-owned trigger policy prefixes are invalid")
    return candidate, evidence, policy


def _prefix_match(path: str, prefixes: list[Any]) -> bool:
    return any(isinstance(prefix, str) and prefix and (path == prefix or path.startswith(prefix)) for prefix in prefixes)


def decide_review_requirement(inputs: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(inputs, dict):
        raise ValueError("review requirement inputs must be an object")
    candidate, evidence, policy = _require_repository_bound_inputs(inputs)
    workflow_change = any(_prefix_match(path, policy["workflowControlPlanePrefixes"]) for path in candidate["changedPaths"])
    high_risk = any(_prefix_match(path, policy["protectedHighRiskPrefixes"]) for path in candidate["changedPaths"])
    intent = inputs.get("maintainerIntent", "default")
    if intent not in {"default", "request"}:
        raise ValueError("maintainerIntent is invalid")
    evidence_status = evidence.get("status")
    reason_codes: list[str] = []
    sources: list[str] = []
    if evidence_status != "passed":
        reason_codes.append("deterministic_evidence_incomplete")
        sources.append("deterministicEvidence.status")
    if workflow_change:
        reason_codes.append("workflow_control_plane_changed")
        sources.append("candidateIdentity.changedPaths")
    if high_risk:
        reason_codes.append("protected_high_risk_boundary_changed")
        sources.append("candidateIdentity.changedPaths")
    if intent == "request":
        reason_codes.append("explicit_maintainer_review_request")
        sources.append("maintainerIntent")
    if not reason_codes:
        reason_codes.append("deterministic_low_risk")
        sources.append("candidateIdentity.changedPaths")

    blocked = evidence_status != "passed"
    requirement = None if blocked else ("required" if reason_codes != ["deterministic_low_risk"] else "not_required")
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
