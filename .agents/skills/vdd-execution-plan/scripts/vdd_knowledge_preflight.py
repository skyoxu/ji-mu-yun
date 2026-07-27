"""Build a VDD-owned, hash-bound knowledge-consumption preflight result."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def evaluate_consumption(*, required_modules: list[str], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    satisfied: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for decision in decisions:
        accepted = decision.get("decision") == "accepted"
        modules = decision.get("satisfies", [])
        if not isinstance(modules, list) or any(not isinstance(value, str) or not value for value in modules):
            raise ValueError("invalid consumption decision modules")
        if accepted and not modules:
            raise ValueError("accepted decision must satisfy a module")
        if not accepted and modules:
            raise ValueError("rejected decision cannot satisfy a module")
        if accepted:
            satisfied.update(modules)
        normalized.append({"decision": "accepted" if accepted else "rejected", "satisfies": modules})
    missing = sorted(set(required_modules) - satisfied)
    return {"status": "blocked" if missing else "ready", "missing_required_modules": missing, "decisions": normalized}


def evaluate_preflight(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate that VDD decisions consume, rather than expand, Locator output."""
    result = evaluate_consumption(
        required_modules=payload.get("required_modules", []),
        decisions=payload.get("decisions", []),
    )
    request = payload.get("locator_request")
    locator_result = payload.get("locator_result")
    if not isinstance(request, dict) or not isinstance(locator_result, dict):
        result["status"] = "blocked"
        result["failure_code"] = "locator_binding_missing"
        return result
    if request.get("schema_version") != "jimuyun.knowledge-locator-request.v1" or locator_result.get("schema_version") != "jimuyun.knowledge-locator-result.v1":
        result["status"] = "blocked"
        result["failure_code"] = "locator_schema_invalid"
        return result
    if request.get("request_id") != locator_result.get("request_id"):
        result["status"] = "blocked"
        result["failure_code"] = "locator_request_id_mismatch"
        return result
    if request.get("snapshot") != locator_result.get("snapshot"):
        result["status"] = "blocked"
        result["failure_code"] = "locator_snapshot_mismatch"
        return result
    candidates = locator_result.get("candidates", [])
    if not isinstance(candidates, list):
        result["status"] = "blocked"
        result["failure_code"] = "locator_candidates_invalid"
        return result
    available = {
        (candidate.get("path"), candidate.get("source_sha256"))
        for candidate in candidates
        if isinstance(candidate, dict)
    }
    for decision in payload.get("decisions", []):
        if decision.get("decision") != "accepted":
            continue
        candidate = decision.get("candidate")
        if not isinstance(candidate, dict) or (
            candidate.get("path"), candidate.get("source_sha256")
        ) not in available:
            result["status"] = "blocked"
            result["failure_code"] = "accepted_candidate_not_locator_bound"
            return result
    if result["status"] == "ready" and locator_result.get("status") != "matched":
        result["status"] = "blocked"
        result["failure_code"] = "locator_result_not_matched"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = evaluate_preflight(payload)
    result["schema_version"] = "jimuyun.vdd-knowledge-preflight.v1"
    result["input_sha256"] = _sha(payload)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
