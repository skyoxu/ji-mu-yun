"""NN+1 promotion gate for the nine false-green fixtures."""
from __future__ import annotations

from typing import Any


def validate_promotion(fixtures: list[dict[str, Any]], predecessor_judge: str | None, writer: str) -> tuple[bool, str]:
    expected = {f"FG-{index:02d}" for index in range(1, 10)}
    if writer != "coverage-gate" or not isinstance(predecessor_judge, str) or not predecessor_judge.startswith("sha256:") or "coverage" in predecessor_judge:
        return False, "PROMOTION-FALSE-GREEN-RED"
    if {item.get("fixture_id") for item in fixtures if isinstance(item, dict)} != expected:
        return False, "PROMOTION-FALSE-GREEN-RED"
    return all(item.get("blocked") is True and item.get("corrected_pair_pass") is True for item in fixtures), "PROMOTION-FALSE-GREEN-RED"
