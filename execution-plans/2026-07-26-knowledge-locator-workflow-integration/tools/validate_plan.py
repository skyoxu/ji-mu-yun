"""Validate and publish the Knowledge Locator workflow integration plan."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PLAN_ID = "knowledge-locator-workflow-integration"
PLAN_DIRECTORY = "2026-07-26-knowledge-locator-workflow-integration"
LIFECYCLE = [
    "draft",
    "plan-ready",
    "implementation-authorized",
    "implementation-complete",
    "acceptance-passed",
    "archived",
]
REQUIRED_FILES = (
    "00-index.md",
    "01-requirements-and-acceptance.md",
    "plan-state.v1.json",
    "resume-state.v1.json",
    "authority-manifest.v1.json",
    "implementation-contract.v1.json",
    "command-registry.v1.json",
    "fixtures/protocol-cases.v1.json",
    "fixtures/migration-cases.v1.json",
    "tools/validate_plan.py",
    "tools/validate_all.py",
    "tools/knowledge_workflow_slice_bridge.py",
    "tools/tests/test_validate_plan.py",
    "95-implementation-evolution-and-completion-report.md",
)
JSON_FILES = (
    "plan-state.v1.json",
    "resume-state.v1.json",
    "authority-manifest.v1.json",
    "implementation-contract.v1.json",
    "command-registry.v1.json",
    "fixtures/protocol-cases.v1.json",
    "fixtures/migration-cases.v1.json",
)
EXPECTED_REQUIREMENTS = [f"KWI-{index:03d}" for index in range(1, 24)]
EXPECTED_ACCEPTANCE = [f"KWI-ACC-{index:03d}" for index in range(1, 24)]
EXPECTED_SLICES = [f"RMAP-S{index}" for index in range(8)]
GLOBAL_FORBIDDEN = {
    "logs/phase-a-innernet/**",
    "runtime/phase-a/**",
    "PhaseA.Platform/**",
    "PhaseA.Platform.Tests/**",
    "execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/**",
}
REQUIRED_AUTHORITY = {
    "AGENTS.md",
    "docs/adr/ADR-0037-phase-shared-llm-codex-entrypoints.md",
    "docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md",
    "docs/adr/ADR-0043-vdd-solo-maintainer-clarification-recovery.md",
    "docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md",
}
REQUIRED_UPSTREAM_AUTHORITY = {
    "execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/00-index.md",
    "execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/requirements-ledger.v1.json",
}
REQUIRED_MIGRATION_SOURCES = {
    "execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/schemas/knowledge-locator-request.v1.schema.json",
    "execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/schemas/knowledge-locator-result.v1.schema.json",
}
SUCCESSOR_POLICY_DECISION = (
    "decision-logs/2026-07-27-knowledge-locator-workflow-successor/policy-decision.json"
)
SUCCESSOR_REVIEW_ID = "knowledge-locator-workflow-plan-r3b-20260727"
SUCCESSOR_CHANGE_ID = "knowledge-locator-workflow-repair-v2"
PROTOCOL_CASES = {
    "adapter-owned-envelope": "positive",
    "llm-owned-envelope": "negative",
    "generated-answer-field": "negative",
    "low-confidence-match": "negative",
    "quick-dev-scope-expansion": "negative",
    "bootstrap-post-prepare-growth": "negative",
    "vdd-optional-insufficient": "positive",
    "vdd-required-missing": "negative",
    "high-score-wrong-domain": "negative",
    "keyword-match-insufficient-specificity": "negative",
    "all-candidates-rejected": "negative",
    "index-concurrent-owner-conflict": "negative",
    "index-verified-generation-reuse": "positive",
    "index-unvalidated-staging-publish": "negative",
    "index-non-atomic-pointer-update": "negative",
    "index-failed-build-preserves-lkg": "negative",
}
MIGRATION_CASES = {
    "dated-locator-contract",
    "dated-maintenance-schema-route",
    "legacy-vdd-plan-without-context",
    "legacy-quick-dev-capsule",
    "finalized-bootstrap-run",
    "stale-catalog-refresh",
}


class StrictJsonError(ValueError):
    """Raised when a JSON document is not strict or contains duplicate keys."""


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise StrictJsonError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> Any:
    raise StrictJsonError(f"non-finite JSON number: {value}")


def strict_load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise StrictJsonError("UTF-8 BOM is forbidden")
    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StrictJsonError(str(exc)) from exc
    if not isinstance(value, dict):
        raise StrictJsonError("JSON root must be an object")
    return value


def _finding(rule_id: str, path: str, detail: str) -> dict[str, str]:
    return {"rule_id": rule_id, "path": path, "detail": detail}


def _duplicates(values: Iterable[str]) -> list[str]:
    return sorted(key for key, count in Counter(values).items() if count > 1)


def _safe_relative(value: object, *, allow_dot: bool = False) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    if re.match(r"^[A-Za-z]:/", value) or value.startswith(("/", "//")):
        return False
    if value == ".":
        return allow_dot
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def _prefix(pattern: str) -> str:
    return pattern[:-3].rstrip("/") if pattern.endswith("/**") else pattern.rstrip("/")


def _patterns_overlap(left: str, right: str) -> bool:
    left_prefix = _prefix(left).casefold()
    right_prefix = _prefix(right).casefold()
    return (
        left_prefix == right_prefix
        or left_prefix.startswith(right_prefix + "/")
        or right_prefix.startswith(left_prefix + "/")
    )


def validate_file_format(plan_root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for relative in REQUIRED_FILES:
        path = plan_root / relative
        if not path.is_file():
            findings.append(_finding("KWI-PLAN-REQUIRED-FILE", relative, "required file is missing"))
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            findings.append(_finding("KWI-PLAN-UTF8", relative, "UTF-8 BOM is forbidden"))
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            findings.append(_finding("KWI-PLAN-UTF8", relative, str(exc)))
        if b"\r" in raw:
            findings.append(_finding("KWI-PLAN-LF", relative, "only LF line endings are allowed"))
        if raw and not raw.endswith(b"\n"):
            findings.append(_finding("KWI-PLAN-FINAL-NEWLINE", relative, "final newline is required"))
    return findings


def validate_requirement_coverage(
    requirements_text: str, contract: dict[str, Any]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    rows = re.findall(r"^\|\s*(KWI-\d{3})\s*\|\s*(RMAP-S\d+)\s*\|", requirements_text, re.MULTILINE)
    row_ids = [item[0] for item in rows]
    if row_ids != EXPECTED_REQUIREMENTS or _duplicates(row_ids):
        findings.append(
            _finding(
                "KWI-PLAN-REQUIREMENT-TABLE",
                "01-requirements-and-acceptance.md",
                "requirement rows must contain KWI-001 through KWI-023 exactly once in order",
            )
        )
    slices = contract.get("slices")
    if not isinstance(slices, list):
        return findings + [_finding("KWI-PLAN-SLICES", "implementation-contract.v1.json", "slices must be an array")]
    contract_requirements: list[str] = []
    contract_acceptance: list[str] = []
    row_slice = dict(rows)
    for item in slices:
        if not isinstance(item, dict):
            findings.append(_finding("KWI-PLAN-SLICE-SHAPE", "implementation-contract.v1.json", "each slice must be an object"))
            continue
        slice_id = item.get("slice_id")
        requirement_ids = item.get("requirement_ids")
        acceptance_ids = item.get("acceptance_ids")
        if not isinstance(requirement_ids, list) or not all(isinstance(value, str) for value in requirement_ids):
            findings.append(_finding("KWI-PLAN-REQUIREMENT-COVERAGE", str(slice_id), "requirement_ids must be strings"))
            continue
        if not isinstance(acceptance_ids, list) or not all(isinstance(value, str) for value in acceptance_ids):
            findings.append(_finding("KWI-PLAN-ACCEPTANCE-COVERAGE", str(slice_id), "acceptance_ids must be strings"))
            continue
        contract_requirements.extend(requirement_ids)
        contract_acceptance.extend(acceptance_ids)
        expected_acceptance = [value.replace("KWI-", "KWI-ACC-", 1) for value in requirement_ids]
        if acceptance_ids != expected_acceptance:
            findings.append(_finding("KWI-PLAN-REQUIREMENT-ACCEPTANCE-MAP", str(slice_id), "acceptance IDs must map one-to-one to requirement IDs"))
        for requirement_id in requirement_ids:
            if row_slice.get(requirement_id) != slice_id:
                findings.append(_finding("KWI-PLAN-REQUIREMENT-SLICE", requirement_id, "Markdown and machine slice ownership differ"))
    if sorted(contract_requirements) != EXPECTED_REQUIREMENTS or _duplicates(contract_requirements):
        findings.append(_finding("KWI-PLAN-REQUIREMENT-COVERAGE", "implementation-contract.v1.json", "requirements must be covered exactly once"))
    if sorted(contract_acceptance) != EXPECTED_ACCEPTANCE or _duplicates(contract_acceptance):
        findings.append(_finding("KWI-PLAN-ACCEPTANCE-COVERAGE", "implementation-contract.v1.json", "acceptance IDs must be covered exactly once"))
    consumption_phrases = (
        "Locator results remain immutable and location-only",
        "Accepted decisions require a nonempty `satisfies` set",
        "rejected decisions have an empty `satisfies` set",
        "rather than creating an independent runtime authority artifact",
    )
    if any(phrase not in requirements_text for phrase in consumption_phrases):
        findings.append(_finding("KWI-PLAN-CONSUMPTION-BOUNDARY", "01-requirements-and-acceptance.md", "minimal adapter-owned consumption-decision boundary is incomplete"))
    return findings


def validate_slices(
    contract: dict[str, Any], repository_root: Path
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if contract.get("schema_version") != "kwi.implementation-contract.v1":
        findings.append(_finding("KWI-PLAN-CONTRACT-VERSION", "implementation-contract.v1.json", "unexpected schema version"))
    if contract.get("plan_id") != PLAN_ID or contract.get("profile") != "self-hosted":
        findings.append(_finding("KWI-PLAN-CONTRACT-IDENTITY", "implementation-contract.v1.json", "plan ID or profile is invalid"))
    if contract.get("command_registry") != "command-registry.v1.json":
        findings.append(_finding("KWI-PLAN-COMMAND-OWNER", "implementation-contract.v1.json", "command registry owner is invalid"))
    backend = contract.get("backend")
    if not isinstance(backend, dict) or backend.get("hidden_state") is not False:
        findings.append(_finding("KWI-PLAN-QUICK-BACKEND", "implementation-contract.v1.json", "Quick Dev requires backend.hidden_state=false"))
    protocol_artifacts = contract.get("protocol_artifacts")
    if (
        not isinstance(protocol_artifacts, dict)
        or protocol_artifacts.get("context_layout") != "context/<capsule-id>"
        or protocol_artifacts.get("attempt_layout") != "attempts/<attempt-id>"
    ):
        findings.append(_finding("KWI-PLAN-QUICK-PROTOCOL", "implementation-contract.v1.json", "Quick Dev requires the canonical context and attempt layouts"))
    bridge = contract.get("adapter_bridge")
    if bridge != {"runner": "tools/knowledge_workflow_slice_bridge.py", "protocol": "kwi.knowledge-workflow-tdd-bridge.v1"}:
        findings.append(_finding("KWI-PLAN-QUICK-BRIDGE", "implementation-contract.v1.json", "Quick Dev requires the plan-local staged lifecycle bridge"))
    global_forbidden = contract.get("global_forbidden_changes")
    if not isinstance(global_forbidden, list) or set(global_forbidden) != GLOBAL_FORBIDDEN:
        findings.append(_finding("KWI-PLAN-GLOBAL-FORBIDDEN", "implementation-contract.v1.json", "global forbidden paths are incomplete"))
    slices = contract.get("slices")
    if not isinstance(slices, list):
        return findings + [_finding("KWI-PLAN-SLICES", "implementation-contract.v1.json", "slices must be an array")]
    ids = [item.get("slice_id") for item in slices if isinstance(item, dict)]
    if ids != EXPECTED_SLICES:
        findings.append(_finding("KWI-PLAN-SLICE-ORDER", "implementation-contract.v1.json", "slices must be RMAP-S0 through RMAP-S7 in order"))
    expected_exit = ["slice-ready"] * 6 + ["implementation-candidate", "implementation-complete"]
    for index, item in enumerate(slices):
        if not isinstance(item, dict):
            continue
        slice_id = item.get("slice_id", f"slice-{index}")
        expected_dependency = [] if index == 0 else [f"RMAP-S{index - 1}"]
        if item.get("depends_on") != expected_dependency:
            findings.append(_finding("KWI-PLAN-SLICE-DEPENDENCY", str(slice_id), f"depends_on must equal {expected_dependency}"))
        if index < len(expected_exit) and item.get("exit_predicate") != expected_exit[index]:
            findings.append(_finding("KWI-PLAN-SLICE-EXIT", str(slice_id), f"exit predicate must be {expected_exit[index]}"))
        forbidden = item.get("forbidden_changes")
        if not isinstance(forbidden, list) or not GLOBAL_FORBIDDEN.issubset(set(forbidden)):
            findings.append(_finding("KWI-PLAN-SLICE-FORBIDDEN", str(slice_id), "slice must include every global forbidden path"))
            forbidden = []
        allowed = item.get("allowed_changes")
        allowed_paths: list[str] = []
        if not isinstance(allowed, dict) or set(allowed) != {"production", "tests", "documentation"}:
            findings.append(_finding("KWI-PLAN-ALLOWED-SHAPE", str(slice_id), "allowed_changes must contain production, tests, and documentation"))
        else:
            for group, values in allowed.items():
                if not isinstance(values, list) or not all(_safe_relative(value) for value in values):
                    findings.append(_finding("KWI-PLAN-ALLOWED-PATH", str(slice_id), f"invalid {group} path"))
                    continue
                allowed_paths.extend(values)
        for allowed_path in allowed_paths:
            for forbidden_path in forbidden:
                if _patterns_overlap(allowed_path, forbidden_path):
                    findings.append(_finding("KWI-PLAN-BOUNDARY-OVERLAP", str(slice_id), f"allowed path overlaps forbidden path: {allowed_path}"))
        snapshots = item.get("execution_snapshot_paths")
        if not isinstance(snapshots, list) or not snapshots:
            findings.append(_finding("KWI-PLAN-SNAPSHOT", str(slice_id), "at least one execution snapshot path is required"))
        else:
            for snapshot in snapshots:
                if not _safe_relative(snapshot) or "*" in snapshot:
                    findings.append(_finding("KWI-PLAN-SNAPSHOT-PATH", str(slice_id), f"invalid snapshot path: {snapshot}"))
                elif not (repository_root / snapshot).is_file():
                    findings.append(_finding("KWI-PLAN-SNAPSHOT-MISSING", str(slice_id), f"snapshot source is missing: {snapshot}"))
        for field in ("execution_read_set", "dependency_closure"):
            values = item.get(field)
            if not isinstance(values, list) or not values or not all(_safe_relative(value) for value in values):
                findings.append(_finding("KWI-PLAN-READ-BOUNDARY", str(slice_id), f"{field} must contain safe repository-relative paths"))
        tdd = item.get("tdd")
        if not isinstance(tdd, dict):
            findings.append(_finding("KWI-PLAN-TDD", str(slice_id), "TDD contract is missing"))
            continue
        red, green, refactor = tdd.get("red"), tdd.get("green"), tdd.get("refactor")
        legacy_red = (
            slice_id in {"RMAP-S0", "RMAP-S1", "RMAP-S2", "RMAP-S3", "RMAP-S4", "RMAP-S5", "RMAP-S6", "RMAP-S7"}
            and isinstance(red, dict)
            and red.get("mode") == "legacy-regression"
            and red.get("expected_exit") == "zero"
            and bool(red.get("test_selector"))
            and bool(red.get("expected_failure_ids"))
        )
        negative_red = (
            isinstance(red, dict)
            and red.get("expected_exit") == "nonzero"
            and not red.get("mode")
            and bool(red.get("test_selector"))
            and bool(red.get("expected_failure_ids"))
        )
        if not (legacy_red or negative_red):
            findings.append(_finding("KWI-PLAN-TDD-RED", str(slice_id), "RED must name a negative command, selector, and failure IDs"))
        if not isinstance(green, dict) or green.get("expected_exit") != "zero":
            findings.append(_finding("KWI-PLAN-TDD-GREEN", str(slice_id), "GREEN must require exit zero"))
        invocations = refactor.get("invocations") if isinstance(refactor, dict) else None
        if not isinstance(invocations, list) or not invocations:
            findings.append(_finding("KWI-PLAN-TDD-REFACTOR", str(slice_id), "refactor invocations are required"))
        if not isinstance(item.get("post_refactor_command_id"), str):
            findings.append(_finding("KWI-PLAN-TDD-TERMINAL", str(slice_id), "post-refactor command is required"))
    rmap_s2 = next((item for item in slices if isinstance(item, dict) and item.get("slice_id") == "RMAP-S2"), None)
    rmap_s2_refactor = rmap_s2.get("tdd", {}).get("refactor", {}).get("invocations", []) if isinstance(rmap_s2, dict) else []
    if "index-publication-test" not in {
        item.get("command_id") for item in rmap_s2_refactor if isinstance(item, dict)
    }:
        findings.append(_finding("KWI-PLAN-INDEX-GUARD", "RMAP-S2", "the index-writing slice must run the concurrency, atomic publication and LKG guard"))
    terminal = contract.get("terminal_validation")
    if not isinstance(terminal, dict) or terminal.get("command_id") != "knowledge-workflow-terminal" or terminal.get("required_slice") != "RMAP-S7" or terminal.get("authorizes") != ["implementation-complete"]:
        findings.append(_finding("KWI-PLAN-TERMINAL", "implementation-contract.v1.json", "terminal validation ownership is invalid"))
    return findings


def _command_references(contract: dict[str, Any]) -> list[str]:
    references: list[str] = []
    for item in contract.get("slices", []):
        if not isinstance(item, dict):
            continue
        tdd = item.get("tdd", {})
        for stage in ("red", "green"):
            value = tdd.get(stage, {}) if isinstance(tdd, dict) else {}
            if isinstance(value, dict) and isinstance(value.get("command_id"), str):
                references.append(value["command_id"])
        refactor = tdd.get("refactor", {}) if isinstance(tdd, dict) else {}
        for invocation in refactor.get("invocations", []) if isinstance(refactor, dict) else []:
            if isinstance(invocation, dict) and isinstance(invocation.get("command_id"), str):
                references.append(invocation["command_id"])
        if isinstance(item.get("post_refactor_command_id"), str):
            references.append(item["post_refactor_command_id"])
    terminal = contract.get("terminal_validation")
    if isinstance(terminal, dict) and isinstance(terminal.get("command_id"), str):
        references.append(terminal["command_id"])
    return references


def validate_commands(
    registry: dict[str, Any], contract: dict[str, Any]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if registry.get("schema_version") != "kwi.command-registry.v1":
        findings.append(_finding("KWI-PLAN-COMMAND-VERSION", "command-registry.v1.json", "unexpected schema version"))
    commands = registry.get("commands")
    if not isinstance(commands, list):
        return findings + [_finding("KWI-PLAN-COMMANDS", "command-registry.v1.json", "commands must be an array")]
    ids = [item.get("id") for item in commands if isinstance(item, dict)]
    if len(ids) != len(commands) or any(not isinstance(value, str) or not value for value in ids) or _duplicates(ids):
        findings.append(_finding("KWI-PLAN-COMMAND-ID", "command-registry.v1.json", "command IDs must be unique nonempty strings"))
    for item in commands:
        if not isinstance(item, dict):
            continue
        command_id = str(item.get("id"))
        if item.get("shell") is not False:
            findings.append(_finding("KWI-PLAN-COMMAND-SHELL", command_id, "shell must be false"))
        if item.get("cwd") != {"type": "repo_path", "value": "."}:
            findings.append(_finding("KWI-PLAN-COMMAND-CWD", command_id, "cwd must be the contained repository root"))
        if not isinstance(item.get("executable"), str) or not item.get("executable"):
            findings.append(_finding("KWI-PLAN-COMMAND-EXECUTABLE", command_id, "executable is required"))
        timeout = item.get("timeout_seconds")
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0 or timeout > 3600:
            findings.append(_finding("KWI-PLAN-COMMAND-TIMEOUT", command_id, "timeout must be between 1 and 3600 seconds"))
        argv = item.get("argv")
        if not isinstance(argv, list) or not argv:
            findings.append(_finding("KWI-PLAN-COMMAND-ARGV", command_id, "argv must be a nonempty array"))
            continue
        for argument in argv:
            if isinstance(argument, str):
                if re.match(r"^[A-Za-z]:[\\/]", argument) or argument.startswith(("/", "\\\\")):
                    findings.append(_finding("KWI-PLAN-COMMAND-PORTABILITY", command_id, f"absolute argument is forbidden: {argument}"))
                continue
            if not isinstance(argument, dict) or set(argument) != {"type", "value"}:
                findings.append(_finding("KWI-PLAN-COMMAND-PLACEHOLDER", command_id, "placeholder must contain only type and value"))
                continue
            if argument.get("type") not in {"plan_path", "repo_path", "run_path"} or not _safe_relative(argument.get("value"), allow_dot=True):
                findings.append(_finding("KWI-PLAN-COMMAND-PLACEHOLDER", command_id, "placeholder path is not contained"))
    registered = {value for value in ids if isinstance(value, str)}
    missing = sorted(set(_command_references(contract)) - registered)
    if missing:
        findings.append(_finding("KWI-PLAN-COMMAND-REFERENCE", "implementation-contract.v1.json", f"unregistered commands: {missing}"))
    by_id = {item.get("id"): item for item in commands if isinstance(item, dict)}
    for slice_item in contract.get("slices", []):
        if not isinstance(slice_item, dict):
            continue
        red = slice_item.get("tdd", {}).get("red", {})
        if not isinstance(red, dict):
            continue
        command = by_id.get(red.get("command_id"))
        selector = red.get("test_selector")
        argv = command.get("argv", []) if isinstance(command, dict) else []
        if isinstance(selector, str) and selector not in argv:
            findings.append(_finding("KWI-PLAN-RED-SELECTOR", str(slice_item.get("slice_id")), "registered RED command must contain the declared test selector"))
    quick_contract = by_id.get("quick-dev-contract")
    expected_contract_argument = {"type": "plan_path", "value": "implementation-contract.v1.json"}
    if not isinstance(quick_contract, dict) or quick_contract.get("argv", [])[-1:] != [expected_contract_argument]:
        findings.append(_finding("KWI-PLAN-QUICK-CONTRACT-COMMAND", "quick-dev-contract", "Quick Dev contract validation must receive the current plan contract"))
    terminal_command = by_id.get("knowledge-workflow-terminal")
    if not isinstance(terminal_command, dict) or terminal_command.get("timeout_seconds", 901) > 900:
        findings.append(_finding("KWI-PLAN-BOOTSTRAP-PREFLIGHT-TIMEOUT", "knowledge-workflow-terminal", "Bootstrap preflight commands must not exceed 900 seconds"))
    index_guard = by_id.get("index-publication-test")
    expected_index_selector = "test_index_build_concurrency_atomic_publish_and_lkg_recovery"
    if (
        not isinstance(index_guard, dict)
        or index_guard.get("argv", [])[-2:] != ["-k", expected_index_selector]
    ):
        findings.append(_finding("KWI-PLAN-INDEX-GUARD-COMMAND", "index-publication-test", "RMAP-S2 must register the exact index publication guard"))
    return findings


def validate_protocol_fixtures(value: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    cases = value.get("cases")
    if value.get("schema_version") != "kwi.protocol-cases.v1" or not isinstance(cases, list):
        return [_finding("KWI-PLAN-PROTOCOL-FIXTURE", "fixtures/protocol-cases.v1.json", "invalid fixture envelope")]
    by_id = {item.get("case_id"): item for item in cases if isinstance(item, dict) and isinstance(item.get("case_id"), str)}
    ids = [item.get("case_id") for item in cases if isinstance(item, dict)]
    if len(ids) != len(cases) or set(ids) != set(PROTOCOL_CASES) or _duplicates([str(item) for item in ids]):
        findings.append(_finding("KWI-PLAN-PROTOCOL-COVERAGE", "fixtures/protocol-cases.v1.json", "protocol case IDs must exactly match the consumed cases"))
    for case_id, expected_kind in PROTOCOL_CASES.items():
        item = by_id.get(case_id)
        if not isinstance(item, dict) or item.get("kind") != expected_kind:
            findings.append(_finding("KWI-PLAN-PROTOCOL-KIND", case_id, f"case must be {expected_kind}"))
        elif expected_kind == "negative" and not isinstance(item.get("failure_code"), str):
            findings.append(_finding("KWI-PLAN-PROTOCOL-FAILURE", case_id, "negative case requires a failure code"))
    llm_case = by_id.get("llm-owned-envelope", {})
    if llm_case.get("consumer") != "locator" or llm_case.get("expected") != "blocked" or llm_case.get("failure_code") != "KWI-CONTRACT-LLM-OWNER":
        findings.append(_finding("KWI-PLAN-LLM-ENVELOPE", "llm-owned-envelope", "LLM-owned trusted envelopes must be blocked"))
    quick_case = by_id.get("quick-dev-scope-expansion", {})
    if quick_case.get("consumer") != "quick-dev" or quick_case.get("expected") != "vdd-repair" or quick_case.get("failure_code") != "KWI-QUICK-SCOPE-EXPANSION" or not {"path-expansion", "decision-reclassification"}.issubset(set(quick_case.get("covers", []))):
        findings.append(_finding("KWI-PLAN-QUICK-SCOPE", "quick-dev-scope-expansion", "Quick Dev expansion must route to VDD repair"))
    bootstrap_case = by_id.get("bootstrap-post-prepare-growth", {})
    if not {"context-growth", "decision-change"}.issubset(set(bootstrap_case.get("covers", []))):
        findings.append(_finding("KWI-PLAN-BOOTSTRAP-DECISION-FREEZE", "bootstrap-post-prepare-growth", "Bootstrap must freeze consumption decisions with Artifact View"))
    wrong_domain = by_id.get("high-score-wrong-domain", {})
    if wrong_domain.get("candidate_score") != "above-threshold" or wrong_domain.get("semantic_fit") is not False or wrong_domain.get("expected") != "rejected-not-counted" or wrong_domain.get("failure_code") != "KWI-CONSUMPTION-WRONG-DOMAIN":
        findings.append(_finding("KWI-PLAN-CONSUMPTION-WRONG-DOMAIN", "high-score-wrong-domain", "a high score cannot override wrong-domain rejection"))
    insufficient = by_id.get("keyword-match-insufficient-specificity", {})
    if insufficient.get("candidate_score") != "above-threshold" or insufficient.get("semantic_fit") is not False or insufficient.get("expected") != "rejected-not-counted" or insufficient.get("failure_code") != "KWI-CONSUMPTION-INSUFFICIENT-SPECIFICITY":
        findings.append(_finding("KWI-PLAN-CONSUMPTION-SPECIFICITY", "keyword-match-insufficient-specificity", "keyword overlap cannot satisfy a context class without semantic specificity"))
    all_rejected = by_id.get("all-candidates-rejected", {})
    if all_rejected.get("required_module") is not True or all_rejected.get("accepted_count") != 0 or all_rejected.get("expected") != "draft" or all_rejected.get("failure_code") != "KWI-CONSUMPTION-REQUIRED-UNCOVERED":
        findings.append(_finding("KWI-PLAN-CONSUMPTION-ALL-REJECTED", "all-candidates-rejected", "an all-rejected required module must remain uncovered"))
    concurrent = by_id.get("index-concurrent-owner-conflict", {})
    lock_keys = concurrent.get("lock_key_covers")
    lock_owner = concurrent.get("lock_owner_covers")
    if (
        not isinstance(lock_keys, list)
        or not {"lifecycle_identity", "domain", "source_snapshot", "policy_revision"}.issubset(set(lock_keys))
        or not isinstance(lock_owner, list)
        or not {"pid", "process_creation_identity", "token", "acquired_at", "generation"}.issubset(set(lock_owner))
        or concurrent.get("expected") != "blocked"
        or concurrent.get("failure_code") != "KWI-INDEX-LOCK-CONFLICT"
    ):
        findings.append(_finding("KWI-PLAN-INDEX-LOCK", "index-concurrent-owner-conflict", "concurrent index builds require a complete lock key and live-owner identity"))
    reuse = by_id.get("index-verified-generation-reuse", {})
    if reuse.get("validated_generation") is not True or reuse.get("same_snapshot") is not True or reuse.get("expected") != "reuse-without-write":
        findings.append(_finding("KWI-PLAN-INDEX-REUSE", "index-verified-generation-reuse", "only an already validated exact-snapshot generation may be reused"))
    staging = by_id.get("index-unvalidated-staging-publish", {})
    validation_checks = staging.get("validation_checks")
    if (
        not isinstance(validation_checks, list)
        or not {"schema", "composition", "hash", "evaluation", "contamination"}.issubset(set(validation_checks))
        or staging.get("all_checks_passed") is not False
        or staging.get("expected") != "blocked"
        or staging.get("failure_code") != "KWI-INDEX-STAGING-UNVALIDATED"
    ):
        findings.append(_finding("KWI-PLAN-INDEX-STAGING", "index-unvalidated-staging-publish", "unvalidated staging generations must not publish"))
    pointer = by_id.get("index-non-atomic-pointer-update", {})
    pointer_names = pointer.get("pointer_names")
    if (
        not isinstance(pointer_names, list)
        or set(pointer_names) != {"current.json", "last-known-good.json"}
        or pointer.get("write_mode") != "in-place"
        or pointer.get("expected") != "blocked"
        or pointer.get("failure_code") != "KWI-INDEX-POINTER-NONATOMIC"
    ):
        findings.append(_finding("KWI-PLAN-INDEX-ATOMIC", "index-non-atomic-pointer-update", "index pointers require flush and atomic replacement"))
    failed = by_id.get("index-failed-build-preserves-lkg", {})
    if (
        failed.get("build_status") != "failed"
        or failed.get("pointer_advanced") is not False
        or failed.get("failed_evidence") != "sidecar-preserved"
        or failed.get("recovery") != "last-known-good"
        or failed.get("expected") != "lkg-preserved"
        or failed.get("failure_code") != "KWI-INDEX-BUILD-FAILED"
    ):
        findings.append(_finding("KWI-PLAN-INDEX-LKG", "index-failed-build-preserves-lkg", "failed builds must preserve sidecar evidence and the previous LKG"))
    return findings


def validate_migration_fixtures(value: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    cases = value.get("cases")
    if value.get("schema_version") != "kwi.migration-cases.v1" or not isinstance(cases, list):
        return [_finding("KWI-PLAN-MIGRATION-FIXTURE", "fixtures/migration-cases.v1.json", "invalid fixture envelope")]
    ids = [item.get("case_id") for item in cases if isinstance(item, dict)]
    if len(ids) != len(cases) or set(ids) != MIGRATION_CASES or _duplicates([str(item) for item in ids]):
        findings.append(_finding("KWI-PLAN-MIGRATION-COVERAGE", "fixtures/migration-cases.v1.json", "migration case IDs must exactly match the consumed cases"))
    for item in cases:
        if not isinstance(item, dict):
            continue
        if item.get("historical_bytes_mutated") is not False:
            findings.append(_finding("KWI-PLAN-MIGRATION-BYTES", str(item.get("case_id")), "historical bytes must remain unchanged"))
        if not isinstance(item.get("mode"), str) or not item.get("mode"):
            findings.append(_finding("KWI-PLAN-MIGRATION-MODE", str(item.get("case_id")), "migration mode is required"))
    return findings


def validate_state(
    state: dict[str, Any], resume: dict[str, Any], index_text: str
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    status = state.get("status")
    if state.get("schema_version") != "vdd.plan-state.v2" or state.get("plan_id") != PLAN_ID or state.get("profile") != "self-hosted" or status not in LIFECYCLE:
        findings.append(_finding("KWI-PLAN-STATE", "plan-state.v1.json", "plan state identity or lifecycle status is invalid"))
        return findings
    status_lines = re.findall(r"^- Status: ([^\r\n]+)$", index_text, re.MULTILINE)
    if status_lines != [status]:
        findings.append(_finding("KWI-PLAN-STATE-PROJECTION", "00-index.md", "index status must exactly match plan state"))
    expected_authorizes = LIFECYCLE[1 : LIFECYCLE.index(status) + 1]
    if state.get("authorizes") != expected_authorizes:
        findings.append(_finding("KWI-PLAN-STATE-AUTHORIZES", "plan-state.v1.json", f"authorizes must equal {expected_authorizes}"))
    history = state.get("status_history")
    if not isinstance(history, list) or not history or history[-1].get("status") != status:
        findings.append(_finding("KWI-PLAN-STATE-HISTORY", "plan-state.v1.json", "status history must end at current status"))
    else:
        positions: list[int] = []
        for item in history:
            item_status = item.get("status") if isinstance(item, dict) else None
            if item_status not in LIFECYCLE:
                findings.append(_finding("KWI-PLAN-STATE-HISTORY", "plan-state.v1.json", "history contains an invalid state"))
                break
            positions.append(LIFECYCLE.index(item_status))
        if any(current < previous or current - previous > 1 for previous, current in zip(positions, positions[1:])):
            findings.append(_finding("KWI-PLAN-STATE-TRANSITION", "plan-state.v1.json", "history contains a skipped or backward transition"))
    if resume.get("schema_version") != "vdd.resume-state.v2" or resume.get("plan_id") != PLAN_ID or resume.get("profile") != "self-hosted":
        findings.append(_finding("KWI-PLAN-RESUME", "resume-state.v1.json", "resume identity is invalid"))
    if resume.get("live_phase_paths_allowed") is not False:
        findings.append(_finding("KWI-PLAN-RESUME-PHASE", "resume-state.v1.json", "live Phase paths must remain forbidden"))
    slice_status = resume.get("slice_status")
    if not isinstance(slice_status, dict) or list(slice_status) != EXPECTED_SLICES:
        findings.append(_finding("KWI-PLAN-RESUME-SLICES", "resume-state.v1.json", "resume state must list all slices in order"))
    if status in {"draft", "plan-ready"}:
        if resume.get("current_slice") is not None or not isinstance(slice_status, dict) or set(slice_status.values()) != {"pending"}:
            findings.append(_finding("KWI-PLAN-PREIMPLEMENTATION", "resume-state.v1.json", "pre-implementation slices must remain pending"))
    return findings


def _git(repository_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def validate_authority(
    manifest: dict[str, Any], state: dict[str, Any], repository_root: Path
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    sources = manifest.get("sources")
    if manifest.get("schema_version") != "kwi.authority-manifest.v1" or manifest.get("plan_id") != PLAN_ID or not isinstance(sources, list):
        return [_finding("KWI-PLAN-AUTHORITY", "authority-manifest.v1.json", "invalid authority manifest envelope")]
    paths = [item.get("path") for item in sources if isinstance(item, dict)]
    if len(paths) != len(sources) or any(not _safe_relative(path) for path in paths) or _duplicates([str(path) for path in paths]):
        findings.append(_finding("KWI-PLAN-AUTHORITY-PATH", "authority-manifest.v1.json", "authority paths must be unique and repository-contained"))
    by_role: dict[str, set[str]] = {}
    status = state.get("status")
    for item in sources:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        path, role, expected = item["path"], item.get("role"), item.get("sha256")
        if role not in {"authority", "implementation-target", "migration-source"}:
            findings.append(_finding("KWI-PLAN-AUTHORITY-ROLE", path, "unknown authority role"))
            continue
        by_role.setdefault(role, set()).add(path)
        target = repository_root / path
        if not target.is_file():
            findings.append(_finding("KWI-PLAN-AUTHORITY-MISSING", path, "pinned source is missing"))
            continue
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            findings.append(_finding("KWI-PLAN-AUTHORITY-HASH", path, "sha256 must be a lowercase hexadecimal digest"))
            continue
        enforce_hash = role in {"authority", "migration-source"}
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if enforce_hash and actual != expected:
            findings.append(_finding("KWI-PLAN-AUTHORITY-DRIFT", path, f"expected {expected}, got {actual}"))
    if not REQUIRED_AUTHORITY.issubset(by_role.get("authority", set())):
        findings.append(_finding("KWI-PLAN-AUTHORITY-COVERAGE", "authority-manifest.v1.json", "required Accepted ADR authority is incomplete"))
    if not REQUIRED_UPSTREAM_AUTHORITY.issubset(by_role.get("authority", set())):
        findings.append(_finding("KWI-PLAN-UPSTREAM-AUTHORITY", "authority-manifest.v1.json", "the completed upstream plan index and active requirement ledger must be hash-bound authority"))
    if not REQUIRED_MIGRATION_SOURCES.issubset(by_role.get("migration-source", set())):
        findings.append(_finding("KWI-PLAN-MIGRATION-SOURCE", "authority-manifest.v1.json", "dated Locator contracts must be pinned migration sources"))
    baseline = state.get("git_baseline")
    head = baseline.get("head") if isinstance(baseline, dict) else None
    tree = baseline.get("tree") if isinstance(baseline, dict) else None
    if manifest.get("git_baseline") != head or not isinstance(head, str) or not isinstance(tree, str):
        findings.append(_finding("KWI-PLAN-BASELINE", "plan-state.v1.json", "baseline identities do not agree"))
    else:
        try:
            _git(repository_root, "cat-file", "-e", f"{head}^{{commit}}")
            actual_tree = _git(repository_root, "rev-parse", f"{head}^{{tree}}")
            if actual_tree != tree:
                findings.append(_finding("KWI-PLAN-BASELINE-TREE", "plan-state.v1.json", f"expected {tree}, got {actual_tree}"))
        except ValueError as exc:
            findings.append(_finding("KWI-PLAN-BASELINE-GIT", "plan-state.v1.json", str(exc)))
    return findings


def validate_report_index(repository_root: Path) -> list[dict[str, str]]:
    relative = "execution-plans/95-implementation-report-index.v1.json"
    path = repository_root / relative
    try:
        value = strict_load(path)
    except (OSError, StrictJsonError) as exc:
        return [_finding("KWI-PLAN-REPORT-INDEX", relative, str(exc))]
    expected = {
        "plan_directory": PLAN_DIRECTORY,
        "report_filename": "95-implementation-evolution-and-completion-report.md",
    }
    entries = value.get("entries")
    matches = [item for item in entries if item == expected] if isinstance(entries, list) else []
    if value.get("schema_version") != "jimuyun.execution-plan-95-report-index.v1" or len(matches) != 1:
        return [_finding("KWI-PLAN-REPORT-INDEX", relative, "report entry must exist exactly once")]
    return []


def validate_successor_reentry(
    repository_root: Path, decision: dict[str, Any] | None = None
) -> list[dict[str, str]]:
    """Consume the root-owned successor decision without granting plan authority."""
    path = repository_root / SUCCESSOR_POLICY_DECISION
    try:
        if decision is None:
            decision = strict_load(path)
        module_path = repository_root / ".agents" / "skills" / "run-phase-bootstrap-review" / "scripts" / "bootstrap_review.py"
        spec = importlib.util.spec_from_file_location("kwi_successor_control_plane", module_path)
        if spec is None or spec.loader is None:
            raise ValueError("bootstrap successor validator is unavailable")
        module = importlib.util.module_from_spec(spec)
        previous_path = list(sys.path)
        try:
            sys.path.insert(0, str(module_path.parent))
            spec.loader.exec_module(module)
        finally:
            sys.path[:] = previous_path
        module.validate_successor_policy_authorization(repository_root, decision)
        if (
            decision.get("supersededReviewId") != SUCCESSOR_REVIEW_ID
            or decision.get("successorChangeId") != SUCCESSOR_CHANGE_ID
        ):
            raise ValueError("successor decision does not bind the expected review lineage")
    except Exception as exc:
        return [_finding("KWI-PLAN-SUCCESSOR-REENTRY", SUCCESSOR_POLICY_DECISION, str(exc))]
    return []


def validate_directory(
    plan_root: Path = PLAN_ROOT, repository_root: Path = REPOSITORY_ROOT
) -> dict[str, Any]:
    plan_root, repository_root = plan_root.resolve(), repository_root.resolve()
    findings = validate_file_format(plan_root)
    documents: dict[str, dict[str, Any]] = {}
    for relative in JSON_FILES:
        path = plan_root / relative
        if not path.is_file():
            continue
        try:
            documents[relative] = strict_load(path)
        except (OSError, StrictJsonError) as exc:
            findings.append(_finding("KWI-PLAN-JSON", relative, str(exc)))
    try:
        index_text = (plan_root / "00-index.md").read_text(encoding="utf-8")
        requirements_text = (plan_root / "01-requirements-and-acceptance.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        findings.append(_finding("KWI-PLAN-MARKDOWN", str(plan_root), str(exc)))
        index_text, requirements_text = "", ""
    state = documents.get("plan-state.v1.json")
    resume = documents.get("resume-state.v1.json")
    contract = documents.get("implementation-contract.v1.json")
    registry = documents.get("command-registry.v1.json")
    manifest = documents.get("authority-manifest.v1.json")
    protocol = documents.get("fixtures/protocol-cases.v1.json")
    migration = documents.get("fixtures/migration-cases.v1.json")
    if state is not None and resume is not None:
        findings.extend(validate_state(state, resume, index_text))
    if contract is not None:
        findings.extend(validate_requirement_coverage(requirements_text, contract))
        findings.extend(validate_slices(contract, repository_root))
    if contract is not None and registry is not None:
        findings.extend(validate_commands(registry, contract))
    if protocol is not None:
        findings.extend(validate_protocol_fixtures(protocol))
    if migration is not None:
        findings.extend(validate_migration_fixtures(migration))
    if manifest is not None and state is not None:
        findings.extend(validate_authority(manifest, state, repository_root))
    findings.extend(validate_successor_reentry(repository_root))
    findings.extend(validate_report_index(repository_root))
    status = state.get("status") if isinstance(state, dict) else None
    return {
        "schema_version": "kwi.plan-validation.v1",
        "plan_id": PLAN_ID,
        "status": "pass" if not findings else "fail",
        "plan_state": status,
        "checks": [
            "required-files-and-encoding",
            "strict-json",
            "lifecycle-and-resume",
            "requirement-and-acceptance-coverage",
            "slice-order-and-boundaries",
            "structured-command-registry",
            "protocol-and-migration-fixtures",
            "authority-and-git-baseline",
            "successor-policy-reentry",
            "implementation-report-index",
        ],
        "findings": findings,
        "authorizes": [],
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def publish_plan_ready_files(plan_root: Path) -> bool:
    """Publish only the draft-to-plan-ready files; callers validate first."""
    state_path = plan_root / "plan-state.v1.json"
    resume_path = plan_root / "resume-state.v1.json"
    index_path = plan_root / "00-index.md"
    state = strict_load(state_path)
    resume = strict_load(resume_path)
    status = state.get("status")
    if status not in {"draft", "plan-ready"}:
        raise ValueError(f"cannot publish plan-ready from {status}")
    if status == "plan-ready":
        return False
    index_text = index_path.read_text(encoding="utf-8")
    if len(re.findall(r"^- Status: draft$", index_text, re.MULTILINE)) != 1:
        raise ValueError("00-index.md does not project draft exactly once")
    state["status"] = "plan-ready"
    state["authorizes"] = ["plan-ready"]
    history = state.get("status_history")
    if not isinstance(history, list):
        raise ValueError("status history is invalid")
    history.append(
        {
            "status": "plan-ready",
            "reason": "The complete self-hosted directory passed its deterministic plan validator.",
            "evidence": ["tools/validate_plan.py --publish-plan-ready"],
        }
    )
    index_text = re.sub(r"^- Status: draft$", "- Status: plan-ready", index_text, count=1, flags=re.MULTILINE)
    index_text = re.sub(
        r"^- Current step:.*$",
        "- Current step: Await explicit implementation authorization before RMAP-S0.",
        index_text,
        count=1,
        flags=re.MULTILINE,
    )
    resume["next_action"] = "Obtain explicit implementation authorization before RMAP-S0."
    _write_json(state_path, state)
    _write_json(resume_path, resume)
    index_path.write_text(index_text, encoding="utf-8", newline="\n")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the Knowledge Locator workflow integration plan.")
    parser.add_argument("--publish-plan-ready", action="store_true")
    args = parser.parse_args(argv)
    result = validate_directory()
    published = False
    if args.publish_plan_ready and result["status"] == "pass":
        try:
            published = publish_plan_ready_files(PLAN_ROOT)
        except (OSError, StrictJsonError, ValueError) as exc:
            result["status"] = "fail"
            result["findings"].append(_finding("KWI-PLAN-PUBLISH", "plan-ready", str(exc)))
        else:
            result = validate_directory()
            if published and result["status"] == "pass":
                result["authorizes"] = ["plan-ready"]
    result["published"] = published
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
