import pytest

from s2_fixture import invoke_s2_boundary


@pytest.mark.cer_assertion("A-O-26DE8E588B36")
def test_o_26de8e588b36(tmp_path):
    observation = invoke_s2_boundary(tmp_path)
    assert observation["exitCode"] == 0 and observation["outputExists"] and observation["markerPresent"], "FAILURE-O-26DE8E588B36: harmless Windows file operation did not execute through the production runner factory."
