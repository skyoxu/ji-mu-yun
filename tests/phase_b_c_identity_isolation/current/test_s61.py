from pathlib import Path

import pytest

from s61_fixture import assert_boundary_observation, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_observation(method_name: str, observation: str, failure_id: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_observation(result, observation, failure_id)


@pytest.mark.cer_assertion("A-O-27A650DB20C0-1")
def test_o_27a650db20c0() -> None:
    _assert_boundary_observation(
        "O_27A650DB20C0",
        "S61-OBSERVATION O-27A650DB20C0 historical-snapshot-manifest-content-hashes-exclusions-and-policy-binding-unchanged",
        "FAILURE-O-27A650DB20C0",
    )


@pytest.mark.cer_assertion("A-O-3584E0AB2B63-1")
def test_o_3584e0ab2b63() -> None:
    _assert_boundary_observation(
        "O_3584E0AB2B63",
        "S61-OBSERVATION O-3584E0AB2B63 bound-policy-excludes-prohibited-content-from-manifest-and-retained-payload",
        "FAILURE-O-3584E0AB2B63",
    )


@pytest.mark.cer_assertion("A-O-4B79BCC985BE-1")
def test_o_4b79bcc985be() -> None:
    _assert_boundary_observation(
        "O_4B79BCC985BE",
        "S61-OBSERVATION O-4B79BCC985BE persisted-before-after-snapshot-comparison-proves-only-new-manifest-uses-new-policy",
        "FAILURE-O-4B79BCC985BE",
    )


@pytest.mark.cer_assertion("A-O-537551CF10EA-1")
def test_o_537551cf10ea() -> None:
    _assert_boundary_observation(
        "O_537551CF10EA",
        "S61-OBSERVATION O-537551CF10EA distinct-policy-version-bindings-retained-for-prior-and-subsequent-snapshots",
        "FAILURE-O-537551CF10EA",
    )


@pytest.mark.cer_assertion("A-OB44C311965F3")
def test_o_b44c311965f3() -> None:
    _assert_boundary_observation(
        "O_B44C311965F3",
        "S61-OBSERVATION O-B44C311965F3 timer-activity-did-not-create-a-snapshot",
        "FAILURE-O-B44C311965F3",
    )
