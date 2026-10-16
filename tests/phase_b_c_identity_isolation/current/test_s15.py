import pytest

from s15_fixture import assert_behavior, invoke_boundary_test


CASE_PREFIX = "PhaseA.Platform.Tests.PhaseB.Repair.S15BoundaryTests"


@pytest.mark.cer_assertion("A-4708-1")
def test_o_4708c4d8efaa() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_4708C4D8EFAA")
    assert_behavior(
        result,
        "S15-OBSERVATION O-4708C4D8EFAA oidc-first-declared-credential-compatibility-without-provider-deployment",
        "FAILURE-O-4708C4D8EFAA",
    )


@pytest.mark.cer_assertion("A-4BA49-1")
def test_o_4ba49cf633bc() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_4BA49CF633BC")
    assert_behavior(
        result,
        "S15-OBSERVATION O-4BA49CF633BC no-password-authentication-system-required",
        "FAILURE-O-4BA49CF633BC",
    )


@pytest.mark.cer_assertion("A-701386-1")
def test_o_701386e2d77d() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_701386E2D77D")
    assert_behavior(
        result,
        "S15-OBSERVATION O-701386E2D77D no-external-provider-deployment-or-runtime-claim",
        "FAILURE-O-701386E2D77D",
    )


@pytest.mark.cer_assertion("A-9FDA-1")
def test_o_9fda0b49e011() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_9FDA0B49E011")
    assert_behavior(
        result,
        "S15-OBSERVATION O-9FDA0B49E011 admin-bearer-not-persisted-as-general-human-browser-credential",
        "FAILURE-O-9FDA0B49E011",
    )
