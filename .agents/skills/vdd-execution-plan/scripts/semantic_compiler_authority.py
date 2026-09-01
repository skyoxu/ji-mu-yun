"""Stable VDD Chapter 4/5/6 compiler authority.

The lower-level semantic_compiler_gate supplies the normative worker envelope
and preflight-bearing schema.  This layer owns stable publication semantics:
failed semantic attempts are content-addressed diagnostics, while canonical
plan artifacts are written only after the corresponding gate is valid.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any, Mapping, Sequence

import semantic_compiler_gate as gate


def _attempt(out_dir: Path, label: str, value: Mapping[str, Any]) -> None:
    digest = gate.sc.sha256_value(value)[7:31]
    gate.sc.atomic_json(out_dir / ".compiler-attempts" / f"{label}-{digest}.json", dict(value))


def _explicit_fixture_cache_wins(out_dir: Path, worker_cache: Mapping[str, Any] | None) -> None:
    """An explicitly supplied deterministic worker fixture supersedes old cache.

    `.compiler-cache` is a replay optimization rather than evidence authority.
    Keeping an older cache ahead of an explicit repair fixture would make the
    stable `--resume-from first-failed-stage` contract impossible to exercise
    and would turn cache presence into semantic authority.
    """
    if worker_cache is None:
        return
    cache_dir = out_dir / ".compiler-cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)


def compile_plan(
    *,
    requirements: Path,
    out_dir: Path,
    companions: Sequence[Path] = (),
    profile: str = "standard",
    worker_cache: Mapping[str, Any] | None = None,
    recommendation_only: bool = False,
    resume_from: str | None = None,
) -> dict[str, Any]:
    if resume_from not in {None, "first-failed-stage"}:
        raise ValueError("unsupported VDD resume mode")
    if recommendation_only and resume_from is not None:
        raise ValueError("recommendation-only cannot be combined with resume")

    if resume_from == "first-failed-stage":
        completed = gate._completed_resume(out_dir)
        if completed is not None:
            return completed

    if recommendation_only:
        return gate._ORIGINAL_COMPILE_PLAN(
            requirements=requirements,
            out_dir=out_dir,
            companions=companions,
            profile=profile,
            worker_cache=worker_cache,
            recommendation_only=True,
        )

    _explicit_fixture_cache_wins(out_dir, worker_cache)
    root = gate.sc.repository_root(requirements.parent)
    source_index = gate.sc.build_source_index(root, requirements, companions)
    preflight = gate.sc.source_preflight(root, source_index)
    if not preflight["valid"]:
        result = {"status": "repair-vdd", "stage": "V0A", "source_index": source_index, "preflight": preflight}
        _attempt(out_dir, "v0a", result)
        return result

    obligations = gate.sc.compile_obligations(
        root=root, out_dir=out_dir, source_index=source_index, worker_cache=worker_cache
    )
    guard = gate.sc.guard_obligations(source_index, obligations)
    if not guard["valid"]:
        result = {"status": "repair-vdd", "stage": "V2", "findings": guard["findings"]}
        _attempt(out_dir, "v2", result)
        return result

    acceptances, failures, _hints = gate.sc.compile_acceptances(
        root=root, out_dir=out_dir, obligations=obligations, worker_cache=worker_cache
    )
    plan_preflight = gate.sc.semantic_preflight(obligations, acceptances, failures)
    if not plan_preflight["valid"]:
        result = {"status": "repair-vdd", "stage": "V3A", "findings": plan_preflight["findings"]}
        _attempt(out_dir, "v3a", result)
        return result

    recall = gate.atomic_recall_alignment(
        root=root,
        out_dir=out_dir,
        source_index=source_index,
        obligations=obligations,
        worker_cache=worker_cache,
    )
    if not recall["valid"]:
        result = {
            "status": "repair-vdd",
            "stage": "V4",
            "gate": "atomic-source-recall",
            "findings": recall["findings"],
            "atomic_quality_metrics": recall["metrics"],
            "source_gap_claims": recall["source_gap_claims"],
        }
        _attempt(out_dir, "v4-atomic-recall", {**result, "alignment": recall})
        return result

    # Canonical recall exists only after the gate is valid. This keeps a failed
    # attempt from poisoning a repaired resume via create-if-absent semantics.
    gate.sc.atomic_json(out_dir / "atomic-recall-alignment.v1.json", recall)

    result = dict(
        gate._ORIGINAL_COMPILE_PLAN(
            requirements=requirements,
            out_dir=out_dir,
            companions=companions,
            profile=profile,
            worker_cache=worker_cache,
            recommendation_only=False,
        )
    )
    result["atomic_quality_metrics"] = recall["metrics"]
    if result.get("status") != "plan-ready":
        _attempt(out_dir, str(result.get("stage") or "compile"), result)
        return result
    if resume_from is not None:
        result["resumed"] = True
        result["resume_from"] = resume_from
        result["resume_strategy"] = "first-failed-stage-cache-replay"
    return result
