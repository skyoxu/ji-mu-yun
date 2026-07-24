#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


CONTRACT_PATH = Path("scripts/skill-contract.json")
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
ARTIFACT_PROOF_REQUIRED_FIELDS = [
    "artifact_path",
    "artifact_kind",
    "proof_scope",
    "finding_ids",
    "dimension_verdicts",
    "schema_producer_authority",
    "immutable_identity",
    "source_of_truth_derivation",
    "independent_recomputation",
    "staleness_propagation",
    "recovery_supersession",
    "consumer_authorization_boundary",
]
ARTIFACT_PROOF_DIMENSIONS = [
    "schema_producer_authority",
    "immutable_identity",
    "source_of_truth_derivation",
    "independent_recomputation",
    "staleness_propagation",
    "recovery_supersession",
    "consumer_authorization_boundary",
]
ARTIFACT_PROOF_FAILURE_IDS = [
    "VDD-ARTIFACT-PROOF-PRODUCER",
    "VDD-ARTIFACT-PROOF-IDENTITY",
    "VDD-ARTIFACT-PROOF-DERIVATION",
    "VDD-ARTIFACT-PROOF-RULE",
    "VDD-ARTIFACT-PROOF-STALENESS",
    "VDD-ARTIFACT-PROOF-LINEAGE",
    "VDD-ARTIFACT-PROOF-CONSUMER",
    "VDD-ARTIFACT-PROOF-APPLICABILITY",
]
ARTIFACT_PROOF_INVALIDATES = [
    "artifact-proof-registry",
    "runtime-artifact-type-proof",
    "plan-repair-verified",
    "plan-ready",
]
ARTIFACT_PROOF_EXCLUSIONS = [
    "plan-ready",
    "slice-ready",
    "bootstrap-review",
    "implementation-accepted",
    "protected-handoff",
    "release-ready",
]
ARTIFACT_PROOF_AUTHORITY_PATH = ".agents/skills/vdd-execution-plan/references/strict-vdd-standard.md"
ARTIFACT_PROOF_AUTHORITY_FILE = Path("references/strict-vdd-standard.md")
ARTIFACT_PROOF_SEMANTIC_FIELD = "/3-authority-intent-kernels-and-executable-contracts"


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


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant is not allowed: {value}")


def parse_json(text: str) -> Any:
    return json.loads(text, parse_constant=reject_json_constant)


