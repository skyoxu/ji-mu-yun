from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", choices=("S0", "S1", "S2"))
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--plan-dir", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    contract_path = args.repository_root / "execution-plans/2026-08-17-quick-dev-tdd-stage-recovery/implementation-contract.v1.json"
    contract_hash = "sha256:" + hashlib.sha256(contract_path.read_bytes()).hexdigest()
    target = ".agents/skills/quick-dev-tdd-adapter/tools/tests" if args.slice is None else {
        "S0": ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_lifecycle.py",
        "S1": ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_recovery.py",
        "S2": ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_migration_cutover.py",
    }[args.slice]
    result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", target, "-q"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=args.repository_root,
    )
    payload = {"schema_version": "quick-dev-tdd-stage-recovery.terminal-result.v1", "status": "pass" if result.returncode == 0 else "fail", "predicate": "slice-ready" if args.slice else "implementation-complete", "plan_id": "quick-dev-tdd-stage-recovery", "contract_hash": contract_hash, "terminal_command_id": "s0-terminal" if args.slice == "S0" else "s1-terminal" if args.slice == "S1" else "s2-terminal" if args.slice == "S2" else "terminal-full", "validated_command_ids": ["adapter-tests", "dogfood-8-17"] if args.slice == "S2" else [], "authorizes": ["implementation-complete"] if result.returncode == 0 and args.slice is None else []}
    rendered = json.dumps(payload)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(rendered)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
