from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from rmap_checks import (
    finding,
    validate_commands,
    validate_contract,
    validate_coverage,
    validate_authority_manifest,
    validate_clarification_projection,
    validate_plan_state,
    validate_requirements,
    validate_shadow_registry,
)


def _pointer_parent(document: Any, pointer: str) -> tuple[Any, str]:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.strip("/").split("/")]
    current = document
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current, parts[-1]


def apply_mutations(document: Any, mutations: list[dict[str, Any]]) -> Any:
    result = copy.deepcopy(document)
    for mutation in mutations:
        parent, key = _pointer_parent(result, mutation["path"])
        if mutation["op"] == "replace":
            if isinstance(parent, list):
                parent[int(key)] = mutation["value"]
            else:
                parent[key] = mutation["value"]
        elif mutation["op"] == "add":
            if isinstance(parent, list):
                parent.append(mutation["value"]) if key == "-" else parent.insert(int(key), mutation["value"])
            else:
                parent[key] = mutation["value"]
        elif mutation["op"] == "remove":
            if isinstance(parent, list):
                del parent[int(key)]
            else:
                del parent[key]
        else:
            raise ValueError(f"unsupported mutation op: {mutation['op']}")
    return result


def validate_fixture_document(plan_root: Path, target: str, document: dict[str, Any], data: dict[str, Any]) -> list[dict[str, str]]:
    if target == "contract":
        return validate_contract(plan_root, document, data["requirements"], data["commands"])
    if target == "command_registry":
        return validate_commands(document)
    if target == "plan_state":
        return validate_plan_state(document, data["review_blocker"])
    if target == "review_blocker":
        return validate_plan_state(data["state"], document)
    if target == "authority_manifest":
        return validate_authority_manifest(plan_root, document)
    if target == "clarification_projection":
        return validate_clarification_projection(document)
    if target == "acceptance":
        return validate_requirements(plan_root, data["requirements"], data["quality"], document)
    if target == "requirement_quality":
        return validate_requirements(plan_root, data["requirements"], document, data["acceptance"])
    if target == "shadow":
        return validate_shadow_registry(document)
    if target == "source_coverage":
        requirement_ids = {item["id"] for item in data["requirements"]["requirements"]}
        return validate_coverage(plan_root, document, requirement_ids)
    return [finding("RMAP-STRUCT-FIXTURE", target, "unknown fixture target")]


def evaluate_fixture(plan_root: Path, fixture_id: str, data: dict[str, Any]) -> list[dict[str, str]]:
    cases = data["fixtures"].get("cases", [])
    case = next((item for item in cases if item.get("id") == fixture_id), None)
    if case is None:
        return [finding("RMAP-STRUCT-FIXTURE", fixture_id, "fixture does not exist")]
    base_key = {"contract": "contract", "command_registry": "commands", "plan_state": "state", "review_blocker": "review_blocker", "authority_manifest": "authority_manifest", "clarification_projection": "clarification", "acceptance": "acceptance", "requirement_quality": "quality", "shadow": "shadow", "source_coverage": "coverage"}.get(case.get("target"))
    if base_key is None:
        return [finding("RMAP-STRUCT-FIXTURE", fixture_id, "fixture target is invalid")]
    mutated = apply_mutations(data[base_key], case.get("mutations", []))
    return validate_fixture_document(plan_root, case["target"], mutated, data)


def validate_fixture_suite(plan_root: Path, data: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    cases = data["fixtures"].get("cases")
    if not isinstance(cases, list) or len(cases) < 10:
        return [finding("RMAP-STRUCT-FIXTURE", "fixture-cases", "fixture suite is incomplete")]
    for case in cases:
        observed = evaluate_fixture(plan_root, case["id"], data)
        rules = sorted({item["rule_id"] for item in observed})
        if case.get("expected_valid") is True:
            if observed:
                findings.append(finding("RMAP-STRUCT-FIXTURE", case["id"], f"valid fixture failed: {rules}"))
        elif rules != [case.get("expected_rule")]:
            findings.append(finding("RMAP-STRUCT-FIXTURE", case["id"], f"expected {[case.get('expected_rule')]}, observed {rules}"))
    return findings
