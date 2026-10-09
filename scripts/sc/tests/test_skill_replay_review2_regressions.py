"""Whole-entry deadline and TEMP ownership regressions (Accepted ADR-0058)."""
from __future__ import annotations

import copy
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import test_skill_replay_review_regressions as support

replay = support.replay


class WholeEntryDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clock = 0.0
        self.receipt = {
            "status": "pass", "exit_code": 0, "authorizes": [], "probes": [],
            "effective_inspected_content": {"identity": "target"},
            "resolved_validator": {"path": "validator.py", "sha256": "validator"},
        }
        self.snapshot = {"inputs": {"dependencies": [], "data": [], "git_baseline": "baseline"}}
        self.patchers = [
            mock.patch.object(replay, "ROOT", self.root),
            mock.patch.object(replay, "time", SimpleNamespace(monotonic=lambda: self.clock)),
            mock.patch.object(replay.runtime, "time", SimpleNamespace(monotonic=lambda: self.clock)),
            mock.patch.object(replay, "current_snapshot_binding", return_value=self.snapshot),
            mock.patch.object(replay, "validate_current_snapshot_binding"),
            mock.patch.object(replay, "historical_receipt", side_effect=lambda value: value),
            mock.patch.object(replay.runtime, "git", return_value=str(self.root).encode()),
            mock.patch.object(replay, "prune_expired_fresh_checkouts", return_value=0),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def metadata(self, *args):
        self.clock = 290.0
        return {"current_snapshot": self.snapshot}

    def native(self, command, root, **kwargs):
        self.child_timeout = kwargs.get("timeout", replay.runtime.REPLAY_TIMEOUT_SECONDS)
        self.clock = self.child_end
        fresh = dict(self.receipt, current_snapshot=self.snapshot)
        return subprocess.CompletedProcess(command, 0, json.dumps({"current_wrapper_replay": fresh}), "")

    def test_validation_spends_the_whole_entry_budget_before_fresh_starts(self):
        def validate(*args):
            self.clock = 301.0
            return copy.deepcopy(self.receipt)

        with mock.patch.object(replay, "validate_package", side_effect=validate), \
             mock.patch.object(replay, "replay_metadata", return_value={}), \
             mock.patch.object(replay, "verify_fresh_replay", return_value={
                 "fresh_checkout": True, "checkout_path": "fixture", "checkout_commit": "baseline"}) as fresh:
            with self.assertRaisesRegex(ValueError, "orchestration timed out"):
                replay.replay_package("target", "capability", "fresh")
            fresh.assert_not_called()

    def test_304_second_whole_replay_cannot_pass_with_a_reset_fresh_clock(self):
        self.child_end = 304.0
        with mock.patch.object(replay, "validate_package", return_value=copy.deepcopy(self.receipt)), \
             mock.patch.object(replay, "replay_metadata", side_effect=self.metadata), \
             mock.patch.object(replay.runtime, "execute_replay", side_effect=self.native):
            with self.assertRaisesRegex(ValueError, "orchestration timed out"):
                replay.replay_package("target", "capability", "fresh")

    def test_fresh_child_gets_only_remaining_time_with_success_positive_control(self):
        self.child_end = 299.0
        with mock.patch.object(replay, "validate_package", return_value=copy.deepcopy(self.receipt)), \
             mock.patch.object(replay, "replay_metadata", side_effect=self.metadata), \
             mock.patch.object(replay.runtime, "execute_replay", side_effect=self.native):
            result, code = replay.replay_package("target", "capability", "fresh")
        self.addCleanup(lambda: __import__("shutil").rmtree(Path(result["checkout_path"]).parent))
        self.assertEqual(0, code)
        self.assertGreater(self.child_timeout, 0)
        self.assertLessEqual(self.child_timeout, 10)
        self.assertEqual(299, result["replay_orchestration_timing"]["elapsed_seconds"])

    def test_receipt_construction_cannot_hide_over_budget_time(self):
        def receipt(value):
            self.clock = 301.0
            return value

        with mock.patch.object(replay, "validate_package", return_value=copy.deepcopy(self.receipt)), \
             mock.patch.object(replay, "replay_metadata", return_value={}), \
             mock.patch.object(replay, "historical_receipt", side_effect=receipt):
            with self.assertRaisesRegex(ValueError, "orchestration timed out"):
                replay.replay_package("target", "capability", "fresh-child")


class TempOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def stale(self, path):
        old = time.time() - 30
        os.utime(path, (old, old))

    def test_old_directory_used_by_a_live_process_is_not_scavenged(self):
        directory = self.root / "jimuyun-fresh-checkout-active"
        directory.mkdir()
        marker = directory / "live.txt"
        child = subprocess.Popen([sys.executable, "-B", "-c",
                                  "import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text('active'); time.sleep(30)",
                                  str(marker)], cwd=directory)
        try:
            until = time.monotonic() + 10
            while not marker.exists() and time.monotonic() < until:
                time.sleep(.02)
            self.assertTrue(marker.is_file())
            self.stale(directory)
            with mock.patch.object(replay.tempfile, "gettempdir", return_value=str(self.root)):
                removed = replay.prune_expired_fresh_checkouts()
            self.assertIsNone(child.poll())
            self.assertTrue(directory.is_dir(), "cleanup deleted a live replay's directory")
            self.assertEqual("active", marker.read_text())
            self.assertEqual(0, removed)
        finally:
            child.terminate()
            child.wait(timeout=10)

    def test_old_unowned_file_and_directory_are_retained(self):
        directory = self.root / "jimuyun-fresh-checkout-unowned"
        directory.mkdir()
        file = self.root / "jimuyun-fresh-checkout-file"
        file.write_bytes(b"not owned")
        for path in (directory, file):
            self.stale(path)
        with mock.patch.object(replay.tempfile, "gettempdir", return_value=str(self.root)):
            replay.prune_expired_fresh_checkouts()
        self.assertTrue(directory.is_dir())
        self.assertEqual(b"not owned", file.read_bytes())

    def test_external_link_target_permissions_and_bytes_are_not_changed(self):
        outside = self.root / "outside"
        outside.mkdir()
        file = outside / "protected.txt"
        file.write_bytes(b"outside boundary")
        file.chmod(stat.S_IREAD)
        self.addCleanup(lambda: file.chmod(stat.S_IWRITE) if file.exists() else None)
        scan = self.root / "scan"
        scan.mkdir()
        link = scan / "jimuyun-fresh-checkout-link"
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                           check=True, capture_output=True)
        else:
            link.symlink_to(outside, target_is_directory=True)
        before = file.stat().st_mode
        self.stale(link)
        def permission_failure(path, **kwargs):
            # Exercise Windows' readonly retry without changing external data.
            callback = kwargs.get("onerror")
            if callback:
                callback(lambda path: None, str(file), (PermissionError, PermissionError(), None))

        with mock.patch.object(replay.tempfile, "gettempdir", return_value=str(scan)), \
             mock.patch.object(replay.shutil, "rmtree", side_effect=permission_failure), \
             mock.patch.object(replay.os, "chmod") as chmod:
            replay.prune_expired_fresh_checkouts()
        chmod.assert_not_called()
        self.assertEqual(before, file.stat().st_mode)
        self.assertEqual(b"outside boundary", file.read_bytes())
        self.assertTrue(link.exists())


