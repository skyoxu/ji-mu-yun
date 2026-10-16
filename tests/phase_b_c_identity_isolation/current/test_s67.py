from pathlib import Path

import pytest

from s67_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_passes(method_name: str, failure_id: str, observation: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_passes(result, failure_id, observation)


@pytest.mark.cer_assertion("A-O1887-RUNNER-DISPATCH")
def test_o_1887ff4a80d2() -> None:
    _assert_boundary_passes(
        "O_1887FF4A80D2",
        "FAILURE-O-1887FF4A80D2",
        "O-1887FF4A80D2 runner-dispatched-controlled-secret-only",
    )


@pytest.mark.cer_assertion("A-O62-RUNNER-REUSE-GUARD")
def test_o_62bc40d98dbd() -> None:
    _assert_boundary_passes(
        "O_62BC40D98DBD",
        "FAILURE-O-62BC40D98DBD",
        "O-62BC40D98DBD cleanup-failure-blocked-reuse-dispatch",
    )


@pytest.mark.cer_assertion("A-O664-RUNNER-CLEANUP-COMPLETION")
def test_o_664bbd21b5e8() -> None:
    _assert_boundary_passes(
        "O_664BBD21B5E8",
        "FAILURE-O-664BBD21B5E8",
        "O-664BBD21B5E8 completion-cleaned-run-secret",
    )
