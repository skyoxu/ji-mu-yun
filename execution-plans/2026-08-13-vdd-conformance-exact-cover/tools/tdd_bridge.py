from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--snapshot-path", action="append", required=True)
    parser.add_argument("--materialize-only", action="store_true")
    args = parser.parse_args()
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    registry = json.loads((plan / contract["command_registry"]).read_text(encoding="utf-8"))
    selected = next(item for item in contract["slices"] if item["slice_id"] == args.slice_id)
    if args.materialize_only:
        declared = selected.get("execution_snapshot_paths")
        if args.snapshot_path != declared:
            raise ValueError("bridge snapshot paths do not match the declared slice snapshot")
        print(json.dumps({"status": "materialized", "slice_id": args.slice_id, "authorizes": []}))
        return 0
    commands = {item["id"]: item for item in registry["commands"]}
    run_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%dT%H%M%S-%fZ")
    run_dir = root / "logs" / "tdd-adapter" / contract["plan_id"] / args.slice_id / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    stages = [
        ("red", selected["tdd"]["red"]["command_id"], False),
        ("green", selected["tdd"]["green"]["command_id"], True),
    ]
    for index in selected["tdd"]["refactor"]["invocations"]:
        stages.append(("refactor", index["command_id"], True))
    for stage, command_id, should_pass in stages:
        command = commands[command_id]
        result = subprocess.run([command["executable"], *command["argv"]], cwd=root, shell=False, check=False, capture_output=True, text=True, timeout=command["timeout_seconds"])
        observed_pass = result.returncode == 0
        if observed_pass != should_pass:
            (run_dir / "failure.json").write_text(json.dumps({"stage": stage, "command_id": command_id, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}, indent=2) + "\n", encoding="utf-8")
            return 2
        (run_dir / f"{stage}.json").write_text(json.dumps({"stage": stage, "command_id": command_id, "exit_code": result.returncode, "observed_at": datetime.now(timezone.utc).isoformat()}, indent=2) + "\n", encoding="utf-8")
    terminal_id = selected["post_refactor_command_id"]
    terminal = commands[terminal_id]
    result = subprocess.run([terminal["executable"], *terminal["argv"]], cwd=root, shell=False, check=False, capture_output=True, text=True, timeout=terminal["timeout_seconds"])
    if result.returncode != 0:
        (run_dir / "terminal-failure.json").write_text(result.stdout + result.stderr, encoding="utf-8")
        return 2
    from validate_all import slice_validation_snapshot
    roots = slice_validation_snapshot(args.slice_id)
    predicate = {"predicate": selected["exit_predicate"], "status": "pass", "plan_id": contract["plan_id"], "slice_id": args.slice_id, "contract_hash": _hash(plan / "implementation-contract.v1.json"), **roots, "authorizes": []}
    (run_dir / f"{selected['exit_predicate']}-result.json").write_text(json.dumps(predicate, indent=2) + "\n", encoding="utf-8")
    (root / "logs" / "tdd-adapter" / contract["plan_id"] / "run-state.v1.json").write_text(json.dumps({"last_slice_id": args.slice_id, "next_action": "route", "authorizes": []}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "slice_id": args.slice_id, "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
