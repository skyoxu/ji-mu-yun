#!/usr/bin/env python3
"""Normalize and append isolated fresh-context evaluation evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_RUN_FIELDS = {
    "scenario_level", "run", "model", "evaluator", "isolation", "rubric_version",
    "vcr_results", "passed", "evidence",
}


def normalize_run(policy: dict[str, Any], raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != REQUIRED_RUN_FIELDS:
        raise ValueError("fresh-context run has an invalid envelope")
    requirements = policy.get("requirements")
    evaluator = policy.get("evaluator")
    if not isinstance(requirements, list) or not isinstance(evaluator, dict):
        raise ValueError("fresh-context policy is invalid")
    if raw["scenario_level"] not in policy.get("scenario_levels", []) or not isinstance(raw["run"], int):
        raise ValueError("fresh-context scenario/run is invalid")
    if raw["model"] not in policy.get("allowed_models", []):
        raise ValueError("fresh-context model is not allowed")
    if (
        raw["evaluator"] != evaluator.get("owner")
        or raw["isolation"] != evaluator.get("isolation")
        or raw["rubric_version"] != evaluator.get("version")
    ):
        raise ValueError("fresh-context evaluator binding is invalid")
    vcr_results = raw["vcr_results"]
    if (
        not isinstance(vcr_results, dict) or set(vcr_results) != set(requirements)
        or any(not isinstance(vcr_results[item], bool) for item in requirements)
        or not isinstance(raw["passed"], bool) or not isinstance(raw["evidence"], str) or not raw["evidence"].strip()
    ):
        raise ValueError("fresh-context run result is invalid")
    return {field: raw[field] for field in sorted(REQUIRED_RUN_FIELDS)}


def append_run(policy: dict[str, Any], run: dict[str, Any], attempt_id: str | None = None) -> tuple[bool, str]:
    results = policy.get("results")
    if attempt_id is not None:
        attempts = policy.get("attempts")
        attempt = next((item for item in attempts if isinstance(item, dict) and item.get("attempt_id") == attempt_id), None) if isinstance(attempts, list) else None
        results = attempt.get("results") if isinstance(attempt, dict) else None
    if not isinstance(results, list):
        return False, "policy results are invalid"
    slot = (run["scenario_level"], run["run"])
    if any(isinstance(item, dict) and (item.get("scenario_level"), item.get("run")) == slot for item in results):
        return False, "duplicate scenario/run slot"
    results.append(run)
    return True, ""


def create_attempt(policy: dict[str, Any], attempt_id: str) -> tuple[bool, str, dict[str, Any] | None]:
    """Append a new evaluation generation without rewriting prior result evidence."""
    if not isinstance(attempt_id, str) or not attempt_id:
        return False, "attempt ID is invalid", None
    attempts = policy.setdefault("attempts", [])
    if not isinstance(attempts, list):
        return False, "policy attempts are invalid", None
    if any(isinstance(item, dict) and item.get("attempt_id") == attempt_id for item in attempts):
        return False, "attempt ID already exists", None
    attempt = {"attempt_id": attempt_id, "status": "unverified", "results": []}
    attempts.append(attempt)
    policy["active_attempt_id"] = attempt_id
    return True, "", attempt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--attempt-id")
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    raw = json.loads(args.run.read_text(encoding="utf-8"))
    try:
        normalized = normalize_run(policy, raw)
        if args.append:
            accepted, message = append_run(policy, normalized, args.attempt_id)
            if not accepted:
                raise ValueError(message)
            args.policy.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"status": "PASS", "run": normalized}, ensure_ascii=False))
        return 0
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
