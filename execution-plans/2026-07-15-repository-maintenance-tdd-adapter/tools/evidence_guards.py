from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
IDENTITY_FIELDS = {
    "head", "index_tree", "tracked_diff_hash", "untracked_manifest_hash", "contract_hash",
    "command_registry_hash", "validator_hash", "authority_manifest_hash",
    "changed_file_manifest_hash", "test_diff_hash", "red_run_id", "green_run_id",
    "refactor_run_id", "candidate_worktree_hash",
}


def _finding(rule: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule, "target": target, "message": message}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _value_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_candidate_document(
    plan_root: Path,
    candidate_path: str,
    candidate: dict[str, Any],
    current: dict[str, str],
    stage_documents: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required = {"schema_version", "predicate", "status", "plan_hash", "source_hash", "slice_id", "authority_revision", "candidate_identity", "authorizes", "does_not_authorize"}
    if set(candidate) != required or candidate.get("schema_version") != "jimuyun.tdd-result.v1" or candidate.get("predicate") != "implementation-candidate" or candidate.get("status") != "pass" or candidate.get("slice_id") != "RMAP-S6":
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "candidate result shape, predicate, or owner slice is invalid"))
    if candidate.get("authorizes") != ["bootstrap-review"] or set(candidate.get("does_not_authorize", [])) != {"implementation-accepted", "protected-handoff", "release-ready"}:
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "candidate authority set is invalid"))
    if candidate.get("authority_revision") != current.get("head"):
        findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, "candidate authority revision differs from the current Git authority"))
    if candidate.get("plan_hash") != current.get("plan_hash") or candidate.get("source_hash") != current.get("source_hash"):
        findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, "candidate plan or source identity is stale"))
    identity = candidate.get("candidate_identity")
    if not isinstance(identity, dict) or set(identity) != IDENTITY_FIELDS:
        findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, "candidate identity field set is incomplete"))
        return findings
    exact = {"head", "index_tree", "tracked_diff_hash", "untracked_manifest_hash", "contract_hash", "command_registry_hash", "validator_hash", "authority_manifest_hash", "candidate_worktree_hash"}
    for key in exact:
        if identity.get(key) != current.get(key):
            findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, f"candidate {key} differs from current state"))
    repository_root = plan_root.parents[1]
    evidence_dir = (repository_root / candidate_path).resolve().parent
    changed_manifest = evidence_dir / "changed-files.json"
    test_diff = evidence_dir / "test-diff.patch"
    expected_files = {"changed_file_manifest_hash": changed_manifest, "test_diff_hash": test_diff}
    for key, path in expected_files.items():
        if not path.is_file() or identity.get(key) != _sha256(path):
            findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, f"candidate {key} does not bind its run artifact"))
    if changed_manifest.is_file():
        try:
            manifest = json.loads(changed_manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            manifest = None
        files = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(manifest, dict) or manifest.get("schema_version") != "rmap.changed-files.v1" or not isinstance(files, list) or any(not isinstance(item, dict) or set(item) != {"path", "sha256"} or not HASH_RE.fullmatch(str(item.get("sha256"))) for item in files):
            findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, "changed-file manifest shape is invalid"))
    stage_documents = stage_documents or []
    by_stage = {item.get("stage"): item for item in stage_documents if isinstance(item, dict)}
    for stage in ("red", "green", "refactor"):
        key = f"{stage}_run_id"
        if not isinstance(identity.get(key), str) or not identity[key] or identity.get(key) != by_stage.get(stage, {}).get("run_id"):
            findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, f"candidate {key} does not bind supplied stage evidence"))
    return findings


