"""Terminal gate: execute each exact command registered for the contract universe."""
from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
CLOSURE = PLAN / "repair/round-5/repair-closure.json"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    try:
        contract = json.loads((PLAN / "implementation-contract.v1.json").read_text(encoding="utf-8"))
        registry = json.loads((PLAN / "command-registry.v1.json").read_text(encoding="utf-8"))
        closure = json.loads(CLOSURE.read_text(encoding="utf-8"))
        command_ids = {item for slice_ in contract["slices"] for key in ("red_command_ids", "green_command_ids") for item in slice_[key]}
        records = {item["id"]: item for item in registry["commands"]}
        if not command_ids or set(records) < command_ids:
            raise RuntimeError("registry does not cover the implementation command universe")
        for command_id in command_ids:
            record = records[command_id]
            if not isinstance(record.get("acceptance_ids"), list) or not record["acceptance_ids"] or not isinstance(registry.get("behavior_programs", {}).get(command_id), dict) or not isinstance(record.get("receipt_checker"), dict):
                raise RuntimeError(f"registry command lacks deterministic binding: {command_id}")
        receipt_ref = closure["composition_receipt"]
        receipt = (PLAN / receipt_ref).resolve()
        if sha(receipt) != closure["composition_receipt_sha256"]:
            raise RuntimeError("closure composition receipt hash is stale")
    except (OSError, KeyError, TypeError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"terminal-full=blocked reason={exc}")
        return 2
    for command_id in sorted(command_ids):
        command = records[command_id].get("command")
        if not isinstance(command, str) or not command:
            print(f"terminal-full=blocked command={command_id} reason=missing-registered-command")
            return 2
        result = subprocess.run(shlex.split(command), cwd=ROOT, check=False)
        if result.returncode:
            print(f"terminal-full=blocked command={command_id}")
            return 2
    repair = subprocess.run([
        sys.executable, str(PLAN / "repair/round-5/repair-knowledge-composition.py"),
        "--validate-receipt", "--receipt", str(receipt), "--closure", str(CLOSURE),
    ], cwd=ROOT, check=False)
    if repair.returncode:
        print("terminal-full=blocked repair-composition")
        return 2
    print("terminal-full=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
