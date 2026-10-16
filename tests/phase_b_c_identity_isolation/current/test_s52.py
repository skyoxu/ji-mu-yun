import pytest

from s52_fixture import assert_behavior, invoke_boundary_test


CASE_NAME = "PhaseA.Platform.Tests.PhaseB.Repair.S52BoundaryTests.O_EE142D9EE309"


@pytest.mark.cer_assertion("A-O-EE142D9EE309-1")
def test_o_ee142d9ee309() -> None:
    assert_behavior(
        invoke_boundary_test(CASE_NAME),
        "S52-OBSERVATION O-EE142D9EE309 old-preview-ticket-denied-after-restore",
        "FAILURE-O-EE142D9EE309",
    )
