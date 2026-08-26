from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import artifact_owners


def test_descriptor_owner_emits_bound_run_local_descriptor(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    assert artifact_owners.run(tmp_path, "S2", "green", run_root) == 0, "FAILURE_ID:QD-DESCRIPTOR-PRODUCER-MISSING"
    value = __import__("json").loads((run_root / "execution-descriptor.v1.json").read_text(encoding="utf-8"))
    assert value.get("producer") == "quick-dev" and value.get("slice_id") == "S2" and value.get("run_id") == run_root.name, "FAILURE_ID:QD-DESCRIPTOR-PRODUCER-MISSING"
