"""Stable VDD compiler authority with an independent atomic source-recall gate.

The legacy semantic_compiler owns the canonical V0->V7 artifact construction.
This wrapper inserts an additional fail-closed source-vs-obligation oracle before
that compiler is allowed to publish plan-ready artifacts. The oracle is read-only
and cannot authorize implementation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from semantic_compiler import (
    atomic_json,
    build_source_index,
    compile_acceptances,
    compile_obligations,
    compile_plan as _compile_plan,
    guard_obligations,
    invoke_worker,
    repository_root,
    semantic_preflight,
    source_preflight,
)


def atomic_recall_alignment(
    *,
    root: Path,
    out_dir: Path,
    source_index: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    worker_cache: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Independently compare frozen source claims with the V1 obligation set."""
    payload = {
        "source_index": source_index,
        "obligations": list(obligations),
    }
    raw = invoke_worker(
        root=root,
        out_dir=out_dir,
        stage="v4-atomic-recall",
        payload=payload,
        worker_cache=worker_cache,
        prompt=(
            "Independently compare each frozen requirement source to the proposed atomic obligations. "
            "Do not trust the prior extractor and do not read another worker's reasoning. Return JSON with "
            "supported_obligation_ids[], invented_obligation_ids[], source_gap_claims[]. "
            "Each source_gap_claim must be an object with source_ref, subject, behavior, reason and must describe "
            "one independently observable behavior present in source but absent from the obligation set. "
            "An obligation that merges multiple independent source behaviors is not sufficient coverage: report the "
            "unrepresented behavior as a source_gap_claim. Never invent runtime evidence."
        ),
    )
    for key in ("supported_obligation_ids", "invented_obligation_ids", "source_gap_claims"):
        if not isinstance(raw.get(key), list):
            raise ValueError(f"atomic recall oracle missing {key}")

    known = {str(item["obligation_id"]) for item in obligations if item.get("status") == "active"}
    source_refs = {str(item["source_ref"]) for item in source_index.get("entries", []) if isinstance(item, Mapping)}
    supported = {str(value) for value in raw["supported_obligation_ids"] if isinstance(value, str)}
    invented = {str(value) for value in raw["invented_obligation_ids"] if isinstance(value, str)}
    findings: list[str] = []

    unknown_supported = supported - known
    unknown_invented = invented - known
    if unknown_supported:
        findings.append("atomic-recall:unknown-supported:" + ",".join(sorted(unknown_supported)))
    if unknown_invented:
        findings.append("atomic-recall:unknown-invented:" + ",".join(sorted(unknown_invented)))
    if supported & invented:
        findings.append("atomic-recall:supported-invented-overlap:" + ",".join(sorted(supported & invented)))
    if (supported | invented) != known:
        findings.append("atomic-recall:obligation-partition-incomplete:" + ",".join(sorted(known - (supported | invented))))

    normalized_gaps: list[dict[str, str]] = []
    seen_gap_keys: set[tuple[str, str, str]] = set()
    for index, item in enumerate(raw["source_gap_claims"]):
        if not isinstance(item, Mapping):
            findings.append(f"atomic-recall:gap[{index}]:not-object")
            continue
        source_ref = item.get("source_ref")
        subject = item.get("subject")
        behavior = item.get("behavior")
        reason = item.get("reason")
        if not all(isinstance(value, str) and value.strip() for value in (source_ref, subject, behavior, reason)):
            findings.append(f"atomic-recall:gap[{index}]:shape")
            continue
        source_ref = str(source_ref).strip()
        subject = str(subject).strip()
        behavior = str(behavior).strip()
        reason = str(reason).strip()
        if source_ref not in source_refs:
            findings.append(f"atomic-recall:gap[{index}]:unknown-source-ref")
            continue
        key = (source_ref, subject.casefold(), behavior.casefold())
        if key in seen_gap_keys:
            findings.append(f"atomic-recall:gap[{index}]:duplicate")
            continue
        seen_gap_keys.add(key)
        normalized_gaps.append({"source_ref": source_ref, "subject": subject, "behavior": behavior, "reason": reason})

    if invented:
        findings.append("atomic-recall:invented-obligation:" + ",".join(sorted(invented)))
    if normalized_gaps:
        findings.append("atomic-recall:source-gap-count:" + str(len(normalized_gaps)))

    true_positive = len(supported & known)
    false_positive = len(invented & known)
    false_negative = len(normalized_gaps) + len(known - (supported | invented))
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else (1.0 if not known else 0.0)
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    metrics = {
        "active_obligation_count": len(known),
        "supported_obligation_count": true_positive,
        "invented_obligation_count": false_positive,
        "source_gap_count": len(normalized_gaps),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }
    return {
        "schema": "vdd.atomic-recall-alignment.v1",
        "valid": not findings,
        "findings": findings,
        "metrics": metrics,
        "source_gap_claims": normalized_gaps,
        "worker": dict(raw),
        "authorizes": [],
    }


def compile_plan(
    *,
    requirements: Path,
    out_dir: Path,
    companions: Sequence[Path] = (),
    profile: str = "standard",
    worker_cache: Mapping[str, Any] | None = None,
    recommendation_only: bool = False,
) -> dict[str, Any]:
    """Run source/obligation preflight plus atomic recall before canonical publication."""
    if recommendation_only:
        return _compile_plan(
            requirements=requirements,
            out_dir=out_dir,
            companions=companions,
            profile=profile,
            worker_cache=worker_cache,
            recommendation_only=True,
        )

    root = repository_root(requirements.parent)
    source_index = build_source_index(root, requirements, companions)
    preflight = source_preflight(root, source_index)
    if not preflight["valid"]:
        return {"status": "repair-vdd", "stage": "V0A", "source_index": source_index, "preflight": preflight}

    obligations = compile_obligations(root=root, out_dir=out_dir, source_index=source_index, worker_cache=worker_cache)
    guard = guard_obligations(source_index, obligations)
    if not guard["valid"]:
        return {"status": "repair-vdd", "stage": "V2", "findings": guard["findings"]}

    acceptances, failures, _hints = compile_acceptances(root=root, out_dir=out_dir, obligations=obligations, worker_cache=worker_cache)
    plan_preflight = semantic_preflight(obligations, acceptances, failures)
    if not plan_preflight["valid"]:
        return {"status": "repair-vdd", "stage": "V3A", "findings": plan_preflight["findings"]}

    recall = atomic_recall_alignment(
        root=root,
        out_dir=out_dir,
        source_index=source_index,
        obligations=obligations,
        worker_cache=worker_cache,
    )
    atomic_json(out_dir / "atomic-recall-alignment.v1.json", recall)
    if not recall["valid"]:
        return {
            "status": "repair-vdd",
            "stage": "V4",
            "gate": "atomic-source-recall",
            "findings": recall["findings"],
            "atomic_quality_metrics": recall["metrics"],
            "source_gap_claims": recall["source_gap_claims"],
        }

    result = _compile_plan(
        requirements=requirements,
        out_dir=out_dir,
        companions=companions,
        profile=profile,
        worker_cache=worker_cache,
        recommendation_only=False,
    )
    result = dict(result)
    result["atomic_quality_metrics"] = recall["metrics"]
    return result
