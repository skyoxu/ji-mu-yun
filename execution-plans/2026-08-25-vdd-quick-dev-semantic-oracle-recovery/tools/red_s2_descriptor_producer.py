from descriptor_compiler import validate_descriptor

def test_descriptor_requires_semantic_artifact_binding() -> None:
    accepted, failure = validate_descriptor({"target":"runner", "argv":["py"], "cwd":".", "timeout_seconds":30, "shell":False, "case_source_refs":["SPEC:FR-3"], "case_producer_ref":"vdd", "semantic_artifact_ref":{"path":"semantic-artifacts.v1.json", "sha256":"not-a-digest", "producer":"vdd", "slice_id":"S1", "run_id":"RUN-test"}})
    assert not accepted and failure == "QD-DESCRIPTOR-BINDING-INCOMPLETE", f"FAILURE_ID:{failure or 'QD-DESCRIPTOR-BINDING-INCOMPLETE'}"
