#!/usr/bin/env python3
"""Validate and optionally publish the knowledge context execution plan."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import hmac
import json
import math
import ntpath
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable


PLAN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PLAN_DIR.parents[1]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from context_crypto import canonicalize_jcs, hmac_sha256_base64, sha256_hex


PLAN_DIRECTORY_NAME = PLAN_DIR.name
PLAN_ID = "jimuyun-four-domain-knowledge-context.v1"
ORIGINAL_REQUIREMENTS = Path(
    "execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan.md"
)
ADR_PATH = Path(
    "docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md"
)
MERGE_ADR_PATH = Path(
    "docs/adr/ADR-0046-knowledge-context-protected-integration-merge.md"
)
ADR_INDEX_PATH = Path("docs/architecture/ADR_INDEX_PHASE.md")
K5_BACKEND = "scripts/sc/_llm_backend.py::run_llm_exec"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
KNOWLEDGE_INTERFACE_SCHEMA_NAMES = {
    "knowledge-locator-request.v1.schema.json",
    "knowledge-locator-result.v1.schema.json",
    "knowledge-maintenance-request.v1.schema.json",
    "knowledge-maintenance-result.v1.schema.json",
}

EXPECTED_LIFECYCLE = [
    "draft",
    "plan-ready",
    "implementation-authorized",
    "implementation-complete",
    "acceptance-passed",
    "archived",
]
EXPECTED_INVENTORIES = {
    "inventories/codex-hosted-callers.v1.json": "codex-hosted",
    "inventories/llm-route-engine-callers.v1.json": "llm-route-engine",
    "inventories/python-llm-backend-callers.v1.json": "python-backend",
}
INVENTORY_OUTPUTS = [
    "source-snapshot.v1.json",
    "codex-hosted-callers.v1.json",
    "llm-route-engine-callers.v1.json",
    "python-llm-backend-callers.v1.json",
    "direct-llm-invocation-violations.v1.json",
]


class PlanValidationError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise PlanValidationError(code, detail)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_path(relative: str | Path) -> Path:
    return REPO_ROOT / Path(relative)


def requirement_source_path(relative: str) -> Path:
    repository_prefixes = (
        "docs/",
        "scripts/",
        "execution-plans/",
        "runtime/",
        "PhaseA.Platform/",
        "PhaseA.Platform.Tests/",
        "Game.Core/",
        "Game.Godot/",
    )
    return repo_path(relative) if relative.startswith(repository_prefixes) else PLAN_DIR / relative


def reject_non_finite(value: str) -> None:
    raise PlanValidationError("json_non_finite", f"Non-finite JSON constant: {value}")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PlanValidationError("json_duplicate_key", f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PlanValidationError("json_utf8_read_failed", f"{path}: {exc}") from exc
    require(not raw.startswith("\ufeff"), "json_bom_forbidden", str(path))
    try:
        return json.loads(
            raw,
            object_pairs_hook=unique_object,
            parse_constant=reject_non_finite,
        )
    except PlanValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise PlanValidationError("json_parse_failed", f"{path}: {exc}") from exc


def write_json(path: Path, value: object) -> None:
    rendered = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    path.write_text(rendered, encoding="utf-8", newline="\n")


def json_type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return False


def validate_instance(value: Any, schema: dict[str, Any], location: str = "$") -> None:
    if "const" in schema:
        require(
            value == schema["const"] and type(value) is type(schema["const"]),
            "schema_const_mismatch",
            f"{location}: expected const {schema['const']!r}",
        )
    if "enum" in schema:
        require(value in schema["enum"], "schema_enum_mismatch", f"{location}: {value!r}")

    expected_type = schema.get("type")
    if expected_type is not None:
        options = expected_type if isinstance(expected_type, list) else [expected_type]
        require(
            any(json_type_matches(value, option) for option in options),
            "schema_type_mismatch",
            f"{location}: expected {options}, got {type(value).__name__}",
        )

    if isinstance(value, str) and "pattern" in schema:
        require(
            re.search(str(schema["pattern"]), value) is not None,
            "schema_pattern_mismatch",
            f"{location}: {value!r}",
        )
    if isinstance(value, str) and "minLength" in schema:
        require(
            len(value) >= int(schema["minLength"]),
            "schema_min_length",
            f"{location}: length={len(value)}",
        )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema:
            require(value >= schema["minimum"], "schema_minimum", f"{location}: {value}")
        if "maximum" in schema:
            require(value <= schema["maximum"], "schema_maximum", f"{location}: {value}")

    if isinstance(value, list):
        if "minItems" in schema:
            require(
                len(value) >= int(schema["minItems"]),
                "schema_min_items",
                f"{location}: {len(value)}",
            )
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                validate_instance(item, item_schema, f"{location}[{index}]")
        if schema.get("uniqueItems") is True:
            identities = [
                json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
                for item in value
            ]
            require(len(identities) == len(set(identities)), "schema_unique_items", location)

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            require(key in value, "schema_required_missing", f"{location}.{key}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            require(not extras, "schema_extra_property", f"{location}: {extras}")
        for key, child_schema in properties.items():
            if key in value:
                validate_instance(value[key], child_schema, f"{location}.{key}")

    if "allOf" in schema:
        for branch in schema["allOf"]:
            validate_instance(value, branch, location)

    if "oneOf" in schema:
        successes = 0
        for branch in schema["oneOf"]:
            try:
                validate_instance(value, branch, location)
                successes += 1
            except PlanValidationError:
                pass
        require(successes == 1, "schema_one_of", f"{location}: matched={successes}")


def validate_plan_index_status(index_text: str, state_status: str) -> None:
    matches = re.findall(r"^- Status: ([a-z][a-z-]*)$", index_text, flags=re.MULTILINE)
    require(len(matches) == 1, "plan_index_status_missing", repr(matches))
    require(
        matches[0] == state_status,
        "plan_index_status_mismatch",
        f"index={matches[0]} state={state_status}",
    )


def repo_path_is_within_policy(path: str, allowed_prefixes: list[str]) -> bool:
    candidate = PurePosixPath(path.rstrip("/"))
    return any(
        candidate == boundary or boundary in candidate.parents
        for prefix in allowed_prefixes
        if (boundary := PurePosixPath(prefix.rstrip("/"))) != PurePosixPath(".")
    )


def audit_schema_node(value: Any, location: str) -> None:
    if isinstance(value, dict):
        if value.get("type") == "object" and "properties" in value:
            require(value.get("additionalProperties") is False, "schema_nested_object_open", location)
            properties = value.get("properties")
            required = value.get("required")
            require(isinstance(properties, dict), "schema_nested_properties", location)
            require(isinstance(required, list), "schema_nested_required", location)
            require(set(required).issubset(properties), "schema_nested_required_undeclared", location)
        for key, child in value.items():
            audit_schema_node(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            audit_schema_node(child, f"{location}[{index}]")


def validate_schema_documents() -> dict[str, dict[str, Any]]:
    schema_dir = PLAN_DIR / "schemas"
    schemas: dict[str, dict[str, Any]] = {}
    ids: set[str] = set()
    for path in sorted(schema_dir.glob("*.schema.json"), key=lambda item: item.name):
        schema = load_json(path)
        require(isinstance(schema, dict), "schema_root_not_object", str(path))
        require(schema.get("$schema") == SCHEMA_DIALECT, "schema_dialect_mismatch", str(path))
        schema_id = schema.get("$id")
        require(isinstance(schema_id, str) and schema_id, "schema_id_missing", str(path))
        require(schema_id not in ids, "schema_id_duplicate", schema_id)
        ids.add(schema_id)
        require(schema.get("type") == "object", "schema_root_type", str(path))
        require(schema.get("additionalProperties") is False, "schema_root_open", str(path))
        required = schema.get("required")
        properties = schema.get("properties")
        require(isinstance(required, list) and required, "schema_required_invalid", str(path))
        require(isinstance(properties, dict), "schema_properties_invalid", str(path))
        require(
            set(required).issubset(properties),
            "schema_required_undeclared",
            str(path),
        )
        audit_schema_node(schema, path.name)
        schemas[path.name] = schema
    require(len(schemas) >= 15, "schema_set_incomplete", f"count={len(schemas)}")
    require(
        KNOWLEDGE_INTERFACE_SCHEMA_NAMES.issubset(schemas),
        "knowledge_interface_schema_missing",
        repr(sorted(KNOWLEDGE_INTERFACE_SCHEMA_NAMES - set(schemas))),
    )
    return schemas


def validate_file_conventions() -> None:
    for path in sorted(PLAN_DIR.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix not in {".md", ".json", ".py"}:
            continue
        raw = path.read_bytes()
        require(not raw.startswith(b"\xef\xbb\xbf"), "file_bom_forbidden", str(path))
        require(b"\r\n" not in raw and b"\r" not in raw, "file_line_ending", str(path))
        require(raw.endswith(b"\n"), "file_final_newline", str(path))


def validate_required_artifacts(contract: dict[str, Any]) -> None:
    artifacts = contract.get("required_artifacts")
    require(isinstance(artifacts, list) and artifacts, "required_artifacts_invalid", "implementation contract")
    require(len(artifacts) == len(set(artifacts)), "required_artifact_duplicate", "implementation contract")
    for relative in artifacts:
        require(isinstance(relative, str) and relative, "required_artifact_path", repr(relative))
        candidate = Path(relative)
        require(not candidate.is_absolute() and ".." not in candidate.parts, "required_artifact_escape", relative)
        require((PLAN_DIR / candidate).is_file(), "required_artifact_missing", relative)


def validate_command_registry() -> None:
    registry = load_json(PLAN_DIR / "command-registry.v1.json")
    require(
        registry.get("schema_version") == "jimuyun.knowledge-plan-command-registry.v1",
        "command_registry_version",
        repr(registry.get("schema_version")),
    )
    commands = registry.get("commands")
    require(isinstance(commands, list), "command_registry_commands", repr(commands))
    by_id = {item.get("command_id"): item for item in commands}
    require(len(by_id) == len(commands), "command_registry_duplicate", repr(commands))
    expected = {
        "inventory-build": ["py", "-3", "tools/build_hosted_inventory.py", "--output-dir", "<output>"],
        "reference-vector-build": ["py", "-3", "tools/build_reference_vector.py", "--output", "<output>"],
        "plan-validate": ["py", "-3", "tools/validate_whole_directory.py"],
        "plan-ready-publish": ["py", "-3", "tools/validate_whole_directory.py", "--publish-plan-ready"],
        "report-index-validate": ["py", "-3", "scripts/python/validate_execution_plan_report_index.py"],
    }
    require(set(by_id) == set(expected), "command_registry_set", repr(sorted(by_id)))
    for command_id, argv in expected.items():
        require(by_id[command_id].get("argv") == argv, "command_registry_argv", command_id)


def validate_adr() -> None:
    adr = repo_path(ADR_PATH).read_text(encoding="utf-8")
    required_phrases = [
        "- Status: Accepted",
        "Knowledge Projection is always `derived_cache`",
        "`toolchain`, `phase`, `workspace`, and `marketplace`",
        "Repository Source, Repository Template, Project Instance, and Run Artifact View",
        "permission trust roots",
        "E1 means retrieval-scoped",
        "E2 means context-bound execution",
        "E3 filesystem/process/network/secret isolation is outside this ADR",
        "local committed `refs/heads/main`",
        "one deterministic Locator core",
        "A caller LLM may provide semantic query intent",
        "Extends ADR-0037",
        "Complements ADR-0038",
        "does not supersede ADR-0037 or ADR-0038",
    ]
    for phrase in required_phrases:
        require(phrase in adr, "adr_0044_contract_missing", phrase)
    index = repo_path(ADR_INDEX_PATH).read_text(encoding="utf-8")
    require(ADR_PATH.name in index, "adr_0044_index_missing", str(ADR_INDEX_PATH))
    merge_adr = repo_path(MERGE_ADR_PATH).read_text(encoding="utf-8")
    for phrase in [
        "- Status: Accepted",
        "formal_merge_decision",
        "extends ADR-0044",
        "complements ADR-0037 and ADR-0038",
        "does not\nsupersede ADR-0037, ADR-0038, ADR-0044",
        "waits for BH-HANDOFF",
        "separate explicit write authorization",
    ]:
        require(phrase in merge_adr, "adr_0046_contract_missing", phrase)
    require(MERGE_ADR_PATH.name in index, "adr_0046_index_missing", str(ADR_INDEX_PATH))


def validate_provenance(state: dict[str, Any]) -> None:
    provenance = load_json(PLAN_DIR / "source-provenance.v1.json")
    original = provenance.get("original_requirements")
    require(isinstance(original, dict), "provenance_original_missing", "source-provenance")
    require(original.get("path") == ORIGINAL_REQUIREMENTS.as_posix(), "provenance_original_path", repr(original))
    original_path = repo_path(str(original["path"]))
    require(original_path.is_file(), "original_requirements_missing", str(original_path))
    require(original.get("sha256") == sha256_path(original_path), "provenance_original_drift", str(original_path))

    evolution = provenance.get("evolution_sources")
    require(isinstance(evolution, list) and len(evolution) == 5, "provenance_evolution_count", repr(evolution))
    expected_evolution = {f"docs/know{i}.txt" for i in range(1, 6)}
    require({entry.get("path") for entry in evolution} == expected_evolution, "provenance_evolution_paths", repr(evolution))
    for entry in evolution:
        source = repo_path(str(entry["path"]))
        require(source.is_file(), "provenance_source_missing", str(source))
        require(entry.get("sha256") == sha256_path(source), "provenance_source_drift", str(source))

    accepted = provenance.get("accepted_adr")
    require(isinstance(accepted, dict), "provenance_adr_missing", "source-provenance")
    require(accepted.get("path") == ADR_PATH.as_posix(), "provenance_adr_path", repr(accepted))
    require(accepted.get("sha256") == sha256_path(repo_path(ADR_PATH)), "provenance_adr_drift", str(ADR_PATH))

    state_source = state.get("source_requirements")
    require(isinstance(state_source, dict), "state_source_missing", "plan-state")
    require(state_source.get("path") == ORIGINAL_REQUIREMENTS.as_posix(), "state_source_path", repr(state_source))
    require(state_source.get("sha256") == sha256_path(original_path), "state_source_drift", str(original_path))

    original_text = original_path.read_text(encoding="utf-8")
    for marker in [
        "original-requirements",
        ADR_PATH.as_posix(),
        f"execution-plans/{PLAN_DIRECTORY_NAME}/00-index.md",
        K5_BACKEND,
        "maintain-knowledge-base",
        "Knowledge Locator",
    ]:
        require(marker in original_text, "original_requirements_marker_missing", marker)


def validate_contracts_and_requirements(
    schemas: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = load_json(PLAN_DIR / "implementation-contract.v1.json")
    ledger = load_json(PLAN_DIR / "requirements-ledger.v1.json")
    state = load_json(PLAN_DIR / "plan-state.v1.json")
    resume = load_json(PLAN_DIR / "resume-state.v1.json")

    validate_instance(state, schemas["plan-state.v1.schema.json"], "plan-state")
    validate_instance(ledger, schemas["requirements.v1.schema.json"], "requirements-ledger")

    for item in [contract, ledger, state, resume]:
        require(item.get("plan_id") == PLAN_ID, "plan_id_mismatch", repr(item.get("plan_id")))
    require(contract.get("profile") == "resumable", "profile_mismatch", "implementation contract")
    require(state.get("profile") == "resumable", "profile_mismatch", "plan state")
    require(resume.get("profile") == "resumable", "profile_mismatch", "resume state")
    require(contract.get("lifecycle_states") == EXPECTED_LIFECYCLE, "lifecycle_mismatch", repr(contract.get("lifecycle_states")))
    require(state.get("status") in {"draft", "plan-ready", "implementation-authorized", "implementation-complete"}, "state_over_authorized", str(state.get("status")))
    expected_authorizes = {
        "draft": [],
        "plan-ready": ["plan-ready"],
        "implementation-authorized": ["plan-ready", "implementation-authorized"],
        "implementation-complete": ["plan-ready", "implementation-authorized", "implementation-complete"],
    }[state["status"]]
    require(state.get("authorizes") == expected_authorizes, "state_authorizes_mismatch", repr(state.get("authorizes")))
    validate_plan_index_status(
        (PLAN_DIR / "00-index.md").read_text(encoding="utf-8"),
        state["status"],
    )

    validate_required_artifacts(contract)
    slices = contract.get("slices")
    require(isinstance(slices, list) and slices, "contract_slices_missing", repr(slices))
    for slice_item in slices:
        require(isinstance(slice_item, dict), "contract_slice_shape", repr(slice_item))
        snapshots = slice_item.get("execution_snapshot_paths")
        require(isinstance(snapshots, list) and snapshots, "slice_snapshot_paths_missing", str(slice_item.get("slice_id")))
        for relative in snapshots:
            require(isinstance(relative, str) and relative and not any(token in relative for token in "*?[]"), "slice_snapshot_path_invalid", repr(relative))
            require(repo_path(relative).is_file(), "slice_snapshot_path_missing", relative)
            require(not relative.startswith(("logs/phase-a-innernet/", "runtime/phase-a/")), "slice_snapshot_path_protected", relative)
    require(contract.get("accepted_adr") == ADR_PATH.as_posix(), "contract_adr_mismatch", repr(contract.get("accepted_adr")))
    require(contract.get("formal_merge_decision") == MERGE_ADR_PATH.as_posix(), "contract_merge_adr_mismatch", repr(contract.get("formal_merge_decision")))
    require(contract.get("source_requirements") == ORIGINAL_REQUIREMENTS.as_posix(), "contract_source_mismatch", repr(contract.get("source_requirements")))
    require(contract.get("k5_llm_ambiguity_backend") == K5_BACKEND, "k5_backend_mismatch", repr(contract.get("k5_llm_ambiguity_backend")))
    locator = contract.get("knowledge_locator")
    require(isinstance(locator, dict), "knowledge_locator_contract_missing", repr(locator))
    require(locator.get("canonical_core_count") == 1, "knowledge_locator_core_count", repr(locator))
    require(locator.get("first_adapter") == "cli", "knowledge_locator_first_adapter", repr(locator))
    require(locator.get("request_transport") == "json-stdin", "knowledge_locator_request_transport", repr(locator))
    require(locator.get("response_transport") == "json-stdout", "knowledge_locator_response_transport", repr(locator))
    require(locator.get("output_kind") == "location-recommendation", "knowledge_locator_output_kind", repr(locator))
    require(locator.get("default_llm_enabled") is False, "knowledge_locator_default_llm", repr(locator))
    require(locator.get("requires_source_hash_revalidation") is True, "knowledge_locator_revalidation", repr(locator))
    require(locator.get("low_confidence_status") == "insufficient_match", "knowledge_locator_low_confidence", repr(locator))
    require(locator.get("matched_confidence_levels") == ["high", "medium"], "knowledge_locator_matched_confidence", repr(locator))
    require(locator.get("trusted_path_policy_required") is True, "knowledge_locator_path_policy", repr(locator))
    require(locator.get("result_path_policy_binding") == "required", "knowledge_locator_path_policy_binding", repr(locator))
    require(
        locator.get("retrieval_order")
        == [
            "exact-path-identifier-symbol",
            "rg-lexical",
            "tokenizer-bm25",
            "relation-graph",
            "deterministic-tie-break",
        ],
        "knowledge_locator_retrieval_order",
        repr(locator),
    )
    require(
        set(locator.get("trusted_field_owners", [])) == {"adapter", "server-registry"},
        "knowledge_locator_trusted_owners",
        repr(locator),
    )

    maintenance = contract.get("knowledge_maintenance")
    require(isinstance(maintenance, dict), "knowledge_maintenance_contract_missing", repr(maintenance))
    require(maintenance.get("skill_id") == "maintain-knowledge-base", "knowledge_maintenance_skill_id", repr(maintenance))
    require(maintenance.get("skill_path") == ".agents/skills/maintain-knowledge-base/SKILL.md", "knowledge_maintenance_skill_path", repr(maintenance))
    require(maintenance.get("authority_ref") == "refs/heads/main", "knowledge_maintenance_authority", repr(maintenance))
    require(maintenance.get("implicit_fetch") is False, "knowledge_maintenance_fetch", repr(maintenance))
    require(maintenance.get("dirty_worktree_is_fact_authority") is False, "knowledge_maintenance_dirty_authority", repr(maintenance))
    require(maintenance.get("source_mutation_allowed") is False, "knowledge_maintenance_source_mutation", repr(maintenance))
    require(maintenance.get("log_policy") == "append-only", "knowledge_maintenance_log_policy", repr(maintenance))
    require(
        maintenance.get("before_snapshot_binding") == "request.knowledge_snapshot_id",
        "knowledge_maintenance_snapshot_binding",
        repr(maintenance),
    )
    require(set(maintenance.get("modes", [])) == {"existing-only", "targeted"}, "knowledge_maintenance_modes", repr(maintenance))
    terminal = contract.get("terminal_validation")
    require(isinstance(terminal, dict), "terminal_validation_missing", repr(terminal))
    require(terminal.get("command_id") == "plan-ready-publish", "terminal_validation_command_id", repr(terminal))
    require(terminal.get("authorizes") == ["plan-ready"], "terminal_validation_authorizes", repr(terminal))
    require(
        set(terminal.get("does_not_authorize", []))
        == {"implementation-authorized", "implementation-complete", "acceptance-passed", "archived", "release"},
        "terminal_validation_over_authorizes",
        repr(terminal),
    )
    require(contract.get("production_code_policy", {}).get("k0_k10") == "forbidden", "k0_k10_policy", repr(contract.get("production_code_policy")))
    require(
        contract.get("production_code_policy", {}).get("k11_k13")
        == "blocked_until_bh_handoff_or_formal_merge_supersede_and_explicit_user_authorization",
        "k11_k13_policy",
        repr(contract.get("production_code_policy")),
    )
    live_policy = contract.get("live_state_policy")
    require(isinstance(live_policy, dict) and live_policy and set(live_policy.values()) == {"forbidden"}, "live_state_policy", repr(live_policy))
    protected_gate = contract.get("protected_gate")
    require(isinstance(protected_gate, dict), "protected_gate_missing", repr(protected_gate))
    require(
        set(protected_gate.get("required_any", []))
        == {"BH-HANDOFF", "formal_merge_decision", "formal_supersede_decision"},
        "protected_gate_options",
        repr(protected_gate),
    )
    require(protected_gate.get("requires_explicit_user_write_authorization") is True, "protected_gate_authorization", repr(protected_gate))
    require(protected_gate.get("client_selectable") is False, "protected_gate_client_control", repr(protected_gate))
    require(protected_gate.get("e2_manifest_gate_mode") == "enforce", "protected_gate_e2_manifest_mode", repr(protected_gate))

    slices = contract.get("slices")
    require(isinstance(slices, list), "slices_invalid", repr(slices))
    slice_ids = [item.get("slice_id") for item in slices]
    expected_slice_ids = [f"K{i}" for i in range(15)]
    require(slice_ids == expected_slice_ids, "slice_order_mismatch", repr(slice_ids))
    slice_set = set(slice_ids)
    for index, item in enumerate(slices):
        allowed = item.get("allowed_changes")
        require(isinstance(allowed, dict), "slice_allowed_changes", repr(item))
        production_allowed = item.get("slice_id") == "K12"
        require(allowed.get("production_code") is production_allowed, "slice_production_code_allowed", str(item.get("slice_id")))
        require(allowed.get("live_metadata_db") is False, "slice_live_db_allowed", str(item.get("slice_id")))
        require(allowed.get("live_hosted_workspace") is False, "slice_live_workspace_allowed", str(item.get("slice_id")))
        dependencies = item.get("depends_on")
        require(isinstance(dependencies, list) and set(dependencies).issubset(slice_set), "slice_dependency_unknown", repr(item))
        require(all(int(dep[1:]) < index for dep in dependencies), "slice_dependency_cycle", repr(item))
        if index <= 10:
            require(item.get("production_write_policy") in {"forbidden", "plan-docs-only"}, "slice_k0_k10_write_policy", repr(item))
        elif index == 12:
            require(item.get("production_write_policy") == "authorized_by_ADR-0046_and_explicit_user_authorization", "slice_k12_write_policy", repr(item))
        elif index <= 13:
            require(item.get("production_write_policy") == "blocked_until_bh_handoff_or_merge", "slice_k11_k13_write_policy", repr(item))
        else:
            require(item.get("production_write_policy") == "separate_authorization", "slice_k14_write_policy", repr(item))

    requirements = ledger.get("requirements")
    require(isinstance(requirements, list) and len(requirements) == 52, "requirement_count", f"count={len(requirements) if isinstance(requirements, list) else 'invalid'}")
    requirement_ids = [item.get("requirement_id") for item in requirements]
    require(requirement_ids == [f"KC-{i:03d}" for i in range(1, 53)], "requirement_id_sequence", repr(requirement_ids))
    acceptance_refs = [item.get("acceptance_ref") for item in requirements]
    require(len(acceptance_refs) == len(set(acceptance_refs)), "acceptance_ref_duplicate", repr(acceptance_refs))
    for item in requirements:
        requirement_id = item["requirement_id"]
        owner = item.get("owner_slice")
        require(owner in slice_set, "requirement_slice_unknown", repr(item))
        require(item.get("status") == "active", "requirement_status", repr(item))
        require(str(item.get("acceptance_ref", "")).startswith(f"acceptance://{requirement_id}/"), "requirement_acceptance_ref", repr(item))
        refs = item.get("source_refs")
        require(isinstance(refs, list) and refs, "requirement_source_refs", repr(item))
        for source_ref in refs:
            source_path = requirement_source_path(source_ref)
            exists = source_path.is_dir() if source_ref.endswith("/") else source_path.is_file()
            require(exists, "requirement_source_missing", f"{requirement_id}: {source_ref}")
        owner_number = int(str(owner)[1:])
        policy = item.get("production_write_policy")
        if owner_number <= 10:
            require(policy == "forbidden", "requirement_k0_k10_policy", repr(item))
        elif owner_number <= 13:
            require(policy == "blocked_until_gate", "requirement_k11_k13_policy", repr(item))
        else:
            require(policy == "separate_authorization", "requirement_k14_policy", repr(item))

    require(isinstance(resume.get("bootstrap_review_started"), bool), "bootstrap_review_state_invalid", repr(resume))
    if resume["bootstrap_review_started"]:
        require(isinstance(resume.get("bootstrap_review_last_run"), str), "bootstrap_review_run_missing", repr(resume))
        require(resume.get("bootstrap_review_last_status") in {"blocked", "advisory", "clean"}, "bootstrap_review_status_invalid", repr(resume))
    require(resume.get("production_code_allowed") is False, "resume_production_allowed", repr(resume))
    require(resume.get("live_workspace_allowed") is False, "resume_live_workspace_allowed", repr(resume))
    return contract, ledger, state, resume


def semantic_fixture_result(payload: dict[str, Any]) -> tuple[bool, str | None]:
    if payload.get("enforcement_level") == "E2" and payload.get("gate_mode") != "enforce":
        return False, "e2_requires_enforce_gate"
    e2_evidence = payload.get("e2_readiness_evidence")
    if payload.get("e2_readiness") is True:
        required_e2_evidence = {
            "manifest_persistence",
            "atomic_nonce_consumption",
            "shared_entrypoint_enforced",
            "all_reachable_callsites_enforced",
            "inventory_current",
            "targeted_tests_current",
            "rollback_evidence_current",
        }
        if (
            payload.get("enforcement_level") != "E2"
            or payload.get("gate_mode") != "enforce"
            or not isinstance(e2_evidence, dict)
            or any(e2_evidence.get(key) is not True for key in required_e2_evidence)
        ):
            return False, "e2_readiness_evidence_incomplete"
    if "expand_network" in payload.get("project_restrictions", []):
        return False, "project_profile_expands_permission"
    known_capabilities = set(payload.get("known_capabilities", []))
    if not set(payload.get("effective_capabilities", [])).issubset(known_capabilities):
        return False, "unknown_capability"
    if payload.get("identity_mode") == "project-bound" and payload.get("source_project_id") != payload.get("project_id"):
        return False, "cross_project_source"
    if payload.get("project_snapshot_id") != payload.get("current_project_snapshot_id"):
        return False, "stale_project_snapshot"
    if payload.get("policy_revision") not in payload.get("known_policy_revisions", []):
        return False, "unknown_policy_revision"
    if payload.get("signature_payload_sha256") != payload.get("computed_payload_sha256"):
        return False, "modified_signed_payload"
    if payload.get("nonce_status") != "unused":
        return False, "replayed_nonce"
    if payload.get("required_omitted") is True:
        return False, "required_artifact_omitted"
    if payload.get("recovery_order_contract_id") != "hosted-route-recovery-order.v1":
        return False, "recovery_order_mismatch"
    if payload.get("source_boundary_mode") == "not_applicable" and payload.get("source_boundary_evidence") is not True:
        return False, "source_boundary_disposition_missing"

    workspace = payload.get("workspace_root")
    cache_root = payload.get("cache_root")
    if isinstance(workspace, str) and isinstance(cache_root, str):
        normalized_workspace = ntpath.normcase(ntpath.normpath(workspace.replace("/", "\\")))
        normalized_cache = ntpath.normcase(ntpath.normpath(cache_root.replace("/", "\\")))
        try:
            if ntpath.commonpath([normalized_workspace, normalized_cache]) == normalized_workspace:
                return False, "cache_root_escape"
        except ValueError:
            pass
    if payload.get("inventory_source_snapshot_id") != payload.get("release_source_snapshot_id"):
        return False, "inventory_source_drift"
    return True, None


def validate_fixtures(schemas: dict[str, dict[str, Any]]) -> None:
    fixture_schema = schemas["fixture-case.v1.schema.json"]
    index = load_json(PLAN_DIR / "fixtures/fixture-cases.v1.json")
    require(index.get("schema_version") == "jimuyun.knowledge-fixture-index.v1", "fixture_index_version", repr(index))
    cases = index.get("cases")
    require(isinstance(cases, list) and cases, "fixture_index_empty", repr(index))
    fixture_ids: set[str] = set()
    indexed_paths: set[str] = set()
    kinds: set[str] = set()
    for case in cases:
        fixture_id = case.get("fixture_id")
        relative = case.get("path")
        require(isinstance(fixture_id, str) and fixture_id not in fixture_ids, "fixture_id_duplicate", repr(fixture_id))
        require(isinstance(relative, str) and relative not in indexed_paths, "fixture_path_duplicate", repr(relative))
        fixture_ids.add(fixture_id)
        indexed_paths.add(relative)
        path = PLAN_DIR / relative
        require(path.is_file(), "fixture_missing", str(relative))
        fixture = load_json(path)
        validate_instance(fixture, fixture_schema, f"fixture:{fixture_id}")
        for key in ["fixture_id", "kind", "expected_result", "expected_failure_code"]:
            require(case.get(key) == fixture.get(key), "fixture_index_mismatch", f"{fixture_id}: {key}")
        kind = fixture["kind"]
        kinds.add(kind)
        passed, failure_code = semantic_fixture_result(fixture["payload"])
        if kind == "positive":
            require(passed and failure_code is None, "positive_fixture_failed", f"{fixture_id}: {failure_code}")
            require(fixture["expected_result"] == "pass" and fixture["expected_failure_code"] is None, "positive_fixture_expectation", fixture_id)
        else:
            require(not passed, "negative_fixture_passed", fixture_id)
            require(failure_code == fixture["expected_failure_code"], "negative_fixture_failure_code", f"{fixture_id}: expected={fixture['expected_failure_code']} actual={failure_code}")

    require(kinds == {"positive", "negative"}, "fixture_kind_coverage", repr(kinds))
    actual_paths = {
        path.relative_to(PLAN_DIR).as_posix()
        for fixture_root in [PLAN_DIR / "fixtures/positive", PLAN_DIR / "fixtures/negative"]
        for path in fixture_root.glob("*.json")
    }
    require(actual_paths == indexed_paths, "fixture_index_coverage", f"indexed={sorted(indexed_paths)} actual={sorted(actual_paths)}")
    require("valid-inventory-snapshot" in fixture_ids, "inventory_positive_fixture_missing", repr(fixture_ids))


def locator_fixture_failure(
    request: dict[str, Any], result: dict[str, Any]
) -> str | None:
    trusted = request["trusted_envelope"]
    if trusted["owner"] == "llm":
        return "llm_controls_trusted_envelope"
    if request["request_id"] != result["request_id"]:
        return "locator_request_identity_mismatch"

    expected_source = {
        "authority_ref": trusted["authority_ref"],
        "source_commit": trusted["source_commit"],
        "source_snapshot_id": trusted["source_snapshot_id"],
    }
    if result["source_identity"] != expected_source:
        return "locator_source_identity_mismatch"

    path_policy = trusted["path_policy"]
    expected_path_policy = {
        "policy_id": path_policy["policy_id"],
        "policy_revision": path_policy["policy_revision"],
        "policy_sha256": path_policy["policy_sha256"],
    }
    if result["path_policy_identity"] != expected_path_policy:
        return "locator_path_policy_identity_mismatch"

    selected_domain = result["selected_domain"]
    if selected_domain is not None and selected_domain not in trusted["allowed_domains"]:
        return "locator_domain_outside_envelope"

    reads = result["recommended_reads"]
    if len(reads) > trusted["max_results"]:
        return "locator_result_budget_exceeded"
    if [item["rank"] for item in reads] != list(range(1, len(reads) + 1)):
        return "locator_rank_sequence"
    if any(item["line_end"] < item["line_start"] for item in reads):
        return "locator_anchor_range"
    if any(
        not repo_path_is_within_policy(item["path"], path_policy["allowed_path_prefixes"])
        for item in reads
    ):
        return "locator_path_outside_policy"

    status = result["status"]
    confidence = result["confidence"]["level"]
    if status == "matched":
        if not reads or selected_domain is None or result["next_action"] != "read-and-verify":
            return "locator_matched_contract"
        if confidence not in {"high", "medium"}:
            return "locator_matched_confidence"
    elif status == "insufficient_match":
        if result["next_action"] != "refine-query" or confidence != "insufficient":
            return "locator_insufficient_contract"
    elif status == "blocked":
        if reads or result["next_action"] != "denied" or confidence != "blocked":
            return "locator_blocked_contract"
    return None


def maintenance_fixture_failure(
    request: dict[str, Any], result: dict[str, Any]
) -> str | None:
    if request["request_id"] != result["request_id"] or request["mode"] != result["mode"]:
        return "maintenance_request_identity_mismatch"
    if result["before_snapshot_id"] != request["knowledge_snapshot_id"]:
        return "maintenance_before_snapshot_mismatch"

    authority = request["authority"]
    if authority["dirty_worktree_authority"] is True:
        return "maintenance_dirty_worktree_authority"
    if authority["implicit_fetch"] is True:
        return "maintenance_implicit_fetch"
    if request["source_write_policy"] != "forbidden" or result["source_mutation_count"] != 0:
        return "maintenance_source_mutation"
    if request["append_only_log"] is not True or result["log"]["append_only"] is not True:
        return "maintenance_log_not_append_only"
    if result["main_commit"] != authority["main_commit"] or result["log"]["main_commit"] != authority["main_commit"]:
        return "maintenance_main_commit_mismatch"

    mode = request["mode"]
    target = request["target"]
    entries = result["entries"]
    if mode == "existing-only":
        if (
            request["discovery_policy"] != "existing-entries-only"
            or target["kind"] != "none"
            or target["repo_relative_path"] is not None
            or target["snapshot_kind"] != "none"
            or target["content_sha256"] is not None
        ):
            return "maintenance_existing_only_target"
        if any(item["disposition"] in {"added", "candidate"} for item in entries):
            return "existing_only_discovery"
    else:
        if (
            request["discovery_policy"] != "target-scoped"
            or target["kind"] == "none"
            or target["repo_relative_path"] is None
            or target["snapshot_kind"] == "none"
            or target["content_sha256"] is None
        ):
            return "maintenance_target_required"

    for entry in entries:
        if entry["source_snapshot_kind"] == "worktree" and entry["authority_status"] != "provisional":
            return "worktree_fact_promotion"
        if entry["authority_status"] == "provisional" and entry["disposition"] != "candidate":
            return "maintenance_provisional_disposition"
        if entry["authority_status"] == "main-backed" and entry["disposition"] == "candidate":
            return "maintenance_main_candidate"
    return None


def knowledge_interface_fixture_failure(
    fixture: dict[str, Any], schemas: dict[str, dict[str, Any]]
) -> str | None:
    operation = fixture["operation"]
    request = fixture["request"]
    result = fixture["result"]
    try:
        if operation == "locator":
            validate_instance(
                request,
                schemas["knowledge-locator-request.v1.schema.json"],
                f"knowledge-fixture:{fixture['fixture_id']}.request",
            )
            validate_instance(
                result,
                schemas["knowledge-locator-result.v1.schema.json"],
                f"knowledge-fixture:{fixture['fixture_id']}.result",
            )
            return locator_fixture_failure(request, result)
        if operation == "maintenance":
            validate_instance(
                request,
                schemas["knowledge-maintenance-request.v1.schema.json"],
                f"knowledge-fixture:{fixture['fixture_id']}.request",
            )
            validate_instance(
                result,
                schemas["knowledge-maintenance-result.v1.schema.json"],
                f"knowledge-fixture:{fixture['fixture_id']}.result",
            )
            return maintenance_fixture_failure(request, result)
    except PlanValidationError as exc:
        return exc.code
    return "knowledge_interface_operation_unknown"


def validate_knowledge_interface_fixtures(
    schemas: dict[str, dict[str, Any]]
) -> None:
    index = load_json(PLAN_DIR / "fixtures/knowledge-interface-cases.v1.json")
    require(
        set(index) == {"schema_version", "cases"},
        "knowledge_fixture_index_shape",
        repr(sorted(index)),
    )
    require(
        index["schema_version"] == "jimuyun.knowledge-interface-fixture-index.v1",
        "knowledge_fixture_index_version",
        repr(index["schema_version"]),
    )
    cases = index["cases"]
    require(isinstance(cases, list) and cases, "knowledge_fixture_index_empty", repr(cases))

    fixture_ids: set[str] = set()
    indexed_paths: set[str] = set()
    coverage: set[tuple[str, str]] = set()
    case_keys = {
        "fixture_id",
        "kind",
        "operation",
        "path",
        "expected_result",
        "expected_failure_code",
    }
    fixture_keys = {
        "schema_version",
        "fixture_id",
        "kind",
        "operation",
        "expected_result",
        "expected_failure_code",
        "request",
        "result",
    }
    for case in cases:
        require(isinstance(case, dict) and set(case) == case_keys, "knowledge_fixture_case_shape", repr(case))
        fixture_id = case["fixture_id"]
        relative = case["path"]
        require(isinstance(fixture_id, str) and fixture_id not in fixture_ids, "knowledge_fixture_id_duplicate", repr(fixture_id))
        require(isinstance(relative, str) and relative not in indexed_paths, "knowledge_fixture_path_duplicate", repr(relative))
        fixture_ids.add(fixture_id)
        indexed_paths.add(relative)

        path = PLAN_DIR / relative
        require(path.is_file(), "knowledge_fixture_missing", relative)
        fixture = load_json(path)
        require(isinstance(fixture, dict) and set(fixture) == fixture_keys, "knowledge_fixture_shape", fixture_id)
        require(
            fixture["schema_version"] == "jimuyun.knowledge-interface-fixture.v1",
            "knowledge_fixture_version",
            fixture_id,
        )
        for key in case_keys - {"path"}:
            require(case[key] == fixture[key], "knowledge_fixture_index_mismatch", f"{fixture_id}: {key}")

        kind = fixture["kind"]
        operation = fixture["operation"]
        require(kind in {"positive", "negative"}, "knowledge_fixture_kind", fixture_id)
        require(operation in {"locator", "maintenance"}, "knowledge_fixture_operation", fixture_id)
        coverage.add((operation, kind))
        failure_code = knowledge_interface_fixture_failure(fixture, schemas)
        if kind == "positive":
            require(fixture["expected_result"] == "pass" and fixture["expected_failure_code"] is None, "knowledge_positive_expectation", fixture_id)
            require(failure_code is None, "knowledge_positive_fixture_failed", f"{fixture_id}: {failure_code}")
            if operation == "maintenance":
                require(fixture["result"]["log"]["failure_code"] is None, "knowledge_positive_log_failure", fixture_id)
        else:
            require(fixture["expected_result"] == "fail" and isinstance(fixture["expected_failure_code"], str), "knowledge_negative_expectation", fixture_id)
            require(failure_code == fixture["expected_failure_code"], "knowledge_negative_failure_code", f"{fixture_id}: expected={fixture['expected_failure_code']} actual={failure_code}")
            if operation == "maintenance":
                require(fixture["result"]["log"]["failure_code"] == failure_code, "knowledge_negative_log_failure", fixture_id)

    require(
        coverage == {
            ("locator", "positive"),
            ("locator", "negative"),
            ("maintenance", "positive"),
            ("maintenance", "negative"),
        },
        "knowledge_fixture_coverage",
        repr(coverage),
    )
    fixture_root = PLAN_DIR / "fixtures/knowledge-interface"
    actual_paths = {
        path.relative_to(PLAN_DIR).as_posix()
        for path in fixture_root.rglob("*.json")
    }
    require(
        actual_paths == indexed_paths,
        "knowledge_fixture_index_coverage",
        f"indexed={sorted(indexed_paths)} actual={sorted(actual_paths)}",
    )


def validate_reference_vector(schemas: dict[str, dict[str, Any]]) -> None:
    relative = "fixtures/reference-vectors/jcs-hmac-reference-vector.v1.json"
    path = PLAN_DIR / relative
    vector = load_json(path)
    validate_instance(
        vector,
        schemas["context-envelope-reference-vector.v1.schema.json"],
        "context-envelope-reference-vector",
    )
    manifest = vector["manifest"]
    validate_instance(
        manifest,
        schemas["hosted-context-manifest.v1.schema.json"],
        "hosted-context-manifest",
    )

    try:
        key = base64.b64decode(vector["test_key_base64"], validate=True)
        expected_canonical = base64.b64decode(
            vector["expected_signed_payload_canonical_utf8_base64"], validate=True
        )
    except (ValueError, TypeError) as exc:
        raise PlanValidationError("reference_vector_base64", str(exc)) from exc

    canonical = canonicalize_jcs(manifest["signed_payload"])
    payload_sha256 = sha256_hex(canonical)
    signature = hmac_sha256_base64(key, canonical)
    require(canonical == expected_canonical, "reference_vector_canonical_bytes", relative)
    require(payload_sha256 == vector["expected_signed_payload_sha256"], "reference_vector_payload_sha256", relative)
    require(hmac.compare_digest(signature, vector["expected_hmac_base64"]), "reference_vector_hmac", relative)
    require(manifest["signature"]["signed_payload_sha256"] == payload_sha256, "manifest_signature_payload_sha256", relative)
    require(hmac.compare_digest(manifest["signature"]["hmac_base64"], signature), "manifest_signature_hmac", relative)

    tampered = copy.deepcopy(manifest["signed_payload"])
    tampered["operation"] = str(tampered["operation"]) + "-tampered"
    tampered_canonical = canonicalize_jcs(tampered)
    require(tampered_canonical != canonical, "reference_vector_tamper_bytes_unchanged", relative)
    require(sha256_hex(tampered_canonical) != payload_sha256, "reference_vector_tamper_hash_unchanged", relative)
    require(
        not hmac.compare_digest(hmac_sha256_base64(key, tampered_canonical), signature),
        "reference_vector_tamper_hmac_unchanged",
        relative,
    )

    builder = PLAN_DIR / "tools/build_reference_vector.py"
    with tempfile.TemporaryDirectory(prefix="knowledge-vector-validate-") as temporary:
        rebuilt = Path(temporary) / "jcs-hmac-reference-vector.v1.json"
        result = subprocess.run(
            [sys.executable, str(builder), "--output", str(rebuilt)],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )
        require(result.returncode == 0, "reference_vector_rebuild_failed", result.stdout + result.stderr)
        require(rebuilt.read_bytes() == path.read_bytes(), "reference_vector_rebuild_drift", relative)


def validate_inventory_entry(item: dict[str, Any], snapshot_files: dict[str, dict[str, Any]]) -> None:
    required = {
        "callsite_id",
        "path",
        "line",
        "column",
        "symbol",
        "source_sha256",
        "callsite_fingerprint",
        "reachability_status",
        "migration_status",
        "context_envelope_status",
    }
    require(required.issubset(item), "inventory_callsite_shape", repr(item))
    relative = item["path"]
    require(relative in snapshot_files, "inventory_source_not_snapshotted", str(relative))
    require(item["source_sha256"] == snapshot_files[relative]["sha256"], "inventory_source_hash_mismatch", str(relative))
    require(repo_path(relative).is_file(), "inventory_source_missing", str(relative))
    require(item["source_sha256"] == sha256_path(repo_path(relative)), "inventory_source_drift", str(relative))
    for status_key in ["reachability_status", "migration_status", "context_envelope_status"]:
        require(item[status_key] == "unassessed", "inventory_status_premature", f"{relative}: {status_key}")
    require(re.fullmatch(r"[0-9a-f]{64}", str(item["callsite_fingerprint"])) is not None, "inventory_fingerprint", str(relative))


def validate_inventories(schemas: dict[str, dict[str, Any]]) -> None:
    snapshot = load_json(PLAN_DIR / "inventories/source-snapshot.v1.json")
    validate_instance(snapshot, schemas["source-snapshot.v1.schema.json"], "source-snapshot")
    snapshot_id = snapshot["source_snapshot_id"]
    snapshot_files_list = snapshot["files"]
    require(isinstance(snapshot_files_list, list) and snapshot_files_list, "source_snapshot_empty", "inventories/source-snapshot.v1.json")
    snapshot_files = {item["path"]: item for item in snapshot_files_list}
    require(len(snapshot_files) == len(snapshot_files_list), "source_snapshot_duplicate_path", "inventories/source-snapshot.v1.json")
    for relative, item in snapshot_files.items():
        path = repo_path(relative)
        require(path.is_file(), "source_snapshot_file_missing", relative)
        require(item.get("sha256") == sha256_path(path), "source_snapshot_file_drift", relative)

    all_callsite_ids: set[str] = set()
    for relative, family in EXPECTED_INVENTORIES.items():
        inventory = load_json(PLAN_DIR / relative)
        validate_instance(inventory, schemas["inventory.v1.schema.json"], relative)
        require(inventory.get("entrypoint_family") == family, "inventory_family", relative)
        require(inventory.get("source_snapshot_id") == snapshot_id, "inventory_snapshot_mismatch", relative)
        callers = inventory.get("callers")
        require(isinstance(callers, list) and callers, "inventory_callers_empty", relative)
        for item in callers + inventory.get("excluded_candidates", []):
            validate_inventory_entry(item, snapshot_files)
            callsite_id = item["callsite_id"]
            require(callsite_id not in all_callsite_ids, "inventory_callsite_duplicate", callsite_id)
            all_callsite_ids.add(callsite_id)

    direct = load_json(PLAN_DIR / "inventories/direct-llm-invocation-violations.v1.json")
    validate_instance(direct, schemas["direct-llm-invocation-violations.v1.schema.json"], "direct-invocations")
    require(direct.get("source_snapshot_id") == snapshot_id, "direct_inventory_snapshot_mismatch", repr(direct.get("source_snapshot_id")))
    require(direct.get("violations") == [], "direct_llm_invocation_bypass", repr(direct.get("violations")))
    for item in direct.get("excluded_candidates", []):
        validate_inventory_entry(item, snapshot_files)

    ledger_path = PLAN_DIR / "inventories/hosted-callsite-migration-ledger.v1.json"
    ledger = load_json(ledger_path)
    validate_instance(ledger, schemas["hosted-callsite-migration-ledger.v1.schema.json"], "migration-ledger")
    require(ledger.get("source_snapshot_id") == snapshot_id, "migration_ledger_snapshot_mismatch", repr(ledger.get("source_snapshot_id")))
    ledger_entries = ledger.get("entries")
    require(isinstance(ledger_entries, list), "migration_ledger_entries", repr(ledger_entries))
    ledger_ids = [item.get("callsite_id") for item in ledger_entries]
    require(len(ledger_ids) == len(set(ledger_ids)), "migration_ledger_duplicate", repr(ledger_ids))
    require(set(ledger_ids) == all_callsite_ids, "migration_ledger_callsite_closure", repr(sorted(set(ledger_ids) ^ all_callsite_ids)))
    for item in ledger_entries:
        reachability = item["reachability"]
        if reachability == "hosted-route":
            require(item["routes"], "migration_ledger_hosted_route_missing", repr(item))
            require(
                (item["initial_gate_mode"], item["migration_status"]) in {("legacy", "pending"), ("enforce", "enforced")},
                "migration_ledger_hosted_gate_state",
                repr(item),
            )
        else:
            require(item["routes"] == [], "migration_ledger_nonhosted_routes", repr(item))
            require(item["initial_gate_mode"] == "not-applicable", "migration_ledger_nonhosted_mode", repr(item))
            require(item["migration_status"] == "excluded", "migration_ledger_nonhosted_status", repr(item))
        require(reachability != "unknown", "migration_ledger_unknown_reachability", repr(item))

    builder = PLAN_DIR / "tools/build_hosted_inventory.py"
    with tempfile.TemporaryDirectory(prefix="knowledge-inventory-validate-") as temporary:
        output_dir = Path(temporary)
        result = subprocess.run(
            [sys.executable, str(builder), "--repo-root", str(REPO_ROOT), "--output-dir", str(output_dir)],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )
        require(result.returncode == 0, "inventory_rebuild_failed", result.stdout + result.stderr)
        for filename in INVENTORY_OUTPUTS:
            expected = PLAN_DIR / "inventories" / filename
            actual = output_dir / filename
            require(actual.is_file(), "inventory_rebuild_output_missing", filename)
            require(expected.read_bytes() == actual.read_bytes(), "inventory_rebuild_drift", filename)

        actual_ledger = output_dir / "hosted-callsite-migration-ledger.v1.json"
        ledger_result = subprocess.run(
            [sys.executable, str(PLAN_DIR / "tools/build_hosted_migration_ledger.py"), "--repo-root", str(REPO_ROOT), "--inventory-dir", str(output_dir), "--output", str(actual_ledger)],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )
        require(ledger_result.returncode == 0, "migration_ledger_rebuild_failed", ledger_result.stdout + ledger_result.stderr)
        require(ledger_path.read_bytes() == actual_ledger.read_bytes(), "migration_ledger_rebuild_drift", "hosted-callsite-migration-ledger.v1.json")


def validate_report_index() -> None:
    path = REPO_ROOT / "execution-plans/95-implementation-report-index.v1.json"
    index = load_json(path)
    entries = index.get("entries")
    require(isinstance(entries, list), "report_index_entries", str(path))
    expected = {
        "plan_directory": PLAN_DIRECTORY_NAME,
        "report_filename": "95-implementation-evolution-and-completion-report.md",
    }
    require(expected in entries, "report_index_entry_missing", repr(expected))
    directories = [entry.get("plan_directory") for entry in entries]
    require(directories == sorted(directories), "report_index_not_sorted", repr(directories))
    require(len(directories) == len(set(directories)), "report_index_duplicate", repr(directories))


def validate_git_head(state: dict[str, Any]) -> None:
    baseline = state.get("git_head")
    require(isinstance(baseline, str) and baseline, "git_head_missing", repr(baseline))
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    require(result.returncode in {0, 1}, "git_head_read_failed", result.stderr)
    require(result.returncode == 0, "git_baseline_not_ancestor", f"baseline={baseline}")


def run_plan_tests() -> None:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tools/tests", "-p", "test_*.py"],
        cwd=PLAN_DIR,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=env,
        check=False,
    )
    require(result.returncode == 0, "plan_tests_failed", result.stdout + result.stderr)


def publish_plan_ready(state: dict[str, Any]) -> dict[str, Any]:
    status = state.get("status")
    require(status in {"draft", "plan-ready"}, "publish_transition_invalid", str(status))
    if status == "draft":
        state["status"] = "plan-ready"
        state["authorizes"] = ["plan-ready"]
        history = state.setdefault("status_history", [])
        history.append(
            {
                "status": "plan-ready",
                "reason": "Whole-directory composition validation passed.",
                "evidence": ["tools/validate_whole_directory.py --publish-plan-ready"],
            }
        )
        write_json(PLAN_DIR / "plan-state.v1.json", state)
    return state


def validate_directory(run_tests: bool = True) -> dict[str, Any]:
    validate_file_conventions()
    schemas = validate_schema_documents()
    contract, _ledger, state, resume = validate_contracts_and_requirements(schemas)
    validate_command_registry()
    validate_adr()
    validate_provenance(state)
    validate_fixtures(schemas)
    validate_knowledge_interface_fixtures(schemas)
    validate_reference_vector(schemas)
    validate_inventories(schemas)
    validate_report_index()
    validate_git_head(state)
    if run_tests:
        run_plan_tests()
    return {"schemas": schemas, "contract": contract, "state": state, "resume": resume}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish-plan-ready", action="store_true")
    parser.add_argument("--skip-tests", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = validate_directory(run_tests=not args.skip_tests)
        state = result["state"]
        if args.publish_plan_ready:
            state = publish_plan_ready(state)
            validate_instance(
                state,
                result["schemas"]["plan-state.v1.schema.json"],
                "plan-state",
            )
        print(
            "WHOLE_DIRECTORY PASS "
            f"status={state['status']} publish={str(args.publish_plan_ready).lower()} "
            f"implementation_authorized={'true' if state['status'] == 'implementation-authorized' else 'false'} "
            f"bootstrap_review_started={str(result['resume']['bootstrap_review_started']).lower()}"
        )
        return 0
    except PlanValidationError as exc:
        print(f"WHOLE_DIRECTORY FAIL code={exc.code} detail={exc.detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
