from pathlib import Path

import pytest

from s20_fixture import assert_boundary_behavior, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_behavior(method_name: str, failure_id: str) -> None:
    assert_boundary_behavior(run_boundary_case(REPOSITORY_ROOT, method_name), failure_id)


@pytest.mark.cer_assertion("A-O-0D256558EC1D-1")
def test_o_0d256558ec1d() -> None:
    _assert_boundary_behavior("O_0D256558EC1D", "FAILURE-O-0D256558EC1D")


@pytest.mark.cer_assertion("SM-W10.ProjectSoftDelete_ReleasesLogicalQuota")
def test_o_ae14d92cb000() -> None:
    _assert_boundary_behavior("O_AE14D92CB000", "FAILURE-O-AE14D92CB000")


@pytest.mark.cer_assertion("SM-W10.ProjectSoftDelete_RetainsDataForProtectedCleanup")
def test_o_ed5afffde466() -> None:
    _assert_boundary_behavior("O_ED5AFFFDE466", "FAILURE-O-ED5AFFFDE466")


@pytest.mark.cer_assertion("SM-W10.ProjectSoftDelete_RetainsOwnershipForProtectedCleanup")
def test_o_fd2c50597483() -> None:
    _assert_boundary_behavior("O_FD2C50597483", "FAILURE-O-FD2C50597483")
