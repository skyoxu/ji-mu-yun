import pytest

from s42_fixture import assert_behavior, invoke_boundary_test


CASE_PREFIX = "PhaseA.Platform.Tests.PhaseB.Repair.S42BoundaryTests"


@pytest.mark.cer_assertion("A-605D7CAE42F3-1")
def test_o_605d7cae42f3() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_605D7CAE42F3")
    assert_behavior(
        result,
        "S42-OBSERVATION O-605D7CAE42F3 evidence-pointer-resolves-through-authorized-readback",
        "FAILURE-O-605D7CAE42F3",
    )