class NativeDeadlineTests(unittest.TestCase):
    def test_nested_budget_cannot_reset_the_parent_deadline(self):
        clock = SimpleNamespace(monotonic=lambda: now[0])
        now = [100.0]
        with mock.patch.object(replay.runtime, "time", clock):
            with self.assertRaisesRegex(ValueError, "orchestration timed out"):
                with replay.runtime.replay_budget():
                    now[0] = 390.0
                    with replay.runtime.replay_budget():
                        self.assertEqual(10, replay.runtime.remaining_timeout(60, "leaf"))
                        now[0] = 400.0
                        with self.assertRaisesRegex(ValueError, "orchestration timed out"):
                            replay.runtime.remaining_timeout(60, "leaf")
            self.assertIsNone(replay.runtime._REPLAY_DEADLINE.get())

    def test_real_sleeping_leaf_is_terminated_at_remaining_parent_budget(self):
        started = time.monotonic()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                with replay.runtime.replay_budget(seconds=.2):
                    replay.runtime.execute([sys.executable, "-B", "-c", "import time; time.sleep(20)"],
                                          Path(directory))
        self.assertLess(time.monotonic() - started, 10)
        self.assertIsNone(replay.runtime._REPLAY_DEADLINE.get())

    def test_git_receives_remaining_time_and_checks_completion(self):
        clock = SimpleNamespace(monotonic=lambda: now[0])
        now = [0.0]
        def native(*args, **kwargs):
            self.assertEqual(5, kwargs["timeout"])
            now[0] = 301.0
            return subprocess.CompletedProcess(args[0], 0, b"result", b"")
        with mock.patch.object(replay.runtime, "time", clock):
            with self.assertRaisesRegex(ValueError, "orchestration timed out"):
                with replay.runtime.replay_budget():
                    now[0] = 295.0
                    with mock.patch.object(replay.runtime.subprocess, "run", side_effect=native):
                        replay.runtime.git(Path.cwd(), "rev-parse", "HEAD")


if __name__ == "__main__":
    unittest.main()
