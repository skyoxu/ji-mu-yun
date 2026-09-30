import pytest
from s25_fixture import invoke_s25_boundary


@pytest.mark.cer_assertion("A-4367428FF3D3-1")
def test_o_4367428ff3d3(tmp_path):
    assert invoke_s25_boundary(tmp_path, "O_4367428FF3D3", "FAILURE-O-4367428FF3D3")


@pytest.mark.cer_assertion("A-O-A28DE8F2511B-1")
def test_o_a28de8f2511b(tmp_path):
    assert invoke_s25_boundary(tmp_path, "O_A28DE8F2511B", "FAILURE-O-A28DE8F2511B")


@pytest.mark.cer_assertion("A-O-E44EA22B607F-1")
def test_o_e44ea22b607f(tmp_path):
    assert invoke_s25_boundary(tmp_path, "O_E44EA22B607F", "FAILURE-O-E44EA22B607F")
