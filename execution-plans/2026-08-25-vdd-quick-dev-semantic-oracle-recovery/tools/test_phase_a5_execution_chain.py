from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


PLAN = Path(__file__).parent.parent
STAGE = PLAN / "tools" / "stage_command.py"
READY = PLAN / "tools" / "slice_ready_predicate.py"


def test_green_rejects_owner_success_while_successor_red_still_fails(tmp_path: Path) -> None:
    result = subprocess.run([sys.executable, str(STAGE), "--slice", "S1", "--stage", "green", "--plan-dir", str(PLAN), "--run-root", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode != 0


def test_s1_slice_ready_rejects_placeholder_observations(tmp_path: Path) -> None:
    (tmp_path / "observations").mkdir()
    for name in ("green-observed.json", "refactor-observed.json"):
        (tmp_path / "observations" / name).write_text("{}\n", encoding="utf-8")
    out = tmp_path / "slice-ready-result.json"
    result = subprocess.run([sys.executable, str(READY), "--repository-root", str(PLAN.parents[1]), "--plan-dir", str(PLAN), "--slice", "S1", "--run-root", str(tmp_path), "--out", str(out)], capture_output=True, text=True)
    assert result.returncode != 0
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "blocked"


def test_s6_requires_all_slice_lineage(tmp_path: Path) -> None:
    out = tmp_path / "implementation-complete-result.json"
    result = subprocess.run([sys.executable, str(PLAN / "tools" / "terminal_predicate.py"), "--repository-root", str(PLAN.parents[1]), "--plan-dir", str(PLAN), "--slice", "S6", "--run-root", str(tmp_path), "--out", str(out)], capture_output=True, text=True)
    assert result.returncode != 0
