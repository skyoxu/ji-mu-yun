from independent_judge import validate_judge

def test_judge_requires_observed_nonzero_execution() -> None:
    receipt = {"executor_id":"sut-executor", "judge_id":"independent-judge", "descriptor_hash":"sha256:descriptor-a", "candidate_hash":"sha256:candidate-a", "run_id":"RUN-S3", "exit_code":0, "actual_argv":["py"]}
    observation = {"run_id":"RUN-S3", "descriptor_argv":["py"], "descriptor_hash":"sha256:descriptor-b", "expected_exit":"zero", "executions":1, "acceptance_assertions":{"A-JUDGE":"receipt.exit_code == 0"}}
    accepted, failure = validate_judge(receipt, observation)
    assert not accepted and failure == "JUDGE-INDEPENDENCE-UNPROVEN", f"FAILURE_ID:{failure or 'JUDGE-INDEPENDENCE-UNPROVEN'}"
