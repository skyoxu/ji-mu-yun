import pytest

from s12_fixture import assert_behavior, invoke_boundary_test


CASE_PREFIX = "PhaseA.Platform.Tests.PhaseB.Repair.S12BoundaryTests"


@pytest.mark.cer_assertion("A-O-53F5B5BDADAC-1")
def test_o_53f5b5bdadac() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_53F5B5BDADAC")
    assert_behavior(result, "S12-OBSERVATION O-53F5B5BDADAC fresh-current-schema", "FAILURE-O-53F5B5BDADAC")


@pytest.mark.cer_assertion("A-O-69160595B925-1")
def test_o_69160595b925() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_69160595B925")
    assert_behavior(result, "S12-OBSERVATION O-69160595B925 project-preserved-after-reuse", "FAILURE-O-69160595B925")


@pytest.mark.cer_assertion("A-O-6D67982456AE-1")
def test_o_6d67982456ae() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_6D67982456AE")
    assert_behavior(result, "S12-OBSERVATION O-6D67982456AE fresh-and-legacy-introduced-fields", "FAILURE-O-6D67982456AE")


@pytest.mark.cer_assertion("A-O-7E6C4AC321CE-1")
def test_o_7e6c4ac321ce() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_7E6C4AC321CE")
    assert_behavior(result, "S12-OBSERVATION O-7E6C4AC321CE run-preserved-after-reuse", "FAILURE-O-7E6C4AC321CE")
