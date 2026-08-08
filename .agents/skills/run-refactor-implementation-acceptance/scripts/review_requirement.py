from __future__ import annotations

import hashlib
import json
from typing import Any


HASH_RE = "sha256:"


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return HASH_RE + hashlib.sha256(payload).hexdigest()


def decide_review_requirement(inputs: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(inputs, dict):
        raise ValueError("review requirement inputs must be an object")
    candidate = inputs.get("candidate")
    evidence = inputs.get("deterministicEvidence")
    facts = inputs.get("protectedFacts")
    if not isinstance(candidate, dict) or not isinstance(evidence, dict) or not isinstance(facts, dict):
        raise ValueError("candidate, deterministicEvidence, and protectedFacts are required")
    changed_paths = candidate.get("changedPaths")
    if not isinstance(changed_paths, list) or any(not isinstance(path, str) or not path for path in changed_paths):
        raise ValueError("candidate changedPaths must be a non-empty string list")
    high_risk = facts.get("highRiskBoundary", False)
    workflow_change = candidate.get("workflowControlPlaneChange", False)
    if not isinstance(high_risk, bool) or not isinstance(workflow_change, bool):
        raise ValueError("risk facts must be explicit booleans")
    intent = inputs.get("maintainerIntent", "default")
    if intent not in {"default", "request"}:
        raise ValueError("maintainerIntent is invalid")
    caller = inputs.get("callerRequirement")
    if caller not in {None, "required", "not_required"}:
        raise ValueError("callerRequirement is invalid")

    reason_codes: list[str] = []
    sources: list[str] = []
    if workflow_change:
        reason_codes.append("workflow-control-plane-change")
        sources.append("candidate.workflowControlPlaneChange")
    if high_risk:
        reason_codes.append("protected-high-risk-boundary")
        sources.append("protectedFacts.highRiskBoundary")
    if intent == "request":
        reason_codes.append("explicit-maintainer-request")
        sources.append("maintainerIntent")
    if evidence.get("status") != "passed":
        reason_codes.append("deterministic-facts-incomplete")
        sources.append("deterministicEvidence.status")
    if not reason_codes:
        reason_codes.append("deterministic-low-risk")
        sources.append("candidate-and-protected-facts")

    requirement = "required" if reason_codes != ["deterministic-low-risk"] else "not_required"
    document: dict[str, Any] = {
        "schemaVersion": "acceptance-semantic-review-requirement-decision.v1",
        "decisionVersion": "v9",
        "requirement": requirement,
        "profile": "bootstrap-implementation-conformance" if requirement == "required" else None,
        "reasonCodes": reason_codes,
        "requirementSources": sources,
        "inputHashes": {
            "candidate": _hash(candidate),
            "deterministicEvidence": _hash(evidence),
            "protectedFacts": _hash(facts),
        },
        "callerRequirement": caller,
        "authorizes": [],
    }
    document["decisionHash"] = _hash(document)
    return document
