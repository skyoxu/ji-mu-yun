"""Make the single V3 schema-repair attempt group-first and relation-safe.

The public/canonical V3 candidate remains three arrays. Only the one-shot
schema-repair worker uses a grouped transport shape so an Acceptance, its RED
intents, and its slice hint share one obligation set by construction. The
result is deterministically projected back to the canonical arrays before the
normal V3 validators run. This prevents repair-time relational drift without
adding retries or weakening any semantic gate.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping

import semantic_compiler_gate as gate
import semantic_worker_transport_patch as transport
import semantic_worker_v3_domain_patch as v3_domain

sc = gate.sc
_BASE_DOMAIN_TRANSPORT = gate._ORIGINAL_INVOKE_WORKER
_GROUP_STAGE = "v3-schema-repair-group-v1"


def _string_array(*, nonempty: bool = False, enum: list[str] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"type": "string", "minLength": 1}
    if enum:
        item["enum"] = enum
    result: dict[str, Any] = {"type": "array", "items": item}
    if nonempty:
        result["minItems"] = 1
    return result


def _repair_obligations(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    original = payload.get("input")
    if not isinstance(original, Mapping):
        return []
    values = original.get("obligations")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def _group_schema(payload: Mapping[str, Any]) -> dict[str, Any]:
    obligations = _repair_obligations(payload)
    known_ids = sorted(
        str(item["obligation_id"])
        for item in obligations
        if isinstance(item.get("obligation_id"), str) and item.get("obligation_id")
    )
    source_refs = sorted({
        str(ref)
        for item in obligations
        for ref in item.get("source_refs", [])
        if isinstance(ref, str) and ref
    })
    obligation_ids = _string_array(nonempty=True, enum=known_ids or None)

    acceptance = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source_refs": _string_array(nonempty=True, enum=source_refs or None),
            "given": {"type": "string", "minLength": 1},
            "when": {"type": "string", "minLength": 1},
            "then": {"type": "string", "minLength": 1},
            "oracle": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "observable": {"type": "string", "minLength": 1},
                    "expected": {"type": "string", "minLength": 1},
                    "forbidden": _string_array(),
                },
                "required": ["observable", "expected", "forbidden"],
            },
            "assertion_ids": _string_array(nonempty=True),
        },
        "required": ["source_refs", "given", "when", "then", "oracle", "assertion_ids"],
    }
    failure = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "failure_family": {"type": "string", "enum": sorted(sc.FAILURE_FAMILIES)},
            "selector_intent": {"type": "string", "minLength": 1},
            "expected_outcome": {"type": "string", "enum": ["fail"]},
            "failure_id": {"type": "string", "minLength": 1},
        },
        "required": ["failure_family", "selector_intent", "expected_outcome", "failure_id"],
    }
    slice_hint = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "production_owners": _string_array(nonempty=True),
            "verification_lane": {"type": "string", "enum": sorted(sc.LANES)},
            "behavior_change": {"type": "string", "minLength": 1},
            "affected_subjects": _string_array(nonempty=True),
            "state_transition": {"type": "string", "minLength": 1},
            "rollback_scope": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "production_paths": _string_array(nonempty=True),
                    "state_or_schema_compatibility": {"type": "string", "minLength": 1},
                },
                "required": ["production_paths", "state_or_schema_compatibility"],
            },
            "allowed_write_paths": _string_array(),
            "execution_snapshot_paths": _string_array(nonempty=True),
            "planned_new_files": _string_array(),
            "terminal_predicate": {"type": "string", "minLength": 1},
            "forbidden_paths": _string_array(),
            "validation_commands": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
            },
        },
        "required": [
            "production_owners", "verification_lane", "behavior_change", "affected_subjects",
            "state_transition", "rollback_scope", "allowed_write_paths", "execution_snapshot_paths",
            "planned_new_files", "terminal_predicate", "forbidden_paths", "validation_commands",
        ],
    }
    group = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "obligation_ids": obligation_ids,
            "acceptance": acceptance,
            "failure_intents": {"type": "array", "minItems": 1, "items": failure},
            "slice_hint": slice_hint,
        },
        "required": ["obligation_ids", "acceptance", "failure_intents", "slice_hint"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"groups": {"type": "array", "minItems": 1, "items": group}},
        "required": ["groups"],
    }


def _project(value: Mapping[str, Any]) -> dict[str, Any]:
    groups = value.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("V3 group repair must return non-empty groups")
    acceptances: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    hints: list[dict[str, Any]] = []
    for index, raw in enumerate(groups):
        if not isinstance(raw, Mapping):
            raise ValueError(f"V3 group repair group {index} is not object")
        ids = raw.get("obligation_ids")
        acceptance = raw.get("acceptance")
        group_failures = raw.get("failure_intents")
        hint = raw.get("slice_hint")
        if not isinstance(ids, list) or not ids or not isinstance(acceptance, Mapping) or not isinstance(group_failures, list) or not group_failures or not isinstance(hint, Mapping):
            raise ValueError(f"V3 group repair group {index} is incomplete")
        acceptances.append({"obligation_ids": list(ids), **dict(acceptance)})
        hints.append({"obligation_ids": list(ids), **dict(hint)})
        for failure in group_failures:
            if not isinstance(failure, Mapping):
                raise ValueError(f"V3 group repair failure in group {index} is not object")
            failures.append({"obligation_ids": list(ids), **dict(failure)})
    return {"acceptances": acceptances, "failure_intents": failures, "slice_hints": hints}


def _trace_summary(trace: str) -> str:
    text = trace.strip()
    if len(text) <= 2600:
        return text
    return text[:300] + "\n...<trace elided>...\n" + text[-2200:]


def _live_group_repair(*, root: Path, out_dir: Path, payload: Mapping[str, Any], prompt: str) -> Mapping[str, Any]:
    scripts = root / "scripts" / "sc"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from _llm_backend import run_llm_exec, resolve_llm_backend
    except ImportError as exc:
        raise RuntimeError("shared LLM backend is unavailable") from exc

    cache_dir = out_dir / ".compiler-cache"
    cache_path = cache_dir / sc._worker_cache_key(_GROUP_STAGE, payload)
    if cache_path.is_file():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cached, Mapping):
            raise ValueError("V3 group repair cache is malformed")
        return _project(cached)

    work = out_dir / ".compiler-work"
    output = work / f"{_GROUP_STAGE}-last-message.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    schema = _group_schema(payload)
    schema_path = transport._schema_path(out_dir, _GROUP_STAGE, schema)
    grouped_prompt = (
        prompt
        + "\n\nGROUP-FIRST REPAIR CONTRACT: return {\"groups\":[...]}, not the three canonical arrays. "
        "Each group owns exactly one normalized obligation_ids set, exactly one Acceptance body, one or more RED "
        "failure intents, and exactly one slice_hint. Do not repeat obligation_ids inside child objects. Do not create "
        "multiple groups for the same obligation set. The compiler will deterministically project groups back to the "
        "canonical acceptances/failure_intents/slice_hints arrays."
        + "\n\nINPUT:\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    backend = resolve_llm_backend(None)
    extra_args = ["--output-schema", str(schema_path)] if backend == "codex-cli" else []
    code, trace, _argv = run_llm_exec(
        backend=backend,
        root=root,
        prompt=grouped_prompt,
        output_last_message=output,
        timeout_sec=transport._REPAIR_TIMEOUT_SECONDS,
        codex_configs=['model_reasoning_effort="medium"'],
        codex_sandbox="read-only",
        codex_extra_args=extra_args,
    )
    if code != 0 and extra_args and transport._unsupported_output_schema(trace):
        if output.exists():
            output.unlink()
        code, trace, _argv = run_llm_exec(
            backend=backend,
            root=root,
            prompt=grouped_prompt,
            output_last_message=output,
            timeout_sec=transport._REPAIR_TIMEOUT_SECONDS,
            codex_configs=['model_reasoning_effort="medium"'],
            codex_sandbox="read-only",
            codex_extra_args=[],
        )
    if code != 0 or not output.is_file():
        raise RuntimeError(f"semantic worker v3-schema-repair failed: {_trace_summary(trace)}")
    raw = sc._parse_json_output(output.read_text(encoding="utf-8"))
    sc.atomic_json(cache_path, raw)
    return _project(raw)


def group_repair_transport(
    *,
    root,
    out_dir,
    stage: str,
    payload: Mapping[str, Any],
    prompt: str,
    worker_cache: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    if stage != "v3-schema-repair":
        return _BASE_DOMAIN_TRANSPORT(
            root=root, out_dir=out_dir, stage=stage, payload=payload, prompt=prompt, worker_cache=worker_cache
        )
    if worker_cache and stage in worker_cache:
        raw = worker_cache[stage]
        if not isinstance(raw, Mapping):
            raise ValueError("injected V3 repair cache must be object")
        value = _project(raw) if "groups" in raw else dict(raw)
    else:
        value = _live_group_repair(root=root, out_dir=out_dir, payload=payload, prompt=prompt)
    findings = v3_domain._domain_findings(stage, payload, value)
    if findings:
        raise ValueError("V3 frozen-domain validation failed: " + "; ".join(findings))
    return value


def install() -> None:
    gate._ORIGINAL_INVOKE_WORKER = group_repair_transport


install()
