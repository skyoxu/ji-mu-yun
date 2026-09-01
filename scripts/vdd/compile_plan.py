#!/usr/bin/env python3
"""Stable VDD Chapter 4/5/6 compiler CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".agents" / "skills" / "vdd-execution-plan" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import semantic_feasibility_patch  # noqa: F401  # installs normative planned-new-file V7 rule
from semantic_compiler_authority import compile_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--profile", choices=("standard", "resumable", "self-hosted"), default="standard")
    parser.add_argument("--companion", type=Path, action="append", default=[])
    parser.add_argument("--worker-cache", type=Path)
    parser.add_argument("--recommendation-only", action="store_true")
    parser.add_argument("--resume-from", choices=("first-failed-stage",), default=None)
    args = parser.parse_args()
    cache = None
    if args.worker_cache:
        value = json.loads(args.worker_cache.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise SystemExit("worker cache must be a JSON object")
        cache = value
    try:
        result = compile_plan(
            requirements=args.requirements,
            out_dir=args.out_dir,
            companions=args.companion,
            profile=args.profile,
            worker_cache=cache,
            recommendation_only=args.recommendation_only,
            resume_from=args.resume_from,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "repair-vdd", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") in {"plan-ready", "recommendation-only"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
