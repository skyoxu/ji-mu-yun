from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import artifact_owners


def test_judge_owner_executes_and_writes_independent_receipt(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    assert artifact_owners.run(tmp_path, "S3", "green", run_root) == 0, "FAILURE_ID:JUDGE-PRODUCER-MISSING"
    value = __import__("json").loads((run_root / "process-receipt.v1.json").read_text(encoding="utf-8"))
    assert value.get("producer") == "independent-judge" and value.get("slice_id") == "S3" and value.get("run_id") == run_root.name, "FAILURE_ID:JUDGE-PRODUCER-MISSING"
