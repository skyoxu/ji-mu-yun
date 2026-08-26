from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
PLAN=ROOT/"execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery"
def sha(p:Path)->str:return "sha256:"+hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p:Path):return {"path":p.relative_to(ROOT).as_posix(),"sha256":sha(p)}
def main():
    review=ROOT/"docs/vdd-review-run.v1.json"; conf=PLAN/"governance/vdd-conformance-result.v1.current-20260826-final-r3.json"
    contract=PLAN/"implementation-contract.v1.json"; authority=PLAN/"knowledge-context.freeze.v1.json"
    value=json.loads(review.read_text(encoding="utf-8")); c=json.loads(conf.read_text(encoding="utf-8"))
    if value.get("schema_version")!="vdd-review-run.v1" or value.get("status")!="accepted" or value.get("decision")!="accepted": raise SystemExit("review not accepted")
    if c.get("status") != "conformant" or c.get("errors")!=[] or c.get("authorizes") != []: raise SystemExit("conformance is not conformant")
    if value.get("source_manifest_hash")!=c.get("semantic_handoff",{}).get("frozen_authority",{}).get("source_manifest_hash"): raise SystemExit("review/source binding mismatch")
    out={"schema_version":"quick-dev-tdd-adapter.implementation-authorization.v2","plan_id":"vdd-quick-dev-semantic-oracle-recovery","candidate_commit":subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip(),"implementation_contract":ref(contract),"authority_manifest":ref(authority),"review_run":ref(review),"conformance_result":ref(conf),"decision":{"owner":"maintainer","transition":"implementation-authorized","basis":"accepted external semantic review bound to current conformance and candidate bytes"},"authorizes":["implementation-authorized"],"does_not_authorize":["acceptance","release","implementation-complete"]}
    (PLAN/"implementation-authorization-receipt.v2.json").write_text(json.dumps(out,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8",newline="\n")
if __name__=="__main__":main()
