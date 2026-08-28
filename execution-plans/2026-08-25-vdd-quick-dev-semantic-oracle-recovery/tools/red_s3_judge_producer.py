import artifact_owners
from pathlib import Path

def test_judge_requires_observed_nonzero_execution() -> None:
    try:
        artifact_owners.produce_receipt(Path.cwd())
    except Exception:
        print("FAILURE_ID:JUDGE-INDEPENDENCE-UNPROVEN")
        raise
    raise AssertionError("FAILURE_ID:JUDGE-INDEPENDENCE-UNPROVEN")
