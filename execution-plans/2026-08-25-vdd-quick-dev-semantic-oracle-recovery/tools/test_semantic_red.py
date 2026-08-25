"""Intentional RED probe for the semantic-oracle handoff."""
from pathlib import Path


def test_vdd_semantic_oracle_boundary_red() -> None:
    # The failure marker is part of the typed RED contract. GREEN must replace
    # this fixture with the real semantic behavior before the slice can pass.
    if not (Path(__file__).parents[1] / "probe-state" / "S1.json").is_file():
        raise AssertionError("FAILURE_ID:VDD-RED-BOUNDARY")
