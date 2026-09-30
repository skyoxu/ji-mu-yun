import pytest

from s74_fixture import assert_behavior, invoke_boundary_test


CASE_NAME = "PhaseA.Platform.Tests.PhaseB.Repair.S74BoundaryTests.O_FA59596D5B97"


@pytest.mark.cer_assertion("A-O-FA59596D5B97-1")
def test_o_fa59596d5b97() -> None:
    result = invoke_boundary_test(CASE_NAME)
    assert_behavior(
        result,
        "S74-OBSERVATION O-FA59596D5B97 unsafe-legacy-workspace-blocked-before-adoption",
        "FAILURE-O-FA59596D5B97",
    )
