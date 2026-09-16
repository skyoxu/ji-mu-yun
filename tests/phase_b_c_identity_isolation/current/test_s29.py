from pathlib import Path

import pytest

from s29_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_passes(method_name: str, failure_id: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_passes(result, failure_id)


@pytest.mark.cer_assertion("A-68-1")
def test_o_68eb3feca634() -> None:
    _assert_boundary_passes("O_68EB3FECA634", "FAILURE-O-68EB3FECA634")


@pytest.mark.cer_assertion("A-O-8252A64854FC-1")
def test_o_8252a64854fc() -> None:
    _assert_boundary_passes("O_8252A64854FC", "FAILURE-O-8252A64854FC")


@pytest.mark.cer_assertion("A-O-B7041EE09EE2-1")
def test_o_b7041ee09ee2() -> None:
    _assert_boundary_passes("O_B7041EE09EE2", "FAILURE-O-B7041EE09EE2")
