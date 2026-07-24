"""Deterministic package checks for the solo-maintainer VDD Skill."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def finding(rule_id: str, path: str, detail: str) -> dict[str, str]:
    return {"rule_id": rule_id, "path": path, "detail": detail}


def result(findings: list[dict[str, str]], checks: list[str]) -> dict[str, Any]:
    return {"ok": not findings, "checks": checks, "findings": findings}


def load_contract(skill_root: Path) -> dict[str, Any]:
    return load_json(skill_root / "scripts" / "skill-contract.json")


def validate_lifecycle(skill_root: Path, contract: dict[str, Any]) -> list[dict[str, str]]:
    path = skill_root / "references" / "lifecycle-state-contract.json"
    try:
        lifecycle = load_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return [finding("VDD-LIFECYCLE-PARSE", str(path), str(exc))]
    findings: list[dict[str, str]] = []
    if lifecycle.get("states") != contract["lifecycle_states"]:
        findings.append(finding("VDD-LIFECYCLE-STATES", str(path), "states must match the static contract"))
    transitions = lifecycle.get("transitions")
    owners = ["vdd-execution-plan", "maintainer", "quick-dev-tdd-adapter", "run-refactor-implementation-acceptance", "archive-skill"]
    expected_transitions = [
        {"from": contract["lifecycle_states"][index], "to": contract["lifecycle_states"][index + 1], "owner": owner}
        for index, owner in enumerate(owners)
    ]
    if transitions != expected_transitions:
        findings.append(finding("VDD-LIFECYCLE-OWNERS", str(path), "transition owners are invalid"))
    if lifecycle.get("bootstrap_review", {}).get("required_by_default") is not False or lifecycle.get("bootstrap_review", {}).get("publishes_lifecycle_state") is not False:
        findings.append(finding("VDD-LIFECYCLE-BOOTSTRAP", str(path), "Bootstrap must remain optional supplemental evidence"))
    if lifecycle.get("implementation_authorization", {}).get("maintainer_override_allowed") is not True:
        findings.append(finding("VDD-LIFECYCLE-OVERRIDE", str(path), "maintainer override must be allowed"))
    exclusions = lifecycle.get("implementation_authorization", {}).get("does_not_authorize")
    if not isinstance(exclusions, list) or not {"acceptance-passed", "archived", "release"}.issubset(exclusions):
        findings.append(finding("VDD-LIFECYCLE-BOUNDARY", str(path), "implementation authorization must exclude later states"))
    compatibility = lifecycle.get("compatibility_adapter")
    if not isinstance(compatibility, dict) or compatibility.get("accepts_legacy_input") is not True or compatibility.get("emits_legacy_output") is not False:
        findings.append(finding("VDD-LIFECYCLE-COMPATIBILITY", str(path), "legacy compatibility must be read-only"))
    return findings


def validate_profile_cases(skill_root: Path, contract: dict[str, Any]) -> list[dict[str, str]]:
    path = skill_root / "scripts" / "fixtures" / "profile-cases.json"
    try:
        data = load_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return [finding("VDD-PROFILE-CASES-PARSE", str(path), str(exc))]
    findings: list[dict[str, str]] = []
    if data.get("schema_version") != "vdd.profile-cases.v1" or not isinstance(data.get("cases"), list):
        return [finding("VDD-PROFILE-CASES-SCHEMA", str(path), "invalid profile case envelope")]
    cases = data["cases"]
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if sorted(ids) != sorted(contract["required_profile_case_ids"]) or len(ids) != len(cases):
        findings.append(finding("VDD-PROFILE-CASES-COVERAGE", str(path), "case IDs must exactly cover the contract"))
    for case in cases:
        if not isinstance(case, dict) or case.get("profile") not in contract["profiles"]:
            findings.append(finding("VDD-PROFILE-CASES-PROFILE", str(path), "each case must name a known profile"))
            continue
        required = case.get("required", [])
        if not isinstance(required, list) or set(required) != set(contract["profiles"][case["profile"]]):
            findings.append(finding("VDD-PROFILE-CASES-REQUIRED", str(path), f"invalid required controls for {case.get('id')}"))
        forbidden = case.get("forbidden", [])
        if not isinstance(forbidden, list) or set(required) & set(forbidden):
            findings.append(finding("VDD-PROFILE-CASES-FORBIDDEN", str(path), f"invalid forbidden controls for {case.get('id')}"))
    by_id = {case.get("id"): case for case in cases if isinstance(case, dict)}
    expectations = {
        "slice-local-stale": ("expected_invalidation", "slice-and-declared-downstream"),
        "shared-contract-replay": ("expected_invalidation", "targeted-then-terminal-full-replay"),
        "legacy-regression": ("expected_red_path", "legacy-regression-without-fabrication"),
        "optional-review": ("expected_review", "supplemental-and-batched"),
        "standard-no-report": ("expected_report", "optional"),
        "self-hosted-competing-pressure": (
            "expected_pressure_response",
            "stabilize-targeted-then-terminal-replay",
        ),
    }
    for case_id, (field, expected) in expectations.items():
        if by_id.get(case_id, {}).get(field) != expected:
            findings.append(finding("VDD-PROFILE-CASES-BEHAVIOR", str(path), f"{case_id} must declare {field}={expected}"))
    return findings


def validate_generic_source(skill_root: Path, contract: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    sources = sorted(
        path
        for path in skill_root.rglob("*")
        if path.is_file() and path.suffix in {".json", ".md", ".py", ".yaml"}
    )
    for path in sources:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(finding("VDD-PACKAGE-UTF8", str(path), str(exc)))
            continue
        if path.name != "skill-contract.json":
            for term in contract["forbidden_default_terms"]:
                if term in text:
                    findings.append(finding("VDD-DEFAULT-STRICTNESS", str(path), f"forbidden default term: {term}"))
            for pattern in contract["forbidden_live_plan_patterns"]:
                if re.search(pattern, text):
                    findings.append(finding("VDD-GENERIC-HARDCODING", str(path), f"forbidden live-plan pattern: {pattern}"))
    return findings


def validate_skill(skill_root: Path) -> dict[str, Any]:
    checks = ["required-files", "required-headings", "static-lifecycle", "profile-cases", "generic-source"]
    findings: list[dict[str, str]] = []
    try:
        contract = load_contract(skill_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return result([finding("VDD-SKILL-CONTRACT", str(skill_root), str(exc))], checks)
    if set(contract.get("profiles", {})) != {"standard", "resumable", "self-hosted"}:
        findings.append(finding("VDD-PROFILES", "scripts/skill-contract.json", "exactly three profiles are required"))
    for relative in contract["required_files"]:
        if not (skill_root / relative).is_file():
            findings.append(finding("VDD-SKILL-FILE", relative, "required file is missing"))
    for relative, headings in contract["required_headings"].items():
        path = skill_root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for heading in headings:
            if heading not in text:
                findings.append(finding("VDD-SKILL-HEADING", relative, f"missing heading: {heading}"))
    findings.extend(validate_lifecycle(skill_root, contract))
    findings.extend(validate_profile_cases(skill_root, contract))
    findings.extend(validate_generic_source(skill_root, contract))
    return result(findings, checks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the VDD Skill package.")
    parser.add_argument("--skill-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)
    payload = validate_skill(Path(args.skill_root).resolve())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
