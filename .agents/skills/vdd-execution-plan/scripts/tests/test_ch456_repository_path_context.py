"""ADR-0041: repository discovery aids V3 without repairing invented paths."""
from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from semantic_repository_context import enrich_repository_context
from semantic_worker_v3_execution_contract_patch import _findings


def test_context_contains_existing_relevant_paths_and_excludes_evidence(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    bodies = {"src/compiler.py": "VALUE = 1\n", "tests/test_compiler.py": "assert True\n",
              "logs/compiler.py": "historical\n", ".tmp-old/compiler.py": "temporary\n"}
    for name, body in bodies.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    payload = {"obligations": [{"obligation_id": "O-1", "subject": "VDD compiler"}]}
    original = deepcopy(payload)
    enriched = enrich_repository_context(tmp_path, payload)
    files = enriched["repository_path_context"]["files"]
    assert {f["path"] for f in files} == {"src/compiler.py", "tests/test_compiler.py"}
    for entry in files:
        assert entry["sha256"] == "sha256:" + hashlib.sha256((tmp_path / entry["path"]).read_bytes()).hexdigest()
    assert enriched["repository_path_context"]["complete"] is False
    assert payload == original
    repair = enrich_repository_context(tmp_path, {"input": enriched, "validator_findings": ["timeout"]})
    assert repair["input"]["repository_path_context"] == enriched["repository_path_context"]
    limited = enrich_repository_context(tmp_path, payload, max_files=1)
    assert len(limited["repository_path_context"]["files"]) == 1


def test_unavailable_discovery_does_not_invent_file_candidates(tmp_path):
    result = enrich_repository_context(tmp_path, {"obligations": [{"subject": "VDD compiler"}]})
    assert result["repository_path_context"]["status"] == "discovery-unavailable"
    assert result["repository_path_context"]["files"] == []


def test_subject_owner_and_future_log_still_fail_execution_contract(tmp_path):
    # Captured failure shape: discovery must not convert this into valid proof.
    payload = {"obligations": [{"obligation_id": "O-1", "subject": "VDD compiler", "status": "active"}]}
    value = {"acceptances": [{"obligation_ids": ["O-1"]}], "slice_hints": [{
        "production_owners": ["VDD compiler"], "allowed_write_paths": [], "planned_new_files": [],
        "execution_snapshot_paths": ["logs/vdd-compiler-recommendation.json"]}]}
    original = deepcopy(value)
    result = _findings(tmp_path, "v3", enrich_repository_context(tmp_path, payload), value)
    assert any("no-real-production-entry" in f for f in result)
    assert any("selector-target-missing-not-planned" in f for f in result)
    assert value == original
