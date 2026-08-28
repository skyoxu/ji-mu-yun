import artifact_owners
from pathlib import Path

def test_exact_cover_requires_receipt_observation_assertion() -> None:
    try:
        artifact_owners.produce_coverage(Path.cwd())
    except Exception:
        print("FAILURE_ID:COVERAGE-EVIDENCE-LINEAGE-UNBOUND")
        raise
    raise AssertionError("FAILURE_ID:COVERAGE-EVIDENCE-LINEAGE-UNBOUND")
