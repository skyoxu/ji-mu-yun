import pytest
from s16_fixture import invoke_s16_boundary


def _run(tmp_path, method, failure_id):
    assert invoke_s16_boundary(tmp_path, method, failure_id)


@pytest.mark.cer_assertion("A-O-BBE96071CA81-1")
def test_o_bbe96071ca81(tmp_path): _run(tmp_path, "O_BBE96071CA81", "FAILURE-O-BBE96071CA81")


@pytest.mark.cer_assertion("A-O-F7C65E43B423-1")
def test_o_f7c65e43b423(tmp_path): _run(tmp_path, "O_F7C65E43B423", "FAILURE-O-F7C65E43B423")
