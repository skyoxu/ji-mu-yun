from pathlib import Path

import pytest

from s32_fixture import assert_boundary_observation, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _assert_case(method_name: str, failure_id: str) -> None:
    assert_boundary_observation(run_boundary_case(REPOSITORY_ROOT, method_name), method_name, failure_id)


@pytest.mark.cer_assertion("A-O24-SAMPLES")
def test_o_24c61509cbfa() -> None:
    _assert_case("O_24C61509CBFA", "FAILURE-O-24C61509CBFA")


@pytest.mark.cer_assertion("A-O318-SIZE")
def test_o_3180cf499b2d() -> None:
    _assert_case("O_3180CF499B2D", "FAILURE-O-3180CF499B2D")


@pytest.mark.cer_assertion("A-O51-ROUTE")
def test_o_51b1e0927330() -> None:
    _assert_case("O_51B1E0927330", "FAILURE-O-51B1E0927330")


@pytest.mark.cer_assertion("A-O548-CLEANUP")
def test_o_54814d965c36() -> None:
    _assert_case("O_54814D965C36", "FAILURE-O-54814D965C36")


@pytest.mark.cer_assertion("A-O-9F7DA3182063-1")
def test_o_9f7da3182063() -> None:
    _assert_case("O_9F7DA3182063", "FAILURE-O-9F7DA3182063")


@pytest.mark.cer_assertion("A-O-A1983E093799-1")
def test_o_a1983e093799() -> None:
    _assert_case("O_A1983E093799", "FAILURE-O-A1983E093799")
