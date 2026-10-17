"""CER binding for repository-relative historical path membership."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SC_DIR = ROOT / "scripts" / "sc"
if str(SC_DIR) not in sys.path:
    sys.path.insert(0, str(SC_DIR))

from _git_snapshot import current_git_fingerprint, git_snapshots_match  # noqa: E402


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def _tracked_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True, text=True, encoding="utf-8",
    )
    return {line for line in result.stdout.splitlines() if line}


@pytest.mark.cer_assertion("FR5-PATH-MEMBERSHIP")
@pytest.mark.parametrize("mutation", ["unchanged", "added", "deleted", "renamed"])
def test_repository_relative_path_membership_is_preserved_or_rejected(mutation: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        git_dir = Path(tempfile.mkdtemp(prefix="s32-cer-git-"))
        _git(root, "init", "--separate-git-dir", str(git_dir))
        _git(root, "config", "user.email", "review@example.invalid")
        _git(root, "config", "user.name", "Review Test")
        (root / "historical.txt").write_bytes(b"historical bytes\n")
        _git(root, "add", "historical.txt")
        _git(root, "commit", "-m", "baseline")
        before = _tracked_paths(root)
        baseline = current_git_fingerprint(root=root)

        if mutation == "added":
            (root / "new-member.txt").write_bytes(b"new member\n")
            _git(root, "add", "new-member.txt")
        elif mutation == "deleted":
            _git(root, "rm", "historical.txt")
        elif mutation == "renamed":
            _git(root, "mv", "historical.txt", "relocated.txt")

        after = _tracked_paths(root)
        candidate = current_git_fingerprint(root=root)
        unchanged = mutation == "unchanged"
        behavior_ok = (after == before and git_snapshots_match(baseline, candidate)) if unchanged else (
            after != before and not git_snapshots_match(baseline, candidate)
        )
        if not behavior_ok:
            print("FAILURE_ID:FR5-PATH-CHANGE-ACCEPTED")
        assert behavior_ok, {"mutation": mutation, "before": sorted(before), "after": sorted(after)}
