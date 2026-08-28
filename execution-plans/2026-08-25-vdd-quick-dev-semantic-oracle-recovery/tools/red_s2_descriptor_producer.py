from semantic_oracle import validate_descriptor

def test_descriptor_requires_case_sources() -> None:
    accepted, failure_id = validate_descriptor({"target":"runner","argv":["python","-c","pass"],"cwd":".","timeout_seconds":30,"shell":False,"case_source_refs":[],"case_producer_ref":"vdd"})
    assert not accepted and failure_id == "QD-DESCRIPTOR-BINDING-INCOMPLETE", f"FAILURE_ID:{failure_id or 'QD-DESCRIPTOR-BINDING-INCOMPLETE'}"
