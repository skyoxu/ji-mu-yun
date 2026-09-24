from pathlib import Path

import pytest

from s33_fixture import assert_boundary_observation, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_observation(method_name: str, observation: str, failure_id: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_observation(result, observation, failure_id)


@pytest.mark.cer_assertion("A-8E338F-CLEANUP-COMPLETE")
def test_o_8e338ffa23d1() -> None:
    _assert_boundary_observation(
        "O_8E338FFA23D1",
        "S33-OBSERVATION O-8E338FFA23D1 terminal-runner-completed-and-queue-lifecycle-cleared",
        "FAILURE-O-8E338FFA23D1",
    )


@pytest.mark.cer_assertion("A-BD42DD-CANCEL-STOPS")
def test_o_bd42dd72212f() -> None:
    _assert_boundary_observation(
        "O_BD42DD72212F",
        "S33-OBSERVATION O-BD42DD72212F cancellation-stopped-running-operation-and-cleared-queue",
        "FAILURE-O-BD42DD72212F",
    )
