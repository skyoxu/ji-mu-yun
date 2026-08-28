from independent_judge import validate_judge

def test_judge_requires_observed_nonzero_execution() -> None:
    receipt = {"executor_id":"sut-executor","judge_id":"independent-judge","descriptor_hash":"sha256:d","candidate_hash":"sha256:c","run_id":"R","exit_code":0,"actual_argv":["python"]}
    observation = {"run_id":"R","descriptor_argv":["python"],"expected_exit":"nonzero","executions":0}
    accepted, failure_id = validate_judge(receipt, observation)
    assert not accepted and failure_id == "JUDGE-INDEPENDENCE-UNPROVEN", f"FAILURE_ID:{failure_id or 'JUDGE-INDEPENDENCE-UNPROVEN'}"
