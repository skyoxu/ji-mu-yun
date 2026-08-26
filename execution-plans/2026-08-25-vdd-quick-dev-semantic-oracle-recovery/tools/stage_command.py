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
    parser.add_argument("--run-root")
    args = parser.parse_args()
    if args.stage == "terminal":
        if not args.run_root:
            return 2
        out = Path(args.run_root) / "implementation-complete-result.json"
        command = [sys.executable, str(Path(args.plan_dir) / "tools" / "terminal_predicate.py"),
                   "--repository-root", str(Path(args.plan_dir).parents[1]),
                   "--plan-dir", args.plan_dir, "--slice", args.slice,
                   "--run-root", args.run_root, "--out", str(out)]
        return subprocess.call(command, cwd=Path(args.plan_dir).parents[1])
    owner = Path(args.plan_dir) / "tools" / "artifact_owners.py"
    command = [sys.executable, str(owner), "--plan-dir", args.plan_dir, "--slice", args.slice, "--stage", args.stage]
    run_root = args.run_root
    if not run_root and args.stage == "terminal":
        plan_id = Path(args.plan_dir).name
        candidates = sorted((Path(args.plan_dir).parents[1] / "logs" / "tdd-adapter" / plan_id / args.slice).glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            run_root = str(candidates[0])
    if run_root:
        command.extend(["--run-root", run_root])
    return subprocess.call(command, cwd=Path(args.plan_dir).parents[1].parent)


if __name__ == "__main__":
    raise SystemExit(main())
