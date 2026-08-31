"""Canonical command-line lifecycle for new Quick Dev plans.

Historical v1 plan loops remain compatibility readers. New Chapter 4/5/6 plans
enter here with explicit descriptors and VDD semantic-plan bytes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from evidence_pipeline import (
    canonical_bytes,
    execute_descriptor,
    judge_receipt,
    runtime_assertion_edges,
    sha256_bytes,
    sha256_value,
    validate_runtime_closure,
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def _safe_write(path: Path, value: Mapping[str, Any]) -> None:
    payload = canonical_bytes(dict(value))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"immutable artifact conflicts: {path.name}")
        return
    path.write_bytes(payload)


def _plan_semantics(bundle: Mapping[str, Any], slice_id: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    if bundle.get("schema_version") != "vdd.semantic-plan-bundle.v1":
        raise ValueError("semantic plan bundle schema is invalid")
    slices = bundle.get("slices")
    acceptances = bundle.get("acceptances")
    failures = bundle.get("failure_intents")
    if not all(isinstance(value, list) for value in (slices, acceptances, failures)):
        raise ValueError("semantic plan bundle is incomplete")
    selected = next((item for item in slices if isinstance(item, dict) and item.get("slice_id") == slice_id), None)
    if selected is None:
        raise ValueError("slice is not declared")
    acceptance_by_id = {
        item["acceptance_id"]: item
        for item in acceptances
        if isinstance(item, dict) and isinstance(item.get("acceptance_id"), str)
    }
    failure_by_id = {
        item["failure_intent_id"]: item
        for item in failures
        if isinstance(item, dict) and isinstance(item.get("failure_intent_id"), str)
    }
    selected_acceptance_ids = selected.get("acceptance_ids")
    selected_failure_ids = selected.get("failure_intent_ids")
    if not isinstance(selected_acceptance_ids, list) or not selected_acceptance_ids:
        raise ValueError("slice acceptance set is invalid")
    if not isinstance(selected_failure_ids, list) or not selected_failure_ids:
        raise ValueError("slice failure-intent set is invalid")
    assertions: list[dict[str, str]] = []
    for acceptance_id in selected_acceptance_ids:
        acceptance = acceptance_by_id.get(acceptance_id)
        if acceptance is None:
            raise ValueError("slice acceptance is missing")
        source_refs = acceptance.get("source_refs")
        assertion_ids = acceptance.get("assertion_ids")
        if not isinstance(source_refs, list) or not source_refs or not isinstance(assertion_ids, list) or not assertion_ids:
            raise ValueError("acceptance assertion/source contract is invalid")
        for assertion_id in assertion_ids:
            if not isinstance(assertion_id, str) or not assertion_id:
                raise ValueError("assertion id is invalid")
            assertions.append(
                {
                    "acceptance_id": acceptance_id,
                    "assertion_id": assertion_id,
                    "case_source_ref": str(source_refs[0]),
                }
            )
    expected_failures: list[str] = []
    for failure_intent_id in selected_failure_ids:
        failure = failure_by_id.get(failure_intent_id)
        if failure is None:
            raise ValueError("slice failure intent is missing")
        failure_id = failure.get("failure_id")
        if not isinstance(failure_id, str) or not failure_id:
            raise ValueError("failure intent identity is invalid")
        expected_failures.append(failure_id)
    return selected, {"failure_ids": sorted(set(expected_failures))}, assertions


def selector_identity(*, selector: str, target_refs: list[str], fixture_refs: list[str], assertion_ids: list[str], cwd: str) -> str:
    if not isinstance(selector, str) or not selector:
        raise ValueError("selector is invalid")
    return sha256_value(
        {
            "selector": selector,
            "target_refs": sorted(target_refs),
            "fixture_refs": sorted(fixture_refs),
            "assertion_ids": sorted(assertion_ids),
            "cwd": cwd,
        }
    )


def execute_stage(
    *,
    workspace: Path,
    plan_bundle_path: Path,
    slice_id: str,
    run_dir: Path,
    stage: str,
    descriptor_path: Path,
    candidate_hash: str,
    profile_identity: str,
    selector: str,
    target_refs: list[str],
    fixture_refs: list[str],
) -> dict[str, Any]:
    """Execute one current stage and publish canonical runtime edges."""
    bundle = _load_json(plan_bundle_path)
    _selected, failure_intent, assertions = _plan_semantics(bundle, slice_id)
    descriptor = _load_json(descriptor_path)
    stage_scope = ["red", "green", "refactor", "terminal"]
    if stage not in stage_scope:
        raise ValueError("stage is invalid")
    expected_exit = "nonzero" if stage == "red" else "zero"
    receipt = execute_descriptor(
        workspace,
        run_dir,
        stage,
        descriptor,
        candidate_hash=candidate_hash,
        profile_identity=profile_identity,
        target_refs=target_refs,
        fixture_refs=fixture_refs,
    )
    observation = judge_receipt(
        run_dir,
        stage,
        descriptor,
        receipt,
        expected_failure_ids=failure_intent["failure_ids"] if stage == "red" else (),
        expected_exit=expected_exit,
    )
    if observation.get("predicate_result") is not True:
        raise RuntimeError(f"{stage} predicate did not pass")

    assertion_ids = [item["assertion_id"] for item in assertions]
    selector_hash = selector_identity(
        selector=selector,
        target_refs=target_refs,
        fixture_refs=fixture_refs,
        assertion_ids=assertion_ids,
        cwd=descriptor["cwd"],
    )
    plan_hash = sha256_bytes(plan_bundle_path.read_bytes())
    edges = runtime_assertion_edges(
        plan_id=str(bundle.get("plan_id") or bundle.get("id") or "semantic-plan"),
        plan_hash=plan_hash,
        slice_id=slice_id,
        run_id=run_dir.name,
        candidate_hash=candidate_hash,
        stage=stage,
        descriptor=descriptor,
        receipt=receipt,
        observation=observation,
        assertions=assertions,
        selector_identity=selector_hash,
    )
    edge_dir = run_dir / "canonical-evidence" / stage / "runtime-edges"
    refs = []
    for index, edge in enumerate(edges, start=1):
        path = edge_dir / f"{index:04d}-{edge['acceptance_id']}-{edge['assertion_id']}.json"
        _safe_write(path, edge)
        refs.append(
            {
                "path": path.relative_to(run_dir).as_posix(),
                "sha256": sha256_value(edge),
                "acceptance_id": edge["acceptance_id"],
                "assertion_id": edge["assertion_id"],
            }
        )
    result = {
        "schema": "quick-dev.stage-result.v1",
        "plan_hash": plan_hash,
        "slice_id": slice_id,
        "run_id": run_dir.name,
        "stage": stage,
        "selector_identity": selector_hash,
        "descriptor_sha256": receipt["descriptor_sha256"],
        "receipt_sha256": sha256_value(receipt),
        "observation_sha256": sha256_value(observation),
        "runtime_edges": refs,
        "verification_outcome": observation["verification_outcome"],
        "predicate_result": True,
        "authorizes": [],
    }
    _safe_write(run_dir / "canonical-evidence" / stage / "stage-result.v1.json", result)
    return result


def terminal_closure(*, bundle: Mapping[str, Any], slice_id: str, runtime_tuples: list[Mapping[str, Any]], current_snapshot_sha256: str) -> tuple[bool, list[str]]:
    final_cover = bundle.get("final_plan_coverage")
    if not isinstance(final_cover, list):
        return False, ["terminal:final-plan-cover-missing"]
    expected = {
        f"{edge.get('slice_id')}|{edge.get('acceptance_id')}|{stage}"
        for edge in final_cover
        if isinstance(edge, Mapping) and edge.get("slice_id") == slice_id
        for stage in edge.get("stage_scope", [])
    }
    if not expected:
        return False, ["terminal:expected-closure-empty"]
    return validate_runtime_closure(runtime_tuples, expected, current_snapshot_sha256=current_snapshot_sha256)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--semantic-plan", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--stage", choices=("red", "green", "refactor", "terminal"), required=True)
    parser.add_argument("--descriptor", type=Path, required=True)
    parser.add_argument("--candidate-hash", required=True)
    parser.add_argument("--profile", default="standard")
    parser.add_argument("--selector", required=True)
    parser.add_argument("--target-ref", action="append", default=[])
    parser.add_argument("--fixture-ref", action="append", default=[])
    args = parser.parse_args()
    try:
        result = execute_stage(
            workspace=args.workspace,
            plan_bundle_path=args.semantic_plan,
            slice_id=args.slice_id,
            run_dir=args.run_dir,
            stage=args.stage,
            descriptor_path=args.descriptor,
            candidate_hash=args.candidate_hash,
            profile_identity=args.profile,
            selector=args.selector,
            target_refs=args.target_ref,
            fixture_refs=args.fixture_ref,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
