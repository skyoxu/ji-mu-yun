#!/usr/bin/env python3
"""Execute every registered GREEN behavior program for the current candidate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]


def main() -> int:
    registry = json.loads((PLAN_ROOT / "command-registry.v1.json").read_text(encoding="utf-8"))
    commands = {item["id"]: item for item in registry["commands"]}
    results = []
    for command_id in registry["terminal_command_ids"]:
        command = commands[command_id]
        argv = [command["executable"], *command["argv"]]
        completed = subprocess.run(argv, cwd=REPOSITORY_ROOT, check=False)
        results.append({"command_id": command_id, "exit_code": completed.returncode})
        if completed.returncode != 0:
            print(json.dumps({"status": "failed", "results": results, "authorizes": []}, sort_keys=True))
            return completed.returncode or 1
    print(json.dumps({"status": "passed", "results": results, "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
