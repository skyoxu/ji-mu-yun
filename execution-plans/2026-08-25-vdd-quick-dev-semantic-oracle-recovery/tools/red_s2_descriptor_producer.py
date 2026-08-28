from descriptor_compiler import validate_descriptor

def test_descriptor_requires_case_sources() -> None:
    accepted, failure = validate_descriptor({"target":"runner", "argv":["py"], "cwd":".", "timeout_seconds":30, "shell":False, "case_source_refs":["SPEC:FR-3"], "case_producer_ref":"vdd"})
    assert not accepted and failure == "QD-DESCRIPTOR-BINDING-INCOMPLETE", f"FAILURE_ID:{failure or 'QD-DESCRIPTOR-BINDING-INCOMPLETE'}"
