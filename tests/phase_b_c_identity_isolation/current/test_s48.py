from pathlib import Path

import pytest

from s48_fixture import assert_boundary_observation, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-O-92963141AC9F-1")
def test_o_92963141ac9f() -> None:
    assert_boundary_observation(run_boundary_case(REPOSITORY_ROOT))
