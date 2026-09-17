"""Constrain V4 atomic-recall worker output to the frozen semantic ID domain.

Atomic recall is an independent semantic oracle, but it is not allowed to invent
identifier tokens.  supported/invented classifications must reference active
obligation ids already present in the frozen V1 payload, and source-gap claims
must reference source refs already present in the frozen source index.

This layer adds dynamic structured output plus deterministic post-parse domain
validation.  A domain violation therefore enters the existing one-shot semantic
repair lane; unknown ids are never silently filtered or reinterpreted.

IMPORTANT: this wrapper composes over the transport chain already installed when
this module is imported.  Non-V4 stages must delegate to that chain rather than
jumping back to the raw transport, otherwise V3 domain/group/execution-contract
validators and their one-shot repair semantics are silently bypassed.
"""
from __future__ import annotations

from semantic_progress import worker_call, stage_call

import json
from pathlib import Path
import sys
from typing import Any, Mapping

import semantic_compiler_gate as gate
import semantic_worker_transport_patch as transport

sc = gate.sc
# Capture the *currently installed* transport chain.  semantic_feasibility_patch
# imports V3 domain/group/execution-contract layers before this module, so this
# preserves those wrappers for every non-V4 call.
_BASE_TRANSPORT = gate._ORIGINAL_INVOKE_WORKER


def _semantic_payload(stage: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if stage.endswith("-schema-repair"):
        nested = payload.get("input")
        if isinstance(nested, Mapping):
            return nested
    return payload


def _domains(stage: str, payload: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    semantic = _semantic_payload(stage, payload)
    obligations = semantic.get("obligations")
    source_index = semantic.get("source_index")
    ids = sorted({
        str(item.get("obligation_id"))
        for item in obligations if isinstance(obligations, list) and isinstance(item, Mapping)
        if item.get("status") == "active" and isinstance(item.get("obligation_id"), str) and item.get("obligation_id")
    }) if isinstance(obligations, list) else []
    entries = source_index.get("entries") if isinstance(source_index, Mapping) else None
    refs = sorted({
        str(item.get("source_ref"))
        for item in entries if isinstance(entries, list) and isinstance(item, Mapping)
        if isinstance(item.get("source_ref"), str) and item.get("source_ref")
    }) if isinstance(entries, list) else []
    if not ids:
        raise ValueError("V4 frozen active obligation id domain is empty")
    if not refs:
        raise ValueError("V4 frozen source-ref domain is empty")
    return ids, refs


def _enum_array(values: list[str]) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string", "enum": values},
    }


def _output_schema(stage: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    ids, refs = _domains(stage, payload)
    gap = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source_ref": {"type": "string", "enum": refs},
            "subject": {"type": "string", "minLength": 1},
            "behavior": {"type": "string", "minLength": 1},
            "reason": {"type": "string", "minLength": 1},
        },
        "required": ["source_ref", "subject", "behavior", "reason"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "supported_obligation_ids": _enum_array(ids),
            "invented_obligation_ids": _enum_array(ids),
            "source_gap_claims": {"type": "array", "items": gap},
        },
        "required": ["supported_obligation_ids", "invented_obligation_ids", "source_gap_claims"],
    }


def _domain_findings(stage: str, payload: Mapping[str, Any], value: Mapping[str, Any]) -> list[str]:
    ids, refs = _domains(stage, payload)
    allowed_ids = set(ids)
    allowed_refs = set(refs)
    findings: list[str] = []
    for field in ("supported_obligation_ids", "invented_obligation_ids"):
        raw = value.get(field)
        if not isinstance(raw, list):
            continue
        strings = [item for item in raw if isinstance(item, str)]
        duplicates = sorted({item for item in strings if strings.count(item) > 1})
        if duplicates:
            findings.append(f"{field}:duplicate-frozen-id:" + ",".join(duplicates))
        unknown = sorted({str(item) for item in raw if isinstance(item, str)} - allowed_ids)
        if unknown:
            findings.append(f"{field}:unknown-frozen-id:" + ",".join(unknown))
    supported = set(value.get("supported_obligation_ids") or [])
    invented = set(value.get("invented_obligation_ids") or [])
    missing = sorted(allowed_ids - (supported | invented))
    if missing:
        # ADR-0041: an incomplete classification cannot be reused as an
        # independent source-recall judgment.
        findings.append("obligation-partition-incomplete:" + ",".join(missing))
    gaps = value.get("source_gap_claims")
    if isinstance(gaps, list):
        for index, raw_gap in enumerate(gaps):
            if not isinstance(raw_gap, Mapping):
                continue
            source_ref = raw_gap.get("source_ref")
            if isinstance(source_ref, str) and source_ref not in allowed_refs:
                findings.append(f"source_gap_claims[{index}]:unknown-frozen-source-ref:{source_ref}")
    return findings


