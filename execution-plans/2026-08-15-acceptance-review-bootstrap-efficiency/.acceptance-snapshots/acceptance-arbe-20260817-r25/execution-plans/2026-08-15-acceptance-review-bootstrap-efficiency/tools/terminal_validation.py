#!/usr/bin/env python3
"""Execute every registered GREEN behavior program for the current candidate."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import hashlib
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--plan-dir", type=Path, default=PLAN_ROOT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    plan_root = args.plan_dir.resolve()
    repository_root = args.repository_root.resolve()
    if plan_root != PLAN_ROOT or repository_root != REPOSITORY_ROOT:
        raise ValueError("terminal runner must use its declared repository and plan roots")
    sys.path.insert(0, str(plan_root / "tools"))
    from validate_all import validate_plan
    validate_plan()
    registry = json.loads((plan_root / "command-registry.v1.json").read_text(encoding="utf-8"))
    commands = {item["id"]: item for item in registry["commands"]}
    results = []
    for command_id in registry["terminal_command_ids"]:
        command = commands[command_id]
        argv = [command["executable"], *command["argv"]]
        completed = subprocess.run(argv, cwd=repository_root, check=False)
        results.append({"command_id": command_id, "exit_code": completed.returncode})
        if completed.returncode != 0:
            result = {"status": "failed", "results": results, "authorizes": []}
            print(json.dumps(result, sort_keys=True))
            return completed.returncode or 1
    contract_path = plan_root / "implementation-contract.v1.json"
    registry_path = plan_root / "command-registry.v1.json"
    contract_hash = "sha256:" + hashlib.sha256(contract_path.read_bytes()).hexdigest()
    registry_hash = "sha256:" + hashlib.sha256(registry_path.read_bytes()).hexdigest()
    result = {
        "schema_version": "quick-dev-implementation-complete.v1",
        "predicate": "implementation-complete",
        "status": "pass",
        "plan_id": json.loads(contract_path.read_text(encoding="utf-8"))["plan_id"],
        "contract_hash": contract_hash,
        "command_registry_hash": registry_hash,
        "terminal_command_id": "terminal-full",
        "validated_command_ids": list(registry["terminal_command_ids"]),
        "results": results,
        "authorizes": ["implementation-complete"],
        "does_not_authorize": ["acceptance-passed", "commit", "release", "archived"],
    }
    print(json.dumps(result, sort_keys=True))
    if args.out is not None:
        output = args.out.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, sort_keys=True, indent=2)
            stream.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
