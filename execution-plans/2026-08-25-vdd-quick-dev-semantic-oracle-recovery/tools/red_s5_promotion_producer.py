import artifact_owners
from pathlib import Path

def test_promotion_requires_independent_predecessor_judge() -> None:
    try:
        artifact_owners.produce_false_green_fixtures(Path.cwd())
    except Exception:
        print("FAILURE_ID:PROMOTION-FALSE-GREEN-RED")
        raise
    raise AssertionError("FAILURE_ID:PROMOTION-FALSE-GREEN-RED")
