from pathlib import Path

import pytest

from s44_fixture import assert_matrix_case, invoke_boundary_test


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FAILURE_ID = "FAILURE-O-6C4973EE3FE2"


@pytest.mark.parametrize(
    ("category", "condition"),
    [
        pytest.param(category, condition, marks=pytest.mark.cer_assertion("A-6C4973-topology-reference-matrix"))
        for category in ("node", "runner", "sandbox", "attempt", "snapshot")
        for condition in ("null", "default", "changed")
    ],
)
def test_o_6c4973ee3fe2(category: str, condition: str) -> None:
    assert_matrix_case(invoke_boundary_test(REPOSITORY_ROOT), category, condition, FAILURE_ID)
