from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from candidate_diff_guards import validate_candidate_diff, validate_candidate_result_ref
from protocol_guards import load_protocol_run, value_hash


HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
IDENTITY_FIELDS = {
    "head", "index_tree", "tracked_diff_hash", "untracked_manifest_hash", "contract_hash",
    "command_registry_hash", "validator_hash", "authority_manifest_hash",
    "candidate_diff_manifest_hash", "candidate_lineage_manifest_hash", "test_diff_hash", "red_run_id", "green_run_id",
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


def _bootstrap_runtime(repository_root: Path) -> Any:
    path = repository_root / ".agents" / "skills" / "run-phase-bootstrap-review" / "scripts" / "bootstrap_review.py"
    spec = importlib.util.spec_from_file_location("rmap_evidence_bootstrap_review", path)
    if spec is None or spec.loader is None:
        raise ValueError("Bootstrap schema runtime cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_bootstrap_envelope_projection(
    repository_root: Path,
    envelope: dict[str, Any],
    authority_revision: str | None = None,
    review_dir: Path | None = None,
) -> list[dict[str, str]]:
    try:
        runtime = _bootstrap_runtime(repository_root)
        schema_errors = runtime.schema_validation_errors(
            "bootstrap-finalized-run-validation.v1.schema.json", envelope
        )
        if schema_errors:
            raise ValueError("; ".join(schema_errors))
        if review_dir is None:
            if (
                envelope.get("validatorRevision") != runtime.FINALIZED_VALIDATOR_REVISION
                or envelope.get("validatorHash") != _sha256(Path(runtime.__file__).resolve())
            ):
                raise ValueError("finalized validator identity is stale")
        else:
            manifest = runtime.read_json(review_dir / "review-input.json")
            recomputed = runtime.validate_finalized_run_evidence(review_dir, manifest, repository_root)
            saved = {key: value for key, value in envelope.items() if key != "generatedAt"}
            current = {key: value for key, value in recomputed.items() if key != "generatedAt"}
            if saved != current:
                raise ValueError("saved envelope differs from repository producer recomputation")
        if authority_revision is not None and envelope.get("authorityRevision") != authority_revision:
            raise ValueError("authority revision is stale")
        if envelope.get("profileName") != "bootstrap-implementation-conformance":
            raise ValueError("wrong Bootstrap review profile")
        if envelope.get("authorizes") != [] or not {
            "plan-acceptance", "implementation-acceptance", "protected-handoff", "release", "commit", "done"
        }.issubset(set(envelope.get("doesNotAuthorize", []))):
            raise ValueError("invalid authorization boundary")
    except (OSError, UnicodeError, ValueError, KeyError, json.JSONDecodeError, RuntimeError):
        return [_finding("RMAP-REVIEW-ENVELOPE", "finalized-run-validation", "finalized-run envelope fails repository producer recomputation or authority binding")]
    return []


def validate_runtime_disposition_sources(review_dir: Path, envelope: dict[str, Any], findings_by_id: dict[str, dict[str, Any]], disposition_items: list[dict[str, Any]], candidate_path: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    open_p2 = {fid for fid, item in findings_by_id.items() if item.get("proposedSeverity") == "P2" and item.get("status") == "advisory"}
    if open_p2:
        p2_path = review_dir / "p2-dispositions.json"
        metrics_path = review_dir / "review-metrics.json"
        try:
            p2_document = json.loads(p2_path.read_text(encoding="utf-8"))
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            runtime_p2 = {item.get("findingId"): item for item in p2_document.get("dispositions", []) if isinstance(item, dict)}
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            p2_document, metrics, runtime_p2 = {}, {}, {}
        if not p2_path.is_file() or metrics.get("p2DispositionHash") != _sha256(p2_path):
            findings.append(_finding("RMAP-REVIEW-P2-SOURCE", candidate_path, "Bootstrap metrics do not hash-bind runtime P2 dispositions"))
        finalized_p2 = {item.get("findingId") for item in disposition_items if str(item.get("status", "")).startswith("p2_")}
        repository_root = Path(__file__).resolve().parents[3]
        try:
            p2_schema_error = "; ".join(_bootstrap_runtime(repository_root).schema_validation_errors("bootstrap-p2-dispositions.v1.schema.json", p2_document))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            p2_schema_error = "Bootstrap P2 schema unavailable"
        if p2_schema_error or p2_document.get("reviewId") != envelope.get("reviewId") or p2_document.get("inputHash") != envelope.get("inputHash") or set(p2_document.get("findingIds", [])) != finalized_p2 or set(runtime_p2) != finalized_p2:
            findings.append(_finding("RMAP-REVIEW-P2-SOURCE", candidate_path, "runtime P2 source identity differs from finalized finding closure"))
        for finding_id in open_p2:
            disposition = runtime_p2.get(finding_id, {})
            required = all(disposition.get(key) for key in ("owner", "expiry", "closureCommandId", "reason", "recheckTrigger"))
            try:
                expiry = datetime.fromisoformat(str(disposition.get("expiry", "")).replace("Z", "+00:00"))
            except ValueError:
                expiry = datetime.min.replace(tzinfo=timezone.utc)
            if disposition.get("status") != "deferred" or disposition.get("risk") == "high" or not required or expiry <= datetime.now(timezone.utc):
                findings.append(_finding("RMAP-REVIEW-P2-DISPOSITION", candidate_path, f"runtime P2 disposition is incomplete for {finding_id}"))
    if any(item.get("proposedSeverity") in {"P0", "P1"} for item in findings_by_id.values()):
        verifier_path = review_dir / "verifier-output.json"
        try:
            verifier = json.loads(verifier_path.read_text(encoding="utf-8"))
            verifier_error = "; ".join(_bootstrap_runtime(Path(__file__).resolve().parents[3]).schema_validation_errors("bootstrap-verifier-output.v1.schema.json", verifier))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            verifier_error = "verifier evidence unavailable"
        blocking_ids = {item.get("findingId") for item in findings_by_id.values() if item.get("proposedSeverity") in {"P0", "P1"}}
        decision_ids = {item.get("findingId") for item in verifier.get("decisions", [])} if isinstance(locals().get("verifier"), dict) else set()
        if verifier_error or decision_ids != blocking_ids or envelope.get("artifactHashes", {}).get("verifierOutput") != _sha256(verifier_path):
            findings.append(_finding("RMAP-REVIEW-VERIFIER-SOURCE", candidate_path, "blocking findings require schema-valid hash-bound verifier decisions"))
    return findings


def validate_candidate_document(
    plan_root: Path,
    candidate_path: str,
    candidate: dict[str, Any],
    current: dict[str, str],
    stage_documents: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required = {"schema_version", "predicate", "status", "plan_hash", "source_hash", "slice_id", "run_id", "authority_revision", "candidate_identity", "authorizes", "does_not_authorize"}
    if set(candidate) != required or candidate.get("schema_version") != "jimuyun.tdd-result.v1" or candidate.get("predicate") != "implementation-candidate" or candidate.get("status") != "pass" or candidate.get("slice_id") != "RMAP-S6" or not isinstance(candidate.get("run_id"), str) or not candidate.get("run_id"):
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "candidate result shape, predicate, or owner slice is invalid"))
    if candidate.get("authorizes") != [] or set(candidate.get("does_not_authorize", [])) != {"implementation-authorized", "implementation-complete", "acceptance-passed", "archived"}:
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
    lineage_manifest = evidence_dir / "candidate-lineage-manifest.json"
    test_diff = evidence_dir / "test-diff.patch"
    expected_files = {"candidate_diff_manifest_hash": changed_manifest, "candidate_lineage_manifest_hash": lineage_manifest, "test_diff_hash": test_diff}
    for key, path in expected_files.items():
        if not path.is_file() or identity.get(key) != _sha256(path):
            findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, f"candidate {key} does not bind its run artifact"))
    if stage_documents is None:
        stage_documents = []
        for stage in ("red", "green", "refactor"):
            try:
                stage_documents.append(json.loads((evidence_dir / f"{stage}-result.json").read_text(encoding="utf-8")))
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
                pass
    by_stage = {item.get("stage"): item for item in stage_documents if isinstance(item, dict)}
    for stage in ("red", "green", "refactor"):
        key = f"{stage}_run_id"
        if not isinstance(identity.get(key), str) or not identity[key] or identity.get(key) != by_stage.get(stage, {}).get("run_id"):
            findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", candidate_path, f"candidate {key} does not bind supplied stage evidence"))
    bundle, protocol_findings = load_protocol_run(plan_root, evidence_dir)
    findings.extend(protocol_findings)
    try:
        manifest = json.loads(changed_manifest.read_text(encoding="utf-8"))
        lineage = json.loads(lineage_manifest.read_text(encoding="utf-8"))
        contract = json.loads((plan_root / "implementation-contract.v1.json").read_text(encoding="utf-8"))
        findings.extend(validate_candidate_diff(
            plan_root,
            repository_root,
            contract,
            manifest,
            changed_manifest.relative_to(repository_root).as_posix(),
            test_diff.read_bytes(),
            lineage,
            current,
            str(candidate.get("run_id")),
        ))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        findings.append(_finding("RMAP-CANDIDATE-DIFF-EXACT", candidate_path, str(exc)))
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
    current: dict[str, str],
    stage_documents: list[dict[str, Any]] | None = None,
    review_dir: Path | None = None,
    candidate_ref: dict[str, Any] | None = None,
    candidate_ref_path: str | None = None,
) -> list[dict[str, str]]:
    findings = validate_candidate_document(plan_root, candidate_path, candidate, current, None)
    repository_root = plan_root.parents[1]
    findings.extend(validate_bootstrap_envelope_projection(repository_root, envelope, current.get("head"), review_dir))
    path = (repository_root / candidate_path).resolve()
    try:
        relative = path.relative_to(repository_root).as_posix()
    except ValueError:
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "candidate path escapes repository")); relative = ""
    artifacts = {item.get("artifact"): item.get("sha256") for item in review_input.get("artifacts", []) if isinstance(item, dict)}
    actual_hash = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    if not relative.startswith("logs/tdd-adapter/") or artifacts.get(relative) != actual_hash:
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "review input does not hash-bind candidate result"))
    if candidate_ref is None or candidate_ref_path is None or not path.is_file():
        findings.append(_finding("RMAP-CANDIDATE-REF", candidate_path, "S7 requires an explicit S6 candidate result reference"))
    else:
        findings.extend(validate_candidate_result_ref(
            plan_root,
            candidate_ref,
            candidate_ref_path,
            candidate_path,
            path.read_bytes(),
            candidate,
            repository_root,
        ))
    profile_name = "bootstrap-implementation-conformance"
    if (
        envelope.get("validationStatus") != "passed"
        or envelope.get("profileName") != profile_name
        or envelope.get("authorizes") != []
        or not {"plan-acceptance", "implementation-acceptance", "protected-handoff", "release", "commit", "done"}.issubset(set(envelope.get("doesNotAuthorize", [])))
    ):
        findings.append(_finding("RMAP-REVIEW-ENVELOPE", candidate_path, "finalized-run envelope is stale, partial, or authoritative"))
    if candidate.get("authority_revision") != envelope.get("authorityRevision"):
        findings.append(_finding("RMAP-REVIEW-EVIDENCE-BINDING", candidate_path, "candidate authority revision differs from finalized review authority"))
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
    if review_dir is not None:
        findings.extend(validate_runtime_disposition_sources(review_dir, envelope, findings_by_id, disposition_items, candidate_path))
    return findings
