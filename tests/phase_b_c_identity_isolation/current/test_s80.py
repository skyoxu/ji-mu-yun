from pathlib import Path

import pytest

from s80_fixture import assert_boundary_behavior, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-OD921E468D50A-1")
def test_o_d92173a93038() -> None:
    result = run_boundary_case(REPOSITORY_ROOT, "O_D92173A93038")
    assert_boundary_behavior(result, "FAILURE-O-D92173A93038")


@pytest.mark.cer_assertion("A-OFCAFEB88277C-1")
def test_o_fcafeb88277c() -> None:
    result = run_boundary_case(REPOSITORY_ROOT, "O_FCAFEB88277C")
    assert_boundary_behavior(result, "FAILURE-O-FCAFEB88277C")
