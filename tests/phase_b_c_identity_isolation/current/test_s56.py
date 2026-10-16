import pytest

from s56_fixture import assert_behavior, invoke_s56_boundary


@pytest.mark.cer_assertion("A-OCEEBD932678A")
def test_o_ceebd932678a() -> None:
    assert_behavior(
        invoke_s56_boundary("O_CEEBD932678A"),
        "FAILURE-O-CEEBD932678A",
    )