def load_json(path: Path) -> Any:
    return parse_json(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def is_safe_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "." not in path.parts


def is_policy_owned_package_path(value: Any, package_relative: str) -> bool:
    return value in {
        package_relative,
        f".agents/skills/vdd-execution-plan/{package_relative}",
    }


def validate_artifact_proof_trust_roots(
    skill_root: Path,
    contract: dict[str, Any],
    proof: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    policy = contract.get("artifact_proof_root_policy")
    policy_fields = {
        "schema_version",
        "fixture_path",
        "required_fields",
        "required_dimensions",
        "authority_path",
        "authority_sha256",
        "semantic_policy_field",
        "identity_mode",
        "identity_algorithm",
        "derivation",
        "validator_path",
        "negative_test_path",
        "callable",
        "expected_failure_ids",
        "required_invalidates",
        "required_lineage_fields",
        "required_exclusions",
    }
    if (
        not isinstance(policy, dict)
        or set(policy) != policy_fields
        or policy.get("schema_version") != "vdd.artifact-proof-root-policy.v1"
        or policy.get("required_fields") != ARTIFACT_PROOF_REQUIRED_FIELDS
        or policy.get("required_dimensions") != ARTIFACT_PROOF_DIMENSIONS
        or policy.get("identity_mode") != "semantic-root-policy"
        or policy.get("identity_algorithm") != "vdd-root-policy-v1"
        or policy.get("derivation") != "semantic-policy-reference"
        or policy.get("authority_path") != ARTIFACT_PROOF_AUTHORITY_PATH
        or policy.get("semantic_policy_field") != ARTIFACT_PROOF_SEMANTIC_FIELD
        or policy.get("callable") != "validate_artifact_proof_trust_roots"
        or policy.get("expected_failure_ids") != ARTIFACT_PROOF_FAILURE_IDS
        or policy.get("required_invalidates") != ARTIFACT_PROOF_INVALIDATES
        or policy.get("required_lineage_fields")
        != ["artifact_path", "immutable_identity", "recovery_supersession"]
        or policy.get("required_exclusions") != ARTIFACT_PROOF_EXCLUSIONS
        or not is_safe_relative_path(policy.get("fixture_path"))
        or not HASH_PATTERN.fullmatch(str(policy.get("authority_sha256")))
        or not is_safe_relative_path(policy.get("validator_path"))
        or not is_safe_relative_path(policy.get("negative_test_path"))
    ):
        return [
            finding(
                "VDD-ARTIFACT-PROOF-PRODUCER",
                str(CONTRACT_PATH),
                "the generic artifact-proof root policy is invalid",
            )
        ]

    target = str(policy["fixture_path"])
    if proof is None:
        try:
            fixture = load_json(skill_root / policy["fixture_path"])
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            fixture = None
        if (
            not isinstance(fixture, dict)
            or fixture.get("schema_version") != "vdd.artifact-proof-root-fixture.v1"
            or not isinstance(fixture.get("root_id"), str)
            or not fixture["root_id"]
            or not isinstance(fixture.get("proof"), dict)
        ):
            return [
                finding(
                    "VDD-ARTIFACT-PROOF-PRODUCER",
                    target,
                    "the detached artifact-proof fixture is invalid",
                )
            ]
        proof = fixture["proof"]

    if set(proof) != set(ARTIFACT_PROOF_REQUIRED_FIELDS):
        return [finding("VDD-ARTIFACT-PROOF-PRODUCER", target, "root must use the complete artifact-proof template")]
    verdicts = proof.get("dimension_verdicts")
    if (
        proof.get("proof_scope") != "static-contract"
        or not isinstance(verdicts, dict)
        or set(verdicts) != set(ARTIFACT_PROOF_DIMENSIONS)
        or any(
            not isinstance(verdicts[dimension], dict)
            or set(verdicts[dimension]) != {"status", "evidence_rule_ids"}
            or verdicts[dimension].get("status") != "PASS"
            or not isinstance(verdicts[dimension].get("evidence_rule_ids"), list)
            or not verdicts[dimension]["evidence_rule_ids"]
            or any(not isinstance(rule_id, str) or not rule_id for rule_id in verdicts[dimension]["evidence_rule_ids"])
            for dimension in ARTIFACT_PROOF_DIMENSIONS
        )
    ):
        return [finding("VDD-ARTIFACT-PROOF-APPLICABILITY", target, "root requires complete executable PASS verdicts")]

    producer = proof.get("schema_producer_authority")
    expected_producer = {
        "authority_path": policy["authority_path"],
        "authority_category": "protocol_authority",
        "authority_sha256": policy["authority_sha256"],
        "producer_kind": "manual-authority",
        "generator_path": None,
        "generator_sha256": None,
    }
    if (
        not is_safe_relative_path(proof.get("artifact_path"))
        or proof.get("artifact_kind") != "normative"
        or not isinstance(proof.get("finding_ids"), list)
        or not proof["finding_ids"]
        or any(not isinstance(item, str) or not item for item in proof["finding_ids"])
        or producer != expected_producer
        or sha256_file(skill_root / ARTIFACT_PROOF_AUTHORITY_FILE) != policy["authority_sha256"]
    ):
        return [finding("VDD-ARTIFACT-PROOF-PRODUCER", target, "producer authority is not the generic VDD protocol authority")]
    identity = proof.get("immutable_identity")
    if (
        not isinstance(identity, dict)
        or set(identity) != {"mode", "algorithm", "artifact_sha256", "authority_revision", "manifest_path"}
        or identity.get("mode") != policy["identity_mode"]
        or identity.get("algorithm") != policy["identity_algorithm"]
        or identity.get("artifact_sha256") is not None
        or not isinstance(identity.get("authority_revision"), str)
        or not identity["authority_revision"]
        or not is_safe_relative_path(identity.get("manifest_path"))
    ):
        return [finding("VDD-ARTIFACT-PROOF-IDENTITY", target, "semantic root identity is invalid")]
    expected_input = {
        "source": policy["authority_path"],
        "source_sha256": policy["authority_sha256"],
        "field": policy["semantic_policy_field"],
        "target_field": "$policy",
        "derivation": policy["derivation"],
    }
    derivation = proof.get("source_of_truth_derivation")
    if derivation != {"rules": [expected_input]}:
        return [finding("VDD-ARTIFACT-PROOF-DERIVATION", target, "root must bind semantic policy instead of regenerable projection bytes")]
    recomputation = proof.get("independent_recomputation")
    if (
        not isinstance(recomputation, dict)
        or set(recomputation)
        != {"rule_id", "validator_path", "validator_sha256", "callable", "negative_test_path", "negative_test_sha256", "expected_failure_ids"}
        or not isinstance(recomputation.get("rule_id"), str)
        or not recomputation["rule_id"]
        or not is_policy_owned_package_path(
            recomputation.get("validator_path"), policy["validator_path"]
        )
        or recomputation.get("validator_sha256") != sha256_file(skill_root / policy["validator_path"])
        or recomputation.get("callable") != policy["callable"]
        or not is_policy_owned_package_path(
            recomputation.get("negative_test_path"), policy["negative_test_path"]
        )
        or recomputation.get("negative_test_sha256") != sha256_file(skill_root / policy["negative_test_path"])
        or recomputation.get("expected_failure_ids") != ARTIFACT_PROOF_FAILURE_IDS
    ):
        return [finding("VDD-ARTIFACT-PROOF-RULE", target, "independent recomputation identity is stale or incomplete")]
    stale = proof.get("staleness_propagation")
    if (
        not isinstance(stale, dict)
        or set(stale) != {"inputs", "invalidates", "regeneration_command_id", "revalidation_command_id"}
        or stale.get("inputs") != [expected_input]
        or stale.get("invalidates") != ARTIFACT_PROOF_INVALIDATES
        or not isinstance(stale.get("regeneration_command_id"), str)
        or not stale["regeneration_command_id"]
        or not isinstance(stale.get("revalidation_command_id"), str)
        or not stale["revalidation_command_id"]
    ):
        return [finding("VDD-ARTIFACT-PROOF-STALENESS", target, "staleness closure is not exact")]
    recovery = proof.get("recovery_supersession")
    if (
        not isinstance(recovery, dict)
        or set(recovery)
        != {"history_policy", "schema_path", "lineage_fields", "predecessor_policy", "lifecycle_status", "predecessor_sha256"}
        or recovery.get("history_policy") != "append-only-successor-no-rewrite"
        or not is_safe_relative_path(recovery.get("schema_path"))
        or recovery.get("lineage_fields") != policy["required_lineage_fields"]
        or not isinstance(recovery.get("predecessor_policy"), str)
        or not recovery["predecessor_policy"]
        or recovery.get("lifecycle_status") != "supersedes"
        or not HASH_PATTERN.fullmatch(str(recovery.get("predecessor_sha256")))
    ):
        return [finding("VDD-ARTIFACT-PROOF-LINEAGE", target, "append-only predecessor lineage is invalid")]
    boundary = proof.get("consumer_authorization_boundary")
    if (
        not isinstance(boundary, dict)
        or set(boundary) != {"consumers", "predicate", "authorizes", "does_not_authorize"}
        or not isinstance(boundary.get("consumers"), list)
        or not boundary["consumers"]
        or any(not isinstance(item, str) or not item for item in boundary["consumers"])
        or not isinstance(boundary.get("predicate"), str)
        or not boundary["predicate"]
        or boundary.get("authorizes") != []
        or boundary.get("does_not_authorize") != ARTIFACT_PROOF_EXCLUSIONS
    ):
        return [finding("VDD-ARTIFACT-PROOF-CONSUMER", target, "root permission lattice is not exact zero authority")]
    return []


def validate_execution_plan_report_index_fixture(
    fixture_path: Path,
) -> list[dict[str, str]]:
    try:
        document = load_json(fixture_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return [finding("VDD-REPORT-INDEX", str(fixture_path), "detached report-index fixture is not valid JSON")]
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "entries"}
        or document.get("schema_version") != "jimuyun.execution-plan-95-report-index.v1"
        or not isinstance(document.get("entries"), list)
    ):
        return [finding("VDD-REPORT-INDEX", str(fixture_path), "detached report-index fixture has an invalid envelope")]
    entries = document["entries"]
    if entries != sorted(entries, key=lambda item: str(item.get("plan_directory", "")).casefold() if isinstance(item, dict) else ""):
        return [finding("VDD-REPORT-INDEX", str(fixture_path), "report-index entries must be case-insensitively sorted")]
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"plan_directory", "report_filename"}:
            return [finding("VDD-REPORT-INDEX", str(fixture_path), "report-index entry shape is invalid")]
        plan_directory = entry["plan_directory"]
        report_filename = entry["report_filename"]
        if (
            not isinstance(plan_directory, str)
            or not plan_directory
            or "/" in plan_directory
            or "\\" in plan_directory
            or plan_directory in {".", ".."}
            or plan_directory.casefold() in seen
            or not isinstance(report_filename, str)
            or not report_filename.startswith("95-")
            or not report_filename.endswith(".md")
            or "/" in report_filename
            or "\\" in report_filename
            or report_filename in {".", ".."}
        ):
            return [finding("VDD-REPORT-INDEX", str(fixture_path), "report-index entry is unsafe or ambiguous")]
        seen.add(plan_directory.casefold())
    return []


