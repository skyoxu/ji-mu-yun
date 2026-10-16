from pathlib import Path

import pytest

from s65_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion('A-O-9FB2427DA00F')
def test_o_9fb2427da00f() -> None:
    result = run_boundary_case(REPOSITORY_ROOT, "O_9FB2427DA00F")
    assert_boundary_passes(result, "FAILURE-O-9FB2427DA00F")
