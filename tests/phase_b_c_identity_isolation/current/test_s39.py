from pathlib import Path

import pytest

from s39_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_passes(method_name: str, failure_id: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_passes(result, failure_id)


@pytest.mark.cer_assertion("A-O26-CONFLICTING-OWNER-NOT-ASSIGNED")
def test_o_26eb3fedc908() -> None:
    _assert_boundary_passes("O_26EB3FEDC908", "FAILURE-O-26EB3FEDC908")


@pytest.mark.cer_assertion("A-O9-AMBIGUOUS-RECORD-QUARANTINED")
def test_o_9cc6d75341b4() -> None:
    _assert_boundary_passes("O_9CC6D75341B4", "FAILURE-O-9CC6D75341B4")


@pytest.mark.cer_assertion("A-OC0-ORPHAN-REMAINS-UNASSIGNED")
def test_o_c0dc8313e8fc() -> None:
    _assert_boundary_passes("O_C0DC8313E8FC", "FAILURE-O-C0DC8313E8FC")
