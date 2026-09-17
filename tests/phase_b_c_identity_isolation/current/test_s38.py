from pathlib import Path

import pytest

from s38_fixture import assert_boundary_behavior, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_behavior(method_name: str, failure_id: str) -> None:
    assert_boundary_behavior(run_boundary_case(REPOSITORY_ROOT, method_name), failure_id)


@pytest.mark.cer_assertion("A-O-24FE1B41FD41-1")
def test_o_24fe1b41fd41() -> None:
    _assert_boundary_behavior("O_24FE1B41FD41", "FAILURE-O-24FE1B41FD41")


@pytest.mark.cer_assertion("A-O-31C3B2EDC77B-1")
def test_o_31c3b2edc77b() -> None:
    _assert_boundary_behavior("O_31C3B2EDC77B", "FAILURE-O-31C3B2EDC77B")


@pytest.mark.cer_assertion("assert-redacted-admin-lifecycle-audit")
def test_o_6c84821c3ded() -> None:
    _assert_boundary_behavior("O_6C84821C3DED", "FAILURE-O-6C84821C3DED")
