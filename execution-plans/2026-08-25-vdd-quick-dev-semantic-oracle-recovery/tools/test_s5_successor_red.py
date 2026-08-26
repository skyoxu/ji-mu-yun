from semantic_oracle import validate_promotion


def test_rejects_coverage_hash_as_predecessor_judge() -> None:
    fixtures = [{"fixture_id":f"FG-{index:02d}","blocked":True,"corrected_pair_pass":True} for index in range(1, 10)]
    accepted, _ = validate_promotion(fixtures, "sha256:coverage-artifact", "coverage-gate")
    assert not accepted, "FAILURE_ID:PROMOTION-PREDECESSOR-JUDGE-UNBOUND"
