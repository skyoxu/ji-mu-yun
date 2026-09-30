from pathlib import Path

import pytest

from s26_fixture import assert_boundary_behavior, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-O13BEA926B50D-1")
def test_o_13bea926b50d() -> None:
    assert_boundary_behavior(
        run_boundary_case(REPOSITORY_ROOT, "O_13BEA926B50D"),
        "FAILURE-O-13BEA926B50D",
    )
