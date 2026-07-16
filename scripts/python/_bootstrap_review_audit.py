from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


RUN_PREFIX = "review-gateway-bootstrap-"
LAYERS = ("blind_hunter", "edge_case_hunter", "acceptance_auditor")
KEY_SIDECARS = (
    "review-input.json",
    "preflight-result.json",
    "review-launch-authorization.json",
    "process-leases.json",
    "reviewer-outputs/blind_hunter.json",
    "reviewer-outputs/edge_case_hunter.json",
    "reviewer-outputs/acceptance_auditor.json",
    "review-candidates.json",
    "review-rejections.json",
    "review-gate-state.json",
    "review-gate-result.json",
    "verifier-output.json",
    "review-dispositions.json",
    "review-metrics.json",
    "review-report.md",
)
TOKEN_FILE_SUFFIXES = {".txt", ".log", ".err", ".out"}
TOKEN_RE = re.compile(r"(?im)^tokens used\s*\n?\s*([0-9][0-9,]*)\s*$")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def strict_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
    )
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def load_json(path: Path, unreadable: list[dict[str, str]]) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return strict_json(path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        unreadable.append({"path": path.as_posix(), "error": f"{type(exc).__name__}: {exc}"})
        return {}


def git_value(repository_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def relative(repository_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repository_root.resolve()).as_posix()


def discover_runs(repository_root: Path) -> list[Path]:
    ci_root = repository_root / "logs" / "ci"
    if not ci_root.is_dir():
        return []
    return sorted(
        path
        for path in ci_root.rglob(f"{RUN_PREFIX}*")
        if path.is_dir() and not any(parent.name.startswith(RUN_PREFIX) for parent in path.parents)
    )


def run_category(run_name: str) -> str:
    name = run_name.removeprefix(RUN_PREFIX)
    if name.startswith("7-07-"):
        return "7-07"
    if name.startswith("7-11-"):
        return "7-11"
    if name.startswith("repo-maint-"):
        return "repository-maintenance"
    if name.startswith("vdd-"):
        return "vdd-skill-and-clarification"
    if name.startswith("refactor-"):
        return "focused-refactor-spec"
    return "bootstrap-skill-and-control"


def token_records(repository_root: Path, run_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TOKEN_FILE_SUFFIXES or path.stat().st_size > 5_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for match in TOKEN_RE.findall(text):
            name = path.relative_to(run_dir).as_posix().lower()
            if "probe" in name:
                kind = "probe"
            elif "verifier" in name:
                kind = "verifier"
            elif "retry" in name or "attempt-2" in name or "acl-" in name:
                kind = "retry-labelled"
            else:
                kind = "reviewer-primary"
            records.append(
                {
                    "path": relative(repository_root, path),
                    "sha256": sha256_file(path),
                    "tokens": int(match.replace(",", "")),
                    "kind": kind,
                }
            )
    return records


def parse_timestamp(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def lease_summary(leases: list[Any]) -> dict[str, Any]:
    states: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    timestamps: list[dt.datetime] = []
    duration_seconds = 0.0
    for value in leases:
        if not isinstance(value, dict):
            continue
        states[str(value.get("state") or "missing")] += 1
        operation = str(value.get("operationId") or "")
        if operation.startswith("reviewer:"):
            kinds["reviewer"] += 1
        elif operation == "verifier":
            kinds["verifier"] += 1
        elif "probe" in operation:
            kinds["probe"] += 1
        else:
            kinds["other"] += 1
        acquired = parse_timestamp(value.get("acquiredAt"))
        updated = parse_timestamp(value.get("updatedAt"))
        if acquired:
            timestamps.append(acquired)
        if updated:
            timestamps.append(updated)
        if acquired and updated and updated >= acquired:
            duration_seconds += (updated - acquired).total_seconds()
    wall_seconds = (max(timestamps) - min(timestamps)).total_seconds() if timestamps else None
    return {
        "states": dict(sorted(states.items())),
        "kinds": dict(sorted(kinds.items())),
        "process_duration_seconds": round(duration_seconds, 3),
        "wall_seconds": round(wall_seconds, 3) if wall_seconds is not None else None,
    }


def finding_counts(gate: dict[str, Any]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    severities: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    findings = gate.get("findings") if isinstance(gate.get("findings"), list) else []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severities[str(finding.get("proposedSeverity") or "missing")] += 1
        statuses[str(finding.get("status") or "missing")] += 1
        for role in finding.get("sourceReviewers", []):
            sources[str(role)] += 1
    return dict(sorted(severities.items())), dict(sorted(statuses.items())), dict(sorted(sources.items()))


def classify_run(repository_root: Path, run_dir: Path, unreadable: list[dict[str, str]]) -> dict[str, Any]:
    review_input = load_json(run_dir / "review-input.json", unreadable)
    gate = load_json(run_dir / "review-gate-result.json", unreadable)
    metrics = load_json(run_dir / "review-metrics.json", unreadable)
    preflight = load_json(run_dir / "preflight-result.json", unreadable)
    leases_doc = load_json(run_dir / "process-leases.json", unreadable)
    gate_schema = str(gate.get("schemaVersion") or "")
    gate_status = str(gate.get("status") or "")
    if gate_schema == "review-result.v1":
        execution_state, result_status = "finalized", gate_status
        classification_basis = "review-gate-result.schemaVersion=review-result.v1"
    elif gate_schema == "bootstrap-review-gate-result.v1":
        execution_state, result_status = gate_status or "gate-state-unknown", ""
        classification_basis = f"review-gate-result.schemaVersion=bootstrap-review-gate-result.v1,status={gate_status or 'missing'}"
    else:
        execution_state, result_status = "prepared-no-gate", ""
        classification_basis = "no recognized review-gate-result schema"

    layer_statuses: dict[str, str] = {}
    layer_candidates: dict[str, int] = {}
    for layer in LAYERS:
        payload = load_json(run_dir / "reviewer-outputs" / f"{layer}.json", unreadable)
        layer_statuses[layer] = str(payload.get("status") or "missing")
        candidates = payload.get("candidates")
        layer_candidates[layer] = len(candidates) if isinstance(candidates, list) else 0

    missing_sidecars: list[str] = []
    sidecar_hashes: list[dict[str, Any]] = []
    for rel in KEY_SIDECARS:
        path = run_dir / rel
        if not path.is_file():
            missing_sidecars.append(rel)
        else:
            sidecar_hashes.append(
                {
                    "path": relative(repository_root, path),
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                }
            )

    tokens = token_records(repository_root, run_dir)
    files = [path for path in run_dir.rglob("*") if path.is_file()]
    cost = review_input.get("reviewCostEstimate") if isinstance(review_input.get("reviewCostEstimate"), dict) else {}
    severity, finding_status, finding_sources = finding_counts(gate)
    return {
        "run_path": relative(repository_root, run_dir),
        "run_name": run_dir.name,
        "category": run_category(run_dir.name),
        "review_id": review_input.get("reviewId"),
        "profile": review_input.get("profileName"),
        "change_id": review_input.get("changeId"),
        "full_review_round": review_input.get("fullReviewRound"),
        "execution_mode": review_input.get("executionMode"),
        "worktree_dirty": review_input.get("worktreeDirty"),
        "artifact_count": len(review_input.get("artifacts", [])) if isinstance(review_input.get("artifacts"), list) else 0,
        "artifact_bytes": cost.get("totalBytes", 0),
        "preflight_status": preflight.get("status"),
        "launch_authorized": (run_dir / "review-launch-authorization.json").is_file(),
        "execution_state": execution_state,
        "classification_basis": classification_basis,
        "result_status": result_status,
        "gate_schema": gate_schema,
        "layer_statuses": layer_statuses,
        "reviewer_submission_counts": layer_candidates,
        "metrics": {
            key: metrics.get(key)
            for key in (
                "rawCandidateCount", "acceptedUniqueCount", "rejectedCount", "confirmedCount",
                "advisoryCount", "unverifiedCount", "refutedCount",
            )
        },
        "final_finding_count": sum(severity.values()),
        "final_finding_severity": severity,
        "final_finding_status": finding_status,
        "final_finding_source_roles": finding_sources,
        "lease_summary": lease_summary(leases_doc.get("leases", []) if isinstance(leases_doc.get("leases"), list) else []),
        "token_records": tokens,
        "token_total": sum(item["tokens"] for item in tokens),
        "file_count": len(files),
        "directory_bytes": sum(path.stat().st_size for path in files),
        "key_sidecars": sidecar_hashes,
        "missing_key_sidecars": missing_sidecars,
    }
