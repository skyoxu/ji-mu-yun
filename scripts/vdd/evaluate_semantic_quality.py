#!/usr/bin/env python3
"""Measure deterministic semantic-quality gates on a curated atomic corpus.

This benchmark intentionally separates two claims:
1. the VDD semantic contract/gate preserves a curated atomic ground truth at
   >=95% recall/precision and rejects controlled omissions/inventions;
2. live-model extraction quality is *not* claimed when the real model backend
   is unavailable. That separate fact is recorded by probe_real_worker.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".agents" / "skills" / "vdd-execution-plan" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from semantic_compiler import _normalize_obligation
from semantic_compiler_gate import atomic_recall_alignment


def _raw(source_ref: str, subject: str, trigger: str, behavior: str, observable: str, requirement_type: str) -> dict[str, Any]:
    return {
        "source_refs": [source_ref],
        "subject": subject,
        "trigger": trigger,
        "state_before": "behavior not yet applied",
        "state_after": "behavior applied",
        "expected_behavior": behavior,
        "observable_result": observable,
        "forbidden_result": ["opposite observable behavior"],
        "requirement_type": requirement_type,
        "obligation_kind": "behavior",
        "unresolved_fragments": [],
        "status": "active",
        "depends_on": [],
    }


def _corpus() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    specs = [
        ("FR-1", "cache", "a key is read", ["return a fresh value after expiry", "reuse a value before expiry", "never return a deleted value"], "Product"),
        ("FR-2", "rate limiter", "a request arrives", ["allow requests below the limit", "reject the first request above the limit", "restore capacity after the window"], "Product"),
        ("FR-3", "workspace", "a session starts", ["isolate one user workspace", "reject cross-user access", "restore the same workspace after reconnect"], "Platform"),
        ("FR-4", "compiler", "a plan is compiled", ["emit stable obligation identities", "reject uncovered source behavior", "keep runtime evidence out of planning"], "Platform"),
        ("FR-5", "executor", "a selector is dispatched", ["run with shell disabled", "record a real process attempt", "reject zero-case success"], "Platform"),
        ("FR-6", "judge", "a receipt is classified", ["derive failure from observation", "reject producer self-report", "produce a stable failure fingerprint"], "Platform"),
        ("FR-7", "recovery", "a run resumes", ["use an explicit predecessor", "reject stale hashes", "never scan latest-success history"], "Platform"),
        ("FR-8", "terminal", "completion is evaluated", ["require exact Acceptance cover", "re-read current dependencies", "reject duplicate closure tuples"], "Platform"),
        ("FR-9", "profile router", "a profile is selected", ["preserve the truth floor", "allow targeted fast-ship scope", "require detached proof for self-hosted promotion"], "Governance"),
        ("FR-10", "write-set gate", "an implementation worker returns", ["allow declared production writes", "reject selector mutation", "reject evidence mutation"], "Governance"),
    ]
    entries: list[dict[str, Any]] = []
    obligations: list[dict[str, Any]] = []
    for order, (rid, subject, trigger, behaviors, requirement_type) in enumerate(specs, start=1):
        source_ref = f"curated.md#{rid}"
        entries.append({
            "requirement_id": rid,
            "source_ref": source_ref,
            "source_text": "; ".join(behaviors),
            "source_order": order,
        })
        for index, behavior in enumerate(behaviors, start=1):
            raw = _raw(source_ref, subject, trigger, behavior, f"{subject} observable {index}", requirement_type)
            obligations.append(_normalize_obligation({"requirement_id": rid, "source_ref": source_ref}, raw))
    return {"schema": "source-index.v1", "entries": entries}, obligations


def _align(source_index: dict[str, Any], obligations: list[dict[str, Any]], worker: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    return atomic_recall_alignment(
        root=ROOT,
        out_dir=out_dir,
        source_index=source_index,
        obligations=obligations,
        worker_cache={"v4-atomic-recall": worker},
    )


def evaluate() -> dict[str, Any]:
    source_index, obligations = _corpus()
    ids = [item["obligation_id"] for item in obligations]
    with tempfile.TemporaryDirectory(prefix="ch456-semantic-metric-") as raw_tmp:
        tmp = Path(raw_tmp)
        positive = _align(source_index, obligations, {
            "supported_obligation_ids": ids,
            "invented_obligation_ids": [],
            "source_gap_claims": [],
        }, tmp / "positive")

        missing = _align(source_index, obligations, {
            "supported_obligation_ids": ids[:-1],
            "invented_obligation_ids": [],
            "source_gap_claims": [{
                "source_ref": source_index["entries"][-1]["source_ref"],
                "subject": obligations[-1]["subject"],
                "behavior": obligations[-1]["expected_behavior"],
                "reason": "controlled curated omission",
            }],
        }, tmp / "missing")

        invented = _align(source_index, obligations, {
            "supported_obligation_ids": ids[:-1],
            "invented_obligation_ids": [ids[-1]],
            "source_gap_claims": [{
                "source_ref": source_index["entries"][-1]["source_ref"],
                "subject": obligations[-1]["subject"],
                "behavior": obligations[-1]["expected_behavior"],
                "reason": "controlled curated invention leaves the real behavior uncovered",
            }],
        }, tmp / "invented")

    precision = float(positive["metrics"]["precision"])
    recall = float(positive["metrics"]["recall"])
    mutations = [missing, invented]
    mutation_rejection_rate = sum(1 for result in mutations if result["valid"] is False) / len(mutations)
    status = "pass" if precision >= 0.95 and recall >= 0.95 and mutation_rejection_rate == 1.0 else "fail"
    return {
        "schema": "vdd.curated-semantic-quality-metric.v1",
        "execution_mode": "deterministic-curated-independent-oracle",
        "curated_requirement_count": len(source_index["entries"]),
        "curated_atomic_obligation_count": len(obligations),
        "precision": precision,
        "recall": recall,
        "required_precision": 0.95,
        "required_recall": 0.95,
        "controlled_mutation_count": len(mutations),
        "controlled_mutation_rejection_rate": mutation_rejection_rate,
        "live_model_extraction_quality_proven": False,
        "live_model_evidence_ref": "ch456-real-worker-probe.json",
        "status": status,
        "authorizes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = evaluate()
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
