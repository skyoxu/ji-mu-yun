from semantic_oracle import validate_many_to_many_cover

def test_exact_cover_red() -> None:
    accepted, failure_id = validate_many_to_many_cover([], {"A-COVER"}, set())
    assert not accepted and failure_id == "COVERAGE-EXACT-COVER-RED"
