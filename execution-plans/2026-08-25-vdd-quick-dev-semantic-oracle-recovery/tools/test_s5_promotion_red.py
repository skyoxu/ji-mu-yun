from semantic_oracle import validate_promotion

def test_false_green_promotion_red() -> None:
    accepted, failure_id = validate_promotion([], None, "sut")
    assert accepted and not failure_id, "FAILURE_ID:PROMOTION-FALSE-GREEN-RED"
