import pytest

from s10_fixture import invoke_s10_boundary


@pytest.mark.cer_assertion("A-O-3E7CE839D9C3-1")
def test_o_3e7ce839d9c3(tmp_path):
    observation = invoke_s10_boundary(tmp_path)

    assert (
        observation["queuedBeforeDisable"]
        and observation["reauthorizationDenied"]
        and observation["queueDrainedAfterDispatch"]
        and not observation["writeLeaseGranted"]
    ), "FAILURE-O-3E7CE839D9C3: disabled-account queued work was dispatched or granted a write lease."
