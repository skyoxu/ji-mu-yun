from pathlib import Path
import hashlib
import json
import subprocess
import sys


def _write_bound(path: Path, value: dict) -> None:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    value["evidence_sha256"] = "sha256:" + hashlib.sha256(body).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_terminal_predicate_fails_closed_for_empty_run(tmp_path: Path) -> None:
    plan = Path(__file__).parent.parent
    result = subprocess.run([sys.executable, str(plan / "tools" / "terminal_predicate.py"), "--repository-root", str(plan.parents[1]), "--plan-dir", str(plan), "--slice", "S6", "--run-root", str(tmp_path), "--out", str(tmp_path / "result.json")], capture_output=True, text=True)
    assert result.returncode != 0


def test_terminal_owner_requires_a_closed_cross_slice_lineage(tmp_path: Path) -> None:
    plan = Path(__file__).parent.parent
    lineage = tmp_path / "lineage"
    run_name = "run-1"
    for index in range(1, 7):
        root = lineage / f"S{index}" / run_name
        _write_bound(root / "observations" / "green.json", {"stage":"green", "run_id":run_name})
        _write_bound(root / "receipts" / "judge.json", {"authorizes":[]})
        _write_bound(root / "terminal-evidence.json", {"status":"pass", "producer":"terminal-validator", "plan_id":"vdd-quick-dev-semantic-oracle-recovery", "slice_id":f"S{index}", "run_id":run_name, "candidate_hash":"sha256:candidate", "contract_hash":"sha256:contract", "registry_hash":"sha256:registry", "authority_hash":"sha256:authority", "observation_ref":"observations/green.json", "receipt_ref":"receipts/judge.json", "acceptance_ids":["A-TERMINAL"]})
        _write_bound(root / "terminal-replay-report.json", {"status":"pass", "slice_id":f"S{index}", "run_id":run_name})
    fixture = {"status":"pass", "producer":"coverage-gate", "fixture_ids":[f"FG-{i:02d}" for i in range(1, 10)], "blocked_ids":[f"FG-{i:02d}" for i in range(1, 10)], "corrected_pair_ids":[f"FG-{i:02d}" for i in range(1, 10)], "predecessor_judge_hash":"sha256:judge", "corrected_pairs_executed":True}
    _write_bound(lineage / "S6" / run_name / "false-green-fixtures.json", fixture)
    root = lineage / "S6" / run_name
    result = subprocess.run([sys.executable, str(plan / "tools" / "terminal_predicate.py"), "--repository-root", str(plan.parents[1]), "--plan-dir", str(plan), "--slice", "S6", "--run-root", str(root), "--out", str(root / "implementation-complete-result.json")], capture_output=True, text=True)
    assert result.returncode != 0, "FAILURE_ID:TERMINAL-PRODUCER-MISSING"
