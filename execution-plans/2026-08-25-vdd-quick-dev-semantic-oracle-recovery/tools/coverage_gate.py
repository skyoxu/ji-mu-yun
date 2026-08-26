"""Exact many-to-many coverage gate."""
from __future__ import annotations

from typing import Any


def validate_many_to_many_cover(edges: list[dict[str, Any]], manifest: set[str], observations: set[str]) -> tuple[bool, str]:
    covered: set[str] = set()
    for edge in edges:
        if not isinstance(edge, dict) or not {"acceptance_id", "case_id", "observation_id"}.issubset(edge):
            return False, "COVERAGE-EXACT-COVER-RED"
        if edge["acceptance_id"] not in manifest or edge["observation_id"] not in observations or not str(edge["observation_id"]).startswith("OBS-"):
            return False, "COVERAGE-EXACT-COVER-RED"
        covered.add(edge["acceptance_id"])
    return covered == manifest and bool(edges), "" if covered == manifest and edges else "COVERAGE-EXACT-COVER-RED"
