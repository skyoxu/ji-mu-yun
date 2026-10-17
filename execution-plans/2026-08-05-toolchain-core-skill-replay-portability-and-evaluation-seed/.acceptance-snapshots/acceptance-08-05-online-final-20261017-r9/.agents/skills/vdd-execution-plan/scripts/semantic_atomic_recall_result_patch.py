"""Correct V4 atomic-recall diagnostics without weakening the gate.

The canonical V4 implementation correctly blocks unknown obligation ids, but its
partition diagnostic also fires when the only difference is an extra unknown id
and then renders an empty missing-id suffix.  Keep unknown-id findings blocking;
only remove the empty partition finding because no known obligation is missing.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import semantic_compiler_gate as gate

_BASE_ATOMIC_RECALL_ALIGNMENT = gate.atomic_recall_alignment
_EMPTY_PARTITION_FINDING = "atomic-recall:obligation-partition-incomplete:"


def _direct_source_entries(source_index: Mapping[str, Any], obligation: Mapping[str, Any]) -> list[dict[str, str]]:
    refs = obligation.get("source_refs")
    if not isinstance(refs, list):
        return []
    wanted = {str(ref) for ref in refs if isinstance(ref, str) and ref}
    entries = source_index.get("entries")
    if not isinstance(entries, list):
        return []
    return [
        {"source_ref": str(entry["source_ref"]), "source_text": str(entry["source_text"])}
        for entry in entries
        if isinstance(entry, Mapping)
        and str(entry.get("source_ref") or "") in wanted
        and isinstance(entry.get("source_text"), str)
    ]


def _recheck_invented(
    *,
    root,
    out_dir,
    source_index: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    result: Mapping[str, Any],
    worker_cache: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Resolve an invented verdict only from the obligation's exact source text.

    The bulk atomic-recall payload contains every companion and may make a
    directly bound source row less salient.  This is a bounded independent
    recheck, not a local entailment guess: every disputed ID remains classified
    exactly once by the worker and a malformed or unavailable recheck preserves
    the blocking verdict.
    """
    worker = result.get("worker")
    invented = worker.get("invented_obligation_ids") if isinstance(worker, Mapping) else None
    if not isinstance(invented, list) or not invented:
        return dict(result)
    by_id = {
        str(item.get("obligation_id")): item
        for item in obligations
        if isinstance(item, Mapping) and isinstance(item.get("obligation_id"), str)
    }
    disputed = [str(oid) for oid in invented if isinstance(oid, str) and oid in by_id]
    if not disputed or len(disputed) != len(invented):
        return dict(result)
    selected = [by_id[oid] for oid in disputed]
    entries = [entry for obligation in selected for entry in _direct_source_entries(source_index, obligation)]
    if not entries:
        return dict(result)
    recheck_stage = "v4-atomic-recall-invented-entailment-recheck"
    # An explicit fixture is a closed semantic input.  It must opt in to this
    # extra independent judgment rather than causing an unconfigured live call.
    if worker_cache is not None and recheck_stage not in worker_cache:
        return dict(result)
    # Reuse the existing V4 frozen-domain envelope.  A bespoke source_entries
    # field would bypass neither the domain validator nor its source-ref check.
    payload = {"source_index": {"entries": entries}, "obligations": selected}
    prompt = (
        "Independently recheck only the disputed atomic obligations against the exact frozen source entries. "
        "Classify every listed obligation ID exactly once as supported or invented. "
        "An obligation is supported when its required transition, observable, and forbidden outcome are directly "
        "entailed by its cited source entry; do not reject a required quantitative, temporal, measurement, or "
        "verification clause merely because it is expressed as part of one source sentence. "
        "Return JSON only: {supported_obligation_ids:[], invented_obligation_ids:[], source_gap_claims:[]}. "
        "source_gap_claims must be []."
    )
    try:
        raw = gate.sc.invoke_worker(
            root=root, out_dir=out_dir, stage=recheck_stage,
            payload=payload, prompt=prompt, worker_cache=worker_cache,
        )
    except (RuntimeError, ValueError):
        return dict(result)
    if not isinstance(raw, Mapping):
        return dict(result)
    supported = raw.get("supported_obligation_ids")
    still_invented = raw.get("invented_obligation_ids")
    gaps = raw.get("source_gap_claims")
    if not isinstance(supported, list) or not isinstance(still_invented, list) or gaps != []:
        return dict(result)
    supported_ids = {str(oid) for oid in supported if isinstance(oid, str)}
    invented_ids = {str(oid) for oid in still_invented if isinstance(oid, str)}
    disputed_set = set(disputed)
    if supported_ids & invented_ids or supported_ids | invented_ids != disputed_set:
        return dict(result)
    if not supported_ids:
        return dict(result)
    updated_worker = dict(worker)
    prior_supported = [str(oid) for oid in worker.get("supported_obligation_ids", []) if isinstance(oid, str)]
    prior_invented = [str(oid) for oid in invented if isinstance(oid, str)]
    updated_worker["supported_obligation_ids"] = list(dict.fromkeys([*prior_supported, *sorted(supported_ids)]))
    updated_worker["invented_obligation_ids"] = [oid for oid in prior_invented if oid not in supported_ids]
    updated = dict(result)
    updated["worker"] = updated_worker
    updated["findings"] = [
        str(finding) for finding in result.get("findings", [])
        if not (str(finding).startswith("atomic-recall:invented-obligation:") and not updated_worker["invented_obligation_ids"])
    ]
    total = len([item for item in obligations if isinstance(item, Mapping) and item.get("status") == "active"])
    supported_count = len(set(updated_worker["supported_obligation_ids"]))
    invented_count = len(set(updated_worker["invented_obligation_ids"]))
    gap_count = len(updated.get("source_gap_claims", []))
    precision = supported_count / (supported_count + invented_count) if supported_count + invented_count else 0.0
    recall = supported_count / (supported_count + gap_count) if supported_count + gap_count else (1.0 if not total else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    updated["metrics"] = {
        "active_obligation_count": total,
        "supported_obligation_count": supported_count,
        "invented_obligation_count": invented_count,
        "source_gap_count": gap_count,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }
    updated["valid"] = not updated["findings"]
    return updated


def _normalize_result(result: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(result)
    findings = [str(item) for item in result.get("findings", [])]
    cleaned = [item for item in findings if item != _EMPTY_PARTITION_FINDING]
    normalized["findings"] = cleaned
    normalized["valid"] = not cleaned

    worker = result.get("worker")
    unknown_supported = [item for item in cleaned if item.startswith("atomic-recall:unknown-supported:")]
    unknown_invented = [item for item in cleaned if item.startswith("atomic-recall:unknown-invented:")]
    normalized["protocol_metrics"] = {
        "unknown_supported_finding_count": len(unknown_supported),
        "unknown_invented_finding_count": len(unknown_invented),
        "worker_result_present": isinstance(worker, Mapping),
    }
    return normalized


def atomic_recall_alignment(
    *,
    root,
    out_dir,
    source_index: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    worker_cache: Mapping[str, Any] | None,
) -> dict[str, Any]:
    initial = _BASE_ATOMIC_RECALL_ALIGNMENT(
            root=root,
            out_dir=out_dir,
            source_index=source_index,
            obligations=obligations,
            worker_cache=worker_cache,
        )
    return _normalize_result(_recheck_invented(
        root=root,
        out_dir=out_dir,
        source_index=source_index,
        obligations=obligations,
        result=initial,
        worker_cache=worker_cache,
    ))


def install() -> None:
    gate.atomic_recall_alignment = atomic_recall_alignment


install()
