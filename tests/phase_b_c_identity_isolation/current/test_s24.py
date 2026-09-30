import pytest

from s24_fixture import invoke_s24_boundary


def assert_product_behavior(result, failure_id: str, predicate: bool, description: str) -> None:
    if result.outcome == "Failed":
        if failure_id not in result.error_message:
            raise RuntimeError("S24 boundary failed outside its bound product assertion")
        print(f"FAILURE_ID:{failure_id}")
        raise AssertionError(f"{failure_id}: {description}")
    if not predicate:
        print(f"FAILURE_ID:{failure_id}")
        raise AssertionError(f"{failure_id}: {description}")


@pytest.mark.cer_assertion("A-43E456451EF0-READBACK-NO-PLAINTEXT")
def test_o_43e456451ef0(tmp_path) -> None:
    result = invoke_s24_boundary(
        tmp_path,
        "O_43E456451EF0",
        "S24_OBSERVATION:O-43E456451EF0;",
        {"noPlaintextKey"},
    )
    assert_product_behavior(
        result,
        "FAILURE-O-43E456451EF0",
        result.outcome == "Passed" and result.observation["noPlaintextKey"] == "true",
        "real Snapshot readback exposed plaintext key material",
    )


@pytest.mark.cer_assertion("A-O-86F8F24B801C-1")
def test_o_86f8f24b801c(tmp_path) -> None:
    result = invoke_s24_boundary(
        tmp_path,
        "O_86F8F24B801C",
        "S24_OBSERVATION:O-86F8F24B801C;",
        {"blocked", "published", "attemptStatus"},
    )
    assert_product_behavior(
        result,
        "FAILURE-O-86F8F24B801C",
        result.outcome == "Passed"
        and result.observation["blocked"] == "true"
        and result.observation["published"] == "false"
        and result.observation["attemptStatus"] == "Quarantined",
        "real Restore did not block publication when its required key was unavailable",
    )
