from semantic_oracle import validate_promotion


def test_promotion_rejects_missing_false_green_fixtures() -> None:
    accepted, failure_id = validate_promotion([], None, "sut")
    assert not accepted and failure_id == "PROMOTION-FALSE-GREEN-RED"


def _fixture(index: int) -> dict:
    from false_green_registry import FIXTURE_REGISTRY
    spec = FIXTURE_REGISTRY[f"FG-{index:02d}"]
    return {"fixture_id": f"FG-{index:02d}", "category": spec["category"], "source_ref": spec["source_ref"], "validator": spec["validator"], "expected_failure_id": spec["failure_id"], "blocked_failure_id": spec["failure_id"], "baseline_hash": "sha256:base", "candidate_hash": "sha256:base", "coverage_hash": "sha256:cover", "predecessor_judge_hash": "sha256:judge", "mutation_hash": f"sha256:mutation-{index}", "mutation_applied": True, "blocked": True, "blocked_exit_code": 1, "corrected_pair_pass": True, "corrected_exit_code": 0}


def test_promotion_rejects_lineage_drift_and_forged_failure() -> None:
    fixtures = [_fixture(index) for index in range(1, 10)]
    fixtures[1]["coverage_hash"] = "sha256:other"
    accepted, failure_id = validate_promotion(fixtures, "sha256:judge", "coverage-gate")
    assert not accepted and failure_id == "PROMOTION-FALSE-GREEN-RED"
    fixtures = [_fixture(index) for index in range(1, 10)]
    fixtures[0]["blocked_failure_id"] = "PROMOTION-FALSE-GREEN-RED"
    accepted, failure_id = validate_promotion(fixtures, "sha256:judge", "coverage-gate")
    assert not accepted and failure_id == "PROMOTION-FALSE-GREEN-RED"


def test_promotion_rejects_identical_mutation_pair() -> None:
    fixtures = [_fixture(index) for index in range(1, 10)]
    fixtures[0]["mutation_hash"] = fixtures[0]["baseline_hash"]
    accepted, failure_id = validate_promotion(fixtures, "sha256:judge", "coverage-gate")
    assert not accepted and failure_id == "PROMOTION-FALSE-GREEN-RED"


def test_promotion_rejects_mismatched_predecessor_lineage() -> None:
    fixtures = [_fixture(index) for index in range(1, 10)]
    fixtures[4]["predecessor_judge_hash"] = "sha256:other-judge"
    accepted, failure_id = validate_promotion(fixtures, "sha256:judge", "coverage-gate")
    assert not accepted and failure_id == "PROMOTION-FALSE-GREEN-RED"


def test_promotion_rejects_forged_blocked_failure_without_mutation_witness() -> None:
    from promotion_gate import validate_fixture_observation
    from false_green_registry import FIXTURE_REGISTRY
    spec = FIXTURE_REGISTRY["FG-08"]
    observation = {
        "fixture_id": "FG-08", "category": spec["category"], "source_ref": spec["source_ref"],
        "validator": spec["validator"], "predecessor_judge_hash": "sha256:judge",
        "baseline_hash": "sha256:base", "candidate_hash": "sha256:candidate",
        "coverage_hash": "sha256:coverage", "mutation_hash": "sha256:mutation",
        "failure_id": spec["failure_id"],
    }
    accepted, failure_id = validate_fixture_observation(observation, "sha256:judge", "blocked")
    assert not accepted and failure_id == "PROMOTION-FALSE-GREEN-RED"


def test_promotion_rejects_unbound_mutation_hash() -> None:
    from promotion_gate import validate_fixture_observation
    from false_green_registry import FIXTURE_REGISTRY
    spec = FIXTURE_REGISTRY["FG-09"]
    observation = {
        "fixture_id": "FG-09", "category": spec["category"], "source_ref": spec["source_ref"],
        "validator": spec["validator"], "predecessor_judge_hash": "sha256:judge",
        "baseline_hash": "sha256:base", "candidate_hash": "sha256:candidate",
        "coverage_hash": "sha256:coverage", "mutation_hash": "sha256:arbitrary",
        "mutation_applied": True, "failure_id": spec["failure_id"],
    }
    accepted, failure_id = validate_fixture_observation(observation, "sha256:judge", "blocked")
    assert not accepted and failure_id == "PROMOTION-FALSE-GREEN-RED"
