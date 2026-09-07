#!/usr/bin/env python3
"""Live Chapter 4/5/6 blind benchmark.

This is acceptance evidence, not a deterministic fixture substitute.  With a
real LLM backend it creates a detached worktree at the current HEAD and drives a
fresh stateful requirement through live VDD semantic workers and the current
Quick Dev bounded RED-author / implementation / refactor workers.  Without a
live backend it emits an explicit environment-blocked receipt and never claims
product acceptance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
SC = ROOT / "scripts" / "sc"
if str(SC) not in sys.path:
    sys.path.insert(0, str(SC))

from _llm_backend import inspect_llm_backend, resolve_llm_backend

SCHEMA = "ch456.live-blind-benchmark.v1"
TASK_ID = "CH456-BLIND-IDEMPOTENCY-LEDGER-V1"
TASK_REL = Path("benchmarks/ch456-live-blind/idempotency-ledger-v1")
DEFAULT_LIMIT_SECONDS = 3600


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(value: Any) -> str:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(root), text=True, capture_output=True, check=check)


def _backend_probe(requested: str | None) -> dict[str, Any]:
    backend = resolve_llm_backend(requested)
    info = dict(inspect_llm_backend(backend))
    return {
        "backend": backend,
        "available": bool(info.get("available")),
        "model": info.get("model"),
        "version": info.get("sdk_version") or info.get("executable_version") or info.get("version"),
        "blocking_errors": list(info.get("blocking_errors") or []),
    }


def _blocked_evidence(*, head: str, backend: Mapping[str, Any], limit_seconds: int) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "task_id": TASK_ID,
        "status": "environment-blocked",
        "execution_attempted": False,
        "source_head": head,
        "backend": dict(backend),
        "profile": "standard",
        "task_scale": {"requirements": 1, "independent_behaviors": 3, "production_owners": 1, "verification_lane": "unit"},
        "limit_seconds": limit_seconds,
        "elapsed_seconds": None,
        "under_60_minutes": None,
        "vdd_worker_calls": 0,
        "vdd_schema_repairs": 0,
        "quick_dev_worker_calls": 0,
        "retry_count": 0,
        "repeated_fingerprint_stops": 0,
        "final_status": None,
        "product_acceptance_proven": False,
        "authorizes": [],
    }


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _parse_child_evidence(stdout: str) -> dict[str, Any] | None:
    """Return the last structured CH456 evidence object even for a failed child."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        return None
    return value


def _task_source() -> str:
    # The domain and behavior set are intentionally distinct from the rate-limiter
    # fixture used while designing the toolchain.
    prefix = TASK_REL.as_posix()
    return f"""# FR-301
An idempotency reservation ledger must be implemented as one bounded stateful slice.

Production owner: `{prefix}/src/idempotency_ledger.py`.
The RED author must create `{prefix}/tests/test_idempotency_ledger.py` and may use the existing fixture `{prefix}/tests/cases.json`.
The production implementation may modify only the production owner above.
The validation command is `py -3 -m pytest {prefix}/tests/test_idempotency_ledger.py -q -p no:cacheprovider`.
The RED test must call the real production owner and, whenever a declared Acceptance assertion fails, emit the matching VDD failure intent as `FAILURE_ID:<failure_id>` before the assertion fails.

The ledger has three independently observable required behaviors, all of which must be exercised by the same selector family:

1. Claiming a key that is already active at `now < expires_at` returns `duplicate` rather than `accepted`.
2. Claiming with `ttl_seconds <= 0` returns `invalid-ttl` and must not create an active reservation.
3. Releasing a key that is not active returns `not-found` rather than reporting a successful release.

The existing skeleton intentionally returns success for every operation, so all three forbidden behaviors are observable before implementation.  A legal GREEN must change production only; GREEN and REFACTOR must preserve the RED selector, fixture and assertions.
"""


