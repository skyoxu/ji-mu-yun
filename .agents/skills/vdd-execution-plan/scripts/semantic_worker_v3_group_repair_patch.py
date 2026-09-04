"""Group-first V3 schema repair with atomic canonical projection.

The repair worker authors shared implementation contexts plus an exact
one-key-per-frozen-obligation assignment object. Multiple obligations may reuse
one context (owner/lane/failure mechanism/selector lifecycle), so path ownership
is authored once instead of being re-guessed independently. Before the canonical
V3 arrays are returned, assignments are deterministically projected to one
Acceptance, one slice hint, and cloned RED intents per obligation. Thus
Acceptance remains atomic while V6 may later merge compatible atomic Acceptances
into one cohesive implementation slice. Legacy group arrays remain readable for
cache/test compatibility, but overlapping legacy membership stays fail-closed.
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
_GROUP_STAGE = "v3-schema-repair-group-v3-shared-context-atomic-projection"


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


def _obligation_refs(payload: Mapping[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in _repair_obligations(payload):
        oid = item.get("obligation_id")
        refs = item.get("source_refs")
        if isinstance(oid, str) and oid and isinstance(refs, list):
            result[oid] = sorted({str(ref) for ref in refs if isinstance(ref, str) and ref})
    return result


def _group_schema(payload: Mapping[str, Any]) -> dict[str, Any]:
    obligations = _repair_obligations(payload)
    known_ids = sorted({
        str(item["obligation_id"])
        for item in obligations
        if isinstance(item.get("obligation_id"), str) and item.get("obligation_id")
    })
    source_refs = sorted({
        str(ref)
        for item in obligations
        for ref in item.get("source_refs", [])
        if isinstance(ref, str) and ref
    })
    group_id_schema: dict[str, Any] = {"type": "string", "minLength": 1}
    assignment_target_schema: dict[str, Any] = {"type": "string", "minLength": 1}
    if known_ids:
        group_id_schema["enum"] = known_ids
        assignment_target_schema["enum"] = known_ids

    acceptance = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "source_refs": _string_array(nonempty=True, enum=source_refs or None),
            "given": {"type": "string", "minLength": 1},
            "when": {"type": "string", "minLength": 1},
            "then": {"type": "string", "minLength": 1},
            "oracle": {
                "type": "object", "additionalProperties": False,
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
        "type": "object", "additionalProperties": False,
        "properties": {
            "failure_family": {"type": "string", "enum": sorted(sc.FAILURE_FAMILIES)},
            "selector_intent": {"type": "string", "minLength": 1},
            "expected_outcome": {"type": "string", "enum": ["fail"]},
            "failure_id": {"type": "string", "minLength": 1},
        },
        "required": ["failure_family", "selector_intent", "expected_outcome", "failure_id"],
    }
    slice_hint = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "production_owners": _string_array(nonempty=True),
            "verification_lane": {"type": "string", "enum": sorted(sc.LANES)},
            "behavior_change": {"type": "string", "minLength": 1},
            "affected_subjects": _string_array(nonempty=True),
            "state_transition": {"type": "string", "minLength": 1},
            "rollback_scope": {
                "type": "object", "additionalProperties": False,
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
                "type": "array", "minItems": 1,
                "items": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
            },
        },
        "required": [
            "production_owners", "verification_lane", "behavior_change", "affected_subjects",
            "state_transition", "rollback_scope", "allowed_write_paths", "execution_snapshot_paths",
            "planned_new_files", "terminal_predicate", "forbidden_paths", "validation_commands",
        ],
    }
    group = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "group_id": group_id_schema,
            "acceptance": acceptance,
            "failure_intents": {"type": "array", "minItems": 1, "items": failure},
            "slice_hint": slice_hint,
        },
        "required": ["group_id", "acceptance", "failure_intents", "slice_hint"],
    }
    assignments = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            oid: dict(assignment_target_schema)
            for oid in known_ids
        },
        "required": known_ids,
    }
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "groups": {"type": "array", "minItems": 1, "items": group},
            "obligation_group_assignments": assignments,
        },
        "required": ["groups", "obligation_group_assignments"],
    }


def _group_body(raw: Mapping[str, Any], index: int) -> tuple[Mapping[str, Any], list[Any], Mapping[str, Any]]:
    acceptance = raw.get("acceptance")
    group_failures = raw.get("failure_intents")
    hint = raw.get("slice_hint")
    if not isinstance(acceptance, Mapping) or not isinstance(group_failures, list) or not group_failures or not isinstance(hint, Mapping):
        raise ValueError(f"V3 group repair group {index} is incomplete")
    return acceptance, group_failures, hint


def _append_atomic(
    *,
    oid: str,
    acceptance: Mapping[str, Any],
    group_failures: list[Any],
    hint: Mapping[str, Any],
    group_index: int,
    refs_by_oid: Mapping[str, list[str]] | None,
    acceptances: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    hints: list[dict[str, Any]],
) -> None:
    atomic_acceptance = dict(acceptance)
    if refs_by_oid is not None and oid in refs_by_oid:
        atomic_acceptance["source_refs"] = list(refs_by_oid[oid])
    acceptances.append({"obligation_ids": [oid], **atomic_acceptance})
    hints.append({"obligation_ids": [oid], **dict(hint)})
    for failure in group_failures:
        if not isinstance(failure, Mapping):
            raise ValueError(f"V3 group repair failure in group {group_index} is not object")
        failures.append({"obligation_ids": [oid], **dict(failure)})


def _project_exact_assignments(
    value: Mapping[str, Any],
    groups: list[Any],
    *,
    refs_by_oid: Mapping[str, list[str]] | None,
) -> dict[str, Any]:
    raw_assignments = value.get("obligation_group_assignments")
    if not isinstance(raw_assignments, Mapping) or not raw_assignments:
        raise ValueError("V3 group repair assignments must be a non-empty object")
    if any(
        not isinstance(oid, str) or not oid.strip()
        or not isinstance(group_id, str) or not group_id.strip()
        for oid, group_id in raw_assignments.items()
    ):
        raise ValueError("V3 group repair assignments must map non-empty obligation IDs to non-empty group IDs")
    assignments = {
        str(oid).strip(): str(group_id).strip()
        for oid, group_id in raw_assignments.items()
    }
    if len(assignments) != len(raw_assignments):
        raise ValueError("V3 group repair assignments contain normalized duplicate obligation IDs")

    if refs_by_oid is not None:
        expected = set(refs_by_oid)
        actual = set(assignments)
        if actual != expected:
            details = []
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            if missing:
                details.append("missing=" + ",".join(missing))
            if extra:
                details.append("unknown=" + ",".join(extra))
            raise ValueError("V3 group repair assignments differ from frozen obligations: " + ";".join(details))

    group_by_id: dict[str, tuple[int, Mapping[str, Any], list[Any], Mapping[str, Any]]] = {}
    for index, raw in enumerate(groups):
        if not isinstance(raw, Mapping):
            raise ValueError(f"V3 group repair group {index} is not object")
        group_id = raw.get("group_id")
        if not isinstance(group_id, str) or not group_id.strip():
            raise ValueError(f"V3 group repair group {index} has invalid group_id")
        normalized_group_id = group_id.strip()
        if normalized_group_id in group_by_id:
            raise ValueError(f"V3 group repair duplicate group_id: {normalized_group_id}")
        acceptance, group_failures, hint = _group_body(raw, index)
        group_by_id[normalized_group_id] = (index, acceptance, group_failures, hint)

    unknown_groups = sorted(set(assignments.values()) - set(group_by_id))
    if unknown_groups:
        raise ValueError("V3 group repair assignments reference unknown groups: " + ",".join(unknown_groups))
    unused_groups = sorted(set(group_by_id) - set(assignments.values()))
    if unused_groups:
        raise ValueError("V3 group repair contains unused groups: " + ",".join(unused_groups))
    invalid_representatives = sorted(
        group_id
        for group_id in group_by_id
        if assignments.get(group_id) != group_id
    )
    if invalid_representatives:
        raise ValueError(
            "V3 group repair group IDs must represent obligations assigned to themselves: "
            + ",".join(invalid_representatives)
        )

    acceptances: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    hints: list[dict[str, Any]] = []
    for oid in sorted(assignments):
        group_index, acceptance, group_failures, hint = group_by_id[assignments[oid]]
        _append_atomic(
            oid=oid,
            acceptance=acceptance,
            group_failures=group_failures,
            hint=hint,
            group_index=group_index,
            refs_by_oid=refs_by_oid,
            acceptances=acceptances,
            failures=failures,
            hints=hints,
        )
    return {"acceptances": acceptances, "failure_intents": failures, "slice_hints": hints}


def _project_legacy_groups(
    groups: list[Any],
    *,
    refs_by_oid: Mapping[str, list[str]] | None,
) -> dict[str, Any]:
    acceptances: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    hints: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(groups):
        if not isinstance(raw, Mapping):
            raise ValueError(f"V3 group repair group {index} is not object")
        ids = raw.get("obligation_ids")
        if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x.strip() for x in ids):
            raise ValueError(f"V3 group repair group {index} has invalid obligation_ids")
        normalized_values = [str(x).strip() for x in ids]
        normalized_ids = sorted(set(normalized_values))
        if len(normalized_ids) != len(normalized_values):
            raise ValueError(f"V3 group repair group {index} has duplicate obligation_ids")
        duplicates = seen & set(normalized_ids)
        if duplicates:
            raise ValueError("V3 group repair obligation appears in multiple groups: " + ",".join(sorted(duplicates)))
        seen.update(normalized_ids)
        acceptance, group_failures, hint = _group_body(raw, index)
        for oid in normalized_ids:
            _append_atomic(
                oid=oid,
                acceptance=acceptance,
                group_failures=group_failures,
                hint=hint,
                group_index=index,
                refs_by_oid=refs_by_oid,
                acceptances=acceptances,
                failures=failures,
                hints=hints,
            )
    return {"acceptances": acceptances, "failure_intents": failures, "slice_hints": hints}


def _project(value: Mapping[str, Any], *, refs_by_oid: Mapping[str, list[str]] | None = None) -> dict[str, Any]:
    groups = value.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("V3 group repair must return non-empty groups")
    if "obligation_group_assignments" in value:
        return _project_exact_assignments(value, groups, refs_by_oid=refs_by_oid)
    return _project_legacy_groups(groups, refs_by_oid=refs_by_oid)


def _trace_summary(trace: str) -> str:
    text = trace.strip()
    return text if len(text) <= 2600 else text[:300] + "\n...<trace elided>...\n" + text[-2200:]


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
    refs_by_oid = _obligation_refs(payload)
    if cache_path.is_file():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cached, Mapping):
            raise ValueError("V3 group repair cache is malformed")
        return _project(cached, refs_by_oid=refs_by_oid)

    output = out_dir / ".compiler-work" / f"{_GROUP_STAGE}-last-message.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    schema_path = transport._schema_path(out_dir, _GROUP_STAGE, _group_schema(payload))
    grouped_prompt = (
        prompt
        + "\n\nGROUP-FIRST REPAIR CONTRACT: return {\"groups\":[...],\"obligation_group_assignments\":{...}}. "
        "Each group has one group_id selected from the supplied frozen obligation IDs plus one shared Acceptance, failure, "
        "and slice context. The assignment object MUST contain every supplied obligation ID as a key exactly once; each "
        "value is the group_id whose context that obligation uses. A group_id must map to itself, every returned group must "
        "be used, and multiple obligations may map to one group ONLY when they share one real production owner context, "
        "verification lane, RED failure mechanism, selector/test lifecycle, legal write boundary, and no predecessor boundary. "
        "The compiler will project assignments deterministically into one Acceptance per obligation."
        + "\n\nINPUT:\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    backend = resolve_llm_backend(None)
    extra_args = ["--output-schema", str(schema_path)] if backend == "codex-cli" else []

    def run(extra: list[str]):
        return run_llm_exec(
            backend=backend, root=root, prompt=grouped_prompt, output_last_message=output,
            timeout_sec=transport._REPAIR_TIMEOUT_SECONDS,
            codex_configs=['model_reasoning_effort="medium"'], codex_sandbox="read-only", codex_extra_args=extra,
        )

    code, trace, _argv = run(extra_args)
    if code != 0 and extra_args and transport._unsupported_output_schema(trace):
        if output.exists():
            output.unlink()
        code, trace, _argv = run([])
    if code != 0 or not output.is_file():
        raise RuntimeError(f"semantic worker v3-schema-repair failed: {_trace_summary(trace)}")
    raw = sc._parse_json_output(output.read_text(encoding="utf-8"))
    projected = _project(raw, refs_by_oid=refs_by_oid)
    sc.atomic_json(cache_path, raw)
    return projected


def group_repair_transport(*, root, out_dir, stage: str, payload: Mapping[str, Any], prompt: str, worker_cache: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if stage != "v3-schema-repair":
        return _BASE_DOMAIN_TRANSPORT(root=root, out_dir=out_dir, stage=stage, payload=payload, prompt=prompt, worker_cache=worker_cache)
    refs_by_oid = _obligation_refs(payload)
    if worker_cache and stage in worker_cache:
        raw = worker_cache[stage]
        if not isinstance(raw, Mapping):
            raise ValueError("injected V3 repair cache must be object")
        value = _project(raw, refs_by_oid=refs_by_oid) if "groups" in raw else dict(raw)
    else:
        value = _live_group_repair(root=Path(root), out_dir=Path(out_dir), payload=payload, prompt=prompt)
    findings = v3_domain._domain_findings(stage, payload, value)
    if findings:
        raise ValueError("V3 frozen-domain validation failed: " + "; ".join(findings))
    return value


def install() -> None:
    gate._ORIGINAL_INVOKE_WORKER = group_repair_transport


install()
