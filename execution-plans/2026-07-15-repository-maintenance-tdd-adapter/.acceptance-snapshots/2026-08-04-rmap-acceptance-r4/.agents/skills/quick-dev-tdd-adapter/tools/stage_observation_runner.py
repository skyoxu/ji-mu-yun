from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
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
    append-only persistence.  stdout and stderr are intentionally not retained.
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
    before = freeze(workspace, declared_paths) if before_snapshots is None else dict(before_snapshots)
    if set(before) != set(declared_paths) or any(value is not None and not isinstance(value, str) for value in before.values()):
        raise ValueError("frozen snapshots do not match declared paths")
    try:
        completed = subprocess.run(
            [executable, *argv], cwd=command_cwd, shell=False, check=False,
            capture_output=True, timeout=timeout,
        )
        exit_code = completed.returncode
    except subprocess.TimeoutExpired:
        exit_code = 124
    changed_files = [
        {"path": path, "before_bytes_base64": before[path], "after_bytes_base64": _snapshot(workspace, path)}
        for path in declared_paths
    ]
    return {
        "stage": stage,
        "exit_code": exit_code,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "changed_files": changed_files,
        "commands_attempted": [command_id],
        "response_summary": response_summary,
    }


def record_observation(run_dir: Path, observation: dict[str, Any]) -> Path:
    """Persist one captured observation without replacing historical stage evidence."""
    required = {"stage", "exit_code", "observed_at", "changed_files", "commands_attempted", "response_summary"}
    if not isinstance(observation, dict) or set(observation) != required or observation.get("stage") not in {"red", "green", "refactor"}:
        raise ValueError("observation shape is invalid")
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
