import pytest

from s14_fixture import assert_behavior, invoke_boundary_test


CASE_NAME = "PhaseA.Platform.Tests.PhaseB.Repair.S14BoundaryTests.O_11DDC0AAE540"


@pytest.mark.cer_assertion("A-11DDC0AAE540-1")
def test_o_11ddc0aae540() -> None:
    result = invoke_boundary_test(CASE_NAME)
    assert_behavior(
        result,
        "S14-OBSERVATION O-11DDC0AAE540 durable-operations-survive-browser-disconnect",
        "FAILURE-O-11DDC0AAE540",
    )
