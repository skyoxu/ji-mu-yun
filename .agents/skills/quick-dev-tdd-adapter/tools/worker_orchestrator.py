"""Bounded model-worker orchestration for Quick Dev Q2/Q4/Q6.

Model workers may mutate only their declared write set. They never write process
receipts, observations, runtime edges, slice-ready, or implementation-complete.
Every invocation snapshots repository bytes before/after and returns a
non-authoritative mutation result for deterministic stage gates to consume.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Mapping, Sequence

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[3]
SC = ROOT / "scripts" / "sc"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(SC) not in sys.path:
    sys.path.insert(0, str(SC))

from _llm_backend import inspect_llm_backend, resolve_llm_backend, run_llm_exec
from current_router import validate_expected_red
from runtime_evidence import load_json, safe_relative, sha256_bytes, sha256_value

WorkerMutator = Callable[[Path, Mapping[str, Any]], None]


def _inside(root: Path, raw: str) -> Path:
    relative = safe_relative(raw)
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"worker path escapes repository: {raw}") from exc
    return path


def _repo_paths(root: Path) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard", "-z"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode == 0:
            return sorted({part.decode("utf-8", errors="strict") for part in proc.stdout.split(b"\0") if part})
    except (OSError, UnicodeError):
        pass
    result: list[str] = []
    excluded = {".git", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache"}
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if any(part in excluded for part in Path(relative).parts):
            continue
        result.append(relative)
    return sorted(set(result))


def workspace_snapshot(root: Path) -> dict[str, str | None]:
    state: dict[str, str | None] = {}
    for raw in _repo_paths(root):
        path = _inside(root, raw)
        state[raw] = sha256_bytes(path.read_bytes()) if path.is_file() and not path.is_symlink() else None
    return state


def changed_paths(before: Mapping[str, str | None], after: Mapping[str, str | None]) -> list[str]:
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))


def _matches(raw: str, declared: Sequence[str]) -> bool:
    path = safe_relative(raw)
    for item in declared:
        root = safe_relative(str(item)).rstrip("/")
        if path == root or path.startswith(root + "/"):
            return True
    return False


def _validate_delta(changed: Sequence[str], *, allowed: Sequence[str], forbidden: Sequence[str], label: str) -> None:
    if not allowed:
        raise ValueError(f"{label} write set is empty")
    for raw in changed:
        path = safe_relative(raw)
        if not _matches(path, allowed) or _matches(path, forbidden):
            raise ValueError(f"{label} write-set violation: {path}")


def _agent_context(plan_dir: Path, slice_id: str) -> dict[str, Any]:
    path = plan_dir / "agent-context" / slice_id / "agent-context.json"
    if not path.is_file() or path.is_symlink():
        raise ValueError("agent-context projection missing")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("slice_id") != slice_id:
        raise ValueError("agent-context projection invalid")
    required = {
        "requirement_ids", "obligation_ids", "acceptance_ids", "source_refs", "contracts",
        "allowed_paths", "forbidden_paths", "selector_intents", "validation_commands",
    }
    if any(key not in value for key in required):
        raise ValueError("agent-context projection incomplete")
    return value


def _slice(bundle: Mapping[str, Any], slice_id: str) -> Mapping[str, Any]:
    matches = [item for item in bundle.get("slices", []) if isinstance(item, Mapping) and item.get("slice_id") == slice_id]
    if len(matches) != 1:
        raise ValueError("slice identity missing or ambiguous")
    return matches[0]


def _worker_payload(
    *,
    bundle: Mapping[str, Any],
    slice_item: Mapping[str, Any],
    context: Mapping[str, Any],
    stage: str,
    predecessor: Mapping[str, Any] | None,
) -> dict[str, Any]:
    acceptance_ids = set(slice_item.get("acceptance_ids", []))
    acceptances = [item for item in bundle.get("acceptances", []) if isinstance(item, Mapping) and item.get("acceptance_id") in acceptance_ids]
    failure_ids = set(slice_item.get("failure_intent_ids", []))
    failure_intents = [item for item in bundle.get("failure_intents", []) if isinstance(item, Mapping) and item.get("failure_intent_id") in failure_ids]
    return {
        "stage": stage,
        "plan_id": bundle.get("plan_id"),
        "slice": dict(slice_item),
        "agent_context": dict(context),
        "acceptances": acceptances,
        "failure_intents": failure_intents,
        "predecessor": dict(predecessor) if isinstance(predecessor, Mapping) else None,
    }


def _prompt(stage: str, payload: Mapping[str, Any], *, allowed: Sequence[str], forbidden: Sequence[str]) -> str:
    goals = {
        "red-author": (
            "Create or minimally edit only the bound test/fixture files to check the declared real production behavior. Existing behavior may pass; never force it to fail. "
            "Do not modify production code, plan/evidence, or hard-code an unconditional failure. "
            "Bind each required assertion to its test using @pytest.mark.cer_assertion('ASSERTION_ID'). "
            "Parameter instances carrying that marker are all required, including deselected ones. "
            "Emit the corresponding FAILURE_ID only before the target behavior assertion fails. "
            "A marker binds a case; it is not execution evidence. Do not use skip/xfail to satisfy a requirement."
        ),
        "implementation": (
            "Implement the smallest production change that fixes the clean expected RED. Do not modify selector, test, fixture, plan, descriptor, or evidence bytes."
        ),
        "refactor": (
            "Refactor the already-GREEN production implementation without changing observable behavior or selector semantics. Do not modify tests, fixtures, plan, descriptor, or evidence bytes."
        ),
    }
    return (
        "You are a bounded Quick Dev worker. " + goals[stage] + "\n"
        + "Allowed repository-relative paths: " + json.dumps(list(allowed), ensure_ascii=False) + "\n"
        + "Forbidden repository-relative paths: " + json.dumps(list(forbidden), ensure_ascii=False) + "\n"
        + "Use only the supplied slice-scoped context; do not reinterpret the full requirements directory. "
        + "Do not write pass/status/receipt/observation/runtime-edge/completion artifacts.\nINPUT:\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def _invoke(
    *,
    root: Path,
    stage: str,
    payload: Mapping[str, Any],
    allowed: Sequence[str],
    forbidden: Sequence[str],
    timeout_seconds: int,
    backend: str | None,
    worker_mutator: WorkerMutator | None,
) -> dict[str, Any]:
    before = workspace_snapshot(root)
    started = time.perf_counter()
    output_sha: str | None = None
    trace = ""
    argv: list[str] = []
    backend_name = "injected-test-worker" if worker_mutator else resolve_llm_backend(backend)
    if worker_mutator is None:
        info = inspect_llm_backend(backend_name)
        if not info.get("available"):
            return {
                "schema": "quick-dev.worker-result.v1",
                "stage": stage,
                "status": "environment-blocked",
                "backend": backend_name,
                "blocking_errors": list(info.get("blocking_errors") or []),
                "changed_paths": [],
                "authorizes_evidence": False,
                "authorizes": [],
            }
        with tempfile.TemporaryDirectory(prefix=f"quick-dev-{stage}-") as raw:
            output = Path(raw) / "last-message.txt"
            code, trace, argv = run_llm_exec(
                backend=backend_name,
                root=root,
                prompt=_prompt(stage, payload, allowed=allowed, forbidden=forbidden),
                output_last_message=output,
                timeout_sec=timeout_seconds,
                codex_configs=["model_reasoning_effort=\"high\""],
                codex_sandbox="workspace-write",
            )
            if output.is_file():
                output_sha = sha256_bytes(output.read_bytes())
            if code != 0:
                after = workspace_snapshot(root)
                changed = changed_paths(before, after)
                if changed:
                    _validate_delta(changed, allowed=allowed, forbidden=forbidden, label=stage)
                return {
                    "schema": "quick-dev.worker-result.v1", "stage": stage, "status": "worker-failed",
                    "backend": backend_name, "exit_code": code, "trace_sha256": sha256_bytes(trace.encode("utf-8")),
                    "argv_sha256": sha256_value(argv), "output_sha256": output_sha,
                    "changed_paths": changed, "authorizes_evidence": False, "authorizes": [],
                }
    else:
        worker_mutator(root, payload)

    after = workspace_snapshot(root)
    changed = changed_paths(before, after)
    _validate_delta(changed, allowed=allowed, forbidden=forbidden, label=stage)
    duration_ms = int((time.perf_counter() - started) * 1000)
    return {
        "schema": "quick-dev.worker-result.v1",
        "stage": stage,
        "status": "worker-changes-valid",
        "backend": backend_name,
        "changed_paths": changed,
        "before_sha256": sha256_value(before),
        "after_sha256": sha256_value(after),
        "duration_ms": duration_ms,
        "trace_sha256": sha256_bytes(trace.encode("utf-8")) if trace else None,
        "argv_sha256": sha256_value(argv) if argv else None,
        "output_sha256": output_sha,
        "authorizes_evidence": False,
        "authorizes": [],
    }


def run_red_author(
    *,
    workspace: Path,
    plan_dir: Path,
    semantic_plan: Path,
    slice_id: str,
    timeout_seconds: int = 300,
    backend: str | None = None,
    worker_mutator: WorkerMutator | None = None,
) -> dict[str, Any]:
    bundle = load_json(semantic_plan)
    selected = _slice(bundle, slice_id)
    context = _agent_context(plan_dir, slice_id)
    test_paths = sorted(set(str(x) for x in selected.get("execution_snapshot_paths", [])) | set(str(x) for x in selected.get("planned_new_files", [])))
    production = [str(x) for x in selected.get("production_owners", [])]
    payload = _worker_payload(bundle=bundle, slice_item=selected, context=context, stage="red-author", predecessor=None)
    return _invoke(
        root=workspace, stage="red-author", payload=payload, allowed=test_paths, forbidden=production,
        timeout_seconds=timeout_seconds, backend=backend, worker_mutator=worker_mutator,
    )


def run_implementation_worker(
    *,
    workspace: Path,
    plan_dir: Path,
    semantic_plan: Path,
    slice_id: str,
    red_stage_result: Mapping[str, Any],
    run_dir: Path | None = None,
    timeout_seconds: int = 600,
    backend: str | None = None,
    worker_mutator: WorkerMutator | None = None,
) -> dict[str, Any]:
    validate_expected_red(red_stage_result)
    bundle = load_json(semantic_plan)
    if "behavior_routing" in bundle:
        from behavior_routing import verify_stage, current_result
        if run_dir is None:
            raise ValueError("behavior-routing:worker-requires-explicit-run")
        descriptor = load_json(run_dir / "descriptors/red.json")
        recorded = load_json(run_dir / "canonical-evidence/red/stage-result.v2.json")
        if recorded != red_stage_result:
            raise ValueError("behavior-routing:worker-predecessor-stale")
        verify_stage(workspace, bundle, run_dir, descriptor)
        current_result(workspace, bundle, slice_id, recorded)
    selected = _slice(bundle, slice_id)
    context = _agent_context(plan_dir, slice_id)
    allowed = [str(x) for x in selected.get("allowed_write_paths", [])]
    forbidden = [str(x) for x in selected.get("execution_snapshot_paths", [])]
    payload = _worker_payload(bundle=bundle, slice_item=selected, context=context, stage="implementation", predecessor=red_stage_result)
    return _invoke(
        root=workspace, stage="implementation", payload=payload, allowed=allowed, forbidden=forbidden,
        timeout_seconds=timeout_seconds, backend=backend, worker_mutator=worker_mutator,
    )


def run_refactor_worker(
    *,
    workspace: Path,
    plan_dir: Path,
    semantic_plan: Path,
    slice_id: str,
    green_stage_result: Mapping[str, Any],
    run_dir: Path | None = None,
    timeout_seconds: int = 600,
    backend: str | None = None,
    worker_mutator: WorkerMutator | None = None,
) -> dict[str, Any]:
    if green_stage_result.get("stage") != "green" or green_stage_result.get("predicate_result") is not True or green_stage_result.get("verification_outcome") != "pass":
        raise ValueError("refactor worker requires clean GREEN")
    bundle = load_json(semantic_plan)
    if "behavior_routing" in bundle:
        from behavior_routing import verify_stage, current_result
        if run_dir is None:
            raise ValueError("behavior-routing:worker-requires-explicit-run")
        descriptor = load_json(run_dir / "descriptors/green.json")
        recorded = load_json(run_dir / "canonical-evidence/green/stage-result.v2.json")
        if recorded != green_stage_result:
            raise ValueError("behavior-routing:worker-predecessor-stale")
        verify_stage(workspace, bundle, run_dir, descriptor)
        current_result(workspace, bundle, slice_id, recorded)
    selected = _slice(bundle, slice_id)
    context = _agent_context(plan_dir, slice_id)
    allowed = [str(x) for x in selected.get("allowed_write_paths", [])]
    forbidden = [str(x) for x in selected.get("execution_snapshot_paths", [])]
    payload = _worker_payload(bundle=bundle, slice_item=selected, context=context, stage="refactor", predecessor=green_stage_result)
    return _invoke(
        root=workspace, stage="refactor", payload=payload, allowed=allowed, forbidden=forbidden,
        timeout_seconds=timeout_seconds, backend=backend, worker_mutator=worker_mutator,
    )
