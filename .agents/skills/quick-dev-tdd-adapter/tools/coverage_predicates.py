"""Deterministic Q7/Q8 coverage predicates for current Quick Dev plans."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path: sys.path.insert(0, str(TOOLS))
from runtime_evidence import current_snapshot, create_json, expected_tuple_keys, load_json, resolve_file, sha256_bytes, sha256_value, validate_closure


def _semantic_index(bundle: Mapping[str, Any], slice_id: str) -> tuple[Mapping[str, Any], dict[str, set[str]]]:
    slices, acceptances = bundle.get("slices"), bundle.get("acceptances")
    if not isinstance(slices, list) or not isinstance(acceptances, list): raise ValueError("semantic plan incomplete")
    selected = next((x for x in slices if isinstance(x, Mapping) and x.get("slice_id") == slice_id), None)
    if selected is None: raise ValueError("slice not declared")
    amap = {x.get("acceptance_id"): x for x in acceptances if isinstance(x, Mapping)}
    expected: dict[str, set[str]] = {}
    for aid in selected.get("acceptance_ids", []):
        item = amap.get(aid); assertion_ids = item.get("assertion_ids") if isinstance(item, Mapping) else None
        if not isinstance(assertion_ids, list) or not assertion_ids: raise ValueError("Acceptance assertions invalid")
        expected[aid] = set(assertion_ids)
    if not expected: raise ValueError("slice has no active Acceptance")
    return selected, expected


def _reread_edge(workspace: Path, run_root: Path, ref: Mapping[str, str], *, slice_id: str, stage: str, selector_identity: str) -> dict[str, Any]:
    path, expected_sha = ref.get("path"), ref.get("sha256")
    if not isinstance(path, str) or not isinstance(expected_sha, str): raise ValueError("runtime edge ref invalid")
    edge = load_json(resolve_file(run_root, path))
    if sha256_value(edge) != expected_sha: raise ValueError("runtime edge hash stale")
    if edge.get("slice_id") != slice_id or edge.get("stage") != stage or edge.get("selector_identity") != selector_identity: raise ValueError("runtime edge identity stale")
    observation = load_json(resolve_file(run_root, edge["observation_ref"])); receipt = load_json(resolve_file(run_root, edge["receipt_ref"]))
    if sha256_value(observation) != edge.get("observation_sha256") or sha256_value(receipt) != edge.get("receipt_sha256") or observation.get("receipt_sha256") != edge.get("receipt_sha256"): raise ValueError("edge predecessor hash stale")
    descriptor = None
    descriptor_path = run_root / "descriptors" / f"{stage}.json"
    if descriptor_path.is_file():
        descriptor = load_json(descriptor_path)
        if sha256_value(descriptor) != edge.get("descriptor_sha256"): raise ValueError("descriptor hash stale")
    target = resolve_file(workspace, edge["target_ref"]); fixture = resolve_file(workspace, edge["fixture_ref"])
    if sha256_bytes(target.read_bytes()) != edge.get("target_sha256") or sha256_bytes(fixture.read_bytes()) != edge.get("fixture_sha256"): raise ValueError("target/fixture hash stale")
    if edge.get("predicate_result") is not True: raise ValueError("predicate-false runtime edge cannot cover")
    return edge


def validate_slice_ready(*, workspace: Path, semantic_plan: Path, run_root: Path, slice_id: str, snapshot_roots: Sequence[Mapping[str, str]], source_commit: str, out: Path, base_commit: str | None = None) -> dict[str, Any]:
    bundle = load_json(semantic_plan); _selected, expected_assertions = _semantic_index(bundle, slice_id)
    snapshot = current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit)
    selector: str | None = None; final_candidate: str | None = None; coverage: dict[str, Any] = {}
    for stage in ("red", "green", "refactor"):
        result = load_json(run_root / "canonical-evidence" / stage / "stage-result.v2.json")
        required_outcome = "fail" if stage == "red" else "pass"
        if result.get("stage") != stage or result.get("slice_id") != slice_id or result.get("predicate_result") is not True or result.get("verification_outcome") != required_outcome: raise ValueError(f"{stage} is not admissible evidence")
        current_selector = result.get("selector_identity")
        if not isinstance(current_selector, str): raise ValueError("selector identity missing")
        if selector is None: selector = current_selector
        elif selector != current_selector: raise ValueError("selector drift")
        if stage in {"green", "refactor"}: final_candidate = result.get("candidate_hash")
        refs = result.get("runtime_edges")
        if not isinstance(refs, list) or not refs: raise ValueError("runtime edges missing")
        observed = {aid: {} for aid in expected_assertions}
        for ref in refs:
            edge = _reread_edge(workspace, run_root, ref, slice_id=slice_id, stage=stage, selector_identity=selector)
            if edge.get("candidate_hash") != result.get("candidate_hash"): raise ValueError("edge/stage candidate mismatch")
            aid, assertion_id = edge.get("acceptance_id"), edge.get("assertion_id")
            if aid not in expected_assertions or assertion_id not in expected_assertions[aid] or assertion_id in observed[aid]: raise ValueError("assertion edge outside exact universe or duplicate")
            observed[aid][assertion_id] = {"path": ref["path"], "sha256": ref["sha256"]}
        for aid, expected in expected_assertions.items():
            if set(observed[aid]) != expected: raise ValueError(f"{stage} assertion exact cover failed for {aid}")
        coverage[stage] = {aid: [observed[aid][assertion] for assertion in sorted(observed[aid])] for aid in sorted(observed)}
    result = {
        "schema": "quick-dev.slice-ready-result.v2", "predicate": "slice-ready", "status": "pass", "slice_id": slice_id,
        "run_id": run_root.name, "plan_sha256": sha256_bytes(semantic_plan.read_bytes()), "candidate_hash": final_candidate,
        "selector_identity": selector, "current_snapshot_sha256": snapshot["sha256"], "assertion_coverage": coverage, "authorizes": [],
    }
    create_json(out, result); return result


def _canonical_edge(ready: Mapping[str, Any], stage: str, aid: str) -> Mapping[str, str]:
    refs = ready.get("assertion_coverage", {}).get(stage, {}).get(aid, []) if isinstance(ready.get("assertion_coverage"), Mapping) else []
    if not isinstance(refs, list) or not refs or not isinstance(refs[0], Mapping): raise ValueError("canonical edge missing")
    return refs[0]


def publish_implementation_complete(*, workspace: Path, semantic_plan: Path, predecessors: Sequence[Mapping[str, str]], snapshot_roots: Sequence[Mapping[str, str]], source_commit: str, out: Path, base_commit: str | None = None) -> dict[str, Any]:
    bundle = load_json(semantic_plan); expected_keys = expected_tuple_keys(bundle)
    before = current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit)
    cover = bundle.get("final_plan_coverage"); acceptance_by_slice: dict[str, set[str]] = {}
    if not isinstance(cover, list): raise ValueError("final plan coverage missing")
    for edge in cover:
        if isinstance(edge, Mapping): acceptance_by_slice.setdefault(str(edge.get("slice_id")), set()).add(str(edge.get("acceptance_id")))
    seen: set[str] = set(); tuples: list[dict[str, str]] = []
    for predecessor in predecessors:
        sid, run_raw, ready_raw = predecessor.get("slice_id"), predecessor.get("run_root"), predecessor.get("result_ref")
        if not all(isinstance(x, str) and x for x in (sid, run_raw, ready_raw)) or sid in seen: raise ValueError("terminal predecessor invalid")
        seen.add(sid); run_root = (workspace / run_raw).resolve(); ready = load_json(resolve_file(workspace, ready_raw))
        if sha256_value(ready) != predecessor.get("result_sha256") or ready.get("slice_id") != sid or ready.get("status") != "pass": raise ValueError("slice-ready predecessor stale")
        if ready.get("current_snapshot_sha256") != before["sha256"]: raise ValueError("slice-ready snapshot stale")
        selector = ready.get("selector_identity"); final_candidate = ready.get("candidate_hash")
        terminal = load_json(run_root / "canonical-evidence" / "terminal" / "stage-result.v2.json")
        if terminal.get("predicate_result") is not True or terminal.get("verification_outcome") != "pass" or terminal.get("selector_identity") != selector or terminal.get("candidate_hash") != final_candidate: raise ValueError("terminal stage not current same-selector pass")
        terminal_refs = terminal.get("runtime_edges"); terminal_index: dict[str, list[Mapping[str, str]]] = {}
        if not isinstance(terminal_refs, list) or not terminal_refs: raise ValueError("terminal runtime edges missing")
        for ref in terminal_refs:
            edge = _reread_edge(workspace, run_root, ref, slice_id=sid, stage="terminal", selector_identity=selector)
            terminal_index.setdefault(edge["acceptance_id"], []).append(ref)
        for aid in sorted(acceptance_by_slice.get(sid, set())):
            for stage in ("red", "green", "refactor"):
                ref = _canonical_edge(ready, stage, aid); _reread_edge(workspace, run_root, ref, slice_id=sid, stage=stage, selector_identity=selector)
                tuples.append({"tuple_key": f"{sid}|{aid}|{stage}", "slice_id": sid, "acceptance_id": aid, "stage": stage, "runtime_edge_ref": ref["path"], "runtime_edge_sha256": ref["sha256"], "selector_identity": selector, "current_snapshot_sha256": before["sha256"]})
            refs = terminal_index.get(aid, [])
            if not refs: raise ValueError(f"terminal Acceptance coverage missing: {aid}")
            ref = sorted(refs, key=lambda x: x["path"])[0]
            tuples.append({"tuple_key": f"{sid}|{aid}|terminal", "slice_id": sid, "acceptance_id": aid, "stage": "terminal", "runtime_edge_ref": ref["path"], "runtime_edge_sha256": ref["sha256"], "selector_identity": selector, "current_snapshot_sha256": before["sha256"]})
    if seen != set(acceptance_by_slice): raise ValueError("terminal predecessor set does not match slices")
    valid, findings = validate_closure(tuples, expected_keys, before["sha256"])
    if not valid: raise ValueError("runtime closure invalid: " + ",".join(findings))
    after = current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit)
    if after["sha256"] != before["sha256"]: raise ValueError("current snapshot changed during Q8")
    result = {"schema": "quick-dev.implementation-complete-result.v2", "predicate": "implementation-complete", "status": "pass", "plan_sha256": sha256_bytes(semantic_plan.read_bytes()), "current_snapshot_sha256": after["sha256"], "predecessors": [dict(x) for x in predecessors], "runtime_closure_tuples": tuples, "runtime_closure_sha256": sha256_value(tuples), "authorizes": []}
    create_json(out, result); return result
