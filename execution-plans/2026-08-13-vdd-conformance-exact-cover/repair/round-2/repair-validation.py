"""Validate the VDD repair artifacts only; never claim implementation completion."""
from __future__ import annotations

import json
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", default="all")
    args = parser.parse_args()
    mapping = json.loads((PLAN / "repair/round-1/requirements-acceptance-slice-command.v1.json").read_text(encoding="utf-8"))
    registry = json.loads((PLAN / "command-registry.v1.json").read_text(encoding="utf-8"))
    commands = {entry["id"] for entry in registry["commands"]}
    mapped = {row["command"] for row in mapping["requirements"]}
    missing = sorted(mapped - commands)
    if missing:
        raise SystemExit(f"unregistered mapping commands: {missing}")
    slices = {row["slice"] for row in mapping["requirements"]}
    if not {"S0","S1","S2","S3a","S3b","S3c","S3d","S4","S5"}.issubset(slices):
        raise SystemExit("repair slice coverage is incomplete")
    subprocess.run([sys.executable, "-m", "unittest", "scripts.python.tests.test_knowledge_context_validation"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, ".agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py", "--skill-root", ".agents/skills/vdd-execution-plan"], cwd=ROOT, check=True)
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    print(f"repair-validation=passed check={args.check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
