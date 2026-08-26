from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import artifact_owners


def test_promotion_owner_runs_all_false_green_fixtures(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    assert artifact_owners.run(tmp_path, "S5", "green", run_root) == 0, "FAILURE_ID:PROMOTION-PRODUCER-MISSING"
    value = __import__("json").loads((run_root / "false-green-fixtures.v1.json").read_text(encoding="utf-8"))
    assert value.get("producer") == "coverage-gate" and value.get("slice_id") == "S5" and value.get("run_id") == run_root.name, "FAILURE_ID:PROMOTION-PRODUCER-MISSING"
