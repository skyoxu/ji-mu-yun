from pathlib import Path

import pytest

from s17_fixture import assert_boundary_behavior, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary(method_name: str, observation: str, failure_id: str) -> None:
    assert_boundary_behavior(run_boundary_case(REPOSITORY_ROOT, method_name), observation, failure_id)


@pytest.mark.cer_assertion("A-O-37C867864CB9-1")
def test_o_37c867864cb9() -> None:
    _assert_boundary("O_37C867864CB9", "S17-OBSERVATION O-37C867864CB9 directory-switch-failure-preserves-ready-content", "FAILURE-O-37C867864CB9")


@pytest.mark.cer_assertion("A-O-5AB7A7A32FF0-1")
def test_o_5ab7a7a32ff0() -> None:
    _assert_boundary("O_5AB7A7A32FF0", "S17-OBSERVATION O-5AB7A7A32FF0 substitute-root-ownership-and-acl-validated", "FAILURE-O-5AB7A7A32FF0")


@pytest.mark.cer_assertion("A-O-6581E0E2E4B3-1")
def test_o_6581e0e2e4b3() -> None:
    _assert_boundary("O_6581E0E2E4B3", "S17-OBSERVATION O-6581E0E2E4B3 account-scoped-restored-readback-validated", "FAILURE-O-6581E0E2E4B3")


@pytest.mark.cer_assertion("A-O-72D8C7339453-1")
def test_o_72d8c7339453() -> None:
    _assert_boundary("O_72D8C7339453", "S17-OBSERVATION O-72D8C7339453 snapshot-to-controlled-run-stages-measured", "FAILURE-O-72D8C7339453")


@pytest.mark.cer_assertion("A-O-79B69B27B422-1")
def test_o_79b69b27b422() -> None:
    _assert_boundary("O_79B69B27B422", "S17-OBSERVATION O-79B69B27B422 six-required-fixture-kinds-restored", "FAILURE-O-79B69B27B422")


@pytest.mark.cer_assertion("A-O-938C55953B20-1")
def test_o_938c55953b20() -> None:
    _assert_boundary("O_938C55953B20", "S17-OBSERVATION O-938C55953B20 documented-sample-p95-within-thirty-minutes", "FAILURE-O-938C55953B20")


@pytest.mark.cer_assertion("A-AB4E-A1")
def test_o_ab4eae11c49f() -> None:
    _assert_boundary("O_AB4EAE11C49F", "S17-OBSERVATION O-AB4EAE11C49F failed-attempt-staging-is-owned-and-quarantined", "FAILURE-O-AB4EAE11C49F")


@pytest.mark.cer_assertion("A-BEEE-A1")
def test_o_beee8e670283() -> None:
    _assert_boundary("O_BEEE8E670283", "S17-OBSERVATION O-BEEE8E670283 failed-attempt-preserves-previous-ready-workspace", "FAILURE-O-BEEE8E670283")


@pytest.mark.cer_assertion("A-BFDBE4F9C8F9-1")
def test_o_bfdbe4f9c8f9() -> None:
    _assert_boundary("O_BFDBE4F9C8F9", "S17-OBSERVATION O-BFDBE4F9C8F9 directory-switch-leaves-one-ready-or-typed-repair-state", "FAILURE-O-BFDBE4F9C8F9")


@pytest.mark.cer_assertion("A-O-D1E63066A439-1")
def test_o_d1e63066a439() -> None:
    _assert_boundary("O_D1E63066A439", "S17-OBSERVATION O-D1E63066A439 logical-identifiers-use-the-storage-contract", "FAILURE-O-D1E63066A439")


@pytest.mark.cer_assertion("A-E31E0D6B06AD-1")
def test_o_e31e0d6b06ad() -> None:
    _assert_boundary("O_E31E0D6B06AD", "S17-OBSERVATION O-E31E0D6B06AD metadata-boundary-has-no-partial-visible-content", "FAILURE-O-E31E0D6B06AD")


@pytest.mark.cer_assertion("A-E51A39E15CA5-1")
def test_o_e51a39e15ca5() -> None:
    _assert_boundary("O_E51A39E15CA5", "S17-OBSERVATION O-E51A39E15CA5 metadata-boundary-leaves-one-ready-or-typed-repair-state", "FAILURE-O-E51A39E15CA5")
