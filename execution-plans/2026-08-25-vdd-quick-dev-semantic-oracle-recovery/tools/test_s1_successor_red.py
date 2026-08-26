from semantic_oracle import validate_semantic_intent


def test_rejects_empty_taxonomy() -> None:
    accepted, _ = validate_semantic_intent({"acceptance_ids":["A-SEMANTIC"],"producer":"vdd","coverage":"exact-cover","fixture_class":"positive","taxonomy":[]})
    assert not accepted, "FAILURE_ID:VDD-SEMANTIC-ARTIFACT-SET-INCOMPLETE"
