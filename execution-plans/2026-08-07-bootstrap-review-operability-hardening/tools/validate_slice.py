from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any

PLAN_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_DIR.parents[1]
VERIFICATION_COMMANDS = {
    "BROH-S0": "broh-s0-target-test",
    "BROH-S1": "broh-s1-target-test",
    "BROH-S2": "broh-s2-target-test",
    "BROH-S3": "broh-s3-target-test",
    "BROH-S4": "broh-s4-target-test",
    "BROH-S5": "broh-s5-target-test",
    "BROH-S6": "broh-s6-target-test",
}


def _validation_module():
    path = PLAN_DIR / "tools" / "validate_all.py"
    spec = importlib.util.spec_from_file_location("broh_slice_validate_all", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("plan-local validation snapshot helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validation_snapshot(slice_id: str) -> dict[str, str]:
    return _validation_module().slice_validation_snapshot(slice_id)


def _contract_hash() -> str:
    payload = (PLAN_DIR / "implementation-contract.v1.json").read_bytes()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _expand(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict) or set(value) != {"type", "value"} or not isinstance(value["value"], str):
        raise ValueError("registered command argument is invalid")
    if value["type"] == "plan_path":
        return (PLAN_DIR / value["value"]).relative_to(REPOSITORY_ROOT).as_posix()
    if value["type"] == "repo_path" and value["value"] == ".":
        return "."
    raise ValueError("unsupported registered command placeholder")


def _command(command_id: str) -> dict[str, Any]:
    registry = json.loads((PLAN_DIR / "command-registry.v1.json").read_text(encoding="utf-8"))
    command = next((item for item in registry.get("commands", []) if item.get("id") == command_id), None)
    if not isinstance(command, dict) or command.get("shell") is not False:
        raise ValueError(f"verification command is not shell-free: {command_id}")
    return {
        "executable": command["executable"],
        "argv": [_expand(value) for value in command["argv"]],
        "timeout_seconds": command["timeout_seconds"],
    }


def validate_slice(slice_id: str, *, run_tests: bool = False) -> list[str]:
    errors: list[str] = []
    if slice_id not in VERIFICATION_COMMANDS:
        return [f"slice-not-terminal-validatable:{slice_id}"]
    contract = json.loads((PLAN_DIR / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict) or selected.get("exit_predicate") != "slice-ready":
        errors.append(f"slice-exit-predicate-invalid:{slice_id}")
    predecessors = _validation_module().predecessor_result_hashes(slice_id)
    errors.extend(
        f"slice-predecessor-evidence-missing:{slice_id}:{predecessor}"
        for predecessor, value in predecessors.items()
        if value == "missing"
    )
    if run_tests:
        try:
            command = _command(VERIFICATION_COMMANDS[slice_id])
            completed = subprocess.run(
                [command["executable"], *command["argv"]],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                check=False,
                timeout=command["timeout_seconds"],
            )
            if completed.returncode != 0:
                errors.append(f"verification-command-failed:{VERIFICATION_COMMANDS[slice_id]}")
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            errors.append(f"verification-command-error:{type(exc).__name__}")
    return sorted(set(errors))


def result(slice_id: str, errors: list[str]) -> dict[str, Any]:
    module = _validation_module()
    snapshot = module.slice_validation_snapshot(slice_id)
    return {
        "schema_version": "jimuyun.bootstrap-review-operability-hardening.slice-validation.v1",
        "status": "pass" if not errors else "fail",
        "predicate": "slice-ready",
        "slice_id": slice_id,
        "contract_hash": _contract_hash(),
        "predecessor_result_hashes": module.predecessor_result_hashes(slice_id),
        **snapshot,
        "validation_snapshot": snapshot,
        "errors": errors,
        "authorizes": [],
        "does_not_authorize": ["implementation-complete", "acceptance-passed", "commit", "release"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", required=True)
    args = parser.parse_args()
    errors = validate_slice(args.slice, run_tests=True)
    print(json.dumps(result(args.slice, errors), sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
