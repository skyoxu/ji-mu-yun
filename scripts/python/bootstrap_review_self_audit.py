#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any

from _bootstrap_review_audit import (
    LAYERS,
    classify_run,
    discover_runs,
    git_value,
    relative,
    sha256_file,
)


SCHEMA_VERSION = "bootstrap-review-self-audit.v1"
SCRIPT_VERSION = "bootstrap-review-self-audit.py.v1"


def counter_add(target: Counter[str], values: dict[str, Any]) -> None:
    for key, value in values.items():
        if isinstance(value, int) and not isinstance(value, bool):
            target[key] += value


def summarize(runs: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    all_submissions: Counter[str] = Counter()
    finalized_submissions: Counter[str] = Counter()
    metrics: Counter[str] = Counter()
    final_severity: Counter[str] = Counter()
    final_status: Counter[str] = Counter()
    final_sources: Counter[str] = Counter()
    token_kind: Counter[str] = Counter()
    token_finality: Counter[str] = Counter()
    lease_states: Counter[str] = Counter()
    lease_kinds: Counter[str] = Counter()
    execution_states: Counter[str] = Counter()
    result_statuses: Counter[str] = Counter()
    categories: Counter[str] = Counter()

    for run in runs:
        finalized = run["execution_state"] == "finalized"
        execution_states[run["execution_state"]] += 1
        categories[run["category"]] += 1
        if finalized:
            result_statuses[str(run["result_status"] or "missing")] += 1
        for layer in LAYERS:
            count = int(run["reviewer_submission_counts"].get(layer) or 0)
            all_submissions[layer] += count
            if finalized:
                finalized_submissions[layer] += count
        if finalized:
            counter_add(metrics, run["metrics"])
            counter_add(final_severity, run["final_finding_severity"])
            counter_add(final_status, run["final_finding_status"])
            counter_add(final_sources, run["final_finding_source_roles"])
        for record in run["token_records"]:
            token_kind[record["kind"]] += record["tokens"]
            token_finality["finalized" if finalized else "non-finalized"] += record["tokens"]
        counter_add(lease_states, run["lease_summary"]["states"])
        counter_add(lease_kinds, run["lease_summary"]["kinds"])

    candidate_funnel = {
        "schema_version": f"{SCHEMA_VERSION}.candidate-funnel",
        "definitions": {
            "all_run_reviewer_submissions": "Sum of reviewer-output candidate arrays across every discovered run, including non-finalized runs.",
            "finalized_run_reviewer_submissions": "Sum of reviewer-output candidate arrays only where review-gate-result has schemaVersion review-result.v1.",
            "gateway_raw_candidate_count": "Sum of review-metrics.rawCandidateCount across finalized runs.",
            "gateway_accepted_unique_count": "Sum of review-metrics.acceptedUniqueCount across finalized runs after gateway validation and deduplication.",
            "gateway_rejected_count": "Sum of review-metrics.rejectedCount across finalized runs.",
        },
        "all_run_reviewer_submissions_by_role": dict(sorted(all_submissions.items())),
        "all_run_reviewer_submissions": sum(all_submissions.values()),
        "finalized_run_reviewer_submissions_by_role": dict(sorted(finalized_submissions.items())),
        "finalized_run_reviewer_submissions": sum(finalized_submissions.values()),
        "gateway": dict(sorted(metrics.items())),
        "final_findings_by_severity": dict(sorted(final_severity.items())),
        "final_findings_by_status": dict(sorted(final_status.items())),
        "final_finding_source_roles": dict(sorted(final_sources.items())),
    }
    token_summary = {
        "schema_version": f"{SCHEMA_VERSION}.token-duration-summary",
        "definitions": {
            "token_total": "Lower bound from anchored 'tokens used' records in UTF-8 .txt/.log/.err/.out files up to 5 MiB.",
            "retry_label": "Filename contains retry, attempt-2, or acl-; this indicates re-execution cost but is not automatically classified as fully avoidable waste.",
            "duration": "Derived from process-leases acquiredAt and updatedAt timestamps when both parse successfully.",
        },
        "tokens_by_execution_kind": dict(sorted(token_kind.items())),
        "tokens_by_run_finality": dict(sorted(token_finality.items())),
        "token_total": sum(token_kind.values()),
        "lease_states": dict(sorted(lease_states.items())),
        "lease_kinds": dict(sorted(lease_kinds.items())),
        "directory_bytes": sum(run["directory_bytes"] for run in runs),
        "non_finalized_directory_bytes": sum(run["directory_bytes"] for run in runs if run["execution_state"] != "finalized"),
    }
    overview = {
        "run_count": len(runs),
        "categories": dict(sorted(categories.items())),
        "execution_states": dict(sorted(execution_states.items())),
        "final_result_statuses": dict(sorted(result_statuses.items())),
    }
    return candidate_funnel, token_summary, overview


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def implementation_hashes(repository_root: Path) -> list[dict[str, str]]:
    paths = [
        Path(__file__).resolve(),
        Path(__file__).resolve().with_name("_bootstrap_review_audit.py"),
    ]
    return [
        {"path": relative(repository_root, path), "sha256": sha256_file(path)}
        for path in paths
    ]


def run_audit(repository_root: Path, out_dir: Path, audit_id: str) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    out_dir = out_dir.resolve()
    unreadable: list[dict[str, str]] = []
    runs = [
        classify_run(repository_root, run_dir, unreadable)
        for run_dir in discover_runs(repository_root)
    ]
    candidate_funnel, token_summary, overview = summarize(runs)
    implementations = implementation_hashes(repository_root)
    input_manifest = {
        "schema_version": f"{SCHEMA_VERSION}.input-manifest",
        "audit_id": audit_id,
        "repository_git_head": git_value(repository_root, "rev-parse", "HEAD"),
        "repository_git_status": git_value(repository_root, "status", "--porcelain=v1"),
        "script_version": SCRIPT_VERSION,
        "implementation_files": implementations,
        "reproduction_command": (
            "py -3 scripts/python/bootstrap_review_self_audit.py "
            f"--audit-id {audit_id} --out-dir {relative(repository_root, out_dir)}"
        ),
        "run_discovery_rule": "logs/ci/**/review-gateway-bootstrap-* directories not nested beneath another matching run directory",
        "run_count": len(runs),
        "run_paths": [run["run_path"] for run in runs],
        "unreadable_inputs": unreadable,
    }
    per_run = {
        "schema_version": f"{SCHEMA_VERSION}.per-run-classification",
        "audit_id": audit_id,
        "runs": runs,
    }
    candidate_funnel["audit_id"] = audit_id
    token_summary["audit_id"] = audit_id
    write_json(out_dir / "audit-input-manifest.json", input_manifest)
    write_json(out_dir / "per-run-classification.json", per_run)
    write_json(out_dir / "candidate-funnel.json", candidate_funnel)
    write_json(out_dir / "token-and-duration-summary.json", token_summary)

    finalized_submissions = candidate_funnel["finalized_run_reviewer_submissions"]
    raw_count = int(candidate_funnel["gateway"].get("rawCandidateCount") or 0)
    accepted = int(candidate_funnel["gateway"].get("acceptedUniqueCount") or 0)
    rejected = int(candidate_funnel["gateway"].get("rejectedCount") or 0)
    checks = [
        {"id": "run-count-positive", "status": "pass" if runs else "fail", "observed": len(runs)},
        {
            "id": "finalized-submissions-match-gateway-raw",
            "status": "pass" if finalized_submissions == raw_count else "fail",
            "observed": {"submissions": finalized_submissions, "raw": raw_count},
        },
        {
            "id": "gateway-funnel-closes",
            "status": "pass" if raw_count == accepted + rejected else "fail",
            "observed": {"raw": raw_count, "accepted": accepted, "rejected": rejected},
        },
        {"id": "inputs-readable", "status": "pass" if not unreadable else "fail", "observed": len(unreadable)},
    ]
    component_paths = [
        out_dir / "audit-input-manifest.json",
        out_dir / "per-run-classification.json",
        out_dir / "candidate-funnel.json",
        out_dir / "token-and-duration-summary.json",
    ]
    result = {
        "schema_version": f"{SCHEMA_VERSION}.result",
        "audit_id": audit_id,
        "status": "pass" if all(item["status"] == "pass" for item in checks) else "fail",
        "repository_git_head": input_manifest["repository_git_head"],
        "implementation_files": implementations,
        "run_count": len(runs),
        "checks": checks,
        "components": [
            {"path": path.name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
            for path in component_paths
        ],
        "overview": overview,
        "candidate_funnel": candidate_funnel,
        "token_and_duration": token_summary,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    write_json(out_dir / "audit-result.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only self-audit for repository Bootstrap Review run logs.")
    parser.add_argument("--repository-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument(
        "--audit-id",
        default=dt.datetime.now(dt.timezone.utc).strftime("bootstrap-self-audit-%Y%m%dT%H%M%SZ"),
    )
    parser.add_argument("--out-dir", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repository_root = Path(args.repository_root).resolve()
    out_dir = (
        Path(args.out_dir).resolve()
        if args.out_dir
        else repository_root / "logs" / "ci" / "bootstrap-self-audit" / args.audit_id
    )
    result = run_audit(repository_root, out_dir, str(args.audit_id))
    print(
        json.dumps(
            {
                "status": result["status"],
                "audit_id": result["audit_id"],
                "run_count": result["run_count"],
                "out_dir": str(out_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
