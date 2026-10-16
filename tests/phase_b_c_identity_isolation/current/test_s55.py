import pytest

from s55_fixture import assert_behavior, invoke_boundary_test


CASE_PREFIX = "PhaseA.Platform.Tests.PhaseB.Repair.S55BoundaryTests"


@pytest.mark.cer_assertion("assert-admin-disable-authorized")
def test_o_42e454ae0e75() -> None:
    assert_behavior(
        invoke_boundary_test(f"{CASE_PREFIX}.O_42E454AE0E75"),
        "FAILURE-O-42E454AE0E75",
    )


@pytest.mark.cer_assertion("assert-admin-revoke-authorized")
def test_o_7cc72d4784ea() -> None:
    assert_behavior(
        invoke_boundary_test(f"{CASE_PREFIX}.O_7CC72D4784EA"),
        "FAILURE-O-7CC72D4784EA",
    )
