#!/usr/bin/env python3
"""Stable VDD Chapter 4/5/6 compiler CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".agents" / "skills" / "vdd-execution-plan" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import semantic_feasibility_patch  # noqa: F401  # installs normative planned-new-file V7 rule
from semantic_compiler_authority import compile_plan
import semantic_compiler as semantic_compiler


def _configure_v1_reuse_from_git(ref: str, requirements: Path) -> None:
    """Bind V1 peer reuse to exact predecessor anchor text, never only a file path."""
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", ref):
        raise ValueError("V1 reuse Git reference is invalid")
    relative = requirements.resolve().relative_to(ROOT.resolve()).as_posix()
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{ref}:{relative}"],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise ValueError("V1 reuse predecessor source is unavailable")
    try:
        text = completed.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("V1 reuse predecessor source is not UTF-8") from exc
    identities = {
        f"{relative}#{requirement_id}": semantic_compiler.sha256_bytes(source_text.encode("utf-8"))
        for requirement_id, source_text, _line in semantic_compiler._sections(text)
    }
    if not identities:
        raise ValueError("V1 reuse predecessor has no requirement anchors")
    semantic_compiler.configure_v1_reuse_predecessor_text_hashes(identities)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--profile", choices=("standard", "resumable", "self-hosted"), default="standard")
    parser.add_argument("--companion", type=Path, action="append", default=[])
    parser.add_argument("--worker-cache", type=Path)
    parser.add_argument("--v3-contract-repair", type=Path,
                        help="Explicit source-bound V3 candidate corrections; independent V4 remains required")
    parser.add_argument("--result-json", type=Path, help="Write the compiler result even on a caught failure")
    parser.add_argument("--recommendation-only", action="store_true")
    parser.add_argument("--resume-from", choices=("first-failed-stage",), default=None)
    parser.add_argument(
        "--v1-reuse-from-git-ref",
        help="Explicit Git predecessor whose unchanged requirement-anchor text may reuse V1 cache entries",
    )
    parser.add_argument(
        "--v1-reuse-from-plan", type=Path,
        help="Explicit plan-ready predecessor bundle whose V4-supported V1 obligations may be rebound per unchanged anchor",
    )
    parser.add_argument("--repair-timeout-seconds", type=int, help="Explicit per-repair worker budget")
    parser.add_argument(
        "--approved-v4-repair-cycles", type=int, default=0,
        help="Explicit maintainer-approved follow-up V4 repair cycles; each cycle permits three closed repairs",
    )
    parser.add_argument(
        "--v4-repair-approval-reference",
        help="Required non-empty maintainer approval reference when approving follow-up V4 repair cycles",
    )
    parser.add_argument("--repair-quick-dev-handoff-from", type=Path,
                        help="Repair execution bindings of a reviewed plan into a distinct successor")
    parser.add_argument("--handoff-test-root", default="scripts/sc/tests/tc_d1_cer")
    parser.add_argument("--runtime-red-intent", action="append", default=[],
                        help="Explicit reviewed runtime intent to bind as expected RED; requires handoff repair")
    args = parser.parse_args()
    if args.runtime_red_intent and not args.repair_quick_dev_handoff_from:
        parser.error("--runtime-red-intent requires --repair-quick-dev-handoff-from")
    if args.repair_quick_dev_handoff_from:
        if any((args.companion, args.worker_cache, args.recommendation_only, args.resume_from,
                args.v1_reuse_from_git_ref, args.v1_reuse_from_plan, args.repair_timeout_seconds,
                args.approved_v4_repair_cycles, args.v4_repair_approval_reference, args.v3_contract_repair)):
            parser.error("handoff repair cannot combine semantic compilation or worker overrides")
        from quick_dev_handoff import publish_repair
        try:
            result = publish_repair(root=ROOT, requirements=args.requirements,
                predecessor=args.repair_quick_dev_handoff_from, out_dir=args.out_dir,
                test_root=args.handoff_test_root, runtime_red_intents=args.runtime_red_intent)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result = {"status": "repair-vdd", "reason": str(exc)}
        if args.result_json:
            args.result_json.parent.mkdir(parents=True, exist_ok=True)
            args.result_json.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("status") == "plan-ready" else 1
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
    if args.v1_reuse_from_git_ref:
        try:
            _configure_v1_reuse_from_git(args.v1_reuse_from_git_ref, args.requirements)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            parser.error(str(exc))
    if args.v1_reuse_from_plan:
        try:
            semantic_compiler.configure_v1_reuse_predecessor_plan(args.v1_reuse_from_plan.resolve())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
    import semantic_alignment_repair_patch as alignment
    alignment.configure_approved_v4_repair_cycles(args.approved_v4_repair_cycles)
    if args.v3_contract_repair:
        if args.worker_cache or args.recommendation_only or args.companion:
            parser.error("V3 candidate repair cannot combine fixtures, recommendation-only or companions")
        import semantic_v3_contract_repair as candidate_repair
        try:
            state_path = args.out_dir / "compiler-state.v1.json"
            if state_path.exists() and json.loads(state_path.read_text(encoding="utf-8")).get("state") == "plan-ready":
                raise ValueError("V3 candidate repair requires a failed or unpublished output directory")
            candidate_repair.install(candidate_repair.load_repair(args.v3_contract_repair, args.requirements))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parser.error(str(exc))
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
