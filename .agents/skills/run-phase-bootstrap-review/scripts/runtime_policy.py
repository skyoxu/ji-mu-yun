"""Pure Bootstrap runtime-policy decisions over append-only process events."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_PROGRESS_KINDS = {"evidence_increment", "segment_terminal", "phase_terminal", "registered_transition"}
_REQUIRED_POSITIVE_FIELDS = (
    "liveness_seconds", "effective_progress_seconds", "no_progress_seconds",
    "launch_grace_seconds", "terminal_grace_seconds", "lease_seconds",
    "backoff_seconds", "status_throttle_seconds", "output_max_bytes",
)


def _identity(value: dict[str, Any]) -> tuple[str, str, str, str]:
    keys = ("candidate", "closure", "segment", "attempt")
    result = tuple(value.get(key) for key in keys)
    if any(not isinstance(item, str) or not item for item in result):
        raise ValueError("effective progress identity is incomplete")
    return result  # type: ignore[return-value]


def validate_runtime_policy(policy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, dict) or policy.get("schema_version") != "bootstrap-runtime-policy.v1":
        raise ValueError("runtime policy schema is invalid")
    for field in _REQUIRED_POSITIVE_FIELDS:
        value = policy.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"runtime policy {field} is invalid")
    limits = policy.get("retry_limits")
    if not isinstance(limits, dict) or not limits:
        raise ValueError("runtime policy retry limits are invalid")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in limits.values()):
        raise ValueError("runtime policy retry limit is invalid")
    if policy.get("authorizes") != []:
        raise ValueError("runtime policy must not authorize lifecycle state")
    return policy


def load_runtime_policy(path: str | Path) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("runtime policy is unavailable") from exc
    return validate_runtime_policy(document)


def validate_effective_progress(event: dict[str, Any], current_identity: dict[str, Any]) -> bool:
    if not isinstance(event, dict) or event.get("kind") not in _PROGRESS_KINDS:
        raise ValueError("event is not effective progress")
    if _identity(event) != _identity(current_identity):
        raise ValueError("effective progress identity is stale")
    if event["kind"] == "evidence_increment" and not isinstance(event.get("evidence_hash"), str):
        raise ValueError("evidence increment lacks an evidence identity")
    return True


def watchdog_state(policy: dict[str, Any], last_effective_progress: int, now: int) -> str:
    validated = validate_runtime_policy(policy)
    ceiling = validated["no_progress_seconds"]
    if not isinstance(last_effective_progress, int) or not isinstance(now, int) or now < last_effective_progress:
        raise ValueError("watchdog timestamps are invalid")
    return "no-progress-stop" if now - last_effective_progress >= ceiling else "active"


def _event_time(event: dict[str, Any], field: str) -> int:
    value = event.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"process event {field} is invalid")
    return value


def reconcile_leases(
    events: list[dict[str, Any]], live_processes: dict[int, str], *, now: int, policy: dict[str, Any],
) -> dict[str, list[str]]:
    """Rebuild lease occupancy from immutable events; heartbeat never refreshes progress."""
    validated = validate_runtime_policy(policy)
    active: dict[str, dict[str, Any]] = {}
    stale: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("process event is invalid")
        attempt = event.get("attempt")
        if not isinstance(attempt, str) or not attempt:
            raise ValueError("process event lacks attempt identity")
        kind = event.get("kind")
        if kind == "attempt_started":
            started_at = _event_time(event, "timestamp")
            active[attempt] = {
                "event": event,
                "liveness_at": started_at,
                "progress_at": started_at,
                "terminal": False,
            }
        elif attempt in active and kind == "heartbeat":
            active[attempt]["liveness_at"] = _event_time(event, "timestamp")
        elif attempt in active and kind == "effective_progress":
            validate_effective_progress(event["progress"], event["identity"])
            active[attempt]["progress_at"] = _event_time(event, "timestamp")
        elif kind in {"attempt_terminal", "attempt_stale"}:
            active.pop(attempt, None)
            stale.add(attempt)
    occupied: set[str] = set()
    for attempt, state in active.items():
        event = state["event"]
        process, write_set = event.get("process"), event.get("write_set")
        if not isinstance(process, dict) or not isinstance(process.get("pid"), int) or not isinstance(process.get("created"), str):
            raise ValueError("attempt process identity is invalid")
        if not isinstance(write_set, list) or any(not isinstance(path, str) or not path for path in write_set):
            raise ValueError("attempt write set is invalid")
        process_matches = live_processes.get(process["pid"]) == process["created"]
        liveness_current = now - state["liveness_at"] < validated["liveness_seconds"]
        progress_current = now - state["progress_at"] < validated["effective_progress_seconds"]
        if not (process_matches and liveness_current and progress_current):
            stale.add(attempt)
            continue
        occupied.update(write_set)
    return {
        "occupied_write_set": sorted(occupied),
        "occupied_attempts": sorted(
            attempt for attempt, state in active.items()
            if attempt not in stale
            and live_processes.get(state["event"]["process"]["pid"]) == state["event"]["process"]["created"]
            and now - state["liveness_at"] < validated["liveness_seconds"]
            and now - state["progress_at"] < validated["effective_progress_seconds"]
        ),
        "stale_attempts": sorted(stale),
    }


def _iso_epoch(value: Any) -> int:
    if not isinstance(value, str):
        raise ValueError("Bootstrap process event timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Bootstrap process event timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("Bootstrap process event timestamp must be timezone-aware")
    return int(parsed.astimezone(timezone.utc).timestamp())


def reconcile_bootstrap_process_events(
    events: list[dict[str, Any]],
    live_processes: dict[int, str],
    *,
    now: int,
    policy: dict[str, Any],
) -> dict[str, list[str]]:
    """Adapt the canonical Bootstrap process-event schema to lease reconciliation."""
    adapted: list[dict[str, Any]] = []
    terminal_types = {"attempt-completed", "attempt-failed", "attempt-rejected", "attempt-stale", "attempt-abandoned"}
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Bootstrap process event is invalid")
        event_type = event.get("eventType")
        attempt = event.get("attemptId")
        if not isinstance(attempt, str) or not attempt:
            continue
        timestamp = _iso_epoch(event.get("timestamp"))
        if event_type == "attempt-started":
            process = {"pid": event.get("pid"), "created": event.get("processIdentity")}
            adapted.append({
                "kind": "attempt_started", "attempt": attempt, "timestamp": timestamp,
                "write_set": event.get("writeSet", []), "process": process,
            })
        elif event_type == "attempt-heartbeat":
            adapted.append({"kind": "heartbeat", "attempt": attempt, "timestamp": timestamp})
        elif event_type == "attempt-effective-progress":
            identity = event.get("effectiveProgressIdentity")
            progress = event.get("effectiveProgress")
            if not isinstance(identity, dict) or not isinstance(progress, dict):
                raise ValueError("Bootstrap Effective Progress event is incomplete")
            adapted.append({
                "kind": "effective_progress", "attempt": attempt, "timestamp": timestamp,
                "identity": identity, "progress": progress,
            })
        elif event_type in terminal_types:
            adapted.append({
                "kind": "attempt_terminal", "attempt": attempt, "timestamp": timestamp,
                "process": {"pid": event.get("pid"), "created": event.get("processIdentity")},
                "write_set": event.get("writeSet", []),
            })
    return reconcile_leases(adapted, live_processes, now=now, policy=policy)


def retry_decision(policy: dict[str, Any], family: str, prior_attempts: int, segment: str, failed_segments: set[str]) -> str:
    limits = validate_runtime_policy(policy)["retry_limits"]
    if not isinstance(family, str) or not isinstance(prior_attempts, int):
        raise ValueError("retry input is invalid")
    limit = limits.get(family)
    if family != "transport" or not isinstance(limit, int) or limit <= 0:
        return "blocked"
    if not isinstance(segment, str) or segment not in failed_segments or prior_attempts >= limit:
        return "blocked"
    return "retry"
