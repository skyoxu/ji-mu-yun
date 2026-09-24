import pytest

from s40_fixture import assert_behavior, invoke_boundary_test


CASE_PREFIX = "PhaseA.Platform.Tests.PhaseB.Repair.S40BoundaryTests"


def assert_case(case: str, observation: str, failure_id: str) -> None:
    assert_behavior(invoke_boundary_test(f"{CASE_PREFIX}.{case}"), observation, failure_id)


@pytest.mark.cer_assertion("A-O-063B424D13AA-EXPLICIT")
@pytest.mark.cer_assertion("A-O-063B424D13AA-STARTS")
def test_o_063b424d13aa() -> None:
    assert_case("O_063B424D13AA", "S40-OBSERVATION O-063B424D13AA explicit-authorized-restore-started-for-snapshot", "FAILURE-O-063B424D13AA")


@pytest.mark.cer_assertion("A-O-2532A1C438CC-1")
def test_o_2532a1c438cc() -> None:
    assert_case("O_2532A1C438CC", "S40-OBSERVATION O-2532A1C438CC run-completion-created-no-restore", "FAILURE-O-2532A1C438CC")


@pytest.mark.cer_assertion("A-O-2B15F2179A84-1")
def test_o_2b15f2179a84() -> None:
    assert_case("O_2B15F2179A84", "S40-OBSERVATION O-2B15F2179A84 eight-authorities-and-current-blocker-recorded", "FAILURE-O-2B15F2179A84")


@pytest.mark.cer_assertion("A-32DDAD281981-1")
def test_o_32ddad281981() -> None:
    assert_case("O_32DDAD281981", "S40-OBSERVATION O-32DDAD281981 restart-reconciled-pre-commit-from-durable-state", "FAILURE-O-32DDAD281981")


@pytest.mark.cer_assertion("A-O-3618B7A10715-1")
def test_o_3618b7a10715() -> None:
    assert_case("O_3618B7A10715", "S40-OBSERVATION O-3618B7A10715 equivalent-request-reused-one-operation", "FAILURE-O-3618B7A10715")


@pytest.mark.cer_assertion("A-56D723EB3077-1")
def test_o_56d723eb3077() -> None:
    assert_case("O_56D723EB3077", "S40-OBSERVATION O-56D723EB3077 operation-states-were-bounded", "FAILURE-O-56D723EB3077")


@pytest.mark.cer_assertion("A-O-682DD1974043-1")
def test_o_682dd1974043() -> None:
    assert_case("O_682DD1974043", "S40-OBSERVATION O-682DD1974043 missing-authority-blocked-before-readback-or-run", "FAILURE-O-682DD1974043")


@pytest.mark.cer_assertion("A-AF06-A1")
def test_o_af06b8605d44() -> None:
    assert_case("O_AF06B8605D44", "S40-OBSERVATION O-AF06B8605D44 bounded-failure-category-and-redacted-envelope", "FAILURE-O-AF06B8605D44")


@pytest.mark.cer_assertion("A-E91B-1")
def test_o_e91bbdcf1838() -> None:
    assert_case("O_E91BBDCF1838", "S40-OBSERVATION O-E91BBDCF1838 restart-reconciled-post-verification-from-durable-state", "FAILURE-O-E91BBDCF1838")


@pytest.mark.cer_assertion("A-F91-EXPLICIT-ENTRY")
def test_o_f91aab48a10c() -> None:
    assert_case("O_F91AAB48A10C", "S40-OBSERVATION O-F91AAB48A10C only-protected-explicit-entry-created-restore", "FAILURE-O-F91AAB48A10C")
