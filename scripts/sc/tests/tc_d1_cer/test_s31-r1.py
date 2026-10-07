"""S31-R1 CER check for non-executed matrix evidence."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.sc import skill_replay_runtime as runtime


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"


def _run_matrix(matrix: dict) -> tuple[int, dict]:
    child = (
        "import runpy,sys\n"
        "from pathlib import Path\n"
        "payload=sys.stdin.read(); old=Path.read_text; oldb=Path.read_bytes\n"
        "Path.read_text=lambda p,*a,**k: payload if p.name=='s31-r1-matrix.json' else old(p,*a,**k)\n"
        "Path.read_bytes=lambda p,*a,**k: payload.encode('utf-8') if p.name=='s31-r1-matrix.json' else oldb(p,*a,**k)\n"
        f"sys.argv=['{ENTRY.as_posix()}','replay-matrix','--matrix','s31-r1-matrix.json']\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    result = runtime.capture_process([sys.executable, '-B', '-c', child], ROOT, timeout=90, input_data=(json.dumps(matrix)).encode("utf-8"))
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Matrix entry did not return JSON: {exc}; stderr={result.stderr[:500]}")
    if not isinstance(receipt, dict):
        pytest.fail("Matrix entry did not return an object")
    return result.returncode, receipt


def _assert_behavior(condition: bool, detail: object) -> None:
    if not condition:
        print("FAILURE_ID:FR8-NONEXECUTED-ACCEPTED")
    assert condition, detail


@pytest.mark.cer_assertion('FR8-NONEXECUTED-EVIDENCE')
def test_present_nonexecuted_matrix_evidence_invalidates_named_case() -> None:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "authorizes": [],
        "cases": [
            {
                "case_id": "nonexecuted-case",
                "target": TARGET,
                "capability": CAPABILITY,
                "expected_exit": 0,
                "matrix_evidence": [{"case_id": "nonexecuted-case", "executed": False}],
            }
        ],
    }
    code, receipt = _run_matrix(matrix)
    rows = receipt.get("case_results") or []
    row = rows[0] if len(rows) == 1 and isinstance(rows[0], dict) else {}
    _assert_behavior(
        code != 0
        and receipt.get("aggregate_valid") is False
        and row.get("case_id") == "nonexecuted-case"
        and row.get("status") != "pass"
        and "execut" in str(row.get("rejection_reason", "")).lower(),
        receipt,
    )
