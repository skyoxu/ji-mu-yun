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
_ATOMIC_RECALL_CHUNK_SIZE = 20
_SOURCE_RECALL_CHUNK_SIZE = 4
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
    overlap = sorted(supported & invented)
    if overlap:
        # The source-recall response is a partition, not two independent
        # tag sets.  Retrying this exact worker response is safe only after a
        # schema repair resolves every contradictory classification.
        findings.append("supported-invented-overlap:" + ",".join(overlap))
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


def _merge_partition_completion(
    payload: Mapping[str, Any],
    original: Mapping[str, Any],
    completion: Mapping[str, Any],
) -> dict[str, Any]:
    """Join a missing-ID-only classification to an otherwise valid V4 result."""
    ids, _ = _domains("v4-atomic-recall", payload)
    original_supported = original.get("supported_obligation_ids")
    original_invented = original.get("invented_obligation_ids")
    completion_supported = completion.get("supported_obligation_ids")
    completion_invented = completion.get("invented_obligation_ids")
    if not all(isinstance(value, list) for value in (
        original_supported, original_invented, completion_supported, completion_invented,
    )):
        raise ValueError("partition completion requires id arrays")
    original_ids = set(original_supported) | set(original_invented)
    missing = set(ids) - original_ids
    completion_ids = set(completion_supported) | set(completion_invented)
    if completion_ids != missing or set(completion_supported) & set(completion_invented):
        raise ValueError("partition completion must classify exactly the missing frozen ids")
    merged = {
        "supported_obligation_ids": list(original_supported) + list(completion_supported),
        "invented_obligation_ids": list(original_invented) + list(completion_invented),
        "source_gap_claims": list(original.get("source_gap_claims") or []),
    }
    findings = _domain_findings("v4-atomic-recall", payload, merged)
    if findings:
        raise ValueError("partition completion produced invalid V4 result: " + "; ".join(findings))
    return merged


def _missing_partition_ids(payload: Mapping[str, Any], value: Mapping[str, Any]) -> list[str] | None:
    """Return missing IDs only for an otherwise valid, incomplete partition."""
    findings = _domain_findings("v4-atomic-recall", payload, value)
    prefix = "obligation-partition-incomplete:"
    if len(findings) != 1 or not findings[0].startswith(prefix):
        return None
    return [item for item in findings[0][len(prefix):].split(",") if item]


def _completion_schema(ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "supported_obligation_ids": _enum_array(ids),
            "invented_obligation_ids": _enum_array(ids),
        },
        "required": ["supported_obligation_ids", "invented_obligation_ids"],
    }


def _completion_findings(ids: list[str], value: Mapping[str, Any]) -> list[str]:
    supported = value.get("supported_obligation_ids")
    invented = value.get("invented_obligation_ids")
    if not isinstance(supported, list) or not isinstance(invented, list):
        return ["partition-completion:id-arrays"]
    actual = set(supported) | set(invented)
    findings: list[str] = []
    if actual != set(ids):
        findings.append("partition-completion:wrong-id-domain")
    if set(supported) & set(invented):
        findings.append("partition-completion:overlap")
    if len(supported) != len(set(supported)) or len(invented) != len(set(invented)):
        findings.append("partition-completion:duplicates")
    return findings


def _chunk_obligation_payload(payload: Mapping[str, Any], ids: list[str]) -> dict[str, Any]:
    """Keep the frozen source index intact while narrowing only the active V1 set."""
    obligations = payload.get("obligations")
    allowed = set(ids)
    if not isinstance(obligations, list):
        raise ValueError("V4 chunking requires an obligations list")
    selected = [
        item for item in obligations
        if isinstance(item, Mapping) and item.get("obligation_id") in allowed
    ]
    if {str(item.get("obligation_id")) for item in selected} != allowed:
        raise ValueError("V4 chunk payload does not match its frozen obligation ids")
    return {**payload, "obligations": selected}


