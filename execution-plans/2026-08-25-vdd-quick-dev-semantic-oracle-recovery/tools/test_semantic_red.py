import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import validate_semantic_intent

def test_vdd_semantic_oracle_boundary_red() -> None:
    valid = {"acceptance_ids": ["A-SEMANTIC"], "producer": "vdd", "coverage": "oracle", "fixture_class": "positive", "taxonomy": ["boundary"]}
    assert validate_semantic_intent(valid) == (True, "")
    accepted, failure_id = validate_semantic_intent(dict(valid, executable="python"))
    assert not accepted and failure_id == "VDD-RED-BOUNDARY"

def test_semantic_boundary_rejects_missing_acceptance() -> None:
    accepted, failure_id = validate_semantic_intent({"producer": "vdd", "coverage": "oracle", "fixture_class": "negative", "taxonomy": []})
    assert not accepted and failure_id == "VDD-RED-BOUNDARY"
