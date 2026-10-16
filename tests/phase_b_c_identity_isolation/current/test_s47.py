import pytest

from s47_fixture import assert_behavior, invoke_boundary_test


CASE_PREFIX = "PhaseA.Platform.Tests.PhaseB.Repair.S47BoundaryTests"


@pytest.mark.cer_assertion("A-O-8FFDBFE8DE13-1")
def test_o_8ffdbfe8de13() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_8FFDBFE8DE13")
    assert_behavior(
        result,
        "S47-OBSERVATION O-8FFDBFE8DE13 artifacts-preserved-after-reuse",
        "FAILURE-O-8FFDBFE8DE13",
    )


@pytest.mark.cer_assertion("A-O-B1796B703851-1")
def test_o_b1796b703851() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_B1796B703851")
    assert_behavior(
        result,
        "S47-OBSERVATION O-B1796B703851 populated-legacy-schema-upgraded",
        "FAILURE-O-B1796B703851",
    )


@pytest.mark.cer_assertion("A-O-BAAD0C35FE10-1")
def test_o_baad0c35fe10() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_BAAD0C35FE10")
    assert_behavior(
        result,
        "S47-OBSERVATION O-BAAD0C35FE10 database-reopened-after-restart",
        "FAILURE-O-BAAD0C35FE10",
    )


@pytest.mark.cer_assertion("A-O-F3ECA0548B57-1")
def test_o_f3eca0548b57() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_F3ECA0548B57")
    assert_behavior(
        result,
        "S47-OBSERVATION O-F3ECA0548B57 ownership-preserved-after-reuse",
        "FAILURE-O-F3ECA0548B57",
    )
