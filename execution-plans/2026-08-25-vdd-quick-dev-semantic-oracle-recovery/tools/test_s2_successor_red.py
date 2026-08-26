from semantic_oracle import validate_descriptor


def test_rejects_empty_descriptor_argv() -> None:
    accepted, _ = validate_descriptor({"target":"fixture","argv":[],"cwd":".","timeout_seconds":30,"shell":False,"case_source_refs":["A-DESCRIPTOR"],"case_producer_ref":"vdd"})
    assert not accepted, "FAILURE_ID:QD-DESCRIPTOR-BINDING-INCOMPLETE"