def validate_candidate_review_documents(
    plan_root: Path,
    candidate_path: str,
    candidate: dict[str, Any],
    review_input: dict[str, Any],
    preflight: dict[str, Any],
    review_result: dict[str, Any],
    dispositions: dict[str, Any],
    p2_deferrals: list[dict[str, Any]],
    current: dict[str, str],
    stage_documents: list[dict[str, Any]] | None = None,
    review_dir: Path | None = None,
) -> list[dict[str, str]]:
    findings = validate_candidate_document(plan_root, candidate_path, candidate, current, stage_documents)
    repository_root = plan_root.parents[1]
    path = (repository_root / candidate_path).resolve()
    try:
        relative = path.relative_to(repository_root).as_posix()
    except ValueError:
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "candidate path escapes repository")); relative = ""
    artifacts = {item.get("artifact"): item.get("sha256") for item in review_input.get("artifacts", []) if isinstance(item, dict)}
    actual_hash = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    if not relative.startswith("logs/tdd-adapter/") or artifacts.get(relative) != actual_hash:
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "review input does not hash-bind candidate result"))
    identity_keys = ("reviewId", "routeVersion", "policyRevision", "authorityRevision", "inputHash")
    if candidate.get("authority_revision") != review_input.get("authorityRevision"):
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "candidate authority revision differs from review input"))
    if any(review_result.get(key) != review_input.get(key) for key in identity_keys) or any(preflight.get(key) != review_input.get(key) for key in identity_keys):
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "review or preflight identity differs from review input"))
    if preflight.get("status") != "passed" or any(item.get("status") != "passed" for item in preflight.get("checks", [])):
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "deterministic preflight is not fully passed"))
    required_checks = set(review_input.get("deterministicPreflightPolicy", {}).get("requiredChecks", [])) | {item.get("checkId") for item in review_input.get("planBoundRequiredChecks", []) if isinstance(item, dict)}
    passed_checks = {item.get("checkId") for item in preflight.get("checks", []) if item.get("status") == "passed"}
    if not required_checks or not required_checks.issubset(passed_checks):
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "required check binding is incomplete"))
    if any(dispositions.get(key) != review_input.get(key) for key in identity_keys):
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "dispositions identity differs from review input"))
    profile_path = repository_root / "execution-plans" / "2026-07-12-llm-review-evidence-gate-hardening" / "bootstrap" / "review-profiles.v1.json"
    try:
        profiles = json.loads(profile_path.read_text(encoding="utf-8")).get("profiles", {})
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        profiles = {}
    profile_name = "bootstrap-implementation-conformance"
    profile = profiles.get(profile_name, {}) if isinstance(profiles, dict) else {}
    unhashed = dict(review_input); unhashed.pop("inputHash", None)
    expected_profile_fields = ("reviewProfile", "policyRevision", "routeVersion", "requiredLayers", "codexExecPolicy", "requiredContextClasses", "completenessPolicy")
    if (
        review_input.get("schemaVersion") != "bootstrap-review-input.v1"
        or review_input.get("authorityClass") != "supplemental_bootstrap"
        or review_input.get("profileName") != profile_name
        or review_input.get("authorityRevision") != current.get("head")
        or review_input.get("inputHash") != _value_hash(unhashed)
        or any(review_input.get(field) != profile.get(field) for field in expected_profile_fields)
    ):
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "review input is not a current trusted Bootstrap profile projection"))
    if preflight.get("schemaVersion") != "bootstrap-preflight-result.v1" or review_result.get("schemaVersion") != "review-result.v1" or dispositions.get("schemaVersion") != "bootstrap-review-dispositions.v1" or review_result.get("authorityClass") != "supplemental_bootstrap" or dispositions.get("authorityClass") != "supplemental_bootstrap":
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "Bootstrap result schema or authority class is invalid"))
    if review_result.get("reviewProfile") != review_input.get("reviewProfile") or review_result.get("requiredLayers") != review_input.get("requiredLayers") or review_result.get("completedLayers") != review_input.get("requiredLayers") or review_result.get("failedLayers") != [] or review_result.get("skippedLayers") != []:
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "final review layer closure differs from trusted input"))
    if review_dir is not None:
        for check in preflight.get("checks", []):
            if not isinstance(check, dict) or check.get("exitCode") != 0 or not isinstance(check.get("evidence"), list) or not check.get("evidence"):
                findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "preflight check lacks successful hash-bound evidence")); continue
            for evidence in check["evidence"]:
                if not isinstance(evidence, dict) or set(evidence) != {"path", "sha256"}:
                    findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "preflight evidence shape is invalid")); continue
                evidence_path = (review_dir / evidence["path"]).resolve()
                try:
                    evidence_path.relative_to(review_dir.resolve())
                except (ValueError, TypeError):
                    findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "preflight evidence escapes review run")); continue
                if not evidence_path.is_file() or evidence.get("sha256") != _sha256(evidence_path):
                    findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "preflight evidence is missing or stale"))
    if review_result.get("status") not in {"clean", "advisory"}:
        findings.append(_finding("RMAP-REVIEW-P0-P1-OPEN", candidate_path, "implementation acceptance requires a non-blocking final review"))
    findings_by_id = {item.get("findingId"): item for item in review_result.get("findings", []) if isinstance(item, dict)}
    disposition_ids = {item.get("findingId") for item in dispositions.get("dispositions", []) if isinstance(item, dict)}
    if set(findings_by_id) != disposition_ids:
        findings.append(_finding("RMAP-REVIEW-P2-DISPOSITION", candidate_path, "finding and disposition sets differ"))
    if any(item.get("proposedSeverity") in {"P0", "P1"} and item.get("status") in {"confirmed", "unverified"} for item in findings_by_id.values()):
        findings.append(_finding("RMAP-REVIEW-P0-P1-OPEN", candidate_path, "accepted P0/P1 remains open"))
    dispositions_by_id = {item.get("findingId"): item for item in dispositions.get("dispositions", []) if isinstance(item, dict)}
    if any(set(item) != {"findingId", "status", "reason"} or item.get("status") != findings_by_id.get(fid, {}).get("status") or not isinstance(item.get("reason"), str) or not item.get("reason") for fid, item in dispositions_by_id.items()):
        findings.append(_finding("RMAP-REVIEW-P2-DISPOSITION", candidate_path, "review disposition is incomplete or differs from the final finding"))
    deferrals = {item.get("finding_id") for item in p2_deferrals if isinstance(item, dict)}
    open_p2 = {fid for fid, item in findings_by_id.items() if item.get("proposedSeverity") == "P2" and item.get("status") == "advisory"}
    if open_p2 - deferrals:
        findings.append(_finding("RMAP-REVIEW-P2-DISPOSITION", candidate_path, "accepted P2 lacks a current disposition"))
    return findings
