from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--plan-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.repository_root)
    plan = Path(args.plan_dir)
    command = [sys.executable, str(plan / "tools" / "validate_all.py")]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return completed.returncode
    try:
        validation = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return 1
    if validation.get("status") != "pass" or validation.get("validated_state") != "implementation-complete":
        return 1
    result = {
        "schema_version": "quick-dev-implementation-complete.v1",
        "plan_id": "2026-08-24-phase-b-c-identity-isolation-workspace-recovery",
        "status": "pass",
        "predicate": "implementation-complete",
        "terminal_command_id": "implementation-complete",
        "validated_command_ids": ["s0-green", "s1-green", "s2-green", "s3-green", "s4-green", "s4-terminal"],
        "authorizes": ["implementation-complete"],
        "contract_hash": "sha256:" + hashlib.sha256((plan / "implementation-contract.v1.json").read_bytes()).hexdigest(),
        "command_registry_hash": "sha256:" + hashlib.sha256((plan / "command-registry.v1.json").read_bytes()).hexdigest(),
        "validation": validation,
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
