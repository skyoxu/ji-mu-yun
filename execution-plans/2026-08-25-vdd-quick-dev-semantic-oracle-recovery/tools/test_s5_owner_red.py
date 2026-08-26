from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import artifact_owners


def test_promotion_owner_runs_all_false_green_fixtures(tmp_path: Path) -> None:
    assert artifact_owners.run(tmp_path, "S5", "green", tmp_path / "run") == 0, "FAILURE_ID:PROMOTION-PRODUCER-MISSING"
