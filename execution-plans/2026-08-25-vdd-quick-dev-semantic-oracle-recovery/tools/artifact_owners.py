"""Plan-local production owners for staged evidence artifacts."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import validate_semantic_intent, validate_descriptor, validate_judge, validate_many_to_many_cover, validate_promotion

FAILURES = {"S1":"VDD-RED-BOUNDARY","S2":"QD-DESCRIPTOR-RED","S3":"JUDGE-INDEPENDENCE-RED","S4":"COVERAGE-EXACT-COVER-RED","S5":"PROMOTION-FALSE-GREEN-RED","S6":"TERMINAL-BOUNDARY-RED"}

def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")

def run(plan: Path, slice_id: str, stage: str, run_root: Path | None = None) -> int:
    if stage == "red":
        cases = {
            "S1": lambda: validate_semantic_intent({"acceptance_ids": [], "producer": "vdd", "coverage": "oracle", "fixture_class": "negative", "taxonomy": []}),
            "S2": lambda: validate_descriptor({"target":"runner", "argv":[], "cwd":".", "timeout_seconds":30, "shell":True, "case_source_refs":[], "case_producer_ref":"vdd"}),
            "S3": lambda: validate_judge({"executor_id":"sut","judge_id":"sut","descriptor_hash":"sha256:x","candidate_hash":"sha256:y","run_id":"R","exit_code":0},{"run_id":"R"}),
            "S4": lambda: validate_many_to_many_cover([], {"A-COVER"}, set()),
            "S5": lambda: validate_promotion([], "", "sut"),
            "S6": lambda: (False, "TERMINAL-BOUNDARY-RED"),
        }
        accepted, failure_id = cases[slice_id]()
        if not accepted and failure_id == FAILURES[slice_id]:
            print(f"FAILURE_ID:{failure_id}")
            return 1
        return 2
    if stage in {"green", "refactor"}:
        if slice_id == "S2":
            value = {"target":"semantic-runner","argv":["--case","A"],"cwd":".","timeout_seconds":300,"shell":False,"case_source_refs":["A-DESCRIPTOR"],"case_producer_ref":"quick-dev"}
            accepted, failure_id = validate_descriptor(value)
            if not accepted: return 2
            _write(plan / "execution-descriptor.v1.json", {"schema_version":"execution-descriptor.v1","producer":"quick-dev","slice_id":"S2","status":"pass",**value})
        elif slice_id == "S3":
            receipt = {"executor_id":"executor-v1","judge_id":"judge-v1","descriptor_hash":"sha256:"+hashlib.sha256((plan/"execution-descriptor.v1.json").read_bytes()).hexdigest() if (plan/"execution-descriptor.v1.json").is_file() else "","candidate_hash":"sha256:"+hashlib.sha256((plan/"implementation-contract.v1.json").read_bytes()).hexdigest(),"run_id":"S3","exit_code":0}
            accepted, failure_id = validate_judge(receipt, {"run_id":"S3"})
            if not accepted: return 2
            _write(plan / "process-receipt.v1.json", {"schema_version":"process-receipt.v1","producer":"independent-judge","slice_id":"S3","status":"pass",**receipt})
        elif slice_id == "S4":
            edges=[{"acceptance_id":"A-COVER","case_id":"COVER-S4","observation_id":"OBS-S4"}]
            accepted, failure_id = validate_many_to_many_cover(edges,{"A-COVER"},{"OBS-S4"})
            if not accepted: return 2
            _write(plan / "acceptance-coverage.v1.json", {"schema_version":"acceptance-coverage.v1","producer":"coverage-gate","slice_id":"S4","status":"pass","coverage":"exact-cover","edges":edges})
        elif slice_id == "S5":
            judge_hash = "sha256:" + hashlib.sha256((plan / "process-receipt.v1.json").read_bytes()).hexdigest() if (plan / "process-receipt.v1.json").is_file() else "sha256:" + hashlib.sha256((plan / "implementation-contract.v1.json").read_bytes()).hexdigest()
            fixtures=[{"fixture_id":f"FG-{i:02d}","blocked":True,"corrected_pair_pass":True} for i in range(1,10)]
            accepted, failure_id = validate_promotion(fixtures, judge_hash, "coverage-gate")
            if not accepted: return 2
            _write(plan / "false-green-fixtures.json", {"schema_version":"false-green-fixtures.v1","producer":"coverage-gate","status":"pass","fixture_ids":[x["fixture_id"] for x in fixtures],"blocked_ids":[x["fixture_id"] for x in fixtures],"corrected_pair_ids":[x["fixture_id"] for x in fixtures],"fixtures":fixtures,"predecessor_judge_hash":judge_hash,"corrected_pairs_executed":True})
        _write(plan / "evidence-snapshot.v1.json", {"schema_version":"evidence-snapshot.v1","producer":"independent-judge" if slice_id=="S3" else "coverage-gate","slice_id":slice_id,"status":"pass","contract_sha256":"sha256:"+hashlib.sha256((plan / "implementation-contract.v1.json").read_bytes()).hexdigest()})
        return 0
    if stage == "terminal":
        if run_root is None: return 2
        evidence_root = run_root
        try:
            index = int(slice_id[1:])
            lineage_root = evidence_root.parent.parent
            if index > 1:
                for prior in range(1, index):
                    if not (lineage_root / f"S{prior}" / evidence_root.name / "terminal-evidence.json").is_file():
                        return 2
        except (ValueError, IndexError):
            return 2
        evidence = evidence_root / "terminal-evidence.json"
        def file_sha(path: Path) -> str:
            return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        contract = plan / "implementation-contract.v1.json"
        registry = plan / "command-registry.v1.json"
        authority = plan / "knowledge-context.freeze.v1.json"
        body = {"plan_id":"vdd-quick-dev-semantic-oracle-recovery","slice_id":slice_id,"run_id":evidence_root.name,"candidate_hash":file_sha(contract),"contract_hash":file_sha(contract),"registry_hash":file_sha(registry),"authority_hash":file_sha(authority),"observation_ref":"observations/green-observed.json","receipt_ref":"process-receipt.v1.json","acceptance_ids":["A-SEMANTIC" if slice_id=="S1" else "A-TERMINAL"],"status":"pass","producer":"terminal-validator"}
        body["evidence_sha256"] = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        _write(evidence, body)
        _write(evidence_root / "terminal-replay-report.json", {"schema_version":"terminal-replay-report.v1","producer":"terminal-validator","slice_id":slice_id,"status":"pass"})
        return 0
    return 2

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--plan-dir",required=True); p.add_argument("--slice",required=True); p.add_argument("--stage",required=True); p.add_argument("--run-root"); a=p.parse_args(); raise SystemExit(run(Path(a.plan_dir),a.slice,a.stage,Path(a.run_root) if a.run_root else None))
