from pathlib import Path

import pytest

from s69_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_passes(method_name: str, failure_id: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_passes(result, failure_id)


@pytest.mark.cer_assertion("A-78D7-ID")
def test_o_78d7e0265bd0() -> None:
    _assert_boundary_passes("O_78D7E0265BD0", "FAILURE-O-78D7E0265BD0")


@pytest.mark.cer_assertion("A-8CED-DERIVED")
def test_o_8ced50b4d419() -> None:
    _assert_boundary_passes("O_8CED50B4D419", "FAILURE-O-8CED50B4D419")


@pytest.mark.cer_assertion("A-950-LAST-USE")
def test_o_950a3be6a619() -> None:
    _assert_boundary_passes("O_950A3BE6A619", "FAILURE-O-950A3BE6A619")


@pytest.mark.cer_assertion("A-E637-EXPIRY")
def test_o_e637552cc6b3() -> None:
    _assert_boundary_passes("O_E637552CC6B3", "FAILURE-O-E637552CC6B3")


@pytest.mark.cer_assertion("A-O-4E871043ED9E")
def test_o_4e871043ed9e() -> None:
    _assert_boundary_passes("O_4E871043ED9E", "FAILURE-O-4E871043ED9E")
