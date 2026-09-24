import pytest

from s57_fixture import assert_behavior, invoke_s57_boundary


@pytest.mark.cer_assertion('A-O0181-selection-rejected')
def test_o_0181c140f5dd(tmp_path):
    assert_behavior(
        invoke_s57_boundary(tmp_path, "O_0181C140F5DD"),
        "FAILURE-O-0181C140F5DD",
    )


@pytest.mark.cer_assertion('A-O8E54-advertising-rejected')
def test_o_8e54c403f37e(tmp_path):
    assert_behavior(
        invoke_s57_boundary(tmp_path, "O_8E54C403F37E"),
        "FAILURE-O-8E54C403F37E",
    )


@pytest.mark.cer_assertion('A-OD7E8-current-tier-evidence')
def test_o_d7e8f1ce9703(tmp_path):
    assert_behavior(
        invoke_s57_boundary(tmp_path, "O_D7E8F1CE9703"),
        "FAILURE-O-D7E8F1CE9703",
    )
