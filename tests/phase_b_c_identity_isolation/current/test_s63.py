from pathlib import Path

import pytest

from s63_fixture import assert_boundary_observation, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-AB9EF0-PERPROJECT-SINGLE-WRITER")
def test_o_ab9ef0d40f90() -> None:
    result = run_boundary_case(REPOSITORY_ROOT, "O_AB9EF0D40F90")
    assert_boundary_observation(
        result,
        "S63-OBSERVATION O-AB9EF0D40F90 per-project-heavy-writer-exclusivity-held-until-release",
        "FAILURE-O-AB9EF0D40F90",
    )
