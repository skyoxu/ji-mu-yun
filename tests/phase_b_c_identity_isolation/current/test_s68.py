from pathlib import Path

import pytest

from s68_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_passes(method_name: str, failure_id: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_passes(result, failure_id)


@pytest.mark.cer_assertion("A-O-F4B56371054A")
def test_o_f4b56371054a() -> None:
    _assert_boundary_passes("O_F4B56371054A", "FAILURE-O-F4B56371054A")


@pytest.mark.cer_assertion("A-O-FF221ED1B7BF")
def test_o_ff221ed1b7bf() -> None:
    _assert_boundary_passes("O_FF221ED1B7BF", "FAILURE-O-FF221ED1B7BF")
