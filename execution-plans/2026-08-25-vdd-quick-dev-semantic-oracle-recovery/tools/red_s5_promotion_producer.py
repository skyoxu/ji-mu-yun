from promotion_gate import validate_promotion

def test_promotion_requires_independent_predecessor_judge() -> None:
    accepted, failure_id = validate_promotion([], "sha256:coverage", "coverage-gate")
    assert not accepted and failure_id == "PROMOTION-FALSE-GREEN-RED", f"FAILURE_ID:{failure_id or 'PROMOTION-FALSE-GREEN-RED'}"
