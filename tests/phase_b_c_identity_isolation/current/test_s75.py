import pytest

from s75_fixture import assert_behavior, invoke_s75_boundary


@pytest.mark.cer_assertion("A-O-AB9213E2F95A-1")
def test_o_ab9213e2f95a(tmp_path) -> None:
    assert_behavior(
        invoke_s75_boundary(tmp_path, "O_AB9213E2F95A"),
        "FAILURE-O-AB9213E2F95A",
    )


@pytest.mark.cer_assertion("A-O-1C96420A7A74-1")
def test_o_1c96420a7a74(tmp_path) -> None:
    assert_behavior(
        invoke_s75_boundary(tmp_path, "O_1C96420A7A74"),
        "FAILURE-O-1C96420A7A74",
    )
