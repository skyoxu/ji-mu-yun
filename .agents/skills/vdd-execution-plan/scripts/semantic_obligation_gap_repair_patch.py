"""Reconcile proven atomic source gaps and invented V1 candidates.

Atomic source recall is an independent judge. When it proves only source gaps,
V1 gets one bounded addition pass. When it returns an exact frozen-ID partition
and identifies only invented candidate obligations, those candidates may be
projected out once, before canonical V1 publication, only if V2 and a fresh
atomic-recall recheck pass. Mixed, incomplete, or ambiguous findings remain
fail-closed. This preserves the repository-owned authority boundary accepted in
ADR-0041 without weakening the precision or recall gate.
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


def _exact_invented_partition(
    recall: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
) -> set[str]:
    """Return removable candidate IDs only for an exact, invented-only V4 partition."""
    gaps = recall.get("source_gap_claims")
    worker = recall.get("worker")
    if not isinstance(gaps, list) or gaps or not isinstance(worker, Mapping):
        return set()

    supported_raw = worker.get("supported_obligation_ids")
    invented_raw = worker.get("invented_obligation_ids")
    worker_gaps = worker.get("source_gap_claims")
    if (
        not isinstance(supported_raw, list)
        or not isinstance(invented_raw, list)
        or not isinstance(worker_gaps, list)
        or worker_gaps
        or any(not isinstance(item, str) for item in [*supported_raw, *invented_raw])
        or len(supported_raw) != len(set(supported_raw))
        or len(invented_raw) != len(set(invented_raw))
    ):
        return set()

    known = {
        str(item.get("obligation_id"))
        for item in obligations
        if isinstance(item, Mapping)
        and item.get("status") == "active"
        and isinstance(item.get("obligation_id"), str)
    }
    supported = set(supported_raw)
    invented = set(invented_raw)
    if not known or not invented or supported & invented or supported | invented != known:
        return set()

    expected = "atomic-recall:invented-obligation:" + ",".join(sorted(invented))
    findings = [str(item) for item in recall.get("findings", [])]
    if findings != [expected]:
        return set()
    return invented


def _project_invented_candidates(
    obligations: Sequence[Mapping[str, Any]],
    invented_ids: set[str],
) -> list[dict[str, Any]] | None:
    """Project only active invented candidates while preserving dependency and source coverage."""
    projected = [
        dict(item)
        for item in obligations
        if not (
            item.get("status") == "active"
            and str(item.get("obligation_id")) in invented_ids
        )
    ]
    remaining_active = {
        str(item.get("obligation_id"))
        for item in projected
        if item.get("status") == "active"
    }
    active_requirements = {
        str(item.get("requirement_id"))
        for item in obligations
        if item.get("status") == "active"
    }
    remaining_requirements = {
        str(item.get("requirement_id"))
        for item in projected
        if item.get("status") == "active"
    }
    if not remaining_active or not active_requirements.issubset(remaining_requirements):
        return None
    for item in projected:
        depends_on = item.get("depends_on", [])
        if isinstance(depends_on, list) and invented_ids.intersection(
            str(value) for value in depends_on
        ):
            return None
    return projected


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
    invented_ids = _exact_invented_partition(recall, obligations)
    if invented_ids:
        projected = _project_invented_candidates(obligations, invented_ids)
        if projected is None:
            return obligations
        guard = sc.guard_obligations(source_index, projected)
        if not guard.get("valid"):
            return obligations
        recheck = gate.atomic_recall_alignment(
            root=root,
            out_dir=out_dir,
            source_index=source_index,
            obligations=projected,
            worker_cache=worker_cache,
        )
        # Projection becomes canonical only after an independent clean recheck.
        return projected if recheck.get("valid") else obligations

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
