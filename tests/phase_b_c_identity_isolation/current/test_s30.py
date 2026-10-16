from pathlib import Path

import pytest

from s30_fixture import assert_boundary_observation, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-O-13F33C30B03B-1")
def test_o_13f33c30b03b() -> None:
    assert_boundary_observation(run_boundary_case(REPOSITORY_ROOT))
