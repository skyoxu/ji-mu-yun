"""Current Quick Dev Q0/Q1/Q2/Q4/recovery predicates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Mapping, Sequence

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path: sys.path.insert(0, str(TOOLS))
from legacy_compat import inspect_legacy_plan
from runtime_evidence import HASH_RE, create_json, current_snapshot, environment_probe, load_json, safe_relative, selector_identity_from_descriptor, sha256_value, validate_descriptor

ACTIONS = ("run-preflight", "author-red", "run-red", "implement", "run-green", "run-refactor", "validate-slice", "run-terminal", "repair-vdd", "stop", "environment-blocked")
PROFILES = ("fast-ship", "standard", "self-hosted")


def validate_profile(profile: str) -> None:
    if profile not in PROFILES: raise ValueError("execution profile invalid")


def _slice(bundle: Mapping[str, Any], slice_id: str) -> Mapping[str, Any]:
    slices = bundle.get("slices")
    if not isinstance(slices, list): raise ValueError("semantic plan slices missing")
    matches = [x for x in slices if isinstance(x, Mapping) and x.get("slice_id") == slice_id]
    if len(matches) != 1: raise ValueError("slice identity missing or ambiguous")
    return matches[0]


def _assert_hash(value: str, label: str) -> None:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value): raise ValueError(f"{label} must be sha256")


def recommendation(*, bundle: Mapping[str, Any], slice_id: str, state: Mapping[str, Any], changed_paths: Sequence[str], profile: str) -> dict[str, Any]:
    validate_profile(profile); selected = _slice(bundle, slice_id)
    for path in changed_paths: safe_relative(path)
    invalidated = invalidate_by_change(selected, changed_paths)
    if invalidated:
        action, reason = "run-red", "change-impact-invalidated-lineage"
    else:
        lifecycle = str(state.get("state") or "planned-only")
        mapping = {
            "planned-only": ("run-preflight", "plan-not-preflighted"), "preflight-passed": ("author-red", "red-not-materialized"),
            "red-materialized": ("run-red", "red-not-observed"), "red-observed": ("implement", "expected-red-required"),
            "implementation-successor": ("run-green", "green-not-observed"), "green-observed": ("run-refactor", "refactor-not-observed"),
            "refactor-observed": ("validate-slice", "slice-not-ready"), "slice-ready": ("run-terminal", "terminal-pending"),
            "whole-plan-terminal": ("stop", "implementation-complete"),
        }
        action, reason = mapping.get(lifecycle, ("repair-vdd", "invalid-lifecycle-state"))
    return {"schema": "quick-dev.recommendation.v1", "plan_id": bundle.get("plan_id"), "plan_hash": sha256_value(dict(bundle)), "slice_id": slice_id, "profile": profile, "recommended_action": action, "forbidden_actions": [x for x in ACTIONS if x != action], "reason_code": reason, "blocked_by": [], "reusable_observations": [], "invalidated_observations": invalidated}


def invalidate_by_change(slice_item: Mapping[str, Any], changed_paths: Sequence[str]) -> list[str]:
    snapshots = set(slice_item.get("execution_snapshot_paths", [])); owners = set(slice_item.get("production_owners", []))
    invalidated: list[str] = []
    for raw in changed_paths:
        path = safe_relative(raw)
        if path in snapshots: invalidated.extend(["red", "green", "refactor", "terminal"])
        elif path in owners: invalidated.extend(["green", "refactor", "terminal"])
    return sorted(set(invalidated), key=("red", "green", "refactor", "terminal").index)


def preflight(*, workspace: Path, semantic_plan: Path, slice_id: str, candidate_hash: str, profile: str) -> dict[str, Any]:
    validate_profile(profile); _assert_hash(candidate_hash, "candidate_hash")
    bundle = load_json(semantic_plan); selected = _slice(bundle, slice_id); errors: list[str] = []
    for key in ("acceptance_ids", "failure_intent_ids", "allowed_write_paths", "execution_snapshot_paths", "terminal_predicate"):
        if key not in selected: errors.append(f"slice:{key}:missing")
    for path in list(selected.get("allowed_write_paths", [])) + list(selected.get("execution_snapshot_paths", [])):
        try: safe_relative(path)
        except ValueError: errors.append(f"unsafe-path:{path}")
    env = environment_probe()
    if not env.get("available"): return {"status": "environment-blocked", "errors": errors, "environment": env}
    return {"status": "preflight-passed" if not errors else "repair-vdd", "errors": errors, "environment": env}


def materialize_descriptor(*, bundle: Mapping[str, Any], slice_id: str, stage: str, run_id: str, candidate_hash: str, argv: Sequence[str], cwd: str, timeout_seconds: int, target_refs: Sequence[str], fixture_refs: Sequence[str]) -> dict[str, Any]:
    _assert_hash(candidate_hash, "candidate_hash"); selected = _slice(bundle, slice_id)
    if stage not in ("red", "green", "refactor", "terminal"): raise ValueError("stage invalid")
    if not argv or any(not isinstance(x, str) or not x for x in argv): raise ValueError("argv invalid")
    if cwd != ".": safe_relative(cwd)
    snapshots = set(selected.get("execution_snapshot_paths", []))
    for ref in [*target_refs, *fixture_refs]:
        safe_relative(ref)
        if ref not in snapshots: raise ValueError(f"target/fixture ref is outside execution snapshot paths: {ref}")
    amap = {x.get("acceptance_id"): x for x in bundle.get("acceptances", []) if isinstance(x, Mapping)}
    assertions = []
    for aid in selected.get("acceptance_ids", []):
        item = amap.get(aid)
        if not isinstance(item, Mapping): raise ValueError("Acceptance missing")
        for assertion_id in item.get("assertion_ids", []): assertions.append({"acceptance_id": aid, "assertion_id": assertion_id, "case_source_ref": target_refs[0], "target_ref": target_refs[0], "fixture_ref": fixture_refs[0]})
    descriptor = {"run_id": run_id, "plan_id": bundle["plan_id"], "slice_id": slice_id, "stage": stage, "candidate_hash": candidate_hash, "argv": list(argv), "cwd": cwd, "shell": False, "timeout_seconds": timeout_seconds, "target_refs": list(target_refs), "fixture_refs": list(fixture_refs), "acceptance_assertions": assertions}
    validate_descriptor(descriptor); return descriptor


def successor_descriptor(red_descriptor: Mapping[str, Any], *, stage: str, run_id: str, candidate_hash: str) -> dict[str, Any]:
    validate_descriptor(red_descriptor); _assert_hash(candidate_hash, "candidate_hash")
    if stage not in {"green", "refactor", "terminal"}: raise ValueError("successor stage invalid")
    result = dict(red_descriptor); result.update({"stage": stage, "run_id": run_id, "candidate_hash": candidate_hash})
    validate_descriptor(result)
    if selector_identity_from_descriptor(result) != selector_identity_from_descriptor(red_descriptor): raise ValueError("successor selector drift")
    return result


def validate_expected_red(stage_result: Mapping[str, Any]) -> None:
    if stage_result.get("stage") != "red" or stage_result.get("predicate_result") is not True or stage_result.get("verification_outcome") != "fail" or stage_result.get("failure_family") != "expected-red": raise ValueError("Q4 requires clean expected-red")


def validate_write_delta(changed_paths: Sequence[str], allowed_paths: Sequence[str], forbidden_paths: Sequence[str] = ()) -> None:
    allowed, forbidden = set(allowed_paths), set(forbidden_paths)
    if not allowed: raise ValueError("production write set empty")
    for raw in changed_paths:
        path = safe_relative(raw)
        if path not in allowed or path in forbidden: raise ValueError(f"write-set violation: {path}")


def q4_gate(*, stage_result: Mapping[str, Any], before_snapshot: Mapping[str, Any], after_snapshot: Mapping[str, Any], changed_paths: Sequence[str], slice_item: Mapping[str, Any]) -> dict[str, Any]:
    validate_expected_red(stage_result)
    if before_snapshot.get("schema") != "current-snapshot-resolver.v1" or after_snapshot.get("schema") != "current-snapshot-resolver.v1": raise ValueError("Q4 requires current snapshot resolver")
    validate_write_delta(changed_paths, slice_item.get("allowed_write_paths", []))
    if any(path in set(slice_item.get("execution_snapshot_paths", [])) for path in changed_paths): raise ValueError("Q4 changed selector/fixture contract and invalidated RED")
    return {"status": "implementation-successor", "predecessor_red_sha256": sha256_value(dict(stage_result)), "before_snapshot_sha256": before_snapshot.get("sha256"), "after_snapshot_sha256": after_snapshot.get("sha256"), "changed_paths": list(changed_paths)}


def failure_fingerprint(observation: Mapping[str, Any], selector_identity: str) -> str:
    return sha256_value({"selector_identity": selector_identity, "stage": observation.get("stage"), "verification_outcome": observation.get("verification_outcome"), "failure_family": observation.get("failure_family"), "failure_id": observation.get("failure_id"), "exit_code": observation.get("exit_code"), "timed_out": observation.get("timed_out"), "observed_failure_ids": observation.get("observed_failure_ids", [])})


def stop_loss(previous: Sequence[str], current: str) -> dict[str, Any]:
    if previous and previous[-1] == current: return {"stop": True, "failure_family": "repeated-deterministic-failure", "action": "stop"}
    return {"stop": False, "failure_family": None, "action": "retry-after-input-change"}


def recovered_run(prior: Mapping[str, Any], *, current_slice_id: str, current_hashes: Mapping[str, str]) -> dict[str, Any]:
    required = ("run_id", "slice_id", "receipt_ref", "receipt_sha256", "observation_ref", "observation_sha256", "runtime_edge_refs")
    if any(key not in prior for key in required) or prior.get("slice_id") != current_slice_id: raise ValueError("recovery predecessor incomplete or wrong slice")
    if not isinstance(prior.get("runtime_edge_refs"), list) or not prior["runtime_edge_refs"]: raise ValueError("recovery runtime edges missing")
    for key, expected in current_hashes.items():
        if prior.get(key) != expected: raise ValueError(f"recovery stale identity: {key}")
    return {"schema": "quick-dev.recovered-run.v1", "evidence_state": "recovered-run", "source_run_id": prior["run_id"], "slice_id": current_slice_id, "receipt_ref": prior["receipt_ref"], "receipt_sha256": prior["receipt_sha256"], "observation_ref": prior["observation_ref"], "observation_sha256": prior["observation_sha256"], "runtime_edge_refs": list(prior["runtime_edge_refs"]), "verification_outcome": prior.get("verification_outcome", "incomplete")}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--plan", type=Path, required=True); parser.add_argument("--slice", dest="slice_id", required=True); parser.add_argument("--profile", choices=PROFILES, default="standard"); parser.add_argument("--state", type=Path); parser.add_argument("--changed-path", action="append", default=[]); parser.add_argument("--recommendation-only", action="store_true")
    args = parser.parse_args(); semantic = args.plan / "semantic-plan-bundle.v1.json"
    if not semantic.is_file():
        print(json.dumps(inspect_legacy_plan(args.plan), sort_keys=True)); return 1
    try:
        bundle = load_json(semantic); state = load_json(args.state) if args.state else {"state": "planned-only"}
        result = recommendation(bundle=bundle, slice_id=args.slice_id, state=state, changed_paths=args.changed_path, profile=args.profile)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"recommended_action": "repair-vdd", "reason": str(exc)}, sort_keys=True)); return 1
    print(json.dumps(result, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
