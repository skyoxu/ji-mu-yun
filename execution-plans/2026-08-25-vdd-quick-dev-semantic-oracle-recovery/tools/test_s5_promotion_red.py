from semantic_oracle import validate_promotion

def test_false_green_promotion_red() -> None:
    accepted, failure_id = validate_promotion([], None, "sut")
    assert not accepted and failure_id == "PROMOTION-FALSE-GREEN-RED"
