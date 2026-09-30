import pytest

from s43_fixture import assert_behavior, invoke_boundary_test


CASE_PREFIX = "PhaseA.Platform.Tests.PhaseB.Repair.S43BoundaryTests"


def assert_case(case: str, observation: str, failure_id: str) -> None:
    assert_behavior(invoke_boundary_test(f"{CASE_PREFIX}.{case}"), observation, failure_id)


@pytest.mark.cer_assertion("A-O0645-OS-DENY")
@pytest.mark.cer_assertion("A-O0645-TARGET-UNCHANGED")
def test_o_0645ff2424d5() -> None:
    assert_case("O_0645FF2424D5", "S43-OBSERVATION O-0645FF2424D5 os-denied-and-foreign-workspace-unchanged", "FAILURE-O-0645FF2424D5")


@pytest.mark.cer_assertion("A-O-69EF78FD43BB-OSDENY")
def test_o_69ef78fd43bb() -> None:
    assert_case("O_69EF78FD43BB", "S43-OBSERVATION O-69EF78FD43BB os-denied-and-sibling-project-unchanged", "FAILURE-O-69EF78FD43BB")


@pytest.mark.cer_assertion("A-O-6A5D780FEFBD-OSDENY")
def test_o_6a5d780fefbd() -> None:
    assert_case("O_6A5D780FEFBD", "S43-OBSERVATION O-6A5D780FEFBD os-denied-and-platform-database-unchanged", "FAILURE-O-6A5D780FEFBD")


@pytest.mark.cer_assertion("A-O-C67F01DFFE58-OSDENY")
def test_o_c67f01dffe58() -> None:
    assert_case("O_C67F01DFFE58", "S43-OBSERVATION O-C67F01DFFE58 os-denied-and-secrets-unchanged", "FAILURE-O-C67F01DFFE58")


@pytest.mark.cer_assertion("A-O-C3DB1284259F-OSDENY")
def test_o_c3db1284259f() -> None:
    assert_case("O_C3DB1284259F", "S43-OBSERVATION O-C3DB1284259F os-denied-and-other-account-resource-unchanged", "FAILURE-O-C3DB1284259F")


@pytest.mark.cer_assertion("A-O6E921-AUTHORIZED")
@pytest.mark.cer_assertion("A-O6E921-NO-UNAUTHORIZED")
def test_o_6e9218a1ebbe() -> None:
    assert_case("O_6E9218A1EBBE", "S43-OBSERVATION O-6E9218A1EBBE authorized-present-and-unauthorized-absent", "FAILURE-O-6E9218A1EBBE")


@pytest.mark.cer_assertion("A-O9CFFE-NO-PLATFORM-SECRET")
def test_o_9cffe326beda() -> None:
    assert_case("O_9CFFE326BEDA", "S43-OBSERVATION O-9CFFE326BEDA platform-secret-absent", "FAILURE-O-9CFFE326BEDA")


@pytest.mark.cer_assertion("A-O8F6-CLEANUP")
def test_o_8f6ea73ec04d() -> None:
    assert_case("O_8F6EA73EC04D", "S43-OBSERVATION O-8F6EA73EC04D cancellation-terminated-context-before-secret-probe", "FAILURE-O-8F6EA73EC04D")


@pytest.mark.cer_assertion("A-O-FE73E295BC86-1")
def test_o_fe73e295bc86() -> None:
    assert_case("O_FE73E295BC86", "S43-OBSERVATION O-FE73E295BC86 process-stopped-with-timeout-outcome", "FAILURE-O-FE73E295BC86")


@pytest.mark.cer_assertion("A-OFB45-acl-drift-blocks-runner")
def test_o_fb45bbbe7adf() -> None:
    assert_case("O_FB45BBBE7ADF", "S43-OBSERVATION O-FB45BBBE7ADF all-drifts-blocked-until-protected-repair", "FAILURE-O-FB45BBBE7ADF")


@pytest.mark.cer_assertion("A-O-E42AFE032932-1")
@pytest.mark.cer_assertion("A-O-E42AFE032932-2")
def test_o_e42afe032932() -> None:
    assert_case("O_E42AFE032932", "S43-OBSERVATION O-E42AFE032932 moved-workspace-drift-blocked-until-repair", "FAILURE-O-E42AFE032932")


@pytest.mark.cer_assertion("A-O-DABFD8EDEBEB-1")
@pytest.mark.cer_assertion("A-O-DABFD8EDEBEB-2")
def test_o_dabfd8edebeb() -> None:
    assert_case("O_DABFD8EDEBEB", "S43-OBSERVATION O-DABFD8EDEBEB upgraded-workspace-drift-blocked-until-repair", "FAILURE-O-DABFD8EDEBEB")


@pytest.mark.cer_assertion("A-O-23B38477405D-1")
def test_o_23b38477405d() -> None:
    assert_case("O_23B38477405D", "S43-OBSERVATION O-23B38477405D restored-workspace-runner-blocked-until-repair", "FAILURE-O-23B38477405D")


@pytest.mark.cer_assertion("A-O-3AEA1DFEA790-1")
def test_o_3aea1dfea790() -> None:
    assert_case("O_3AEA1DFEA790", "S43-OBSERVATION O-3AEA1DFEA790 created-workspace-publication-blocked-until-audited-repair", "FAILURE-O-3AEA1DFEA790")


@pytest.mark.cer_assertion("A-O-2B80E38C8384-1")
def test_o_2b80e38c8384() -> None:
    assert_case("O_2B80E38C8384", "S43-OBSERVATION O-2B80E38C8384 restored-workspace-publication-blocked-until-audited-repair", "FAILURE-O-2B80E38C8384")
