from pathlib import Path
def test_judge_independence_red() -> None:
    if not (Path(__file__).parents[1] / "probe-state" / "S3.json").is_file():
        raise AssertionError("FAILURE_ID:JUDGE-INDEPENDENCE-RED")
