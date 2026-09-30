"""Deterministic Q7/Q8 coverage predicates for current Quick Dev plans."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from closure_predicate import validate_runtime_closure
from runtime_evidence import HASH_RE, current_snapshot, create_json, expected_tuple_keys, load_json, resolve_file, sha256_bytes, sha256_value


def _git_changed_paths(workspace: Path, source_commit: str, root_path: str) -> set[str]:
    """Return tracked and untracked paths changed below one frozen root."""
    args = ["git", "diff", "--name-only", source_commit, "--", root_path]
    tracked = subprocess.run(args, cwd=workspace, capture_output=True, text=True, check=False)
    if tracked.returncode != 0:
        return set()
    values = {line.replace("\\", "/") for line in tracked.stdout.splitlines() if line.strip()}
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", root_path],
        cwd=workspace, capture_output=True, text=True, check=False,
    )
    if untracked.returncode == 0:
        values.update(line.replace("\\", "/") for line in untracked.stdout.splitlines() if line.strip())
    # Acceptance materializes its own run inputs after the Q8 snapshot was
    # frozen. Those files are evidence transport, not runtime plan content.
    values = {
        item for item in values
        if "/acceptance-inputs/" not in item
        and "/.acceptance-snapshots/" not in item
        and not item.endswith("/acceptance-projection-request.v1.json")
        and "/acceptance-run-request." not in item
    }
    return values


def _path_allowed(path: str, allowed: set[str]) -> bool:
    return any(path == item or path.startswith(item.rstrip("/") + "/") for item in allowed)


def _semantic_index(bundle: Mapping[str, Any], slice_id: str) -> tuple[Mapping[str, Any], dict[str, set[str]]]:
    slices, acceptances = bundle.get("slices"), bundle.get("acceptances")
    if not isinstance(slices, list) or not isinstance(acceptances, list):
        raise ValueError("semantic plan incomplete")
    selected = next((x for x in slices if isinstance(x, Mapping) and x.get("slice_id") == slice_id), None)
    if selected is None:
        raise ValueError("slice not declared")
    amap = {x.get("acceptance_id"): x for x in acceptances if isinstance(x, Mapping)}
    expected: dict[str, set[str]] = {}
    for aid in selected.get("acceptance_ids", []):
        item = amap.get(aid)
        assertion_ids = item.get("assertion_ids") if isinstance(item, Mapping) else None
        if not isinstance(assertion_ids, list) or not assertion_ids:
            raise ValueError("Acceptance assertions invalid")
        expected[aid] = set(assertion_ids)
    if not expected:
        raise ValueError("slice has no active Acceptance")
    return selected, expected


def _reread_edge(workspace: Path, run_root: Path, ref: Mapping[str, str], *, slice_id: str, stage: str, selector_identity: str) -> dict[str, Any]:
    path, expected_sha = ref.get("path"), ref.get("sha256")
    if not isinstance(path, str) or not isinstance(expected_sha, str):
        raise ValueError("runtime edge ref invalid")
    edge = load_json(resolve_file(run_root, path))
    if sha256_value(edge) != expected_sha:
        raise ValueError("runtime edge hash stale")
    if edge.get("slice_id") != slice_id or edge.get("stage") != stage or edge.get("selector_identity") != selector_identity:
        raise ValueError("runtime edge identity stale")
    observation = load_json(resolve_file(run_root, edge["observation_ref"]))
    receipt = load_json(resolve_file(run_root, edge["receipt_ref"]))
    if sha256_value(observation) != edge.get("observation_sha256"):
        raise ValueError("observation hash stale")
    if sha256_value(receipt) != edge.get("receipt_sha256") or observation.get("receipt_sha256") != edge.get("receipt_sha256"):
        raise ValueError("receipt hash stale")
    descriptor_path = run_root / "descriptors" / f"{stage}.json"
    if not descriptor_path.is_file():
        raise ValueError("frozen descriptor missing")
    descriptor = load_json(descriptor_path)
    if sha256_value(descriptor) != edge.get("descriptor_sha256"):
        raise ValueError("descriptor hash stale")
    from case_evidence import assertion_cases, reread_stage_cases, VERSION
    cases = assertion_cases(descriptor, receipt)
    if stage in {"green", "refactor"} and cases != reread_stage_cases(run_root, "red"):
        raise ValueError("case-set-changed-since-red")
    key = (edge.get("acceptance_id"), edge.get("assertion_id"))
    if (edge.get("case_evidence_schema") != VERSION or key not in cases
            or edge.get("case_ids") != cases[key]
            or edge.get("case_report_sha256") != receipt.get("case_report_sha256")):
        raise ValueError("case-edge-binding-stale")
    for node in cases[key]:
        relative = node.split("::", 1)[0]
        if descriptor["cwd"] != ".":
            relative = descriptor["cwd"] + "/" + relative
        case_file = resolve_file(workspace, relative)
        if sha256_bytes(case_file.read_bytes()) != receipt["target_hashes"].get(relative):
            raise ValueError("case-target-stale:" + node)
    target = resolve_file(workspace, edge["target_ref"])
    fixture = resolve_file(workspace, edge["fixture_ref"])
    if sha256_bytes(target.read_bytes()) != edge.get("target_sha256"):
        raise ValueError("target hash stale")
    if sha256_bytes(fixture.read_bytes()) != edge.get("fixture_sha256"):
        raise ValueError("fixture hash stale")
    if edge.get("predicate_result") is not True or edge.get("observed") is not True:
        raise ValueError("non-observed/predicate-false edge cannot cover")
    return edge


def validate_slice_ready(*, workspace: Path, semantic_plan: Path, run_root: Path, slice_id: str, snapshot_roots: Sequence[Mapping[str, str]], source_commit: str, out: Path, base_commit: str | None = None) -> dict[str, Any]:
    bundle = load_json(semantic_plan)
    _selected, expected_assertions = _semantic_index(bundle, slice_id)
    from behavior_routing import read_route, stage_map, verify_stage, current_result, verify_case_continuity
    routed = "behavior_routing" in bundle
    route = read_route(workspace, bundle, run_root, slice_id) if routed else None
    requirements = stage_map(bundle, slice_id, route) if routed else {aid: ("red", "green", "refactor") for aid in expected_assertions}
    snapshot = current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit)
    stage_selectors = {}
    selector: str | None = None
    final_candidate: str | None = None
    coverage: dict[str, Any] = {}
    for stage in ("red", "green", "refactor", "regression"):
        stage_expected = {aid: ids for aid, ids in expected_assertions.items() if stage in requirements[aid]}
        if not stage_expected:
            continue
        result = load_json(run_root / "canonical-evidence" / stage / "stage-result.v2.json")
        required_outcome = "fail" if stage == "red" else "pass"
        if result.get("stage") != stage or result.get("slice_id") != slice_id or result.get("predicate_result") is not True or result.get("verification_outcome") != required_outcome:
            raise ValueError(f"{stage} is not admissible evidence")
        current_selector = result.get("selector_identity")
        if not isinstance(current_selector, str):
            raise ValueError("selector identity missing")
        stage_selectors[stage] = current_selector
        if stage != "regression":
            if selector is None:
                selector = current_selector
            elif selector != current_selector:
                raise ValueError("RED/GREEN/REFACTOR selector drift")
        if routed:
            descriptor = load_json(run_root / "descriptors" / (stage + ".json"))
            verify_stage(workspace, bundle, run_root, descriptor, require_probe_current=False)
            verify_case_continuity(descriptor, load_json(run_root / "canonical-evidence" / stage / "process-receipt.v2.json"), route)
            if stage in {"refactor", "regression"}:
                current_result(workspace, bundle, slice_id, result)
        if stage in {"green", "refactor", "regression"}:
            if routed and stage == "regression" and final_candidate is not None and final_candidate != result.get("candidate_hash"):
                raise ValueError("behavior-routing:mixed-candidate-drift")
            final_candidate = result.get("candidate_hash")
        refs = result.get("runtime_edges")
        if not isinstance(refs, list) or not refs:
            raise ValueError("runtime edges missing")
        observed = {aid: {} for aid in stage_expected}
        for ref in refs:
            edge = _reread_edge(workspace, run_root, ref, slice_id=slice_id, stage=stage, selector_identity=current_selector)
            if edge.get("candidate_hash") != result.get("candidate_hash"):
                raise ValueError("edge/stage candidate mismatch")
            aid, assertion_id = edge.get("acceptance_id"), edge.get("assertion_id")
            if aid not in stage_expected or assertion_id not in stage_expected[aid] or assertion_id in observed[aid]:
                raise ValueError("assertion edge outside exact universe or duplicate")
            observed[aid][assertion_id] = {"path": ref["path"], "sha256": ref["sha256"]}
        for aid, expected in stage_expected.items():
            if set(observed[aid]) != expected:
                raise ValueError(f"{stage} assertion exact cover failed for {aid}")
        coverage[stage] = {aid: [observed[aid][assertion] for assertion in sorted(observed[aid])] for aid in sorted(observed)}
    result = {
        "schema": "quick-dev.slice-ready-result.v2",
        "predicate": "slice-ready",
        "status": "pass",
        "slice_id": slice_id,
        "run_id": run_root.name,
        "plan_sha256": sha256_bytes(semantic_plan.read_bytes()),
        "candidate_hash": final_candidate,
        "selector_identity": selector,
        "current_snapshot_sha256": snapshot["sha256"],
        "assertion_coverage": coverage,
        "authorizes": [],
    }
    if routed:
        result["behavior_route_sha256"] = sha256_value(route)
        result["stage_selectors"] = stage_selectors
        result["selector_identity"] = selector or stage_selectors["regression"]
    create_json(out, result)
    return result


def _canonical_edge(ready: Mapping[str, Any], stage: str, aid: str) -> Mapping[str, str]:
    coverage = ready.get("assertion_coverage")
    refs = coverage.get(stage, {}).get(aid, []) if isinstance(coverage, Mapping) else []
    if not isinstance(refs, list) or not refs or not isinstance(refs[0], Mapping):
        raise ValueError("canonical edge missing")
    return refs[0]


def _validate_detached_binding(binding: Mapping[str, Any] | None, profile: str) -> Mapping[str, Any] | None:
    if profile != "self-hosted":
        if binding is not None:
            raise ValueError("detached promotion binding is only valid for self-hosted profile")
        return None
    if not isinstance(binding, Mapping):
        raise ValueError("self-hosted terminal requires validated detached promotion binding")
    if binding.get("schema") != "quick-dev.detached-promotion-binding.v1" or binding.get("validated") is not True:
        raise ValueError("detached promotion binding invalid")
    if binding.get("validator_identity") != "quick-dev-detached-bundle-validator.v1":
        raise ValueError("detached promotion validator identity invalid")
    if not isinstance(binding.get("bundle_sha256"), str) or not HASH_RE.fullmatch(binding["bundle_sha256"]):
        raise ValueError("detached promotion bundle hash invalid")
    return dict(binding)


def _replay_snapshot(workspace, roots, source_commit, base_commit, terminal_input, allowed_changed_paths=None):
    """Recheck frozen runtime roots; Acceptance's new evidence is not runtime input."""
    from runtime_evidence import ROOT_KINDS, hash_path, safe_relative
    snapshot = terminal_input.get("snapshot_manifest")
    if not isinstance(snapshot, dict) or snapshot.get("sha256") != sha256_value({k: v for k, v in snapshot.items() if k != "sha256"}):
        raise ValueError("completion snapshot manifest missing or stale")
    frozen = snapshot.get("roots", [])
    expected = {r["root_kind"]: r for r in roots}
    if set(expected) != set(ROOT_KINDS) or len(roots) != 8 or len(frozen) != 8 or {r["root_kind"] for r in frozen} != set(expected):
        raise ValueError("completion snapshot roots mismatch")
    if snapshot.get("git_delta", {}).get("base_commit") != (base_commit or source_commit):
        raise ValueError("completion snapshot base mismatch")
    for row in frozen:
        spec = expected[row["root_kind"]]
        if any(row.get(k) != spec.get(k) for k in ("repository_relative_posix_path", "inclusion_reason")) or row.get("source_commit") != source_commit:
            raise ValueError("completion snapshot identity mismatch")
        path = (workspace / safe_relative(row["repository_relative_posix_path"])).resolve()
        path.relative_to(workspace.resolve())
        if hash_path(path) != row["content_sha256"]:
            allowed = {str(item).replace("\\", "/").strip("/") for item in (allowed_changed_paths or [])}
            if row["root_kind"] not in {"plan", "plan_state_transition"} or not allowed:
                raise ValueError("completion runtime root stale: " + row["root_kind"])
            changed = _git_changed_paths(workspace, source_commit, row["repository_relative_posix_path"])
            root_prefix = row["repository_relative_posix_path"].rstrip("/") + "/"
            scoped = {item for item in changed if item == row["repository_relative_posix_path"] or item.startswith(root_prefix)}
            if not scoped or any(not _path_allowed(item, allowed) for item in scoped):
                raise ValueError("completion runtime root stale: " + row["root_kind"])
    return snapshot


