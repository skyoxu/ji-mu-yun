#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SC_DIR = REPO_ROOT / "scripts" / "sc"
if str(SC_DIR) not in sys.path:
    sys.path.insert(0, str(SC_DIR))

from _change_scope import classify_change_scope_between_snapshots  # noqa: E402
from _git_snapshot import current_git_fingerprint, git_snapshots_match, has_complete_content_identity  # noqa: E402


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


class GitSnapshotTests(unittest.TestCase):
    def _repository(self, root: Path) -> None:
        _git(root, "init")
        _git(root, "config", "user.email", "review@example.invalid")
        _git(root, "config", "user.name", "Review Test")
        (root / "tracked.txt").write_text("base\n", encoding="utf-8")
        _git(root, "add", "tracked.txt")
        _git(root, "commit", "-m", "base")

    def test_dirty_tracked_bytes_change_with_same_status_is_not_same_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._repository(root)
            (root / "tracked.txt").write_text("first\n", encoding="utf-8")
            first = current_git_fingerprint(root=root)
            (root / "tracked.txt").write_text("second\n", encoding="utf-8")
            second = current_git_fingerprint(root=root)

            self.assertEqual(first["head"], second["head"])
            self.assertEqual(first["status_short"], second["status_short"])
            self.assertFalse(git_snapshots_match(first, second))
            scope = classify_change_scope_between_snapshots(previous_git=first, current_git=second)
            unchanged_scope = classify_change_scope_between_snapshots(previous_git=first, current_git=first)
            self.assertTrue(scope["content_identity_changed_without_status_delta"])
            self.assertEqual("full-pipeline", scope["deterministic_strategy"])
            self.assertNotEqual(unchanged_scope["change_fingerprint"], scope["change_fingerprint"])

    def test_staged_and_untracked_bytes_are_part_of_snapshot_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._repository(root)
            (root / "tracked.txt").write_text("staged-one\n", encoding="utf-8")
            _git(root, "add", "tracked.txt")
            staged_one = current_git_fingerprint(root=root)
            (root / "tracked.txt").write_text("staged-two\n", encoding="utf-8")
            _git(root, "add", "tracked.txt")
            staged_two = current_git_fingerprint(root=root)
            self.assertEqual(staged_one["status_short"], staged_two["status_short"])
            self.assertFalse(git_snapshots_match(staged_one, staged_two))

            _git(root, "reset", "--hard", "HEAD")
            (root / "new.txt").write_text("one\n", encoding="utf-8")
            untracked_one = current_git_fingerprint(root=root)
            (root / "new.txt").write_text("two\n", encoding="utf-8")
            untracked_two = current_git_fingerprint(root=root)
            self.assertEqual(untracked_one["status_short"], untracked_two["status_short"])
            self.assertFalse(git_snapshots_match(untracked_one, untracked_two))

    def test_legacy_fingerprint_does_not_match_current_versioned_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._repository(root)
            current = current_git_fingerprint(root=root)
            legacy = {"head": current["head"], "status_short": current["status_short"]}

            self.assertFalse(git_snapshots_match(legacy, current))

    def test_tampered_or_unknown_versioned_fingerprint_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._repository(root)
            current = current_git_fingerprint(root=root)
            self.assertTrue(has_complete_content_identity(current))

            tampered = json.loads(json.dumps(current))
            tampered["content_identity"]["snapshot_sha256"] = "sha256:" + "0" * 64
            self.assertFalse(has_complete_content_identity(tampered))
            self.assertFalse(git_snapshots_match(current, tampered))

            unknown = {"schema_version": "sc-review-git-fingerprint.v999", "head": current["head"], "status_short": []}
            self.assertFalse(git_snapshots_match(unknown, unknown))
            scope = classify_change_scope_between_snapshots(previous_git=unknown, current_git=current)
            self.assertTrue(scope["content_identity_incompatible"])
            self.assertEqual("full-pipeline", scope["deterministic_strategy"])

    def test_special_index_flags_make_snapshot_incomplete(self) -> None:
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._repository(root)
                _git(root, "update-index", flag, "tracked.txt")

                snapshot = current_git_fingerprint(root=root)

                self.assertFalse(has_complete_content_identity(snapshot))
                self.assertIn("git_special_index_flags_present", snapshot["content_identity"]["error_codes"])


if __name__ == "__main__":
    unittest.main()
