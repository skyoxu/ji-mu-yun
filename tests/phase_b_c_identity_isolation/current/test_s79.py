from pathlib import Path

import pytest

from s79_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CASE_NAME = "O_39E75106860B"
FAILURE_ID = "FAILURE-O-39E75106860B"


@pytest.mark.cer_assertion("A-O-39E75106860B-1")
def test_o_39e75106860b() -> None:
    result = run_boundary_case(REPOSITORY_ROOT, CASE_NAME)
    assert_boundary_passes(result, FAILURE_ID)
