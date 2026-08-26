from semantic_oracle import validate_semantic_intent

def test_vdd_semantic_oracle_boundary_red() -> None:
    accepted, failure_id = validate_semantic_intent({"acceptance_ids": [], "producer": "vdd", "coverage": "oracle", "fixture_class": "negative", "taxonomy": []})
    assert accepted and not failure_id, "FAILURE_ID:VDD-RED-BOUNDARY"

def test_semantic_boundary_rejects_missing_acceptance() -> None:
    accepted, failure_id = validate_semantic_intent({"producer": "vdd", "coverage": "oracle", "fixture_class": "negative", "taxonomy": []})
    assert not accepted and failure_id == "VDD-RED-BOUNDARY"
