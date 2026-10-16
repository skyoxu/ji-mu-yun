import pytest

from s22_fixture import FAILURE_ID, invoke_s22_boundary


@pytest.mark.cer_assertion("A-O-D6DA22255508-1")
def test_o_d6da22255508(tmp_path) -> None:
    result = invoke_s22_boundary(tmp_path)
    if result.outcome == "Failed":
        if FAILURE_ID not in result.error_message:
            raise RuntimeError("S22 boundary failed outside its bound product assertion")
        print(f"FAILURE_ID:{FAILURE_ID}")
        raise AssertionError(f"{FAILURE_ID}: real snapshot protection boundary did not satisfy the declared behavior")

    observation = result.observation
    behavior_proved = (
        result.outcome == "Passed"
        and observation["keyReference"].startswith("keyref-")
        and observation["mechanism"] == "AES-256-GCM"
        and observation["protectedPayload"] == "true"
        and observation["recovered"] == "true"
    )
    if not behavior_proved:
        print(f"FAILURE_ID:{FAILURE_ID}")
        raise AssertionError(f"{FAILURE_ID}: real protected payload was not recovered through its selected key-reference profile")