def require_string_list(container: dict[str, Any], field_name: str) -> list[str]:
    value = container.get(field_name)
    if not isinstance(value, list) or not value or any(not is_non_empty_string(item) for item in value):
        raise ValueError(f"skill contract {field_name} must be a non-empty string list")
    return value


def require_string_list_map(container: dict[str, Any], field_name: str) -> dict[str, list[str]]:
    value = container.get(field_name)
    if not isinstance(value, dict) or not value:
        raise ValueError(f"skill contract {field_name} must be a non-empty object")
    for key, items in value.items():
        if not is_non_empty_string(key) or not isinstance(items, list) or not items or any(
            not is_non_empty_string(item) for item in items
        ):
            raise ValueError(
                f"skill contract {field_name} entries must map non-empty strings to non-empty string lists"
            )
    return value


def load_contract(skill_root: Path) -> dict[str, Any]:
    path = skill_root / CONTRACT_PATH
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError("skill contract must be a JSON object")
    if data.get("schema_version") != "vdd.skill-contract.v2":
        raise ValueError(f"unsupported skill contract schema: {data.get('schema_version')!r}")
    require_string_list(data, "required_files")
    require_string_list_map(data, "required_headings")
    require_string_list_map(data, "required_links")
    validation_result = data.get("validation_result")
    if not isinstance(validation_result, dict):
        raise ValueError("skill contract validation_result must be an object")
    for field_name in ("required_fields", "allowed_statuses", "allowed_check_statuses"):
        require_string_list(validation_result, field_name)
    authority_by_predicate = validation_result.get("authority_by_predicate")
    if not isinstance(authority_by_predicate, dict) or not authority_by_predicate:
        raise ValueError("skill contract validation_result authority_by_predicate is required")
    for predicate, authority in authority_by_predicate.items():
        if not is_non_empty_string(predicate) or not isinstance(authority, dict):
            raise ValueError("skill contract authority_by_predicate entries must be objects")
        for field_name in ("authorizes", "does_not_authorize"):
            require_string_list(authority, field_name)
        if set(authority["authorizes"]) & set(authority["does_not_authorize"]):
            raise ValueError(f"skill contract authority policy overlaps for predicate {predicate}")
    trust_root_findings = validate_artifact_proof_trust_roots(skill_root, data)
    if trust_root_findings:
        first = trust_root_findings[0]
        raise ValueError(f"{first['rule_id']}: {first['message']}")
    compliance = data.get("compliance")
    if not isinstance(compliance, dict):
        raise ValueError("skill contract compliance must be an object")
    for field_name in ("required_scenario_levels", "ordered_steps"):
        require_string_list(compliance, field_name)
    clarification = data.get("clarification")
    if not isinstance(clarification, dict):
        raise ValueError("skill contract clarification must be an object")
    if not is_non_empty_string(clarification.get("schema_version")):
        raise ValueError("skill contract clarification schema_version is required")
    for field_name in (
        "required_state_fields",
        "required_round_fields",
        "required_question_fields",
        "allowed_question_fields",
        "required_exit_fields",
        "allowed_modes",
        "allowed_statuses",
        "allowed_invalidation_source_statuses",
        "allowed_supersede_source_statuses",
        "required_command_rule_ids",
        "sensitive_value_families",
        "allowed_interaction_modes",
        "allowed_question_statuses",
        "allowed_question_bases",
        "reopenable_question_statuses",
        "open_blocker_statuses",
        "dimension_keys",
        "required_case_ids",
    ):
        require_string_list(clarification, field_name)
    require_string_list_map(clarification, "question_status_transitions")
    minimum_questions = clarification.get("minimum_questions_per_round")
    if not isinstance(minimum_questions, int) or isinstance(minimum_questions, bool) or minimum_questions < 1:
        raise ValueError("skill contract clarification minimum_questions_per_round must be positive")
    if not is_non_empty_string(clarification.get("evidence_target_overlap_policy")):
        raise ValueError("skill contract clarification evidence_target_overlap_policy is required")
    for field_name in (
        "target_identity_case_policy",
        "state_mutation_lock_policy",
        "target_registry_policy",
        "transition_commit_policy",
    ):
        if not is_non_empty_string(clarification.get(field_name)):
            raise ValueError(f"skill contract clarification {field_name} is required")
    maximum_active = clarification.get("maximum_active_runs_per_target")
    if not isinstance(maximum_active, int) or isinstance(maximum_active, bool) or maximum_active < 1:
        raise ValueError("skill contract clarification maximum_active_runs_per_target must be positive")
    return data


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_timezone_datetime(value: Any) -> bool:
    if not is_non_empty_string(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_string_list(
    findings: list[dict[str, str]], fixture: Path, data: dict[str, Any], field_name: str
) -> None:
    value = data.get(field_name)
    if not isinstance(value, list) or any(not is_non_empty_string(item) for item in value):
        findings.append(
            finding(
                "VDD-RESULT-FIELD",
                str(fixture),
                f"{field_name} must be a list of non-empty strings",
            )
        )


def validate_result_fixture(skill_root: Path, fixture: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    checks = [
        "result-fields",
        "result-status",
        "result-hashes",
        "result-checks",
        "result-freshness",
        "result-authority",
    ]
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

    for field_name in ("run_id", "predicate", "validator_version"):
        if not is_non_empty_string(data.get(field_name)):
            findings.append(
                finding(
                    "VDD-RESULT-FIELD",
                    str(fixture),
                    f"{field_name} must be a non-empty string",
                )
            )
    if not is_timezone_datetime(data.get("generated_at")):
        findings.append(
            finding(
                "VDD-RESULT-FIELD",
                str(fixture),
                "generated_at must be a timezone-aware ISO 8601 datetime",
            )
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
            if not is_non_empty_string(check.get("rule_id")):
                findings.append(finding("VDD-RESULT-CHECK", target, "check rule_id is required"))
            check_status = check.get("status")
            if check_status not in rules["allowed_check_statuses"]:
                findings.append(
                    finding("VDD-RESULT-CHECK", target, f"invalid check status: {check_status!r}")
                )
            evidence = check.get("evidence")
            if not isinstance(evidence, list) or not evidence or not all(
                is_non_empty_string(item) for item in evidence
            ):
                findings.append(
                    finding("VDD-RESULT-CHECK", target, "check evidence must be a non-empty string list")
                )
            if status == "pass" and check_status != "pass":
                findings.append(
                    finding("VDD-RESULT-CHECK", target, "pass result cannot contain non-pass checks")
                )

    for list_field in ("authorizes", "does_not_authorize"):
        validate_string_list(findings, fixture, data, list_field)
    diagnostics = data.get("diagnostics")
    if not isinstance(diagnostics, list) or any(not isinstance(item, dict) for item in diagnostics):
        findings.append(
            finding("VDD-RESULT-FIELD", str(fixture), "diagnostics must be a list of objects")
        )
    elif any(not is_non_empty_string(item.get("rule_id")) for item in diagnostics):
        findings.append(
            finding(
                "VDD-RESULT-FIELD",
                str(fixture),
                "every diagnostic must contain a non-empty rule_id",
            )
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
    if status == "pass":
        predicate = data.get("predicate")
        authority = (
            rules["authority_by_predicate"].get(predicate)
            if is_non_empty_string(predicate)
            else None
        )
        if authority is None:
            findings.append(
                finding(
                    "VDD-RESULT-AUTHORITY",
                    str(fixture),
                    f"pass result uses an unregistered authority predicate: {predicate!r}",
                )
            )
        else:
            for field_name in ("authorizes", "does_not_authorize"):
                actual = data.get(field_name)
                expected = authority[field_name]
                valid_actual = isinstance(actual, list) and all(
                    is_non_empty_string(item) for item in actual
                )
                if (
                    not valid_actual
                    or len(actual) != len(expected)
                    or set(actual) != set(expected)
                ):
                    findings.append(
                        finding(
                            "VDD-RESULT-AUTHORITY",
                            str(fixture),
                            f"{field_name} must exactly match predicate {predicate}: {expected}",
                        )
                    )
            authorizes = data.get("authorizes")
            does_not_authorize = data.get("does_not_authorize")
            if (
                isinstance(authorizes, list)
                and all(is_non_empty_string(item) for item in authorizes)
                and isinstance(does_not_authorize, list)
                and all(is_non_empty_string(item) for item in does_not_authorize)
                and set(authorizes) & set(does_not_authorize)
            ):
                findings.append(
                    finding(
                        "VDD-RESULT-AUTHORITY",
                        str(fixture),
                        "authorizes and does_not_authorize must be disjoint",
                    )
                )
    if status == "pass" and diagnostics:
        findings.append(
            finding("VDD-RESULT-STATUS", str(fixture), "pass result cannot contain diagnostics")
        )
    if status in {"fail", "blocked", "incomplete"}:
        if data.get("authorizes"):
            findings.append(
                finding(
                    "VDD-RESULT-AUTHORITY",
                    str(fixture),
                    f"{status} result cannot authorize a transition",
                )
            )
        if not diagnostics:
            findings.append(
                finding(
                    "VDD-RESULT-STATUS",
                    str(fixture),
                    f"{status} result must contain a diagnostic",
                )
            )
        if isinstance(checks_value, list) and not any(
            isinstance(check, dict) and check.get("status") in {"fail", "skip"}
            for check in checks_value
        ):
            findings.append(
                finding(
                    "VDD-RESULT-CHECK",
                    str(fixture),
                    f"{status} result must contain a fail or skip check",
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
            event = parse_json(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            findings.append(
                finding(
                    "VDD-COMPLIANCE-PARSE",
                    f"{fixture}:{line_number}",
                    f"invalid JSON: {exc.msg if isinstance(exc, json.JSONDecodeError) else exc}",
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
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in seqs
    ):
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


def load_clarification_module(skill_root: Path):
    path = skill_root / "scripts" / "clarification_state.py"
    if not path.is_file():
        raise OSError(f"clarification state implementation missing: {path}")
    spec = importlib.util.spec_from_file_location("vdd_clarification_state", path)
    if spec is None or spec.loader is None:
        raise OSError(f"cannot load clarification state implementation: {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (ImportError, SyntaxError) as exc:
        raise ValueError(f"invalid clarification state implementation: {exc}") from exc
    return module


def validate_clarification_fixture(skill_root: Path, fixture: Path) -> dict[str, Any]:
    checks = [
        "clarification-schema",
        "clarification-rounds",
        "clarification-confidence",
        "clarification-exit",
        "clarification-freshness",
        "clarification-write-boundary",
    ]
    try:
        module = load_clarification_module(skill_root)
        data = load_json(fixture)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return result([finding("VDD-CLARIFICATION-PARSE", str(fixture), str(exc))], checks)
    findings = module.validate_state_data(data, str(fixture))
    return result(findings, checks)


def validate_clarification_contract_alignment(skill_root: Path) -> list[dict[str, str]]:
    try:
        contract = load_contract(skill_root)["clarification"]
        module = load_clarification_module(skill_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return [finding("VDD-CLARIFICATION-CONTRACT-DRIFT", "scripts/skill-contract.json", str(exc))]
    comparisons = {
        "schema_version": (contract["schema_version"], module.SCHEMA_VERSION),
        "required_state_fields": (tuple(contract["required_state_fields"]), module.REQUIRED_STATE_FIELDS),
        "required_round_fields": (tuple(contract["required_round_fields"]), module.REQUIRED_ROUND_FIELDS),
        "required_question_fields": (
            tuple(contract["required_question_fields"]),
            module.REQUIRED_QUESTION_FIELDS,
        ),
        "allowed_question_fields": (
            set(contract["allowed_question_fields"]),
            set(module.ALLOWED_QUESTION_FIELDS),
        ),
        "required_exit_fields": (tuple(contract["required_exit_fields"]), module.REQUIRED_EXIT_FIELDS),
        "allowed_modes": (set(contract["allowed_modes"]), module.ALLOWED_MODES),
        "allowed_statuses": (set(contract["allowed_statuses"]), module.ALLOWED_STATUSES),
        "allowed_invalidation_source_statuses": (
            set(contract["allowed_invalidation_source_statuses"]),
            module.INVALIDATION_SOURCE_STATUSES,
        ),
        "allowed_supersede_source_statuses": (
            set(contract["allowed_supersede_source_statuses"]),
            module.SUPERSEDE_SOURCE_STATUSES,
        ),
        "evidence_target_overlap_policy": (
            contract["evidence_target_overlap_policy"],
            module.EVIDENCE_TARGET_OVERLAP_POLICY,
        ),
        "maximum_active_runs_per_target": (
            contract["maximum_active_runs_per_target"],
            module.MAXIMUM_ACTIVE_RUNS_PER_TARGET,
        ),
        "target_identity_case_policy": (
            contract["target_identity_case_policy"],
            module.TARGET_IDENTITY_CASE_POLICY,
        ),
        "state_mutation_lock_policy": (
            contract["state_mutation_lock_policy"],
            module.STATE_MUTATION_LOCK_POLICY,
        ),
        "target_registry_policy": (
            contract["target_registry_policy"],
            module.TARGET_REGISTRY_POLICY,
        ),
        "transition_commit_policy": (
            contract["transition_commit_policy"],
            module.TRANSITION_COMMIT_POLICY,
        ),
        "sensitive_value_families": (
            tuple(contract["sensitive_value_families"]),
            module.SENSITIVE_VALUE_FAMILIES,
        ),
        "required_command_rule_ids": (
            tuple(contract["required_command_rule_ids"]),
            module.COMMAND_RULE_IDS,
        ),
        "allowed_interaction_modes": (
            set(contract["allowed_interaction_modes"]),
            module.ALLOWED_INTERACTION_MODES,
        ),
        "allowed_question_statuses": (
            set(contract["allowed_question_statuses"]),
            module.ALLOWED_QUESTION_STATUSES,
        ),
        "allowed_question_bases": (
            set(contract["allowed_question_bases"]),
            module.ALLOWED_QUESTION_BASES,
        ),
        "reopenable_question_statuses": (
            set(contract["reopenable_question_statuses"]),
            module.REOPENABLE_QUESTION_STATUSES,
        ),
        "open_blocker_statuses": (
            set(contract["open_blocker_statuses"]),
            module.OPEN_BLOCKER_STATUSES,
        ),
        "question_status_transitions": (
            {key: set(value) for key, value in contract["question_status_transitions"].items()},
            module.QUESTION_STATUS_TRANSITIONS,
        ),
        "minimum_questions_per_round": (
            contract["minimum_questions_per_round"],
            module.MINIMUM_QUESTIONS_PER_ROUND,
        ),
        "dimension_keys": (tuple(contract["dimension_keys"]), module.DIMENSION_KEYS),
    }
    findings: list[dict[str, str]] = []
    for field_name, (declared, implemented) in comparisons.items():
        if declared != implemented:
            findings.append(
                finding(
                    "VDD-CLARIFICATION-CONTRACT-DRIFT",
                    "scripts/skill-contract.json",
                    f"{field_name} declared={declared!r}, implemented={implemented!r}",
                )
            )
    return findings


def _apply_json_pointer(document: Any, pointer: str, value: Any) -> None:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError(f"invalid mutation path: {pointer!r}")
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    current = document
    for part in parts[:-1]:
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise ValueError(f"mutation path crosses scalar: {pointer}")
    final = parts[-1]
    if isinstance(current, list):
        current[int(final)] = copy.deepcopy(value)
    elif isinstance(current, dict):
        if final not in current:
            raise ValueError(f"mutation path does not exist: {pointer}")
        current[final] = copy.deepcopy(value)
    else:
        raise ValueError(f"mutation path crosses scalar: {pointer}")


def validate_clarification_cases(skill_root: Path, fixture: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    checks = ["clarification-case-schema", "clarification-case-coverage", "clarification-case-results"]
    try:
        contract = load_contract(skill_root)
        module = load_clarification_module(skill_root)
        data = load_json(fixture)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return result([finding("VDD-CLARIFICATION-CASE-PARSE", str(fixture), str(exc))], checks)
    if not isinstance(data, dict) or data.get("schema_version") != "vdd.clarification-cases.v1":
        return result(
            [finding("VDD-CLARIFICATION-CASE-PARSE", str(fixture), "invalid clarification cases envelope")],
            checks,
        )
    base_fixture = data.get("base_fixture")
    if not is_non_empty_string(base_fixture):
        return result(
            [finding("VDD-CLARIFICATION-CASE-PARSE", str(fixture), "base_fixture is required")],
            checks,
        )
    try:
        base = load_json(fixture.parent / base_fixture)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return result(
            [finding("VDD-CLARIFICATION-CASE-PARSE", str(fixture), f"invalid base fixture: {exc}")],
            checks,
        )
    cases = data.get("cases")
    if not isinstance(cases, list):
        return result(
            [finding("VDD-CLARIFICATION-CASE-PARSE", str(fixture), "cases must be a list")],
            checks,
        )
    case_ids = [case.get("id") for case in cases if isinstance(case, dict)]
    required = contract["clarification"]["required_case_ids"]
    missing = [case_id for case_id in required if case_id not in case_ids]
    duplicates = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1}, key=str)
    if missing or duplicates or len(case_ids) != len(cases):
        findings.append(
            finding(
                "VDD-CLARIFICATION-CASE-COVERAGE",
                str(fixture),
                f"missing={missing}, duplicates={duplicates}, malformed={len(cases) - len(case_ids)}",
            )
        )
    for index, case in enumerate(cases):
        case_target = f"{fixture}#cases[{index}]"
        if not isinstance(case, dict) or not is_non_empty_string(case.get("id")):
            continue
        candidate = copy.deepcopy(base)
        mutations = case.get("mutations")
        if not isinstance(mutations, list):
            findings.append(
                finding("VDD-CLARIFICATION-CASE-PARSE", case_target, "mutations must be a list")
            )
            continue
        try:
            for mutation in mutations:
                if not isinstance(mutation, dict) or "value" not in mutation:
                    raise ValueError("each mutation requires path and value")
                _apply_json_pointer(candidate, mutation.get("path"), mutation["value"])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            findings.append(finding("VDD-CLARIFICATION-CASE-PARSE", case_target, str(exc)))
            continue
        case_findings = module.validate_state_data(candidate, case_target)
        observed_rules = {item["rule_id"] for item in case_findings}
        expected_ok = case.get("expected_ok")
        expected_rule = case.get("expected_rule")
        observed_ok = not case_findings
        expected_rules = set() if expected_ok is True else {expected_rule}
        if (
            not isinstance(expected_ok, bool)
            or (expected_ok is False and not is_non_empty_string(expected_rule))
            or (expected_ok is True and expected_rule is not None)
            or observed_ok != expected_ok
            or observed_rules != expected_rules
        ):
            findings.append(
                finding(
                    "VDD-CLARIFICATION-CASE-RESULT",
                    case_target,
                    f"expected ok={expected_ok}, rules={sorted(expected_rules, key=str)}; observed {case_findings}",
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
    if not isinstance(data, dict):
        return result(
            [finding("VDD-SCENARIO-PARSE", str(fixture), "scenario fixture must be a JSON object")],
            checks,
        )

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
        "clarification-pass-fixture",
        "clarification-cases-fixture",
        "clarification-contract-alignment",
        "compliance-scenarios-fixture",
        "pass-result-fixture",
        "stale-result-fixture",
        "compliant-trace-fixture",
        "implementation-first-trace-fixture",
        "write-before-clarification-trace-fixture",
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

    findings.extend(validate_clarification_contract_alignment(skill_root))

    fixture_root = skill_root / "scripts" / "fixtures"
    fixture_expectations = [
        (
            validate_clarification_fixture,
            fixture_root / "clarification-state-pass.json",
            True,
            None,
        ),
        (
            validate_clarification_cases,
            fixture_root / "clarification-cases.json",
            True,
            None,
        ),
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
        (
            validate_trace,
            fixture_root / "compliance-trace-write-before-clarification.jsonl",
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
    parser.add_argument("--clarification-fixture", help="Validate one clarification state JSON fixture")
    parser.add_argument("--clarification-cases", help="Validate clarification mutation cases")
    args = parser.parse_args(argv)

    skill_root = Path(args.skill_root).resolve()
    if args.result_fixture:
        payload = validate_result_fixture(skill_root, Path(args.result_fixture).resolve())
    elif args.scenario_fixture:
        payload = validate_scenarios(skill_root, Path(args.scenario_fixture).resolve())
    elif args.trace_fixture:
        payload = validate_trace(skill_root, Path(args.trace_fixture).resolve())
    elif args.clarification_fixture:
        payload = validate_clarification_fixture(
            skill_root, Path(args.clarification_fixture).resolve()
        )
    elif args.clarification_cases:
        payload = validate_clarification_cases(skill_root, Path(args.clarification_cases).resolve())
    else:
        payload = validate_skill(skill_root)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
