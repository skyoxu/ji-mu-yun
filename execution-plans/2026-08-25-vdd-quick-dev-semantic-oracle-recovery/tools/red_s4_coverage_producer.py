from coverage_gate import validate_many_to_many_cover

def test_exact_cover_requires_receipt_observation_assertion() -> None:
    accepted, failure_id = validate_many_to_many_cover([{"acceptance_id":"A-COVER","case_id":"CASE-1","observation_id":"OBS-1"}], {"A-COVER"}, {"OBS-1"})
    assert not accepted and failure_id == "COVERAGE-EVIDENCE-LINEAGE-UNBOUND", f"FAILURE_ID:{failure_id or 'COVERAGE-EVIDENCE-LINEAGE-UNBOUND'}"
