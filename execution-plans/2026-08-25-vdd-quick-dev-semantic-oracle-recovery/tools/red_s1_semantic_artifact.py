"""Pure S1 semantic behavior cases; no lifecycle or run-root dependencies."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import validate_semantic_intent


def test_semantic_positive_manifest_rejects_missing_fr_fields() -> None:
    intent = {
        "acceptance_ids": ["A-SEMANTIC"], "covers_acceptance_ids": ["A-SEMANTIC"],
        "producer": "vdd", "coverage": "exact-cover", "fixture_class": "positive",
        "taxonomy": ["outcome", "failure_family", "failure_id"],
        "oracle_id": "semantic-oracle", "oracle_class": "contract",
        "test_selector": "tests/semantic.py", "subject_role": "sut",
        "required_case_roles": ["positive", "negative"],
        "red_failure_family": "semantic-contract-gap", "expected_failure_ids": ["VDD-RED-BOUNDARY"],
        "green_expected_observations": ["semantic-artifacts.v1.json"], "minimum_executed_cases": 3,
        "independent_judge_required": True, "case_source_refs": ["SPEC:FR-1"],
        "case_producer_ref": "semantic-fixture-owner", "complexity_class": "complex",
        "verification_lane": "self-hosted", "context_lookup_required": False,
        "context_lookup_reason": "repository-owned", "minimum_red_scope": "semantic",
        "upgrade_conditions": [],
    }
    accepted, failure_id = validate_semantic_intent(intent)
    assert not accepted and failure_id == "VDD-SEMANTIC-ARTIFACT-SET-INCOMPLETE", f"FAILURE_ID:{failure_id or 'VDD-SEMANTIC-ARTIFACT-SET-INCOMPLETE'}"


def test_semantic_negative_rejects_downstream_execution_fields() -> None:
    accepted, failure_id = validate_semantic_intent({"acceptance_ids": ["A-SEMANTIC"], "producer": "vdd", "coverage": "exact-cover", "fixture_class": "negative", "taxonomy": ["semantic"], "executable": "pytest", "argv": []})
    assert not accepted and failure_id == "VDD-RED-BOUNDARY"


def test_semantic_mutation_rejects_missing_taxonomy() -> None:
    accepted, failure_id = validate_semantic_intent({"acceptance_ids": ["A-SEMANTIC"], "producer": "vdd", "coverage": "exact-cover", "fixture_class": "mutation", "taxonomy": []})
    assert not accepted and failure_id == "VDD-RED-BOUNDARY"
