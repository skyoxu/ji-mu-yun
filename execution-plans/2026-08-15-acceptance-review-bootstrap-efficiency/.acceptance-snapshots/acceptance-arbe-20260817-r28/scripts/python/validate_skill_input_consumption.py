#!/usr/bin/env python
"""Validate a Skill input receipt and its hash-bound sidecars."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skill_input_consumption import (
    DEFAULT_MAX_SNAPSHOT_BYTES,
    SkillInputError,
    canonical_hash,
    contained_path,
    contract_hash,
    expand_source_graph,
    forbidden_repository_path,
    line_ranges,
    is_reparse_point,
    read_json,
    redact_bytes,
    redaction_profile_hash,
    repository_identity,
    sha256_bytes,
    validate_contract,
    validate_request_payload,
    write_bytes_atomic,
    write_json_atomic,
)


ZERO_HASH = "sha256:" + "0" * 64
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
CHILD_CAPABILITIES = {"read-frozen-snapshot", "write-context-output"}


class ReceiptValidationError(ValueError):
    pass


def _reject_symlink_components(path: Path, label: str, *, stop: Path | None = None) -> None:
    current = path.absolute()
    boundary = stop.absolute() if stop is not None else None
    while True:
        if is_reparse_point(current):
            raise ReceiptValidationError(f"{label}.path may not contain a symlink")
        if boundary is not None and current == boundary:
            return
        if current.parent == current:
            return
        current = current.parent


def _artifact(root: Path, value: Any, label: str) -> tuple[Path, str]:
    if not isinstance(value, dict) or not isinstance(value.get("path"), str) or not isinstance(value.get("sha256"), str):
        raise ReceiptValidationError(f"{label} must contain path and sha256")
    if not SHA256_RE.fullmatch(value["sha256"]):
        raise ReceiptValidationError(f"{label}.sha256 is invalid")
    raw = Path(value["path"])
    if raw.is_absolute():
        raise ReceiptValidationError(f"{label}.path must be relative")
    joined = root / raw
    _reject_symlink_components(joined, label, stop=root)
    resolved = joined.resolve()
    try:
        rel = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ReceiptValidationError(f"{label}.path escapes receipt root") from exc
    if rel.startswith("logs/"):
        raise ReceiptValidationError(f"{label}.path is forbidden")
    return resolved, rel


def _check_sha(value: Any, label: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ReceiptValidationError(f"{label} is not sha256:<64 lowercase hex>")


def _validate_model_safe_payload(payload: Any, label: str) -> None:
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        redacted, _sensitivity, _status = redact_bytes(raw)
    except SkillInputError as exc:
        raise ReceiptValidationError(f"{label} is not model-safe UTF-8") from exc
    if redacted != raw:
        raise ReceiptValidationError(f"{label} contains credential-like output")


def _validate_context(payload: Any, manifest_hash: str, *, max_context_bytes: int | None = None, serialized_size: int | None = None) -> None:
    if not isinstance(payload, dict):
        raise ReceiptValidationError("context artifact must be an object")
    required = {"schema_version", "source_manifest_hash", "sections", "truncated", "omitted_items", "generated_at"}
    if set(payload) != required:
        raise ReceiptValidationError("context artifact fields do not match schema")
    if payload["schema_version"] != "skill-input-context.v1" or payload["source_manifest_hash"] != manifest_hash:
        raise ReceiptValidationError("context artifact schema or manifest binding is invalid")
    if not isinstance(payload["sections"], list) or len(payload["sections"]) > 200:
        raise ReceiptValidationError("context sections are invalid")
    for section in payload["sections"]:
        if not isinstance(section, dict) or set(section) != {"title", "content"} or not all(isinstance(section[k], str) and section[k] for k in section):
            raise ReceiptValidationError("context section is invalid")
    if type(payload["truncated"]) is not bool or type(payload["omitted_items"]) is not int or payload["omitted_items"] < 0:
        raise ReceiptValidationError("context truncation fields are invalid")
    if not isinstance(payload["generated_at"], str) or not payload["generated_at"]:
        raise ReceiptValidationError("context generated_at is invalid")
    _validate_model_safe_payload(payload, "context artifact")
    if max_context_bytes is not None:
        if serialized_size is None:
            serialized_size = len((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        if serialized_size > max_context_bytes:
            raise ReceiptValidationError("context artifact exceeds contract max_context_bytes")


def _validate_decision(payload: Any, manifest_hash: str, context_hash: str, source_statuses: dict[str, str]) -> None:
    if not isinstance(payload, dict):
        raise ReceiptValidationError("semantic decision must be an object")
    required = {"schema_version", "producer_role", "execution_identity", "source_manifest_hash", "context_artifact_hash", "source_statuses", "status", "rationale", "redaction_status", "redaction_profile_hash", "authorizes"}
    optional = {"snapshot_read_coverage"}
    if not required.issubset(payload) or set(payload) - required - optional:
        raise ReceiptValidationError("semantic decision fields do not match schema")
    if payload["schema_version"] != "skill-semantic-decision.v1" or payload["source_manifest_hash"] != manifest_hash or payload["context_artifact_hash"] != context_hash:
        raise ReceiptValidationError("semantic decision binding is invalid")
    if not isinstance(payload["producer_role"], str) or not payload["producer_role"]:
        raise ReceiptValidationError("semantic decision producer role is invalid")
    _check_sha(payload["execution_identity"], "semantic decision execution_identity")
    _check_sha(payload["redaction_profile_hash"], "semantic decision redaction_profile_hash")
    if payload["redaction_profile_hash"] != redaction_profile_hash():
        raise ReceiptValidationError("semantic decision redaction profile is stale")
    if payload["status"] not in {"accepted", "insufficient"} or not isinstance(payload["rationale"], str) or len(payload["rationale"].encode("utf-8")) > 2000:
        raise ReceiptValidationError("semantic decision status or rationale is invalid")
    if (
        payload["authorizes"] != []
        or not isinstance(payload["source_statuses"], dict)
        or any(
            not isinstance(path, str)
            or not path
            or status not in {"accepted", "insufficient", "not-evaluated"}
            for path, status in payload["source_statuses"].items()
        )
    ):
        raise ReceiptValidationError("semantic decision must not authorize actions")
    if payload["source_statuses"] != source_statuses:
        raise ReceiptValidationError("semantic decision source statuses do not match receipt")
    if payload["redaction_status"] not in {"not-required", "complete", "failed"}:
        raise ReceiptValidationError("semantic decision redaction status is invalid")
    coverage = payload.get("snapshot_read_coverage")
    if coverage is not None:
        if (
            not isinstance(coverage, dict)
            or set(coverage) != {"path", "sha256"}
            or not isinstance(coverage["path"], str)
            or not coverage["path"]
        ):
            raise ReceiptValidationError("semantic decision snapshot read coverage is invalid")
        _check_sha(coverage["sha256"], "semantic decision snapshot read coverage sha256")
    _validate_model_safe_payload(payload, "semantic decision")


def _validate_paged_read_coverage(
    coverage_ref: dict[str, Any],
    output_root: Path,
    repository_root: Path,
    manifest_path: Path,
    request: dict[str, Any],
) -> None:
    raw_path = Path(coverage_ref["path"])
    if raw_path.is_absolute() or ".." in raw_path.parts:
        raise ReceiptValidationError("snapshot read coverage path is invalid")
    coverage_path = (output_root / raw_path).resolve()
    try:
        coverage_path.relative_to(output_root.resolve())
    except ValueError as exc:
        raise ReceiptValidationError("snapshot read coverage path escapes output root") from exc
    if not coverage_path.is_file() or sha256_bytes(coverage_path.read_bytes()) != coverage_ref["sha256"]:
        raise ReceiptValidationError("snapshot read coverage is missing or stale")
    coverage = read_json(coverage_path)
    required = {"schema_version", "source_manifest_hash", "input_mode", "chunk_bytes", "segments"}
    if (
        not isinstance(coverage, dict)
        or set(coverage) != required
        or coverage["schema_version"] != "skill-input-read-coverage.v1"
        or coverage["source_manifest_hash"] != request["source_manifest_hash"]
        or coverage["input_mode"] != "paged-frozen-snapshot-stdin"
        or coverage["chunk_bytes"] != request["max_snapshot_chunk_bytes"]
        or not isinstance(coverage["segments"], list)
        or not coverage["segments"]
    ):
        raise ReceiptValidationError("snapshot read coverage payload is invalid")
    manifest = read_json(manifest_path)
    expected_sources = {
        item["path"]: item["semantic_snapshot_sha256"]
        for item in manifest.get("sources", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    coverage_by_source: dict[str, list[dict[str, Any]]] = {}
    required_segment = {
        "source_path", "source_sha256", "ordinal", "total", "start_byte", "end_byte",
        "start_line", "end_line", "content_sha256",
    }
    for segment in coverage["segments"]:
        if not isinstance(segment, dict) or set(segment) != required_segment:
            raise ReceiptValidationError("snapshot read coverage segment is invalid")
        source_path = segment["source_path"]
        if source_path not in expected_sources or segment["source_sha256"] != expected_sources[source_path]:
            raise ReceiptValidationError("snapshot read coverage source binding is invalid")
        for field in ("ordinal", "total", "start_byte", "end_byte", "start_line", "end_line"):
            if not isinstance(segment[field], int) or isinstance(segment[field], bool) or segment[field] < 0:
                raise ReceiptValidationError("snapshot read coverage range is invalid")
        _check_sha(segment["content_sha256"], "snapshot read coverage content sha256")
        coverage_by_source.setdefault(source_path, []).append(segment)
    if set(coverage_by_source) != set(expected_sources):
        raise ReceiptValidationError("snapshot read coverage omits a frozen source")
    for source_path, segments in coverage_by_source.items():
        live_source, _ = contained_path(repository_root, source_path)
        source_bytes, _sensitivity, redaction_status = redact_bytes(live_source.read_bytes())
        if redaction_status == "failed" or sha256_bytes(source_bytes) != expected_sources[source_path]:
            raise ReceiptValidationError("snapshot read coverage source projection is invalid")
        ordered = sorted(segments, key=lambda item: item["ordinal"])
        if [item["ordinal"] for item in ordered] != list(range(1, len(ordered) + 1)):
            raise ReceiptValidationError("snapshot read coverage ordinal is not contiguous")
        if any(item["total"] != len(ordered) for item in ordered):
            raise ReceiptValidationError("snapshot read coverage total is invalid")
        cursor = 0
        line_cursor = 1
        for segment in ordered:
            if segment["start_byte"] != cursor or not cursor <= segment["end_byte"] <= len(source_bytes):
                raise ReceiptValidationError("snapshot read coverage byte range is not contiguous")
            if segment["end_byte"] - segment["start_byte"] > coverage["chunk_bytes"]:
                raise ReceiptValidationError("snapshot read coverage page exceeds chunk_bytes")
            page = source_bytes[segment["start_byte"]:segment["end_byte"]]
            if sha256_bytes(page) != segment["content_sha256"]:
                raise ReceiptValidationError("snapshot read coverage content hash is invalid")
            if (
                segment["start_line"] != line_cursor
                or segment["end_line"] != line_cursor + page.count(b"\n")
            ):
                raise ReceiptValidationError("snapshot read coverage line range is invalid")
            cursor = segment["end_byte"]
            line_cursor = segment["end_line"]
        if cursor != len(source_bytes):
            raise ReceiptValidationError("snapshot read coverage does not reach EOF")


def _validate_child_request_binding(
    payload: Any,
    receipt: dict[str, Any],
    contract: dict[str, Any],
    repository_root: Path,
    manifest_path: Path,
    context_path: Path,
    decision_path: Path,
    decision: dict[str, Any],
) -> None:
    required = {
        "schema_version", "consumer", "operation", "contract_hash", "source_manifest_hash",
        "snapshot_root", "output_root", "execution_identity", "max_context_bytes",
        "allowed_capabilities", "authorizes",
    }
    if not isinstance(payload, dict) or not required.issubset(payload) or set(payload) - required - {"max_snapshot_bytes", "input_mode", "max_snapshot_chunk_bytes"}:
        raise ReceiptValidationError("child request fields do not match schema")
    if (
        payload["schema_version"] != "skill-input-child-request.v1"
        or payload["consumer"] != receipt["consumer"]
        or payload["operation"] != receipt["operation"]
        or payload["contract_hash"] != receipt["contract_hash"]
        or payload["source_manifest_hash"] != receipt["source_manifest"]["sha256"]
        or payload["max_context_bytes"] != contract["max_context_bytes"]
        or payload.get("max_snapshot_bytes", DEFAULT_MAX_SNAPSHOT_BYTES)
        != contract.get("max_snapshot_bytes", DEFAULT_MAX_SNAPSHOT_BYTES)
        or payload.get("input_mode", "serialized-snapshot-stdin")
        != contract.get("semantic_input_mode", "serialized-snapshot-stdin")
        or payload["authorizes"] != []
        or payload["execution_identity"] != decision.get("execution_identity")
    ):
        raise ReceiptValidationError("child request binding is stale")
    _check_sha(payload["execution_identity"], "child request execution_identity")
    if payload.get("input_mode", "serialized-snapshot-stdin") == "paged-frozen-snapshot-stdin":
        if payload.get("max_snapshot_chunk_bytes") != contract.get("max_snapshot_chunk_bytes"):
            raise ReceiptValidationError("child request page budget is stale")
        coverage_ref = decision.get("snapshot_read_coverage")
        if not isinstance(coverage_ref, dict):
            raise ReceiptValidationError("paged child decision lacks snapshot read coverage")
    elif payload.get("max_snapshot_chunk_bytes") is not None or decision.get("snapshot_read_coverage") is not None:
        raise ReceiptValidationError("serialized child may not bind snapshot read coverage")
    capabilities = payload["allowed_capabilities"]
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or len(capabilities) != len(set(capabilities))
        or any(capability not in CHILD_CAPABILITIES for capability in capabilities)
    ):
        raise ReceiptValidationError("child request capabilities are invalid")
    try:
        snapshot_root, _ = contained_path(repository_root, payload["snapshot_root"])
        output_root, _ = contained_path(repository_root, payload["output_root"])
    except (TypeError, SkillInputError) as exc:
        raise ReceiptValidationError("child request path binding is invalid") from exc
    if not snapshot_root.is_dir() or not output_root.is_dir():
        raise ReceiptValidationError("child request roots are invalid")
    if (snapshot_root / "source-manifest.v1.json").resolve() != manifest_path.resolve():
        raise ReceiptValidationError("child request snapshot manifest is stale")
    for sidecar, label in ((context_path, "context"), (decision_path, "decision")):
        try:
            sidecar.resolve().relative_to(output_root.resolve())
        except ValueError as exc:
            raise ReceiptValidationError(f"child request {label} output escapes output_root") from exc
    if payload.get("input_mode", "serialized-snapshot-stdin") == "paged-frozen-snapshot-stdin":
        _validate_paged_read_coverage(
            decision["snapshot_read_coverage"], output_root, repository_root, manifest_path, payload
        )


def validate_receipt(receipt_path: Path, repository_root: Path, contract_path: Path, require_ready: bool = False) -> dict[str, Any]:
    _reject_symlink_components(receipt_path, "receipt")
    try:
        receipt_path.resolve().relative_to((repository_root.resolve() / "logs").resolve())
    except ValueError:
        pass
    else:
        raise ReceiptValidationError("receipt may not be stored under logs")
    receipt = read_json(receipt_path)
    if not isinstance(receipt, dict) or receipt.get("schema_version") != "skill-input-consumption.v1":
        raise ReceiptValidationError("receipt schema_version is invalid")
    required_receipt = {
        "schema_version", "consumer", "operation", "request_hash", "request_binding", "target", "route_identity",
        "repository_identity", "adapter_version", "created_at", "contract_hash", "source_manifest", "child_request",
        "sources", "missing_sources", "changed_sources", "semantic_decision", "context_artifact",
        "diagnostic_authorization", "authorizes", "binding_hash", "ready",
    }
    if set(receipt) != required_receipt:
        raise ReceiptValidationError("receipt fields do not match schema")
    if receipt.get("authorizes") != []:
        raise ReceiptValidationError("receipt authorizes must be empty")
    for key in ("request_hash", "contract_hash", "binding_hash"):
        _check_sha(receipt.get(key), f"receipt.{key}")
    if receipt["contract_hash"] != contract_hash(contract_path):
        raise ReceiptValidationError("contract hash mismatch")
    contract = read_json(contract_path)
    if not isinstance(contract, dict):
        raise ReceiptValidationError("contract must be an object")
    try:
        validate_contract(contract, repository_root)
    except SkillInputError as exc:
        raise ReceiptValidationError(str(exc)) from exc
    if receipt["consumer"] != contract["consumer"] or receipt["operation"] not in contract["operations"]:
        raise ReceiptValidationError("receipt consumer or operation is not declared by contract")
    if (
        not isinstance(receipt.get("target"), str)
        or not receipt["target"]
        or not isinstance(receipt.get("route_identity"), str)
        or not receipt["route_identity"]
        or receipt.get("adapter_version") != "skill-input-adapter.v1"
        or not isinstance(receipt.get("created_at"), str)
        or not receipt["created_at"]
    ):
        raise ReceiptValidationError("receipt route metadata is invalid")
    try:
        target_path, target_relative = contained_path(repository_root, receipt["target"], must_exist=False)
        validate_request_payload(receipt["route_identity"], path="route_identity")
    except SkillInputError as exc:
        raise ReceiptValidationError(str(exc)) from exc
    if target_relative != receipt["target"] or forbidden_repository_path(target_relative) or is_reparse_point(target_path):
        raise ReceiptValidationError("receipt target is forbidden")
    request_binding = receipt.get("request_binding")
    if not isinstance(request_binding, dict) or set(request_binding) != {"request", "consumer", "operation", "target", "route_identity", "source_roles"}:
        raise ReceiptValidationError("receipt request_binding is invalid")
    if (
        not isinstance(request_binding["request"], dict)
        or request_binding["consumer"] != receipt["consumer"]
        or request_binding["operation"] != receipt["operation"]
        or request_binding["target"] != receipt["target"]
        or request_binding["route_identity"] != receipt["route_identity"]
        or canonical_hash(request_binding) != receipt["request_hash"]
    ):
        raise ReceiptValidationError("receipt request binding is stale")
    try:
        validate_request_payload(request_binding["request"])
    except SkillInputError as exc:
        raise ReceiptValidationError(str(exc)) from exc
    role_values = request_binding["source_roles"]
    if (
        not isinstance(role_values, dict)
        or any(
            not isinstance(role_name, str)
            or role_name not in contract["source_roles"]
            or not isinstance(paths, list)
            or not paths
            or any(not isinstance(path, str) or not path for path in paths)
            or len(paths) != len(set(paths))
            for role_name, paths in role_values.items()
        )
    ):
        raise ReceiptValidationError("receipt source role binding is invalid")
    try:
        expected_expanded = expand_source_graph(repository_root, contract, receipt["operation"], role_values)
    except SkillInputError as exc:
        raise ReceiptValidationError(str(exc)) from exc
    expected_paths = {relative for _path, relative in expected_expanded}
    receipt_paths = [source.get("path") for source in receipt.get("sources", []) if isinstance(source, dict)]
    if not receipt_paths or len(receipt_paths) != len(set(receipt_paths)) or set(receipt_paths) != expected_paths:
        raise ReceiptValidationError("receipt sources do not match the declared source graph")
    identity = receipt.get("repository_identity")
    if not isinstance(identity, dict) or set(identity) != {"head", "index_hash", "scoped_worktree_hash"}:
        raise ReceiptValidationError("receipt repository identity is invalid")
    for key in ("index_hash", "scoped_worktree_hash"):
        _check_sha(identity.get(key), f"receipt.repository_identity.{key}")
    if not isinstance(identity.get("head"), str) or not identity["head"]:
        raise ReceiptValidationError("receipt repository identity head is invalid")
    try:
        current_identity = repository_identity(repository_root, expected_paths)
    except SkillInputError as exc:
        raise ReceiptValidationError(str(exc)) from exc
    # The source manifest binds every consumed file by content hash. HEAD is
    # provenance only, so unrelated commits cannot invalidate a frozen input.
    if any(identity[key] != current_identity[key] for key in ("index_hash", "scoped_worktree_hash")):
        raise ReceiptValidationError("receipt repository identity is stale")
    root = receipt_path.parent.resolve()
    manifest_path, _ = _artifact(root, receipt.get("source_manifest"), "source_manifest")
    if not manifest_path.is_file() or sha256_bytes(manifest_path.read_bytes()) != receipt["source_manifest"]["sha256"]:
        raise ReceiptValidationError("source manifest is missing or stale")
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "snapshot_kind", "consumer", "operation", "sources", "created_at"} or manifest.get("schema_version") != "skill-input-source-manifest.v1" or manifest.get("snapshot_kind") != "model-safe" or manifest.get("consumer") != receipt["consumer"] or manifest.get("operation") != receipt["operation"] or not isinstance(manifest.get("sources"), list) or not manifest["sources"]:
        raise ReceiptValidationError("source manifest is invalid")
    for manifest_source in manifest["sources"]:
        if not isinstance(manifest_source, dict) or set(manifest_source) != {"path", "sha256", "semantic_snapshot_sha256", "sensitivity", "redaction_status"}:
            raise ReceiptValidationError("source manifest entry is invalid")
    if len(receipt.get("sources", [])) != len(manifest["sources"]):
        raise ReceiptValidationError("receipt and source manifest source counts differ")
    source_statuses: dict[str, str] = {}
    manifest_by_path = {item.get("path"): item for item in manifest["sources"] if isinstance(item, dict)}
    if len(manifest_by_path) != len(manifest["sources"]):
        raise ReceiptValidationError("source manifest contains invalid or duplicate paths")
    for source in receipt["sources"]:
        source_required_fields = {
            "path", "required", "sha256_before", "sha256_after", "size_bytes", "line_count",
            "sensitivity", "semantic_snapshot_sha256", "redaction_status", "ranges_consumed",
            "transport_status", "semantic_status",
        }
        if not isinstance(source, dict) or set(source) != source_required_fields or not isinstance(source.get("path"), str):
            raise ReceiptValidationError("receipt source entry is invalid")
        manifest_source = manifest_by_path.get(source["path"])
        if not isinstance(manifest_source, dict):
            raise ReceiptValidationError(f"source missing from manifest: {source['path']}")
        _check_sha(source.get("sha256_before"), f"source {source.get('path')} sha256_before")
        _check_sha(source.get("sha256_after"), f"source {source.get('path')} sha256_after")
        source_path, relative = contained_path(repository_root, source["path"])
        if relative != source["path"] or forbidden_repository_path(relative):
            raise ReceiptValidationError(f"forbidden source path: {source['path']}")
        if type(source["required"]) is not bool or not isinstance(source["size_bytes"], int) or source["size_bytes"] < 0 or not isinstance(source["ranges_consumed"], list):
            raise ReceiptValidationError(f"receipt source metadata is invalid: {source['path']}")
        required = False
        for role_name in contract["operations"][receipt["operation"]]["required_inputs"]:
            for raw_root in role_values.get(role_name, []):
                required_root, _ = contained_path(repository_root, raw_root)
                if source_path == required_root or required_root.is_dir() and required_root in source_path.parents:
                    required = True
        if source["required"] != required:
            raise ReceiptValidationError(f"receipt source required flag is stale: {source['path']}")
        raw = source_path.read_bytes()
        digest = sha256_bytes(raw)
        if digest != source["sha256_before"] or digest != source["sha256_after"]:
            raise ReceiptValidationError(f"source hash drift: {source['path']}")
        safe, sensitivity, redaction = redact_bytes(raw)
        line_count, ranges = line_ranges(safe)
        if (
            source["size_bytes"] != len(raw)
            or source.get("line_count") != line_count
            or source["ranges_consumed"] != ranges
            or source.get("transport_status") != "complete"
            or source.get("semantic_status") not in {"accepted", "insufficient", "not-evaluated"}
        ):
            raise ReceiptValidationError(f"source transport coverage is incomplete: {source['path']}")
        if sha256_bytes(safe) != source["semantic_snapshot_sha256"] or sensitivity != source["sensitivity"] or redaction != source["redaction_status"]:
            raise ReceiptValidationError(f"source snapshot/redaction mismatch: {source['path']}")
        if (
            manifest_source.get("sha256") != source.get("sha256_after")
            or manifest_source.get("semantic_snapshot_sha256") != source.get("semantic_snapshot_sha256")
            or manifest_source.get("sensitivity") != source.get("sensitivity")
            or manifest_source.get("redaction_status") != source.get("redaction_status")
        ):
            raise ReceiptValidationError(f"source manifest mismatch: {source['path']}")
        source_statuses[source["path"]] = source.get("semantic_status", "not-evaluated")
    if not isinstance(receipt.get("missing_sources"), list) or not isinstance(receipt.get("changed_sources"), list):
        raise ReceiptValidationError("receipt missing or changed source fields are invalid")
    if receipt.get("missing_sources") or receipt.get("changed_sources"):
        raise ReceiptValidationError("receipt has missing or changed sources")
    decision_ref = receipt.get("semantic_decision")
    context_ref = receipt.get("context_artifact")
    ready = receipt.get("ready") is True
    if ready or require_ready:
        child_request_path, _ = _artifact(root, receipt.get("child_request"), "child_request")
        decision_path, _ = _artifact(root, decision_ref, "semantic_decision")
        context_path, _ = _artifact(root, context_ref, "context_artifact")
        if (
            not child_request_path.is_file()
            or not decision_path.is_file()
            or not context_path.is_file()
            or receipt["child_request"]["sha256"] == ZERO_HASH
            or decision_ref["sha256"] == ZERO_HASH
            or context_ref["sha256"] == ZERO_HASH
        ):
            raise ReceiptValidationError("ready receipt requires child request, decision, and context sidecars")
        child_request = read_json(child_request_path)
        decision = read_json(decision_path)
        context = read_json(context_path)
        if (
            sha256_bytes(child_request_path.read_bytes()) != receipt["child_request"]["sha256"]
            or sha256_bytes(decision_path.read_bytes()) != decision_ref["sha256"]
            or sha256_bytes(context_path.read_bytes()) != context_ref["sha256"]
        ):
            raise ReceiptValidationError("sidecar hash mismatch")
        _validate_context(
            context,
            receipt["source_manifest"]["sha256"],
            max_context_bytes=contract["max_context_bytes"],
            serialized_size=len(context_path.read_bytes()),
        )
        _validate_decision(decision, receipt["source_manifest"]["sha256"], context_ref["sha256"], source_statuses)
        _validate_child_request_binding(
            child_request,
            receipt,
            contract,
            repository_root,
            manifest_path,
            context_path,
            decision_path,
            decision,
        )
        credential_sources = any(
            source.get("sensitivity") == "credential-bearing" for source in receipt["sources"]
        )
        if (
            decision["status"] != "accepted"
            or decision["redaction_status"] == "failed"
            or credential_sources and decision["redaction_status"] != "complete"
            or context["truncated"]
            or any(status != "accepted" for status in source_statuses.values())
        ):
            raise ReceiptValidationError("ready receipt has insufficient semantic input")
    diagnostic = receipt.get("diagnostic_authorization")
    if diagnostic is not None:
        if not isinstance(diagnostic, dict) or set(diagnostic) != {"authority_path", "authority_sha256", "scope", "target", "issuer", "expires_at"}:
            raise ReceiptValidationError("diagnostic authorization is invalid")
        authority_path, _ = _artifact(root, {"path": diagnostic["authority_path"], "sha256": diagnostic["authority_sha256"]}, "diagnostic authority")
        if not authority_path.is_file() or sha256_bytes(authority_path.read_bytes()) != diagnostic["authority_sha256"]:
            raise ReceiptValidationError("diagnostic authority is missing or stale")
        if diagnostic["target"] != receipt["target"] or not all(isinstance(diagnostic[key], str) and diagnostic[key] for key in ("scope", "issuer", "expires_at")):
            raise ReceiptValidationError("diagnostic authorization scope is invalid")
        try:
            expires = datetime.fromisoformat(diagnostic["expires_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ReceiptValidationError("diagnostic authorization expiry is invalid") from exc
        if expires.tzinfo is None or expires.astimezone(timezone.utc) <= datetime.now(timezone.utc):
            raise ReceiptValidationError("diagnostic authorization is expired")
    binding = dict(receipt)
    binding.pop("binding_hash", None)
    if canonical_hash(binding) != receipt["binding_hash"]:
        raise ReceiptValidationError("binding hash mismatch")
    if require_ready and not ready:
        raise ReceiptValidationError("receipt is not ready")
    return {"status": "ready" if ready else "candidate", "receipt": receipt_path.as_posix()}


def publish_ready(
    receipt_path: Path,
    child_request: Path,
    semantic_decision: Path,
    context_artifact: Path,
    repository_root: Path,
    contract_path: Path,
) -> None:
    """Bind validated child sidecars and publish the receipt's ready gate."""
    previous_receipt_bytes = receipt_path.read_bytes()
    receipt = read_json(receipt_path)
    if not isinstance(receipt, dict) or receipt.get("ready") is True:
        raise ReceiptValidationError("only a candidate receipt may be published")
    root = receipt_path.parent.resolve()
    try:
        child_request_relative = child_request.resolve().relative_to(root).as_posix()
        decision_relative = semantic_decision.resolve().relative_to(root).as_posix()
        context_relative = context_artifact.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ReceiptValidationError("sidecars must be inside the receipt root") from exc
    child_request_path, _ = _artifact(
        root,
        {"path": child_request_relative, "sha256": sha256_bytes(child_request.read_bytes())},
        "child_request",
    )
    decision_path, _ = _artifact(root, {"path": decision_relative, "sha256": sha256_bytes(semantic_decision.read_bytes())}, "semantic_decision")
    context_path, _ = _artifact(root, {"path": context_relative, "sha256": sha256_bytes(context_artifact.read_bytes())}, "context_artifact")
    decision_payload = read_json(decision_path)
    if isinstance(decision_payload, dict) and isinstance(decision_payload.get("source_statuses"), dict):
        for source in receipt.get("sources", []):
            if source.get("path") in decision_payload["source_statuses"]:
                source["semantic_status"] = decision_payload["source_statuses"][source["path"]]
    receipt["semantic_decision"] = {"path": decision_relative, "sha256": sha256_bytes(decision_path.read_bytes())}
    receipt["context_artifact"] = {"path": context_relative, "sha256": sha256_bytes(context_path.read_bytes())}
    receipt["child_request"] = {"path": child_request_relative, "sha256": sha256_bytes(child_request_path.read_bytes())}
    receipt["ready"] = True
    receipt["binding_hash"] = canonical_hash({key: value for key, value in receipt.items() if key != "binding_hash"})
    proposed_path = receipt_path.with_name(f"{receipt_path.name}.{uuid.uuid4().hex}.proposed")
    try:
        write_json_atomic(proposed_path, receipt)
        validate_receipt(proposed_path, repository_root.resolve(), contract_path.resolve(), require_ready=True)
    finally:
        try:
            proposed_path.unlink()
        except FileNotFoundError:
            pass
    manifest_path, _ = _artifact(root, receipt["source_manifest"], "source_manifest")
    removed_payload = _remove_model_snapshot_payload(root, manifest_path, receipt.get("sources", []))
    try:
        write_json_atomic(receipt_path, receipt, expected_bytes=previous_receipt_bytes)
    except Exception:
        _restore_model_snapshot_payload(removed_payload)
        raise


