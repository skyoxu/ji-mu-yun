"""NN+1 promotion gate for the nine false-green fixtures."""
from __future__ import annotations

from typing import Any


def validate_promotion(fixtures: list[dict[str, Any]], predecessor_judge: str | None, writer: str) -> tuple[bool, str]:
    expected = {f"FG-{index:02d}" for index in range(1, 10)}
    if writer != "coverage-gate" or not isinstance(predecessor_judge, str) or not predecessor_judge.startswith("sha256:") or "coverage" in predecessor_judge:
        return False, "PROMOTION-FALSE-GREEN-RED"
    if len(fixtures) != 9 or {item.get("fixture_id") for item in fixtures if isinstance(item, dict)} != expected:
        return False, "PROMOTION-FALSE-GREEN-RED"
    if len({item.get("category") for item in fixtures if isinstance(item, dict)}) != 9:
        return False, "PROMOTION-FALSE-GREEN-RED"
    if any(not item.get("blocked_failure_id") or not item.get("baseline_hash", "").startswith("sha256:") or not item.get("mutation_hash", "").startswith("sha256:") or item.get("baseline_hash") == item.get("mutation_hash") for item in fixtures if isinstance(item, dict)):
        return False, "PROMOTION-FALSE-GREEN-RED"
    return all(item.get("blocked") is True and item.get("corrected_pair_pass") is True for item in fixtures), "PROMOTION-FALSE-GREEN-RED"
