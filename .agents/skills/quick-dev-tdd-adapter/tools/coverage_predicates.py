"""Deterministic Q7/Q8 coverage predicates for current Quick Dev plans."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from current_lifecycle import (
    STAGES, canonical_bytes, create_json, current_snapshot, expected_tuple_keys,
    load_json, resolve_file, sha256_bytes, sha256_value, validate_closure,
)


def _semantic_index(bundle: Mapping[str, Any], slice_id: str) -> tuple[dict[str, Any], dict[str, set[str]]]:
    slices, acceptances = bundle.get("slices"), bundle.get("acceptances")
    if not isinstance(slices, list) or not isinstance(acceptances, list):
        raise ValueError("semantic plan is incomplete")
    selected = next((item for item in slices if isinstance(item, dict) and item.get("slice_id") == slice_id), None)
    if selected is None:
        raise ValueError("slice is not declared")
    acceptance_map = {item.get("acceptance_id"): item for item in acceptances if isinstance(item, dict)}
    expected: dict[str, set[str]] = {}
    for acceptance_id in selected.get("acceptance_ids", []):
        item = acceptance_map.get(acceptance_id)
        assertion_ids = item.get("assertion_ids") if isinstance(item, dict) else None
        if not isinstance(assertion_ids, list) or not assertion_ids or any(not isinstance(value, str) or not value for value in assertion_ids):
            raise ValueError(f"acceptance assertions are invalid: {acceptance_id}")
        expected[acceptance_id] = set(assertion_ids)
    if not expected:
        raise ValueError("slice has no active Acceptance")
    return selected, expected


def _reread_edge(workspace: Path, run_root: Path, ref: Mapping[str, str], *, slice_id: str, stage: str, selector_identity: str) -> dict[str, Any]:
    path = ref.get("path")
    expected_sha = ref.get("sha256")
    if not isinstance(path, str) or not isinstance(expected_sha, str):
        raise ValueError("runtime edge ref is invalid")
    edge_path = resolve_file(run_root, path)
    edge = load_json(edge_path)
    if sha256_value(edge) != expected_sha:
        raise ValueError("runtime edge hash is stale")
    if edge.get("slice_id") != slice_id or edge.get("stage") != stage or edge.get("selector_identity") != selector_identity:
        raise ValueError("runtime edge identity is stale")
    observation = load_json(resolve_file(run_root, edge["observation_ref"]))
    receipt = load_json(resolve_file(run_root, edge["receipt_ref"]))
    if sha256_value(observation) != edge.get("observation_sha256"):
        raise ValueError("runtime observation hash is stale")
    if sha256_value(receipt) != edge.get("receipt_sha256") or observation.get("receipt_sha256") != edge.get("receipt_sha256"):
        raise ValueError("runtime receipt hash is stale")
    target = resolve_file(workspace, edge["target_ref"])
    fixture = resolve_file(workspace, edge["fixture_ref"])
    if sha256_bytes(target.read_bytes()) != edge.get("target_sha256"):
        raise ValueError("runtime target hash is stale")
    if sha256_bytes(fixture.read_bytes()) != edge.get("fixture_sha256"):
        raise ValueError("runtime fixture hash is stale")
    return edge


def validate_slice_ready(
    *, workspace: Path, semantic_plan: Path, run_root: Path, slice_id: str,
    snapshot_roots: Sequence[Mapping[str, str]], source_commit: str,
    out: Path, base_commit: str | None = None,
) -> dict[str, Any]:
    """Q7: prove RED/GREEN/REFACTOR exact assertion coverage for one slice."""
    bundle = load_json(semantic_plan)
    _selected, expected_assertions = _semantic_index(bundle, slice_id)
    snapshot = current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit)
    selector_identity: str | None = None
    candidate_hash: str | None = None
    coverage: dict[str, dict[str, list[dict[str, str]]]] = {}

    for stage in ("red", "green", "refactor"):
        result_path = run_root / "canonical-evidence" / stage / "stage-result.v2.json"
        result = load_json(result_path)
        required_outcome = "fail" if stage == "red" else "pass"
        if result.get("stage") != stage or result.get("slice_id") != slice_id or result.get("predicate_result") is not True or result.get("verification_outcome") != required_outcome:
            raise ValueError(f"{stage} stage result is not current success evidence")
        current_selector = result.get("selector_identity")
        if not isinstance(current_selector, str):
            raise ValueError("selector identity is missing")
        if selector_identity is None:
            selector_identity = current_selector
        elif current_selector != selector_identity:
            raise ValueError("RED/GREEN/REFACTOR selector identity drifted")
        refs = result.get("runtime_edges")
        if not isinstance(refs, list) or not refs:
            raise ValueError(f"{stage} runtime edges are missing")
        observed: dict[str, dict[str, dict[str, str]]] = {acceptance: {} for acceptance in expected_assertions}
        for ref in refs:
            if not isinstance(ref, Mapping):
                raise ValueError("runtime edge ref is invalid")
            edge = _reread_edge(workspace, run_root, ref, slice_id=slice_id, stage=stage, selector_identity=selector_identity)
            acceptance_id, assertion_id = edge.get("acceptance_id"), edge.get("assertion_id")
            if acceptance_id not in expected_assertions or assertion_id not in expected_assertions[acceptance_id]:
                raise ValueError("runtime edge is outside declared Acceptance/assertion universe")
            if assertion_id in observed[acceptance_id]:
                raise ValueError("duplicate runtime assertion edge")
            observed[acceptance_id][assertion_id] = {"path": ref["path"], "sha256": ref["sha256"]}
            edge_candidate = edge.get("candidate_hash")
            if candidate_hash is None:
                candidate_hash = edge_candidate
            elif edge_candidate != candidate_hash:
                raise ValueError("runtime candidate identity drifted")
        for acceptance_id, assertion_ids in expected_assertions.items():
            if set(observed[acceptance_id]) != assertion_ids:
                raise ValueError(f"{stage} assertion exact cover failed for {acceptance_id}")
        coverage[stage] = {acceptance: [observed[acceptance][assertion] for assertion in sorted(observed[acceptance])] for acceptance in sorted(observed)}

    result = {
        "schema": "quick-dev.slice-ready-result.v2",
        "predicate": "slice-ready", "status": "pass", "slice_id": slice_id,
        "run_id": run_root.name, "plan_sha256": sha256_bytes(semantic_plan.read_bytes()),
        "candidate_hash": candidate_hash, "selector_identity": selector_identity,
        "current_snapshot_sha256": snapshot["sha256"], "assertion_coverage": coverage,
        "authorizes": [],
    }
    create_json(out, result)
    return result


def _canonical_edge_for_acceptance(slice_ready: Mapping[str, Any], stage: str, acceptance_id: str) -> Mapping[str, str]:
    coverage = slice_ready.get("assertion_coverage", {})
    stage_coverage = coverage.get(stage, {}) if isinstance(coverage, Mapping) else {}
    refs = stage_coverage.get(acceptance_id) if isinstance(stage_coverage, Mapping) else None
    if not isinstance(refs, list) or not refs:
        raise ValueError("slice-ready canonical edge is missing")
    ref = refs[0]
    if not isinstance(ref, Mapping):
        raise ValueError("slice-ready canonical edge is invalid")
    return ref


def publish_implementation_complete(
    *, workspace: Path, semantic_plan: Path, predecessors: Sequence[Mapping[str, str]],
    snapshot_roots: Sequence[Mapping[str, str]], source_commit: str,
    out: Path, base_commit: str | None = None,
) -> dict[str, Any]:
    """Q8 terminal result predicate and sole current completion writer."""
    bundle = load_json(semantic_plan)
    expected_keys = expected_tuple_keys(bundle)
    before = current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit)
    seen_slices: set[str] = set()
    tuples: list[dict[str, str]] = []

    cover = bundle.get("final_plan_coverage")
    if not isinstance(cover, list):
        raise ValueError("final plan coverage is missing")
    acceptance_by_slice: dict[str, set[str]] = {}
    for edge in cover:
        if isinstance(edge, Mapping):
            acceptance_by_slice.setdefault(str(edge.get("slice_id")), set()).add(str(edge.get("acceptance_id")))

    for predecessor in predecessors:
        slice_id, run_root_raw, ready_raw = predecessor.get("slice_id"), predecessor.get("run_root"), predecessor.get("result_ref")
        if not all(isinstance(value, str) and value for value in (slice_id, run_root_raw, ready_raw)):
            raise ValueError("terminal predecessor is invalid")
        if slice_id in seen_slices:
            raise ValueError("terminal predecessor slice is duplicated")
        seen_slices.add(slice_id)
        run_root = (workspace / run_root_raw).resolve()
        ready_path = resolve_file(workspace, ready_raw)
        ready = load_json(ready_path)
        if sha256_value(ready) != predecessor.get("result_sha256"):
            raise ValueError("slice-ready predecessor hash is stale")
        if ready.get("predicate") != "slice-ready" or ready.get("status") != "pass" or ready.get("slice_id") != slice_id or ready.get("run_id") != run_root.name:
            raise ValueError("slice-ready predecessor identity is stale")
        if ready.get("current_snapshot_sha256") != before["sha256"]:
            raise ValueError("slice-ready predecessor snapshot is stale")
        selector = ready.get("selector_identity")
        if not isinstance(selector, str):
            raise ValueError("slice-ready selector identity is missing")

        terminal_result = load_json(run_root / "canonical-evidence" / "terminal" / "stage-result.v2.json")
        if terminal_result.get("stage") != "terminal" or terminal_result.get("predicate_result") is not True or terminal_result.get("verification_outcome") != "pass" or terminal_result.get("selector_identity") != selector:
            raise ValueError("terminal stage result is not a same-selector process pass")
        terminal_refs = terminal_result.get("runtime_edges")
        if not isinstance(terminal_refs, list) or not terminal_refs:
            raise ValueError("terminal runtime edges are missing")
        terminal_index: dict[str, dict[str, Mapping[str, str]]] = {}
        for ref in terminal_refs:
            edge = _reread_edge(workspace, run_root, ref, slice_id=slice_id, stage="terminal", selector_identity=selector)
            terminal_index.setdefault(edge["acceptance_id"], {})[edge["assertion_id"]] = ref

        for acceptance_id in sorted(acceptance_by_slice.get(slice_id, set())):
            for stage in ("red", "green", "refactor"):
                ref = _canonical_edge_for_acceptance(ready, stage, acceptance_id)
                edge = _reread_edge(workspace, run_root, ref, slice_id=slice_id, stage=stage, selector_identity=selector)
                tuples.append({
                    "tuple_key": f"{slice_id}|{acceptance_id}|{stage}", "slice_id": slice_id,
                    "acceptance_id": acceptance_id, "stage": stage, "runtime_edge_ref": ref["path"],
                    "runtime_edge_sha256": ref["sha256"], "selector_identity": selector,
                    "current_snapshot_sha256": before["sha256"],
                })
            terminal_assertions = terminal_index.get(acceptance_id, {})
            if not terminal_assertions:
                raise ValueError(f"terminal Acceptance coverage missing: {acceptance_id}")
            terminal_ref = terminal_assertions[sorted(terminal_assertions)[0]]
            tuples.append({
                "tuple_key": f"{slice_id}|{acceptance_id}|terminal", "slice_id": slice_id,
                "acceptance_id": acceptance_id, "stage": "terminal", "runtime_edge_ref": terminal_ref["path"],
                "runtime_edge_sha256": terminal_ref["sha256"], "selector_identity": selector,
                "current_snapshot_sha256": before["sha256"],
            })

    if seen_slices != set(acceptance_by_slice):
        raise ValueError("terminal predecessor set does not match partitioned slices")
    valid, findings = validate_closure(tuples, expected_keys, before["sha256"])
    if not valid:
        raise ValueError("runtime closure invalid: " + ",".join(findings))
    after = current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit)
    if after["sha256"] != before["sha256"]:
        raise ValueError("current snapshot changed during terminal validation")
    result = {
        "schema": "quick-dev.implementation-complete-result.v2",
        "predicate": "implementation-complete", "status": "pass",
        "plan_sha256": sha256_bytes(semantic_plan.read_bytes()),
        "current_snapshot_sha256": after["sha256"],
        "predecessors": [dict(item) for item in predecessors],
        "runtime_closure_tuples": tuples,
        "runtime_closure_sha256": sha256_value(tuples),
        "authorizes": [],
    }
    create_json(out, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    ready = sub.add_parser("slice-ready")
    ready.add_argument("--workspace", type=Path, required=True)
    ready.add_argument("--semantic-plan", type=Path, required=True)
    ready.add_argument("--run-root", type=Path, required=True)
    ready.add_argument("--slice-id", required=True)
    ready.add_argument("--snapshot-roots", type=Path, required=True)
    ready.add_argument("--source-commit", required=True)
    ready.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "slice-ready":
            roots = json.loads(args.snapshot_roots.read_text(encoding="utf-8"))
            result = validate_slice_ready(workspace=args.workspace, semantic_plan=args.semantic_plan, run_root=args.run_root, slice_id=args.slice_id, snapshot_roots=roots, source_commit=args.source_commit, out=args.out)
        else:
            raise ValueError("unsupported predicate command")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
