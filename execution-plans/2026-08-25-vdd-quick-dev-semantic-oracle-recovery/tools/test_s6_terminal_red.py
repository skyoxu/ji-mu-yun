from pathlib import Path

def test_terminal_boundary_red(tmp_path: Path) -> None:
    import subprocess, sys
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("artifact_owners.py")), "--plan-dir", str(Path(__file__).parent.parent), "--slice", "S6", "--stage", "red"], capture_output=True, text=True)
    assert result.returncode == 1 and "FAILURE_ID:TERMINAL-BOUNDARY-RED" in result.stdout
