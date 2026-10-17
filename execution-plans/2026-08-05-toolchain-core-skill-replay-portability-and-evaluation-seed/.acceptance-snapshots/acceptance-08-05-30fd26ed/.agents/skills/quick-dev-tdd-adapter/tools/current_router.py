"""Current Quick Dev Q0/Q1/Q2/Q4/recovery predicates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from legacy_compat import inspect_legacy_plan
from runtime_evidence import HASH_RE, environment_probe, load_json, safe_relative, selector_identity_from_descriptor, sha256_value, validate_descriptor

ACTIONS = ("run-probe", "run-regression", "route-behaviors", "run-preflight", "author-red", "run-red", "implement", "run-green", "run-refactor", "validate-slice", "run-terminal", "repair-vdd", "stop", "environment-blocked")
_PREFLIGHT_FIELDS = ("complexity_class", "verification_lane", "context_lookup_required", "context_lookup_reason", "minimum_red_scope", "upgrade_conditions")


def _authority_json(name: str) -> Mapping[str, Any]:
    value = json.loads((TOOLS / name).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must contain object")
    return value


def profile_contract(profile: str) -> Mapping[str, Any]:
    policy = _authority_json("profile-policy.v1.json")
    profiles = policy.get("profiles")
    if not isinstance(profiles, Mapping) or profile not in profiles or not isinstance(profiles[profile], Mapping):
        raise ValueError("execution profile invalid")
    truth = policy.get("truth_floor")
    if not isinstance(truth, Mapping) or not all(value is True for value in truth.values()):
        raise ValueError("profile truth floor is invalid")
    return profiles[profile]


def _slice(bundle: Mapping[str, Any], slice_id: str) -> Mapping[str, Any]:
    slices = bundle.get("slices")
    if not isinstance(slices, list):
        raise ValueError("semantic plan slices missing")
    matches = [x for x in slices if isinstance(x, Mapping) and x.get("slice_id") == slice_id]
    if len(matches) != 1:
        raise ValueError("slice identity missing or ambiguous")
    return matches[0]


def _assert_hash(value: str, label: str) -> None:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise ValueError(f"{label} must be sha256")


def impact_for_kinds(change_kinds: Sequence[str]) -> list[str]:
    matrix = _authority_json("change-impact-matrix.v1.json")
    rules = matrix.get("rules")
    if not isinstance(rules, list):
        raise ValueError("change impact matrix invalid")
    by_kind = {item.get("change_kind"): item.get("invalidate") for item in rules if isinstance(item, Mapping)}
    invalidated: set[str] = set()
    for kind in change_kinds:
        if kind not in by_kind or not isinstance(by_kind[kind], list):
            raise ValueError(f"unknown change kind: {kind}")
        invalidated.update(str(x) for x in by_kind[kind])
    order = ["descriptor", "coverage", "red", "green", "refactor", "successors", "terminal"]
    return sorted(invalidated, key=lambda x: order.index(x) if x in order else len(order))


def _matches_declared(path: str, declared: Sequence[str]) -> bool:
    for raw in declared:
        root = safe_relative(str(raw)).rstrip("/")
        if path == root or path.startswith(root + "/"):
            return True
    return False


def infer_change_kinds(slice_item: Mapping[str, Any], changed_paths: Sequence[str]) -> list[str]:
    snapshots = [str(x) for x in slice_item.get("execution_snapshot_paths", []) if isinstance(x, str)]
    owners = [str(x) for x in slice_item.get("production_owners", []) if isinstance(x, str)]
    kinds: set[str] = set()
    for raw in changed_paths:
        path = safe_relative(raw)
        lowered = path.lower()
        if _matches_declared(path, snapshots):
            kinds.add("selector_fixture_target_case_source")
        elif _matches_declared(path, owners):
            kinds.add("production_owner")
        elif any(token in lowered for token in ("descriptor", "materializer", "stage_pipeline", "stable_runner")):
            kinds.add("descriptor_compiler")
        elif any(token in lowered for token in ("validator", "judge", "runtime_evidence", "coverage_predicate", "closure_predicate", "semantic_compiler")):
            kinds.add("validator_or_judge")
        elif (path.startswith("docs/") or path.startswith("_bmad-output/")) and Path(path).suffix.lower() in {".md", ".txt", ".rst"}:
            kinds.add("ordinary_documentation")
        else:
            raise ValueError(f"unclassified changed path must be explicitly typed: {path}")
    return sorted(kinds)


def _observation_projection(
    *,
    observations: Sequence[Mapping[str, Any]],
    slice_id: str,
    invalidated_stages: Sequence[str],
    current_snapshot_sha256: str | None,
) -> tuple[list[str], list[str]]:
    invalidated_stage_set = set(invalidated_stages)
    reusable: list[str] = []
    invalidated: list[str] = []
    for index, item in enumerate(observations):
        if not isinstance(item, Mapping):
            raise ValueError(f"observation index[{index}] must be object")
        observation_id = item.get("observation_id")
        stage = item.get("stage")
        observed_slice = item.get("slice_id")
        snapshot_sha = item.get("current_snapshot_sha256")
        if not isinstance(observation_id, str) or not observation_id:
            raise ValueError(f"observation index[{index}] missing observation_id")
        if observed_slice != slice_id:
            continue
        stale_snapshot = bool(current_snapshot_sha256 and snapshot_sha and snapshot_sha != current_snapshot_sha256)
        if stage in invalidated_stage_set or stale_snapshot:
            invalidated.append(observation_id)
        else:
            reusable.append(observation_id)
    return sorted(set(reusable)), sorted(set(invalidated))


def recommendation(
    *,
    bundle: Mapping[str, Any],
    slice_id: str,
    state: Mapping[str, Any],
    changed_paths: Sequence[str],
    change_kinds: Sequence[str],
    profile: str,
    observation_index: Sequence[Mapping[str, Any]] = (),
    current_snapshot_sha256: str | None = None,
) -> dict[str, Any]:
    profile_contract(profile)
    selected = _slice(bundle, slice_id)
    if current_snapshot_sha256 is not None:
        _assert_hash(current_snapshot_sha256, "current_snapshot_sha256")
    kinds = list(change_kinds) + infer_change_kinds(selected, changed_paths)
    kinds = sorted(set(kinds))
    invalidated_stages = impact_for_kinds(kinds) if kinds else []
    routed = "behavior_routing" in bundle
    if routed:
        from behavior_routing import validate_plan
        validate_plan(bundle)
        if "red" in invalidated_stages:
            invalidated_stages.append("probe")
        if "green" in invalidated_stages:
            invalidated_stages.append("regression")
    reusable, invalidated = _observation_projection(
        observations=observation_index,
        slice_id=slice_id,
        invalidated_stages=invalidated_stages,
        current_snapshot_sha256=current_snapshot_sha256,
    )
    if "red" in invalidated_stages:
        action, reason = ("author-red" if routed else "run-red"), "change-impact-invalidated-red"
    elif "green" in invalidated_stages:
        action, reason = ("author-red" if routed else "run-green"), "change-impact-invalidated-green"
    else:
        lifecycle = str(state.get("state") or "planned-only")
        mapping = {
            "probe-materialized": ("run-probe", "current-behavior-unobserved"),
            "probe-observed": ("route-behaviors", "reread-observed-dispositions"),
            "regression-observed": ("validate-slice", "regression-ready-for-coverage"),
            "planned-only": ("run-preflight", "plan-not-preflighted"),
            "preflight-passed": ("author-red", "red-not-materialized"),
            "red-materialized": ("run-red", "red-not-observed"),
            "red-observed": ("implement", "expected-red-required"),
            "implementation-successor": ("run-green", "green-not-observed"),
            "green-observed": ("run-refactor", "refactor-not-observed"),
            "refactor-observed": ("validate-slice", "slice-not-ready"),
            "slice-ready": ("run-terminal", "terminal-pending"),
            "whole-plan-terminal": ("stop", "implementation-complete"),
        }
        action, reason = mapping.get(lifecycle, ("repair-vdd", "invalid-lifecycle-state"))
        if routed and lifecycle == "refactor-observed":
            action, reason = "route-behaviors", "check-required-regression"
    return {
        "schema": "quick-dev.recommendation.v1",
        "plan_id": bundle.get("plan_id"),
        "plan_hash": sha256_value(dict(bundle)),
        "slice_id": slice_id,
        "profile": profile,
        "current_snapshot_sha256": current_snapshot_sha256,
        "recommended_action": action,
        "forbidden_actions": [x for x in ACTIONS if x != action],
        "reason_code": reason,
        "blocked_by": [],
        "reusable_observations": reusable,
        "invalidated_observations": invalidated,
        "invalidated_stages": invalidated_stages,
        "change_kinds": kinds,
    }


def preflight(*, workspace: Path, semantic_plan: Path, slice_id: str, candidate_hash: str, profile: str) -> dict[str, Any]:
    profile_contract(profile)
    _assert_hash(candidate_hash, "candidate_hash")
    bundle = load_json(semantic_plan)
    selected = _slice(bundle, slice_id)
    errors: list[str] = []
    for key in ("acceptance_ids", "failure_intent_ids", "allowed_write_paths", "execution_snapshot_paths", "terminal_predicate", *_PREFLIGHT_FIELDS):
        if key not in selected:
            errors.append(f"slice:{key}:missing")
    if selected.get("complexity_class") not in {"simple", "complex", "architectural"}:
        errors.append("slice:complexity_class:invalid")
    if selected.get("verification_lane") not in {"unit", "integration", "matrix", "runtime"}:
        errors.append("slice:verification_lane:invalid")
    if not isinstance(selected.get("context_lookup_required"), bool):
        errors.append("slice:context_lookup_required:invalid")
    if not isinstance(selected.get("context_lookup_reason"), str) or not selected.get("context_lookup_reason", "").strip():
        errors.append("slice:context_lookup_reason:invalid")
    if not isinstance(selected.get("minimum_red_scope"), str) or not selected.get("minimum_red_scope", "").strip():
        errors.append("slice:minimum_red_scope:invalid")
    upgrades = selected.get("upgrade_conditions")
    if not isinstance(upgrades, list) or not upgrades or any(not isinstance(item, str) or not item for item in upgrades):
        errors.append("slice:upgrade_conditions:invalid")
    for path in list(selected.get("allowed_write_paths", [])) + list(selected.get("execution_snapshot_paths", [])):
        try:
            safe_relative(path)
        except ValueError:
            errors.append(f"unsafe-path:{path}")
    if "behavior_routing" in bundle:
        from behavior_routing import validate_plan
        try:
            validate_plan(bundle)
        except ValueError as exc:
            errors.append(str(exc))
    env = environment_probe()
    if not env.get("available"):
        return {"status": "environment-blocked", "errors": errors, "environment": env}
    return {"status": "preflight-passed" if not errors else "repair-vdd", "errors": errors, "environment": env}


def materialize_descriptor(*, bundle: Mapping[str, Any], slice_id: str, stage: str, run_id: str, candidate_hash: str, argv: Sequence[str], cwd: str, timeout_seconds: int, target_refs: Sequence[str], fixture_refs: Sequence[str], routing_result: Mapping[str, Any] | None = None) -> dict[str, Any]:
    _assert_hash(candidate_hash, "candidate_hash")
    selected = _slice(bundle, slice_id)
    if stage not in {"red", "green", "refactor", "terminal", "probe", "regression"}:
        raise ValueError("stage invalid")
    if not argv or any(not isinstance(x, str) or not x for x in argv):
        raise ValueError("argv invalid")
    if not target_refs or not fixture_refs:
        raise ValueError("target/fixture refs required")
    if cwd != ".":
        safe_relative(cwd)
    snapshots = set(selected.get("execution_snapshot_paths", []))
    for ref in [*target_refs, *fixture_refs]:
        safe_relative(ref)
        if ref not in snapshots:
            raise ValueError(f"target/fixture outside execution snapshot: {ref}")
    amap = {x.get("acceptance_id"): x for x in bundle.get("acceptances", []) if isinstance(x, Mapping)}
    assertions = []
    for aid in selected.get("acceptance_ids", []):
        item = amap.get(aid)
        if not isinstance(item, Mapping):
            raise ValueError("Acceptance missing")
        for assertion_id in item.get("assertion_ids", []):
            assertions.append({"acceptance_id": aid, "assertion_id": assertion_id, "case_source_ref": target_refs[0], "target_ref": target_refs[0], "fixture_ref": fixture_refs[0]})
    descriptor = {"run_id": run_id, "plan_id": bundle["plan_id"], "slice_id": slice_id, "stage": stage, "candidate_hash": candidate_hash, "argv": list(argv), "cwd": cwd, "shell": False, "timeout_seconds": timeout_seconds, "target_refs": list(target_refs), "fixture_refs": list(fixture_refs), "acceptance_assertions": assertions}
    if "behavior_routing" in bundle:
        from behavior_routing import SCHEMA, stage_assertions, validate_plan
        validate_plan(bundle)
        expected = stage_assertions(bundle, slice_id, stage, routing_result)
        assertions = [a for a in assertions if (a["acceptance_id"], a["assertion_id"]) in expected]
        if not assertions:
            raise ValueError("behavior-routing:no-obligations-for-stage")
        descriptor["acceptance_assertions"] = assertions
        descriptor["behavior_route"] = {"schema": SCHEMA, "probe_result_sha256": sha256_value(routing_result) if routing_result else None}
    from case_evidence import contract_for, validate_contract
    descriptor["case_contract"] = contract_for(bundle, assertions)
    validate_contract(descriptor)
    validate_descriptor(descriptor)
    return descriptor


def successor_descriptor(red_descriptor: Mapping[str, Any], *, stage: str, run_id: str, candidate_hash: str, terminal_argv: Sequence[str] | None = None) -> dict[str, Any]:
    validate_descriptor(red_descriptor)
    _assert_hash(candidate_hash, "candidate_hash")
    if stage not in {"green", "refactor", "terminal"}:
        raise ValueError("successor stage invalid")
    result = dict(red_descriptor)
    result.update({"stage": stage, "run_id": run_id, "candidate_hash": candidate_hash})
    if stage == "terminal" and terminal_argv is not None:
        result["argv"] = list(terminal_argv)
    validate_descriptor(result)
    if stage != "terminal" and selector_identity_from_descriptor(result) != selector_identity_from_descriptor(red_descriptor):
        raise ValueError("successor selector drift")
    return result


def validate_expected_red(stage_result: Mapping[str, Any]) -> None:
    if stage_result.get("stage") != "red" or stage_result.get("predicate_result") is not True or stage_result.get("verification_outcome") != "fail" or stage_result.get("failure_family") != "expected-red":
        raise ValueError("Q4 requires clean expected-red")


def validate_red_author_delta(changed_paths: Sequence[str], test_write_paths: Sequence[str], production_paths: Sequence[str]) -> None:
    tests, production = set(test_write_paths), set(production_paths)
    for raw in changed_paths:
        path = safe_relative(raw)
        if path not in tests or path in production:
            raise ValueError(f"RED author write-set violation: {path}")


def validate_write_delta(changed_paths: Sequence[str], allowed_paths: Sequence[str], forbidden_paths: Sequence[str] = ()) -> None:
    allowed, forbidden = set(allowed_paths), set(forbidden_paths)
    if not allowed:
        raise ValueError("production write set empty")
    for raw in changed_paths:
        path = safe_relative(raw)
        if path not in allowed or path in forbidden:
            raise ValueError(f"write-set violation: {path}")


def q4_gate(*, stage_result: Mapping[str, Any], before_snapshot: Mapping[str, Any], after_snapshot: Mapping[str, Any], changed_paths: Sequence[str], slice_item: Mapping[str, Any]) -> dict[str, Any]:
    validate_expected_red(stage_result)
    if before_snapshot.get("schema") != "current-snapshot-resolver.v1" or after_snapshot.get("schema") != "current-snapshot-resolver.v1":
        raise ValueError("Q4 requires current snapshot resolver")
    validate_write_delta(changed_paths, slice_item.get("allowed_write_paths", []))
    if any(path in set(slice_item.get("execution_snapshot_paths", [])) for path in changed_paths):
        raise ValueError("Q4 changed selector/fixture and invalidated RED")
    return {"status": "implementation-successor", "predecessor_red_sha256": sha256_value(dict(stage_result)), "before_snapshot_sha256": before_snapshot.get("sha256"), "after_snapshot_sha256": after_snapshot.get("sha256"), "changed_paths": list(changed_paths)}


def failure_fingerprint(observation: Mapping[str, Any], selector_identity: str) -> str:
    return sha256_value({"selector_identity": selector_identity, "stage": observation.get("stage"), "verification_outcome": observation.get("verification_outcome"), "failure_family": observation.get("failure_family"), "failure_id": observation.get("failure_id"), "exit_code": observation.get("exit_code"), "timed_out": observation.get("timed_out"), "observed_failure_ids": observation.get("observed_failure_ids", [])})


def stop_loss(previous: Sequence[str], current: str) -> dict[str, Any]:
    if previous and previous[-1] == current:
        return {"stop": True, "failure_family": "repeated-deterministic-failure", "action": "stop"}
    return {"stop": False, "failure_family": None, "action": "retry-after-input-change"}


def recovered_run(prior: Mapping[str, Any], *, current_slice_id: str, current_hashes: Mapping[str, str]) -> dict[str, Any]:
    required = ("run_id", "slice_id", "receipt_ref", "receipt_sha256", "observation_ref", "observation_sha256", "runtime_edge_refs")
    if any(key not in prior for key in required) or prior.get("slice_id") != current_slice_id:
        raise ValueError("recovery predecessor incomplete or wrong slice")
    if not isinstance(prior.get("runtime_edge_refs"), list) or not prior["runtime_edge_refs"]:
        raise ValueError("recovery runtime edges missing")
    for key, expected in current_hashes.items():
        if prior.get(key) != expected:
            raise ValueError(f"recovery stale identity: {key}")
    return {"schema": "quick-dev.recovered-run.v1", "evidence_state": "recovered-run", "source_run_id": prior["run_id"], "slice_id": current_slice_id, "receipt_ref": prior["receipt_ref"], "receipt_sha256": prior["receipt_sha256"], "observation_ref": prior["observation_ref"], "observation_sha256": prior["observation_sha256"], "runtime_edge_refs": list(prior["runtime_edge_refs"]), "verification_outcome": prior.get("verification_outcome", "incomplete")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--slice", dest="slice_id", required=True)
    parser.add_argument("--profile", default="standard")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument("--change-kind", action="append", default=[])
    parser.add_argument("--recommendation-only", action="store_true")
    args = parser.parse_args()
    semantic = args.plan / "semantic-plan-bundle.v1.json"
    if not semantic.is_file():
        print(json.dumps(inspect_legacy_plan(args.plan), sort_keys=True))
        return 1
    try:
        bundle = load_json(semantic)
        state = load_json(args.state) if args.state else {"state": "planned-only"}
        result = recommendation(bundle=bundle, slice_id=args.slice_id, state=state, changed_paths=args.changed_path, change_kinds=args.change_kind, profile=args.profile)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"recommended_action": "repair-vdd", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
