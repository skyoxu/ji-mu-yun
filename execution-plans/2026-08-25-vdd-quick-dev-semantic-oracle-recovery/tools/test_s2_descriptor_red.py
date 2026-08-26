import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import validate_descriptor

def test_descriptor_boundary_red() -> None:
    valid = {"target": "semantic-runner", "argv": ["--case", "A"], "cwd": ".", "timeout_seconds": 30, "shell": False, "case_source_refs": ["A"], "case_producer_ref": "vdd"}
    assert validate_descriptor(valid) == (True, "")
    accepted, failure_id = validate_descriptor(dict(valid, shell=True))
    assert not accepted and failure_id == "QD-DESCRIPTOR-RED"
