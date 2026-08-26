"""Publish an authorization receipt bound to a pre-publication candidate commit."""
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
PLAN=ROOT/"execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery"
def digest(path:Path)->str:return "sha256:"+hashlib.sha256(path.read_bytes()).hexdigest()
def ref(path:Path)->dict[str,str]:return {"path":path.relative_to(ROOT).as_posix(),"sha256":digest(path)}
def main()->None:
    commit=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    tree=subprocess.run(["git","rev-parse",f"{commit}^{{tree}}"],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    value={"schema_version":"quick-dev-tdd-adapter.implementation-authorization-successor.v2","plan_id":"vdd-quick-dev-semantic-oracle-recovery","candidate_commit":commit,"candidate_tree_hash":"sha256:"+tree,"implementation_contract":ref(PLAN/"implementation-contract.v1.json"),"command_registry":ref(PLAN/"command-registry.v1.json"),"authority_manifest":ref(PLAN/"knowledge-context.freeze.v1.json"),"review_run":ref(ROOT/"docs/vdd-review-run.v1.json"),"conformance_result":ref(PLAN/"governance/vdd-conformance-result.v1.current-20260826-final-r3.json"),"decision":{"owner":"maintainer","transition":"implementation-authorized","basis":"accepted semantic review; candidate commit/tree is immutable and evidence publication is outside candidate closure"},"authorizes":["implementation-authorized"]}
    out=PLAN/"implementation-authorization-receipt.successor.v2.json"
    out.write_text(json.dumps(value,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8",newline="\n")
if __name__=="__main__":main()
