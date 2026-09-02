"""Repair one independently proven atomic source gap before V3 compilation.

Atomic source recall is an independent judge.  When it proves a real source gap
(and only a source gap), V1 gets one bounded opportunity to add missing atomic
obligations.  Existing obligations and frozen source text are immutable.  The
repaired obligation set must pass V2 and a fresh atomic-recall recheck; otherwise
the normal repair-vdd result remains authoritative.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import semantic_compiler_gate as gate
import semantic_atomic_recall_result_patch  # noqa: F401  # exact recall diagnostics first

sc = gate.sc
_BASE_COMPILE_OBLIGATIONS = sc.compile_obligations


def _only_source_gaps(recall: Mapping[str, Any]) -> bool:
    findings = [str(item) for item in recall.get("findings", [])]
    gaps = recall.get("source_gap_claims")
    return (
        bool(findings)
        and isinstance(gaps, list)
        and bool(gaps)
        and all(item.startswith("atomic-recall:source-gap-count:") for item in findings)
    )


def _source_entry_by_ref(source_index: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for raw in source_index.get("entries", []):
        if isinstance(raw, Mapping) and isinstance(raw.get("source_ref"), str) and raw.get("source_ref"):
            result[str(raw["source_ref"])] = raw
    return result


def _repair_payload(
    source_index: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    gaps: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    refs = {str(item.get("source_ref")) for item in gaps if isinstance(item, Mapping) and item.get("source_ref")}
    entries = [
        dict(item)
        for item in source_index.get("entries", [])
        if isinstance(item, Mapping) and str(item.get("source_ref")) in refs
    ]
    existing = [
        dict(item)
        for item in obligations
        if isinstance(item, Mapping) and refs.intersection(str(ref) for ref in item.get("source_refs", []))
    ]
    return {
        "affected_sources": entries,
        "existing_obligations": existing,
        "source_gap_claims": [dict(item) for item in gaps if isinstance(item, Mapping)],
    }


def _additional_obligations(
    *,
    root,
    out_dir,
    source_index: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    gaps: Sequence[Mapping[str, Any]],
    worker_cache: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    payload = _repair_payload(source_index, obligations, gaps)
    raw = gate._ORIGINAL_INVOKE_WORKER(
        root=root,
        out_dir=out_dir,
        stage="v1-source-gap-repair",
        payload=payload,
        worker_cache=worker_cache,
        prompt=(
            "Add only the atomic obligations independently proven missing by source_gap_claims. Return "
            "{\"obligations\":[...]}; do not repeat, rewrite, merge, delete, defer, or weaken existing obligations. "
            "Each added obligation must bind exactly one affected source_ref and use the normal V1 fields. "
            "Preserve universal, exclusivity, temporal, and lifecycle qualifiers exactly: words such as only, must, "
            "throughout, before, after, during, never, always, until, and across all implementation activity change "
            "the behavior and must not be narrowed to one phase unless the source itself narrows it. Every added "
            "obligation must be status='active', unresolved_fragments=[], and represent one independently observable "
            "behavior from a supplied source_gap_claim. Do not invent implementation or runtime evidence."
        ),
    )
    items = raw.get("obligations")
    if not isinstance(items, list) or not items:
        raise ValueError("V1 source-gap repair returned no obligations")
    by_ref = _source_entry_by_ref(source_index)
    gap_refs = {
        str(item.get("source_ref"))
        for item in gaps
        if isinstance(item, Mapping) and isinstance(item.get("source_ref"), str)
    }
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"V1 source-gap repair obligation {index} is not object")
        refs = item.get("source_refs")
        if not isinstance(refs, list) or len(refs) != 1 or not isinstance(refs[0], str):
            raise ValueError("V1 source-gap repair obligation must bind exactly one source_ref")
        source_ref = refs[0]
        if source_ref not in gap_refs or source_ref not in by_ref:
            raise ValueError("V1 source-gap repair escaped the proven source-gap domain")
        if item.get("status", "active") != "active":
            raise ValueError("V1 source-gap repair may add only active obligations")
        unresolved = item.get("unresolved_fragments", [])
        if not isinstance(unresolved, list) or unresolved:
            raise ValueError("V1 source-gap repair may not add unresolved obligations")
        normalized.append(sc._normalize_obligation(by_ref[source_ref], item))
    return normalized


def compile_obligations_with_gap_repair(
    *,
    root,
    out_dir,
    source_index: Mapping[str, Any],
    worker_cache: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    obligations = list(
        _BASE_COMPILE_OBLIGATIONS(
            root=root,
            out_dir=out_dir,
            source_index=source_index,
            worker_cache=worker_cache,
        )
    )
    recall = gate.atomic_recall_alignment(
        root=root,
        out_dir=out_dir,
        source_index=source_index,
        obligations=obligations,
        worker_cache=worker_cache,
    )
    if recall.get("valid") or not _only_source_gaps(recall):
        return obligations

    gaps = [item for item in recall.get("source_gap_claims", []) if isinstance(item, Mapping)]
    additions = _additional_obligations(
        root=root,
        out_dir=out_dir,
        source_index=source_index,
        obligations=obligations,
        gaps=gaps,
        worker_cache=worker_cache,
    )
    existing_ids = {str(item.get("obligation_id")) for item in obligations}
    if any(str(item.get("obligation_id")) in existing_ids for item in additions):
        raise ValueError("V1 source-gap repair produced an existing obligation identity")
    repaired = sorted(
        [*obligations, *additions],
        key=lambda item: (str(item.get("requirement_id")), str(item.get("obligation_id"))),
    )
    guard = sc.guard_obligations(source_index, repaired)
    if not guard.get("valid"):
        raise ValueError("V1 source-gap repair failed V2: " + ",".join(str(x) for x in guard.get("findings", [])))
    recheck = gate.atomic_recall_alignment(
        root=root,
        out_dir=out_dir,
        source_index=source_index,
        obligations=repaired,
        worker_cache=worker_cache,
    )
    if not recheck.get("valid"):
        # Fail closed. The stable authority will surface this attempt rather than
        # accepting a locally guessed source repair.
        return repaired
    return repaired


def install() -> None:
    sc.compile_obligations = compile_obligations_with_gap_repair


install()
