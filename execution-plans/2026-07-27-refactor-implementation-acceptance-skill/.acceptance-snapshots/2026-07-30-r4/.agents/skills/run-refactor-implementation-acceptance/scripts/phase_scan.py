"""Phase-aware static and security scan bundle execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from acceptance_core import InputError, canonical_hash, phase_changed_paths, validate_candidate_manifest
from execution_control import ControlError, resolve_registered_command, run_controlled_command


_KINDS = {"static-analysis", "security-scan"}


def _phase_changed_paths(candidate_manifest: Any, baseline_manifest: Any) -> list[str]:
    validate_candidate_manifest(candidate_manifest, baseline_manifest)
    paths = phase_changed_paths(candidate_manifest)
    if not paths:
        raise InputError("Phase scan was requested without Phase changed paths")
    return paths


def _descriptor(registry: Any, command_id: str) -> dict[str, Any]:
    try:
        return resolve_registered_command(registry, command_id)
    except ControlError as exc:
        raise InputError("scan command registry is not hash-bound") from exc


def _verify_frozen_snapshot(snapshot_root: Path, candidate_manifest: dict[str, Any]) -> None:
    """Bind every candidate byte used by a scan to the custody snapshot."""
    if not snapshot_root.is_dir() or snapshot_root.is_symlink():
        raise InputError("candidate snapshot root is invalid")
    for item in candidate_manifest["files"]:
        candidate_path, expected = item.get("candidate_path"), item.get("candidate_sha256")
        if candidate_path is None:
            continue
        path = (snapshot_root / candidate_path).resolve()
        try:
            path.relative_to(snapshot_root.resolve())
        except ValueError as exc:
            raise InputError("candidate snapshot path escapes root") from exc
        if not path.is_file() or path.is_symlink():
            raise InputError("candidate snapshot is incomplete")
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise InputError("candidate snapshot bytes drift from manifest")


def run_phase_scan(
    *, repository_root: Path, kind: str, execution_mode: str, baseline_manifest: Any, candidate_manifest: Any,
    command_registry: Any, command_id: str, candidate_snapshot_root: Path,
) -> dict[str, Any]:
    if kind not in _KINDS:
        raise InputError("scan kind is invalid")
    if execution_mode != "controlled_validation":
        raise InputError("Phase scan execution requires controlled_validation")
    root = repository_root.resolve()
    if not root.is_dir():
        raise InputError("repository root is invalid")
    required_paths = _phase_changed_paths(candidate_manifest, baseline_manifest)
    snapshot = candidate_snapshot_root.resolve()
    try:
        snapshot.relative_to(root)
    except ValueError as exc:
        raise InputError("candidate snapshot must be contained by repository root") from exc
    _verify_frozen_snapshot(snapshot, candidate_manifest)
    command = _descriptor(command_registry, command_id)
    try:
        controlled = run_controlled_command(snapshot, command)
    except ControlError as exc:
        raise InputError("controlled Phase scan command failed validation") from exc
    process = controlled["processResult"]
    stdout, exit_code = process.get("stdout", "").encode("utf-8"), controlled["exitCode"]
    receipt = {
        "commandId": command_id, "exitCode": exit_code,
        "stdoutSha256": "sha256:" + hashlib.sha256(stdout).hexdigest(),
        "stderrSha256": process.get("stderrSha256"),
    }
    base = {
        "schemaVersion": "phase-scan-bundle-result.v1",
        "bundleId": "phase-static-analysis" if kind == "static-analysis" else "phase-security-scan",
        "candidateContentManifestHash": canonical_hash(candidate_manifest),
        "commandRegistryHash": command_registry["registryHash"],
        "commandId": command_id,
        "toolHash": canonical_hash(command),
        "requiredChangedPaths": required_paths,
        "processResult": receipt,
        "processResultHash": canonical_hash(receipt),
        "authorizes": [],
    }
    try:
        payload = json.loads(stdout.decode("utf-8")) if exit_code == 0 else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    read_paths = payload.get("readPaths") if isinstance(payload, dict) else []
    findings = payload.get("findings") if isinstance(payload, dict) else []
    if not isinstance(read_paths, list) or any(not isinstance(path, str) for path in read_paths):
        read_paths = []
    if not isinstance(findings, list):
        findings = []
    missing = sorted(set(required_paths) - set(read_paths))
    status = "passed" if exit_code == 0 and isinstance(payload, dict) and payload.get("status") == "passed" and sorted(read_paths) == required_paths else "incomplete"
    return {
        **base, "status": status, "readChangedPaths": sorted(read_paths),
        "missingChangedPaths": missing, "findings": findings,
    }
