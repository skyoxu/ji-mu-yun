from semantic_oracle import validate_judge


def test_rejects_descriptor_execution_drift() -> None:
    accepted, _ = validate_judge({"executor_id":"executor-entrypoint","judge_id":"judge-entrypoint","descriptor_hash":"sha256:descriptor","candidate_hash":"sha256:candidate","run_id":"run-1","exit_code":0,"actual_argv":["different"]}, {"run_id":"run-1","descriptor_argv":["frozen"]})
    assert not accepted, "FAILURE_ID:JUDGE-INDEPENDENCE-UNPROVEN"
