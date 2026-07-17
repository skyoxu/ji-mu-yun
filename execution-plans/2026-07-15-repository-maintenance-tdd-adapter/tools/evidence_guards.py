from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from protocol_guards import load_protocol_run, value_hash


HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
IDENTITY_FIELDS = {
    "head", "index_tree", "tracked_diff_hash", "untracked_manifest_hash", "contract_hash",
    "command_registry_hash", "validator_hash", "authority_manifest_hash",
    "changed_file_manifest_hash", "test_diff_hash", "red_run_id", "green_run_id",
    "refactor_run_id", "candidate_worktree_hash", "final_context_manifest_hash",
    "final_capsule_hash", "attempt_ledger_manifest_hash", "run_events_hash",
    "final_attempt_event_hash", "accepted_attempt_id", "accepted_attempt_decision_hash",
}


def _finding(rule: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule, "target": target, "message": message}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _value_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_bootstrap_envelope_projection(
    repository_root: Path,
    envelope: dict[str, Any],
    authority_revision: str | None = None,
) -> list[dict[str, str]]:
    profile_path = repository_root / ".agents" / "skills" / "run-phase-bootstrap-review" / "references" / "review-profiles.v1.json"
    validator_path = repository_root / ".agents" / "skills" / "run-phase-bootstrap-review" / "scripts" / "bootstrap_review.py"
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))["profiles"]["bootstrap-implementation-conformance"]
    except (OSError, UnicodeError, ValueError, KeyError, json.JSONDecodeError):
        profile = {}
    required = {
        "schemaVersion", "validationStatus", "reviewId", "changeId", "fullReviewRound",
        "profileName", "reviewProfile", "routeVersion", "controlPlaneRevision", "policyRevision",
        "profileHash", "authorityRevision", "inputHash", "authorityContextHash", "artifactHashes",
        "finalStatus", "findingClosure", "validatorRevision", "validatorHash", "authorizes",
        "doesNotAuthorize", "generatedAt",
    }
    invalid = (
        set(envelope) != required
        or envelope.get("schemaVersion") != "bootstrap-finalized-run-validation.v1"
        or envelope.get("validationStatus") != "passed"
        or envelope.get("profileName") != "bootstrap-implementation-conformance"
        or envelope.get("profileHash") != _value_hash(profile)
        or envelope.get("reviewProfile") != profile.get("reviewProfile")
        or envelope.get("routeVersion") != profile.get("routeVersion")
        or envelope.get("controlPlaneRevision") != profile.get("controlPlaneRevision")
        or envelope.get("policyRevision") != profile.get("policyRevision")
        or (authority_revision is not None and envelope.get("authorityRevision") != authority_revision)
        or envelope.get("validatorRevision") != "bootstrap-finalized-run-validator.v1"
        or not validator_path.is_file()
        or envelope.get("validatorHash") != _sha256(validator_path)
        or envelope.get("authorizes") != []
        or not {"plan-acceptance", "implementation-acceptance", "protected-handoff", "release", "commit", "done"}.issubset(set(envelope.get("doesNotAuthorize", [])))
    )
    return [_finding("RMAP-REVIEW-ENVELOPE", "finalized-run-validation", "finalized-run envelope profile, validator, or authority boundary is stale")] if invalid else []


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
    bundle, protocol_findings = load_protocol_run(plan_root, evidence_dir)
    findings.extend(protocol_findings)
    accepted_id = identity.get("accepted_attempt_id")
    attempt = next((item for item in bundle.get("attempts", []) if item.get("adapter_decision", {}).get("attempt_id") == accepted_id), None)
    contexts = bundle.get("contexts", [])
    final_context = contexts[-1] if contexts else None
    context_path = evidence_dir / "context" / str(final_context.get("context_manifest", {}).get("capsule_id")) / "context-manifest.v1.json" if final_context else None
    capsule_path = evidence_dir / "context" / str(final_context.get("slice_capsule", {}).get("capsule_id")) / "slice-capsule.v1.json" if final_context else None
    decision_path = evidence_dir / "attempts" / str(accepted_id) / "adapter-decision.v1.json"
    ledger_path = evidence_dir / "attempt-ledger-manifest.v1.json"
    events_path = evidence_dir / "run-events.jsonl"
    if context_path is None or capsule_path is None or not context_path.is_file() or not capsule_path.is_file() or identity.get("final_context_manifest_hash") != _sha256(context_path) or identity.get("final_capsule_hash") != _sha256(capsule_path):
        findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, "candidate does not bind the final persisted context capsule"))
    if attempt is None or attempt.get("adapter_decision", {}).get("stage") != "refactor" or attempt.get("adapter_decision", {}).get("decision") != "accepted_for_validation" or not decision_path.is_file() or identity.get("accepted_attempt_decision_hash") != _sha256(decision_path):
        findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, "candidate does not bind the accepted refactor attempt decision"))
    elif final_context and attempt["backend_request"].get("capsule_ref", {}).get("sha256") != value_hash(final_context["slice_capsule"]):
        findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, "accepted attempt is not bound to the final capsule"))
    events = bundle.get("events", [])
    if (
        not ledger_path.is_file()
        or not events_path.is_file()
        or identity.get("attempt_ledger_manifest_hash") != _sha256(ledger_path)
        or identity.get("run_events_hash") != _sha256(events_path)
        or not events
        or identity.get("final_attempt_event_hash") != value_hash(events[-1])
    ):
        findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, "candidate does not bind the attempt ledger manifest, raw event log, and final canonical event"))
    return findings


