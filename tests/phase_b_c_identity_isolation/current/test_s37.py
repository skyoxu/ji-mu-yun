from pathlib import Path

import pytest

from s37_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_case(method_name: str, failure_id: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_passes(result, failure_id)


@pytest.mark.cer_assertion("A-3891AA894A7D-1")
def test_o_3891aa894a7d() -> None:
    _assert_case("O_3891AA894A7D", "FAILURE-O-3891AA894A7D")


@pytest.mark.cer_assertion("A-O-47916B4565D3-1")
def test_o_47916b4565d3() -> None:
    _assert_case("O_47916B4565D3", "FAILURE-O-47916B4565D3")


@pytest.mark.cer_assertion("A-O-565263FA671C-1")
def test_o_565263fa671c() -> None:
    _assert_case("O_565263FA671C", "FAILURE-O-565263FA671C")


@pytest.mark.cer_assertion("A-O-57B8A8A9EC54-UNCHANGED")
@pytest.mark.cer_assertion("A-O-57B8A8A9EC54-DENY-AUTHN")
def test_o_57b8a8a9ec54() -> None:
    _assert_case("O_57B8A8A9EC54", "FAILURE-O-57B8A8A9EC54")


@pytest.mark.cer_assertion("A-O-CE9948D0DD76-SERVER-AUTH")
@pytest.mark.cer_assertion("A-O-CE9948D0DD76-ACCEPT")
def test_o_ce9948d0dd76() -> None:
    _assert_case("O_CE9948D0DD76", "FAILURE-O-CE9948D0DD76")
