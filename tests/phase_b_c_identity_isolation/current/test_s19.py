import pytest

from s19_fixture import assert_behavior, invoke_boundary_test


CASE_NAME = "PhaseA.Platform.Tests.PhaseB.Repair.S19BoundaryTests.O_192BAC5BF05E"
OBSERVATION = (
    "S19-OBSERVATION O-192BAC5BF05E "
    "server-record-and-verified-content-validity-is-identical-across-null-default-and-changed-placement-references"
)


@pytest.mark.cer_assertion("A-192-1")
def test_o_192bac5bf05e() -> None:
    assert_behavior(invoke_boundary_test(CASE_NAME), OBSERVATION, "FAILURE-O-192BAC5BF05E")
