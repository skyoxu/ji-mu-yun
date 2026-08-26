from pathlib import Path
from semantic_oracle import validate_descriptor

def test_descriptor_boundary_red() -> None:
    accepted, failure_id = validate_descriptor({"target": "runner", "argv": [], "cwd": ".", "timeout_seconds": 30, "shell": True, "case_source_refs": [], "case_producer_ref": "vdd"})
    assert not accepted and failure_id == "QD-DESCRIPTOR-RED"
