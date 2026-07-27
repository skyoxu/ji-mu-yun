"""Phase-aware static and security scan bundle execution."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from acceptance_core import InputError, canonical_hash, validate_candidate_manifest


_KINDS = {"static-analysis", "security-scan"}


def _phase_changed_paths(candidate_manifest: Any) -> list[str]:
    baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
    validate_candidate_manifest(candidate_manifest, baseline)
    paths = {
        item["candidate_path"]
        for item in candidate_manifest["files"]
        if item.get("change_type") != "unchanged"
        and isinstance(item.get("candidate_path"), str)
        and (
            item["candidate_path"].startswith("PhaseA.Platform/")
            or item["candidate_path"].startswith("PhaseA.Platform.Tests/")
            or item["candidate_path"].startswith("runtime/phase-a/")
            or item["candidate_path"].startswith("scripts/python/phase_a_")
            or item["candidate_path"].startswith("scripts/python/phase_b_")
        )
    }
    if not paths:
        raise InputError("Phase scan was requested without Phase changed paths")
    return sorted(paths)


def _descriptor(registry: Any, command_id: str) -> dict[str, Any]:
    commands = registry.get("commands") if isinstance(registry, dict) else None
    if not isinstance(commands, list):
        raise InputError("scan command registry is invalid")
    matches = [item for item in commands if isinstance(item, dict) and item.get("id") == command_id]
    if len(matches) != 1:
        raise InputError("scan command must resolve uniquely")
    command = matches[0]
    required = {"id", "executable", "argv", "cwd", "timeout_seconds", "shell"}
    if set(command) != required or command.get("shell") is not False or command.get("cwd") != ".":
        raise InputError("scan command must be shell-free and repository-rooted")
    if not isinstance(command.get("executable"), str) or not command["executable"] or not isinstance(command.get("argv"), list) or any(not isinstance(value, str) for value in command["argv"]):
        raise InputError("scan command invocation is invalid")
    if not isinstance(command.get("timeout_seconds"), int) or command["timeout_seconds"] <= 0:
        raise InputError("scan command timeout is invalid")
    return command


def run_phase_scan(
    *, repository_root: Path, kind: str, execution_mode: str, candidate_manifest: Any,
    command_registry: Any, command_id: str,
) -> dict[str, Any]:
    if kind not in _KINDS:
        raise InputError("scan kind is invalid")
    if execution_mode != "controlled_validation":
        raise InputError("Phase scan execution requires controlled_validation")
    root = repository_root.resolve()
    if not root.is_dir():
        raise InputError("repository root is invalid")
    required_paths = _phase_changed_paths(candidate_manifest)
    command = _descriptor(command_registry, command_id)
    try:
        completed = subprocess.run(
            [command["executable"], *command["argv"]], cwd=root, shell=False,
            capture_output=True, timeout=command["timeout_seconds"], check=False,
        )
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        stdout, stderr, exit_code = b"", str(exc).encode("utf-8", errors="replace"), None
    receipt = {
        "commandId": command_id, "exitCode": exit_code,
        "stdoutSha256": "sha256:" + hashlib.sha256(stdout).hexdigest(),
        "stderrSha256": "sha256:" + hashlib.sha256(stderr).hexdigest(),
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
