import pytest
from s31_fixture import invoke_s31_boundary


@pytest.mark.cer_assertion("A-AB4321DB8007-1")
@pytest.mark.cer_assertion("A-AB4321DB8007-2")
def test_o_ab4321db8007(tmp_path):
    assert invoke_s31_boundary(tmp_path, "O_AB4321DB8007", "FAILURE-O-AB4321DB8007")
