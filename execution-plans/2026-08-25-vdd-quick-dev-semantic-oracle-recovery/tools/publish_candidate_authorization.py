"""Publish a plan-scoped authorization for high-velocity TDD."""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
PLAN=ROOT/"execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery"
def digest(path:Path)->str:return "sha256:"+hashlib.sha256(path.read_bytes()).hexdigest()
def ref(path:Path)->dict[str,str]:return {"path":path.relative_to(ROOT).as_posix(),"sha256":digest(path)}
def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--review-input",type=Path,required=True); parser.add_argument("--review-run",type=Path,required=True); parser.add_argument("--review-binding",type=Path,required=True); parser.add_argument("--conformance",type=Path,required=True)
    args=parser.parse_args()
    review_input,args_review,binding_path,conformance_path=(value.resolve() for value in (args.review_input,args.review_run,args.review_binding,args.conformance))
    review=json.loads(args_review.read_text(encoding="utf-8")); binding=json.loads(binding_path.read_text(encoding="utf-8")); conformance=json.loads(conformance_path.read_text(encoding="utf-8")); input_value=json.loads(review_input.read_text(encoding="utf-8"))
    if review.get("schema_version") != "vdd-review-run.v1" or review.get("status") != "accepted" or review.get("decision") != "accepted":
        raise SystemExit("accepted external review is required")
    if conformance.get("status") != "conformant" or conformance.get("errors") != [] or conformance.get("authorizes") != []:
        raise SystemExit("conformant conformance result is required")
    refs={"review_input":ref(review_input),"review_run":ref(args_review),"review_candidate_binding":ref(binding_path),"conformance_result":ref(conformance_path),"implementation_contract":ref(PLAN/"implementation-contract.v1.json"),"command_registry":ref(PLAN/"command-registry.v1.json"),"source_freeze":input_value.get("source_freeze"),"requirements_mapping":input_value.get("requirements_mapping")}
    # The binding cannot contain a reference to itself. Validate every
    # externally supplied artifact reference, while treating the binding
    # document's own path/hash as the publisher's custody fact.
    external_refs = {key: value for key, value in refs.items() if key in {"review_input", "review_run", "conformance_result", "source_freeze", "requirements_mapping"}}
    if binding.get("schema_version")!="vdd-review-candidate-binding.v1" or binding.get("status")!="accepted" or binding.get("decision")!="accepted" or any(binding.get(key)!=external_refs[key] for key in external_refs): raise SystemExit("semantic review binding is stale")
    value={"schema_version":"quick-dev-tdd-adapter.implementation-authorization.v3","plan_id":"vdd-quick-dev-semantic-oracle-recovery","scope":"whole_plan","mode":"high_velocity_tdd",**refs,"authority_manifest":ref(PLAN/"knowledge-context.freeze.v1.json"),"decision":{"owner":"maintainer","transition":"implementation-authorized","basis":"accepted semantic review for plan-scoped high-velocity TDD"},"binds":["plan_id","requirements_mapping","source_freeze","implementation_contract","command_registry","authority_manifest"],"does_not_bind":["candidate_commit","implementation_source_hashes","run_evidence"],"authorizes":["implementation-authorized"]}
    out=PLAN/"implementation-authorization-receipt.v3.json"
    out.write_text(json.dumps(value,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8",newline="\n")
    state={"schema_version":"vdd.lifecycle.v2","plan_id":"vdd-quick-dev-semantic-oracle-recovery","state":"implementation-authorized","owner":"maintainer","profile":"self-hosted","authorization_scope":"whole_plan","mode":"high_velocity_tdd","canonical_selection_hash":json.loads((PLAN/"plan-state.v1.json").read_text(encoding="utf-8"))["canonical_selection_hash"],"authorization_receipt":ref(out),"authorizes":["implementation-authorized"]}
    (PLAN/"plan-state.v1.json").write_text(json.dumps(state,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8",newline="\n")
if __name__=="__main__":main()
