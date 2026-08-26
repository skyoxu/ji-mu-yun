from pathlib import Path
import hashlib
import json
import subprocess
import sys


def _bound(path: Path, value: dict) -> None:
    value["evidence_sha256"] = "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_rejects_forged_terminal_lineage(tmp_path: Path) -> None:
    plan = Path(__file__).parent.parent
    for index in range(1, 7):
        root = tmp_path / "lineage" / f"S{index}" / "run-1"
        _bound(root / "observations" / "green.json", {"stage":"green"})
        _bound(root / "receipts" / "judge.json", {"authorizes":[]})
        _bound(root / "terminal-evidence.json", {"status":"pass","producer":"terminal-validator","plan_id":"vdd-quick-dev-semantic-oracle-recovery","slice_id":f"S{index}","run_id":"run-1","candidate_hash":"sha256:forged","contract_hash":"sha256:forged","registry_hash":"sha256:forged","authority_hash":"sha256:forged","observation_ref":"observations/green.json","receipt_ref":"receipts/judge.json","acceptance_ids":["A-TERMINAL"]})
        _bound(root / "terminal-replay-report.json", {"status":"pass"})
    _bound(tmp_path / "lineage" / "S6" / "run-1" / "false-green-fixtures.json", {"status":"pass","producer":"coverage-gate","fixture_ids":[f"FG-{i:02d}" for i in range(1,10)],"blocked_ids":[f"FG-{i:02d}" for i in range(1,10)],"corrected_pair_ids":[f"FG-{i:02d}" for i in range(1,10)],"predecessor_judge_hash":"sha256:forged","corrected_pairs_executed":True})
    root = tmp_path / "lineage" / "S6" / "run-1"
    result = subprocess.run([sys.executable, str(plan / "tools" / "terminal_predicate.py"), "--repository-root", str(plan.parents[1]), "--plan-dir", str(plan), "--slice", "S6", "--run-root", str(root), "--out", str(root / "result.json")], capture_output=True, text=True)
    assert result.returncode != 0, "FAILURE_ID:TERMINAL-LINEAGE-NOT-CLOSED"
