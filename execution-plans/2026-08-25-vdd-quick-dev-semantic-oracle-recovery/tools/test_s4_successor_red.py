from semantic_oracle import validate_many_to_many_cover


def test_rejects_unbound_observation_edge() -> None:
    accepted, _ = validate_many_to_many_cover([{"acceptance_id":"A-COVER","case_id":"case-1","observation_id":"forged-observation"}], {"A-COVER"}, {"forged-observation"})
    assert not accepted, "FAILURE_ID:COVERAGE-EVIDENCE-LINEAGE-UNBOUND"
