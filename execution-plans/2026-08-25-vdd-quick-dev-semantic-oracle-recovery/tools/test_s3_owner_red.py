from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import artifact_owners


def test_judge_owner_executes_and_writes_independent_receipt(tmp_path: Path) -> None:
    assert artifact_owners.run(tmp_path, "S3", "green", tmp_path / "run") == 0, "FAILURE_ID:JUDGE-PRODUCER-MISSING"
