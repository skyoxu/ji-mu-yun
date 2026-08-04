from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any


def _snapshot(value: Any) -> bytes | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("snapshot must be base64 text or null")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("snapshot must be valid base64") from exc


def parse(observation: dict[str, Any]) -> dict[str, Any]:
    """Validate an explicit, non-authoritative stage observation and decode snapshot bytes."""
    required = {"stage", "exit_code", "observed_at", "changed_files", "commands_attempted", "response_summary"}
    if set(observation) != required or observation.get("stage") not in {"red", "green", "refactor"}:
        raise ValueError("stage observation shape is invalid")
    if not isinstance(observation["exit_code"], int) or not isinstance(observation["observed_at"], str) or not isinstance(observation["response_summary"], str):
        raise ValueError("stage observation scalar fields are invalid")
    commands = observation["commands_attempted"]
    changes = observation["changed_files"]
    if not isinstance(commands, list) or any(not isinstance(item, str) or not item for item in commands) or not isinstance(changes, list):
        raise ValueError("stage observation lists are invalid")
    parsed: list[dict[str, Any]] = []
    for item in changes:
        if not isinstance(item, dict) or set(item) != {"path", "before_bytes_base64", "after_bytes_base64"} or not isinstance(item.get("path"), str):
            raise ValueError("changed file observation is invalid")
        path = PurePosixPath(item["path"])
        if path.is_absolute() or ".." in path.parts or not item["path"]:
            raise ValueError("changed file path is invalid")
        parsed.append({"path": item["path"], "before_bytes": _snapshot(item["before_bytes_base64"]), "after_bytes": _snapshot(item["after_bytes_base64"])})
    return {**observation, "changed_files": parsed}


def parse_sequence(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse one complete, strictly ordered observed TDD lifecycle."""
    parsed = [parse(item) for item in observations]
    if [item["stage"] for item in parsed] != ["red", "green", "refactor"]:
        raise ValueError("stage observation order must be RED, GREEN, REFACTOR")
    if parsed[0]["exit_code"] == 0:
        raise ValueError("RED observation requires a nonzero exit")
    if any(item["exit_code"] != 0 for item in parsed[1:]):
        raise ValueError("GREEN and REFACTOR observations require zero exits")
    try:
        times = [datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00")) for item in parsed]
    except ValueError as exc:
        raise ValueError("stage observation timestamps are invalid") from exc
    if any(item.tzinfo is None for item in times) or not (times[0] < times[1] < times[2]):
        raise ValueError("stage observation timestamps are not strictly increasing")
    return parsed


def canonical_diff(observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive deterministic file transitions from one parsed observation's snapshots."""
    changes = observation.get("changed_files")
    if not isinstance(changes, list):
        raise ValueError("parsed changed files are required")
    result: list[dict[str, Any]] = []
    for item in sorted(changes, key=lambda value: value["path"]):
        before, after = item.get("before_bytes"), item.get("after_bytes")
        if before is None and after is None:
            raise ValueError("a changed file requires before or after bytes")
        change_type = "add" if before is None else "delete" if after is None else "modify"
        result.append({
            "path": item["path"], "change_type": change_type,
            "before_sha256": None if before is None else "sha256:" + hashlib.sha256(before).hexdigest(),
            "after_sha256": None if after is None else "sha256:" + hashlib.sha256(after).hexdigest(),
        })
    return result


def backend_response(observation: dict[str, Any], plan_id: str, slice_id: str, run_id: str, attempt_id: str) -> dict[str, Any]:
    """Project one observation into the schema's minimized, non-authoritative backend response."""
    changed_files = [item["path"] for item in observation.get("changed_files", [])]
    summary = observation.get("response_summary")
    if not isinstance(summary, str):
        raise ValueError("parsed response summary is required")
    return {
        "schema_version": "jimuyun.backend-response.v1", "plan_id": plan_id, "slice_id": slice_id,
        "run_id": run_id, "attempt_id": attempt_id, "stage": observation["stage"],
        "backend_protocol_version": "1.0", "self_reported_status": "candidate",
        "changed_files": changed_files, "commands_attempted": list(observation["commands_attempted"]),
        "blockers": [], "response_summary": summary,
        "raw_response_hash": "sha256:" + hashlib.sha256(summary.encode("utf-8")).hexdigest(),
        "raw_body_persisted": False, "contains_sensitive_data": False, "untrusted": True,
    }


def backend_request(plan_id: str, slice_id: str, run_id: str, attempt_id: str, stage: str, capsule_hash: str, allowed_command_ids: list[str], previous_attempt_id: str | None) -> dict[str, Any]:
    goals = {"red": "observe-red", "green": "make-red-green", "refactor": "preserve-green-refactor"}
    if stage not in goals or not capsule_hash.startswith("sha256:") or not allowed_command_ids:
        raise ValueError("request inputs are invalid")
    binding = f"STAGE-{stage.upper()}"
    payload = {"capsule_hash": capsule_hash, "stage_binding_id": binding, "goal": goals[stage], "allowed_command_ids": allowed_command_ids}
    return {
        "schema_version": "jimuyun.backend-request.v1", "plan_id": plan_id, "slice_id": slice_id,
        "run_id": run_id, "attempt_id": attempt_id, "stage": stage, "stage_binding_id": binding,
        "actor": {"role": "slice-capsule-executor", "backend_protocol_version": "1.0", "actor_instance_id": "explicit-stage-observation", "identity_authoritative": False},
        "capsule_ref": {"path_type": "run_path", "path": f"context/CAP-{int(attempt_id.split('-')[-1]):03d}/slice-capsule.v1.json", "sha256": capsule_hash},
        "goal": goals[stage], "allowed_command_ids": allowed_command_ids,
        "request_payload_hash": "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "raw_body_persisted": False, "contains_sensitive_data": False, "previous_attempt_id": previous_attempt_id,
    }
