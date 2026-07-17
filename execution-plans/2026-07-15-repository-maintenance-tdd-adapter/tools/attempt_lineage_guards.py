from __future__ import annotations

from typing import Any

from protocol_artifact_guards import finding, value_hash, validate_ref


STAGE_ORDER = ["red", "green", "refactor"]
ACCEPTED_LIFECYCLE = [
    "attempt-started",
    "request-recorded",
    "response-recorded",
    "diff-recorded",
    "decision-finalized",
]


def validate_accepted_stage_order(
    attempts: list[dict[str, Any]], *, require_complete: bool
) -> list[dict[str, str]]:
    accepted = [
        attempt.get("adapter_decision", {}).get("stage")
        for attempt in attempts
        if attempt.get("adapter_decision", {}).get("decision") == "accepted_for_validation"
    ]
    expected = STAGE_ORDER if require_complete else STAGE_ORDER[: len(accepted)]
    if accepted != expected:
        return [finding("RMAP-ATTEMPT-STAGE-ORDER", "attempts", "accepted stages are not the legal RED -> GREEN -> REFACTOR prefix")]
    return []


def validate_event_lifecycle(
    identity: tuple[str, str, str],
    attempts: list[dict[str, Any]],
    events: list[dict[str, Any]],
    store: dict[tuple[str, str], bytes],
) -> list[dict[str, str]]:
    if not events or [item.get("sequence") for item in events] != list(range(1, len(events) + 1)):
        return [finding("RMAP-ATTEMPT-LINEAGE", "events", "event sequence is missing or non-monotonic")]
    previous_hash: str | None = None
    grouped: dict[str, list[dict[str, Any]]] = {}
    for index, event in enumerate(events):
        if (event.get("plan_id"), event.get("slice_id"), event.get("run_id")) != identity or event.get("previous_event_hash") != previous_hash:
            return [finding("RMAP-ATTEMPT-LINEAGE", "events", "event identity or predecessor hash is invalid")]
        for ref_index, ref in enumerate(event.get("artifact_refs", [])):
            errors = validate_ref(ref, store, f"events[{index}].artifact_refs[{ref_index}]", role_required=False)
            if errors:
                return [finding("RMAP-ATTEMPT-EVENT-ARTIFACT", f"events[{index}]", "event artifact reference is missing or stale against actual bytes")]
        grouped.setdefault(str(event.get("attempt_id")), []).append(event)
        previous_hash = value_hash(event)
    attempt_ids = {attempt.get("backend_request", {}).get("attempt_id") for attempt in attempts}
    if set(grouped) != attempt_ids:
        return [finding("RMAP-ATTEMPT-EVENT-LIFECYCLE", "events", "event attempts do not exactly cover persisted attempts")]
    for attempt in attempts:
        decision = attempt["adapter_decision"]
        attempt_id = decision["attempt_id"]
        lifecycle = grouped[attempt_id]
        event_types = [event["event_type"] for event in lifecycle]
        status = decision["decision"]
        if status == "accepted_for_validation":
            if event_types != ACCEPTED_LIFECYCLE or any(event["attempt_status"] != "in_progress" for event in lifecycle[:-1]) or lifecycle[-1]["attempt_status"] != "accepted":
                return [finding("RMAP-ATTEMPT-EVENT-LIFECYCLE", attempt_id, "accepted attempt lifecycle is incomplete or reordered")]
        elif status == "rejected":
            if event_types != ACCEPTED_LIFECYCLE or lifecycle[-1]["attempt_status"] != "rejected":
                return [finding("RMAP-ATTEMPT-EVENT-LIFECYCLE", attempt_id, "rejected attempt lifecycle is incomplete")]
        elif status == "incomplete":
            if event_types[-1:] != ["attempt-incomplete"] or lifecycle[-1]["attempt_status"] != "incomplete":
                return [finding("RMAP-ATTEMPT-EVENT-LIFECYCLE", attempt_id, "incomplete attempt lacks terminal evidence")]
        else:
            return [finding("RMAP-ATTEMPT-EVENT-LIFECYCLE", attempt_id, "unknown attempt decision state")]
    return []
