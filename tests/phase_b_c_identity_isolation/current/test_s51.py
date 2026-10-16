import pytest
from s51_fixture import invoke_s51_boundary


@pytest.mark.cer_assertion("A-E9499880E6EF-1")
@pytest.mark.cer_assertion("A-E9499880E6EF-2")
def test_o_e9499880e6ef(tmp_path):
    assert invoke_s51_boundary(tmp_path, "O_E9499880E6EF", "FAILURE-O-E9499880E6EF")
