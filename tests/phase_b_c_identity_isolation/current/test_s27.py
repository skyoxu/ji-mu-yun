from pathlib import Path

import pytest

from s27_fixture import assert_boundary_observation, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-O-EF3B026F4525-1")
def test_o_ef3b026f4525() -> None:
    assert_boundary_observation(
        run_boundary_case(REPOSITORY_ROOT, "O_EF3B026F4525"),
        "S27-OBSERVATION O-EF3B026F4525 publication-denied-after-account-disablement-no-result-or-lease",
        "FAILURE-O-EF3B026F4525",
    )
