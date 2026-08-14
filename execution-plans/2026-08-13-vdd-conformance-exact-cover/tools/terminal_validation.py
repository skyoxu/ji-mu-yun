"""Execute the current plan's hash-bound TDD command universe."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


PLAN = Path(__file__).resolve().parents[1]
ROOT = PLAN.parents[1]


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def behavior_path(reference: dict[str, object]) -> Path:
    value = reference.get("path")
    if not isinstance(value, str) or not value:
        raise RuntimeError("behavior program path is missing")
    path = (ROOT / value).resolve()
    path.relative_to(ROOT.resolve())
    if not path.is_file() or reference.get("sha256") != sha(path):
        raise RuntimeError(f"behavior program is missing or stale: {value}")
    dependencies = reference.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise RuntimeError("behavior program dependencies are invalid")
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            raise RuntimeError("behavior program dependency is invalid")
        raw_path, expected = dependency.get("path"), dependency.get("sha256")
        if not isinstance(raw_path, str) or not isinstance(expected, str):
            raise RuntimeError("behavior program dependency binding is invalid")
        candidate = (ROOT / raw_path).resolve()
        candidate.relative_to(ROOT.resolve())
        if not candidate.is_file() or sha(candidate) != expected:
            raise RuntimeError(f"behavior program dependency is missing or stale: {raw_path}")
    return path


def validate_dependencies(references: object) -> None:
    if not isinstance(references, list):
        raise RuntimeError("implementation dependency closure is invalid")
    for reference in references:
        if not isinstance(reference, dict):
            raise RuntimeError("implementation dependency entry is invalid")
        behavior_path(reference)


def run_command(records: dict[str, dict[str, object]], programs: dict[str, object], command_id: str, expected: int) -> None:
    record = records.get(command_id)
    reference = programs.get(command_id)
    if not isinstance(record, dict) or not isinstance(reference, dict):
        raise RuntimeError(f"command lacks registered behavior binding: {command_id}")
    if record.get("shell") is not False:
        raise RuntimeError(f"command permits a shell: {command_id}")
    executable, argv, timeout = record.get("executable"), record.get("argv"), record.get("timeout_seconds")
    if not isinstance(executable, str) or not isinstance(argv, list) or not isinstance(timeout, int) or timeout <= 0:
        raise RuntimeError(f"command descriptor is invalid: {command_id}")
    if any(not isinstance(value, str) for value in argv):
        raise RuntimeError(f"command arguments are invalid: {command_id}")
    behavior_path(reference)
    result = subprocess.run([executable, *argv], cwd=ROOT, check=False, timeout=timeout)
    if (result.returncode == 0) != (expected == 0):
        raise RuntimeError(f"TDD outcome mismatch for {command_id}: expected {expected}, got {result.returncode}")


def main() -> int:
    try:
        contract = json.loads((PLAN / "implementation-contract.v1.json").read_text(encoding="utf-8"))
        registry = json.loads((PLAN / contract["command_registry"]).read_text(encoding="utf-8"))
        records = {item["id"]: item for item in registry["commands"]}
        programs = registry["behavior_programs"]
        if not isinstance(programs, dict):
            raise RuntimeError("behavior program registry is invalid")
        validate_dependencies(registry.get("implementation_dependencies"))
        for slice_ in contract["slices"]:
            for command_id in slice_["red_command_ids"]:
                run_command(records, programs, command_id, 1)
            for command_id in slice_["green_command_ids"]:
                run_command(records, programs, command_id, 0)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"terminal-validation=blocked reason={exc}")
        return 2
    print("terminal-validation=implementation-complete authorizes=[]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
