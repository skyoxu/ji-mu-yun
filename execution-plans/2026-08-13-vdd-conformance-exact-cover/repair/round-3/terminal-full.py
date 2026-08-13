"""Current implementation terminal gate; lifecycle state is not an input."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
COMMAND = PLAN / "repair/round-3/implementation-command.py"
COMPOSITION = PLAN / "repair/round-3/composition.py"


def main() -> int:
    evidence = PLAN / "implementation-evidence.v1.json"
    if not evidence.is_file():
        print("terminal-full=blocked implementation-evidence-missing")
        return 2
    try:
        data = json.loads(evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("terminal-full=blocked implementation-evidence-invalid")
        return 2
    required = {"vdd-source-freeze", "exact-cover", "semantic-handoff", "authorization-preflight"}
    if data.get("schema_version") != "vdd-exact-cover-implementation-evidence.v1" or not required.issubset(set(data.get("implemented_commands", []))):
        print("terminal-full=blocked implementation-slices-incomplete")
        return 2
    for command in sorted(data["implemented_commands"]):
        result = subprocess.run([sys.executable, str(COMMAND), "--command", command, "--terminal-full"], cwd=ROOT, check=False)
        if result.returncode:
            print(f"terminal-full=blocked command={command}")
            return 2
    composition = subprocess.run([sys.executable, str(COMPOSITION)], cwd=ROOT, check=False)
    if composition.returncode:
        print("terminal-full=blocked composition")
        return 2
    print("terminal-full=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
