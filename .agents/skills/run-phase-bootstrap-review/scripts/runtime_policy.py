"""Pure Bootstrap runtime-policy decisions over append-only process events."""
from __future__ import annotations

from typing import Any


_PROGRESS_KINDS = {"evidence_increment", "segment_terminal", "phase_terminal", "registered_transition"}


def _identity(value: dict[str, Any]) -> tuple[str, str, str, str]:
    keys = ("candidate", "closure", "segment", "attempt")
    result = tuple(value.get(key) for key in keys)
    if any(not isinstance(item, str) or not item for item in result):
        raise ValueError("effective progress identity is incomplete")
    return result  # type: ignore[return-value]


def validate_effective_progress(event: dict[str, Any], current_identity: dict[str, Any]) -> bool:
    if not isinstance(event, dict) or event.get("kind") not in _PROGRESS_KINDS:
        raise ValueError("event is not effective progress")
    if _identity(event) != _identity(current_identity):
        raise ValueError("effective progress identity is stale")
    if event["kind"] == "evidence_increment" and not isinstance(event.get("evidence_hash"), str):
        raise ValueError("evidence increment lacks an evidence identity")
    return True


def watchdog_state(policy: dict[str, Any], last_effective_progress: int, now: int) -> str:
    ceiling = policy.get("no_progress_seconds") if isinstance(policy, dict) else None
    if not isinstance(ceiling, int) or isinstance(ceiling, bool) or ceiling <= 0:
        raise ValueError("runtime policy no-progress ceiling is invalid")
    if not isinstance(last_effective_progress, int) or not isinstance(now, int) or now < last_effective_progress:
        raise ValueError("watchdog timestamps are invalid")
    return "no-progress-stop" if now - last_effective_progress >= ceiling else "active"


def reconcile_leases(events: list[dict[str, Any]], live_processes: dict[int, str]) -> dict[str, list[str]]:
    active: dict[str, dict[str, Any]] = {}
    stale: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("process event is invalid")
        attempt = event.get("attempt")
        if not isinstance(attempt, str) or not attempt:
            raise ValueError("process event lacks attempt identity")
        if event.get("kind") == "attempt_started":
            active[attempt] = event
        elif event.get("kind") in {"attempt_terminal", "attempt_stale"}:
            active.pop(attempt, None)
            process = event.get("process")
            if isinstance(process, dict) and isinstance(process.get("pid"), int) and isinstance(process.get("created"), str):
                if live_processes.get(process["pid"]) != process["created"]:
                    stale.append(attempt)
    occupied: set[str] = set()
    for attempt, event in active.items():
        process, write_set = event.get("process"), event.get("write_set")
        if not isinstance(process, dict) or not isinstance(process.get("pid"), int) or not isinstance(process.get("created"), str):
            raise ValueError("attempt process identity is invalid")
        if not isinstance(write_set, list) or any(not isinstance(path, str) or not path for path in write_set):
            raise ValueError("attempt write set is invalid")
        if live_processes.get(process["pid"]) != process["created"]:
            stale.append(attempt)
            continue
        occupied.update(write_set)
    return {"occupied_write_set": sorted(occupied), "stale_attempts": sorted(stale)}


def retry_decision(policy: dict[str, Any], family: str, prior_attempts: int, segment: str, failed_segments: set[str]) -> str:
    limits = policy.get("retry_limits") if isinstance(policy, dict) else None
    if not isinstance(limits, dict) or not isinstance(family, str) or not isinstance(prior_attempts, int):
        raise ValueError("retry input is invalid")
    limit = limits.get(family)
    if family != "transport" or not isinstance(limit, int) or limit <= 0:
        return "blocked"
    if not isinstance(segment, str) or segment not in failed_segments or prior_attempts >= limit:
        return "blocked"
    return "retry"
