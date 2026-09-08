"""Q3/Q5/Q6/terminal dispatcher for current Quick Dev plans."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

TOOLS=Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))
from independent_judge_v2 import judge_receipt
from process_executor_v2 import execute_process
from regression_gate import run_regression_gate
from runtime_evidence import build_runtime_edges,create_json,load_json,selector_identity_from_descriptor,sha256_bytes,sha256_value,validate_descriptor


def semantic_assertions(bundle: Mapping[str, Any], slice_id: str, *, allowed=None) -> tuple[set[tuple[str,str]],list[str]]:
    slices,acceptances,failures=bundle.get("slices"),bundle.get("acceptances"),bundle.get("failure_intents")
    if not all(isinstance(x,list) for x in (slices,acceptances,failures)):
        raise ValueError("semantic plan incomplete")
    selected=next((x for x in slices if isinstance(x,Mapping) and x.get("slice_id")==slice_id),None)
    if selected is None:
        raise ValueError("slice not declared")
    amap={x.get("acceptance_id"):x for x in acceptances if isinstance(x,Mapping)}
    fmap={x.get("failure_intent_id"):x for x in failures if isinstance(x,Mapping)}
    assertions:set[tuple[str,str]]=set()
    for aid in selected.get("acceptance_ids",[]):
        item=amap.get(aid)
        if not isinstance(item,Mapping):
            raise ValueError("Acceptance missing")
        for assertion_id in item.get("assertion_ids",[]):
            if allowed is None or (aid, assertion_id) in allowed:
                assertions.add((aid,assertion_id))
    expected=[]
    for fid in selected.get("failure_intent_ids",[]):
        item=fmap.get(fid)
        if not isinstance(item,Mapping) or not isinstance(item.get("failure_id"),str):
            raise ValueError("failure intent missing")
        family=item.get("failure_family")
        if not isinstance(family,str) or not family:
            raise ValueError("failure intent family missing")
        if family=="expected-red" and (allowed is None or set(item.get("acceptance_ids", [])) & {a for a, _ in allowed}):
            expected.append(item["failure_id"])
    if not assertions or (not expected and allowed is None):
        raise ValueError("slice semantic bindings incomplete")
    return assertions,sorted(set(expected))


def validate_nonterminal_successor(run_dir: Path, descriptor: Mapping[str, Any]) -> dict[str, Any]:
    """Re-read the explicit frozen RED predecessor before GREEN/REFACTOR."""
    validate_descriptor(descriptor)
    if descriptor.get("stage") not in {"green","refactor"}:
        raise ValueError("successor predecessor validation only applies to GREEN/REFACTOR")
    red_descriptor_path=run_dir.resolve()/"descriptors"/"red.json"
    red_result_path=run_dir.resolve()/"canonical-evidence"/"red"/"stage-result.v2.json"
    if not red_descriptor_path.is_file() or not red_result_path.is_file():
        raise ValueError("GREEN/REFACTOR requires explicit frozen RED predecessor")
    red_descriptor=load_json(red_descriptor_path)
    red_result=load_json(red_result_path)
    validate_descriptor(red_descriptor)
    if red_descriptor.get("stage")!="red":
        raise ValueError("RED predecessor descriptor stage invalid")
    if red_descriptor.get("run_id")!=run_dir.name or descriptor.get("run_id")!=run_dir.name:
        raise ValueError("RED successor run binding mismatch")
    if red_descriptor.get("plan_id")!=descriptor.get("plan_id") or red_descriptor.get("slice_id")!=descriptor.get("slice_id"):
        raise ValueError("RED successor semantic identity mismatch")
    if red_result.get("schema")!="quick-dev.stage-result.v2" or red_result.get("stage")!="red":
        raise ValueError("RED predecessor result invalid")
    if red_result.get("run_id")!=run_dir.name or red_result.get("plan_id")!=descriptor.get("plan_id") or red_result.get("slice_id")!=descriptor.get("slice_id"):
        raise ValueError("RED predecessor result lineage mismatch")
    if red_result.get("predicate_result") is not True or red_result.get("verification_outcome")!="fail" or red_result.get("failure_family")!="expected-red":
        raise ValueError("GREEN/REFACTOR predecessor is not clean expected-red")
    from case_evidence import reread_stage_cases
    reread_stage_cases(run_dir.resolve(), "red")
    red_descriptor_sha=sha256_value(red_descriptor)
    if red_result.get("descriptor_sha256")!=red_descriptor_sha:
        raise ValueError("frozen RED descriptor hash drifted after observation")
    red_selector=selector_identity_from_descriptor(red_descriptor)
    if red_result.get("selector_identity")!=red_selector:
        raise ValueError("RED stage result selector binding invalid")
    if selector_identity_from_descriptor(descriptor)!=red_selector:
        raise ValueError("GREEN/REFACTOR selector drift from frozen RED")
    return {
        "red_descriptor_ref":"descriptors/red.json",
        "red_descriptor_sha256":red_descriptor_sha,
        "red_stage_result_ref":"canonical-evidence/red/stage-result.v2.json",
        "red_stage_result_sha256":sha256_value(red_result),
        "selector_identity":red_selector,
    }


def execute_stage(*,workspace:Path,semantic_plan:Path,run_dir:Path,descriptor_path:Path,profile_identity:str,failure_history=None)->dict[str,Any]:
    bundle=load_json(semantic_plan)
    descriptor=load_json(descriptor_path)
    validate_descriptor(descriptor)
    if descriptor["run_id"]!=run_dir.name:
        raise ValueError("descriptor run binding mismatch")
    from stage_reentry import existing_result, input_binding, check_history
    prior = existing_result(workspace, bundle, run_dir, descriptor, profile_identity)
    if prior is not None:
        return prior
    decision = check_history(run_dir, descriptor, failure_history)
    if decision['status'] == 'blocked':
        return decision
    from behavior_routing import verify_stage, production_hashes, derive_dispositions
    route = verify_stage(workspace, bundle, run_dir, descriptor)
    routed = "behavior_routing" in bundle
    production_before = production_hashes(workspace, bundle, descriptor["slice_id"]) if routed else None
    predecessor_binding=None
    if descriptor["stage"] in {"green","refactor"}:
        predecessor_binding=validate_nonterminal_successor(run_dir,descriptor)
    allowed = {(a["acceptance_id"], a["assertion_id"]) for a in descriptor["acceptance_assertions"]} if routed else None
    expected_assertions,expected_failures=semantic_assertions(bundle,descriptor["slice_id"], allowed=allowed)
    actual_assertions={(a["acceptance_id"],a["assertion_id"]) for a in descriptor["acceptance_assertions"]}
    if actual_assertions!=expected_assertions:
        raise ValueError("descriptor assertion universe differs from semantic plan")
    if descriptor.get("case_contract") is not None:
        from case_evidence import contract_for, validate_contract
        validate_contract(descriptor)
        expected_bindings = contract_for(bundle, descriptor["acceptance_assertions"])["bindings"]
        failures_by_assertion = {(row["acceptance_id"], row["assertion_id"]): row["expected_failure_ids"] for row in expected_bindings}
        for row in descriptor["case_contract"]["bindings"]:
            if sorted(row["expected_failure_ids"]) != failures_by_assertion[(row["acceptance_id"], row["assertion_id"])]:
                raise ValueError("case-failure-binding-differs-from-semantic-plan")
    evidence_dir = run_dir / 'canonical-evidence' / descriptor['stage']
    binding = input_binding(workspace, bundle, descriptor, profile_identity)
    # Atomic reservation also prevents concurrent or interrupted duplicate launches.
    evidence_dir.mkdir(parents=True, exist_ok=False)
    create_json(evidence_dir / 'execution-input.v1.json', binding)
    receipt=execute_process(workspace,run_dir,descriptor["stage"],descriptor,profile_identity=profile_identity)
    if routed and production_before != production_hashes(workspace, bundle, descriptor["slice_id"]):
        raise ValueError("behavior-routing:production-changed-during-test")
    dispositions = derive_dispositions(bundle, descriptor, receipt) if descriptor["stage"] == "probe" else None
    observation=judge_receipt(run_dir,descriptor["stage"],descriptor,receipt,expected_failure_ids=expected_failures if descriptor["stage"]=="red" else (), probe_dispositions=dispositions, behavior_route=route)

    regression_binding=None
    if descriptor["stage"] in {"refactor", "regression"} and observation.get("predicate_result") is True:
        gate_path=run_dir/"canonical-evidence"/descriptor["stage"]/"regression-gate.v1.json"
        gate=run_regression_gate(
            workspace=workspace,
            bundle=bundle,
            slice_id=descriptor["slice_id"],
            profile=profile_identity,
            primary_argv=descriptor["argv"],
            primary_receipt=receipt,
            timeout_seconds=descriptor["timeout_seconds"],
            out=gate_path,
        )
        regression_binding={"ref":gate_path.relative_to(run_dir).as_posix(),"sha256":sha256_value(gate)}

    selector_hash=selector_identity_from_descriptor(descriptor)
    plan_hash=sha256_bytes(semantic_plan.read_bytes())
    edges=build_runtime_edges(plan_id=bundle["plan_id"],plan_hash=plan_hash,slice_id=descriptor["slice_id"],run_id=descriptor["run_id"],candidate_hash=descriptor["candidate_hash"],stage=descriptor["stage"],descriptor=descriptor,receipt=receipt,observation=observation,selector_hash=selector_hash)
    refs=[]
    edge_dir=run_dir/"canonical-evidence"/descriptor["stage"]/"runtime-edges"
    for index,edge in enumerate(edges,start=1):
        path=edge_dir/f"{index:04d}-{edge['acceptance_id']}-{edge['assertion_id']}.json"
        create_json(path,edge)
        refs.append({"path":path.relative_to(run_dir).as_posix(),"sha256":sha256_value(edge),"acceptance_id":edge["acceptance_id"],"assertion_id":edge["assertion_id"]})
    result={
        "schema":"quick-dev.stage-result.v2","plan_hash":plan_hash,"plan_id":bundle["plan_id"],"slice_id":descriptor["slice_id"],"run_id":descriptor["run_id"],"stage":descriptor["stage"],"candidate_hash":descriptor["candidate_hash"],"selector_identity":selector_hash,
        "case_evidence_error":observation.get("case_evidence_error"),
        "descriptor_sha256":sha256_value(descriptor),"receipt_sha256":sha256_value(receipt),"observation_sha256":sha256_value(observation),"runtime_edges":refs,
        "verification_outcome":observation["verification_outcome"],"failure_family":observation["failure_family"],"failure_id":observation["failure_id"],"failure_fingerprint":observation.get("failure_fingerprint"),"predicate_result":observation["predicate_result"],"authorizes":[],
    }
    if routed:
        result["behavior_plan_sha256"] = sha256_value(bundle)
        result["production_hashes"] = production_before
        result["behavior_route"] = descriptor["behavior_route"]
    if routed and descriptor["stage"] == "regression":
        result["required_next_action"] = "validate-slice" if observation["predicate_result"] else "repair-vdd"
    if dispositions is not None:
        result["behavior_dispositions"] = dispositions
        result["required_next_action"] = (("run-red" if any(x["disposition"] == "missing" for x in dispositions) else "run-regression") if observation["predicate_result"] else "repair-vdd")
    if predecessor_binding is not None:
        result["red_predecessor_binding"]=predecessor_binding
    if regression_binding is not None:
        result["regression_gate"]=regression_binding
    create_json(run_dir/"canonical-evidence"/descriptor["stage"]/"stage-result.v2.json",result)
    create_json(evidence_dir / 'execution-complete.v1.json', {'result_sha256': sha256_value(result), 'input_sha256': sha256_value(binding)})
    return result


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--workspace",type=Path,required=True)
    parser.add_argument("--semantic-plan",type=Path,required=True)
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--descriptor",type=Path,required=True)
    parser.add_argument("--profile",default="standard")
    args=parser.parse_args()
    try:
        result=execute_stage(workspace=args.workspace,semantic_plan=args.semantic_plan,run_dir=args.run_dir,descriptor_path=args.descriptor,profile_identity=args.profile)
    except (OSError,UnicodeError,json.JSONDecodeError,ValueError) as exc:
        print(json.dumps({"status":"blocked","reason":str(exc)},sort_keys=True))
        return 1
    print(json.dumps(result,sort_keys=True))
    return 0 if result.get("predicate_result") is True else 1


if __name__=="__main__":
    raise SystemExit(main())
