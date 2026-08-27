"""S1 behavior RED: complete semantic manifest must be accepted."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import validate_semantic_intent


def test_complete_fr1_fr2_fr10_manifest_is_accepted() -> None:
    intent = {
        "acceptance_ids": ["A-SEMANTIC"], "covers_acceptance_ids": ["A-SEMANTIC"],
        "producer": "vdd", "coverage": "exact-cover", "fixture_class": "positive",
        "taxonomy": ["outcome", "failure_family", "failure_id"], "oracle_id": "semantic-oracle",
        "oracle_class": "contract", "test_selector": "tests/semantic.py", "subject_role": "sut",
        "required_case_roles": ["positive", "negative", "mutation"], "red_failure_family": "semantic-contract-gap",
        "expected_failure_ids": ["VDD-SEMANTIC-MANIFEST-INCOMPLETE"], "green_expected_observations": ["semantic-artifacts.v1.json"],
        "minimum_executed_cases": 3, "independent_judge_required": True,
        "case_source_refs": ["SPEC:FR-1", "SPEC:FR-2", "SPEC:FR-10"], "case_producer_ref": "vdd-semantic-fixture-owner",
        "complexity_class": "complex", "verification_lane": "self-hosted", "context_lookup_required": False,
        "context_lookup_reason": "repository-owned", "minimum_red_scope": "semantic", "upgrade_conditions": "none",
    }
    accepted, failure_id = validate_semantic_intent(intent)
    if not accepted:
        print(f"FAILURE_ID:{failure_id or 'VDD-SEMANTIC-MANIFEST-INCOMPLETE'}")
    assert accepted, "FAILURE_ID:VDD-SEMANTIC-MANIFEST-INCOMPLETE"
