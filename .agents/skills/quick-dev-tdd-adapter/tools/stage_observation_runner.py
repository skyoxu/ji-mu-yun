from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import re
import os
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any


def _relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("observation path is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError("observation path escapes the workspace")
    return value


def _snapshot(root: Path, path: str) -> str | None:
    target = root / path
    if not target.exists():
        return None
    if not target.is_file() or target.is_symlink():
        raise ValueError("observation target is not a regular file")
    return base64.b64encode(target.read_bytes()).decode("ascii")


def freeze(workspace: Path, paths: list[str]) -> dict[str, str | None]:
    """Freeze explicit pre-stage snapshots before a RED test or production write."""
    root = workspace.resolve()
    declared = sorted({_relative_path(path) for path in paths})
    if not declared:
        raise ValueError("at least one snapshot path is required")
    return {path: _snapshot(root, path) for path in declared}


def _workspace_manifest(root: Path) -> dict[str, bytes | None]:
    """Capture real workspace bytes, excluding only adapter-owned runtime data."""
    manifest: dict[str, bytes | None] = {}
    for current, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in {".git", "__pycache__", ".pytest_cache"}]
        current_path = Path(current)
        try:
            relative_dir = current_path.relative_to(root).as_posix()
        except ValueError:
            continue
        if relative_dir == "logs/tdd-adapter" or relative_dir.startswith("logs/tdd-adapter/"):
            dirs[:] = []
            continue
        for name in files:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if relative == "logs/tdd-adapter" or relative.startswith("logs/tdd-adapter/"):
                continue
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                manifest[relative] = path.read_bytes()
            except OSError:
                continue
    return manifest


def run(
    workspace: Path,
    stage: str,
    command: dict[str, Any],
    paths: list[str],
    response_summary: str,
    *,
    before_snapshots: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Run one structured command and immediately return explicit file snapshots.

    The caller remains responsible for deciding when a stage is permitted and for
    append-only persistence. RED retains typed failure markers.
    """
    if stage not in {"red", "green", "refactor"} or not isinstance(response_summary, str):
        raise ValueError("stage or response summary is invalid")
    required = {"id", "executable", "argv", "cwd", "timeout_seconds", "shell"}
    if not isinstance(command, dict) or set(command) != required or command.get("shell") is not False:
        raise ValueError("command must be a structured shell-free descriptor")
    command_id, executable, argv, cwd, timeout = (command[key] for key in ("id", "executable", "argv", "cwd", "timeout_seconds"))
    if (
        not isinstance(command_id, str) or not command_id
        or not isinstance(executable, str) or not executable
        or not isinstance(argv, list) or any(not isinstance(item, str) for item in argv)
        or not isinstance(cwd, str) or not isinstance(timeout, int) or timeout <= 0
    ):
        raise ValueError("command descriptor fields are invalid")
    workspace = workspace.resolve()
    relative_cwd = _relative_path(cwd) if cwd != "." else cwd
    command_cwd = (workspace / relative_cwd).resolve()
    try:
        command_cwd.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("command cwd escapes the workspace") from exc
    if not command_cwd.is_dir():
        raise ValueError("command cwd is not a directory")
    declared_paths = sorted({_relative_path(path) for path in paths})
    if not declared_paths:
        raise ValueError("at least one snapshot path is required")
    before = _workspace_manifest(workspace)
    for path in declared_paths:
        before.setdefault(path, _snapshot(workspace, path))
    try:
        completed = subprocess.run(
            [executable, *argv], cwd=command_cwd, shell=False, check=False,
            capture_output=True, timeout=timeout,
        )
        exit_code = completed.returncode
        output = (completed.stdout + b"\n" + completed.stderr).decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        exit_code = 124
        output = ""
    after = _workspace_manifest(workspace)
    changed_paths = sorted(set(before) | set(after))
    changed_files = [
        {"path": path, "before_bytes_base64": None if before.get(path) is None else base64.b64encode(before[path]).decode("ascii"), "after_bytes_base64": None if after.get(path) is None else base64.b64encode(after[path]).decode("ascii")}
        for path in changed_paths if before.get(path) != after.get(path)
    ]
    return {
        "stage": stage,
        "exit_code": exit_code,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "changed_files": changed_files,
        "commands_attempted": [command_id],
        "response_summary": response_summary,
        "observed_failure_ids": sorted(set(re.findall(r"FAILURE_ID:([A-Z0-9][A-Z0-9._-]*)", output))) if stage == "red" else [],
    }


def record_observation(run_dir: Path, observation: dict[str, Any]) -> Path:
    """Persist one captured observation without replacing historical stage evidence."""
    required = {"stage", "exit_code", "observed_at", "changed_files", "commands_attempted", "response_summary"}
    optional = {"observed_failure_ids"}
    if not isinstance(observation, dict) or not set(observation).issubset(required | optional) or not required.issubset(observation) or observation.get("stage") not in {"red", "green", "refactor"}:
        raise ValueError("observation shape is invalid")
    if "observed_failure_ids" in observation and (not isinstance(observation["observed_failure_ids"], list) or any(not isinstance(item, str) or not item for item in observation["observed_failure_ids"])):
        raise ValueError("observed_failure_ids must be a string list")
    if not isinstance(observation["response_summary"], str) or not observation["response_summary"]:
        raise ValueError("response_summary must be nonempty")
    try:
        observed_at = datetime.fromisoformat(str(observation["observed_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must include a timezone")
    output = run_dir / "observations" / f"{observation['stage']}-observed.json"
    if output.exists():
        raise ValueError("stage observation already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(observation, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    return output
