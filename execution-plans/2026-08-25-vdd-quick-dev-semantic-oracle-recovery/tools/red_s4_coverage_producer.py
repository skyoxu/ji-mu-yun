from coverage_gate import validate_many_to_many_cover

def test_exact_cover_requires_receipt_observation_assertion() -> None:
    edges = [{"acceptance_id":"A-COVER", "case_id":"", "observation_id":"OBS-S4", "assertion":"receipt.exit_code == 0"}]
    accepted, failure = validate_many_to_many_cover(edges, {"A-COVER"}, {"OBS-S4"})
    assert not accepted and failure == "COVERAGE-EVIDENCE-LINEAGE-UNBOUND", f"FAILURE_ID:{failure or 'COVERAGE-EVIDENCE-LINEAGE-UNBOUND'}"
