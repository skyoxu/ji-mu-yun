#!/usr/bin/env python3
"""Run one approved deterministic Chapter 4/5/6 metric and bind its output to HEAD.

This is deliberately not an arbitrary command wrapper. Each metric name maps to
one repository-owned producer and fixed arguments. The candidate HEAD is read
before and after producer execution; output is stamped only when HEAD is stable
and the producer actually created a JSON evidence object during this invocation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "ch456.candidate-bound-metric-run.v1"
LEGACY_PLAN = "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery"
LEGACY_BASELINE = "7890d90cd9a9183159742bacc5575a07ad061dc7"

PRODUCERS: dict[str, tuple[str, ...]] = {
    "architecture-reconcile": ("scripts/vdd/evaluate_architecture_reconcile.py",),
    "curated-semantic": ("scripts/vdd/evaluate_semantic_quality.py",),
    "semantic-chain-mutations": ("scripts/vdd/evaluate_semantic_chain_mutations.py",),
    "agent-context-mutations": ("scripts/vdd/evaluate_agent_context_mutations.py",),
    "stable-facade": ("scripts/quick_dev/evaluate_stable_facade.py",),
    "detached-mutations": ("scripts/quick_dev/evaluate_detached_mutations.py",),
    "selective-replay": ("scripts/quick_dev/evaluate_replay_matrix.py",),
    "legacy-replay": (
        "scripts/quick_dev/replay_legacy_tdd.py",
        "--plan", LEGACY_PLAN,
        "--red-baseline", LEGACY_BASELINE,
    ),
}


def _head() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"producer output must be a JSON object: {path}")
    return value


def run(metric: str, out: Path) -> tuple[int, dict[str, Any]]:
    if metric not in PRODUCERS:
        raise ValueError(f"unsupported metric: {metric}")
    out = out.resolve()
    try:
        out.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("--out must remain inside the repository") from exc
    if out.exists():
        if not out.is_file():
            raise ValueError(f"refusing to replace non-file output: {out}")
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)

    before = _head()
    if not before:
        raise ValueError("candidate HEAD unavailable before metric execution")
    started_ns = time.time_ns()
    argv = [sys.executable, *PRODUCERS[metric], "--out", str(out)]
    proc = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)
    after = _head()
    if after != before:
        raise ValueError(f"candidate HEAD changed during metric execution: {before} -> {after}")
    if not out.is_file():
        raise ValueError(f"producer did not create evidence: {metric}")
    if out.stat().st_mtime_ns < started_ns:
        raise ValueError(f"producer output predates this invocation: {metric}")

    value = _load(out)
    existing = value.get("source_head")
    if existing is not None and existing != before:
        raise ValueError(f"producer candidate binding mismatch: {metric}: {existing} != {before}")
    value["source_head"] = before
    value["candidate_metric_producer"] = metric
    out.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    receipt = {
        "schema": SCHEMA,
        "metric": metric,
        "candidate_head": before,
        "producer_argv": argv,
        "producer_exit_code": proc.returncode,
        "evidence_path": str(out),
        "evidence_schema": value.get("schema"),
        "status": "pass" if proc.returncode == 0 else "producer-failed",
        "stdout_tail": proc.stdout[-1600:],
        "stderr_tail": proc.stderr[-1600:],
        "authorizes": [],
    }
    return proc.returncode, receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metric", choices=tuple(PRODUCERS), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path)
    args = parser.parse_args()
    try:
        code, receipt = run(args.metric, args.out)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, subprocess.SubprocessError) as exc:
        code = 1
        receipt = {
            "schema": SCHEMA,
            "metric": args.metric,
            "candidate_head": _head(),
            "status": "blocked",
            "error": str(exc),
            "authorizes": [],
        }
    payload = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.receipt_out:
        args.receipt_out.parent.mkdir(parents=True, exist_ok=True)
        args.receipt_out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
