from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from q1_planned_preflight import validate_planned_preflight


def _bundle() -> dict:
    return {
        "plan_id": "PLAN-Q1",
        "slices": [
            {
                "slice_id": "S1",
                "acceptance_ids": ["A-Q1"],
                "production_owners": ["src/service.py"],
                "allowed_write_paths": ["src/service.py"],
                "planned_new_files": ["tests/test_service.py", "tests/fixture.json"],
                "execution_snapshot_paths": ["tests/test_service.py", "tests/fixture.json"],
                "proof": {"selector_intents": ["tests/test_service.py::test_behavior"]},
            }
        ],
        "agent_contexts": [
            {
                "slice_id": "S1",
                "acceptance_ids": ["A-Q1"],
                "selector_intents": ["tests/test_service.py::test_behavior"],
                "validation_commands": [[sys.executable, "-m", "pytest", "tests/test_service.py", "-q"]],
            }
        ],
    }


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text("def behavior(): return False\n", encoding="utf-8")
    return tmp_path


def test_q1_accepts_missing_red_files_only_when_declared_planned(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    before = sorted(path.relative_to(workspace).as_posix() for path in workspace.rglob("*"))
    result = validate_planned_preflight(
        workspace=workspace,
        bundle=_bundle(),
        slice_id="S1",
        timeout_seconds=120,
    )
    after = sorted(path.relative_to(workspace).as_posix() for path in workspace.rglob("*"))
    assert result["status"] == "planned-contract-valid"
    assert result["required_next_action"] == "author-red"
    assert result["argv"][1:3] == ["-m", "pytest"]
    assert result["target_refs"] == ["tests/test_service.py"]
    assert result["fixture_refs"] == ["tests/fixture.json"]
    assert result["cwd"] == "." and result["shell"] is False and result["timeout_seconds"] == 120
    assert result["model_called"] is False and result["tests_executed"] is False and result["writes_performed"] is False
    assert before == after


def test_q1_rejects_empty_argv_before_execution(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    bundle = _bundle()
    bundle["agent_contexts"][0]["validation_commands"] = [[]]
    try:
        validate_planned_preflight(workspace=workspace, bundle=bundle, slice_id="S1", timeout_seconds=120)
    except ValueError as exc:
        assert "argv" in str(exc)
    else:
        raise AssertionError("empty argv must be rejected")


def test_q1_rejects_unmaterialized_unplanned_snapshot_and_owner_outside_write_set(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    missing = _bundle()
    missing["slices"][0]["planned_new_files"] = []
    try:
        validate_planned_preflight(workspace=workspace, bundle=missing, slice_id="S1", timeout_seconds=120)
    except ValueError as exc:
        assert "neither materialized nor declared planned" in str(exc)
    else:
        raise AssertionError("unplanned target/fixture must be rejected")

    owner = _bundle()
    owner["slices"][0]["allowed_write_paths"] = ["src/other.py"]
    try:
        validate_planned_preflight(workspace=workspace, bundle=owner, slice_id="S1", timeout_seconds=120)
    except ValueError as exc:
        assert "owner outside" in str(exc)
    else:
        raise AssertionError("owner outside GREEN write set must be rejected")


def test_q1_rejects_nonpositive_timeout_and_projection_drift(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    try:
        validate_planned_preflight(workspace=workspace, bundle=_bundle(), slice_id="S1", timeout_seconds=0)
    except ValueError as exc:
        assert "timeout" in str(exc)
    else:
        raise AssertionError("nonpositive timeout must be rejected")

    drift = deepcopy(_bundle())
    drift["agent_contexts"][0]["selector_intents"] = ["tests/other.py::test_other"]
    try:
        validate_planned_preflight(workspace=workspace, bundle=drift, slice_id="S1", timeout_seconds=120)
    except ValueError as exc:
        assert "selector projection drift" in str(exc)
    else:
        raise AssertionError("selector projection drift must be rejected")
