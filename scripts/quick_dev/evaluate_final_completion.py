#!/usr/bin/env python3
"""Strict Chapter 4/5/6 work-package completion predicate.

This gate intentionally differs from the capability harness: an unavailable live
model backend is *not* a pass.  The entire draft -> PRD -> SPEC -> Architecture
work package is complete only when deterministic capability metrics, live semantic
quality, a live fresh-medium <=60 minute run, detached anti-false-green evidence,
selective replay, Architecture reconciliation and the 8-25 regression all pass on
one candidate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

SCHEMA = "ch456.final-completion-gate.v1"


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"evidence must be JSON object: {path}")
    return value


def _head() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _status_pass(value: Mapping[str, Any]) -> bool:
    return value.get("status") == "pass"


def _threshold_pass(value: Mapping[str, Any]) -> bool:
    return value.get("threshold_passed") is True


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    evidence = {
        "architecture_reconcile": _load(args.architecture_reconcile),
        "curated_semantic": _load(args.curated_semantic),
        "semantic_chain_mutations": _load(args.semantic_chain_mutations),
        "agent_context_mutations": _load(args.agent_context_mutations),
        "real_semantic": _load(args.real_semantic),
        "stable_facade": _load(args.stable_facade),
        "detached_mutations": _load(args.detached_mutations),
        "selective_replay": _load(args.selective_replay),
        "live_blind": _load(args.live_blind),
        "legacy_replay": _load(args.legacy_replay),
    }
    checks = {
        "architecture_reconcile": _status_pass(evidence["architecture_reconcile"]),
        "curated_semantic": _status_pass(evidence["curated_semantic"]),
        "semantic_chain_mutations": _threshold_pass(evidence["semantic_chain_mutations"]),
        "agent_context_mutations": _threshold_pass(evidence["agent_context_mutations"]),
        "real_semantic_quality": (
            evidence["real_semantic"].get("status") == "pass"
            and evidence["real_semantic"].get("execution_attempted") is True
            and evidence["real_semantic"].get("execution_succeeded") is True
        ),
        "stable_facade": _threshold_pass(evidence["stable_facade"]),
        "detached_anti_false_green": _threshold_pass(evidence["detached_mutations"]),
        "selective_replay": _threshold_pass(evidence["selective_replay"]),
        "live_blind_under_60_minutes": (
            evidence["live_blind"].get("status") == "pass"
            and evidence["live_blind"].get("execution_attempted") is True
            and evidence["live_blind"].get("product_acceptance_proven") is True
            and evidence["live_blind"].get("under_60_minutes") is True
        ),
        "legacy_8_25_replay": _status_pass(evidence["legacy_replay"]),
    }
    current_head = _head()
    live_head = str(evidence["live_blind"].get("source_head") or "")
    checks["live_blind_candidate_binding"] = bool(current_head and live_head == current_head)
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema": SCHEMA,
        "status": "pass" if not failed else "blocked",
        "candidate_head": current_head,
        "checks": checks,
        "failed_checks": failed,
        "completion": "implementation-work-package-complete" if not failed else "not-complete",
        "authorizes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--architecture-reconcile", type=Path, required=True)
    parser.add_argument("--curated-semantic", type=Path, required=True)
    parser.add_argument("--semantic-chain-mutations", type=Path, required=True)
    parser.add_argument("--agent-context-mutations", type=Path, required=True)
    parser.add_argument("--real-semantic", type=Path, required=True)
    parser.add_argument("--stable-facade", type=Path, required=True)
    parser.add_argument("--detached-mutations", type=Path, required=True)
    parser.add_argument("--selective-replay", type=Path, required=True)
    parser.add_argument("--live-blind", type=Path, required=True)
    parser.add_argument("--legacy-replay", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("ch456-final-completion.json"))
    args = parser.parse_args()
    try:
        result = evaluate(args)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "schema": SCHEMA,
            "status": "blocked",
            "completion": "not-complete",
            "failed_checks": ["evidence-load"],
            "error": str(exc),
            "authorizes": [],
        }
    args.out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
