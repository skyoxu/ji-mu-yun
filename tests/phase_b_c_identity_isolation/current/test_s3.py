from pathlib import Path

import pytest

from s3_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CASE_NAME = "O_6578750F6BE9"
FAILURE_ID = "FAILURE-O-6578750F6BE9"


@pytest.mark.cer_assertion("A-O657-NO-PLAINTEXT-KEY")
def test_o_6578750f6be9() -> None:
    result = run_boundary_case(REPOSITORY_ROOT, CASE_NAME)
    assert_boundary_passes(result, FAILURE_ID)
