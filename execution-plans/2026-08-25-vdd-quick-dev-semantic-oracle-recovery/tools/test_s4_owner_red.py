from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import artifact_owners


def test_coverage_owner_computes_run_local_exact_cover(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    assert artifact_owners.run(tmp_path, "S4", "green", run_root) == 0, "FAILURE_ID:COVERAGE-PRODUCER-MISSING"
    value = __import__("json").loads((run_root / "acceptance-coverage.v1.json").read_text(encoding="utf-8"))
    assert value.get("producer") == "coverage-gate" and value.get("slice_id") == "S4" and value.get("run_id") == run_root.name, "FAILURE_ID:COVERAGE-PRODUCER-MISSING"
