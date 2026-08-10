"""Select accepted knowledge decisions before Bootstrap Artifact View freeze."""

from __future__ import annotations

from typing import Any


def select_context(*, required_classes: list[str], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    satisfied: set[str] = set()
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for decision in decisions:
        values = decision.get("satisfies", [])
        if decision.get("decision") == "accepted" and isinstance(values, list) and values:
            satisfied.update(value for value in values if isinstance(value, str))
            accepted.append(decision)
        else:
            rejected.append(decision)
    missing = sorted(set(required_classes) - satisfied)
    return {"status": "incomplete" if missing else "ready", "missing_context_classes": missing, "accepted": accepted, "rejected": rejected}
