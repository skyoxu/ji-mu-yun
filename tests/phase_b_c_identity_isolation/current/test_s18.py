from pathlib import Path

import pytest

from s18_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_boundary_passes(method_name: str, failure_id: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_passes(result, failure_id)


@pytest.mark.cer_assertion("A-O-A9245A7F9268-1")
def test_o_a9245a7f9268() -> None:
    _assert_boundary_passes("O_A9245A7F9268", "FAILURE-O-A9245A7F9268")


@pytest.mark.cer_assertion("A-O-ACFFD4AF755A-1")
def test_o_acffd4af755a() -> None:
    _assert_boundary_passes("O_ACFFD4AF755A", "FAILURE-O-ACFFD4AF755A")


@pytest.mark.cer_assertion("A-O-3E90E18CC0AD-1")
def test_o_3e90e18cc0ad() -> None:
    _assert_boundary_passes("O_3E90E18CC0AD", "FAILURE-O-3E90E18CC0AD")


@pytest.mark.cer_assertion("A-O-A7A82D9D64AA-1")
def test_o_a7a82d9d64aa() -> None:
    _assert_boundary_passes("O_A7A82D9D64AA", "FAILURE-O-A7A82D9D64AA")


@pytest.mark.cer_assertion("A-AA616-1")
def test_o_aa616f4ea4f8_current_role() -> None:
    _assert_boundary_passes("O_AA616F4EA4F8", "FAILURE-O-AA616F4EA4F8")


@pytest.mark.cer_assertion("A-AA616-2")
def test_o_aa616f4ea4f8_removed_capability_denied() -> None:
    _assert_boundary_passes("O_AA616F4EA4F8", "FAILURE-O-AA616F4EA4F8")
