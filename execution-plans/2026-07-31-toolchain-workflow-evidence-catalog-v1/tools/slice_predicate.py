"""Run the registered current slice validator and emit a Quick Dev predicate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from validate_all import slice_validation_snapshot
from validate_plan import PLAN_ID, PLAN_ROOT, REPOSITORY_ROOT, validate_directory


VALIDATION_COMMANDS = {
    "TEC-S0": ["plan-authority-negative"],
    "TEC-S1": ["catalog-contract-suite"],
    "TEC-S2": ["catalog-adapter-suite"],
    "TEC-S3": ["catalog-generation-suite", "catalog-query-suite"],
    "TEC-S4": ["catalog-publication-suite"],
    "TEC-S5": ["catalog-closure-suite", "catalog-forbidden-suite"],
    "TEC-S6": ["catalog-terminal"],
}
PREDICATES = {
    "TEC-S0": "slice-ready",
    "TEC-S1": "slice-ready",
    "TEC-S2": "slice-ready",
    "TEC-S3": "slice-ready",
    "TEC-S4": "slice-ready",
    "TEC-S5": "implementation-candidate",
    "TEC-S6": "implementation-complete",
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _expand(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict) or set(value) != {"type", "value"} or not isinstance(value["value"], str):
        raise ValueError("command argument is invalid")
    if value["type"] == "plan_path":
        return (PLAN_ROOT.relative_to(REPOSITORY_ROOT) / value["value"]).as_posix()
    if value["type"] == "repo_path":
        return value["value"]
    raise ValueError("unsupported command argument type")


def _run(command: dict[str, Any]) -> int:
    if command.get("shell") is not False or command.get("cwd") != {"type": "repo_path", "value": "."}:
        raise ValueError("command must be shell-free at repository root")
    argv = [_expand(value) for value in command.get("argv", [])]
    completed = subprocess.run(
        [command["executable"], *argv],
        cwd=REPOSITORY_ROOT,
        shell=False,
        check=False,
        timeout=command["timeout_seconds"],
    )
    return completed.returncode


def evaluate(slice_id: str) -> dict[str, Any]:
    plan_result = validate_directory()
    if plan_result["status"] != "pass":
        return {"schema_version": "tec.slice-predicate.v1", "plan_id": PLAN_ID, "slice_id": slice_id, "status": "fail", "predicate": PREDICATES[slice_id], "failure_code": "plan_contract_invalid", "authorizes": []}
    registry = _load(PLAN_ROOT / "command-registry.v1.json")
    commands = {item["id"]: item for item in registry["commands"]}
    for command_id in VALIDATION_COMMANDS[slice_id]:
        command = commands.get(command_id)
        if not isinstance(command, dict) or _run(command) != 0:
            return {"schema_version": "tec.slice-predicate.v1", "plan_id": PLAN_ID, "slice_id": slice_id, "status": "fail", "predicate": PREDICATES[slice_id], "failure_code": f"command_failed:{command_id}", "authorizes": []}
    contract_bytes = (PLAN_ROOT / "implementation-contract.v1.json").read_bytes()
    result: dict[str, Any] = {
        "schema_version": "tec.slice-predicate.v1",
        "plan_id": PLAN_ID,
        "slice_id": slice_id,
        "status": "pass",
        "predicate": PREDICATES[slice_id],
        "contract_hash": "sha256:" + hashlib.sha256(contract_bytes).hexdigest(),
        "authorizes": ["implementation-complete"] if slice_id == "TEC-S6" else [],
        "does_not_authorize": ["acceptance-passed", "archived", "handoff", "release", "deployment"],
    }
    result.update(slice_validation_snapshot(slice_id))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice-id", choices=tuple(VALIDATION_COMMANDS), required=True)
    args = parser.parse_args()
    result = evaluate(args.slice_id)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