def publish_implementation_complete(
    *,
    workspace: Path,
    semantic_plan: Path,
    predecessors: Sequence[Mapping[str, str]],
    snapshot_roots: Sequence[Mapping[str, str]],
    source_commit: str,
    out: Path,
    base_commit: str | None = None,
    detached_promotion_binding: Mapping[str, Any] | None = None,
    profile: str = "standard",
    verify_existing: bool = False,
    allowed_changed_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    detached_binding = _validate_detached_binding(detached_promotion_binding, profile)
    bundle = load_json(semantic_plan)
    from behavior_routing import read_route, stage_map, verify_stage, current_result, verify_case_continuity, validate_plan
    routed = "behavior_routing" in bundle
    validate_plan(bundle)
    expected_keys = set() if routed else expected_tuple_keys(bundle)
    frozen_input = load_json(out.with_name("terminal-input.v2.json")) if verify_existing else None
    before = (_replay_snapshot(workspace, snapshot_roots, source_commit, base_commit, frozen_input, allowed_changed_paths)
              if verify_existing else current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit))
    cover = bundle.get("final_plan_coverage")
    acceptance_by_slice: dict[str, set[str]] = {}
    if not isinstance(cover, list):
        raise ValueError("final plan coverage missing")
    for edge in cover:
        if isinstance(edge, Mapping):
            acceptance_by_slice.setdefault(str(edge.get("slice_id")), set()).add(str(edge.get("acceptance_id")))
    seen: set[str] = set()
    tuples: list[dict[str, str]] = []
    terminal_descriptors: list[dict[str, str]] = []
    final_candidates: dict[str, str] = {}
    terminal_selectors: dict[str, str] = {}
    for predecessor in predecessors:
        sid, run_raw, ready_raw = predecessor.get("slice_id"), predecessor.get("run_root"), predecessor.get("result_ref")
        if not all(isinstance(x, str) and x for x in (sid, run_raw, ready_raw)) or sid in seen:
            raise ValueError("terminal predecessor invalid")
        seen.add(sid)
        run_root = (workspace / run_raw).resolve()
        try:
            run_root.relative_to(workspace.resolve())
        except ValueError as exc:
            raise ValueError("terminal predecessor run root escapes workspace") from exc
        ready = load_json(resolve_file(workspace, ready_raw))
        if sha256_value(ready) != predecessor.get("result_sha256") or ready.get("slice_id") != sid or ready.get("status") != "pass":
            raise ValueError("slice-ready predecessor stale")
        if ready.get("current_snapshot_sha256") != before["sha256"]:
            raise ValueError("slice-ready snapshot stale")
        route = read_route(workspace, bundle, run_root, sid) if routed else None
        requirements = stage_map(bundle, sid, route) if routed else {aid: ("red", "green", "refactor") for aid in acceptance_by_slice[sid]}
        if routed:
            if ready.get("behavior_route_sha256") != sha256_value(route):
                raise ValueError("behavior-routing:ready-probe-stale")
            for aid, stages in requirements.items():
                expected_keys.update(f"{sid}|{aid}|{stage}" for stage in (*stages, "terminal"))
        tdd_selector = ready.get("selector_identity")
        final_candidate = ready.get("candidate_hash")
        if not isinstance(final_candidate, str) or not HASH_RE.fullmatch(final_candidate):
            raise ValueError("slice-ready final candidate invalid")
        final_candidates[sid] = final_candidate
        terminal_descriptor_path = run_root / "descriptors" / "terminal.json"
        if not terminal_descriptor_path.is_file():
            raise ValueError("terminal descriptor missing")
        terminal_descriptor = load_json(terminal_descriptor_path)
        terminal_descriptors.append({
            "slice_id": sid,
            "ref": terminal_descriptor_path.relative_to(workspace).as_posix(),
            "sha256": sha256_value(terminal_descriptor),
        })
        terminal = load_json(run_root / "canonical-evidence" / "terminal" / "stage-result.v2.json")
        if terminal.get("predicate_result") is not True or terminal.get("verification_outcome") != "pass" or terminal.get("candidate_hash") != final_candidate:
            raise ValueError("terminal stage not current process pass")
        if routed:
            verify_stage(workspace, bundle, run_root, terminal_descriptor)
            current_result(workspace, bundle, sid, terminal)
        terminal_selector = terminal.get("selector_identity")
        if not isinstance(terminal_selector, str) or not terminal_selector:
            raise ValueError("terminal selector identity missing")
        terminal_selectors[sid] = terminal_selector
        terminal_refs = terminal.get("runtime_edges")
        terminal_index: dict[str, list[Mapping[str, str]]] = {}
        _selected, required_assertions = _semantic_index(bundle, sid)
        terminal_assertions: dict[str, set[str]] = {}
        if not isinstance(terminal_refs, list) or not terminal_refs:
            raise ValueError("terminal runtime edges missing")
        for ref in terminal_refs:
            edge = _reread_edge(workspace, run_root, ref, slice_id=sid, stage="terminal", selector_identity=terminal_selector)
            aid, assertion_id = edge["acceptance_id"], edge["assertion_id"]
            observed_ids = terminal_assertions.setdefault(aid, set())
            if assertion_id in observed_ids:
                raise ValueError("terminal assertion duplicate")
            observed_ids.add(assertion_id)
            terminal_index.setdefault(edge["acceptance_id"], []).append(ref)
        if terminal_assertions != required_assertions:
            raise ValueError("terminal assertion exact cover")
        for aid in sorted(acceptance_by_slice.get(sid, set())):
            for stage in requirements[aid]:
                selector_for_stage = ready.get("stage_selectors", {}).get(stage) if routed else tdd_selector
                if routed:
                    stage_result = load_json(run_root / "canonical-evidence" / stage / "stage-result.v2.json")
                    descriptor = load_json(run_root / "descriptors" / (stage + ".json"))
                    verify_stage(workspace, bundle, run_root, descriptor, require_probe_current=False)
                    verify_case_continuity(descriptor, load_json(run_root / "canonical-evidence" / stage / "process-receipt.v2.json"), route)
                    if stage_result.get("predicate_result") is not True or stage_result.get("selector_identity") != selector_for_stage:
                        raise ValueError("behavior-routing:stage-result-stale")
                    if stage in {"refactor", "regression"}:
                        current_result(workspace, bundle, sid, stage_result)
                # The tuple remains per Acceptance; re-read every assertion proof.
                refs = ready.get("assertion_coverage", {}).get(stage, {}).get(aid, [])
                actual = []
                for assertion_ref in refs:
                    checked = _reread_edge(workspace, run_root, assertion_ref, slice_id=sid,
                                           stage=stage, selector_identity=selector_for_stage)
                    if checked["acceptance_id"] != aid:
                        raise ValueError("Q8 assertion Acceptance mismatch")
                    actual.append(checked["assertion_id"])
                if set(actual) != required_assertions[aid] or len(actual) != len(set(actual)):
                    raise ValueError("Q8 assertion exact cover")
                ref = _canonical_edge(ready, stage, aid)
                _reread_edge(workspace, run_root, ref, slice_id=sid, stage=stage, selector_identity=selector_for_stage)
                tuples.append({
                    "tuple_key": f"{sid}|{aid}|{stage}",
                    "slice_id": sid,
                    "acceptance_id": aid,
                    "stage": stage,
                    "runtime_edge_ref": ref["path"],
                    "runtime_edge_sha256": ref["sha256"],
                    "selector_identity": selector_for_stage,
                    "current_snapshot_sha256": before["sha256"],
                })
            refs = terminal_index.get(aid, [])
            if not refs:
                raise ValueError(f"terminal Acceptance coverage missing: {aid}")
            ref = sorted(refs, key=lambda x: x["path"])[0]
            tuples.append({
                "tuple_key": f"{sid}|{aid}|terminal",
                "slice_id": sid,
                "acceptance_id": aid,
                "stage": "terminal",
                "runtime_edge_ref": ref["path"],
                "runtime_edge_sha256": ref["sha256"],
                "selector_identity": terminal_selector,
                "current_snapshot_sha256": before["sha256"],
            })
    if seen != set(acceptance_by_slice):
        raise ValueError("terminal predecessor set does not match slices")
    valid, findings = validate_runtime_closure(tuples, expected_keys, before["sha256"])
    if not valid:
        raise ValueError("runtime closure invalid: " + ",".join(findings))

    slices = bundle.get("slices")
    if not isinstance(slices, list):
        raise ValueError("V6 partition manifest missing")
    active_acceptances = sorted({aid for aids in acceptance_by_slice.values() for aid in aids})
    predicates = sorted({str(item.get("terminal_predicate")) for item in slices if isinstance(item, Mapping) and item.get("terminal_predicate")})
    terminal_input = {
        "schema": "quick-dev.terminal-input.v2",
        "snapshot_manifest": before,
        "plan_id": bundle.get("plan_id"),
        "plan_sha256": sha256_bytes(semantic_plan.read_bytes()),
        "v6_partition_manifest_sha256": sha256_value(slices),
        "terminal_predicates": predicates,
        "terminal_descriptors": sorted(terminal_descriptors, key=lambda item: item["slice_id"]),
        "evaluator_identity": "quick-dev-terminal-predicate.v2",
        "current_snapshot_sha256": before["sha256"],
        "predecessors": [dict(x) for x in predecessors],
        "active_acceptance_ids": active_acceptances,
        "final_candidates": dict(sorted(final_candidates.items())),
        "terminal_selectors": dict(sorted(terminal_selectors.items())),
        "runtime_closure_tuples": tuples,
        "profile": profile,
        "detached_promotion_binding": detached_binding,
    }

    after = (_replay_snapshot(workspace, snapshot_roots, source_commit, base_commit, frozen_input)
             if verify_existing else current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit))
    if after["sha256"] != before["sha256"]:
        raise ValueError("current snapshot changed during Q8")
    terminal_input["current_snapshot_sha256"] = after["sha256"]
    terminal_input_path = out.with_name("terminal-input.v2.json")
    result = {
        "schema": "quick-dev.implementation-complete-result.v2",
        "predicate": "implementation-complete",
        "status": "pass",
        "profile": profile,
        "plan_sha256": sha256_bytes(semantic_plan.read_bytes()),
        "current_snapshot_sha256": after["sha256"],
        "predecessors": [dict(x) for x in predecessors],
        "runtime_closure_tuples": tuples,
        "runtime_closure_sha256": sha256_value(tuples),
        "terminal_input_ref": terminal_input_path.relative_to(workspace).as_posix(),
        "terminal_input_sha256": sha256_value(terminal_input),
        "detached_promotion_binding": detached_binding,
        "evaluator_identity": "quick-dev-terminal-predicate.v2",
        "authorizes": [],
    }
    if verify_existing:
        # ADR-0058: rederive Q8 proof without executing a process or publishing.
        if load_json(terminal_input_path) != terminal_input or load_json(out) != result:
            raise ValueError("implementation completion replay mismatch")
    else:
        create_json(terminal_input_path, terminal_input)
        create_json(out, result)
    return result
