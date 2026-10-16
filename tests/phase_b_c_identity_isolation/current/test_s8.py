from pathlib import Path

import pytest

from s8_fixture import assert_boundary_behavior, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-O-1939141A84C2-1")
def test_o_1939141a84c2() -> None:
    result = run_boundary_case(REPOSITORY_ROOT, "O_1939141A84C2")
    assert_boundary_behavior(result, "FAILURE-O-1939141A84C2")
