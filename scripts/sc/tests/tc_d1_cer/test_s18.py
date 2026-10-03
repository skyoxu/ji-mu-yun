"""S18 CER checks for exact historical tracked membership preservation."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
VERIFY_BASE_CLEAN = ROOT / "scripts" / "ci" / "verify_base_clean.ps1"
VERIFY_TASK_MAPPING = ROOT / "scripts" / "python" / "verify_task_mapping.py"
ASSERTION = "A-70E6-membership"
FAILURE_ID = "F-70E6-MEMBERSHIP-CHANGE"
PYTHON = shutil.which("py") or sys.executable
PYTHON_PREFIX = ["-3"] if Path(PYTHON).name.lower() == "py.exe" else []


def _tracked_membership(root: Path) -> frozenset[str]:
    """Return the normalized tracked fixture members without touching a live repository."""
    return frozenset(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts and "logs" not in path.parts
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def _fixture_repository(tmp_path: Path) -> tuple[Path, frozenset[str]]:
    root = tmp_path / "membership-fixture"
    (root / "docs" / "architecture" / "base").mkdir(parents=True)
    (root / "docs" / "architecture" / "base" / "01-foundation.md").write_text(
        "CH01 foundation\n", encoding="utf-8", newline="\n"
    )
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "docs" / "adr" / "ADR-0001-fixture.md").write_text(
        "# Fixture ADR\n", encoding="utf-8", newline="\n"
    )
    _write_json(
        root / ".taskmaster" / "tasks" / "tasks.json",
        {"master": {"tasks": [{"id": 1, "title": "fixture"}]}},
    )
    _write_json(
        root / ".taskmaster" / "tasks" / "tasks_back.json",
        [{"taskmaster_id": 1, "acceptance": ["fixture"]}],
    )
    _write_json(
        root / ".taskmaster" / "tasks" / "tasks_gameplay.json",
        [{"taskmaster_id": 1, "acceptance": ["fixture"]}],
    )
    (root / "historical.txt").write_text("frozen membership\n", encoding="utf-8", newline="\n")

    return root, _tracked_membership(root)


def _run_base_clean(root: Path) -> subprocess.CompletedProcess[str]:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        raise RuntimeError("PowerShell is required to invoke the production verifier")
    return subprocess.run(
        [powershell, "-NoProfile", "-File", str(VERIFY_BASE_CLEAN), "-RepoRoot", str(root)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )


def _run_task_mapping(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, *PYTHON_PREFIX, str(VERIFY_TASK_MAPPING)],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )


def _assert_target(condition: bool, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{FAILURE_ID}")
    assert condition, detail


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("added", marks=pytest.mark.cer_assertion(ASSERTION)),
        pytest.param("deleted", marks=pytest.mark.cer_assertion(ASSERTION)),
        pytest.param("renamed", marks=pytest.mark.cer_assertion(ASSERTION)),
    ],
)
def test_production_verifiers_reject_changed_tracked_membership(mutation: str) -> None:
    with tempfile.TemporaryDirectory(prefix="s18-membership-", dir=r"C:\tmp") as directory:
        root, before = _fixture_repository(Path(directory))
        baseline_clean = _run_base_clean(root)
        baseline_mapping = _run_task_mapping(root)
        assert baseline_clean.returncode == 0, baseline_clean.stdout + baseline_clean.stderr
        assert baseline_mapping.returncode == 0, baseline_mapping.stdout + baseline_mapping.stderr
        assert "Task mapping verification report" in baseline_mapping.stdout

        if mutation == "added":
            (root / "added.txt").write_text("new member\n", encoding="utf-8", newline="\n")
        elif mutation == "deleted":
            (root / "historical.txt").unlink()
        else:
            (root / "historical.txt").rename(root / "renamed.txt")

        after = _tracked_membership(root)
        assert after != before

        result = _run_base_clean(root)
        _assert_target(
            result.returncode != 0,
            {"mutation": mutation, "before": sorted(before), "after": sorted(after), "stdout": result.stdout},
        )
