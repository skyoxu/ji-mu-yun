from semantic_oracle import validate_promotion


def test_promotion_rejects_missing_false_green_fixtures() -> None:
    accepted, failure_id = validate_promotion([], None, "sut")
    assert not accepted and failure_id == "PROMOTION-FALSE-GREEN-RED"
