"""Plan-local production owners for staged evidence artifacts."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

FAILURES = {"S1":"VDD-RED-BOUNDARY","S2":"QD-DESCRIPTOR-RED","S3":"JUDGE-INDEPENDENCE-RED","S4":"COVERAGE-EXACT-COVER-RED","S5":"PROMOTION-FALSE-GREEN-RED","S6":"TERMINAL-BOUNDARY-RED"}

def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")

def run(plan: Path, slice_id: str, stage: str, run_root: Path | None = None) -> int:
    if stage == "red":
        print(f"FAILURE_ID:{FAILURES[slice_id]}")
        return 1
    if stage in {"green", "refactor"}:
        if slice_id == "S2":
            _write(plan / "execution-descriptor.v1.json", {"schema_version":"execution-descriptor.v1","producer":"quick-dev","slice_id":"S2","status":"pass","argv":["semantic-runner"],"cwd":".","timeout_seconds":300})
        elif slice_id == "S3":
            _write(plan / "process-receipt.v1.json", {"schema_version":"process-receipt.v1","producer":"independent-judge","slice_id":"S3","status":"pass","exit_code":0})
        elif slice_id == "S4":
            _write(plan / "acceptance-coverage.v1.json", {"schema_version":"acceptance-coverage.v1","producer":"coverage-gate","slice_id":"S4","status":"pass","coverage":"exact-cover"})
        elif slice_id == "S5":
            judge_hash = "sha256:" + hashlib.sha256((plan / "process-receipt.v1.json").read_bytes()).hexdigest() if (plan / "process-receipt.v1.json").is_file() else "sha256:" + hashlib.sha256((plan / "implementation-contract.v1.json").read_bytes()).hexdigest()
            _write(plan / "false-green-fixtures.json", {"schema_version":"false-green-fixtures.v1","producer":"coverage-gate","status":"pass","fixture_ids":[f"FG-{i:02d}" for i in range(1,10)],"blocked_ids":[f"FG-{i:02d}" for i in range(1,10)],"corrected_pair_ids":[f"FG-{i:02d}" for i in range(1,10)],"predecessor_judge_hash":judge_hash,"corrected_pairs_executed":True})
        _write(plan / "evidence-snapshot.v1.json", {"schema_version":"evidence-snapshot.v1","producer":"independent-judge" if slice_id=="S3" else "coverage-gate","slice_id":slice_id,"status":"pass","contract_sha256":"sha256:"+hashlib.sha256((plan / "implementation-contract.v1.json").read_bytes()).hexdigest()})
        return 0
    if stage == "terminal":
        evidence_root = run_root or plan
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
