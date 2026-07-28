"""Phase-aware static and security scan bundle execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from acceptance_core import InputError, canonical_hash, phase_changed_paths, validate_candidate_manifest
from execution_control import ControlError, run_controlled_command, validate_command_descriptor


_KINDS = {"static-analysis", "security-scan"}


def _phase_changed_paths(candidate_manifest: Any, baseline_manifest: Any) -> list[str]:
    validate_candidate_manifest(candidate_manifest, baseline_manifest)
    paths = phase_changed_paths(candidate_manifest)
    if not paths:
        raise InputError("Phase scan was requested without Phase changed paths")
    return paths


def _descriptor(registry: Any, command_id: str) -> dict[str, Any]:
    commands = registry.get("commands") if isinstance(registry, dict) else None
    if not isinstance(commands, list):
        raise InputError("scan command registry is invalid")
    matches = [item for item in commands if isinstance(item, dict) and item.get("id") == command_id]
    if len(matches) != 1:
        raise InputError("scan command must resolve uniquely")
    command = matches[0]
    try:
        validate_command_descriptor(command)
    except ControlError as exc:
        raise InputError("scan command must use the controlled descriptor contract") from exc
    return command


def run_phase_scan(
    *, repository_root: Path, kind: str, execution_mode: str, baseline_manifest: Any, candidate_manifest: Any,
    command_registry: Any, command_id: str,
) -> dict[str, Any]:
    if kind not in _KINDS:
        raise InputError("scan kind is invalid")
    if execution_mode != "controlled_validation":
        raise InputError("Phase scan execution requires controlled_validation")
    root = repository_root.resolve()
    if not root.is_dir():
        raise InputError("repository root is invalid")
    required_paths = _phase_changed_paths(candidate_manifest, baseline_manifest)
    command = _descriptor(command_registry, command_id)
    try:
        controlled = run_controlled_command(root, command)
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
        "commandRegistryHash": canonical_hash(command_registry),
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
