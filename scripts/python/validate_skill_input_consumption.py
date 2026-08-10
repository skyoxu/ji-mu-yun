#!/usr/bin/env python
"""Validate a Skill input receipt and its hash-bound sidecars."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from skill_input_consumption import (
    SkillInputError,
    canonical_hash,
    contained_path,
    contract_hash,
    read_json,
    redact_bytes,
    sha256_bytes,
    validate_contract,
    write_json_atomic,
)


ZERO_HASH = "sha256:" + "0" * 64
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ReceiptValidationError(ValueError):
    pass


def _artifact(root: Path, value: Any, label: str) -> tuple[Path, str]:
    if not isinstance(value, dict) or not isinstance(value.get("path"), str) or not isinstance(value.get("sha256"), str):
        raise ReceiptValidationError(f"{label} must contain path and sha256")
    if not SHA256_RE.fullmatch(value["sha256"]):
        raise ReceiptValidationError(f"{label}.sha256 is invalid")
    raw = Path(value["path"])
    if raw.is_absolute():
        raise ReceiptValidationError(f"{label}.path must be relative")
    resolved = (root / raw).resolve()
    try:
        rel = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ReceiptValidationError(f"{label}.path escapes receipt root") from exc
    if rel.startswith("logs/") or resolved.is_symlink():
        raise ReceiptValidationError(f"{label}.path is forbidden")
    return resolved, rel


def _check_sha(value: Any, label: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ReceiptValidationError(f"{label} is not sha256:<64 lowercase hex>")


def _validate_context(payload: Any, manifest_hash: str) -> None:
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


def _validate_decision(payload: Any, manifest_hash: str, context_hash: str, source_statuses: dict[str, str]) -> None:
    if not isinstance(payload, dict):
        raise ReceiptValidationError("semantic decision must be an object")
    required = {"schema_version", "producer_role", "execution_identity", "source_manifest_hash", "context_artifact_hash", "source_statuses", "status", "rationale", "redaction_status", "redaction_profile_hash", "authorizes"}
    if set(payload) != required:
        raise ReceiptValidationError("semantic decision fields do not match schema")
    if payload["schema_version"] != "skill-semantic-decision.v1" or payload["source_manifest_hash"] != manifest_hash or payload["context_artifact_hash"] != context_hash:
        raise ReceiptValidationError("semantic decision binding is invalid")
    _check_sha(payload["execution_identity"], "semantic decision execution_identity")
    _check_sha(payload["redaction_profile_hash"], "semantic decision redaction_profile_hash")
    if payload["status"] not in {"accepted", "insufficient"} or not isinstance(payload["rationale"], str) or len(payload["rationale"].encode("utf-8")) > 2000:
        raise ReceiptValidationError("semantic decision status or rationale is invalid")
    if payload["authorizes"] != [] or not isinstance(payload["source_statuses"], dict):
        raise ReceiptValidationError("semantic decision must not authorize actions")
    if payload["source_statuses"] != source_statuses:
        raise ReceiptValidationError("semantic decision source statuses do not match receipt")
    if payload["redaction_status"] not in {"not-required", "complete", "failed"}:
        raise ReceiptValidationError("semantic decision redaction status is invalid")


def validate_receipt(receipt_path: Path, repository_root: Path, contract_path: Path, require_ready: bool = False) -> dict[str, Any]:
    receipt = read_json(receipt_path)
    if not isinstance(receipt, dict) or receipt.get("schema_version") != "skill-input-consumption.v1":
        raise ReceiptValidationError("receipt schema_version is invalid")
    required_receipt = {
        "schema_version", "consumer", "operation", "request_hash", "target", "route_identity",
        "repository_identity", "adapter_version", "created_at", "contract_hash", "source_manifest",
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
    root = receipt_path.parent.resolve()
    manifest_path, _ = _artifact(root, receipt.get("source_manifest"), "source_manifest")
    if not manifest_path.is_file() or sha256_bytes(manifest_path.read_bytes()) != receipt["source_manifest"]["sha256"]:
        raise ReceiptValidationError("source manifest is missing or stale")
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "skill-input-source-manifest.v1" or manifest.get("snapshot_kind") != "model-safe" or not isinstance(manifest.get("sources"), list):
        raise ReceiptValidationError("source manifest is invalid")
    if len(receipt.get("sources", [])) != len(manifest["sources"]):
        raise ReceiptValidationError("receipt and source manifest source counts differ")
    source_statuses: dict[str, str] = {}
    manifest_by_path = {item.get("path"): item for item in manifest["sources"] if isinstance(item, dict)}
    if len(manifest_by_path) != len(manifest["sources"]):
        raise ReceiptValidationError("source manifest contains invalid or duplicate paths")
    for source in receipt["sources"]:
        if not isinstance(source, dict) or not isinstance(source.get("path"), str):
            raise ReceiptValidationError("receipt source entry is invalid")
        manifest_source = manifest_by_path.get(source["path"])
        if not isinstance(manifest_source, dict):
            raise ReceiptValidationError(f"source missing from manifest: {source['path']}")
        _check_sha(source.get("sha256_before"), f"source {source.get('path')} sha256_before")
        _check_sha(source.get("sha256_after"), f"source {source.get('path')} sha256_after")
        source_path, relative = contained_path(repository_root, source["path"])
        if relative != source["path"] or relative.startswith("logs/") or relative.startswith(".git/"):
            raise ReceiptValidationError(f"forbidden source path: {source['path']}")
        raw = source_path.read_bytes()
        digest = sha256_bytes(raw)
        if digest != source["sha256_before"] or digest != source["sha256_after"]:
            raise ReceiptValidationError(f"source hash drift: {source['path']}")
        safe, sensitivity, redaction = redact_bytes(raw)
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
    if receipt.get("missing_sources") or receipt.get("changed_sources"):
        raise ReceiptValidationError("receipt has missing or changed sources")
    decision_ref = receipt.get("semantic_decision")
    context_ref = receipt.get("context_artifact")
    ready = receipt.get("ready") is True
    if ready or require_ready:
        decision_path, _ = _artifact(root, decision_ref, "semantic_decision")
        context_path, _ = _artifact(root, context_ref, "context_artifact")
        if not decision_path.is_file() or not context_path.is_file() or decision_ref["sha256"] == ZERO_HASH or context_ref["sha256"] == ZERO_HASH:
            raise ReceiptValidationError("ready receipt requires decision and context sidecars")
        decision = read_json(decision_path)
        context = read_json(context_path)
        if sha256_bytes(decision_path.read_bytes()) != decision_ref["sha256"] or sha256_bytes(context_path.read_bytes()) != context_ref["sha256"]:
            raise ReceiptValidationError("sidecar hash mismatch")
        _validate_context(context, receipt["source_manifest"]["sha256"])
        _validate_decision(decision, receipt["source_manifest"]["sha256"], context_ref["sha256"], source_statuses)
        if decision["status"] != "accepted" or context["truncated"] or any(status != "accepted" for status in source_statuses.values()):
            raise ReceiptValidationError("ready receipt has insufficient semantic input")
    binding = dict(receipt)
    binding.pop("binding_hash", None)
    if canonical_hash(binding) != receipt["binding_hash"]:
        raise ReceiptValidationError("binding hash mismatch")
    if require_ready and not ready:
        raise ReceiptValidationError("receipt is not ready")
    return {"status": "ready" if ready else "candidate", "receipt": receipt_path.as_posix()}


def publish_ready(receipt_path: Path, semantic_decision: Path, context_artifact: Path) -> None:
    """Bind validated child sidecars and publish the receipt's ready gate."""
    receipt = read_json(receipt_path)
    if not isinstance(receipt, dict) or receipt.get("ready") is True:
        raise ReceiptValidationError("only a candidate receipt may be published")
    root = receipt_path.parent.resolve()
    try:
        decision_relative = semantic_decision.resolve().relative_to(root).as_posix()
        context_relative = context_artifact.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ReceiptValidationError("sidecars must be inside the receipt root") from exc
    decision_path, _ = _artifact(root, {"path": decision_relative, "sha256": sha256_bytes(semantic_decision.read_bytes())}, "semantic_decision")
    context_path, _ = _artifact(root, {"path": context_relative, "sha256": sha256_bytes(context_artifact.read_bytes())}, "context_artifact")
    decision_payload = read_json(decision_path)
    if isinstance(decision_payload, dict) and isinstance(decision_payload.get("source_statuses"), dict):
        for source in receipt.get("sources", []):
            if source.get("path") in decision_payload["source_statuses"]:
                source["semantic_status"] = decision_payload["source_statuses"][source["path"]]
    receipt["semantic_decision"] = {"path": decision_relative, "sha256": sha256_bytes(decision_path.read_bytes())}
    receipt["context_artifact"] = {"path": context_relative, "sha256": sha256_bytes(context_path.read_bytes())}
    receipt["ready"] = True
    receipt["binding_hash"] = canonical_hash({key: value for key, value in receipt.items() if key != "binding_hash"})
    write_json_atomic(receipt_path, receipt)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--publish-ready", action="store_true")
    parser.add_argument("--semantic-decision", type=Path)
    parser.add_argument("--context-artifact", type=Path)
    args = parser.parse_args()
    try:
        if args.publish_ready:
            if not args.semantic_decision or not args.context_artifact:
                raise ReceiptValidationError("--publish-ready requires --semantic-decision and --context-artifact")
            publish_ready(args.receipt.resolve(), args.semantic_decision.resolve(), args.context_artifact.resolve())
        result = validate_receipt(args.receipt.resolve(), args.repository_root.resolve(), args.contract.resolve(), args.require_ready)
    except (OSError, SkillInputError, ReceiptValidationError) as exc:
        print(f"skill input receipt validation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
