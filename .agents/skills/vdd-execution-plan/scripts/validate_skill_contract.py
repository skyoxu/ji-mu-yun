#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path("scripts/skill-contract.json")
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}


def result(findings: list[dict[str, str]], checks: list[str] | None = None) -> dict[str, Any]:
    ordered = sorted(findings, key=lambda item: (item["rule_id"], item["target"], item["message"]))
    return {
        "schema_version": "vdd.skill-validation.v1",
        "ok": not ordered,
        "checks": checks or [],
        "findings": ordered,
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_contract(skill_root: Path) -> dict[str, Any]:
    path = skill_root / CONTRACT_PATH
    data = load_json(path)
    if data.get("schema_version") != "vdd.skill-contract.v1":
        raise ValueError(f"unsupported skill contract schema: {data.get('schema_version')!r}")
    return data


def validate_result_fixture(skill_root: Path, fixture: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    checks = ["result-fields", "result-status", "result-hashes", "result-checks", "result-freshness"]
    try:
        contract = load_contract(skill_root)
        data = load_json(fixture)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return result([finding("VDD-RESULT-PARSE", str(fixture), str(exc))], checks)
    if not isinstance(data, dict):
        return result(
            [finding("VDD-RESULT-PARSE", str(fixture), "validation result must be a JSON object")],
            checks,
        )

    rules = contract["validation_result"]
    for field_name in rules["required_fields"]:
        if field_name not in data:
            findings.append(
                finding("VDD-RESULT-FIELD", str(fixture), f"missing required field: {field_name}")
            )

    if data.get("schema_version") != "vdd.validation-result.v1":
        findings.append(
            finding(
                "VDD-RESULT-SCHEMA",
                str(fixture),
                f"unsupported result schema: {data.get('schema_version')!r}",
            )
        )

    status = data.get("status")
    if status not in rules["allowed_statuses"]:
        findings.append(
            finding("VDD-RESULT-STATUS", str(fixture), f"invalid status: {status!r}")
        )

    for field_name in ("candidate_hash", "current_candidate_hash", "source_hash"):
        value = data.get(field_name)
        if not isinstance(value, str) or not HASH_PATTERN.fullmatch(value):
            findings.append(
                finding("VDD-RESULT-HASH", str(fixture), f"invalid {field_name}: {value!r}")
            )

    if status == "pass" and data.get("candidate_hash") != data.get("current_candidate_hash"):
        findings.append(
            finding(
                "VDD-RESULT-STALE",
                str(fixture),
                "pass result is bound to a stale candidate hash",
            )
        )

    checks_value = data.get("checks")
    if not isinstance(checks_value, list):
        findings.append(finding("VDD-RESULT-CHECK", str(fixture), "checks must be a list"))
    else:
        if status == "pass" and not checks_value:
            findings.append(
                finding("VDD-RESULT-CHECK", str(fixture), "pass result must contain checks")
            )
        for index, check in enumerate(checks_value):
            target = f"{fixture}#checks[{index}]"
            if not isinstance(check, dict):
                findings.append(finding("VDD-RESULT-CHECK", target, "check must be an object"))
                continue
            if not isinstance(check.get("rule_id"), str) or not check.get("rule_id"):
                findings.append(finding("VDD-RESULT-CHECK", target, "check rule_id is required"))
            check_status = check.get("status")
            if check_status not in rules["allowed_check_statuses"]:
                findings.append(
                    finding("VDD-RESULT-CHECK", target, f"invalid check status: {check_status!r}")
                )
            evidence = check.get("evidence")
            if not isinstance(evidence, list) or not all(
                isinstance(item, str) and item for item in evidence
            ):
                findings.append(
                    finding("VDD-RESULT-CHECK", target, "check evidence must be a non-empty string list")
                )
            if status == "pass" and check_status != "pass":
                findings.append(
                    finding("VDD-RESULT-CHECK", target, "pass result cannot contain non-pass checks")
                )

    for list_field in ("authorizes", "does_not_authorize", "diagnostics"):
        if list_field in data and not isinstance(data[list_field], list):
            findings.append(
                finding("VDD-RESULT-FIELD", str(fixture), f"{list_field} must be a list")
            )

    if status == "pass" and not data.get("authorizes"):
        findings.append(
            finding("VDD-RESULT-AUTHORITY", str(fixture), "pass result must name its authorization")
        )
    if status == "pass" and not data.get("does_not_authorize"):
        findings.append(
            finding(
                "VDD-RESULT-AUTHORITY",
                str(fixture),
                "pass result must bound what it does not authorize",
            )
        )

    return result(findings, checks)


def validate_trace(skill_root: Path, fixture: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    checks = ["trace-jsonl", "trace-sequence", "trace-actions", "trace-order"]
    try:
        contract = load_contract(skill_root)
        raw_lines = fixture.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return result([finding("VDD-COMPLIANCE-PARSE", str(fixture), str(exc))], checks)

    events: list[dict[str, Any]] = []
    for line_number, raw in enumerate(raw_lines, 1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            findings.append(
                finding(
                    "VDD-COMPLIANCE-PARSE",
                    f"{fixture}:{line_number}",
                    f"invalid JSON: {exc.msg}",
                )
            )
            continue
        if not isinstance(event, dict):
            findings.append(
                finding(
                    "VDD-COMPLIANCE-PARSE",
                    f"{fixture}:{line_number}",
                    "event must be an object",
                )
            )
            continue
        events.append(event)

    seqs = [event.get("seq") for event in events]
    if any(not isinstance(value, int) or value <= 0 for value in seqs):
        findings.append(
            finding("VDD-COMPLIANCE-SEQUENCE", str(fixture), "seq values must be positive integers")
        )
    elif seqs != sorted(seqs) or len(seqs) != len(set(seqs)):
        findings.append(
            finding(
                "VDD-COMPLIANCE-SEQUENCE",
                str(fixture),
                "seq values must be unique and strictly increasing",
            )
        )

    expected = contract["compliance"]["ordered_steps"]
    actions = [event.get("action") for event in events]
    unknown = [action for action in actions if action not in expected]
    if unknown:
        findings.append(
            finding(
                "VDD-COMPLIANCE-ACTION",
                str(fixture),
                f"unknown actions: {unknown}",
            )
        )
    missing = [action for action in expected if action not in actions]
    duplicates = sorted({action for action in actions if actions.count(action) > 1})
    if missing or duplicates:
        findings.append(
            finding(
                "VDD-COMPLIANCE-ACTION",
                str(fixture),
                f"missing={missing}, duplicates={duplicates}",
            )
        )
    elif actions != expected:
        findings.append(
            finding(
                "VDD-COMPLIANCE-ORDER",
                str(fixture),
                f"expected order {expected}, observed {actions}",
            )
        )

    for index, event in enumerate(events):
        evidence = event.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            findings.append(
                finding(
                    "VDD-COMPLIANCE-EVIDENCE",
                    f"{fixture}#event[{index}]",
                    "event evidence is required",
                )
            )

    return result(findings, checks)


def validate_scenarios(skill_root: Path, fixture: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    checks = ["scenario-schema", "scenario-levels", "scenario-prompts"]
    try:
        contract = load_contract(skill_root)
        data = load_json(fixture)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return result([finding("VDD-SCENARIO-PARSE", str(fixture), str(exc))], checks)

    if data.get("schema_version") != "vdd.skill-scenarios.v1":
        findings.append(
            finding(
                "VDD-SCENARIO-SCHEMA",
                str(fixture),
                f"unsupported scenario schema: {data.get('schema_version')!r}",
            )
        )
    if not isinstance(data.get("task_id"), str) or not data.get("task_id"):
        findings.append(finding("VDD-SCENARIO-FIELD", str(fixture), "task_id is required"))
    if not isinstance(data.get("task_invariant"), str) or not data.get("task_invariant"):
        findings.append(
            finding("VDD-SCENARIO-FIELD", str(fixture), "task_invariant is required")
        )

    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list):
        return result(
            findings + [finding("VDD-SCENARIO-FIELD", str(fixture), "scenarios must be a list")],
            checks,
        )
    levels: list[Any] = []
    for index, scenario in enumerate(scenarios):
        target = f"{fixture}#scenarios[{index}]"
        if not isinstance(scenario, dict):
            findings.append(finding("VDD-SCENARIO-FIELD", target, "scenario must be an object"))
            continue
        levels.append(scenario.get("level"))
        if not isinstance(scenario.get("prompt"), str) or not scenario.get("prompt", "").strip():
            findings.append(finding("VDD-SCENARIO-PROMPT", target, "prompt is required"))

    expected_levels = contract["compliance"]["required_scenario_levels"]
    missing = [level for level in expected_levels if level not in levels]
    unknown = [level for level in levels if level not in expected_levels]
    duplicates = sorted({level for level in levels if levels.count(level) > 1}, key=str)
    if missing or unknown or duplicates:
        findings.append(
            finding(
                "VDD-SCENARIO-LEVEL",
                str(fixture),
                f"missing={missing}, unknown={unknown}, duplicates={duplicates}",
            )
        )
    return result(findings, checks)


def validate_skill(skill_root: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    checks = [
        "required-files",
        "required-headings",
        "required-links",
        "compliance-scenarios-fixture",
        "pass-result-fixture",
        "stale-result-fixture",
        "compliant-trace-fixture",
        "implementation-first-trace-fixture",
    ]
    try:
        contract = load_contract(skill_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return result([finding("VDD-SKILL-CONTRACT", str(skill_root / CONTRACT_PATH), str(exc))], checks)

    for relative in contract["required_files"]:
        path = skill_root / relative
        if not path.is_file():
            findings.append(finding("VDD-SKILL-FILE", relative, "required file is missing"))

    for relative, headings in contract["required_headings"].items():
        path = skill_root / relative
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(finding("VDD-SKILL-UTF8", relative, str(exc)))
            continue
        line_set = set(lines)
        for heading in headings:
            if heading not in line_set:
                findings.append(
                    finding("VDD-SKILL-HEADING", relative, f"missing heading: {heading}")
                )

    for relative, links in contract["required_links"].items():
        path = skill_root / relative
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(finding("VDD-SKILL-UTF8", relative, str(exc)))
            continue
        for link in links:
            if link not in text:
                findings.append(finding("VDD-SKILL-LINK", relative, f"missing reference: {link}"))

    fixture_root = skill_root / "scripts" / "fixtures"
    fixture_expectations = [
        (
            validate_scenarios,
            fixture_root / "compliance-scenarios.json",
            True,
            None,
        ),
        (
            validate_result_fixture,
            fixture_root / "validation-result-pass.json",
            True,
            None,
        ),
        (
            validate_result_fixture,
            fixture_root / "validation-result-stale.json",
            False,
            "VDD-RESULT-STALE",
        ),
        (
            validate_trace,
            fixture_root / "compliance-trace-pass.jsonl",
            True,
            None,
        ),
        (
            validate_trace,
            fixture_root / "compliance-trace-implementation-first.jsonl",
            False,
            "VDD-COMPLIANCE-ORDER",
        ),
    ]
    for validator, fixture, expected_ok, expected_rule in fixture_expectations:
        if not fixture.is_file():
            continue
        fixture_result = validator(skill_root, fixture)
        rule_ids = {item["rule_id"] for item in fixture_result["findings"]}
        if fixture_result["ok"] != expected_ok or (
            expected_rule is not None and expected_rule not in rule_ids
        ):
            findings.append(
                finding(
                    "VDD-SKILL-FIXTURE",
                    str(fixture.relative_to(skill_root)),
                    f"expected ok={expected_ok}, rule={expected_rule}; observed {fixture_result}",
                )
            )

    return result(findings, checks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the vdd-execution-plan Skill contract.")
    parser.add_argument(
        "--skill-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Skill directory containing SKILL.md",
    )
    parser.add_argument("--result-fixture", help="Validate one validation-result JSON fixture")
    parser.add_argument("--scenario-fixture", help="Validate one compliance scenario JSON fixture")
    parser.add_argument("--trace-fixture", help="Validate one compliance JSONL trace")
    args = parser.parse_args(argv)

    skill_root = Path(args.skill_root).resolve()
    if args.result_fixture:
        payload = validate_result_fixture(skill_root, Path(args.result_fixture).resolve())
    elif args.scenario_fixture:
        payload = validate_scenarios(skill_root, Path(args.scenario_fixture).resolve())
    elif args.trace_fixture:
        payload = validate_trace(skill_root, Path(args.trace_fixture).resolve())
    else:
        payload = validate_skill(skill_root)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
