from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib


def validate_candidate_review_documents(
    plan_root: Path,
    candidate_path: str,
    candidate: dict[str, Any],
    review_input: dict[str, Any],
    preflight: dict[str, Any],
    review_result: dict[str, Any],
    dispositions: dict[str, Any],
    predicate: str,
    p2_deferrals: list[dict[str, Any]],
    current_plan_hash: str,
    current_source_hash: str,
    expected_slice_id: str,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    def add(rule: str, message: str) -> None:
        findings.append({"rule_id": rule, "target": candidate_path, "message": message})
    required_candidate = {"schema_version", "predicate", "status", "plan_hash", "source_hash", "slice_id", "authority_revision", "candidate_commit_or_tree_hash", "authorizes", "does_not_authorize"}
    if not required_candidate.issubset(candidate) or candidate.get("schema_version") != "jimuyun.tdd-result.v1" or candidate.get("predicate") != "implementation-candidate" or candidate.get("status") != "pass":
        add("RMAP-REVIEW-EVIDENCE-BINDING", "candidate result shape or state is invalid")
    if candidate.get("authorizes") != ["bootstrap-review"] or set(candidate.get("does_not_authorize", [])) != {"implementation-accepted", "protected-handoff", "release-ready"}:
        add("RMAP-REVIEW-EVIDENCE-BINDING", "candidate authority set is invalid")
    if candidate.get("plan_hash") != current_plan_hash or candidate.get("source_hash") != current_source_hash or candidate.get("slice_id") != expected_slice_id:
        add("RMAP-REVIEW-EVIDENCE-BINDING", "candidate plan, source, or slice identity is stale")
    if candidate.get("authority_revision") != review_input.get("authorityRevision"):
        add("RMAP-REVIEW-EVIDENCE-BINDING", "candidate authority revision differs from review input")
    repository_root = plan_root.parents[1]
    path = (repository_root / candidate_path).resolve()
    try:
        relative = path.relative_to(repository_root).as_posix()
    except ValueError:
        add("RMAP-REVIEW-EVIDENCE-BINDING", "candidate path escapes repository"); relative = ""
    artifacts = {item.get("artifact"): item.get("sha256") for item in review_input.get("artifacts", []) if isinstance(item, dict)}
    actual_hash = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    if not relative.startswith("logs/tdd-adapter/") or artifacts.get(relative) != actual_hash:
        add("RMAP-REVIEW-EVIDENCE-BINDING", "review input does not hash-bind candidate result")
    identity = ("reviewId", "routeVersion", "policyRevision", "authorityRevision", "inputHash")
    if any(review_result.get(key) != review_input.get(key) for key in identity) or any(preflight.get(key) != review_input.get(key) for key in identity):
        add("RMAP-REVIEW-EVIDENCE-BINDING", "review or preflight identity differs from review input")
    if preflight.get("status") != "passed" or any(item.get("status") != "passed" for item in preflight.get("checks", [])):
        add("RMAP-REVIEW-EVIDENCE-BINDING", "deterministic preflight is not fully passed")
    required_checks = set(review_input.get("deterministicPreflightPolicy", {}).get("requiredChecks", [])) | {item.get("checkId") for item in review_input.get("planBoundRequiredChecks", []) if isinstance(item, dict)}
    passed_checks = {item.get("checkId") for item in preflight.get("checks", []) if item.get("status") == "passed"}
    if not required_checks or not required_checks.issubset(passed_checks):
        add("RMAP-REVIEW-EVIDENCE-BINDING", "required check binding is incomplete")
    if dispositions and any(dispositions.get(key) != review_input.get(key) for key in identity):
        add("RMAP-REVIEW-EVIDENCE-BINDING", "dispositions identity differs from review input")
    if predicate == "implementation-candidate":
        if review_result.get("status") not in {"clean", "advisory"}:
            add("RMAP-REVIEW-P0-P1-OPEN", "review is not non-blocking")
        return findings
    if review_result.get("status") not in {"clean", "advisory"}:
        add("RMAP-REVIEW-P0-P1-OPEN", "implementation acceptance requires a non-blocking final review")
    findings_by_id = {item.get("findingId"): item for item in review_result.get("findings", []) if isinstance(item, dict)}
    disposition_ids = {item.get("findingId") for item in dispositions.get("dispositions", []) if isinstance(item, dict)}
    if findings_by_id and set(findings_by_id) != disposition_ids:
        add("RMAP-REVIEW-P2-DISPOSITION", "finding and disposition sets differ")
    if any(item.get("proposedSeverity") in {"P0", "P1"} and item.get("status") in {"confirmed", "unverified"} for item in findings_by_id.values()):
        add("RMAP-REVIEW-P0-P1-OPEN", "accepted P0/P1 remains open")
    deferrals = {item.get("finding_id") for item in p2_deferrals if isinstance(item, dict)}
    open_p2 = {fid for fid, item in findings_by_id.items() if item.get("proposedSeverity") == "P2" and item.get("status") == "advisory"}
    if open_p2 - deferrals:
        add("RMAP-REVIEW-P2-DISPOSITION", "accepted P2 lacks a current disposition")
    return findings
