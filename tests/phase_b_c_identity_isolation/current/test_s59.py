from pathlib import Path

import pytest

from s59_fixture import assert_boundary_observation, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-O-C865-1")
def test_o_c865a3100948() -> None:
    assert_boundary_observation(
        run_boundary_case(REPOSITORY_ROOT, "O_C865A3100948"),
        "S59-OBSERVATION O-C865A3100948 snapshot-content-survives-source-loss",
        "FAILURE-O-C865A3100948",
    )


@pytest.mark.cer_assertion("ASSERT-824-LAST-PUBLISHED-RPO")
def test_o_824_last_published_rpo() -> None:
    assert_boundary_observation(
        run_boundary_case(REPOSITORY_ROOT, "O_824_LAST_PUBLISHED_RPO"),
        "S59-OBSERVATION O-824-LAST-PUBLISHED-RPO last-published-a-survives-interrupted-b",
        "FAILURE-O-824-LAST-PUBLISHED-RPO",
    )