def validate_candidate_review_documents(
    plan_root: Path,
    candidate_path: str,
    candidate: dict[str, Any],
    envelope: dict[str, Any],
    review_input: dict[str, Any],
    review_result: dict[str, Any],
    dispositions: dict[str, Any],
    p2_deferrals: list[dict[str, Any]],
    current: dict[str, str],
    stage_documents: list[dict[str, Any]] | None = None,
    review_dir: Path | None = None,
) -> list[dict[str, str]]:
    findings = validate_candidate_document(plan_root, candidate_path, candidate, current, stage_documents)
    repository_root = plan_root.parents[1]
    findings.extend(validate_bootstrap_envelope_projection(repository_root, envelope, current.get("head")))
    path = (repository_root / candidate_path).resolve()
    try:
        relative = path.relative_to(repository_root).as_posix()
    except ValueError:
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "candidate path escapes repository")); relative = ""
    artifacts = {item.get("artifact"): item.get("sha256") for item in review_input.get("artifacts", []) if isinstance(item, dict)}
    actual_hash = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    if not relative.startswith("logs/tdd-adapter/") or artifacts.get(relative) != actual_hash:
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "review input does not hash-bind candidate result"))
    profile_path = repository_root / ".agents" / "skills" / "run-phase-bootstrap-review" / "references" / "review-profiles.v1.json"
    validator_path = repository_root / ".agents" / "skills" / "run-phase-bootstrap-review" / "scripts" / "bootstrap_review.py"
    try:
        profiles = json.loads(profile_path.read_text(encoding="utf-8")).get("profiles", {})
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        profiles = {}
    profile_name = "bootstrap-implementation-conformance"
    profile = profiles.get(profile_name, {}) if isinstance(profiles, dict) else {}
    required_envelope_fields = {
        "schemaVersion", "validationStatus", "reviewId", "changeId", "fullReviewRound",
        "profileName", "reviewProfile", "routeVersion", "controlPlaneRevision",
        "policyRevision", "profileHash", "authorityRevision", "inputHash",
        "authorityContextHash", "artifactHashes", "finalStatus", "findingClosure",
        "validatorRevision", "validatorHash", "authorizes", "doesNotAuthorize", "generatedAt",
    }
    if (
        set(envelope) != required_envelope_fields
        or envelope.get("schemaVersion") != "bootstrap-finalized-run-validation.v1"
        or envelope.get("validationStatus") != "passed"
        or envelope.get("profileName") != profile_name
        or envelope.get("profileHash") != _value_hash(profile)
        or envelope.get("reviewProfile") != profile.get("reviewProfile")
        or envelope.get("routeVersion") != profile.get("routeVersion")
        or envelope.get("controlPlaneRevision") != profile.get("controlPlaneRevision")
        or envelope.get("policyRevision") != profile.get("policyRevision")
        or envelope.get("authorityRevision") != current.get("head")
        or envelope.get("validatorRevision") != "bootstrap-finalized-run-validator.v1"
        or not validator_path.is_file()
        or envelope.get("validatorHash") != _sha256(validator_path)
        or envelope.get("authorizes") != []
        or not {"plan-acceptance", "implementation-acceptance", "protected-handoff", "release", "commit", "done"}.issubset(set(envelope.get("doesNotAuthorize", [])))
    ):
        findings.append(_finding("RMAP-REVIEW-ENVELOPE", candidate_path, "finalized-run envelope is stale, partial, or authoritative"))
    if candidate.get("authority_revision") != envelope.get("authorityRevision"):
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "candidate authority revision differs from finalized review authority"))
    if review_dir is None:
        findings.append(_finding("RMAP-REVIEW-ENVELOPE", candidate_path, "Bootstrap run directory is required"))
    else:
        paths = {
            "reviewInput": review_dir / "review-input.json",
            "preflightResult": review_dir / "preflight-result.json",
            "gateState": review_dir / "review-gate-state.json",
            "candidates": review_dir / "review-candidates.json",
            "rejections": review_dir / "review-rejections.json",
            "finalResult": review_dir / "review-gate-result.json",
            "dispositions": review_dir / "review-dispositions.json",
            "metrics": review_dir / "review-metrics.json",
        }
        hashes = envelope.get("artifactHashes", {})
        if set(hashes) != set(paths) or any(not target.is_file() or hashes.get(name) != _sha256(target) for name, target in paths.items()):
            findings.append(_finding("RMAP-REVIEW-ENVELOPE", candidate_path, "finalized-run envelope does not bind current Bootstrap artifact bytes"))
    unhashed = dict(review_input); unhashed.pop("inputHash", None)
    if (
        review_input.get("profileName") != profile_name
        or review_input.get("inputHash") != _value_hash(unhashed)
        or review_input.get("inputHash") != envelope.get("inputHash")
        or review_input.get("authorityContextHash") != envelope.get("authorityContextHash")
    ):
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "review input identity differs from finalized envelope"))
    if (
        review_result.get("schemaVersion") != "review-result.v1"
        or dispositions.get("schemaVersion") != "bootstrap-review-dispositions.v1"
        or review_result.get("status") != envelope.get("finalStatus")
    ):
        findings.append(_finding("RMAP-REVIEW-ENVELOPE", candidate_path, "final result or dispositions differ from finalized envelope"))
    if envelope.get("finalStatus") not in {"clean", "advisory"}:
        findings.append(_finding("RMAP-REVIEW-P0-P1-OPEN", candidate_path, "implementation acceptance requires a non-blocking final review"))
    findings_by_id = {item.get("findingId"): item for item in review_result.get("findings", []) if isinstance(item, dict)}
    disposition_items = [item for item in dispositions.get("dispositions", []) if isinstance(item, dict)]
    disposition_ids = {item.get("findingId") for item in disposition_items}
    closure = envelope.get("findingClosure", {})
    if (
        closure.get("candidateCount") != len(disposition_items)
        or closure.get("visibleFindingCount") != len(findings_by_id)
        or len(disposition_ids) != len(disposition_items)
        or not set(findings_by_id).issubset(disposition_ids)
    ):
        findings.append(_finding("RMAP-REVIEW-P2-DISPOSITION", candidate_path, "finding closure differs from finalized disposition set"))
    if any(item.get("proposedSeverity") in {"P0", "P1"} and item.get("status") in {"confirmed", "unverified"} for item in findings_by_id.values()):
        findings.append(_finding("RMAP-REVIEW-P0-P1-OPEN", candidate_path, "accepted P0/P1 remains open"))
    deferrals = {item.get("finding_id") for item in p2_deferrals if isinstance(item, dict)}
    open_p2 = {fid for fid, item in findings_by_id.items() if item.get("proposedSeverity") == "P2" and item.get("status") == "advisory"}
    if open_p2 - deferrals:
        findings.append(_finding("RMAP-REVIEW-P2-DISPOSITION", candidate_path, "accepted P2 lacks a current disposition"))
    return findings
