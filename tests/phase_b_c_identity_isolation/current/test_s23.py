import json

import pytest

from s23_fixture import invoke_s23_boundary


@pytest.mark.cer_assertion("A-O7E028-QUEUE-REVOKE-DRAIN")
def test_o_7e028cbb46e6(tmp_path):
    observation = invoke_s23_boundary(tmp_path, "O_7E028CBB46E6")
    assert observation["queued"] and observation["denied"] and observation["drained"] and not observation["workRan"], "FAILURE-O-7E028CBB46E6: revoked queued work was not drained before execution."


@pytest.mark.cer_assertion("A-OC8170-QUEUE-DISABLE-LEASE")
def test_o_c81702c3110f(tmp_path):
    observation = invoke_s23_boundary(tmp_path, "O_C81702C3110F")
    assert observation["queued"] and observation["denied"] and not observation["writeLeaseGranted"], "FAILURE-O-C81702C3110F: disabled-account work received a write lease."


@pytest.mark.cer_assertion("A-OE48D-QUEUE-REVOKE-LEASE")
def test_o_e48d8e1001e0(tmp_path):
    observation = invoke_s23_boundary(tmp_path, "O_E48D8E1001E0")
    assert observation["queued"] and observation["denied"] and not observation["writeLeaseGranted"], "FAILURE-O-E48D8E1001E0: revoked-credential work received a write lease."
