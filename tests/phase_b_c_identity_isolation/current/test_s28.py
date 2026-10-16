from pathlib import Path

import pytest

from s28_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_passes(method_name: str, failure_id: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_passes(result, failure_id)


@pytest.mark.cer_assertion("A-O-5277C4B77BBF-1")
def test_o_5277c4b77bbf() -> None:
    _assert_boundary_passes("O_5277C4B77BBF", "FAILURE-O-5277C4B77BBF")


@pytest.mark.cer_assertion("A-O-80DBEB1AFBC6-1")
def test_o_80dbeb1afbc6() -> None:
    _assert_boundary_passes("O_80DBEB1AFBC6", "FAILURE-O-80DBEB1AFBC6")


@pytest.mark.cer_assertion("A-O-DB28C97417D0-1")
def test_o_db28c97417d0() -> None:
    _assert_boundary_passes("O_DB28C97417D0", "FAILURE-O-DB28C97417D0")
