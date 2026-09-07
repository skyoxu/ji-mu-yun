#!/usr/bin/env python3
"""Strict Chapter 4/5/6 work-package completion predicate.

This gate intentionally differs from the capability harness: an unavailable live
model backend is *not* a pass. The entire draft -> PRD -> SPEC -> Architecture
work package is complete only when deterministic capability metrics, live semantic
quality, a live fresh-medium <=60 minute run, detached anti-false-green evidence,
selective replay, Architecture reconciliation and the 8-25 regression all pass on
one candidate.

The gate requires a final-evidence manifest that binds the current candidate HEAD
to the exact bytes of every evidence artifact. All denominator evidence must
already be candidate-sealed with the same source_head; unsealed, stale or mixed
run evidence fails closed.

The final result is also the minimal reviewer handoff. When a live denominator
fails, it carries a bounded diagnostic summary so a separately committed
``ch456-final-completion.json`` is sufficient to distinguish environment,
worker-quality, lifecycle and timing failures without publishing the full evidence
bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

SCHEMA = "ch456.final-completion-gate.v1"
MANIFEST_SCHEMA = "ch456.final-evidence-manifest.v1"
EVIDENCE_KEYS = (
    "architecture_reconcile",
    "curated_semantic",
    "semantic_chain_mutations",
    "agent_context_mutations",
    "real_semantic",
    "stable_facade",
    "detached_mutations",
    "selective_replay",
    "live_blind",
    "legacy_replay",
)


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"evidence must be JSON object: {path}")
    return value


def _head() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _status_pass(value: Mapping[str, Any]) -> bool:
    return value.get("status") == "pass"


def _threshold_pass(value: Mapping[str, Any]) -> bool:
    return value.get("threshold_passed") is True



def _all_mutations_rejected(value: Mapping[str, Any], total_key: str,
                            rejected_key: str, rows_key: str, rate_key: str | None = None) -> bool:
    """ADR-0041: one leaked critical mutation blocks, even with a passing summary."""
    total = value.get(total_key)
    rejected = value.get(rejected_key)
    rows = value.get(rows_key)
    return (
        type(total) is int and total > 0
        and type(rejected) is int and rejected == total
        and isinstance(rows, list) and len(rows) == total
        and all(isinstance(row, Mapping) and row.get("rejected") is True for row in rows)
        and (rate_key is None or value.get(rate_key) == 1.0)
    )


def _critical_mutations_pass(value: Mapping[str, Any], *, detached: bool = False) -> bool:
    if not _threshold_pass(value) or value.get("baseline_valid") is not True:
        return False
    if not detached:
        return _all_mutations_rejected(
            value, "mutation_cases", "rejected_cases", "cases", "rejection_rate"
        )
    return (
        _all_mutations_rejected(
            value, "structural_mutation_cases", "structural_rejected_cases",
            "structural_cases", "structural_rejection_rate"
        )
        and _all_mutations_rejected(
            value,
            "failure_family_omission_cases", "failure_family_rejected_cases",
            "failure_family_cases"
        )
        and value.get("failure_family_leaks") == 0
        and value.get("failure_family_leakage_rate") == 0.0
    )


def _score_at_least(value: Mapping[str, Any], score: str, required: str) -> bool:
    observed = value.get(score)
    floor = value.get(required)
    return (
        isinstance(observed, (int, float))
        and isinstance(floor, (int, float))
        and float(observed) >= float(floor)
    )


def _curated_semantic_pass(value: Mapping[str, Any]) -> bool:
    return (
        _status_pass(value)
        and _score_at_least(value, "precision", "required_precision")
        and _score_at_least(value, "recall", "required_recall")
        and value.get("controlled_mutation_rejection_rate") == 1.0
    )


def _selective_replay_pass(value: Mapping[str, Any]) -> bool:
    return (
        _status_pass(value)
        and _score_at_least(value, "accuracy", "required_accuracy")
        and value.get("failed_cases") == 0
    )


def _candidate_bound(value: Mapping[str, Any], current_head: str) -> bool:
    return bool(current_head and value.get("source_head") == current_head)


def _bounded_backend_summary(value: Mapping[str, Any]) -> dict[str, Any] | None:
    backend = value.get("backend")
    if not isinstance(backend, Mapping):
        availability = value.get("availability")
        if isinstance(availability, Mapping):
            backend = availability
        else:
            return None
    keys = ("backend", "available", "blocking_errors", "model", "version", "executable")
    return {key: backend.get(key) for key in keys if key in backend}


def _failure_summary(value: Mapping[str, Any], *, kind: str) -> dict[str, Any]:
    if kind == "real_semantic":
        keys = (
            "status",
            "execution_attempted",
            "execution_succeeded",
            "compiler_status",
            "compiler_stage",
            "compiler_findings",
            "precision_threshold_passed",
            "recall_threshold_passed",
            "atomic_behavior_floor_passed",
            "atomic_quality_metrics",
            "error",
        )
    elif kind == "live_blind":
        keys = (
            "status",
            "execution_attempted",
            "product_acceptance_proven",
            "under_60_minutes",
            "elapsed_seconds",
            "limit_seconds",
            "final_status",
            "vdd_worker_calls",
            "vdd_schema_repairs",
            "quick_dev_worker_calls",
            "retry_count",
            "repeated_fingerprint_stops",
            "failure_stage",
            "error",
        )
    else:
        keys = ("status", "error")
    summary = {key: value.get(key) for key in keys if key in value}
    backend = _bounded_backend_summary(value)
    if backend is not None:
        summary["backend"] = backend
    return summary


def _manifest_findings(
    manifest: Mapping[str, Any],
    *,
    current_head: str,
    paths: Mapping[str, Path],
    evidence: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    findings: list[str] = []
    if manifest.get("schema") != MANIFEST_SCHEMA:
        findings.append("manifest-schema")
    if not current_head or manifest.get("candidate_head") != current_head:
        findings.append("manifest-candidate-head")
    required = manifest.get("required_evidence_keys")
    if required != list(EVIDENCE_KEYS):
        findings.append("manifest-required-keys")
    rows = manifest.get("evidence")
    if not isinstance(rows, Mapping):
        return findings + ["manifest-evidence-map"]
    if set(rows) != set(EVIDENCE_KEYS):
        findings.append("manifest-evidence-key-set")
    for key in EVIDENCE_KEYS:
        row = rows.get(key)
        if not isinstance(row, Mapping):
            findings.append(f"manifest-row:{key}")
            continue
        path = paths[key].resolve()
        if row.get("path") != str(path):
            findings.append(f"manifest-path:{key}")
        if row.get("sha256") != _sha256(path):
            findings.append(f"manifest-sha256:{key}")
        source_head = evidence[key].get("source_head")
        if not isinstance(source_head, str) or not source_head:
            findings.append(f"evidence-unsealed:{key}")
        elif source_head != current_head:
            findings.append(f"evidence-candidate-head:{key}")
        if row.get("source_head") != source_head:
            findings.append(f"manifest-source-head:{key}")
        if row.get("schema") != evidence[key].get("schema"):
            findings.append(f"manifest-schema-binding:{key}")
    return findings


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    paths = {key: Path(getattr(args, key)) for key in EVIDENCE_KEYS}
    evidence = {key: _load(paths[key]) for key in EVIDENCE_KEYS}
    manifest = _load(args.manifest)
    current_head = _head()
    manifest_findings = _manifest_findings(
        manifest,
        current_head=current_head,
        paths=paths,
        evidence=evidence,
    )
    candidate_bindings = {key: _candidate_bound(evidence[key], current_head) for key in EVIDENCE_KEYS}
    checks = {
        "final_evidence_manifest": not manifest_findings,
        "all_evidence_candidate_binding": all(candidate_bindings.values()),
        "architecture_reconcile": _status_pass(evidence["architecture_reconcile"]),
        "curated_semantic": _curated_semantic_pass(evidence["curated_semantic"]),
        "semantic_chain_mutations": _critical_mutations_pass(evidence["semantic_chain_mutations"]),
        "agent_context_mutations": _critical_mutations_pass(evidence["agent_context_mutations"]),
        "real_semantic_quality": (
            evidence["real_semantic"].get("status") == "pass"
            and evidence["real_semantic"].get("execution_attempted") is True
            and evidence["real_semantic"].get("execution_succeeded") is True
        ),
        "stable_facade": _threshold_pass(evidence["stable_facade"]),
        "detached_anti_false_green": _critical_mutations_pass(evidence["detached_mutations"], detached=True),
        "selective_replay": _selective_replay_pass(evidence["selective_replay"]),
        "live_blind_under_60_minutes": (
            evidence["live_blind"].get("status") == "pass"
            and evidence["live_blind"].get("execution_attempted") is True
            and evidence["live_blind"].get("product_acceptance_proven") is True
            and evidence["live_blind"].get("under_60_minutes") is True
        ),
        "legacy_8_25_replay": _status_pass(evidence["legacy_replay"]),
        "live_blind_candidate_binding": candidate_bindings["live_blind"],
        "real_semantic_candidate_binding": candidate_bindings["real_semantic"],
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    failed_evidence: dict[str, Any] = {}
    if "real_semantic_quality" in failed:
        failed_evidence["real_semantic_quality"] = _failure_summary(evidence["real_semantic"], kind="real_semantic")
    if "live_blind_under_60_minutes" in failed:
        failed_evidence["live_blind_under_60_minutes"] = _failure_summary(evidence["live_blind"], kind="live_blind")
    return {
        "schema": SCHEMA,
        "status": "pass" if not failed else "blocked",
        "candidate_head": current_head,
        "manifest_candidate_head": manifest.get("candidate_head"),
        "candidate_bindings": candidate_bindings,
        "manifest_findings": manifest_findings,
        "checks": checks,
        "failed_checks": failed,
        "failed_evidence": failed_evidence,
        "completion": "implementation-work-package-complete" if not failed else "not-complete",
        "authorizes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
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
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
