from pathlib import Path

import pytest

from s76_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-O-2D555B351AEA-1")
def test_o_2d555b351aea() -> None:
    assert_boundary_passes(
        run_boundary_case(REPOSITORY_ROOT, "O_2D555B351AEA"),
        "FAILURE-O-2D555B351AEA",
    )


@pytest.mark.cer_assertion("A-O-6D53742720D9-1")
def test_o_6d53742720d9() -> None:
    assert_boundary_passes(
        run_boundary_case(REPOSITORY_ROOT, "O_6D53742720D9"),
        "FAILURE-O-6D53742720D9",
    )


@pytest.mark.cer_assertion("A-O-E616BEDB47C4-1")
def test_o_e616bedb47c4() -> None:
    assert_boundary_passes(
        run_boundary_case(REPOSITORY_ROOT, "O_E616BEDB47C4"),
        "FAILURE-O-E616BEDB47C4",
    )
