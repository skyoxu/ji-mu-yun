from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import artifact_owners


def test_coverage_owner_computes_run_local_exact_cover(tmp_path: Path) -> None:
    assert artifact_owners.run(tmp_path, "S4", "green", tmp_path / "run") == 0, "FAILURE_ID:COVERAGE-PRODUCER-MISSING"
