import sys, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import validate_judge

def test_judge_independence_red() -> None:
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("artifact_owners.py")), "--plan-dir", str(Path(__file__).parent.parent), "--slice", "S3", "--stage", "red"], capture_output=True, text=True)
    assert result.returncode == 1 and "FAILURE_ID:JUDGE-INDEPENDENCE-RED" in result.stdout
