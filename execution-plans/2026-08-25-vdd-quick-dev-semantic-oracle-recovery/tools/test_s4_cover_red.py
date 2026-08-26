from semantic_oracle import validate_many_to_many_cover

def test_exact_cover_red() -> None:
    accepted, failure_id = validate_many_to_many_cover([], {"A-COVER"}, set())
    assert accepted and not failure_id, "FAILURE_ID:COVERAGE-EXACT-COVER-RED"
