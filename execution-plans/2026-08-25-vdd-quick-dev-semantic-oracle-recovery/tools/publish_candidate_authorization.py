"""Publish an authorization receipt bound to a pre-publication candidate commit."""
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
    commit=input_value.get("candidate",{}).get("head_commit")
    if not isinstance(commit,str) or not commit or subprocess.run(["git","merge-base","--is-ancestor",commit,"HEAD"],cwd=ROOT,capture_output=True,text=True,check=False).returncode != 0: raise SystemExit("review candidate is not a current branch ancestor")
    tree=subprocess.run(["git","rev-parse",f"{commit}^{{tree}}"],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    refs={"review_input":ref(review_input),"review_run":ref(args_review),"review_candidate_binding":ref(binding_path),"conformance_result":ref(conformance_path),"implementation_contract":ref(PLAN/"implementation-contract.v1.json"),"command_registry":ref(PLAN/"command-registry.v1.json"),"source_freeze":input_value.get("source_freeze"),"requirements_mapping":input_value.get("requirements_mapping")}
    if binding.get("schema_version")!="vdd-review-candidate-binding.v1" or binding.get("status")!="accepted" or binding.get("decision")!="accepted" or binding.get("candidate_commit")!=commit or input_value.get("candidate",{}).get("head_commit")!=commit or any(binding.get(key)!=refs[key] for key in refs): raise SystemExit("candidate review binding is stale")
    value={"schema_version":"quick-dev-tdd-adapter.implementation-authorization-successor.v2","plan_id":"vdd-quick-dev-semantic-oracle-recovery","candidate_commit":commit,"candidate_tree_hash":"sha256:"+tree,**refs,"authority_manifest":ref(PLAN/"knowledge-context.freeze.v1.json"),"decision":{"owner":"maintainer","transition":"implementation-authorized","basis":"accepted candidate-bound semantic review"},"authorizes":["implementation-authorized"]}
    out=PLAN/"implementation-authorization-receipt.successor.v2.json"
    out.write_text(json.dumps(value,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8",newline="\n")
    state={"schema_version":"vdd.lifecycle.v2","plan_id":"vdd-quick-dev-semantic-oracle-recovery","state":"implementation-authorized","owner":"maintainer","profile":"self-hosted","canonical_selection_hash":json.loads((PLAN/"plan-state.v1.json").read_text(encoding="utf-8"))["canonical_selection_hash"],"baseline_commit":commit,"authorization_receipt":ref(out),"authorizes":["implementation-authorized"]}
    (PLAN/"plan-state.v1.json").write_text(json.dumps(state,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8",newline="\n")
if __name__=="__main__":main()
