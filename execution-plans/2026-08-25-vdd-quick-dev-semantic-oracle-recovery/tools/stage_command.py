"""Small stateless command dispatcher used by the plan registry.

It executes the slice's real behavior tests; it never writes pass state or
terminal evidence. The adapter owns lifecycle evidence and the terminal
predicate only validates run-local artifacts.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

TESTS = {
    "S1": "test_semantic_red.py",
    "S2": "test_s2_descriptor_red.py",
    "S3": "test_s3_judge_red.py",
    "S4": "test_s4_cover_red.py",
    "S5": "test_s5_promotion_red.py",
    "S6": "test_s6_terminal_red.py",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", required=True, choices=sorted(TESTS))
    parser.add_argument("--stage", required=True, choices=("green", "refactor", "terminal"))
    parser.add_argument("--plan-dir", required=True)
    args = parser.parse_args()
    root = Path(args.plan_dir).parents[1].parent
    if args.stage == "terminal":
        from validate_all import validate_terminal
        result = validate_terminal(Path(args.plan_dir))
        return 0 if result.get("status") == "pass" else 1
    test = Path(args.plan_dir) / "tools" / TESTS[args.slice]
    return subprocess.call([sys.executable, "-m", "pytest", str(test), "-q"], cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
