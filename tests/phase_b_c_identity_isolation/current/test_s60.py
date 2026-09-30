from pathlib import Path

import pytest

from s60_fixture import assert_boundary_observation, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-O-1E49B9F4CF89")
def test_o_1e49b9f4cf89() -> None:
    assert_boundary_observation(
        run_boundary_case(REPOSITORY_ROOT, "O_1E49B9F4CF89"),
        "S60-OBSERVATION O-1E49B9F4CF89 all-six-escape-forms-rejected-for-workspace-snapshot-restore-and-artifact-reads",
        "FAILURE-O-1E49B9F4CF89",
    )


@pytest.mark.cer_assertion("A-O-3B86525DF394")
def test_o_3b86525df394() -> None:
    assert_boundary_observation(
        run_boundary_case(REPOSITORY_ROOT, "O_3B86525DF394"),
        "S60-OBSERVATION O-3B86525DF394 all-six-escape-forms-rejected-for-workspace-snapshot-restore-and-artifact-writes",
        "FAILURE-O-3B86525DF394",
    )