def _remove_model_snapshot_payload(root: Path, manifest_path: Path, sources: list[Any]) -> list[tuple[Path, bytes]]:
    """Remove copied source bytes with an in-memory rollback image."""
    snapshot_root = manifest_path.parent.resolve()
    if snapshot_root == root or is_reparse_point(manifest_path) or not snapshot_root.is_dir():
        return []
    payload: list[tuple[Path, bytes]] = []
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("path"), str):
            continue
        candidate = snapshot_root / source["path"]
        _reject_symlink_components(candidate, "snapshot payload", stop=snapshot_root)
        try:
            candidate.resolve().relative_to(snapshot_root)
        except ValueError:
            raise ReceiptValidationError("snapshot payload escapes snapshot root")
        if candidate.is_file() and not is_reparse_point(candidate):
            payload.append((candidate, candidate.read_bytes()))
    try:
        for candidate, _content in payload:
            candidate.unlink()
    except Exception:
        _restore_model_snapshot_payload(payload)
        raise
    for directory in sorted((item for item in snapshot_root.rglob("*") if item.is_dir()), key=lambda item: len(item.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass
    return payload


def _restore_model_snapshot_payload(payload: list[tuple[Path, bytes]]) -> None:
    """Restore removed payload bytes after cleanup or ready CAS failure."""
    for target, content in payload:
        target.parent.mkdir(parents=True, exist_ok=True)
        write_bytes_atomic(target, content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--publish-ready", action="store_true")
    parser.add_argument("--child-request", type=Path)
    parser.add_argument("--semantic-decision", type=Path)
    parser.add_argument("--context-artifact", type=Path)
    args = parser.parse_args()
    try:
        if args.publish_ready:
            if not args.child_request or not args.semantic_decision or not args.context_artifact:
                raise ReceiptValidationError("--publish-ready requires --child-request, --semantic-decision, and --context-artifact")
            publish_ready(
                args.receipt.resolve(),
                args.child_request.resolve(),
                args.semantic_decision.resolve(),
                args.context_artifact.resolve(),
                args.repository_root.resolve(),
                args.contract.resolve(),
            )
        result = validate_receipt(args.receipt.resolve(), args.repository_root.resolve(), args.contract.resolve(), args.require_ready)
    except (OSError, SkillInputError, ReceiptValidationError) as exc:
        print(f"skill input receipt validation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
