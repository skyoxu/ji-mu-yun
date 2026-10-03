"""S36 adversarial-validator success classification checks."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts/sc/skill_package_replay.py"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"


def _run_case() -> tuple[subprocess.CompletedProcess[str], dict]:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "authorizes": [],
        "cases": [{
            "case_id": "s36-adversarial-validator",
            "target": TARGET,
            "capability": CAPABILITY,
            "expected_exit": 0,
            "adversarial_validator": True,
        }],
    }
    child = (
        "import json,runpy,sys\n"
        "from pathlib import Path\n"
        "data=sys.stdin.read(); old=Path.read_text; oldb=Path.read_bytes\n"
        "Path.read_text=lambda p,*a,**k: data if p.name=='s36-adversarial.json' else old(p,*a,**k)\n"
        "Path.read_bytes=lambda p,*a,**k: data.encode() if p.name=='s36-adversarial.json' else oldb(p,*a,**k)\n"
        f"sys.argv=[{str(ENTRY)!r},'replay-matrix','--matrix','s36-adversarial.json']\n"
        "runpy.run_path(sys.argv[0],run_name='__main__')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", child],
        cwd=ROOT,
        input=json.dumps(matrix),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    return result, payload if isinstance(payload, dict) else {}


@pytest.mark.cer_assertion("A-7C7AF-adversarial-reject")
def test_adversarial_validator_success_is_rejected() -> None:
    result, payload = _run_case()
    row = (payload.get("case_results") or [{}])[0]
    checks = [
        result.returncode != 0,
        payload.get("aggregate_valid") is False,
        row.get("status") == "fail",
        row.get("rejection_reason") == "adversarial validator input is rejected",
    ]
    if not all(checks):
        print("FAILURE_ID:F-7C7AF-UNREJECTED-ADVERSARIAL")
    assert all(checks)
