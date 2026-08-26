import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import validate_judge

def test_judge_independence_red() -> None:
    receipt = {"executor_id": "executor-v1", "judge_id": "judge-v1", "descriptor_hash": "sha256:d", "candidate_hash": "sha256:c", "run_id": "R1", "exit_code": 0}
    observation = {"run_id": "R1", "assertions": []}
    assert validate_judge(receipt, observation) == (True, "")
    accepted, failure_id = validate_judge(dict(receipt, judge_id="sut"), observation)
    assert not accepted and failure_id == "JUDGE-INDEPENDENCE-RED"
