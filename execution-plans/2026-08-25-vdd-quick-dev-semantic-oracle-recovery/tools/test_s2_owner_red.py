from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import artifact_owners


def test_descriptor_owner_emits_bound_run_local_descriptor(tmp_path: Path) -> None:
    assert artifact_owners.run(tmp_path, "S2", "green", tmp_path / "run") == 0, "FAILURE_ID:QD-DESCRIPTOR-PRODUCER-MISSING"
