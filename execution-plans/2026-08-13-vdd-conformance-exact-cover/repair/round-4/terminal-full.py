"""Terminal implementation gate derived from the implementation contract."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
COMMAND = PLAN / "repair/round-4/implementation-command.py"


def main() -> int:
    try:
        contract = json.loads((PLAN / "implementation-contract.v1.json").read_text(encoding="utf-8"))
        commands = set()
        for item in contract.get("slices", []):
            commands.update(item.get("red_command_ids", []))
            commands.update(item.get("green_command_ids", []))
        if not commands:
            raise RuntimeError("implementation command universe is empty")
        evidence = json.loads((PLAN / "implementation-evidence.v1.json").read_text(encoding="utf-8"))
        if set(evidence.get("commands", {})) != commands:
            raise RuntimeError("implementation evidence command universe does not match contract")
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"terminal-full=blocked reason={exc}")
        return 2
    for command in sorted(commands):
        result = subprocess.run([sys.executable, str(COMMAND), "--command", command], cwd=ROOT, check=False)
        if result.returncode:
            print(f"terminal-full=blocked command={command}")
            return 2
    repair = subprocess.run([sys.executable, str(ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover/repair/round-4/repair-knowledge-composition.py"), "--validate-receipt"], cwd=ROOT, check=False)
    if repair.returncode:
        print("terminal-full=blocked repair-composition")
        return 2
    print("terminal-full=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
