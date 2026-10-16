import pytest

from s58_fixture import assert_behavior, invoke_boundary_test


CASE_PREFIX = "PhaseA.Platform.Tests.PhaseB.Repair.S58BoundaryTests"


@pytest.mark.cer_assertion("A-O-1A7E73D125DE-1")
def test_o_1a7e73d125de() -> None:
    assert_behavior(invoke_boundary_test(f"{CASE_PREFIX}.O_1A7E73D125DE"), "FAILURE-O-1A7E73D125DE")


@pytest.mark.cer_assertion("A-O23FD839F9318-1")
def test_o_23fd839f9318() -> None:
    assert_behavior(invoke_boundary_test(f"{CASE_PREFIX}.O_23FD839F9318"), "FAILURE-O-23FD839F9318")


@pytest.mark.cer_assertion("A-O2FF634492AF9-1")
def test_o_2ff634492af9() -> None:
    assert_behavior(invoke_boundary_test(f"{CASE_PREFIX}.O_2FF634492AF9"), "FAILURE-O-2FF634492AF9")


@pytest.mark.cer_assertion("A-O-A043E6A86196-1")
def test_o_a043e6a86196() -> None:
    assert_behavior(invoke_boundary_test(f"{CASE_PREFIX}.O_A043E6A86196"), "FAILURE-O-A043E6A86196")


@pytest.mark.cer_assertion("A-B5-1")
def test_o_b5f50fba08ee() -> None:
    assert_behavior(invoke_boundary_test(f"{CASE_PREFIX}.O_B5F50FBA08EE"), "FAILURE-O-B5F50FBA08EE")


@pytest.mark.cer_assertion("A-O-BC46A5C1C348-1")
def test_o_bc46a5c1c348() -> None:
    assert_behavior(invoke_boundary_test(f"{CASE_PREFIX}.O_BC46A5C1C348"), "FAILURE-O-BC46A5C1C348")


@pytest.mark.cer_assertion("A-ODA02CE96AA87-1")
def test_o_da02ce96aa87() -> None:
    assert_behavior(invoke_boundary_test(f"{CASE_PREFIX}.O_DA02CE96AA87"), "FAILURE-O-DA02CE96AA87")


@pytest.mark.cer_assertion("A-F0-1")
def test_o_f0e150db52c5() -> None:
    assert_behavior(invoke_boundary_test(f"{CASE_PREFIX}.O_F0E150DB52C5"), "FAILURE-O-F0E150DB52C5")
