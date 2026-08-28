"""NN+1 promotion gate for the nine false-green fixtures."""
from __future__ import annotations

from typing import Any
import hashlib
import json
from false_green_registry import FIXTURE_REGISTRY

def validate_fixture_observation(observation: dict[str, Any], predecessor_judge: str, variant: str) -> tuple[bool, str]:
    """Validate one observed fixture pair before aggregate promotion."""
    if variant not in {"blocked", "corrected"} or not isinstance(predecessor_judge, str) or not predecessor_judge.startswith("sha256:"):
        return False, "PROMOTION-FALSE-GREEN-RED"
    fixture_id = observation.get("fixture_id")
    spec = FIXTURE_REGISTRY.get(fixture_id)
    if spec is None or observation.get("category") != spec["category"] or observation.get("source_ref") != spec["source_ref"] or observation.get("validator") != spec["validator"]:
        return False, "PROMOTION-FALSE-GREEN-RED"
    if observation.get("predecessor_judge_hash") != predecessor_judge:
        return False, "PROMOTION-FALSE-GREEN-RED"
    for key in ("baseline_hash", "candidate_hash", "coverage_hash", "mutation_hash"):
        if not isinstance(observation.get(key), str) or not observation[key].startswith("sha256:"):
            return False, "PROMOTION-FALSE-GREEN-RED"
    expected_mutation = "sha256:" + hashlib.sha256(json.dumps({"fixture_id": fixture_id, "field": spec["mutation"]}, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if observation["baseline_hash"] == observation["mutation_hash"] or observation["mutation_hash"] != expected_mutation:
        return False, "PROMOTION-FALSE-GREEN-RED"
    if variant == "blocked":
        if observation.get("mutation_applied") is not True or observation.get("failure_id") != spec["failure_id"]:
            return False, "PROMOTION-FALSE-GREEN-RED"
        return False, spec["failure_id"]
    return observation.get("failure_id") is None, "" if observation.get("failure_id") is None else "PROMOTION-FALSE-GREEN-RED"


def validate_promotion(fixtures: list[dict[str, Any]], predecessor_judge: str | None, writer: str) -> tuple[bool, str]:
    expected = {f"FG-{index:02d}" for index in range(1, 10)}
    if writer != "coverage-gate" or not isinstance(predecessor_judge, str) or not predecessor_judge.startswith("sha256:") or "coverage" in predecessor_judge:
        return False, "PROMOTION-FALSE-GREEN-RED"
    if len(fixtures) != 9 or {item.get("fixture_id") for item in fixtures if isinstance(item, dict)} != expected:
        return False, "PROMOTION-FALSE-GREEN-RED"
    if len({item.get("category") for item in fixtures if isinstance(item, dict)}) != 9:
        return False, "PROMOTION-FALSE-GREEN-RED"
    lineage = None
    for item in fixtures:
        spec = FIXTURE_REGISTRY.get(item.get("fixture_id")) if isinstance(item, dict) else None
        if not spec or any(item.get(k) != spec[k] for k in ("category", "source_ref", "validator")) or item.get("expected_failure_id") != spec["failure_id"] or item.get("blocked_failure_id") != spec["failure_id"]:
            return False, "PROMOTION-FALSE-GREEN-RED"
    for item in fixtures:
        spec = FIXTURE_REGISTRY.get(item.get("fixture_id")) if isinstance(item, dict) else None
        if not spec or item.get("category") != spec["category"] or item.get("source_ref") != spec["source_ref"] or item.get("validator") != spec["validator"] or item.get("expected_failure_id") != spec["failure_id"] or item.get("blocked_failure_id") != spec["failure_id"]:
            return False, "PROMOTION-FALSE-GREEN-RED"
        if not item.get("baseline_hash", "").startswith("sha256:") or not item.get("candidate_hash", "").startswith("sha256:") or not item.get("coverage_hash", "").startswith("sha256:") or not item.get("predecessor_judge_hash", "").startswith("sha256:") or not item.get("mutation_hash", "").startswith("sha256:") or item.get("baseline_hash") == item.get("mutation_hash"):
            return False, "PROMOTION-FALSE-GREEN-RED"
        if item.get("baseline_hash") == item.get("mutation_hash") or item.get("blocked_exit_code", 0) == 0 or item.get("corrected_exit_code") != 0:
            return False, "PROMOTION-FALSE-GREEN-RED"
        if item.get("mutation_applied") is not True:
            return False, "PROMOTION-FALSE-GREEN-RED"
        if item["predecessor_judge_hash"] != predecessor_judge:
            return False, "PROMOTION-FALSE-GREEN-RED"
        current_lineage = (item["baseline_hash"], item["candidate_hash"], item["coverage_hash"], item["predecessor_judge_hash"])
        if lineage is None:
            lineage = current_lineage
        elif current_lineage != lineage:
            return False, "PROMOTION-FALSE-GREEN-RED"
    if any(not item.get("blocked_failure_id") for item in fixtures if isinstance(item, dict)):
        return False, "PROMOTION-FALSE-GREEN-RED"
    return all(item.get("blocked") is True and item.get("corrected_pair_pass") is True for item in fixtures), "PROMOTION-FALSE-GREEN-RED"
