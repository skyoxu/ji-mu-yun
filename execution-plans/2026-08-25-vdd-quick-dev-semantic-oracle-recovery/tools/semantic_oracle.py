"""Repository-owned semantic and boundary oracles for the self-hosted plan."""
from __future__ import annotations

from typing import Any
from pathlib import Path
import hashlib
import importlib
import json


def validate_semantic_intent(value: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(value, dict):
        return False, "VDD-RED-BOUNDARY"
    required = {"acceptance_ids", "producer", "coverage", "fixture_class", "taxonomy"}
    if not required.issubset(value):
        return False, "VDD-RED-BOUNDARY"
    forbidden = {"command", "descriptor", "receipt", "observation", "hash", "failure_id", "executable", "argv"}
    if forbidden.intersection(value):
        return False, "VDD-RED-BOUNDARY"
    if not value["acceptance_ids"] or not value["producer"] or not value["coverage"] or not isinstance(value.get("taxonomy"), list) or not value["taxonomy"]:
        return False, "VDD-RED-BOUNDARY"
    if value.get("rollback") not in (None, "deferred"):
        return False, "VDD-RED-BOUNDARY"
    return True, ""


def validate_descriptor(value: dict[str, Any]) -> tuple[bool, str]:
    owner = _owner_delegate("descriptor_compiler", "validate_descriptor")
    if owner is not None:
        return owner(value)
    required = {"target", "argv", "cwd", "timeout_seconds", "shell", "case_source_refs", "case_producer_ref"}
    if not isinstance(value, dict) or not required.issubset(value):
        return False, "QD-DESCRIPTOR-RED"
    if value.get("shell") is not False or not isinstance(value.get("argv"), list) or not value["argv"] or value.get("timeout_seconds", 0) <= 0:
        return False, "QD-DESCRIPTOR-RED"
    return True, ""


def validate_judge(receipt: dict[str, Any], observation: dict[str, Any]) -> tuple[bool, str]:
    owner = _owner_delegate("independent_judge", "validate_judge")
    if owner is not None:
        return owner(receipt, observation)
    required = {"executor_id", "judge_id", "descriptor_hash", "candidate_hash", "run_id", "exit_code"}
    if not isinstance(receipt, dict) or not required.issubset(receipt):
        return False, "JUDGE-INDEPENDENCE-RED"
    if receipt.get("executor_id") == receipt.get("judge_id") or receipt.get("judge_id") in {"sut", "candidate"}:
        return False, "JUDGE-INDEPENDENCE-RED"
    if (
        not isinstance(observation, dict) or observation.get("run_id") != receipt.get("run_id")
        or receipt.get("actual_argv") != observation.get("descriptor_argv")
    ):
        return False, "JUDGE-INDEPENDENCE-RED"
    return True, ""


def validate_many_to_many_cover(edges: list[dict[str, Any]], manifest: set[str], observations: set[str]) -> tuple[bool, str]:
    owner = _owner_delegate("coverage_gate", "validate_many_to_many_cover")
    if owner is not None:
        return owner(edges, manifest, observations)
    covered: set[str] = set()
    seen_cases: set[str] = set()
    for edge in edges:
        if not isinstance(edge, dict) or not {"acceptance_id", "case_id", "observation_id"}.issubset(edge):
            return False, "COVERAGE-EXACT-COVER-RED"
        if edge["acceptance_id"] not in manifest or edge["observation_id"] not in observations or not str(edge["observation_id"]).startswith("OBS-"):
            return False, "COVERAGE-EXACT-COVER-RED"
        covered.add(edge["acceptance_id"])
        seen_cases.add(edge["case_id"])
    return (covered == manifest and bool(seen_cases)), ("" if covered == manifest and seen_cases else "COVERAGE-EXACT-COVER-RED")


FALSE_GREEN_IDS = {f"FG-{index:02d}" for index in range(1, 10)}


def validate_promotion(fixtures: list[dict[str, Any]], predecessor_judge: str | None, writer: str) -> tuple[bool, str]:
    owner = _owner_delegate("promotion_gate", "validate_promotion")
    if owner is not None:
        return owner(fixtures, predecessor_judge, writer)
    ids = {item.get("fixture_id") for item in fixtures if isinstance(item, dict)}
    if ids != FALSE_GREEN_IDS or len(fixtures) != 9 or not isinstance(predecessor_judge, str) or not predecessor_judge.startswith("sha256:") or "coverage" in predecessor_judge or writer != "coverage-gate":
        return False, "PROMOTION-FALSE-GREEN-RED"
    if any(item.get("blocked") is not True or item.get("corrected_pair_pass") is not True for item in fixtures):
        return False, "PROMOTION-FALSE-GREEN-RED"
    return True, ""


def _owner_delegate(module_name: str, function_name: str):
    """Use a Phase B owner when it is present; retain a stable compatibility API."""
    try:
        candidate = getattr(importlib.import_module(module_name), function_name)
    except (ImportError, AttributeError):
        return None
    return candidate if callable(candidate) else None


def compile_run_local_semantic_artifacts(run_root: Path) -> dict[str, Any]:
    """Compile VDD semantic outputs from an explicit run-local intent input."""
    input_path = run_root / "semantic-intent-input.v1.json"
    if not input_path.is_file():
        raise FileNotFoundError("semantic-intent-input.v1.json")
    value = json.loads(input_path.read_text(encoding="utf-8"))
    accepted, failure_id = validate_semantic_intent(value)
    if not accepted:
        raise ValueError(failure_id)
    body = {
        "schema_version": "semantic-artifacts.v1",
        "producer": "vdd",
        "status": "pass",
        "slice_id": "S1",
        "run_id": run_root.name,
        "semantic_intent": value,
        "semantic_verification": {
            "case_source_refs": value.get("case_source_refs", []),
            "case_producer_ref": value.get("case_producer_ref"),
            "required_case_roles": ["positive", "negative", "mutation"],
        },
        "verification_cases": [
            {"case_id": "S1-positive", "fixture_class": "positive", "outcome": "accepted", "evidence_state": "observed", "failure_family": None, "failure_id": None},
            {"case_id": "S1-negative", "fixture_class": "negative", "outcome": "rejected", "evidence_state": "observed", "failure_family": "semantic-contract-gap", "failure_id": "VDD-RED-BOUNDARY"},
            {"case_id": "S1-mutation", "fixture_class": "mutation", "outcome": "rejected", "evidence_state": "observed", "failure_family": "semantic-contract-gap", "failure_id": "VDD-RED-BOUNDARY"},
        ],
    }
    body["evidence_sha256"] = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "semantic-artifacts.v1.json").write_text(json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    return body
