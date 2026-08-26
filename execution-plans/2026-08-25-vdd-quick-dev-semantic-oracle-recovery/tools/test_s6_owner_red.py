from pathlib import Path
import subprocess
import sys


def test_terminal_predicate_consumes_run_local_evidence(tmp_path: Path) -> None:
    plan = Path(__file__).parent.parent
    result = subprocess.run([sys.executable, str(plan / "tools" / "terminal_predicate.py"), "--repository-root", str(plan.parents[1]), "--plan-dir", str(plan), "--slice", "S6", "--run-root", str(tmp_path), "--out", str(tmp_path / "result.json")], capture_output=True, text=True)
    assert result.returncode != 0, "FAILURE_ID:TERMINAL-PRODUCER-MISSING"
