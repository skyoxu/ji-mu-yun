import sys, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import validate_promotion

def test_false_green_promotion_red() -> None:
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("artifact_owners.py")), "--plan-dir", str(Path(__file__).parent.parent), "--slice", "S5", "--stage", "red"], capture_output=True, text=True)
    assert result.returncode == 1 and "FAILURE_ID:PROMOTION-FALSE-GREEN-RED" in result.stdout
