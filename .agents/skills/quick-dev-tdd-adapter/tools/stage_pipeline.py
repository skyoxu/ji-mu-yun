"""Q3/Q5/Q6/terminal stage dispatcher for current Quick Dev plans."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path: sys.path.insert(0, str(TOOLS))

from runtime_evidence import (
    STAGES, build_runtime_edges, create_json, execute_process, judge_receipt,
    load_json, selector_identity, sha256_bytes, sha256_value,
)


def semantic_slice(bundle: Mapping[str, Any], slice_id: str, selector: str) -> tuple[list[str], list[dict[str, str]]]:
    if bundle.get("schema_version") != "vdd.semantic-plan-bundle.v1": raise ValueError("semantic plan schema is invalid")
    slices, acceptances, failures = bundle.get("slices"), bundle.get("acceptances"), bundle.get("failure_intents")
    if not all(isinstance(value, list) for value in (slices, acceptances, failures)): raise ValueError("semantic plan is incomplete")
    selected = next((item for item in slices if isinstance(item, dict) and item.get("slice_id") == slice_id), None)
    if selected is None: raise ValueError("slice is not declared")
    acceptance_map = {item.get("acceptance_id"): item for item in acceptances if isinstance(item, dict)}
    failure_map = {item.get("failure_intent_id"): item for item in failures if isinstance(item, dict)}
    assertions: list[dict[str, str]] = []
    for acceptance_id in selected.get("acceptance_ids", []):
        item = acceptance_map.get(acceptance_id); assertion_ids = item.get("assertion_ids") if isinstance(item, dict) else None
        if not isinstance(assertion_ids, list) or not assertion_ids: raise ValueError("slice acceptance assertion contract is invalid")
        for assertion_id in assertion_ids:
            if not isinstance(assertion_id, str) or not assertion_id: raise ValueError("assertion id is invalid")
            assertions.append({"acceptance_id": acceptance_id, "assertion_id": assertion_id, "case_source_ref": selector})
    expected = []
    for intent_id in selected.get("failure_intent_ids", []):
        item = failure_map.get(intent_id); failure_id = item.get("failure_id") if isinstance(item, dict) else None
        if not isinstance(failure_id, str) or not failure_id: raise ValueError("slice failure intent is invalid")
        expected.append(failure_id)
    if not assertions or not expected: raise ValueError("slice semantic bindings are incomplete")
    return sorted(set(expected)), assertions


def execute_stage(*, workspace: Path, semantic_plan: Path, slice_id: str, run_dir: Path, stage: str, descriptor_path: Path, candidate_hash: str, profile_identity: str, selector: str, target_refs: Sequence[str], fixture_refs: Sequence[str]) -> dict[str, Any]:
    if stage not in STAGES: raise ValueError("stage is invalid")
    bundle, descriptor = load_json(semantic_plan), load_json(descriptor_path)
    expected_failures, assertions = semantic_slice(bundle, slice_id, selector)
    receipt = execute_process(workspace, run_dir, stage, descriptor, candidate_hash=candidate_hash, profile_identity=profile_identity, target_refs=target_refs, fixture_refs=fixture_refs)
    observation = judge_receipt(run_dir, stage, descriptor, receipt, expected_failure_ids=expected_failures if stage == "red" else (), expected_exit="nonzero" if stage == "red" else "zero")
    if observation.get("predicate_result") is not True: raise RuntimeError(f"{stage} predicate did not pass")
    assertion_ids = [item["assertion_id"] for item in assertions]
    selector_hash = selector_identity(selector, target_refs, fixture_refs, assertion_ids, descriptor["cwd"])
    plan_hash = sha256_bytes(semantic_plan.read_bytes())
    edges = build_runtime_edges(plan_id=str(bundle.get("plan_id") or "semantic-plan"), plan_hash=plan_hash, slice_id=slice_id, run_id=run_dir.name, candidate_hash=candidate_hash, stage=stage, descriptor=descriptor, receipt=receipt, observation=observation, assertions=assertions, selector_hash=selector_hash)
    refs = []
    edge_dir = run_dir / "canonical-evidence" / stage / "runtime-edges"
    for index, edge in enumerate(edges, start=1):
        path = edge_dir / f"{index:04d}-{edge['acceptance_id']}-{edge['assertion_id']}.json"; create_json(path, edge)
        refs.append({"path": path.relative_to(run_dir).as_posix(), "sha256": sha256_value(edge), "acceptance_id": edge["acceptance_id"], "assertion_id": edge["assertion_id"]})
    result = {"schema": "quick-dev.stage-result.v2", "plan_hash": plan_hash, "slice_id": slice_id, "run_id": run_dir.name, "stage": stage, "selector_identity": selector_hash, "descriptor_sha256": receipt["descriptor_sha256"], "receipt_sha256": sha256_value(receipt), "observation_sha256": sha256_value(observation), "runtime_edges": refs, "verification_outcome": observation["verification_outcome"], "predicate_result": True, "authorizes": []}
    create_json(run_dir / "canonical-evidence" / stage / "stage-result.v2.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--workspace", type=Path, required=True); parser.add_argument("--semantic-plan", type=Path, required=True); parser.add_argument("--slice-id", required=True); parser.add_argument("--run-dir", type=Path, required=True); parser.add_argument("--stage", choices=STAGES, required=True); parser.add_argument("--descriptor", type=Path, required=True); parser.add_argument("--candidate-hash", required=True); parser.add_argument("--profile", default="standard"); parser.add_argument("--selector", required=True); parser.add_argument("--target-ref", action="append", required=True); parser.add_argument("--fixture-ref", action="append", required=True)
    args = parser.parse_args()
    try:
        result = execute_stage(workspace=args.workspace, semantic_plan=args.semantic_plan, slice_id=args.slice_id, run_dir=args.run_dir, stage=args.stage, descriptor_path=args.descriptor, candidate_hash=args.candidate_hash, profile_identity=args.profile, selector=args.selector, target_refs=args.target_ref, fixture_refs=args.fixture_ref)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, sort_keys=True)); return 1
    print(json.dumps(result, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
