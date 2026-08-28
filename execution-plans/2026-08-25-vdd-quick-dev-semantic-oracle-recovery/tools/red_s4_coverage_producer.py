from coverage_gate import validate_many_to_many_cover

def test_exact_cover_requires_receipt_observation_assertion() -> None:
    ids = {"A-SEMANTIC", "A-DESCRIPTOR", "A-JUDGE", "A-COVER"}
    edges = [{"acceptance_id": aid, "case_id":"CASE-S4", "observation_id":"OBS-S3", "assertion":"unbound assertion"} for aid in ids]
    accepted, failure = validate_many_to_many_cover(edges, ids, {"OBS-S3"})
    assert not accepted and failure == "COVERAGE-EVIDENCE-LINEAGE-UNBOUND", f"FAILURE_ID:{failure or 'COVERAGE-EVIDENCE-LINEAGE-UNBOUND'}"
