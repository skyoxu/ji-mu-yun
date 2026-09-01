from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from semantic_feasibility_patch import feasibility_with_planned_red_files


def _case(tmp_path: Path, *, planned: bool) -> tuple[list[dict], list[dict], list[dict], dict]:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "subject.py").write_text("def value():\n    return 0\n", encoding="utf-8")
    snapshots = ["tests/test_subject.py", "tests/fixture.json"]
    planned_files = list(snapshots) if planned else []
    slices = [{
        "slice_id": "S1",
        "production_owners": ["src/subject.py"],
        "allowed_write_paths": ["src/subject.py"],
        "planned_new_files": planned_files,
        "execution_snapshot_paths": snapshots,
        "failure_intent_ids": ["FI-X"],
        "acceptance_ids": ["A-X"],
    }]
    acceptances = [{"acceptance_id": "A-X", "assertion_ids": ["ASSERT-X"]}]
    failures = [{"failure_intent_id": "FI-X", "selector_intent": "tests/test_subject.py"}]
    hints = {"A-X": {"validation_commands": [[sys.executable, "-m", "pytest", "tests/test_subject.py", "-q"]]}}
    return slices, acceptances, failures, hints


def test_planned_new_red_paths_are_feasible_before_q2_materialization(tmp_path: Path) -> None:
    slices, acceptances, failures, hints = _case(tmp_path, planned=True)
    result = feasibility_with_planned_red_files(tmp_path, slices, acceptances, failures, hints)
    assert result["valid"], result["findings"]


def test_missing_unplanned_red_paths_remain_fail_closed(tmp_path: Path) -> None:
    slices, acceptances, failures, hints = _case(tmp_path, planned=False)
    result = feasibility_with_planned_red_files(tmp_path, slices, acceptances, failures, hints)
    assert result["valid"] is False
    assert any("selector-target-missing" in item for item in result["findings"])
