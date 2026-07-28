"""Deterministic validation primitives for implementation-acceptance runs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


class InputError(ValueError):
    pass


_MODES = {"evidence_only", "controlled_validation"}
_CANDIDATE_MODES = {"commit", "dirty_worktree", "proposed_commit_set"}
_MANIFEST_STATUS = {"complete", "partial", "unavailable"}
_ROLES = {"implementation", "consumer", "source", "authority", "test", "evidence"}
_CHANGE_TYPES = {"unchanged", "added", "modified", "deleted", "renamed", "untracked"}
_EXTRACTION_MODES = {"registry_backed", "parser_backed", "semantic_candidate"}
_COMPLETENESS = {"deterministic_complete", "semantically_attested_complete", "candidate", "incomplete"}
_PHASE_PREFIXES = ("PhaseA.Platform/", "PhaseA.Platform.Tests/", "runtime/phase-a/", "scripts/python/phase_a_", "scripts/python/phase_b_", "scripts/sc/_llm_backend.py")
_GODOT_PREFIXES = ("Game.Godot/", "Tests.Godot/", "Game.Core/", "Game.Core.Tests/")


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _hash(value: Any, field: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
        raise InputError(f"{field} must be a sha256 hash")


def _relative(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise InputError(f"{field} must be a repository-relative path")


def _normalized_relative(value: Any, field: str) -> str:
    _relative(value, field)
    return value.replace("\\", "/")


def parse_run_input(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError("run input must be an object")
    target = value.get("target")
    if not isinstance(target, str) or not Path(target).is_absolute():
        raise InputError("target must be an absolute path")
    mode = value.get("execution_mode", "evidence_only")
    if mode not in _MODES:
        raise InputError("execution_mode is invalid")
    if "candidate_mode" in value and value["candidate_mode"] not in _CANDIDATE_MODES:
        raise InputError("candidate_mode is invalid")
    return {**value, "target": target, "execution_mode": mode}


def validate_run_input(value: Any) -> None:
    parsed = parse_run_input(value)
    required_strings = {
        "run_id", "created_utc", "change_id", "baseline_revision", "candidate_revision",
        "baseline_content_manifest_path", "baseline_content_manifest_hash",
        "candidate_content_manifest_path", "candidate_content_manifest_hash",
        "code_review_domain", "code_review_policy_path", "code_review_policy_hash",
        "target_plan_hash", "validator_hash", "adapter_id", "adapter_version", "adapter_hash",
    }
    missing = [field for field in required_strings if not isinstance(parsed.get(field), str) or not parsed[field].strip()]
    if missing:
        raise InputError("run input lacks required fields: " + ", ".join(sorted(missing)))
    if parsed.get("candidate_mode") not in _CANDIDATE_MODES:
        raise InputError("run input candidate_mode is required")
    if not isinstance(parsed.get("target_plan_paths"), list) or not parsed["target_plan_paths"]:
        raise InputError("run input target_plan_paths is required")
    if parsed.get("code_review_domain") != "phase_service":
        raise InputError("unsupported code_review_domain")
    for field in {name for name in required_strings if name.endswith("_hash")}:
        _hash(parsed[field], field)
    for field in ("baseline_content_manifest_path", "candidate_content_manifest_path", "code_review_policy_path"):
        _relative(parsed[field], field)
    for field in ("allowed_write_roots", "forbidden_write_roots", "changed_paths", "affected_consumer_refs"):
        if not isinstance(parsed.get(field), list):
            raise InputError(f"run input {field} is required")


def validate_baseline_manifest(value: Any) -> None:
    if not isinstance(value, dict) or value.get("schemaVersion") != "acceptance-baseline-content-manifest.v1":
        raise InputError("baseline manifest schemaVersion is invalid")
    if set(value) != {"schemaVersion", "status", "coverageGaps", "authorizes", "files"}:
        raise InputError("baseline manifest top-level fields are invalid")
    _validate_manifest_header(value)
    files = value.get("files")
    if not isinstance(files, list):
        raise InputError("baseline manifest files are invalid")
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "roles", "inclusion_reason"}:
            raise InputError("baseline manifest file is invalid")
        path = item.get("path")
        _relative(path, "baseline file path")
        _hash(item.get("sha256"), "baseline file sha256")
        _roles(item.get("roles"))
        if not isinstance(item.get("inclusion_reason"), str) or not item["inclusion_reason"].strip() or path in seen:
            raise InputError("baseline manifest file is incomplete or duplicated")
        seen.add(path)


def _validate_manifest_header(value: dict[str, Any]) -> None:
    status = value.get("status")
    gaps = value.get("coverageGaps")
    if status not in _MANIFEST_STATUS or not isinstance(gaps, list) or value.get("authorizes") != []:
        raise InputError("manifest status, coverageGaps, or authority boundary is invalid")
    if status == "complete" and gaps:
        raise InputError("complete manifest cannot contain coverage gaps")
    if status != "complete" and not gaps:
        raise InputError("partial or unavailable manifest must explain coverage gaps")


def _roles(value: Any) -> None:
    if not isinstance(value, list) or not value or len(value) != len(set(value)) or not set(value).issubset(_ROLES):
        raise InputError("manifest roles are invalid")


def validate_candidate_manifest(value: Any, baseline: Any) -> None:
    validate_baseline_manifest(baseline)
    if not isinstance(value, dict) or value.get("schemaVersion") != "acceptance-candidate-content-manifest.v1":
        raise InputError("candidate manifest schemaVersion is invalid")
    if set(value) != {"schemaVersion", "status", "coverageGaps", "authorizes", "files"}:
        raise InputError("candidate manifest top-level fields are invalid")
    _validate_manifest_header(value)
    files = value.get("files")
    if not isinstance(files, list):
        raise InputError("candidate manifest files are invalid")
    baseline_files = {item["path"]: item["sha256"] for item in baseline["files"]}
    baseline_seen: set[str] = set()
    candidate_seen: set[str] = set()
    for item in files:
        if (
            not isinstance(item, dict)
            or set(item) != {"change_type", "roles", "baseline_path", "baseline_sha256", "candidate_path", "candidate_sha256", "inclusion_reason"}
            or item.get("change_type") not in _CHANGE_TYPES
        ):
            raise InputError("candidate manifest file fields are invalid")
        _roles(item.get("roles"))
        kind, old_path, new_path = item["change_type"], item.get("baseline_path"), item.get("candidate_path")
        old_hash, new_hash = item.get("baseline_sha256"), item.get("candidate_sha256")
        if not isinstance(item.get("inclusion_reason"), str) or not item["inclusion_reason"].strip():
            raise InputError("candidate manifest inclusion reason is invalid")
        if kind in {"unchanged", "modified", "renamed", "deleted"}:
            _relative(old_path, "baseline_path")
            _hash(old_hash, "baseline_sha256")
        if kind in {"unchanged", "modified", "renamed", "added", "untracked"}:
            _relative(new_path, "candidate_path")
            _hash(new_hash, "candidate_sha256")
        if kind in {"added", "untracked"} and (old_path is not None or old_hash is not None):
            raise InputError("added or untracked entry cannot have a baseline")
        if kind == "deleted" and (new_path is not None or new_hash is not None or baseline_files.get(old_path) != old_hash):
            raise InputError("deleted entry must be a baseline tombstone")
        if kind in {"modified", "renamed"} and baseline_files.get(old_path) != old_hash:
            raise InputError("modified or renamed entry must close against the baseline")
        if kind == "unchanged" and (old_path != new_path or old_hash != new_hash):
            raise InputError("unchanged entry is inconsistent")
        if kind == "unchanged" and baseline_files.get(old_path) != old_hash:
            raise InputError("unchanged entry must close against the baseline")
        if kind == "modified" and (old_path != new_path or old_hash == new_hash):
            raise InputError("modified entry is inconsistent")
        if kind == "renamed" and old_path == new_path:
            raise InputError("renamed entry must change path")
        if old_path is not None:
            if old_path in baseline_seen:
                raise InputError("candidate manifest duplicates a baseline path")
            baseline_seen.add(old_path)
        if new_path is not None:
            if new_path in candidate_seen:
                raise InputError("candidate manifest duplicates a candidate path")
            candidate_seen.add(new_path)
    if value["status"] == "complete" and baseline_seen != set(baseline_files):
        raise InputError("complete candidate manifest must cover every baseline path")


def candidate_changed_paths(candidate: Any) -> list[str]:
    if not isinstance(candidate, dict) or not isinstance(candidate.get("files"), list):
        raise InputError("candidate manifest files are invalid")
    paths: list[str] = []
    for item in candidate["files"]:
        if not isinstance(item, dict):
            raise InputError("candidate manifest file is invalid")
        if item.get("change_type") != "unchanged":
            path = item.get("candidate_path") or item.get("baseline_path")
            _relative(path, "changed candidate path")
            paths.append(path)
    if len(paths) != len(set(paths)):
        raise InputError("candidate changed paths are duplicated")
    return sorted(paths)


def phase_changed_paths(candidate: Any) -> list[str]:
    """Return the scan target for every change that enters the Phase policy."""
    if not isinstance(candidate, dict) or not isinstance(candidate.get("files"), list):
        raise InputError("candidate manifest files are invalid")
    paths: list[str] = []
    for item in candidate["files"]:
        if not isinstance(item, dict):
            raise InputError("candidate manifest file is invalid")
        if item.get("change_type") == "unchanged":
            continue
        baseline_path = item.get("baseline_path")
        candidate_path = item.get("candidate_path")
        identities = (
            _normalized_relative(path, "Phase policy path")
            for path in (baseline_path, candidate_path)
            if isinstance(path, str)
        )
        if any(path.startswith(_PHASE_PREFIXES) for path in identities):
            path = _normalized_relative(candidate_path or baseline_path, "Phase changed path")
            paths.append(path)
    if len(paths) != len(set(paths)):
        raise InputError("Phase changed paths are duplicated")
    return sorted(paths)


def validate_source_inventory(value: Any) -> None:
    if not isinstance(value, dict) or value.get("schemaVersion") != "acceptance-source-inventory.v1":
        raise InputError("source inventory schemaVersion is invalid")
    if set(value) != {"schemaVersion", "overallCompleteness", "partitions"}:
        raise InputError("source inventory top-level fields are invalid")
    partitions = value.get("partitions")
    if not isinstance(partitions, list) or not partitions:
        raise InputError("source inventory partitions are invalid")
    observed: list[str] = []
    ids: set[str] = set()
    for item in partitions:
        if (
            not isinstance(item, dict)
            or set(item) - {"partition_id", "source_refs", "extraction_mode", "completeness", "attestationHash", "attestationScopeHash"}
            or not isinstance(item.get("partition_id"), str)
            or item["partition_id"] in ids
        ):
            raise InputError("source inventory partition id is invalid")
        ids.add(item["partition_id"])
        if item.get("extraction_mode") not in _EXTRACTION_MODES or item.get("completeness") not in _COMPLETENESS:
            raise InputError("source inventory partition mode is invalid")
        source_refs = item.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs:
            raise InputError("source inventory partition lacks sources")
        source_paths: set[str] = set()
        for source in source_refs:
            if not isinstance(source, dict) or set(source) != {"path", "sha256"}:
                raise InputError("source inventory source reference is invalid")
            _relative(source.get("path"), "source inventory source path")
            _hash(source.get("sha256"), "source inventory source hash")
            if source["path"] in source_paths:
                raise InputError("source inventory source path is duplicated")
            source_paths.add(source["path"])
        if item["extraction_mode"] == "semantic_candidate" and item["completeness"] == "deterministic_complete":
            raise InputError("semantic partition cannot claim deterministic completion")
        if item["completeness"] == "semantically_attested_complete":
            _hash(item.get("attestationHash"), "semantic partition attestationHash")
            _hash(item.get("attestationScopeHash"), "semantic partition attestationScopeHash")
        if item["completeness"] != "semantically_attested_complete" and (
            item.get("attestationHash") is not None or item.get("attestationScopeHash") is not None
        ):
            raise InputError("non-attested partition cannot carry attestation bindings")
        observed.append(item["completeness"])
    expected = "incomplete" if "incomplete" in observed else "candidate" if "candidate" in observed else "semantically_attested_complete" if "semantically_attested_complete" in observed else "deterministic_complete"
    if value.get("overallCompleteness") != expected:
        raise InputError("source inventory overallCompleteness is inconsistent")


def validate_policy_pack(value: Any) -> None:
    if not isinstance(value, dict) or value.get("schemaVersion") != "code-review-policy-pack.v1":
        raise InputError("policy pack schemaVersion is invalid")
    if set(value) != {"schemaVersion", "policyId", "targetDomain", "authorityRefs", "checks", "policyRevision"}:
        raise InputError("policy pack fields are invalid")
    if value.get("policyId") != "phase-service-code-review" or value.get("targetDomain") != "phase_service":
        raise InputError("policy pack identity is invalid")
    revision = value.get("policyRevision")
    core = {key: item for key, item in value.items() if key != "policyRevision"}
    if revision != canonical_hash(core):
        raise InputError("policy pack revision is stale")
    checks = value.get("checks")
    if not isinstance(checks, list) or not checks:
        raise InputError("policy pack checks are invalid")
    if any(not isinstance(item, dict) or set(item) != {"policyCheckId", "evaluationMode"} for item in checks):
        raise InputError("policy pack check fields are invalid")
    ids = [item.get("policyCheckId") for item in checks if isinstance(item, dict)]
    if len(ids) != len(checks) or len(set(ids)) != len(ids) or any(not isinstance(item, str) or not item.startswith("PHASE-CR-") for item in ids):
        raise InputError("policy pack check ids are invalid")
    if any(item.get("evaluationMode") not in {"deterministic", "review_gate", "hybrid", "conditional_gate"} for item in checks):
        raise InputError("policy pack evaluation mode is invalid")


def resolve_phase_policy(policy: Any, candidate_manifest: Any, baseline_manifest: Any, adapter_hash: str) -> dict[str, Any]:
    validate_policy_pack(policy)
    validate_candidate_manifest(candidate_manifest, baseline_manifest)
    _hash(adapter_hash, "adapter_hash")
    paths = [_normalized_relative(path, "Changed path") for path in candidate_changed_paths(candidate_manifest)]
    phase_paths = phase_changed_paths(candidate_manifest)
    external_paths = sorted(path for path in paths if path not in phase_paths)
    if external_paths and not phase_paths:
        raise InputError("unsupported_code_review_domain")
    if not phase_paths:
        raise InputError("phase policy was not triggered")
    binding = {"schemaVersion": "code-review-policy-binding.v1", "policyId": policy["policyId"], "policyRevision": policy["policyRevision"], "policyHash": canonical_hash(policy), "candidateManifestHash": canonical_hash(candidate_manifest), "adapterHash": adapter_hash, "triggeredPaths": phase_paths, "unreviewedExternalDomainPaths": external_paths, "activatedCheckIds": [item["policyCheckId"] for item in policy["checks"]], "authorizes": []}
    binding["bindingHash"] = canonical_hash(binding)
    return binding


def validate_diff_coverage(value: Any) -> None:
    if not isinstance(value, dict) or value.get("schemaVersion") != "phase-diff-coverage-result.v1":
        raise InputError("diff coverage schemaVersion is invalid")
    if value.get("minimumChangedLineCoveragePct") != 85.0:
        raise InputError("diff coverage threshold must be 85.0")
    counts = value.get("counts")
    if not isinstance(counts, dict):
        raise InputError("diff coverage counts are invalid")
    measurable, covered = counts.get("measurableChangedExecutableLines"), counts.get("coveredChangedExecutableLines")
    if not isinstance(measurable, int) or not isinstance(covered, int) or measurable < 0 or covered < 0 or covered > measurable:
        raise InputError("diff coverage counts are inconsistent")
    if measurable == 0:
        if value.get("status") != "not_applicable":
            raise InputError("zero measurable lines must be not_applicable")
        return
    percent = covered / measurable * 100
    if value.get("status") != "passed" or value.get("changedLineCoveragePct") != percent or percent < 85.0:
        raise InputError("diff coverage does not meet the required threshold")


def validate_task_checklist_closure(value: Any) -> None:
    if not isinstance(value, dict) or value.get("schemaVersion") != "task-checklist-closure.v1":
        raise InputError("task checklist closure schemaVersion is invalid")
    required_top_level = {
        "schemaVersion", "acceptanceRunId", "candidateContentManifestHash", "sources", "items",
        "requiredItemCount", "checkedRequiredItemCount", "verifiedRequiredItemCount", "status", "authorizes",
    }
    if set(value) != required_top_level or value.get("authorizes") != []:
        raise InputError("task checklist closure top-level fields are invalid")
    items = value.get("items")
    if not isinstance(items, list) or not items:
        raise InputError("task checklist items are invalid")
    ids: set[str] = set()
    for item in items:
        required_fields = {
            "taskChecklistItemId", "sourceRef", "sectionAnchor", "textSignature", "requiredness", "checked",
            "matrixCheckIds", "implementationRefs", "testRefs", "evidenceIds", "status",
        }
        if not isinstance(item, dict) or set(item) != required_fields or not isinstance(item.get("taskChecklistItemId"), str) or item["taskChecklistItemId"] in ids:
            raise InputError("task checklist item identity is invalid")
        ids.add(item["taskChecklistItemId"])
        if item.get("requiredness") not in {"required", "optional"} or not isinstance(item.get("checked"), bool):
            raise InputError("task checklist item contract is invalid")
        references = ("matrixCheckIds", "implementationRefs", "testRefs", "evidenceIds")
        if any(not isinstance(item.get(name), list) for name in references):
            raise InputError("task checklist item references are invalid")
        if item["requiredness"] == "required" and (item.get("checked") is not True or item.get("status") != "verified" or any(not item[name] for name in references)):
            raise InputError("required task checklist item is not closed")


def validate_scan_scope(value: Any, expected_paths: list[str], kind: str, candidate_manifest_hash: str | None = None) -> None:
    bundle_id = "phase-static-analysis" if kind == "static-analysis" else "phase-security-scan" if kind == "security-scan" else None
    if bundle_id is None or not isinstance(value, dict) or value.get("schemaVersion") != "phase-scan-bundle-result.v1" or value.get("bundleId") != bundle_id:
        raise InputError("scan result schemaVersion is invalid")
    if (
        value.get("status") != "passed"
        or sorted(value.get("requiredChangedPaths", [])) != sorted(expected_paths)
        or sorted(value.get("readChangedPaths", [])) != sorted(expected_paths)
        or value.get("missingChangedPaths") != []
    ):
        raise InputError("scan scope is incomplete")
    if candidate_manifest_hash is not None and value.get("candidateContentManifestHash") != candidate_manifest_hash:
        raise InputError("scan candidate manifest binding is stale")
    process = value.get("processResult")
    if (
        not isinstance(value.get("commandId"), str)
        or not isinstance(value.get("toolHash"), str)
        or not isinstance(value.get("commandRegistryHash"), str)
        or not isinstance(value.get("processResultHash"), str)
        or not isinstance(process, dict)
        or process.get("exitCode") != 0
    ):
        raise InputError("scan command binding is invalid")


def validate_policy_matrix_coverage(binding: Any, matrix_rows: Any) -> None:
    if not isinstance(binding, dict) or not isinstance(matrix_rows, list):
        raise InputError("policy binding or matrix rows are invalid")
    expected = binding.get("activatedCheckIds")
    if not isinstance(expected, list) or len(expected) != len(set(expected)):
        raise InputError("activated policy checks are invalid")
    observed: list[str] = []
    for row in matrix_rows:
        if not isinstance(row, dict) or not isinstance(row.get("policyCheckId"), str) or not isinstance(row.get("check_id"), str):
            raise InputError("policy matrix row is invalid")
        if row.get("policyBindingHash") != binding.get("bindingHash"):
            raise InputError("policy matrix row has stale binding")
        observed.append(row["policyCheckId"])
    if sorted(observed) != sorted(expected) or len(observed) != len(set(observed)):
        raise InputError("policy checks do not have exact matrix coverage")
