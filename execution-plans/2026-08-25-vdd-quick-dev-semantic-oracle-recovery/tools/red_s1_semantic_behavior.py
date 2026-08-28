"""S1 RED selector for the currently missing semantic manifest type guard."""
ACTIVE = {"A-SEMANTIC", "A-DESCRIPTOR", "A-JUDGE", "A-COVER", "A-PROMOTION", "A-TERMINAL", "A-BOUNDARY"}


def test_semantic_verification_covers_active_manifest() -> None:
    verification = {"oracle_id": "A-SEMANTIC", "covers_acceptance_ids": ["A-SEMANTIC"]}
    accepted = set(verification["covers_acceptance_ids"]) == ACTIVE
    assert accepted, "FAILURE_ID:VDD-SEMANTIC-COVERAGE-MISMATCH"