def _source_recall_payload(payload: Mapping[str, Any], refs: list[str]) -> dict[str, Any]:
    source_index = payload.get("source_index")
    obligations = payload.get("obligations")
    if not isinstance(source_index, Mapping) or not isinstance(source_index.get("entries"), list) or not isinstance(obligations, list):
        raise ValueError("V4 source recall requires frozen sources and obligations")
    allowed = set(refs)
    entries = [item for item in source_index["entries"] if isinstance(item, Mapping) and item.get("source_ref") in allowed]
    if {item.get("source_ref") for item in entries} != allowed:
        raise ValueError("V4 source chunk does not match its frozen refs")
    # ADR-0041: source refs locate the text under review, not the entire
    # obligation closure. Another requirement can already impose the same
    # observable duty (FR-9's three named callers imply SM-4 non-emptiness).
    # Keep the complete V1 set visible to prevent a false source gap.
    cross_source_text = [
        {"source_ref": item["source_ref"], "source_text": item["source_text"]}
        for item in source_index["entries"]
        if isinstance(item, Mapping)
        and item.get("source_ref") not in allowed
        and isinstance(item.get("source_ref"), str)
        and isinstance(item.get("source_text"), str)
    ]
    return {
        "source_index": {**source_index, "entries": entries},
        "cross_source_text": cross_source_text,
        "obligations": list(obligations),
    }


def _source_gap_schema(refs: list[str]) -> dict[str, Any]:
    return {
        "type": "object", "additionalProperties": False,
        "properties": {"source_gap_claims": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "source_ref": {"type": "string", "enum": refs},
                "subject": {"type": "string", "minLength": 1},
                "behavior": {"type": "string", "minLength": 1},
                "reason": {"type": "string", "minLength": 1},
            },
            "required": ["source_ref", "subject", "behavior", "reason"],
        }}},
        "required": ["source_gap_claims"],
    }


def _source_gap_findings(refs: list[str], value: Mapping[str, Any]) -> list[str]:
    gaps = value.get("source_gap_claims")
    if not isinstance(gaps, list):
        return ["source-gap-claims:not-array"]
    findings: list[str] = []
    allowed = set(refs)
    for index, gap in enumerate(gaps):
        if not isinstance(gap, Mapping) or set(gap) != {"source_ref", "subject", "behavior", "reason"}:
            findings.append(f"source-gap-claims[{index}]:shape")
            continue
        if gap.get("source_ref") not in allowed or any(
            not isinstance(gap.get(key), str) or not gap[key].strip()
            for key in ("subject", "behavior", "reason")
        ):
            findings.append(f"source-gap-claims[{index}]:domain")
    return findings


