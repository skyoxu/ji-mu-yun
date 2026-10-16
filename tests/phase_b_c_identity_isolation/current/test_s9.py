from pathlib import Path

import pytest

from s9_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_passes(method_name: str, failure_id: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_passes(result, failure_id)


@pytest.mark.cer_assertion("A-O-05CB0734E7E0-1")
def test_o_05cb0734e7e0() -> None:
    _assert_boundary_passes("O_05CB0734E7E0", "FAILURE-O-05CB0734E7E0")


@pytest.mark.cer_assertion("A-O-12B44DD27432-1")
def test_o_12b44dd27432() -> None:
    _assert_boundary_passes("O_12B44DD27432", "FAILURE-O-12B44DD27432")
