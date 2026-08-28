from promotion_gate import validate_fixture_observation
import hashlib, json

def test_promotion_requires_independent_predecessor_judge() -> None:
    mutation_hash = "sha256:" + hashlib.sha256(json.dumps({"fixture_id": "FG-01", "field": "case_producer_ref"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    observation = {
        "fixture_id": "FG-01", "category": "semantic-manifest-drift", "source_ref": "FR-2",
        "validator": "semantic", "predecessor_judge_hash": "sha256:predecessor",
        "baseline_hash": "sha256:baseline", "candidate_hash": "sha256:candidate",
        "coverage_hash": "sha256:coverage", "mutation_hash": mutation_hash,
        "mutation_applied": True, "failure_id": None,
    }
    accepted, failure = validate_fixture_observation(observation, "sha256:predecessor", "corrected")
    assert not accepted and failure == "PROMOTION-FALSE-GREEN-RED", f"FAILURE_ID:{failure or 'PROMOTION-FALSE-GREEN-RED'}"
