from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent))
import artifact_owners


def test_descriptor_owner_emits_bound_run_local_descriptor(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    (run_root / "semantic-intent-input.v1.json").write_text(json.dumps({"acceptance_ids":["A-SEMANTIC"],"producer":"vdd","coverage":"exact-cover","fixture_class":"positive","taxonomy":["semantic"]}), encoding="utf-8")
    artifact_owners.compile_run_local_semantic_artifacts(run_root)
    (run_root / "descriptor-input.v1.json").write_text(json.dumps({"descriptor":{"target":"fixture","argv":["py","-3","-c","pass"],"cwd":".","timeout_seconds":30,"shell":False,"case_source_refs":["A-SEMANTIC"],"case_producer_ref":"vdd"}}), encoding="utf-8")
    assert artifact_owners.run(tmp_path, "S2", "green", run_root) == 0, "FAILURE_ID:QD-DESCRIPTOR-PRODUCER-MISSING"
    value = json.loads((run_root / "execution-descriptor.v1.json").read_text(encoding="utf-8"))
    assert value.get("producer") == "quick-dev" and value.get("slice_id") == "S2" and value.get("run_id") == run_root.name, "FAILURE_ID:QD-DESCRIPTOR-PRODUCER-MISSING"


def test_descriptor_owner_rejects_unbound_semantic_input(tmp_path: Path) -> None:
    run_root = tmp_path / "run"; run_root.mkdir()
    (run_root / "semantic-artifacts.v1.json").write_text(json.dumps({"producer":"vdd","status":"pass","slice_id":"S1","run_id":run_root.name,"evidence_sha256":"sha256:forged"}), encoding="utf-8")
    (run_root / "descriptor-input.v1.json").write_text(json.dumps({"descriptor":{"target":"fixture","argv":["py"],"cwd":".","timeout_seconds":30,"shell":False,"case_source_refs":["A"],"case_producer_ref":"vdd"}}), encoding="utf-8")
    assert artifact_owners.run(tmp_path, "S2", "green", run_root) != 0
