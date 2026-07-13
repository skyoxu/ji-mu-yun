#!/usr/bin/env python3
"""Prepare and validate manual, plan-local bootstrap reviews."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import importlib.util
from pathlib import Path
from typing import Any


PLAN_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = PLAN_ROOT / "bootstrap" / "review-profiles.v1.json"
PLAN_VALIDATOR_PATH = PLAN_ROOT / "tools" / "validate_whole_directory.py"
LAYERS = ("blind_hunter", "edge_case_hunter", "acceptance_auditor")
HASH_PREFIX = "sha256:"
AUTHORITY_CLASS = "supplemental_bootstrap"
REVIEW_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{2,63}")


class BootstrapError(Exception):
    """A deterministic operator or validation error."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def value_hash(value: Any) -> str:
    return HASH_PREFIX + hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_hash(path: Path) -> str:
    return HASH_PREFIX + hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"Cannot read valid UTF-8 JSON from {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def ensure_within(path: Path, parent: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as exc:
        raise BootstrapError(f"{label} is outside repository root: {path}") from exc
    return resolved


def git_revision(repository_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    revision = result.stdout.strip()
    if result.returncode or not revision:
        raise BootstrapError("Repository root must have a readable Git HEAD")
    return revision


def git_worktree_dirty(repository_root: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise BootstrapError("Repository root must have a readable Git worktree status")
    return bool(result.stdout.strip())


def load_schema_runtime() -> Any:
    spec = importlib.util.spec_from_file_location("bootstrap_plan_validator", PLAN_VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise BootstrapError("Cannot load the plan-local JSON Schema runtime")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def schema_registry() -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for path in (PLAN_ROOT / "schemas").glob("*.schema.json"):
        value = read_json(path)
        if not isinstance(value, dict):
            raise BootstrapError(f"Schema must be a JSON object: {path.name}")
        registry[path.name] = value
    return registry


def schema_validation_errors(schema_name: str, instance: Any) -> list[str]:
    registry = schema_registry()
    schema = registry.get(schema_name)
    if schema is None:
        raise BootstrapError(f"Missing plan-local schema: {schema_name}")
    runtime = load_schema_runtime()
    return runtime.schema_errors(schema, instance, registry)


def load_profile(name: str) -> dict[str, Any]:
    registry = read_json(PROFILE_PATH)
    profile = registry.get("profiles", {}).get(name) if isinstance(registry, dict) else None
    if not isinstance(profile, dict):
        raise BootstrapError(f"Unknown bootstrap review profile: {name}")
    if profile.get("automaticInvocation") is not False or profile.get("readOnly") is not True:
        raise BootstrapError("Bootstrap profile must be read-only and prohibit automatic invocation")
    if profile.get("requiredLayers") != list(LAYERS):
        raise BootstrapError("Bootstrap profile must require all three reviewer layers")
    revision_payload = {key: value for key, value in profile.items() if key != "policyRevision"}
    if profile.get("policyRevision") != value_hash(revision_payload):
        raise BootstrapError("Bootstrap profile policyRevision does not match its canonical content")
    return profile


def collect_scope(repository_root: Path, scopes: list[str], out_dir: Path) -> tuple[list[str], list[dict[str, Any]]]:
    if not scopes:
        raise BootstrapError("At least one --scope is required")
    resolved_scopes: list[Path] = []
    for raw in scopes:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = repository_root / candidate
        candidate = ensure_within(candidate, repository_root, "Scope")
        if not candidate.exists():
            raise BootstrapError(f"Scope does not exist: {candidate}")
        resolved_scopes.append(candidate)
    for scope in resolved_scopes:
        if out_dir == scope or scope in out_dir.parents:
            raise BootstrapError("Output directory must not be inside a reviewed scope")

    files: dict[str, Path] = {}
    for scope in resolved_scopes:
        candidates = [scope] if scope.is_file() else sorted(path for path in scope.rglob("*") if path.is_file())
        for path in candidates:
            resolved = ensure_within(path, repository_root, "Scoped file")
            relative = resolved.relative_to(repository_root).as_posix()
            files[relative] = resolved
    if not files:
        raise BootstrapError("Reviewed scope contains no files")
    scope_names = sorted({path.relative_to(repository_root).as_posix() for path in resolved_scopes})
    artifacts = []
    for relative, path in sorted(files.items()):
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        artifacts.append(
            {
                "artifact": relative,
                "sha256": HASH_PREFIX + hashlib.sha256(raw).hexdigest(),
                "sizeBytes": len(raw),
                "textEncoding": "utf-8" if text is not None else None,
                "lineCount": len(text.splitlines()) if text is not None else None,
            }
        )
    return scope_names, artifacts


def prompt_text(layer: str, manifest: dict[str, Any]) -> str:
    return f"""# Isolated Bootstrap Review: {layer}

Review ID: `{manifest['reviewId']}`
Route: `{manifest['routeVersion']}`
Authority revision: `{manifest['authorityRevision']}`
Input hash: `{manifest['inputHash']}`

This is a manual, read-only review. Do not modify the reviewed scope or invoke another reviewer.
Read `review-input.json`, inspect only its hash-bound artifacts, and fill
`reviewer-outputs/{layer}.json`. Keep every binding field unchanged.

Zero candidates are valid. Set `status` to `completed` only after the layer is actually reviewed.
Keep `coverage.requiredArtifacts` unchanged. Move an artifact from `missingArtifacts` to
`readArtifacts` only after reading it. `completed` requires every required artifact to be read and
no missing artifact. If required role context is absent from the manifest, set `status` to `failed`,
write a concrete `failureReason`, keep candidates empty, and never read outside the manifest.
There is no minimum finding quota. A fixed-count instruction is nonbinding first-pass exploration
only; never save a candidate merely to satisfy a requested count.
Every candidate must cite the current repository-relative artifact, its manifest `artifactHash`,
an exact inclusive line range and exact text, a concrete trigger/state/bad-outcome tuple, context
read, existing guard analysis, severity rationale, confidence >= 0.8, and authority/consumer/validator.
Each candidate object must contain exactly these fields:
`candidateId`, `artifactKind`, `artifact`, `artifactHash`, `startLine`, `endLine`, `exactEvidence`,
`triggerInput`, `requiredState`, `badOutcome`, `contextRead`, `existingGuardAnalysis`,
`proposedSeverity`, `severityRationale`, `confidence`, `dimension`, `authorityOwner`, `consumer`,
and `validatorRef`.

Use a stable uppercase `candidateId` matching `[A-Z][A-Z0-9-]{{4,63}}`. `artifactKind` must be one
of `code|document|plan|schema|fixture`; `proposedSeverity` must be `P0|P1|P2`; and `dimension` must
be one of `code|document|plan|security|acceptance|edge-case`. Set `startLine` and `endLine` to
inclusive positive integers and copy those lines verbatim into `exactEvidence`. Set `contextRead`
to a non-empty array of manifest artifact references using `path`, `path:line`, or
`path:start-end`. Do not add any other candidate fields.
Do not write verifier decisions or gateway-owned dispositions.
"""


def reviewer_template(layer: str, manifest: dict[str, Any]) -> dict[str, Any]:
    required_artifacts = [item["artifact"] for item in manifest["artifacts"]]
    return {
        "schemaVersion": "bootstrap-reviewer-output.v1",
        "reviewId": manifest["reviewId"],
        "reviewerLayer": layer,
        "routeVersion": manifest["routeVersion"],
        "authorityRevision": manifest["authorityRevision"],
        "inputHash": manifest["inputHash"],
        "status": "pending",
        "coverage": {
            "requiredArtifacts": required_artifacts,
            "readArtifacts": [],
            "missingArtifacts": required_artifacts,
        },
        "candidates": [],
    }


def command_prepare(args: argparse.Namespace) -> int:
    repository_root = Path(args.repository_root).resolve()
    if not repository_root.is_dir():
        raise BootstrapError(f"Repository root does not exist: {repository_root}")
    out_dir_candidate = Path(args.out_dir)
    if not out_dir_candidate.is_absolute():
        out_dir_candidate = repository_root / out_dir_candidate
    out_dir = ensure_within(out_dir_candidate, repository_root, "Output directory")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise BootstrapError("Output directory must be absent or empty")
    if REVIEW_ID_PATTERN.fullmatch(args.review_id) is None:
        raise BootstrapError("Review ID must be 3-64 lowercase letters, digits, dot, underscore, or hyphen")
    profile = load_profile(args.profile)
    scopes, artifacts = collect_scope(repository_root, args.scope, out_dir)
    manifest = {
        "schemaVersion": "bootstrap-review-input.v1",
        "reviewId": args.review_id,
        "repositoryRoot": str(repository_root),
        "reviewProfile": profile["reviewProfile"],
        "profileName": args.profile,
        "policyRevision": profile["policyRevision"],
        "routeVersion": profile["routeVersion"],
        "requiredLayers": profile["requiredLayers"],
        "scope": scopes,
        "authorityRevision": git_revision(repository_root),
        "worktreeDirty": git_worktree_dirty(repository_root),
        "authorityClass": AUTHORITY_CLASS,
        "artifacts": artifacts,
    }
    manifest["inputHash"] = value_hash(manifest)
    write_json(out_dir / "review-input.json", manifest)
    for layer in LAYERS:
        write_text(out_dir / "reviewer-prompts" / f"{layer}.md", prompt_text(layer, manifest))
        write_json(out_dir / "reviewer-outputs" / f"{layer}.json", reviewer_template(layer, manifest))
    print(f"Prepared manual bootstrap review at {out_dir}")
    return 0


def load_run(run_dir_arg: str) -> tuple[Path, dict[str, Any], Path]:
    run_dir = Path(run_dir_arg).resolve()
    manifest = read_json(run_dir / "review-input.json")
    repository_root = Path(manifest.get("repositoryRoot", "")).resolve()
    ensure_within(run_dir, repository_root, "Run directory")
    expected_hash = manifest.get("inputHash")
    unhashed = dict(manifest)
    unhashed.pop("inputHash", None)
    if expected_hash != value_hash(unhashed):
        raise BootstrapError("review-input.json inputHash does not match its content")
    profile = load_profile(manifest.get("profileName", ""))
    for field in ("reviewProfile", "policyRevision", "routeVersion", "requiredLayers"):
        if manifest.get(field) != profile.get(field):
            raise BootstrapError(f"review-input.json has stale or substituted {field}")
    if manifest.get("authorityClass") != AUTHORITY_CLASS:
        raise BootstrapError("review-input.json has an invalid bootstrap authority class")
    if git_revision(repository_root) != manifest.get("authorityRevision"):
        raise BootstrapError("Git authority revision changed after prepare")
    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict) or not isinstance(artifact.get("artifact"), str):
            raise BootstrapError("review-input.json contains an invalid artifact entry")
        path = ensure_within(repository_root / artifact["artifact"], repository_root, "Input artifact")
        if not path.is_file() or file_hash(path) != artifact.get("sha256"):
            raise BootstrapError(f"Prepared input artifact is stale: {artifact['artifact']}")
    return run_dir, manifest, repository_root


def validate_binding(output: Any, manifest: dict[str, Any], layer: str) -> list[str]:
    if not isinstance(output, dict):
        return ["schema_invalid: reviewer output must be an object"]
    errors = [f"schema_invalid: {error}" for error in schema_validation_errors(
        "bootstrap-reviewer-output.v1.schema.json", output
    )]
    expected = {
        "schemaVersion": "bootstrap-reviewer-output.v1",
        "reviewId": manifest["reviewId"],
        "reviewerLayer": layer,
        "routeVersion": manifest["routeVersion"],
        "authorityRevision": manifest["authorityRevision"],
        "inputHash": manifest["inputHash"],
    }
    errors.extend(f"schema_invalid: {key} binding mismatch" for key, value in expected.items() if output.get(key) != value)
    allowed = set(expected) | {"status", "failureReason", "coverage", "candidates"}
    if set(output) - allowed:
        errors.append("schema_invalid: unexpected reviewer output fields")
    if output.get("status") not in {"pending", "completed", "failed"}:
        errors.append("schema_invalid: status must be pending, completed or failed")
    if not isinstance(output.get("candidates"), list):
        errors.append("schema_invalid: candidates must be an array")
    if output.get("status") == "failed" and not str(output.get("failureReason", "")).strip():
        errors.append("schema_invalid: failed layer requires failureReason")
    if output.get("status") == "completed" and "failureReason" in output:
        errors.append("schema_invalid: completed layer cannot contain failureReason")
    coverage = output.get("coverage")
    expected_artifacts = [item["artifact"] for item in manifest["artifacts"]]
    if isinstance(coverage, dict):
        required_artifacts = coverage.get("requiredArtifacts")
        read_artifacts = coverage.get("readArtifacts")
        missing_artifacts = coverage.get("missingArtifacts")
        if required_artifacts != expected_artifacts:
            errors.append("coverage_invalid: requiredArtifacts must match the prepared manifest")
        if isinstance(read_artifacts, list) and isinstance(missing_artifacts, list):
            read_set = set(read_artifacts)
            missing_set = set(missing_artifacts)
            expected_set = set(expected_artifacts)
            if read_set & missing_set or read_set | missing_set != expected_set:
                errors.append("coverage_invalid: readArtifacts and missingArtifacts must partition requiredArtifacts")
            if output.get("status") == "pending" and (read_artifacts or missing_artifacts != expected_artifacts):
                errors.append("coverage_invalid: pending coverage must leave every artifact missing")
            if output.get("status") == "completed" and (read_artifacts != expected_artifacts or missing_artifacts):
                errors.append("coverage_invalid: completed coverage requires every artifact to be read")
    return errors


def validate_scope_references(
    references: Any,
    manifest: dict[str, Any],
    label: str,
) -> tuple[str | None, str]:
    if not isinstance(references, list) or not references or any(
        not isinstance(item, str) or not item.strip() for item in references
    ):
        return "missing_context", f"{label} must contain inspected context"
    artifact_map = {item["artifact"]: item for item in manifest["artifacts"]}
    for reference in references:
        match = re.fullmatch(r"(.+?)(?::([1-9][0-9]*)(?:-([1-9][0-9]*))?)?", reference.strip())
        if match is None:
            return "missing_context", f"{label} contains an invalid reference: {reference}"
        artifact, start_raw, end_raw = match.groups()
        prepared = artifact_map.get(artifact)
        if prepared is None:
            return "missing_context", f"{label} references an artifact outside prepared scope: {artifact}"
        if start_raw is None:
            continue
        line_count = prepared.get("lineCount")
        start = int(start_raw)
        end = int(end_raw or start_raw)
        if not isinstance(line_count, int) or end < start or end > line_count:
            return "missing_context", f"{label} references an invalid text line range: {reference}"
    return None, ""


def candidate_reason(candidate: Any, manifest: dict[str, Any], repository_root: Path) -> tuple[str | None, str]:
    if not isinstance(candidate, dict):
        return "schema_invalid", "Candidate must be an object"
    required = {
        "candidateId", "artifactKind", "artifact", "artifactHash", "startLine", "endLine", "exactEvidence",
        "triggerInput", "requiredState", "badOutcome", "contextRead", "existingGuardAnalysis", "proposedSeverity",
        "severityRationale", "confidence", "dimension", "authorityOwner", "consumer", "validatorRef",
    }
    if set(candidate) != required:
        return "schema_invalid", "Candidate fields do not match bootstrap-reviewer-output.v1"
    candidate_id = candidate.get("candidateId")
    if not isinstance(candidate_id, str) or re.fullmatch(r"[A-Z][A-Z0-9-]{4,63}", candidate_id) is None:
        return "schema_invalid", "candidateId is invalid"
    artifact = candidate.get("artifact")
    artifact_map = {item["artifact"]: item for item in manifest["artifacts"]}
    if not isinstance(artifact, str) or artifact not in artifact_map:
        return "missing_location", "Artifact is not part of the prepared scope"
    if candidate.get("artifactHash") != artifact_map[artifact]["sha256"]:
        return "stale_evidence", "Candidate artifactHash does not match prepared input"
    path = ensure_within(repository_root / artifact, repository_root, "Candidate artifact")
    if not path.is_file() or file_hash(path) != artifact_map[artifact]["sha256"]:
        return "stale_evidence", "Current artifact hash differs from prepared input"
    if artifact_map[artifact].get("textEncoding") != "utf-8":
        return "missing_location", "Candidate evidence must reference a UTF-8 text artifact"
    start, end = candidate.get("startLine"), candidate.get("endLine")
    if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool) or start < 1 or end < start:
        return "missing_location", "Line range is invalid"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeError:
        return "stale_evidence", "Artifact is not UTF-8 text"
    if end > len(lines) or candidate.get("exactEvidence") != "\n".join(lines[start - 1:end]):
        return "stale_evidence", "Exact evidence does not match the current inclusive line range"
    text_fields = ("triggerInput", "requiredState", "badOutcome")
    if any(not isinstance(candidate.get(key), str) or not candidate[key].strip() for key in text_fields):
        return "missing_failure_tuple", "Trigger, required state and bad outcome are all required"
    context_code, context_reason = validate_scope_references(candidate.get("contextRead"), manifest, "contextRead")
    if context_code:
        return context_code, context_reason
    if not isinstance(candidate.get("existingGuardAnalysis"), str) or not candidate["existingGuardAnalysis"].strip():
        return "missing_guard_analysis", "Existing guard analysis is required"
    confidence = candidate.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or confidence < 0.8 or confidence > 1:
        return "low_confidence", "Confidence must be between 0.8 and 1"
    if candidate.get("proposedSeverity") not in {"P0", "P1", "P2"}:
        return "severity_unsupported", "Only P0, P1 and P2 are supported"
    enums = {
        "artifactKind": {"code", "document", "plan", "schema", "fixture"},
        "dimension": {"code", "document", "plan", "security", "acceptance", "edge-case"},
    }
    if any(candidate.get(key) not in values for key, values in enums.items()):
        return "schema_invalid", "Candidate enum value is invalid"
    for key in ("severityRationale", "authorityOwner", "consumer", "validatorRef"):
        if not isinstance(candidate.get(key), str) or not candidate[key].strip():
            return "schema_invalid", f"{key} is required"
    return None, ""


def raw_candidate_hash(candidate: Any) -> str:
    return value_hash(candidate)


def rejection(candidate: Any, layer: str, manifest: dict[str, Any], code: str, reason: str) -> dict[str, Any]:
    candidate_hash = raw_candidate_hash(candidate)
    candidate_id = candidate.get("candidateId", "unknown") if isinstance(candidate, dict) else "unknown"
    suppression = value_hash(
        [manifest["routeVersion"], candidate_hash, manifest["inputHash"], code, manifest["authorityRevision"]]
    )
    return {
        "schemaVersion": "review-rejection.v1",
        "candidateId": str(candidate_id),
        "reviewerLayer": layer,
        "routeVersion": manifest["routeVersion"],
        "authorityRevision": manifest["authorityRevision"],
        "inputHash": manifest["inputHash"],
        "candidateHash": candidate_hash,
        "suppressionFingerprint": suppression,
        "reasonCode": code,
        "reason": reason,
    }


def finding_from_candidate(candidate: dict[str, Any], layer: str, manifest: dict[str, Any]) -> dict[str, Any]:
    evidence_hash = value_hash(candidate["exactEvidence"])
    fingerprint = value_hash(
        [
            manifest["routeVersion"], candidate["artifact"], evidence_hash, candidate["triggerInput"],
            candidate["requiredState"], candidate["badOutcome"], manifest["authorityRevision"], candidate["dimension"],
        ]
    )
    finding = {key: value for key, value in candidate.items() if key not in {"candidateId", "artifactHash"}}
    finding.update(
        {
            "schemaVersion": "review-finding.v1",
            "findingId": "BSR-" + fingerprint.removeprefix(HASH_PREFIX)[:16].upper(),
            "sourceReviewers": [layer],
            "routeVersion": manifest["routeVersion"],
            "authorityRevision": manifest["authorityRevision"],
            "evidenceFingerprint": fingerprint,
            "status": "candidate",
        }
    )
    return finding


def verifier_prompt(manifest: dict[str, Any], blockers: list[dict[str, Any]]) -> str:
    ids = "\n".join(f"- `{item['findingId']}`: {item['artifact']}:{item['startLine']}" for item in blockers) or "- None"
    return f"""# Manual Independent Blocker Verification

Review ID: `{manifest['reviewId']}`
Input hash: `{manifest['inputHash']}`

Do not discover new findings or modify reviewed files. Independently inspect only the listed P0/P1
candidates, their exact evidence, context and guards. Fill `verifier-output.json` with exactly one
decision for every listed ID and no other IDs. Decisions are `confirmed`, `refuted`, or `unverified`.
For `unverified`, select `security`, `data_loss`, or `other`; the gateway derives the disposition.

Candidates:
{ids}
"""


def verifier_template(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "bootstrap-verifier-output.v1",
        "reviewId": manifest["reviewId"],
        "routeVersion": manifest["routeVersion"],
        "authorityRevision": manifest["authorityRevision"],
        "inputHash": manifest["inputHash"],
        "decisions": [],
    }


def evaluate_reviewer_outputs(
    run_dir: Path,
    manifest: dict[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    completed: list[str] = []
    failed: list[str] = []
    layer_failures: list[dict[str, str]] = []
    rejections: list[dict[str, Any]] = []
    accepted_by_fingerprint: dict[str, dict[str, Any]] = {}
    for layer in manifest["requiredLayers"]:
        path = run_dir / "reviewer-outputs" / f"{layer}.json"
        try:
            output = read_json(path)
        except BootstrapError as exc:
            failed.append(layer)
            layer_failures.append({"reviewerLayer": layer, "reason": str(exc)})
            continue
        binding_errors = validate_binding(output, manifest, layer)
        if binding_errors or output.get("status") != "completed":
            failed.append(layer)
            reason = "; ".join(binding_errors) or str(output.get("failureReason", "Layer did not complete"))
            layer_failures.append({"reviewerLayer": layer, "reason": reason})
            continue
        completed.append(layer)
        for candidate in output["candidates"]:
            code, reason = candidate_reason(candidate, manifest, repository_root)
            if code:
                rejections.append(rejection(candidate, layer, manifest, code, reason))
                continue
            finding = finding_from_candidate(candidate, layer, manifest)
            fingerprint = finding["evidenceFingerprint"]
            if fingerprint in accepted_by_fingerprint:
                current = accepted_by_fingerprint[fingerprint]
                current["sourceReviewers"] = sorted(set(current["sourceReviewers"] + [layer]))
                rejections.append(rejection(candidate, layer, manifest, "duplicate", f"Merged into {current['findingId']}"))
            else:
                accepted_by_fingerprint[fingerprint] = finding
    findings = sorted(accepted_by_fingerprint.values(), key=lambda item: item["findingId"])
    blockers = [item for item in findings if item["proposedSeverity"] in {"P0", "P1"}]
    p2 = [item for item in findings if item["proposedSeverity"] == "P2"]
    if failed:
        status = "incomplete"
    elif blockers:
        status = "awaiting_verification"
    elif p2:
        status = "advisory"
    else:
        status = "clean"
    candidates_doc = {
        "schemaVersion": "bootstrap-review-candidates.v1",
        "authorityClass": AUTHORITY_CLASS,
        "findings": findings,
    }
    rejections_doc = {
        "schemaVersion": "bootstrap-review-rejections.v1",
        "authorityClass": AUTHORITY_CLASS,
        "rejections": rejections,
    }
    gate_state = {
        "schemaVersion": "bootstrap-review-gate-result.v1",
        "authorityClass": AUTHORITY_CLASS,
        "reviewId": manifest["reviewId"],
        "routeVersion": manifest["routeVersion"],
        "reviewProfile": manifest["reviewProfile"],
        "policyRevision": manifest["policyRevision"],
        "authorityRevision": manifest["authorityRevision"],
        "inputHash": manifest["inputHash"],
        "requiredLayers": manifest["requiredLayers"],
        "completedLayers": completed,
        "failedLayers": failed,
        "layerFailures": layer_failures,
        "status": status,
        "candidateCount": len(findings),
        "blockerCandidateCount": len(blockers),
        "rejectionCount": len(rejections),
        "candidatesHash": value_hash(candidates_doc),
        "rejectionsHash": value_hash(rejections_doc),
    }
    return {
        "findings": findings,
        "blockers": blockers,
        "candidatesDoc": candidates_doc,
        "rejectionsDoc": rejections_doc,
        "gateState": gate_state,
    }


def command_gate(args: argparse.Namespace) -> int:
    run_dir, manifest, repository_root = load_run(args.run_dir)
    evaluated = evaluate_reviewer_outputs(run_dir, manifest, repository_root)
    findings = evaluated["findings"]
    blockers = evaluated["blockers"]
    candidates_doc = evaluated["candidatesDoc"]
    rejections_doc = evaluated["rejectionsDoc"]
    gate_state = evaluated["gateState"]
    write_json(run_dir / "review-candidates.json", candidates_doc)
    write_json(run_dir / "review-rejections.json", rejections_doc)
    write_json(run_dir / "review-gate-state.json", gate_state)
    write_json(run_dir / "review-gate-result.json", gate_state)
    write_text(run_dir / "verification-prompt.md", verifier_prompt(manifest, blockers))
    write_json(run_dir / "verifier-output.json", verifier_template(manifest))
    print(
        f"Gated manual outputs: {gate_state['status']}; "
        f"accepted={len(findings)} rejected={len(rejections_doc['rejections'])}"
    )
    return 0


def validate_verifier(output: Any, manifest: dict[str, Any], blocker_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(output, dict):
        raise BootstrapError("Verifier output must be an object")
    schema_errors = schema_validation_errors("bootstrap-verifier-output.v1.schema.json", output)
    if schema_errors:
        raise BootstrapError("Verifier output violates bootstrap-verifier-output.v1: " + "; ".join(schema_errors))
    expected = {
        "schemaVersion": "bootstrap-verifier-output.v1",
        "reviewId": manifest["reviewId"],
        "routeVersion": manifest["routeVersion"],
        "authorityRevision": manifest["authorityRevision"],
        "inputHash": manifest["inputHash"],
    }
    if any(output.get(key) != value for key, value in expected.items()):
        raise BootstrapError("Verifier output binding does not match review input")
    if set(output) != set(expected) | {"decisions"} or not isinstance(output.get("decisions"), list):
        raise BootstrapError("Verifier output shape is invalid")
    decisions: dict[str, dict[str, Any]] = {}
    for decision in output["decisions"]:
        if not isinstance(decision, dict):
            raise BootstrapError("Every verifier decision must be an object")
        required = {"findingId", "decision", "reason", "evidenceChecked"}
        allowed = required | {"unverifiedClass"}
        if not required.issubset(decision) or set(decision) - allowed:
            raise BootstrapError("Verifier decision shape is invalid")
        finding_id = decision["findingId"]
        if finding_id not in blocker_ids or finding_id in decisions:
            raise BootstrapError(f"Verifier supplied an unknown or duplicate finding ID: {finding_id}")
        status = decision["decision"]
        if status not in {"confirmed", "refuted", "unverified"}:
            raise BootstrapError(f"Invalid verifier decision for {finding_id}")
        if not isinstance(decision["reason"], str) or not decision["reason"].strip():
            raise BootstrapError(f"Verifier reason is required for {finding_id}")
        checked = decision["evidenceChecked"]
        if not isinstance(checked, list) or not checked or any(not isinstance(item, str) or not item.strip() for item in checked):
            raise BootstrapError(f"Verifier evidenceChecked is required for {finding_id}")
        context_code, context_reason = validate_scope_references(checked, manifest, "evidenceChecked")
        if context_code:
            raise BootstrapError(f"Verifier evidence is invalid for {finding_id}: {context_reason}")
        if status == "unverified" and decision.get("unverifiedClass") not in {"security", "data_loss", "other"}:
            raise BootstrapError(f"Unverified class is required for {finding_id}")
        if status != "unverified" and "unverifiedClass" in decision:
            raise BootstrapError(f"Only unverified decisions may set unverifiedClass: {finding_id}")
        decisions[finding_id] = decision
    missing = blocker_ids - set(decisions)
    if missing:
        raise BootstrapError(f"Verifier decisions are missing for: {', '.join(sorted(missing))}")
    return decisions


def command_finalize(args: argparse.Namespace) -> int:
    run_dir, manifest, repository_root = load_run(args.run_dir)
    gate = read_json(run_dir / "review-gate-state.json")
    if gate.get("inputHash") != manifest["inputHash"]:
        raise BootstrapError("Gate result does not belong to this review input")
    if gate.get("failedLayers"):
        raise BootstrapError("Cannot finalize while required reviewer layers are incomplete")
    candidate_doc = read_json(run_dir / "review-candidates.json")
    rejections_doc = read_json(run_dir / "review-rejections.json")
    if gate.get("candidatesHash") != value_hash(candidate_doc):
        raise BootstrapError("review-candidates.json changed after gate")
    if gate.get("rejectionsHash") != value_hash(rejections_doc):
        raise BootstrapError("review-rejections.json changed after gate")
    reevaluated = evaluate_reviewer_outputs(run_dir, manifest, repository_root)
    if reevaluated["candidatesDoc"] != candidate_doc:
        raise BootstrapError("Reviewer outputs no longer reproduce review-candidates.json")
    if reevaluated["rejectionsDoc"] != rejections_doc:
        raise BootstrapError("Reviewer outputs no longer reproduce review-rejections.json")
    if reevaluated["gateState"] != gate:
        raise BootstrapError("Reviewer outputs no longer reproduce review-gate-state.json")
    findings = candidate_doc.get("findings") if isinstance(candidate_doc, dict) else None
    if not isinstance(findings, list):
        raise BootstrapError("review-candidates.json is invalid")
    for finding in findings:
        artifact = finding.get("artifact", "") if isinstance(finding, dict) else ""
        prepared = next((item for item in manifest["artifacts"] if item["artifact"] == artifact), None)
        if prepared is None or file_hash(ensure_within(repository_root / artifact, repository_root, "Finding artifact")) != prepared["sha256"]:
            raise BootstrapError(f"Finding evidence became stale before finalize: {artifact}")
    blockers = {item["findingId"]: item for item in findings if item.get("proposedSeverity") in {"P0", "P1"}}
    decisions = validate_verifier(read_json(run_dir / "verifier-output.json"), manifest, set(blockers))
    dispositions: list[dict[str, Any]] = []
    visible: list[dict[str, Any]] = []
    has_blocking = False
    has_manual_pause = False
    for finding in findings:
        current = dict(finding)
        finding_id = current["findingId"]
        if current["proposedSeverity"] == "P2":
            current["status"] = "advisory"
            visible.append(current)
            dispositions.append({"findingId": finding_id, "status": "advisory", "reason": "P2 passed the deterministic evidence gate"})
            continue
        decision = decisions[finding_id]
        current["status"] = decision["decision"]
        disposition = {"findingId": finding_id, "status": decision["decision"], "reason": decision["reason"]}
        if decision["decision"] == "confirmed":
            has_blocking = True
            visible.append(current)
        elif decision["decision"] == "unverified":
            classification = decision["unverifiedClass"]
            machine_disposition = "blocking" if classification in {"security", "data_loss"} else "manual_pause"
            current["unverifiedClass"] = classification
            current["unverifiedDisposition"] = machine_disposition
            disposition.update({"unverifiedClass": classification, "unverifiedDisposition": machine_disposition})
            has_blocking |= machine_disposition == "blocking"
            has_manual_pause |= machine_disposition == "manual_pause"
            visible.append(current)
        dispositions.append(disposition)
    if has_blocking and has_manual_pause:
        raise BootstrapError("Blocking and manual-pause dispositions cannot be mixed in one final result")
    if has_blocking:
        status = "blocked"
    elif has_manual_pause:
        status = "incomplete"
    elif any(item["status"] == "advisory" for item in visible):
        status = "advisory"
    else:
        status = "clean"
    result = {
        "schemaVersion": "review-result.v1",
        "reviewId": manifest["reviewId"],
        "routeVersion": manifest["routeVersion"],
        "reviewProfile": manifest["reviewProfile"],
        "policyRevision": manifest["policyRevision"],
        "requiredLayers": manifest["requiredLayers"],
        "completedLayers": manifest["requiredLayers"],
        "scope": manifest["scope"],
        "authorityRevision": manifest["authorityRevision"],
        "inputHash": manifest["inputHash"],
        "status": status,
        "failedLayers": [],
        "skippedLayers": [],
        "findings": visible,
    }
    runtime = load_schema_runtime()
    registry = schema_registry()
    result_schema_errors = runtime.schema_errors(registry["review-result.v1.schema.json"], result, registry)
    profile_key = (manifest["reviewProfile"], manifest["policyRevision"])
    runtime.TRUSTED_REVIEW_POLICIES[profile_key] = set(manifest["requiredLayers"])
    result_schema_errors.extend(runtime.result_semantic_errors(result, profile_key))
    for finding in visible:
        result_schema_errors.extend(runtime.finding_semantic_errors(finding))
    if result_schema_errors:
        raise BootstrapError("Final result violates review-result.v1: " + "; ".join(result_schema_errors))
    write_json(run_dir / "review-gate-result.json", result)
    write_json(
        run_dir / "review-dispositions.json",
        {
            "schemaVersion": "bootstrap-review-dispositions.v1",
            "authorityClass": AUTHORITY_CLASS,
            "dispositions": dispositions,
        },
    )
    rejection_count = len(rejections_doc.get("rejections", [])) if isinstance(rejections_doc, dict) else 0
    metrics = {
        "schemaVersion": "bootstrap-review-metrics.v1",
        "authorityClass": AUTHORITY_CLASS,
        "reviewId": manifest["reviewId"],
        "inputHash": manifest["inputHash"],
        "status": status,
        "rawCandidateCount": len(findings) + rejection_count,
        "acceptedUniqueCount": len(findings),
        "rejectedCount": rejection_count,
        "confirmedCount": sum(item["status"] == "confirmed" for item in visible),
        "advisoryCount": sum(item["status"] == "advisory" for item in visible),
        "unverifiedCount": sum(item["status"] == "unverified" for item in visible),
        "refutedCount": sum(item["status"] == "refuted" for item in dispositions),
    }
    write_json(run_dir / "review-metrics.json", metrics)
    report_lines = [
        "# Bootstrap Review Report", "", f"Review ID: `{manifest['reviewId']}`", f"Status: `{status}`", "",
        f"Accepted unique candidates: {len(findings)}", f"Rejected candidates: {rejection_count}",
        f"Visible findings: {len(visible)}", "", f"Authority class: `{AUTHORITY_CLASS}`",
        "This evidence is plan-local bootstrap output, not BH-HANDOFF or production gateway authority.",
    ]
    write_text(run_dir / "review-report.md", "\n".join(report_lines) + "\n")
    print(f"Finalized manual bootstrap review: {status}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="Create hash-bound manual reviewer materials")
    prepare.add_argument("--repository-root", required=True)
    prepare.add_argument("--review-id", required=True)
    prepare.add_argument("--profile", required=True)
    prepare.add_argument("--scope", action="append", required=True)
    prepare.add_argument("--out-dir", required=True)
    prepare.set_defaults(handler=command_prepare)
    gate = subparsers.add_parser("gate", help="Validate and deduplicate manually saved reviewer outputs")
    gate.add_argument("--run-dir", required=True)
    gate.set_defaults(handler=command_gate)
    finalize = subparsers.add_parser("finalize", help="Apply manually saved verifier decisions")
    finalize.add_argument("--run-dir", required=True)
    finalize.set_defaults(handler=command_finalize)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return args.handler(args)
    except BootstrapError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
