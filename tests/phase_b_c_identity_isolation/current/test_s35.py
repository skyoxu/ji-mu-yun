import pytest

from s35_fixture import ASSERTION_ID, FAILURE_ID, run_s35_boundary


@pytest.mark.cer_assertion(ASSERTION_ID)
def test_o_bf44fb067530():
    result = run_s35_boundary()

    if result.outcome != "Passed":
        print(f"FAILURE_ID:{FAILURE_ID}")
    assert result.outcome == "Passed", (
        f"{FAILURE_ID}: production migration created a Snapshot without an explicit request."
    )
    assert result.operation_id, "The completed production migration did not return an operation record."
    assert result.snapshot_inventory_count == 0, (
        f"{FAILURE_ID}: production migration created a Snapshot without an explicit request."
    )
