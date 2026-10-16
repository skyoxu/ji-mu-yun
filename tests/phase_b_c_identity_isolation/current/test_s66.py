from pathlib import Path

import pytest

from s66_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_passes(method_name: str, failure_id: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_passes(result, failure_id)


@pytest.mark.cer_assertion("A-O-242D0431B63A-1")
def test_o_242d0431b63a() -> None:
    _assert_boundary_passes("O_242D0431B63A", "FAILURE-O-242D0431B63A")


@pytest.mark.cer_assertion("A-O-4EA9FCB86873-1")
def test_o_4ea9fcb86873() -> None:
    _assert_boundary_passes("O_4EA9FCB86873", "FAILURE-O-4EA9FCB86873")
