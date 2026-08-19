#!/usr/bin/env python
"""Prepare a hash-bound Skill input snapshot and non-authorizing receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from skill_input_consumption import (
    SkillInputError,
    canonical_hash,
    contained_path,
    contract_hash,
    declared_missing_plan_files,
    expand_source_graph,
    line_ranges,
    now_utc,
    redact_bytes,
    read_json,
    repository_identity,
    sha256_bytes,
    artifact_identity_hash,
    validate_contract,
    validate_request_payload,
    forbidden_repository_path,
    is_reparse_point,
    write_bytes_atomic,
    write_json_atomic,
    generated_artifact_exclusions,
)


ZERO_HASH = "sha256:" + "0" * 64


def _reject_symlink_components(path: Path, *, stop: Path | None = None) -> None:
    current = path.absolute()
    boundary = stop.absolute() if stop is not None else None
    while True:
        if is_reparse_point(current):
            raise SkillInputError(f"artifact path may not contain a symlink: {path}")
        if boundary is not None and current == boundary:
            return
        if current.parent == current:
            return
        current = current.parent


def _directory_membership(
    repository_root: Path,
    directory: Path,
    *,
    excluded_paths: frozenset[str] = frozenset(),
) -> tuple[tuple[str, str], ...]:
    members: list[tuple[str, str]] = []
    for item in directory.rglob("*"):
        if is_reparse_point(item):
            raise SkillInputError(f"symlink source is not allowed: {item}")
        if not item.is_file() and not item.is_dir():
            continue
        relative = item.resolve().relative_to(repository_root.resolve()).as_posix()
        if relative in excluded_paths or any(
            relative.startswith(prefix + "/") for prefix in excluded_paths
        ):
            continue
        members.append((relative, "file" if item.is_file() else "directory"))
    return tuple(sorted(members))


def _parse_role(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise SkillInputError("--source-role must be role=repository-relative-path")
    role, path = value.split("=", 1)
    if not role or not path:
        raise SkillInputError("--source-role contains an empty role or path")
    return role, path


def _relative_artifact(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise SkillInputError("artifact must be inside the receipt root") from exc


def _role_root_allowed(repository_root: Path, role: dict[str, Any], raw_path: str) -> None:
    root_name = role.get("root")
    if root_name == "repository":
        return
    _, relative = contained_path(repository_root, raw_path)
    if not (relative == root_name or relative.startswith(str(root_name).rstrip("/") + "/")):
        raise SkillInputError(f"source does not satisfy role root: {raw_path}")


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    repository_root = args.repository_root.resolve()
    contract_path = args.contract.resolve()
    contract = read_json(contract_path)
    if not isinstance(contract, dict):
        raise SkillInputError("contract must be a JSON object")
    validate_contract(contract, repository_root)
    if args.operation not in contract["operations"]:
        raise SkillInputError("operation is not declared by contract")
    if args.consumer != contract["consumer"]:
        raise SkillInputError("consumer does not match contract")
    if not isinstance(args.route_identity, str) or not args.route_identity:
        raise SkillInputError("route identity is invalid")
    validate_request_payload(args.route_identity, path="route_identity")
    request = read_json(args.request_json) if args.request_json else {}
    if not isinstance(request, dict):
        raise SkillInputError("request JSON must be an object")
    validate_request_payload(request)

    role_values: dict[str, list[str]] = {}
    for raw in args.source_role:
        role, path = _parse_role(raw)
        role_values.setdefault(role, []).append(path)
    operation = contract["operations"][args.operation]
    required_roles = operation.get("required_inputs", [])
    for role_name in required_roles:
        if role_name not in role_values:
            raise SkillInputError(f"required source role is missing: {role_name}")
        if role_name not in contract["source_roles"]:
            raise SkillInputError(f"source role is undeclared: {role_name}")
    for role_name, paths in role_values.items():
        role = contract["source_roles"].get(role_name)
        if not isinstance(role, dict):
            raise SkillInputError(f"source role is undeclared: {role_name}")
        for path in paths:
            _role_root_allowed(repository_root, role, path)

    target_path, target_relative = contained_path(repository_root, args.target, must_exist=False)
    if forbidden_repository_path(target_relative):
        raise SkillInputError("target may not be under logs")
    _reject_symlink_components(args.receipt)
    receipt_path = args.receipt.resolve()
    receipt_root = receipt_path.parent
    _reject_symlink_components(args.snapshot_root)
    snapshot_root = args.snapshot_root.resolve()
    logs_root = (repository_root / "logs").resolve()
    try:
        receipt_root.relative_to(logs_root)
    except ValueError:
        pass
    else:
        raise SkillInputError("receipt may not be stored under logs")
    try:
        snapshot_root.relative_to(logs_root)
    except ValueError:
        pass
    else:
        raise SkillInputError("snapshot may not be stored under logs")
    if snapshot_root.exists() and is_reparse_point(snapshot_root):
        raise SkillInputError("snapshot root may not be a symlink")
    snapshot_root.mkdir(parents=True, exist_ok=True)
    try:
        snapshot_relative = snapshot_root.relative_to(repository_root).as_posix()
    except ValueError as exc:
        raise SkillInputError("snapshot root must stay inside the repository") from exc
    excluded_snapshot_paths = frozenset({snapshot_relative}) | generated_artifact_exclusions(repository_root, target_path)

    normalized_role_values: dict[str, list[str]] = {}
    directory_memberships: dict[str, tuple[Path, tuple[tuple[str, str], ...]]] = {}
    for role_name, paths in role_values.items():
        normalized_role_values[role_name] = []
        for path in paths:
            resolved_source, relative_source = contained_path(repository_root, path)
            normalized_role_values[role_name].append(relative_source)
            if resolved_source.is_dir() and relative_source not in directory_memberships:
                directory_memberships[relative_source] = (
                    resolved_source,
                    _directory_membership(
                        repository_root,
                        resolved_source,
                        excluded_paths=excluded_snapshot_paths,
                    ),
                )
        if len(normalized_role_values[role_name]) != len(set(normalized_role_values[role_name])):
            raise SkillInputError(f"source role contains duplicate canonical paths: {role_name}")
    allowed_missing = declared_missing_plan_files(repository_root, target_path)
    expanded = expand_source_graph(
        repository_root,
        contract,
        args.operation,
        normalized_role_values,
        allowed_missing,
        excluded_snapshot_paths,
    )
    required_roots: list[Path] = []
    required_role_names = set(required_roles)
    for role_name in required_role_names:
        for raw in role_values.get(role_name, []):
            required_root, _ = contained_path(repository_root, raw)
            required_roots.append(required_root)
    identity = repository_identity(repository_root, [relative for _, relative in expanded])
    source_entries: list[dict[str, Any]] = []
    manifest_entries: list[dict[str, Any]] = []
    changed_sources: list[str] = []
    for source, relative in expanded:
        if relative.casefold() == "source-manifest.v1.json":
            raise SkillInputError("source path is reserved for the protocol manifest")
        before = source.read_bytes()
        after = source.read_bytes()
        source_hash_before = sha256_bytes(before)
        source_hash_after = sha256_bytes(after)
        transport_status = "complete" if before == after else "changed"
        if transport_status == "changed":
            changed_sources.append(relative)
            safe_bytes, sensitivity, redaction_status = b"", "normal", "failed"
            semantic_hash = sha256_bytes(safe_bytes)
            line_count, ranges = 0, []
        else:
            try:
                safe_bytes, sensitivity, redaction_status = redact_bytes(before)
                line_count, ranges = line_ranges(safe_bytes)
                semantic_hash = sha256_bytes(safe_bytes)
            except SkillInputError:
                transport_status = "failed"
                safe_bytes, sensitivity, redaction_status = b"", "restricted", "failed"
                semantic_hash = sha256_bytes(safe_bytes)
                line_count, ranges = 0, []
        if transport_status == "complete":
            destination = snapshot_root / relative
            _reject_symlink_components(destination, stop=snapshot_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            write_bytes_atomic(destination, safe_bytes)
        entry = {
            "path": relative,
            "required": any(source == required_root or required_root.is_dir() and required_root in source.parents for required_root in required_roots),
            "sha256_before": source_hash_before,
            "sha256_after": source_hash_after,
            "size_bytes": len(before),
            "line_count": line_count,
            "sensitivity": sensitivity,
            "semantic_snapshot_sha256": semantic_hash,
            "redaction_status": redaction_status,
            "ranges_consumed": ranges,
            "transport_status": transport_status,
            "semantic_status": "not-evaluated",
        }
        source_entries.append(entry)
        manifest_entries.append({
            "path": relative,
            "sha256": source_hash_after,
            "semantic_snapshot_sha256": semantic_hash,
            "sensitivity": sensitivity,
            "redaction_status": redaction_status,
        })

    for relative_root, (directory, before_membership) in directory_memberships.items():
        if (
            _directory_membership(
                repository_root,
                directory,
                excluded_paths=excluded_snapshot_paths,
            )
            != before_membership
        ):
            raise SkillInputError(f"directory source membership changed: {relative_root}")

    manifest = {
        "schema_version": "skill-input-source-manifest.v1",
        "snapshot_kind": "model-safe",
        "consumer": args.consumer,
        "operation": args.operation,
        "sources": manifest_entries,
        "created_at": now_utc(),
    }
    manifest_path = snapshot_root / "source-manifest.v1.json"
    write_json_atomic(manifest_path, manifest)
    manifest_hash = artifact_identity_hash(manifest_path)
    request_binding = {
        "request": request,
        "consumer": args.consumer,
        "operation": args.operation,
        "target": target_relative,
        "route_identity": args.route_identity,
        "source_roles": normalized_role_values,
    }
    request_hash = canonical_hash(request_binding)
    root_relative = _relative_artifact(manifest_path, receipt_root)
    receipt = {
        "schema_version": "skill-input-consumption.v1",
        "consumer": args.consumer,
        "operation": args.operation,
        "request_binding": request_binding,
        "request_hash": request_hash,
        "target": target_relative,
        "route_identity": args.route_identity,
        "repository_identity": identity,
        "adapter_version": "skill-input-adapter.v1",
        "created_at": now_utc(),
        "contract_hash": contract_hash(contract_path),
        "source_manifest": {"path": root_relative, "sha256": manifest_hash},
        "child_request": {"path": "pending/skill-input-child-request.v1.json", "sha256": ZERO_HASH},
        "sources": source_entries,
        "missing_sources": [],
        "changed_sources": changed_sources,
        "semantic_decision": {"path": "pending/semantic-decision.v1.json", "sha256": ZERO_HASH, "status": "insufficient"},
        "context_artifact": {"path": "pending/skill-input-context.v1.json", "sha256": ZERO_HASH},
        "diagnostic_authorization": None,
        "authorizes": [],
        "ready": False,
    }
    receipt["binding_hash"] = canonical_hash(receipt)
    write_json_atomic(receipt_path, receipt)
    return {"status": "candidate", "ready": False, "receipt": receipt_path.as_posix(), "source_manifest": manifest_path.as_posix()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--consumer", required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--route-identity", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--source-role", action="append", default=[])
    parser.add_argument("--request-json", type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args)
    except (OSError, SkillInputError) as exc:
        print(f"skill input preparation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
