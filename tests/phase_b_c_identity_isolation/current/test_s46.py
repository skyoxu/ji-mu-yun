from pathlib import Path

import pytest

from s46_fixture import assert_boundary_observation, invoke_boundary_test


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-O08-TERMINAL-COVERAGE")
def test_o_08ba4578bec0() -> None:
    assert_boundary_observation(
        invoke_boundary_test(REPOSITORY_ROOT, "O_08BA4578BEC0"),
        "S46-OBSERVATION O-08BA4578BEC0 terminal-coverage-complete",
        "FAILURE-O-08BA4578BEC0",
    )


@pytest.mark.cer_assertion("A-O163-1")
def test_o_16352853820e() -> None:
    assert_boundary_observation(
        invoke_boundary_test(REPOSITORY_ROOT, "O_16352853820E"),
        "S46-OBSERVATION O-16352853820E independent-process-evidence-validated",
        "FAILURE-O-16352853820E",
    )


@pytest.mark.cer_assertion("A-CDE3-independent-topology-evidence")
def test_o_cde3e478ff2d() -> None:
    assert_boundary_observation(
        invoke_boundary_test(REPOSITORY_ROOT, "O_CDE3E478FF2D"),
        "S46-OBSERVATION O-CDE3E478FF2D topology-seed-independently-revalidated",
        "FAILURE-O-CDE3E478FF2D",
    )
