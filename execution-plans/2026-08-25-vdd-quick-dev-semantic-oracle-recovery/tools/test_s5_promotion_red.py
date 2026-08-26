import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import validate_promotion

def test_false_green_promotion_red() -> None:
    fixtures = [{"fixture_id": f"FG-{i:02d}", "blocked": True, "corrected_pair_pass": True} for i in range(1, 10)]
    assert validate_promotion(fixtures, "judge-v1", "coverage-gate") == (True, "")
    accepted, failure_id = validate_promotion(fixtures[:-1], "judge-v1", "coverage-gate")
    assert not accepted and failure_id == "PROMOTION-FALSE-GREEN-RED"
