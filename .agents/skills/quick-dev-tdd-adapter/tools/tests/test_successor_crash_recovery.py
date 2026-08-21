import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[5]
TOOLS = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools"


def _load():
    spec = importlib.util.spec_from_file_location("loop_plan_directory_r1", TOOLS / "loop_plan_directory.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_successor_reservation_reuses_identical_lineage(tmp_path):
    module = _load()
    predecessor = tmp_path / "RUN-OLD"
    predecessor.mkdir()
    lineage = {"predecessor_run": "logs/tdd-adapter/plan/R1/RUN-OLD", "next_transition": "green", "authorizes": []}
    first = module.reserve_successor_run(predecessor, lineage)
    second = module.reserve_successor_run(predecessor, lineage)
    assert first == second
    assert (first / "successor-lineage.v1.json").is_file()


def test_successor_reservation_rejects_competing_lineage_after_crash(tmp_path):
    module = _load()
    predecessor = tmp_path / "RUN-OLD"
    predecessor.mkdir()
    initial = {"predecessor_run": "logs/tdd-adapter/plan/R1/RUN-OLD", "next_transition": "slice-terminal", "authorizes": []}
    successor = module.reserve_successor_run(predecessor, initial)
    assert json.loads((successor / "successor-lineage.v1.json").read_text(encoding="utf-8"))["next_transition"] == "slice-terminal"
    with pytest.raises(RuntimeError, match="conflicts"):
        module.reserve_successor_run(predecessor, {**initial, "next_transition": "green"})
