import artifact_owners
from pathlib import Path

def test_descriptor_requires_case_sources() -> None:
    try:
        artifact_owners.produce_descriptor(Path.cwd())
    except Exception:
        print("FAILURE_ID:QD-DESCRIPTOR-BINDING-INCOMPLETE")
        raise
    raise AssertionError("FAILURE_ID:QD-DESCRIPTOR-BINDING-INCOMPLETE")
