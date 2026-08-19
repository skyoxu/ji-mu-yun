import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
PLAN = ROOT / "execution-plans/2026-08-18-toolchain-workflow-repair"


def test_terminal_is_non_authorizing_and_requires_real_slice_receipts():
    result = subprocess.run(
        ["python", str(PLAN / "tools/terminal_full.py"), "--repository-root", str(ROOT), "--plan-dir", str(PLAN)],
        capture_output=True, text=True, check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["predicate"] == "implementation-complete"
    assert payload["authorizes"] == []
    assert payload["failures"]
