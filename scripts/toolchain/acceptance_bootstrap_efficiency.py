"""Fail-closed evidence validator for Acceptance/Bootstrap rollout regression."""

from __future__ import annotations

from typing import Any


_HISTORICAL_RUNS = {"vcec-r1", "vcec-r1m", "vcec-r1n"}
_METRICS = {"closureBytes", "segments", "attempts", "retries", "tokens", "wallTimeSeconds"}


class RolloutEvidenceError(ValueError):
    pass


def validate_rollout_evidence(value: Any) -> dict[str, Any]:
    """Validate regression evidence without turning it into lifecycle authority."""
    required = {
        "schemaVersion", "historicalRuns", "deterministicFailure", "semanticCorpus",
        "telemetry", "gates", "defaultSwitch", "authorizes",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise RolloutEvidenceError("rollout evidence fields are invalid")
    if value["schemaVersion"] != "acceptance-bootstrap-efficiency-rollout.v1" or value["authorizes"] != []:
        raise RolloutEvidenceError("rollout evidence cannot authorize lifecycle state")
    historical = value["historicalRuns"]
    if not isinstance(historical, list) or {item.get("runId") for item in historical if isinstance(item, dict)} != _HISTORICAL_RUNS:
        raise RolloutEvidenceError("historical run coverage is incomplete")
    for item in historical:
        if (
            not isinstance(item, dict)
            or set(item) != {"runId", "outcome", "classification", "reusable", "authorizes"}
            or item.get("outcome") != "abandoned"
            or item.get("classification") != "historical-runtime-failure"
            or item.get("reusable") is not False
            or item.get("authorizes") != []
        ):
            raise RolloutEvidenceError("historical failure was rewritten or made reusable")
    deterministic = value["deterministicFailure"]
    if (
        not isinstance(deterministic, dict)
        or set(deterministic) != {"status", "reviewerCalls", "authorizes"}
        or deterministic.get("status") != "failed"
        or deterministic.get("reviewerCalls") != 0
        or deterministic.get("authorizes") != []
    ):
        raise RolloutEvidenceError("deterministic failure launched reviewer work")
    corpus = value["semanticCorpus"]
    if (
        not isinstance(corpus, dict)
        or set(corpus) != {"status", "falseAuthorization", "authorizes"}
        or corpus.get("status") != "passed"
        or corpus.get("falseAuthorization") is not False
        or corpus.get("authorizes") != []
    ):
        raise RolloutEvidenceError("semantic corpus permits false authorization")
    telemetry = value["telemetry"]
    if (
        not isinstance(telemetry, dict)
        or set(telemetry) != _METRICS
        or any(not isinstance(metric, int) or isinstance(metric, bool) or metric < 0 for metric in telemetry.values())
        or telemetry["segments"] < 1
    ):
        raise RolloutEvidenceError("rollout telemetry is incomplete")
    gates = value["gates"]
    if not isinstance(gates, dict) or set(gates) != {"M0", "M1", "M2"} or any(state not in {"passed", "blocked", "pending"} for state in gates.values()):
        raise RolloutEvidenceError("rollout gates are invalid")
    if not isinstance(value["defaultSwitch"], bool):
        raise RolloutEvidenceError("default switch is invalid")
    if value["defaultSwitch"] and set(gates.values()) != {"passed"}:
        raise RolloutEvidenceError("default switch is premature")
    return value
