import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import validate_many_to_many_cover

def test_exact_cover_red() -> None:
    edges = [{"acceptance_id": "A", "case_id": "C1", "observation_id": "O1"}, {"acceptance_id": "A", "case_id": "C2", "observation_id": "O2"}, {"acceptance_id": "B", "case_id": "C2", "observation_id": "O2"}]
    assert validate_many_to_many_cover(edges, {"A", "B"}, {"O1", "O2"}) == (True, "")
    accepted, failure_id = validate_many_to_many_cover(edges[:1], {"A", "B"}, {"O1", "O2"})
    assert not accepted and failure_id == "COVERAGE-EXACT-COVER-RED"