def _schema_path(out_dir: Path, stage: str, schema: Mapping[str, Any]) -> Path:
    digest = sc.sha256_value(schema)[7:19]
    path = out_dir / ".compiler-work" / "worker-schemas" / f"v4-atomic-recall-{digest}.json"
    sc.atomic_json(path, dict(schema))
    return path


def v4_transport_invoke_worker(
    *,
    root: Path,
    out_dir: Path,
    stage: str,
    payload: Mapping[str, Any],
    prompt: str,
    worker_cache: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    if not stage.startswith("v4-atomic-recall"):
        return _BASE_TRANSPORT(
            root=root,
            out_dir=out_dir,
            stage=stage,
            payload=payload,
            prompt=prompt,
            worker_cache=worker_cache,
        )

    cache_dir = out_dir / ".compiler-cache"
    cache_path = cache_dir / sc._worker_cache_key(stage, payload)
    if cache_path.is_file():
        value = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError("worker cache is malformed")
        findings = _domain_findings(stage, payload, value)
        if findings:
            raise ValueError("V4 worker output violates frozen id domain: " + "; ".join(findings))
        return value
    if worker_cache and stage in worker_cache:
        value = worker_cache[stage]
        if not isinstance(value, Mapping):
            raise ValueError(f"injected worker cache {stage} must be object")
        findings = _domain_findings(stage, payload, value)
        if findings:
            raise ValueError("V4 worker output violates frozen id domain: " + "; ".join(findings))
        sc.atomic_json(cache_path, value)
        return value

    scripts = root / "scripts" / "sc"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from _llm_backend import run_llm_exec, resolve_llm_backend
    except ImportError as exc:
        raise RuntimeError("shared LLM backend is unavailable") from exc

    work = out_dir / ".compiler-work"
    output = work / f"{stage}-last-message.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if not output.is_file():
            raise ValueError(f"semantic worker output path is not a file: {output}")
        output.unlink()

    ids, refs = _domains(stage, payload)
    frozen_contract = (
        "\n\nFROZEN V4 ID DOMAIN: supported_obligation_ids and invented_obligation_ids may contain ONLY these exact ids: "
        + json.dumps(ids, ensure_ascii=False)
        + ". Do not create, rewrite, abbreviate, duplicate, or infer identifier tokens. source_gap_claims.source_ref may contain ONLY: "
        + json.dumps(refs, ensure_ascii=False)
        + ". Classify every frozen obligation exactly once as supported or invented. An empty source_gap_claims array is valid when no independently observable source behavior is missing."
    )
    full_prompt = (
        "You are a read-only semantic compiler worker. Do not modify files. "
        "Return JSON only. Do not invent requirements or runtime evidence.\n\n"
        + prompt
        + frozen_contract
        + "\n\nINPUT:\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    backend = resolve_llm_backend(None)
    is_repair = stage.endswith("-schema-repair")
    timeout_sec = transport._REPAIR_TIMEOUT_SECONDS if is_repair else transport._NORMAL_TIMEOUT_SECONDS
    reasoning = "medium" if is_repair else "high"
    schema = _output_schema(stage, payload)
    extra_args: list[str] = []
    if backend == "codex-cli":
        extra_args = ["--output-schema", str(_schema_path(out_dir, stage, schema))]

    def execute(extra: list[str]) -> tuple[int, str, list[str]]:
        return worker_call(run_llm_exec, progress_dir=out_dir, progress_stage=stage,
            backend=backend,
            root=root,
            prompt=full_prompt,
            output_last_message=output,
            timeout_sec=timeout_sec,
            codex_configs=[f'model_reasoning_effort="{reasoning}"'],
            codex_sandbox="read-only",
            codex_extra_args=extra,
        )

    code, trace, _argv = execute(extra_args)
    if code != 0 and extra_args and transport._unsupported_output_schema(trace):
        if output.exists():
            output.unlink()
        code, trace, _argv = execute([])
    if code != 0 or not output.is_file():
        raise RuntimeError(f"semantic worker {stage} failed: {transport._bounded_trace(trace)}")

    value = sc._parse_json_output(output.read_text(encoding="utf-8"))
    findings = _domain_findings(stage, payload, value)
    if findings:
        raise ValueError("V4 worker output violates frozen id domain: " + "; ".join(findings))
    sc.atomic_json(cache_path, value)
    return value


def install() -> None:
    # Compose V4 specialization over the already-installed V3 transport stack.
    gate._ORIGINAL_INVOKE_WORKER = v4_transport_invoke_worker


install()