def _prepare_task(root: Path) -> tuple[Path, Path]:
    task = root / TASK_REL
    if task.exists():
        raise RuntimeError("blind benchmark task path already exists in candidate; task is no longer fresh")
    (task / "src").mkdir(parents=True)
    (task / "tests").mkdir(parents=True)
    requirements = task / "requirements.md"
    requirements.write_text(_task_source(), encoding="utf-8")
    (task / "src" / "idempotency_ledger.py").write_text(
        "class IdempotencyLedger:\n"
        "    def claim(self, key, now, ttl_seconds):\n"
        "        return 'accepted'\n\n"
        "    def release(self, key):\n"
        "        return 'released'\n",
        encoding="utf-8",
    )
    (task / "tests" / "cases.json").write_text(
        json.dumps({"duplicate": {"key": "alpha", "now": 5, "ttl_seconds": 10}, "invalid_ttl": 0, "missing_release": "missing"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return task, requirements


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected object: {path}")
    return value


def _inner(*, backend: str, limit_seconds: int) -> dict[str, Any]:
    root = ROOT
    started_wall = _now()
    started = time.perf_counter()
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    task, requirements = _prepare_task(root)

    vdd = root / ".agents" / "skills" / "vdd-execution-plan" / "scripts"
    quick = root / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
    for path in (vdd, quick):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    from semantic_compiler_authority import compile_plan
    from stable_runner import (
        candidate_identity,
        _execute_named_stage,
        _materialize_named_descriptor,
        q0_recommendation,
        q1_preflight,
        q2_author_red,
        q4_implementation_worker,
        q6_refactor_worker_and_run,
    )
    from current_router import successor_descriptor
    from coverage_predicates import publish_implementation_complete, validate_slice_ready
    from runtime_evidence import create_json, load_json, sha256_value
    from stage_pipeline import execute_stage

    evidence_root = root / "logs" / "ch456-live-blind"
    plan = evidence_root / "plan"
    run_dir = root / "logs" / "tdd-adapter" / "ch456-live-blind" / "RUN-BLIND-001"
    (run_dir / "descriptors").mkdir(parents=True, exist_ok=True)
    router_state = evidence_root / "router-state.json"
    snapshot_state = evidence_root / "snapshot-state.json"
    snapshot_state.parent.mkdir(parents=True, exist_ok=True)
    snapshot_state.write_text('{"state":"benchmark-frozen"}\n', encoding="utf-8")

    transitions: list[dict[str, Any]] = []
    quick_workers: list[dict[str, Any]] = []

    plan_result = compile_plan(requirements=requirements, out_dir=plan, profile="standard", worker_cache=None)
    if plan_result.get("status") != "plan-ready":
        raise RuntimeError("live VDD did not reach plan-ready: " + json.dumps(plan_result, sort_keys=True)[:1200])
    semantic = plan / "semantic-plan-bundle.v1.json"
    bundle = load_json(semantic)
    obligations = [item for item in bundle.get("obligations", []) if isinstance(item, Mapping) and item.get("status") == "active"]
    slices = [item for item in bundle.get("slices", []) if isinstance(item, Mapping)]
    if len(obligations) < 3:
        raise RuntimeError("blind VDD collapsed the three independent source behaviors")
    if len(slices) != 1:
        raise RuntimeError(f"blind benchmark contract expects one cohesive slice, observed {len(slices)}")
    slice_id = str(slices[0]["slice_id"])

    contract = plan / "agent-context" / slice_id / "agent-context.json"
    validator = quick / "independent_judge_v2.py"
    roots = [
        {"root_kind": "candidate_tree", "repository_relative_posix_path": (TASK_REL / "src").as_posix(), "inclusion_reason": "blind production owner"},
        {"root_kind": "plan", "repository_relative_posix_path": semantic.relative_to(root).as_posix(), "inclusion_reason": "live semantic plan"},
        {"root_kind": "contract", "repository_relative_posix_path": contract.relative_to(root).as_posix(), "inclusion_reason": "slice agent context"},
        {"root_kind": "descriptor", "repository_relative_posix_path": (run_dir / "descriptors").relative_to(root).as_posix(), "inclusion_reason": "frozen descriptors"},
        {"root_kind": "fixture", "repository_relative_posix_path": (TASK_REL / "tests").as_posix(), "inclusion_reason": "blind test and fixture set"},
        {"root_kind": "source", "repository_relative_posix_path": requirements.relative_to(root).as_posix(), "inclusion_reason": "fresh source requirement"},
        {"root_kind": "validator_judge", "repository_relative_posix_path": validator.relative_to(root).as_posix(), "inclusion_reason": "independent judge"},
        {"root_kind": "plan_state_transition", "repository_relative_posix_path": snapshot_state.relative_to(root).as_posix(), "inclusion_reason": "frozen benchmark state root"},
    ]

    def route(state: str) -> dict[str, Any]:
        router_state.write_text(json.dumps({"state": state}, sort_keys=True) + "\n", encoding="utf-8")
        result = q0_recommendation(
            semantic=semantic,
            slice_id=slice_id,
            profile="standard",
            state_path=router_state,
            changed_paths=[],
            change_kinds=[],
            snapshot_roots=roots,
            source_commit=head,
            base_commit=head,
            observation_index=[],
        )
        transitions.append({"state": state, "recommended_action": result.get("recommended_action"), "reason_code": result.get("reason_code")})
        return result

    if route("planned-only").get("recommended_action") != "run-preflight":
        raise RuntimeError("Q0 did not route planned-only to preflight")
    preflight = q1_preflight(semantic=semantic, slice_id=slice_id, profile="standard")
    if preflight.get("status") != "preflight-passed":
        raise RuntimeError("Q1 preflight failed: " + json.dumps(preflight, sort_keys=True)[:1000])
    if route("preflight-passed").get("recommended_action") != "author-red":
        raise RuntimeError("Q0 did not route preflight-passed to author-red")

    red_author = q2_author_red(
        semantic=semantic,
        slice_id=slice_id,
        run_dir=run_dir,
        profile="standard",
        timeout_seconds=min(600, limit_seconds),
        backend=backend,
    )
    quick_workers.append(dict(red_author.get("worker") or {}))
    if "behavior_routing" in bundle and red_author.get("status") == "probe-materialized":
        # ADR-0041: use the current probe protocol without changing the blind RED gate.
        if route("probe-materialized").get("recommended_action") != "run-probe":
            raise RuntimeError("Q0 did not route probe-materialized to run-probe")
        probe = _execute_named_stage(semantic, run_dir, "probe", "standard")
        if probe.get("predicate_result") is not True:
            raise RuntimeError("Behavior probe failed: " + json.dumps(probe, sort_keys=True)[:1200])
        red_path = _materialize_named_descriptor(semantic, run_dir, "red")
        red_author = {**red_author, "status": "red-materialized", "descriptor_ref": red_path.relative_to(root).as_posix()}
    if red_author.get("status") != "red-materialized":
        raise RuntimeError("Q2 RED author failed: " + json.dumps(red_author, sort_keys=True)[:1200])
    if route("red-materialized").get("recommended_action") != "run-red":
        raise RuntimeError("Q0 did not route red-materialized to run-red")

    red_path = root / str(red_author["descriptor_ref"])
    red = execute_stage(workspace=root, semantic_plan=semantic, run_dir=run_dir, descriptor_path=red_path, profile_identity="standard")
    if red.get("predicate_result") is not True or red.get("failure_family") != "expected-red":
        raise RuntimeError("Q3 did not observe clean expected RED: " + json.dumps(red, sort_keys=True)[:1200])
    if route("red-observed").get("recommended_action") != "implement":
        raise RuntimeError("Q0 did not route expected RED to implementation")

    implementation = q4_implementation_worker(
        semantic=semantic,
        slice_id=slice_id,
        run_dir=run_dir,
        snapshot_roots=roots,
        source_commit=head,
        base_commit=head,
        timeout_seconds=min(900, limit_seconds),
        backend=backend,
    )
    quick_workers.append(dict(implementation.get("worker") or {}))
    if implementation.get("status") != "implementation-successor":
        raise RuntimeError("Q4 implementation worker failed: " + json.dumps(implementation, sort_keys=True)[:1200])
    if route("implementation-successor").get("recommended_action") != "run-green":
        raise RuntimeError("Q0 did not route implementation successor to GREEN")

    green_path = root / str(implementation["green_descriptor_ref"])
    green = execute_stage(workspace=root, semantic_plan=semantic, run_dir=run_dir, descriptor_path=green_path, profile_identity="standard")
    if green.get("predicate_result") is not True or green.get("verification_outcome") != "pass":
        raise RuntimeError("Q5 GREEN failed: " + json.dumps(green, sort_keys=True)[:1200])
    if route("green-observed").get("recommended_action") != "run-refactor":
        raise RuntimeError("Q0 did not route GREEN to REFACTOR")

    refactor = q6_refactor_worker_and_run(
        semantic=semantic,
        slice_id=slice_id,
        run_dir=run_dir,
        profile="standard",
        timeout_seconds=min(900, limit_seconds),
        backend=backend,
    )
    quick_workers.append(dict(refactor.get("worker") or {}))
    if refactor.get("status") != "refactor-observed":
        raise RuntimeError("Q6 refactor failed: " + json.dumps(refactor, sort_keys=True)[:1200])
    if "behavior_routing" in bundle:
        from behavior_routing import read_route
        behavior_route = read_route(root, bundle, run_dir, slice_id)
        if any(row["disposition"] == "present" for row in behavior_route["behavior_dispositions"]):
            regression = _execute_named_stage(semantic, run_dir, "regression", "standard")
            if regression.get("predicate_result") is not True:
                raise RuntimeError("Present behavior regression failed")
        expected_action = "route-behaviors"
    else:
        expected_action = "validate-slice"
    if route("refactor-observed").get("recommended_action") != expected_action:
        raise RuntimeError("Q0 did not route REFACTOR to slice validation")

    # Freeze the terminal descriptor before Q7 so Q7 and Q8 observe the same
    # descriptor-root bytes.  The terminal process itself still executes only
    # after slice-ready, preserving lifecycle order.
    red_descriptor = load_json(red_path)
    current_identity = candidate_identity(root, bundle, slice_id)
    if "behavior_routing" in bundle:
        terminal_path = _materialize_named_descriptor(semantic, run_dir, "terminal")
    else:
        terminal_descriptor = successor_descriptor(
            red_descriptor,
            stage="terminal",
            run_id=run_dir.name,
            candidate_hash=current_identity["candidate_hash"],
            terminal_argv=red_descriptor["argv"],
        )
        terminal_path = run_dir / "descriptors" / "terminal.json"
        create_json(terminal_path, terminal_descriptor)

    ready_path = run_dir / "slice-ready.json"
    ready = validate_slice_ready(
        workspace=root,
        semantic_plan=semantic,
        run_root=run_dir,
        slice_id=slice_id,
        snapshot_roots=roots,
        source_commit=head,
        base_commit=head,
        out=ready_path,
    )
    if ready.get("status") != "pass":
        raise RuntimeError("Q7 slice-ready failed")
    if route("slice-ready").get("recommended_action") != "run-terminal":
        raise RuntimeError("Q0 did not route slice-ready to terminal")

    terminal = execute_stage(workspace=root, semantic_plan=semantic, run_dir=run_dir, descriptor_path=terminal_path, profile_identity="standard")
    if terminal.get("predicate_result") is not True or terminal.get("verification_outcome") != "pass":
        raise RuntimeError("terminal process failed: " + json.dumps(terminal, sort_keys=True)[:1200])

    predecessor = {
        "slice_id": slice_id,
        "run_root": run_dir.relative_to(root).as_posix(),
        "result_ref": ready_path.relative_to(root).as_posix(),
        "result_sha256": sha256_value(ready),
    }
    complete_path = run_dir / "implementation-complete.json"
    complete = publish_implementation_complete(
        workspace=root,
        semantic_plan=semantic,
        predecessors=[predecessor],
        snapshot_roots=roots,
        source_commit=head,
        base_commit=head,
        out=complete_path,
        profile="standard",
    )
    if complete.get("status") != "pass":
        raise RuntimeError("Q8 implementation-complete failed")
    stop = route("whole-plan-terminal")
    if stop.get("recommended_action") != "stop":
        raise RuntimeError("Q0 did not terminate completed lineage")

    receipts = sorted((plan / ".compiler-work" / "worker-receipts").glob("*.json"))
    receipt_values = [_load(path) for path in receipts]
    repairs = sum(1 for item in receipt_values if item.get("schema_repair_attempted") is True)
    worker_calls = [item for item in quick_workers if item]
    if not receipts or any(str(item.get("model", "")).startswith("injected-") for item in receipt_values):
        raise RuntimeError("blind benchmark did not use live VDD workers")
    if len(worker_calls) < 3 or any(item.get("backend") == "injected-test-worker" for item in worker_calls):
        raise RuntimeError("blind benchmark did not use all three live Quick Dev workers")
    if any(item.get("status") != "worker-changes-valid" for item in worker_calls):
        raise RuntimeError("one or more live Quick Dev workers did not produce a valid bounded mutation")

    elapsed = time.perf_counter() - started
    return {
        "schema": SCHEMA,
        "task_id": TASK_ID,
        "status": "pass" if elapsed <= limit_seconds else "time-budget-failed",
        "execution_attempted": True,
        "started_at": started_wall,
        "finished_at": _now(),
        "source_head": head,
        "task_source_sha256": _sha(_task_source()),
        "task_was_absent_at_start": True,
        "profile": "standard",
        "task_scale": {"requirements": 1, "independent_behaviors": 3, "active_obligations": len(obligations), "slices": len(slices), "production_owners": 1, "verification_lane": "unit"},
        "limit_seconds": limit_seconds,
        "elapsed_seconds": round(elapsed, 3),
        "under_60_minutes": elapsed <= limit_seconds,
        "vdd_worker_calls": len(receipts),
        "vdd_schema_repairs": repairs,
        "quick_dev_worker_calls": len(worker_calls),
        "quick_dev_worker_stages": [item.get("stage") for item in worker_calls],
        "retry_count": repairs,
        "repeated_fingerprint_stops": 0,
        "router_transitions": transitions,
        "final_status": complete.get("status"),
        "runtime_closure_tuple_count": len(complete.get("runtime_closure_tuples", [])),
        "product_acceptance_proven": bool(elapsed <= limit_seconds and complete.get("status") == "pass"),
        "authorizes": [],
    }


def _outer(*, out: Path, backend_requested: str | None, limit_seconds: int, require_live: bool,
           repair_timeout_seconds: int | None = None) -> int:
    head = _git(ROOT, "rev-parse", "HEAD").stdout.strip()
    probe = _backend_probe(backend_requested)
    if not probe["available"]:
        evidence = _blocked_evidence(head=head, backend=probe, limit_seconds=limit_seconds)
        evidence["repair_timeout_seconds_override"] = repair_timeout_seconds
        _write(out, evidence)
        print(json.dumps(evidence, sort_keys=True))
        return 2 if require_live else 0

    with tempfile.TemporaryDirectory(prefix="ch456-live-blind-") as raw:
        worktree = Path(raw) / "worktree"
        add = _git(ROOT, "worktree", "add", "--detach", str(worktree), head, check=False)
        if add.returncode != 0:
            evidence = {**_blocked_evidence(head=head, backend=probe, limit_seconds=limit_seconds), "status": "harness-failed", "execution_attempted": True, "reason": "git-worktree-add-failed", "stderr_sha256": _sha(add.stderr)}
            evidence["repair_timeout_seconds_override"] = repair_timeout_seconds
            _write(out, evidence)
            print(json.dumps(evidence, sort_keys=True))
            return 1
        try:
            command = [
                sys.executable,
                str(worktree / "scripts" / "quick_dev" / "run_live_blind_benchmark.py"),
                "--inner",
                "--backend",
                str(probe["backend"]),
                "--limit-seconds",
                str(limit_seconds),
                *(["--repair-timeout-seconds", str(repair_timeout_seconds)]
                  if repair_timeout_seconds is not None else []),
            ]
            completed = subprocess.run(command, cwd=str(worktree), text=True, capture_output=True, timeout=limit_seconds + 120, check=False)
            evidence = _parse_child_evidence(completed.stdout)
            if not isinstance(evidence, dict):
                evidence = {
                    "schema": SCHEMA,
                    "task_id": TASK_ID,
                    "status": "failed",
                    "execution_attempted": True,
                    "source_head": head,
                    "backend": probe,
                    "limit_seconds": limit_seconds,
                    "elapsed_seconds": None,
                    "under_60_minutes": None,
                    "product_acceptance_proven": False,
                    "child_exit_code": completed.returncode,
                    "reason": "child-evidence-unparseable",
                    "stdout_sha256": _sha(completed.stdout),
                    "stderr_sha256": _sha(completed.stderr),
                    "authorizes": [],
                }
            else:
                evidence["backend"] = probe
                evidence["child_exit_code"] = completed.returncode
            evidence["repair_timeout_seconds_override"] = repair_timeout_seconds
            _write(out, evidence)
            print(json.dumps(evidence, sort_keys=True))
            return 0 if evidence.get("status") == "pass" else 1
        except subprocess.TimeoutExpired as exc:
            evidence = {
                "schema": SCHEMA,
                "task_id": TASK_ID,
                "status": "time-budget-failed",
                "execution_attempted": True,
                "source_head": head,
                "backend": probe,
                "limit_seconds": limit_seconds,
                "elapsed_seconds": limit_seconds,
                "under_60_minutes": False,
                "product_acceptance_proven": False,
                "stdout_sha256": _sha(exc.stdout or ""),
                "stderr_sha256": _sha(exc.stderr or ""),
                "authorizes": [],
            }
            evidence["repair_timeout_seconds_override"] = repair_timeout_seconds
            _write(out, evidence)
            print(json.dumps(evidence, sort_keys=True))
            return 1
        finally:
            _git(ROOT, "worktree", "remove", "--force", str(worktree), check=False)
            _git(ROOT, "worktree", "prune", check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("ch456-live-blind-benchmark.json"))
    parser.add_argument("--backend")
    parser.add_argument("--limit-seconds", type=int, default=DEFAULT_LIMIT_SECONDS)
    parser.add_argument("--require-live", action="store_true")
    parser.add_argument("--repair-timeout-seconds", type=int, help="Explicit per-repair VDD worker budget")
    parser.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.repair_timeout_seconds is not None and args.repair_timeout_seconds <= 0:
        parser.error("repair timeout must be positive")
    if args.limit_seconds <= 0 or args.limit_seconds > DEFAULT_LIMIT_SECONDS:
        raise SystemExit("--limit-seconds must be in 1..3600")
    if args.inner:
        if not args.backend:
            raise SystemExit("inner benchmark requires --backend")
        # ADR-0041: the detached child must apply the same override as compile_plan.py.
        if args.repair_timeout_seconds is not None:
            vdd = ROOT / ".agents" / "skills" / "vdd-execution-plan" / "scripts"
            if str(vdd) not in sys.path:
                sys.path.insert(0, str(vdd))
            import semantic_worker_transport_patch as transport
            transport._REPAIR_TIMEOUT_SECONDS = args.repair_timeout_seconds
        try:
            result = _inner(backend=args.backend, limit_seconds=args.limit_seconds)
            result["repair_timeout_seconds_override"] = args.repair_timeout_seconds
            print(json.dumps(result, sort_keys=True))
            return 0 if result.get("status") == "pass" else 1
        except Exception as exc:
            failure = {
                "schema": SCHEMA,
                "task_id": TASK_ID,
                "status": "failed",
                "execution_attempted": True,
                "source_head": _git(ROOT, "rev-parse", "HEAD").stdout.strip(),
                "backend": {"backend": args.backend, "available": True},
                "limit_seconds": args.limit_seconds,
                "under_60_minutes": None,
                "product_acceptance_proven": False,
                "error_type": type(exc).__name__,
                "error": str(exc)[:1600],
                "repair_timeout_seconds_override": args.repair_timeout_seconds,
                "authorizes": [],
            }
            print(json.dumps(failure, sort_keys=True))
            return 1
    return _outer(out=args.out.resolve(), backend_requested=args.backend, limit_seconds=args.limit_seconds,
                  require_live=args.require_live, repair_timeout_seconds=args.repair_timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())

