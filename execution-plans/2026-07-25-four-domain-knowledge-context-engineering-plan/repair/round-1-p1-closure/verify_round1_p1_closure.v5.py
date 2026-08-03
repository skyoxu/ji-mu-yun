#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys

EXPECTED = [
    ".agents/skills/maintain-knowledge-base/scripts/test_maintain_knowledge.py",
    "execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/tools/tests/test_plan_validator.py",
    "scripts/sc/tests/test_llm_backend.py",
    "scripts/sc/tests/test_llm_review_runtime_budget.py"
]
COMMANDS = [
    [sys.executable, ".agents/skills/maintain-knowledge-base/scripts/test_maintain_knowledge.py"],
    [sys.executable, "scripts/sc/tests/test_llm_backend.py"],
    [sys.executable, "scripts/sc/tests/test_llm_review_runtime_budget.py"],
    [sys.executable, "execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/tools/tests/test_plan_validator.py"],
]

parser = argparse.ArgumentParser()
parser.add_argument("--bound-test", action="append", default=[])
args = parser.parse_args()
if sorted(args.bound_test) != EXPECTED:
    raise SystemExit("bound targeted test set mismatch")
for index, command in enumerate(COMMANDS, 1):
    result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
    if result.returncode != 0:
        print(result.stdout, end="", file=sys.stderr)
        print(result.stderr, end="", file=sys.stderr)
        raise SystemExit(result.returncode)
    print(f"CHECK {{index}} PASS")
print("7-25 ROUND 1 P1 REPAIR COMPOSITION PASS")
