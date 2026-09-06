"""ADR-0041: exact command binding repairs only redundant omitted-directory paths."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from semantic_selector_path_projection import project_selector_paths
import semantic_worker_v3_execution_contract_patch as execution


def case(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/owner.py").write_text("VALUE = 1\n")
    (tmp_path / "tools/tests").mkdir(parents=True)
    (tmp_path / "tools/tests/test_route.py").write_text("assert True\n")
    return {"slice_hints": [{"obligation_ids": ["O-1"], "production_owners": ["src/owner.py"],
             "allowed_write_paths": ["src/owner.py"], "planned_new_files": [],
             "execution_snapshot_paths": ["tools/test_route.py"],
             "validation_commands": [["python", "tools/tests/test_route.py"]]}],
            "acceptances": [{"obligation_ids": ["O-1"]}]}


def test_transport_projects_and_records_without_mutating_worker_output(tmp_path, monkeypatch):
    value = case(tmp_path)
    original = deepcopy(value)
    monkeypatch.setattr(execution, "_BASE_TRANSPORT", lambda **kw: value)
    monkeypatch.setattr(execution.total_coverage, "complete_total_coverage", lambda **kw: kw["value"])
    payload = {"obligations": [{"obligation_id": "O-1", "status": "active"}]}
    assert any("selector-target-missing-not-planned" in f for f in execution._findings(tmp_path, "v3", payload, value))
    out = tmp_path / "plan"
    result = execution.execution_contract_transport(root=tmp_path, out_dir=out, stage="v3-schema-repair",
               payload={"input": payload}, prompt="", worker_cache={})
    assert result["slice_hints"][0]["execution_snapshot_paths"] == ["tools/tests/test_route.py"]
    assert execution._findings(tmp_path, "v3", payload, result) == []
    assert list((out / ".compiler-work/selector-path-projections").glob("*.json"))
    assert value == original
    assert result["acceptances"] == original["acceptances"]


@pytest.mark.parametrize("defect", ["existing", "planned", "multiple_commands", "multiple_snapshots",
    "different_name", "different_tree", "missing_target", "source_explicit", "other_field", "module_command"])
def test_ambiguous_or_explicit_paths_remain_unchanged(tmp_path, defect):
    value = case(tmp_path)
    hint = value["slice_hints"][0]
    source = {}
    if defect == "existing":
        (tmp_path / "tools/test_route.py").write_text("assert False\n")
    elif defect == "planned":
        hint["planned_new_files"] = ["tools/test_route.py"]
    elif defect == "multiple_commands":
        hint["validation_commands"] *= 2
    elif defect == "multiple_snapshots":
        hint["execution_snapshot_paths"].append("fixture.json")
    elif defect == "different_name":
        hint["execution_snapshot_paths"] = ["tools/test_other.py"]
    elif defect == "different_tree":
        hint["execution_snapshot_paths"] = ["other/test_route.py"]
    elif defect == "missing_target":
        (tmp_path / "tools/tests/test_route.py").unlink()
    elif defect == "source_explicit":
        source = {"source_contracts": [{"source_text": "Use tools/test_route.py"}]}
    elif defect == "other_field":
        hint["forbidden_paths"] = ["tools/test_route.py"]
    elif defect == "module_command":
        hint["validation_commands"] = [["python", "-m", "pytest", "tools/tests/test_route.py"]]
    original = deepcopy(value)
    result, changes = project_selector_paths(tmp_path, source, value)
    assert result == original
    assert changes == []
