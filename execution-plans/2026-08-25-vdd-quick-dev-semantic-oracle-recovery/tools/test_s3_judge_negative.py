from semantic_oracle import validate_judge


def test_judge_rejects_sut_self_certification() -> None:
    accepted, failure_id = validate_judge({"executor_id":"sut","judge_id":"sut","descriptor_hash":"sha256:x","candidate_hash":"sha256:y","run_id":"R","exit_code":0}, {"run_id":"R"})
    assert not accepted and failure_id == "JUDGE-INDEPENDENCE-RED"
