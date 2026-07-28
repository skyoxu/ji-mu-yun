from __future__ import annotations

import hashlib
import json
import re
from typing import Any


LLM_INPUT_IDENTITY_SCHEMA = "sc-llm-review-input-identity.v1"
LLM_RUNTIME_IDENTITY_SCHEMA = "sc-llm-review-runtime-identity.v1"
LLM_REVIEW_METRICS_SCHEMA = "sc-llm-review-metrics.v1"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTITY_KEYS = {
    "schema_version",
    "requested_agents",
    "prompt_set",
    "runtime",
    "delivery_profile",
    "security_profile",
    "threat_model",
    "review_profile",
    "template_sha256",
    "diff_mode",
    "semantic_gate",
    "prompt_max_chars",
    "prompt_budget_gate",
    "skip_agent_prompts",
    "complete",
    "input_identity_hash",
}
_RUNTIME_KEYS = {
    "schema_version",
    "backend",
    "model",
    "reasoning_effort",
    "sandbox",
    "prompt_transport",
    "config_sha256",
    "backend_executable_sha256",
    "backend_version_sha256",
    "backend_adapter_sha256",
    "endpoint_sha256",
    "sdk_version",
    "complete",
    "error_codes",
}
_PIPELINE_METRICS_KEYS = {
    "schema_version",
    "requested_reviewer_count",
    "result_count",
    "status_counts",
    "llm_invocation_count",
    "llm_duration_sec_total",
    "prompt_chars_total",
    "prompt_chars_max",
    "prompt_chars_by_agent",
    "prompt_set_sha256",
    "prompt_truncated_count",
    "prompt_truncated_agents",
    "output_chars_total",
    "runtime",
    "input_identity_hash",
    "input_identity_complete",
    "pipeline_reuse_mode",
    "llm_result_reused",
}


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def is_valid_runtime_identity(value: Any, *, require_complete: bool) -> bool:
    if not isinstance(value, dict) or set(value) != _RUNTIME_KEYS:
        return False
    if value.get("schema_version") != LLM_RUNTIME_IDENTITY_SCHEMA:
        return False
    for key in ("backend", "model", "sandbox", "prompt_transport"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            return False
    if not isinstance(value.get("reasoning_effort"), str) or not isinstance(value.get("sdk_version"), str):
        return False
    for key in ("config_sha256", "backend_executable_sha256", "backend_version_sha256", "backend_adapter_sha256", "endpoint_sha256"):
        field_value = value.get(key)
        if not is_sha256(field_value) and field_value not in {"absent", "not-applicable", "unresolved"}:
            return False
    if not isinstance(value.get("complete"), bool):
        return False
    error_codes = value.get("error_codes")
    if not isinstance(error_codes, list) or not all(isinstance(item, str) and item.strip() for item in error_codes):
        return False
    if require_complete and (value.get("complete") is not True or error_codes):
        return False
    if value.get("complete") is True and error_codes:
        return False
    return True


def is_complete_llm_input_identity(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != _IDENTITY_KEYS:
        return False
    if value.get("schema_version") != LLM_INPUT_IDENTITY_SCHEMA or value.get("complete") is not True:
        return False
    requested_agents = value.get("requested_agents")
    prompt_set = value.get("prompt_set")
    if (
        not isinstance(requested_agents, list)
        or not requested_agents
        or not all(isinstance(item, str) and item.strip() for item in requested_agents)
        or len(set(requested_agents)) != len(requested_agents)
    ):
        return False
    if not isinstance(prompt_set, list):
        return False
    prompt_agents: set[str] = set()
    for row in prompt_set:
        if not isinstance(row, dict) or set(row) != {"agent", "prompt_sha256"}:
            return False
        agent = row.get("agent")
        if not isinstance(agent, str) or not agent.strip() or agent in prompt_agents or not is_sha256(row.get("prompt_sha256")):
            return False
        if agent not in requested_agents:
            return False
        prompt_agents.add(agent)
    if not is_valid_runtime_identity(value.get("runtime"), require_complete=True):
        return False
    for key in ("delivery_profile", "security_profile", "threat_model", "review_profile", "diff_mode", "semantic_gate", "prompt_budget_gate"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            return False
    template_hash = value.get("template_sha256")
    if template_hash != "absent" and not is_sha256(template_hash):
        return False
    if not isinstance(value.get("prompt_max_chars"), int) or isinstance(value.get("prompt_max_chars"), bool) or value["prompt_max_chars"] <= 0:
        return False
    if not isinstance(value.get("skip_agent_prompts"), bool) or not is_sha256(value.get("input_identity_hash")):
        return False
    identity_payload = {key: value[key] for key in _IDENTITY_KEYS - {"complete", "input_identity_hash"}}
    return value.get("input_identity_hash") == canonical_hash(identity_payload)


def validate_pipeline_llm_review_metrics(value: Any, *, base_path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{base_path}: must be object"]
    unexpected = sorted(set(value) - _PIPELINE_METRICS_KEYS)
    missing = sorted(_PIPELINE_METRICS_KEYS - set(value))
    errors.extend(f"{base_path}.{key}: unexpected property" for key in unexpected)
    errors.extend(f"{base_path}.{key}: missing required property" for key in missing)
    if errors:
        return errors
    if value.get("schema_version") != LLM_REVIEW_METRICS_SCHEMA:
        errors.append(f"{base_path}.schema_version: unsupported value")
    for key in (
        "requested_reviewer_count",
        "result_count",
        "llm_invocation_count",
        "prompt_chars_total",
        "prompt_chars_max",
        "prompt_truncated_count",
        "output_chars_total",
    ):
        if not isinstance(value.get(key), int) or isinstance(value.get(key), bool) or value[key] < 0:
            errors.append(f"{base_path}.{key}: must be integer >= 0")
    if not isinstance(value.get("llm_duration_sec_total"), (int, float)) or isinstance(value.get("llm_duration_sec_total"), bool) or value["llm_duration_sec_total"] < 0:
        errors.append(f"{base_path}.llm_duration_sec_total: must be number >= 0")
    for key in ("status_counts", "prompt_chars_by_agent"):
        mapping = value.get(key)
        if not isinstance(mapping, dict) or any(
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
            for name, count in (mapping.items() if isinstance(mapping, dict) else [])
        ):
            errors.append(f"{base_path}.{key}: must map non-empty strings to integers >= 0")
    if not is_sha256(value.get("prompt_set_sha256")):
        errors.append(f"{base_path}.prompt_set_sha256: must be a sha256 hash")
    truncated = value.get("prompt_truncated_agents")
    if not isinstance(truncated, list) or not all(isinstance(item, str) and item.strip() for item in truncated):
        errors.append(f"{base_path}.prompt_truncated_agents: must be an array of non-empty strings")
    if not is_valid_runtime_identity(value.get("runtime"), require_complete=False):
        errors.append(f"{base_path}.runtime: invalid runtime identity")
    identity_hash = value.get("input_identity_hash")
    if identity_hash != "" and not is_sha256(identity_hash):
        errors.append(f"{base_path}.input_identity_hash: must be empty or a sha256 hash")
    if not isinstance(value.get("input_identity_complete"), bool) or not isinstance(value.get("llm_result_reused"), bool):
        errors.append(f"{base_path}: identity and reuse flags must be boolean")
    elif value.get("input_identity_complete") is True and not is_sha256(identity_hash):
        errors.append(f"{base_path}.input_identity_hash: complete identity requires a sha256 hash")
    if value.get("pipeline_reuse_mode") not in {"none", "full-clean-reuse", "deterministic-only-reuse", "sc-test-reuse", "mixed-reuse"}:
        errors.append(f"{base_path}.pipeline_reuse_mode: unsupported value")
    elif value.get("llm_result_reused") is not (value.get("pipeline_reuse_mode") == "full-clean-reuse"):
        errors.append(f"{base_path}.llm_result_reused: inconsistent with pipeline_reuse_mode")
    return errors
