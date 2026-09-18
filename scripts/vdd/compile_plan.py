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
    parser.add_argument("--result-json", type=Path, help="Write the compiler result even on a caught failure")
    parser.add_argument("--recommendation-only", action="store_true")
    parser.add_argument("--resume-from", choices=("first-failed-stage",), default=None)
    parser.add_argument("--repair-timeout-seconds", type=int, help="Explicit per-repair worker budget")
    parser.add_argument(
        "--approved-v4-repair-cycles", type=int, default=0,
        help="Explicit maintainer-approved follow-up V4 repair cycles; each cycle permits three closed repairs",
    )
    parser.add_argument(
        "--v4-repair-approval-reference",
        help="Required non-empty maintainer approval reference when approving follow-up V4 repair cycles",
    )
    args = parser.parse_args()
    if args.repair_timeout_seconds is not None:
        if args.repair_timeout_seconds <= 0:
            parser.error("repair timeout must be positive")
        import semantic_worker_transport_patch as transport
        transport._REPAIR_TIMEOUT_SECONDS = args.repair_timeout_seconds
    if args.approved_v4_repair_cycles < 0:
        parser.error("approved V4 repair cycles must be non-negative")
    if args.approved_v4_repair_cycles and not (
        isinstance(args.v4_repair_approval_reference, str) and args.v4_repair_approval_reference.strip()
    ):
        parser.error("approved V4 repair cycles require --v4-repair-approval-reference")
    if args.v4_repair_approval_reference and not args.approved_v4_repair_cycles:
        parser.error("V4 repair approval reference requires approved V4 repair cycles")
    import semantic_alignment_repair_patch as alignment
    alignment.configure_approved_v4_repair_cycles(args.approved_v4_repair_cycles)
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
        result = {"status": "repair-vdd", "reason": str(exc)}
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") in {"plan-ready", "recommendation-only"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
