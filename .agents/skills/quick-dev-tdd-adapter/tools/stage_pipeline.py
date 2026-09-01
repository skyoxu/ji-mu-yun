"""Q3/Q5/Q6/terminal dispatcher for current Quick Dev plans."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path: sys.path.insert(0, str(TOOLS))
from runtime_evidence import build_runtime_edges, create_json, execute_process, judge_receipt, load_json, selector_identity_from_descriptor, sha256_bytes, sha256_value, validate_descriptor


def semantic_assertions(bundle: Mapping[str, Any], slice_id: str) -> tuple[set[tuple[str, str]], list[str]]:
    slices = bundle.get("slices"); acceptances = bundle.get("acceptances"); failures = bundle.get("failure_intents")
    if not all(isinstance(x, list) for x in (slices, acceptances, failures)): raise ValueError("semantic plan incomplete")
    selected = next((x for x in slices if isinstance(x, Mapping) and x.get("slice_id") == slice_id), None)
    if selected is None: raise ValueError("slice not declared")
    acceptance_map = {x.get("acceptance_id"): x for x in acceptances if isinstance(x, Mapping)}
    failure_map = {x.get("failure_intent_id"): x for x in failures if isinstance(x, Mapping)}
    assertions: set[tuple[str, str]] = set()
    for aid in selected.get("acceptance_ids", []):
        item = acceptance_map.get(aid)
        if not isinstance(item, Mapping): raise ValueError("Acceptance missing")
        for assertion_id in item.get("assertion_ids", []): assertions.add((aid, assertion_id))
    expected = []
    for fid in selected.get("failure_intent_ids", []):
        item = failure_map.get(fid)
        if not isinstance(item, Mapping) or not isinstance(item.get("failure_id"), str): raise ValueError("failure intent missing")
        expected.append(item["failure_id"])
    if not assertions or not expected: raise ValueError("slice semantic bindings incomplete")
    return assertions, sorted(set(expected))


def execute_stage(*, workspace: Path, semantic_plan: Path, run_dir: Path, descriptor_path: Path, profile_identity: str) -> dict[str, Any]:
    bundle = load_json(semantic_plan); descriptor = load_json(descriptor_path); validate_descriptor(descriptor)
    if descriptor["run_id"] != run_dir.name: raise ValueError("descriptor run binding mismatch")
    expected_assertions, expected_failures = semantic_assertions(bundle, descriptor["slice_id"])
    actual_assertions = {(a["acceptance_id"], a["assertion_id"]) for a in descriptor["acceptance_assertions"]}
    if actual_assertions != expected_assertions: raise ValueError("descriptor assertion universe differs from semantic plan")
    receipt = execute_process(workspace, run_dir, descriptor["stage"], descriptor, profile_identity=profile_identity)
    observation = judge_receipt(run_dir, descriptor["stage"], descriptor, receipt, expected_failure_ids=expected_failures if descriptor["stage"] == "red" else ())
    selector_hash = selector_identity_from_descriptor(descriptor)
    plan_hash = sha256_bytes(semantic_plan.read_bytes())
    edges = build_runtime_edges(plan_id=bundle["plan_id"], plan_hash=plan_hash, slice_id=descriptor["slice_id"], run_id=descriptor["run_id"], candidate_hash=descriptor["candidate_hash"], stage=descriptor["stage"], descriptor=descriptor, receipt=receipt, observation=observation, selector_hash=selector_hash)
    refs = []
    edge_dir = run_dir / "canonical-evidence" / descriptor["stage"] / "runtime-edges"
    for index, edge in enumerate(edges, start=1):
        path = edge_dir / f"{index:04d}-{edge['acceptance_id']}-{edge['assertion_id']}.json"; create_json(path, edge)
        refs.append({"path": path.relative_to(run_dir).as_posix(), "sha256": sha256_value(edge), "acceptance_id": edge["acceptance_id"], "assertion_id": edge["assertion_id"]})
    result = {
        "schema": "quick-dev.stage-result.v2", "plan_hash": plan_hash, "plan_id": bundle["plan_id"],
        "slice_id": descriptor["slice_id"], "run_id": descriptor["run_id"], "stage": descriptor["stage"],
        "candidate_hash": descriptor["candidate_hash"], "selector_identity": selector_hash,
        "descriptor_sha256": sha256_value(descriptor), "receipt_sha256": sha256_value(receipt),
        "observation_sha256": sha256_value(observation), "runtime_edges": refs,
        "verification_outcome": observation["verification_outcome"], "failure_family": observation["failure_family"],
        "failure_id": observation["failure_id"], "predicate_result": observation["predicate_result"], "authorizes": [],
    }
    create_json(run_dir / "canonical-evidence" / descriptor["stage"] / "stage-result.v2.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--workspace", type=Path, required=True); parser.add_argument("--semantic-plan", type=Path, required=True); parser.add_argument("--run-dir", type=Path, required=True); parser.add_argument("--descriptor", type=Path, required=True); parser.add_argument("--profile", default="standard")
    args = parser.parse_args()
    try: result = execute_stage(workspace=args.workspace, semantic_plan=args.semantic_plan, run_dir=args.run_dir, descriptor_path=args.descriptor, profile_identity=args.profile)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, sort_keys=True)); return 1
    print(json.dumps(result, sort_keys=True)); return 0 if result.get("predicate_result") is True else 1


if __name__ == "__main__": raise SystemExit(main())
