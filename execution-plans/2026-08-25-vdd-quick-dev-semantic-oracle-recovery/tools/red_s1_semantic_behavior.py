"""S1 RED selector for the currently missing semantic manifest type guard."""
from semantic_oracle import validate_semantic_intent


def test_semantic_acceptance_ids_must_be_a_list() -> None:
    intent = {
        "acceptance_ids": "A-SEMANTIC", "covers_acceptance_ids": "A-SEMANTIC",
        "producer": "vdd", "coverage": "exact-cover", "fixture_class": "positive",
        "taxonomy": ["outcome", "failure_family", "failure_id"], "oracle_id": "semantic-oracle",
        "oracle_class": "contract", "test_selector": "tests/semantic.py", "subject_role": "sut",
        "required_case_roles": ["positive", "negative", "mutation"], "red_failure_family": "semantic-contract-gap",
        "expected_failure_ids": ["VDD-SEMANTIC-MANIFEST-INCOMPLETE"], "green_expected_observations": ["semantic-artifacts.v1.json"],
        "minimum_executed_cases": 3, "independent_judge_required": True,
        "case_source_refs": ["SPEC:FR-1"], "case_producer_ref": "vdd-semantic-fixture-owner",
        "complexity_class": "complex", "verification_lane": "self-hosted", "context_lookup_required": False,
        "context_lookup_reason": "repository-owned", "minimum_red_scope": "semantic", "upgrade_conditions": [],
    }
    accepted, failure = validate_semantic_intent(intent)
    assert not accepted and failure == "VDD-SEMANTIC-MANIFEST-INCOMPLETE", f"FAILURE_ID:{failure or 'VDD-SEMANTIC-MANIFEST-INCOMPLETE'}"
