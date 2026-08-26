"""Repository-owned semantic and boundary oracles for the self-hosted plan."""
from __future__ import annotations

from typing import Any


def validate_semantic_intent(value: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(value, dict):
        return False, "VDD-RED-BOUNDARY"
    required = {"acceptance_ids", "producer", "coverage", "fixture_class", "taxonomy"}
    if not required.issubset(value):
        return False, "VDD-RED-BOUNDARY"
    forbidden = {"command", "descriptor", "receipt", "observation", "hash", "failure_id", "executable", "argv"}
    if forbidden.intersection(value):
        return False, "VDD-RED-BOUNDARY"
    if not value["acceptance_ids"] or not value["producer"] or not value["coverage"]:
        return False, "VDD-RED-BOUNDARY"
    if value.get("rollback") not in (None, "deferred"):
        return False, "VDD-RED-BOUNDARY"
    return True, ""


def validate_descriptor(value: dict[str, Any]) -> tuple[bool, str]:
    required = {"target", "argv", "cwd", "timeout_seconds", "shell", "case_source_refs", "case_producer_ref"}
    if not isinstance(value, dict) or not required.issubset(value):
        return False, "QD-DESCRIPTOR-RED"
    if value.get("shell") is not False or not isinstance(value.get("argv"), list) or value.get("timeout_seconds", 0) <= 0:
        return False, "QD-DESCRIPTOR-RED"
    return True, ""


def validate_judge(receipt: dict[str, Any], observation: dict[str, Any]) -> tuple[bool, str]:
    required = {"executor_id", "judge_id", "descriptor_hash", "candidate_hash", "run_id", "exit_code"}
    if not isinstance(receipt, dict) or not required.issubset(receipt):
        return False, "JUDGE-INDEPENDENCE-RED"
    if receipt.get("executor_id") == receipt.get("judge_id") or receipt.get("judge_id") in {"sut", "candidate"}:
        return False, "JUDGE-INDEPENDENCE-RED"
    if not isinstance(observation, dict) or observation.get("run_id") != receipt.get("run_id"):
        return False, "JUDGE-INDEPENDENCE-RED"
    return True, ""


def validate_many_to_many_cover(edges: list[dict[str, Any]], manifest: set[str], observations: set[str]) -> tuple[bool, str]:
    covered: set[str] = set()
    seen_cases: set[str] = set()
    for edge in edges:
        if not isinstance(edge, dict) or not {"acceptance_id", "case_id", "observation_id"}.issubset(edge):
            return False, "COVERAGE-EXACT-COVER-RED"
        if edge["acceptance_id"] not in manifest or edge["observation_id"] not in observations:
            return False, "COVERAGE-EXACT-COVER-RED"
        covered.add(edge["acceptance_id"])
        seen_cases.add(edge["case_id"])
    return (covered == manifest and bool(seen_cases)), ("" if covered == manifest and seen_cases else "COVERAGE-EXACT-COVER-RED")


FALSE_GREEN_IDS = {f"FG-{index:02d}" for index in range(1, 10)}


def validate_promotion(fixtures: list[dict[str, Any]], predecessor_judge: str | None, writer: str) -> tuple[bool, str]:
    ids = {item.get("fixture_id") for item in fixtures if isinstance(item, dict)}
    if ids != FALSE_GREEN_IDS or len(fixtures) != 9 or not predecessor_judge or writer != "coverage-gate":
        return False, "PROMOTION-FALSE-GREEN-RED"
    if any(item.get("blocked") is not True or item.get("corrected_pair_pass") is not True for item in fixtures):
        return False, "PROMOTION-FALSE-GREEN-RED"
    return True, ""
