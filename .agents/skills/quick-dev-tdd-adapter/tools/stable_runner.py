"""Stable deterministic Quick Dev CLI facade for Chapter 4/5/6 current plans."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[3]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from coverage_predicates import publish_implementation_complete, validate_slice_ready
from current_router import (
    materialize_descriptor,
    preflight,
    profile_contract,
    recommendation,
    successor_descriptor,
    validate_expected_red,
)
from detached_promotion import detached_bundle_metadata, validate_detached_bundle
from q4_q6_gates import begin_q4, finish_q4
from recovery_resolver import recover_current_run
from runtime_evidence import create_json, current_snapshot, load_json, safe_relative, sha256_bytes, sha256_value
from stage_pipeline import execute_stage
from worker_orchestrator import run_implementation_worker, run_red_author, run_refactor_worker


def _inside_root(path: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} is outside repository") from exc
    return resolved


def _semantic_plan(plan: Path) -> Path:
    plan = _inside_root(plan, "plan")
    semantic = plan / "semantic-plan-bundle.v1.json"
    if not semantic.is_file():
        raise ValueError("current semantic-plan-bundle.v1.json missing")
    return semantic


def _slice(bundle: Mapping[str, Any], slice_id: str) -> Mapping[str, Any]:
    slices = bundle.get("slices")
    if not isinstance(slices, list):
        raise ValueError("semantic plan slices missing")
    matches = [item for item in slices if isinstance(item, Mapping) and item.get("slice_id") == slice_id]
    if len(matches) != 1:
        raise ValueError("slice identity missing or ambiguous")
    return matches[0]


def _agent_context(plan_dir: Path, slice_id: str) -> Mapping[str, Any]:
    path = plan_dir / "agent-context" / slice_id / "agent-context.json"
    value = _load_json_object(path, "agent-context")
    if value.get("slice_id") != slice_id:
        raise ValueError("agent-context slice mismatch")
    return value


def candidate_identity(workspace: Path, bundle: Mapping[str, Any], slice_id: str) -> dict[str, Any]:
    """Compute a slice-scoped product/execution candidate identity without governance bytes."""
    selected = _slice(bundle, slice_id)
    refs = set()
    for field in ("production_owners", "planned_new_files", "execution_snapshot_paths"):
        values = selected.get(field, [])
        if not isinstance(values, list):
            raise ValueError(f"slice {field} invalid")
        for raw in values:
            refs.add(safe_relative(str(raw)))
    state: dict[str, str | None] = {}
    for ref in sorted(refs):
        path = (workspace / ref).resolve()
        try:
            path.relative_to(workspace.resolve())
        except ValueError as exc:
            raise ValueError("candidate path escapes repository") from exc
        if path.is_file() and not path.is_symlink():
            state[ref] = sha256_bytes(path.read_bytes())
        else:
            state[ref] = None
    material = {
        "schema": "quick-dev.slice-candidate-identity.v1",
        "plan_id": bundle.get("plan_id"),
        "plan_sha256": sha256_value(dict(bundle)),
        "slice_id": slice_id,
        "paths": state,
    }
    return {"schema": "quick-dev.slice-candidate-identity.v1", "candidate_hash": sha256_value(material), "paths": state}


def _load_json_list(path: Path, label: str) -> list[Mapping[str, Any]]:
    value = json.loads(_inside_root(path, label).read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{label} must contain JSON object list")
    return list(value)


def _load_json_object(path: Path, label: str, *, inside_repo: bool = True) -> Mapping[str, Any]:
    resolved = _inside_root(path, label) if inside_repo else path.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise ValueError(f"{label} is missing or unsafe")
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must contain JSON object")
    return value


def _descriptor_inputs(bundle: Mapping[str, Any], plan_dir: Path, slice_id: str) -> tuple[list[str], list[str], list[str]]:
    selected = _slice(bundle, slice_id)
    context = _agent_context(plan_dir, slice_id)
    commands = context.get("validation_commands")
    if not isinstance(commands, list) or not commands or not isinstance(commands[0], list) or not commands[0]:
        raise ValueError("agent-context validation command missing")
    argv = [str(item) for item in commands[0]]
    if any(not item for item in argv):
        raise ValueError("validation command contains empty argv")
    # A CER slice may distribute its assertion cases over several explicit
    # pytest commands.  Its stage selector must execute that whole declared
    # case surface, rather than silently treating only command zero as the
    # proof floor.  Combine only the mechanically equivalent, shell-free form
    # so heterogeneous commands retain their own explicit routing.
    normalized = [[str(item) for item in command] for command in commands]
    def pytest_parts(command: list[str]):
        offset = 2 if command[:2] == ["py", "-3"] else 1
        return offset if (len(command) >= offset + 3 and command[offset:offset + 2] == ["-m", "pytest"]
                          and all(item == "-q" or not item.startswith("-") for item in command[offset + 2:])) else None
    pytest_offsets = [pytest_parts(command) for command in normalized]
    pytest_commands = (
        len(normalized) > 1
        and all(offset is not None for offset in pytest_offsets)
    )
    primary_covers_assertions = False
    if pytest_commands:
        required = {
            assertion_id
            for acceptance in bundle.get("acceptances", [])
            if acceptance.get("acceptance_id") in selected.get("acceptance_ids", [])
            for assertion_id in acceptance.get("assertion_ids", [])
        }
        declared: set[str] = set()
        primary_offset = pytest_offsets[0]
        for item in normalized[0][primary_offset + 2:]:
            if item == "-q":
                continue
            ref = safe_relative(item.split("::", 1)[0])
            path = ROOT / ref
            if path.suffix != ".py" or not path.is_file() or path.is_symlink():
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeError):
                continue
            constants = {
                node.targets[0].id: node.value.value
                for node in tree.body
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            }
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "cer_assertion":
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            declared.add(arg.value)
                        elif isinstance(arg, ast.Name) and arg.id in constants:
                            declared.add(constants[arg.id])
        primary_covers_assertions = bool(required) and required <= declared
    if pytest_commands and not primary_covers_assertions:
        prefixes = {tuple(command[:offset]) for command, offset in zip(normalized, pytest_offsets)}
        if len(prefixes) == 1:
            prefix = list(prefixes.pop())
            # Repeated validation commands may legitimately arise when a
            # single assertion is projected through both its target and
            # fixture context.  Pytest will execute the same node twice in
            # that form, which violates CER's unique-case requirement.
            # Preserve declaration order while making each non-option input
            # occur once in the combined shell-free selector.
            selector_items: list[str] = []
            for command, offset in zip(normalized, pytest_offsets):
                for item in command[offset + 2:]:
                    if item != "-q" and item not in selector_items:
                        selector_items.append(item)
            argv = [*prefix, "-m", "pytest", *selector_items, "-q"]
    snapshots = [safe_relative(str(item)) for item in selected.get("execution_snapshot_paths", [])]
    if not snapshots:
        raise ValueError("slice execution snapshot paths missing")
    selector_text = " ".join(
        [*argv, *[str(item) for item in (selected.get("proof") or {}).get("selector_intents", [])]]
    )
    # Explicit argv targets outrank prose references to fixture paths.
    argv_paths = {part.split("::", 1)[0] for part in argv}
    targets = [path for path in snapshots if path in argv_paths]
    if not targets:
        targets = [path for path in snapshots if path in selector_text]
    if not targets:
        targets = [path for path in snapshots if Path(path).suffix.lower() in {".py", ".cs", ".gd", ".js", ".ts"}]
    if not targets:
        targets = [snapshots[0]]
    fixtures = [path for path in snapshots if path not in targets]
    if not fixtures:
        fixtures = [targets[0]]
    return argv, targets, fixtures


def _stage_descriptor(run_dir: Path, stage: str) -> Path:
    return run_dir / "descriptors" / f"{stage}.json"


def q0_recommendation(
    *,
    semantic: Path,
    slice_id: str,
    profile: str,
    state_path: Path | None,
    changed_paths: Sequence[str],
    change_kinds: Sequence[str],
    snapshot_roots: Sequence[Mapping[str, str]] | None,
    source_commit: str | None,
    base_commit: str | None,
    observation_index: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    bundle = load_json(semantic)
    state = load_json(_inside_root(state_path, "state")) if state_path else {"state": "planned-only"}
    if not snapshot_roots or not source_commit:
        return {
            "schema": "quick-dev.recommendation.v1",
            "plan_id": bundle.get("plan_id"),
            "plan_hash": sha256_value(dict(bundle)),
            "slice_id": slice_id,
            "profile": profile,
            "current_snapshot_sha256": None,
            "recommended_action": "repair-vdd",
            "forbidden_actions": ["run-preflight", "author-red", "run-red", "implement", "run-green", "run-refactor", "validate-slice", "run-terminal", "stop"],
            "reason_code": "current-snapshot-input-missing",
            "blocked_by": ["snapshot_roots", "source_commit"],
            "reusable_observations": [],
            "invalidated_observations": [],
            "invalidated_stages": [],
            "change_kinds": [],
            "model_called": False,
            "tests_executed": False,
            "writes_performed": False,
        }
    snapshot = current_snapshot(ROOT, snapshot_roots, source_commit=source_commit, base_commit=base_commit)
    result = recommendation(
        bundle=bundle,
        slice_id=slice_id,
        state=state,
        changed_paths=changed_paths,
        change_kinds=change_kinds,
        profile=profile,
        observation_index=observation_index,
        current_snapshot_sha256=snapshot["sha256"],
    )
    return {
        **result,
        "candidate_identity": candidate_identity(ROOT, bundle, slice_id),
        "model_called": False,
        "tests_executed": False,
        "writes_performed": False,
    }


def q1_preflight(*, semantic: Path, slice_id: str, profile: str) -> dict[str, Any]:
    bundle = load_json(semantic)
    identity = candidate_identity(ROOT, bundle, slice_id)
    result = preflight(workspace=ROOT, semantic_plan=semantic, slice_id=slice_id, candidate_hash=identity["candidate_hash"], profile=profile)
    return {**result, "candidate_identity": identity, "plan_sha256": sha256_bytes(semantic.read_bytes()), "slice_id": slice_id, "profile": profile, "authorizes": []}


def _declared_cer_assertions(path: Path) -> set[str]:
    """Read literal or module-constant CER markers without invoking a worker."""
    try:
        # Pytest accepts UTF-8 BOM input, so the marker scanner must do the
        # same or a valid CER selector is misclassified as unmapped.
        tree = ast.parse(path.read_text(encoding="utf-8").lstrip("\ufeff"))
    except (OSError, SyntaxError, UnicodeError):
        return set()
    constants = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    declared: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "cer_assertion":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                declared.add(arg.value)
            elif isinstance(arg, ast.Name) and arg.id in constants:
                declared.add(constants[arg.id])
    return declared


def q2_author_red(
    *,
    semantic: Path,
    slice_id: str,
    run_dir: Path,
    profile: str,
    timeout_seconds: int,
    backend: str | None,
) -> dict[str, Any]:
    run_dir = _inside_root(run_dir, "run-dir")
    plan_dir = semantic.parent
    bundle = load_json(semantic)
    argv, target_refs, fixture_refs = _descriptor_inputs(bundle, plan_dir, slice_id)
    selected = _slice(bundle, slice_id)
    missing = [path for path in sorted(set(target_refs + fixture_refs)) if not (ROOT / path).is_file()]
    # `planned_new_files` is a plan-time declaration which permits an absent
    # RED input.  It is not evidence that an already materialized, correctly
    # mapped input still needs a model author.  Treating it as such needlessly
    # re-authorizes workers during resumed runs and can strand an otherwise
    # deterministic probe behind an unrelated backend timeout.
    worker_required = bool(missing)
    if "behavior_routing" in bundle:
        # A new plan may bind existing tests with new assertion IDs. This only
        # decides whether authoring is needed; the probe alone proves behavior.
        required = {sid for a in bundle["acceptances"] if a["acceptance_id"] in selected["acceptance_ids"] for sid in a["assertion_ids"]}
        declared = set()
        # Assertions may be deliberately split between the primary selector
        # and frozen fixture tests.  Both are executed by the descriptor, so
        # authoring is necessary only when their combined mapping is incomplete.
        for ref in sorted(set(target_refs + fixture_refs)):
            declared.update(_declared_cer_assertions(ROOT / ref))
        worker_required = worker_required or not required <= declared
    if worker_required:
        worker = run_red_author(
            workspace=ROOT,
            plan_dir=plan_dir,
            semantic_plan=semantic,
            slice_id=slice_id,
            timeout_seconds=timeout_seconds,
            backend=backend,
        )
        if worker.get("status") != "worker-changes-valid":
            return {**worker, "required_next_action": "author-red"}
    else:
        worker = {
            "schema": "quick-dev.worker-result.v1", "stage": "red-author", "status": "worker-not-required",
            "changed_paths": [], "authorizes_evidence": False, "authorizes": [],
        }
    for ref in sorted(set(target_refs + fixture_refs)):
        path = _inside_root(ROOT / ref, "RED target/fixture")
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"RED author did not materialize bound path: {ref}")
    identity = candidate_identity(ROOT, bundle, slice_id)
    stage = "probe" if "behavior_routing" in bundle else "red"
    descriptor = materialize_descriptor(
        bundle=bundle,
        slice_id=slice_id,
        stage=stage,
        run_id=run_dir.name,
        candidate_hash=identity["candidate_hash"],
        argv=argv,
        cwd=".",
        timeout_seconds=max(1, min(timeout_seconds, 600)),
        target_refs=target_refs,
        fixture_refs=fixture_refs,
    )
    descriptor_path = _stage_descriptor(run_dir, stage)
    create_json(descriptor_path, descriptor)
    return {
        "schema": "quick-dev.red-author-result.v1",
        "status": "probe-materialized" if stage == "probe" else "red-materialized",
        "worker": worker,
        "descriptor_ref": descriptor_path.relative_to(ROOT).as_posix(),
        "descriptor_sha256": sha256_value(descriptor),
        "candidate_identity": identity,
        "required_next_action": "run-probe" if stage == "probe" else "run-red",
        "authorizes_evidence": False,
        "authorizes": [],
    }


def q4_handoff(
    *,
    semantic: Path,
    slice_id: str,
    run_dir: Path,
    snapshot_roots: Sequence[Mapping[str, str]],
    source_commit: str,
    base_commit: str | None,
) -> dict[str, Any]:
    run_dir = _inside_root(run_dir, "run-dir")
    bundle = load_json(semantic)
    selected = _slice(bundle, slice_id)
    red = load_json(run_dir / "canonical-evidence" / "red" / "stage-result.v2.json")
    validate_expected_red(red)
    from case_evidence import reread_stage_cases
    reread_stage_cases(run_dir, "red")
    if "behavior_routing" in bundle:
        from behavior_routing import verify_stage, current_result
        verify_stage(ROOT, bundle, run_dir, load_json(_stage_descriptor(run_dir, "red")))
        current_result(ROOT, bundle, slice_id, red)
    if red.get("slice_id") != slice_id or red.get("plan_id") != bundle.get("plan_id") or red.get("run_id") != run_dir.name:
        raise ValueError("Q4 RED predecessor lineage mismatch")
    before = begin_q4(
        workspace=ROOT,
        snapshot_roots=snapshot_roots,
        source_commit=source_commit,
        red_stage_result=red,
        base_commit=base_commit,
    )
    return {
        "schema": "quick-dev.implementation-worker-handoff.v2",
        "status": "implementation-worker-required",
        "plan_id": bundle.get("plan_id"),
        "slice_id": slice_id,
        "run_id": run_dir.name,
        "candidate_hash": red.get("candidate_hash"),
        "predecessor_red_sha256": sha256_value(red),
        "allowed_production_paths": list(selected.get("allowed_write_paths", [])),
        "forbidden_execution_snapshot_paths": list(selected.get("execution_snapshot_paths", [])),
        "required_next_stage": "green",
        "before": before,
        "authorizes_evidence": False,
        "authorizes": [],
    }


def q4_finish(
    *,
    semantic: Path,
    slice_id: str,
    run_dir: Path,
    before: Mapping[str, Any],
    snapshot_roots: Sequence[Mapping[str, str]],
    source_commit: str,
    base_commit: str | None,
    claimed_changed_paths: Sequence[str],
) -> dict[str, Any]:
    run_dir = _inside_root(run_dir, "run-dir")
    bundle = load_json(semantic)
    selected = _slice(bundle, slice_id)
    red = load_json(run_dir / "canonical-evidence" / "red" / "stage-result.v2.json")
    result = finish_q4(
        workspace=ROOT,
        snapshot_roots=snapshot_roots,
        source_commit=source_commit,
        before=before,
        red_stage_result=red,
        changed_paths=claimed_changed_paths,
        slice_item=selected,
        base_commit=base_commit,
    )
    result = {**result, "plan_id": bundle.get("plan_id"), "slice_id": slice_id, "run_id": run_dir.name}
    if result.get("status") != "implementation-successor":
        return result
    red_descriptor = load_json(_stage_descriptor(run_dir, "red"))
    identity = candidate_identity(ROOT, bundle, slice_id)
    green = successor_descriptor(
        red_descriptor, stage="green", run_id=run_dir.name,
        candidate_hash=identity["candidate_hash"],
    )
    green_path = _stage_descriptor(run_dir, "green")
    create_json(green_path, green)
    return {
        **result,
        "green_descriptor_ref": green_path.relative_to(ROOT).as_posix(),
        "green_descriptor_sha256": sha256_value(green),
        "required_next_action": "run-green",
    }


def q4_implementation_worker(
    *,
    semantic: Path,
    slice_id: str,
    run_dir: Path,
    snapshot_roots: Sequence[Mapping[str, str]],
    source_commit: str,
    base_commit: str | None,
    timeout_seconds: int,
    backend: str | None,
) -> dict[str, Any]:
    handoff = q4_handoff(
        semantic=semantic, slice_id=slice_id, run_dir=run_dir, snapshot_roots=snapshot_roots,
        source_commit=source_commit, base_commit=base_commit,
    )
    red = load_json(_inside_root(run_dir, "run-dir") / "canonical-evidence" / "red" / "stage-result.v2.json")
    worker = run_implementation_worker(
        workspace=ROOT,
        plan_dir=semantic.parent,
        semantic_plan=semantic,
        slice_id=slice_id,
        red_stage_result=red,
        run_dir=run_dir,
        timeout_seconds=timeout_seconds,
        backend=backend,
    )
    if worker.get("status") != "worker-changes-valid":
        return {"schema": "quick-dev.implementation-worker-result.v1", "status": worker.get("status"), "failure_family": worker.get("failure_family"), "reason_code": worker.get("reason_code"), "worker": worker, "handoff": handoff, "authorizes": []}
    gate = q4_finish(
        semantic=semantic, slice_id=slice_id, run_dir=run_dir, before=handoff["before"],
        snapshot_roots=snapshot_roots, source_commit=source_commit, base_commit=base_commit,
        claimed_changed_paths=worker.get("changed_paths", []),
    )
    if gate.get("status") != "implementation-successor":
        return {
            "schema": "quick-dev.implementation-worker-result.v1",
            "status": gate.get("status"), "failure_family": gate.get("failure_family"),
            "reason_code": gate.get("reason_code"), "worker": worker, "q4_gate": gate,
            "authorizes_evidence": False, "authorizes": [],
        }
    return {
        "schema": "quick-dev.implementation-worker-result.v1",
        "status": "implementation-successor",
        "worker": worker,
        "q4_gate": gate,
        "green_descriptor_ref": gate["green_descriptor_ref"],
        "green_descriptor_sha256": gate["green_descriptor_sha256"],
        "required_next_action": gate["required_next_action"],
        "authorizes_evidence": False,
        "authorizes": [],
    }


def q6_refactor_worker_and_run(
    *,
    semantic: Path,
    slice_id: str,
    run_dir: Path,
    profile: str,
    timeout_seconds: int,
    backend: str | None,
    failure_history=None,
) -> dict[str, Any]:
    from behavior_routing import read_route as read_behavior_route
    run_dir = _inside_root(run_dir, "run-dir")
    from stage_reentry import existing_result, check_history
    bundle = load_json(semantic)
    def resumed_refactor(result):
        next_action = "repair-vdd"
        if result.get("predicate_result") is True:
            from behavior_routing import next_action as route_next
            next_action = route_next(ROOT, bundle, run_dir, read_behavior_route(ROOT, bundle, run_dir, slice_id)) if "behavior_routing" in bundle else "validate-slice"
        return {"schema": "quick-dev.refactor-worker-result.v1", "status": "refactor-observed" if result.get("predicate_result") else "refactor-failed", "stage_result": result, "worker": {"status": "not-invoked-existing-descriptor"}, "required_next_action": next_action, "authorizes_evidence": False, "authorizes": []}
    refactor_path = _stage_descriptor(run_dir, "refactor")
    if refactor_path.is_file():
        descriptor = load_json(refactor_path)
        prior = existing_result(ROOT, bundle, run_dir, descriptor, profile)
        if prior is not None:
            return resumed_refactor(prior)
        # Descriptor already materialized: resume its test, not the model worker.
        stage_result = execute_stage(workspace=ROOT, semantic_plan=semantic, run_dir=run_dir, descriptor_path=refactor_path, profile_identity=profile, failure_history=failure_history)
        return resumed_refactor(stage_result)
    if (run_dir / "canonical-evidence/refactor").exists():
        raise ValueError("stage-reentry-blocked: incomplete refactor evidence; recover or use a new run")
    red_descriptor = load_json(_stage_descriptor(run_dir, "red"))
    candidate = candidate_identity(ROOT, bundle, slice_id)
    prospective = successor_descriptor(red_descriptor, stage="refactor", run_id=run_dir.name, candidate_hash=candidate["candidate_hash"])
    decision = check_history(run_dir, prospective, failure_history)
    if decision["status"] == "blocked":
        return decision
    green = load_json(run_dir / "canonical-evidence" / "green" / "stage-result.v2.json")
    worker = run_refactor_worker(
        workspace=ROOT,
        plan_dir=semantic.parent,
        semantic_plan=semantic,
        slice_id=slice_id,
        green_stage_result=green,
        run_dir=run_dir,
        timeout_seconds=timeout_seconds,
        backend=backend,
    )
    if worker.get("status") != "worker-changes-valid":
        return {"schema": "quick-dev.refactor-worker-result.v1", "status": worker.get("status"), "worker": worker, "authorizes": []}
    bundle = load_json(semantic)
    red_descriptor = load_json(_stage_descriptor(run_dir, "red"))
    identity = candidate_identity(ROOT, bundle, slice_id)
    refactor = successor_descriptor(red_descriptor, stage="refactor", run_id=run_dir.name, candidate_hash=identity["candidate_hash"])
    refactor_path = _stage_descriptor(run_dir, "refactor")
    create_json(refactor_path, refactor)
    stage_result = execute_stage(
        workspace=ROOT,
        semantic_plan=semantic,
        run_dir=run_dir,
        descriptor_path=refactor_path,
        profile_identity=profile, failure_history=failure_history,
    )
    return {
        "schema": "quick-dev.refactor-worker-result.v1",
        "status": "refactor-observed" if stage_result.get("predicate_result") is True else "refactor-failed",
        "worker": worker,
        "stage_result": stage_result,
        "required_next_action": (("run-regression" if "behavior_routing" in bundle and any(row["disposition"] == "present" for row in read_behavior_route(ROOT, bundle, run_dir, slice_id)["behavior_dispositions"]) else "validate-slice") if stage_result.get("predicate_result") is True else "repair-vdd"),
        "authorizes_evidence": False,
        "authorizes": [],
    }


def _detached_promotion_binding(path: Path, profile: str) -> Mapping[str, Any] | None:
    if profile != "self-hosted":
        return None
    resolved = path.resolve()
    bundle = _load_json_object(resolved, "detached-bundle", inside_repo=False)
    if bundle.get("schema") != "detached-judge-bundle.v1":
        raise ValueError("self-hosted promotion requires canonical detached-judge-bundle.v1")
    valid, findings = validate_detached_bundle(
        bundle,
        candidate_root=ROOT,
        bundle_root=resolved.parent,
        allow_v2=False,
    )
    if not valid:
        raise ValueError("detached promotion bundle invalid: " + ",".join(findings))
    metadata = detached_bundle_metadata(bundle)
    return {
        "schema": "quick-dev.detached-promotion-binding.v1",
        "bundle_sha256": sha256_value(dict(bundle)),
        "judge_identity": metadata["judge_identity"],
        "judge_version": metadata["judge_version"],
        "source_commit": bundle.get("source_commit"),
        "source_tree": bundle.get("source_tree"),
        "artifact_count": metadata["artifact_count"],
        "validated": True,
        "validator_identity": "quick-dev-detached-bundle-validator.v1",
        "authorizes": [],
    }


def _materialize_named_descriptor(semantic: Path, run_dir: Path, stage: str) -> Path:
    run_dir = _inside_root(run_dir, "run-dir")
    descriptor = _stage_descriptor(run_dir, stage)
    if not descriptor.is_file():
        bundle = load_json(semantic)
        routed = "behavior_routing" in bundle
        if stage != "terminal" and not (routed and stage in {"red", "regression"}):
            raise ValueError(f"{stage} descriptor missing")
        base = load_json(_stage_descriptor(run_dir, "probe" if routed else "red"))
        slice_id = base["slice_id"]
        from behavior_routing import read_route
        route = read_route(ROOT, bundle, run_dir, slice_id) if routed else None
        argv, target_refs, fixture_refs = _descriptor_inputs(bundle, semantic.parent, slice_id)
        identity = candidate_identity(ROOT, bundle, slice_id)
        terminal = materialize_descriptor(
            bundle=bundle, slice_id=slice_id, stage=stage, run_id=run_dir.name,
            candidate_hash=identity["candidate_hash"], argv=argv, cwd=".", timeout_seconds=120,
            target_refs=target_refs, fixture_refs=fixture_refs, routing_result=route,
        )
        create_json(descriptor, terminal)
    return descriptor


def _execute_named_stage(semantic: Path, run_dir: Path, stage: str, profile: str, failure_history=None) -> Mapping[str, Any]:
    run_dir = _inside_root(run_dir, "run-dir")
    descriptor = _materialize_named_descriptor(semantic, run_dir, stage)
    return execute_stage(
        workspace=ROOT,
        semantic_plan=semantic,
        run_dir=run_dir,
        descriptor_path=descriptor,
        profile_identity=profile, failure_history=failure_history,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--slice", dest="slice_id", required=True)
    parser.add_argument("--profile", default="standard")
    parser.add_argument("--recommendation-only", action="store_true")
    parser.add_argument(
        "--action",
        choices=(
            "run-probe", "run-regression", "route-behaviors", "preflight", "run-preflight", "recommendation", "author-red", "run-red", "implement", "run-green",
            "run-refactor", "execute-stage", "implementation-handoff", "implementation-finish", "slice-ready",
            "validate-slice", "run-terminal", "implementation-complete", "recover",
        ),
        default="preflight",
    )
    parser.add_argument("--failure-history", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument("--change-kind", action="append", default=[])
    parser.add_argument("--observation-index", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--descriptor", type=Path)
    parser.add_argument("--snapshot-roots", type=Path)
    parser.add_argument("--predecessors", type=Path)
    parser.add_argument("--recovery-input", type=Path)
    parser.add_argument("--before-state", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--base-commit")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--detached-bundle", type=Path)
    parser.add_argument("--detached-promotion-passed", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker-timeout-seconds", type=int, default=600)
    parser.add_argument("--llm-backend")
    args = parser.parse_args()
    try:
        failure_history = _load_json_list(args.failure_history, "failure-history") if args.failure_history else None
        profile_contract(args.profile)
        semantic = _semantic_plan(args.plan)
        snapshot_roots = _load_json_list(args.snapshot_roots, "snapshot-roots") if args.snapshot_roots else None
        observations = _load_json_list(args.observation_index, "observation-index") if args.observation_index else []
        if args.recommendation_only or args.action == "recommendation":
            result = q0_recommendation(
                semantic=semantic,
                slice_id=args.slice_id,
                profile=args.profile,
                state_path=args.state,
                changed_paths=args.changed_path,
                change_kinds=args.change_kind,
                snapshot_roots=snapshot_roots,
                source_commit=args.source_commit,
                base_commit=args.base_commit,
                observation_index=observations,
            )
        elif args.action in {"preflight", "run-preflight"}:
            result = q1_preflight(semantic=semantic, slice_id=args.slice_id, profile=args.profile)
        elif args.action == "author-red":
            if args.run_dir is None:
                raise ValueError("author-red requires --run-dir")
            result = q2_author_red(
                semantic=semantic, slice_id=args.slice_id, run_dir=args.run_dir, profile=args.profile,
                timeout_seconds=args.worker_timeout_seconds, backend=args.llm_backend,
            )
        elif args.action == "route-behaviors":
            from behavior_routing import read_route, next_action
            if args.run_dir is None:
                raise ValueError("route-behaviors requires --run-dir")
            bundle = load_json(semantic)
            run_root = _inside_root(args.run_dir, "run-dir")
            route = read_route(ROOT, bundle, run_root, args.slice_id)
            result = {"status": "probe-observed", "behavior_dispositions": route["behavior_dispositions"], "required_next_action": next_action(ROOT, bundle, run_root, route), "authorizes": []}
        elif args.action in {"run-red", "run-green", "run-terminal", "run-probe", "run-regression"}:
            if args.run_dir is None:
                raise ValueError(f"{args.action} requires --run-dir")
            stage = args.action.removeprefix("run-")
            result = _execute_named_stage(semantic, args.run_dir, stage, args.profile, failure_history)
        elif args.action == "implement":
            if args.run_dir is None or snapshot_roots is None or args.source_commit is None:
                raise ValueError("implement requires --run-dir --snapshot-roots --source-commit")
            result = q4_implementation_worker(
                semantic=semantic, slice_id=args.slice_id, run_dir=args.run_dir, snapshot_roots=snapshot_roots,
                source_commit=args.source_commit, base_commit=args.base_commit,
                timeout_seconds=args.worker_timeout_seconds, backend=args.llm_backend,
            )
        elif args.action == "run-refactor":
            if args.run_dir is None:
                raise ValueError("run-refactor requires --run-dir")
            result = q6_refactor_worker_and_run(
                semantic=semantic, slice_id=args.slice_id, run_dir=args.run_dir, profile=args.profile,
                timeout_seconds=args.worker_timeout_seconds, backend=args.llm_backend, failure_history=failure_history,
            )
        elif args.action == "execute-stage":
            if args.run_dir is None or args.descriptor is None:
                raise ValueError("execute-stage requires --run-dir and --descriptor")
            result = execute_stage(workspace=ROOT, semantic_plan=semantic, run_dir=_inside_root(args.run_dir, "run-dir"), descriptor_path=_inside_root(args.descriptor, "descriptor"), profile_identity=args.profile, failure_history=failure_history)
        elif args.action == "implementation-handoff":
            if args.run_dir is None or snapshot_roots is None or args.source_commit is None:
                raise ValueError("implementation-handoff requires --run-dir --snapshot-roots --source-commit")
            result = q4_handoff(
                semantic=semantic,
                slice_id=args.slice_id,
                run_dir=args.run_dir,
                snapshot_roots=snapshot_roots,
                source_commit=args.source_commit,
                base_commit=args.base_commit,
            )
            if args.out is not None:
                create_json(_inside_root(args.out, "out"), result)
        elif args.action == "implementation-finish":
            if args.run_dir is None or args.before_state is None or snapshot_roots is None or args.source_commit is None:
                raise ValueError("implementation-finish requires --run-dir --before-state --snapshot-roots --source-commit")
            before = _load_json_object(args.before_state, "before-state")
            if before.get("schema") == "quick-dev.implementation-worker-handoff.v2":
                nested = before.get("before")
                if not isinstance(nested, Mapping):
                    raise ValueError("implementation handoff missing Q4 before snapshot")
                before = nested
            result = q4_finish(
                semantic=semantic,
                slice_id=args.slice_id,
                run_dir=args.run_dir,
                before=before,
                snapshot_roots=snapshot_roots,
                source_commit=args.source_commit,
                base_commit=args.base_commit,
                claimed_changed_paths=args.changed_path,
            )
            if args.out is not None:
                create_json(_inside_root(args.out, "out"), result)
        elif args.action in {"slice-ready", "validate-slice"}:
            if args.run_dir is None or snapshot_roots is None or args.source_commit is None or args.out is None:
                raise ValueError("validate-slice requires --run-dir --snapshot-roots --source-commit --out")
            _materialize_named_descriptor(semantic, _inside_root(args.run_dir, "run-dir"), "terminal")
            result = validate_slice_ready(workspace=ROOT, semantic_plan=semantic, run_root=_inside_root(args.run_dir, "run-dir"), slice_id=args.slice_id, snapshot_roots=snapshot_roots, source_commit=args.source_commit, base_commit=args.base_commit, out=_inside_root(args.out, "out"))
        elif args.action == "implementation-complete":
            if snapshot_roots is None or args.predecessors is None or args.source_commit is None or args.out is None:
                raise ValueError("implementation-complete requires --snapshot-roots --predecessors --source-commit --out")
            if args.detached_promotion_passed:
                raise ValueError("boolean detached promotion authority is forbidden; provide --detached-bundle")
            detached_binding = None
            if args.profile == "self-hosted":
                if args.detached_bundle is None:
                    raise ValueError("self-hosted terminal requires --detached-bundle")
                detached_binding = _detached_promotion_binding(args.detached_bundle, args.profile)
            result = publish_implementation_complete(
                workspace=ROOT,
                semantic_plan=semantic,
                predecessors=_load_json_list(args.predecessors, "predecessors"),
                snapshot_roots=snapshot_roots,
                source_commit=args.source_commit,
                base_commit=args.base_commit,
                out=_inside_root(args.out, "out"),
                detached_promotion_binding=detached_binding,
                profile=args.profile,
            )
        else:
            if args.run_dir is None or args.recovery_input is None or snapshot_roots is None or args.source_commit is None:
                raise ValueError("recover requires --run-dir --recovery-input --snapshot-roots --source-commit")
            recovery = _load_json_object(args.recovery_input, "recovery-input")
            result = recover_current_run(
                workspace=ROOT,
                run_root=_inside_root(args.run_dir, "run-dir"),
                recovery_input=recovery,
                snapshot_roots=snapshot_roots,
                source_commit=args.source_commit,
                base_commit=args.base_commit,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "recommended_action": "repair-vdd", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 1 if result.get("status") == "task-implementation-failure" else 0


if __name__ == "__main__":
    raise SystemExit(main())
