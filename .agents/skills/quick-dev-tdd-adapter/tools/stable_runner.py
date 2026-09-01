"""Stable deterministic Quick Dev CLI facade for Chapter 4/5/6 current plans."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[3]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from coverage_predicates import publish_implementation_complete, validate_slice_ready
from current_router import preflight, profile_contract, recommendation, validate_expected_red
from detached_promotion import validate_detached_bundle
from q4_q6_gates import begin_q4, finish_q4
from recovery_resolver import recover_current_run
from runtime_evidence import create_json, current_snapshot, load_json, safe_relative, sha256_bytes, sha256_value
from stage_pipeline import execute_stage


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
    return {**result, "plan_id": bundle.get("plan_id"), "slice_id": slice_id, "run_id": run_dir.name}


def _detached_promotion_binding(path: Path, profile: str) -> Mapping[str, Any] | None:
    if profile != "self-hosted":
        return None
    bundle = _load_json_object(path, "detached-bundle", inside_repo=False)
    valid, findings = validate_detached_bundle(bundle, candidate_root=ROOT)
    if not valid:
        raise ValueError("detached promotion bundle invalid: " + ",".join(findings))
    return {
        "schema": "quick-dev.detached-promotion-binding.v1",
        "bundle_sha256": sha256_value(dict(bundle)),
        "judge_identity": bundle.get("judge_identity"),
        "judge_version": bundle.get("judge_version"),
        "source_commit": bundle.get("source_commit"),
        "source_tree": bundle.get("source_tree"),
        "artifact_count": len(bundle.get("artifacts", [])),
        "validated": True,
        "validator_identity": "quick-dev-detached-bundle-validator.v1",
        "authorizes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--slice", dest="slice_id", required=True)
    parser.add_argument("--profile", default="standard")
    parser.add_argument("--recommendation-only", action="store_true")
    parser.add_argument(
        "--action",
        choices=("preflight", "recommendation", "execute-stage", "implementation-handoff", "implementation-finish", "slice-ready", "implementation-complete", "recover"),
        default="preflight",
    )
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
    args = parser.parse_args()
    try:
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
        elif args.action == "preflight":
            result = q1_preflight(semantic=semantic, slice_id=args.slice_id, profile=args.profile)
        elif args.action == "execute-stage":
            if args.run_dir is None or args.descriptor is None:
                raise ValueError("execute-stage requires --run-dir and --descriptor")
            result = execute_stage(workspace=ROOT, semantic_plan=semantic, run_dir=_inside_root(args.run_dir, "run-dir"), descriptor_path=_inside_root(args.descriptor, "descriptor"), profile_identity=args.profile)
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
        elif args.action == "slice-ready":
            if args.run_dir is None or snapshot_roots is None or args.source_commit is None or args.out is None:
                raise ValueError("slice-ready requires --run-dir --snapshot-roots --source-commit --out")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
