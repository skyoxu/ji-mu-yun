import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
PLAN = ROOT / "execution-plans/2026-08-18-toolchain-workflow-repair"


def test_entry_refuses_to_claim_ready_before_semantic_skill_input_is_ready():
    result = subprocess.run(
        ["python", str(PLAN / "tools/validate_quick_dev_entry.py"), "--repository-root", str(ROOT), "--plan-dir", str(PLAN), "--out", str(PLAN / "repair/round-1/quick-dev-entry-validation.v1.json")],
        capture_output=True, text=True, check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert "skill-input-not-ready" in payload["failures"]
    assert payload["authorizes"] == []
