"""S32 integration checks for frozen Git tracked-path membership."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import shutil
import time
import uuid
from pathlib import Path

import pytest

_CER_ASSERTION_BINDINGS = [pytest.mark.cer_assertion("A-NFR7-EXTERNAL-PROCESS-BOUNDED")]


ROOT = Path(__file__).resolve().parents[4]
SC_DIR = ROOT / "scripts" / "sc"
if str(SC_DIR) not in sys.path:
    sys.path.insert(0, str(SC_DIR))

from _git_snapshot import current_git_fingerprint, git_snapshots_match, has_complete_content_identity  # noqa: E402

TOOLS = ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from current_router import materialize_descriptor  # noqa: E402
from process_executor_v2 import execute_process  # noqa: E402


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True, text=True, encoding="utf-8",
    )


def _repository(root: Path) -> None:
    git_dir = Path(tempfile.mkdtemp(prefix="s32-git-"))
    _git(root, "init", "--separate-git-dir", str(git_dir))
    _git(root, "config", "user.email", "review@example.invalid")
    _git(root, "config", "user.name", "Review Test")
    (root / "frozen.txt").write_bytes(b"frozen historical bytes\n")
    _git(root, "add", "frozen.txt")
    _git(root, "commit", "-m", "baseline")


def _tracked_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=root, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True, text=True, encoding="utf-8",
    )
    return {line for line in result.stdout.splitlines() if line}


def _assert_snapshot(condition: bool, failure_id: str, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, detail


@pytest.mark.cer_assertion("A-70341EC7ADE8-1")
@pytest.mark.parametrize("mutation", ["unchanged", "added", "deleted", "renamed"])
def test_tracked_membership_snapshot_accepts_only_unchanged_control(mutation: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _repository(root)
        before_paths = _tracked_paths(root)
        baseline = current_git_fingerprint(root=root)

        if mutation == "added":
            (root / "added.txt").write_bytes(b"new tracked member\n")
            _git(root, "add", "added.txt")
        elif mutation == "deleted":
            _git(root, "rm", "frozen.txt")
        elif mutation == "renamed":
            _git(root, "mv", "frozen.txt", "moved.txt")

        after_paths = _tracked_paths(root)
        candidate = current_git_fingerprint(root=root)
        complete = has_complete_content_identity(baseline) and has_complete_content_identity(candidate)
        matches = git_snapshots_match(baseline, candidate)
        expected_paths = before_paths if mutation == "unchanged" else {
            "added": before_paths | {"added.txt"},
            "deleted": before_paths - {"frozen.txt"},
            "renamed": (before_paths - {"frozen.txt"}) | {"moved.txt"},
        }[mutation]
        _assert_snapshot(
            complete and after_paths == expected_paths and matches is (mutation == "unchanged"),
            "F-70341EC7ADE8-HISTORICAL-MEMBERSHIP-CHANGED",
            {"mutation": mutation, "before": sorted(before_paths), "after": sorted(after_paths), "matches": matches},
        )


@pytest.mark.cer_assertion("A-NFR7-EXTERNAL-PROCESS-BOUNDED")
def test_external_process_timeout_has_bounded_terminal_receipt() -> None:
    tmp_path = ROOT / f".s32-runtime-{uuid.uuid4().hex}"
    tmp_path.mkdir()
    try:
        worker = tmp_path / "worker.py"
        worker.write_text("import time\nimport pytest\n@pytest.mark.cer_assertion('A-NFR7-EXTERNAL-PROCESS-BOUNDED')\ndef test_sleeping_worker():\n    time.sleep(2)\n", encoding="utf-8")
        fixture = tmp_path / "fixture.txt"
        fixture.write_text("bounded\n", encoding="utf-8")
        bundle = {
            "schema_version": "vdd.semantic-plan-bundle.v1",
            "plan_id": "PLAN-7B2637C400E8",
            "obligations": [{"obligation_id": "O-A2EB2B214D66", "status": "active"}],
            "acceptances": [{"acceptance_id": "A-4A962ABEBD9B", "obligation_ids": ["O-A2EB2B214D66"], "assertion_ids": ["A-NFR7-EXTERNAL-PROCESS-BOUNDED"]}],
            "slices": [{"slice_id": "S32", "acceptance_ids": ["A-4A962ABEBD9B"], "obligation_ids": ["O-A2EB2B214D66"], "execution_snapshot_paths": ["worker.py", "fixture.txt"]}],
        }
        descriptor = materialize_descriptor(
            bundle=bundle, slice_id="S32", stage="terminal", run_id="RUN-S32",
            candidate_hash="sha256:" + "0" * 64,
            argv=[sys.executable, "-m", "pytest", "worker.py", "-q"], cwd=".",
            timeout_seconds=1, target_refs=["worker.py"], fixture_refs=["fixture.txt"],
        )
        receipt = execute_process(tmp_path, tmp_path / "RUN-S32", "terminal", descriptor, profile_identity="standard")
        bounded = (
            receipt.get("timed_out") is True
            and receipt.get("process_attempts") == 1
            and receipt.get("exit_code") is None
            and isinstance(receipt.get("elapsed_seconds"), (int, float))
            and receipt["elapsed_seconds"] <= descriptor["timeout_seconds"] + 0.5
            and receipt.get("timeout_seconds") == descriptor["timeout_seconds"]
            and isinstance(receipt.get("output_limit_bytes"), int)
            and receipt["output_limit_bytes"] > 0
            and receipt.get("case_report") is None
            and receipt.get("cases") == 0
        )
        _assert_snapshot(bounded, "F-EXTERNAL-PROCESS-TIMEOUT", receipt)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
