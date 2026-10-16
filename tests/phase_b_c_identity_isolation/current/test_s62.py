from pathlib import Path

import pytest

from s62_fixture import assert_boundary_observation, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-93887-A1")
def test_o_93887d63fce9() -> None:
    assert_boundary_observation(
        run_boundary_case(REPOSITORY_ROOT, "O_93887D63FCE9"),
        "S62-OBSERVATION O-93887D63FCE9 restore-interruption-and-staging-disposition-audited",
        "FAILURE-O-93887D63FCE9",
    )