def _merge_atomic_recall_chunks(
    payload: Mapping[str, Any],
    chunks: list[Mapping[str, Any]],
    expected_chunks: list[list[str]] | None = None,
) -> dict[str, Any]:
    """Merge chunk results without silently dropping or reclassifying evidence."""
    ids, _ = _domains("v4-atomic-recall", payload)
    supported: list[str] = []
    invented: list[str] = []
    gaps: dict[str, Mapping[str, Any]] = {}
    for index, result in enumerate(chunks):
        if not isinstance(result, Mapping):
            raise ValueError(f"V4 chunk {index + 1} is not an object")
        supported_raw = result.get("supported_obligation_ids")
        invented_raw = result.get("invented_obligation_ids")
        gaps_raw = result.get("source_gap_claims")
        if not isinstance(supported_raw, list) or not isinstance(invented_raw, list) or not isinstance(gaps_raw, list):
            raise ValueError(f"V4 chunk {index + 1} has malformed result arrays")
        if any(not isinstance(item, str) for item in [*supported_raw, *invented_raw]):
            raise ValueError(f"V4 chunk {index + 1} has a malformed obligation id")
        if expected_chunks is not None and set(supported_raw) | set(invented_raw) != set(expected_chunks[index]):
            raise ValueError(f"V4 chunk {index + 1} does not cover its assigned obligation ids")
        supported.extend(supported_raw)
        invented.extend(invented_raw)
        for gap in gaps_raw:
            if not isinstance(gap, Mapping):
                raise ValueError(f"V4 chunk {index + 1} has a malformed source gap")
            key = json.dumps(dict(gap), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            gaps[key] = dict(gap)

    supported_set = set(supported)
    invented_set = set(invented)
    if len(supported) != len(supported_set) or len(invented) != len(invented_set):
        raise ValueError("V4 chunk merge found duplicate obligation ids")
    overlap = sorted(supported_set & invented_set)
    if overlap:
        raise ValueError("V4 chunk merge found supported/invented overlap: " + ",".join(overlap))
    if supported_set | invented_set != set(ids):
        missing = sorted(set(ids) - (supported_set | invented_set))
        unknown = sorted((supported_set | invented_set) - set(ids))
        raise ValueError(
            "V4 chunk merge partition mismatch: missing=" + ",".join(missing)
            + "; unknown=" + ",".join(unknown)
        )
    return {
        "supported_obligation_ids": sorted(supported_set),
        "invented_obligation_ids": sorted(invented_set),
        "source_gap_claims": [gaps[key] for key in sorted(gaps)],
    }


def _schema_path(out_dir: Path, stage: str, schema: Mapping[str, Any]) -> Path:
    digest = sc.sha256_value(schema)[7:19]
    path = out_dir / ".compiler-work" / "worker-schemas" / f"v4-atomic-recall-{digest}.json"
    sc.atomic_json(path, dict(schema))
    return path


def _invoke_source_gap_chunk(
    *, root: Path, out_dir: Path, payload: Mapping[str, Any], refs: list[str],
    stage: str, worker_cache: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    cache_path = out_dir / ".compiler-cache" / sc._worker_cache_key(stage, payload)
    value: Mapping[str, Any]
    if cache_path.is_file():
        value = json.loads(cache_path.read_text(encoding="utf-8"))
    elif worker_cache and stage in worker_cache:
        value = worker_cache[stage]
    else:
        scripts = root / "scripts" / "sc"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from _llm_backend import run_llm_exec, resolve_llm_backend
        output = out_dir / ".compiler-work" / f"{stage}-last-message.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        transport._preserve_prior_output(output)
        backend = resolve_llm_backend(None)
        schema = _source_gap_schema(refs)
        extra = ["--output-schema", str(_schema_path(out_dir, stage, schema))] if backend == "codex-cli" else []
        full_prompt = (
            "You are a read-only semantic compiler worker. Return JSON only. Independently compare every "
            "frozen source entry in INPUT with the complete supplied obligation set, including obligations "
            "citing other source refs; cross_source_text supplies their frozen wording for verification. "
            "Report only independently required "
            "behaviors or verification duties absent from the complete set. A duty already entailed by another "
            "obligation is not a gap. Descriptive current-state facts "
            "are not gaps. Return source_gap_claims[] only; an empty array is valid. Do not invent requirements."
            "\n\nINPUT:\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        )
        code, trace, _ = worker_call(
            run_llm_exec, progress_dir=out_dir, progress_stage=stage,
            backend=backend, root=root, prompt=full_prompt,
            output_last_message=output, timeout_sec=transport._REPAIR_TIMEOUT_SECONDS,
            codex_configs=['model_reasoning_effort="high"'], codex_sandbox="read-only",
            codex_extra_args=[*transport.codex_worker_isolation_args(), *extra],
        )
        if code != 0 or not output.is_file():
            raise RuntimeError(f"semantic worker {stage} failed: {transport._bounded_trace(trace)}")
        value = sc._parse_json_output(output.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"V4 source gap chunk {stage} is not an object")
    findings = _source_gap_findings(refs, value)
    if findings:
        raise ValueError(f"V4 source gap chunk {stage} invalid: " + "; ".join(findings))
    sc.atomic_json(cache_path, value)
    return value


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

    # The full V4 request is intentionally split only at the transport seam.
    # V1/V3 inputs, source refs, and the final canonical witness remain
    # unchanged; this prevents a large obligation set from timing out before
    # producing machine-readable JSON.
    if stage == "v4-atomic-recall":
        obligations = payload.get("obligations")
        active_ids = sorted(
            str(item.get("obligation_id"))
            for item in obligations
            if isinstance(item, Mapping)
            and item.get("status") == "active"
            and isinstance(item.get("obligation_id"), str)
            and item.get("obligation_id")
        ) if isinstance(obligations, list) else []
        if len(active_ids) > _ATOMIC_RECALL_CHUNK_SIZE:
            cache_dir = out_dir / ".compiler-cache"
            cache_path = cache_dir / sc._worker_cache_key(stage, payload)
            if cache_path.is_file():
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if not isinstance(cached, Mapping):
                    raise ValueError("V4 worker cache is malformed")
                findings = _domain_findings(stage, payload, cached)
                if findings:
                    raise ValueError("V4 worker output violates frozen id domain: " + "; ".join(findings))
                return cached
            if worker_cache and stage in worker_cache:
                cached = worker_cache[stage]
                if not isinstance(cached, Mapping):
                    raise ValueError(f"injected worker cache {stage} must be object")
                findings = _domain_findings(stage, payload, cached)
                if findings:
                    raise ValueError("V4 worker output violates frozen id domain: " + "; ".join(findings))
                sc.atomic_json(cache_path, cached)
                return cached
            chunks: list[Mapping[str, Any]] = []
            assigned_chunks: list[list[str]] = []
            for offset in range(0, len(active_ids), _ATOMIC_RECALL_CHUNK_SIZE):
                chunk_ids = active_ids[offset:offset + _ATOMIC_RECALL_CHUNK_SIZE]
                chunk_payload = _chunk_obligation_payload(payload, chunk_ids)
                chunk_stage = f"v4-atomic-recall-chunk-{offset // _ATOMIC_RECALL_CHUNK_SIZE + 1:03d}"
                chunk = v4_transport_invoke_worker(
                    root=root,
                    out_dir=out_dir,
                    stage=chunk_stage,
                    payload=chunk_payload,
                    prompt=(
                        prompt
                        + "\nThis is one deterministic V4 obligation chunk. Classify only the supplied active obligations; "
                        "do not infer or mention obligations outside this chunk. Return source_gap_claims=[]; "
                        "source-gap recall is assessed separately against all obligations citing each source."
                    ),
                    worker_cache=worker_cache,
                )
                findings = _domain_findings(chunk_stage, chunk_payload, chunk)
                if findings:
                    raise ValueError(f"V4 chunk {chunk_stage} violates frozen id domain: " + "; ".join(findings))
                if chunk.get("source_gap_claims"):
                    raise ValueError(f"V4 chunk {chunk_stage} reported a gap without global source context")
                chunks.append(chunk)
                assigned_chunks.append(chunk_ids)
            merged = _merge_atomic_recall_chunks(payload, chunks, assigned_chunks)
            _, source_refs = _domains(stage, payload)
            source_gaps: list[Mapping[str, Any]] = []
            for offset in range(0, len(source_refs), _SOURCE_RECALL_CHUNK_SIZE):
                refs = source_refs[offset:offset + _SOURCE_RECALL_CHUNK_SIZE]
                source_payload = _source_recall_payload(payload, refs)
                source_stage = f"v4-atomic-recall-source-{offset // _SOURCE_RECALL_CHUNK_SIZE + 1:03d}"
                source_result = _invoke_source_gap_chunk(
                    root=root, out_dir=out_dir, payload=source_payload,
                    refs=refs, stage=source_stage, worker_cache=worker_cache,
                )
                source_gaps.extend(source_result["source_gap_claims"])
            gap_keys: set[tuple[str, str, str]] = set()
            for gap in source_gaps:
                key = (gap["source_ref"], gap["subject"].casefold(), gap["behavior"].casefold())
                if key in gap_keys:
                    raise ValueError("V4 source recall returned duplicate gap claims")
                gap_keys.add(key)
            merged["source_gap_claims"] = sorted(
                [dict(gap) for gap in source_gaps],
                key=lambda gap: (gap["source_ref"], gap["subject"], gap["behavior"], gap["reason"]),
            )
            sc.atomic_json(cache_path, merged)
            return merged

    is_partition_repair = stage.endswith("-partition-repair")
    repair_ids = payload.get("missing_obligation_ids") if is_partition_repair else None
    if is_partition_repair:
        if not isinstance(repair_ids, list) or not repair_ids or not all(isinstance(item, str) and item for item in repair_ids):
            raise ValueError("partition repair requires nonempty missing_obligation_ids")
        repair_ids = sorted(set(repair_ids))

    def validate(value: Mapping[str, Any]) -> list[str]:
        if is_partition_repair:
            return _completion_findings(repair_ids, value)
        return _domain_findings(stage, payload, value)

    def complete_if_needed(value: Mapping[str, Any]) -> Mapping[str, Any]:
        if not (
            stage in {"v4-atomic-recall", "v4-atomic-recall-schema-repair"}
            or stage.startswith("v4-atomic-recall-chunk-")
        ):
            return value
        semantic_payload = _semantic_payload(stage, payload)
        missing = _missing_partition_ids(semantic_payload, value)
        if missing is None:
            return value
        completion = v4_transport_invoke_worker(
            root=root,
            out_dir=out_dir,
            stage="v4-atomic-recall-partition-repair",
            payload={"input": semantic_payload, "missing_obligation_ids": missing},
            prompt=(
                "Classify exactly the supplied missing frozen obligation IDs as supported or invented. "
                "Do not reassess source gaps and do not output any other IDs."
            ),
            worker_cache=worker_cache,
        )
        return _merge_partition_completion(semantic_payload, value, completion)

    cache_dir = out_dir / ".compiler-cache"
    cache_path = cache_dir / sc._worker_cache_key(stage, payload)
    if cache_path.is_file():
        value = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError("worker cache is malformed")
        findings = validate(value)
        if findings:
            raise ValueError("V4 worker output violates frozen id domain: " + "; ".join(findings))
        return value
    if worker_cache and stage in worker_cache:
        value = worker_cache[stage]
        if not isinstance(value, Mapping):
            raise ValueError(f"injected worker cache {stage} must be object")
        value = complete_if_needed(value)
        findings = validate(value)
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
    transport._preserve_prior_output(output)

    ids, refs = _domains(stage, payload)
    if is_partition_repair:
        frozen_contract = (
            "\n\nFROZEN V4 PARTITION REPAIR: supported_obligation_ids and invented_obligation_ids may contain ONLY these exact missing ids: "
            + json.dumps(repair_ids, ensure_ascii=False)
            + ". Classify each exactly once. Do not output source_gap_claims or any other ID."
        )
    else:
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
    is_schema_repair = stage.endswith("-schema-repair")
    is_v4_repair = stage in {"v4", "v4-atomic-recall", "v4-recheck"} or stage.startswith("v4-atomic-recall-chunk-")
    timeout_sec = transport._REPAIR_TIMEOUT_SECONDS if (is_schema_repair or is_v4_repair) else transport._NORMAL_TIMEOUT_SECONDS
    reasoning = "medium" if is_schema_repair else "high"
    schema = _completion_schema(repair_ids) if is_partition_repair else _output_schema(stage, payload)
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
        transport._preserve_prior_output(output)
        code, trace, _argv = execute([])
    if code != 0 or not output.is_file():
        raise RuntimeError(f"semantic worker {stage} failed: {transport._bounded_trace(trace)}")

    value = sc._parse_json_output(output.read_text(encoding="utf-8"))
    value = complete_if_needed(value)
    findings = validate(value)
    if findings:
        raise ValueError("V4 worker output violates frozen id domain: " + "; ".join(findings))
    sc.atomic_json(cache_path, value)
    return value


def install() -> None:
    # Compose V4 specialization over the already-installed V3 transport stack.
    gate._ORIGINAL_INVOKE_WORKER = v4_transport_invoke_worker


install()
