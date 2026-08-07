"""Negative-before-implementation and terminal predicate for Package A."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REQUIRED_OUTPUTS = [
    "docs/standards/skill-authoring-standard.md",
    "docs/adr/ADR-0060-repository-skill-authoring-contract.md",
    "scripts/sc/config/skill-authoring-standard.v1.json",
    "scripts/sc/schemas/skill-quality-contract.v1.schema.json",
    "scripts/sc/schemas/skill-quality-result.v1.schema.json",
    "scripts/sc/validate_skill_quality.py",
    "scripts/sc/skill_quality_examples.py",
    "scripts/sc/tests/test_validate_skill_quality.py",
    "scripts/sc/tests/test_skill_quality_examples.py",
]
REQUIRED_DIRECTORIES = [
    "scripts/sc/tests/fixtures/skill-quality/contract",
    "scripts/sc/tests/fixtures/skill-quality/validator",
    "scripts/sc/tests/fixtures/skill-quality/examples",
    "scripts/sc/tests/fixtures/skill-quality/security",
    "scripts/sc/tests/fixtures/skill-quality/migration",
]
COMMAND_REGISTRY_PATH = ROOT / "execution-plans/2026-08-06-skill-authoring-standard/command-registry.v1.json"
REQUIRED_TERMINAL_COMMAND_IDS = (
    "standard-contract-tests",
    "standard-example-tests",
    "package-a-terminal",
)
EXPECTED_TERMINAL_COMMAND_ARGV = {
    "standard-contract-tests": ["-3", "-B", "scripts/sc/tests/test_validate_skill_quality.py"],
    "standard-example-tests": ["-3", "-B", "scripts/sc/tests/test_skill_quality_examples.py"],
    "package-a-terminal": ["-3", "-B", "scripts/sc/validate_skill_quality.py", "--repository-root", ".", "--contract", "scripts/sc/config/skill-authoring-standard.v1.json", "--target-root", ".agents/skills"],
}


def missing() -> list[str]:
    files = [path for path in REQUIRED_OUTPUTS if not (ROOT / path).is_file()]
    directories = [f"{path}/" for path in REQUIRED_DIRECTORIES if not (ROOT / path).is_dir()]
    return files + directories


def _command_argv(descriptor: dict[str, object]) -> tuple[list[str], int]:
    if descriptor.get("shell") is not False:
        raise ValueError("terminal command must set shell=false")
    if descriptor.get("executable") != "py":
        raise ValueError("terminal command executable must be py")
    cwd = descriptor.get("cwd")
    if cwd != {"type": "repo_path", "value": "."}:
        raise ValueError("terminal command cwd must be repository root")
    timeout = descriptor.get("timeout_seconds")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 0 < timeout <= 3600:
        raise ValueError("terminal command timeout is invalid")
    raw_argv = descriptor.get("argv")
    if not isinstance(raw_argv, list) or not all(isinstance(item, str) for item in raw_argv):
        raise ValueError("terminal command argv must be a string array")
    argv = ["py", *raw_argv]
    for item in argv[1:]:
        if "\x00" in item or Path(item).is_absolute() or ".." in Path(item).parts:
            raise ValueError("terminal command contains an unsafe path argument")
        if item in {"-c", "--command"}:
            raise ValueError("terminal command cannot execute inline code")
    return argv, timeout


def run_terminal_replay(registry: dict[str, object]) -> dict[str, object]:
    command_ids = registry.get("terminal_replay_command_ids")
    commands = registry.get("commands")
    by_id = {item.get("id"): item for item in commands if isinstance(item, dict)} if isinstance(commands, list) else {}
    result: dict[str, object] = {"status": "passed", "commands": [], "authorizes": []}
    if not isinstance(command_ids, list) or not command_ids or len(command_ids) != len(set(command_ids)):
        return {"status": "blocked", "commands": [], "errors": ["terminal-replay-command-list-invalid"], "authorizes": []}
    if tuple(command_ids) != REQUIRED_TERMINAL_COMMAND_IDS:
        return {"status": "blocked", "commands": [], "errors": ["terminal-replay-command-set-incomplete-or-reordered"], "authorizes": []}
    for command_id in command_ids:
        descriptor = by_id.get(command_id)
        entry: dict[str, object] = {"commandId": command_id}
        try:
            if not isinstance(descriptor, dict):
                raise ValueError("registered terminal command is missing")
            if descriptor.get("argv") != EXPECTED_TERMINAL_COMMAND_ARGV[command_id]:
                raise ValueError("registered terminal command argv is not bound to the Package A command")
            argv, timeout = _command_argv(descriptor)
            completed = subprocess.run(
                argv,
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
            )
            entry.update({"argv": argv, "exitCode": completed.returncode})
            if completed.returncode != 0:
                entry["stderr"] = completed.stderr[-4000:]
                result["status"] = "blocked"
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            entry.update({"exitCode": None, "error": str(exc)})
            result["status"] = "blocked"
        result["commands"].append(entry)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", choices=["SAS-S0", "SAS-S1", "SAS-S2", "SAS-S3"])
    args = parser.parse_args()
    absent = missing()
    if args.slice == "SAS-S0":
        absent = [p for p in absent if p.startswith("docs/standards/") or p.startswith("docs/adr/") or "config/" in p or "skill-quality-contract" in p or "fixtures/skill-quality/contract/" in p]
    elif args.slice == "SAS-S1":
        absent = [p for p in absent if p.startswith("scripts/sc/validate") or "skill-quality-result" in p or "test_validate" in p or "fixtures/skill-quality/validator/" in p]
    elif args.slice == "SAS-S2":
        absent = [p for p in absent if "skill_quality_examples" in p or "test_skill_quality_examples" in p or "fixtures/skill-quality/examples/" in p or "fixtures/skill-quality/security/" in p]
    if args.slice:
        payload = {"predicate": args.slice, "status": "blocked" if absent else "candidate", "missing": absent, "authorizes": []}
        print(json.dumps(payload, indent=2))
        return 1 if absent else 0
    replay = {"status": "blocked", "commands": [], "errors": ["terminal-replay-skipped-missing-outputs"], "authorizes": []}
    if not absent:
        try:
            replay = run_terminal_replay(json.loads(COMMAND_REGISTRY_PATH.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            replay = {"status": "blocked", "commands": [], "errors": [str(exc)], "authorizes": []}
    payload = {"predicate": "terminal", "status": "blocked" if absent or replay["status"] != "passed" else "candidate", "missing": absent, "terminalReplay": replay, "authorizes": []}
    print(json.dumps(payload, indent=2))
    return 1 if absent or replay["status"] != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
