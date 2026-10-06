"""Real-process watchdog and closure freshness checks (Accepted ADR-0058)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from scripts.sc import verify_skill_replay as runner


class ClosureFreshnessTests(unittest.TestCase):
    def test_new_module_and_changed_import_bytes_are_seen_in_later_closures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = root / "owner"
            owner.mkdir()
            importer = owner / "entry.py"
            importer.write_text("import first_policy\n", encoding="utf-8")
            initial = runner.runtime.dependency_closure(root, ("owner",))
            self.assertEqual(["owner/entry.py"], [r["path"] for r in initial])
            first = root / "first_policy.py"
            first.write_text("ALLOW = True\n", encoding="utf-8")
            found = runner.runtime.dependency_closure(root, ("owner",))
            self.assertIn("first_policy.py", [r["path"] for r in found])
            importer.write_text("import second_policy\n", encoding="utf-8")
            second = root / "second_policy.py"
            second.write_text("ALLOW = False\n", encoding="utf-8")
            changed = runner.runtime.dependency_closure(root, ("owner",))
            self.assertEqual({"owner/entry.py", "second_policy.py"}, {r["path"] for r in changed})
            second.unlink()
            removed = runner.runtime.dependency_closure(root, ("owner",))
            self.assertEqual(["owner/entry.py"], [r["path"] for r in removed])
            self.assertNotEqual(initial, removed)


class VerificationProcessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def pytest(self, body, *, timeout=10):
        test = self.root / "test_control.py"
        test.write_text(body, encoding="utf-8", newline="\n")
        events = self.root / "events.jsonl"
        command = [sys.executable, "-u", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "-p", "scripts.sc.verify_skill_replay", "--tc-d1-progress", str(events),
                   "--junitxml=" + str(self.root / "junit.xml"), str(test)]
        result = runner.supervise(command, runner.ROOT, self.root / "run", events=events,
                                  test_timeout=timeout, startup_timeout=30, heartbeat=0.3)
        manifests = [r["nodeids"] for r in result["records"] if r["kind"] == "collection"]
        self.assertEqual(1, len(manifests), (self.root / "run/stderr.txt").read_text(encoding="utf-8"))
        return result, manifests[0]

    def test_all_real_phase_reports_and_exact_collection_are_required(self):
        result, expected = self.pytest("def test_first():\n    assert 1 + 1 == 2\ndef test_second():\n    assert 'ok'.upper() == 'OK'\n")
        self.assertTrue(runner.evaluate_reports(result, expected)["pass"])
        self.assertFalse(runner.evaluate_reports(result, expected + ["absent-test"])["pass"])
        self.assertTrue((self.root / "junit.xml").is_file())

    def test_real_failure_does_not_become_a_successful_verification(self):
        result, expected = self.pytest("def test_rejected():\n    assert False, 'independent control failure'\n")
        self.assertFalse(runner.evaluate_reports(result, expected)["pass"])
        self.assertNotEqual(0, result["exit_code"])

    def test_real_skip_is_non_promotable(self):
        result, expected = self.pytest("import pytest\ndef test_skipped():\n    pytest.skip('intentional skip control')\n")
        status = runner.evaluate_reports(result, expected)
        self.assertFalse(status["pass"])
        self.assertGreater(status["skipped_reports"], 0)

    def test_timeout_identifies_node_and_stops_its_actual_descendant(self):
        ready = self.root / "child-ready.txt"
        leaked = self.root / "child-survived.txt"
        child = "import time; from pathlib import Path; Path(" + repr(str(ready)) + ").write_text('ready'); time.sleep(5); Path(" + repr(str(leaked)) + ").write_text('leaked')"
        body = "import subprocess,sys,time\ndef test_hang():\n    subprocess.Popen([sys.executable, '-c', " + repr(child) + "])\n    time.sleep(100)\n"
        result, expected = self.pytest(body, timeout=2)
        self.assertTrue(ready.exists(), "the actual descendant must have started")
        self.assertEqual("test-timeout", result["reason"])
        self.assertIn("test_hang", result["active_nodeid"])
        self.assertFalse(runner.evaluate_reports(result, expected)["pass"])
        self.assertTrue((self.root / "run/process-result.json").is_file())
        time.sleep(3.5)
        self.assertFalse(leaked.exists(), "owned descendant survived timeout cleanup")
        self.assertFalse((self.root / "junit.xml").exists(), "interruption must not fabricate native JUnit")


if __name__ == "__main__":
    unittest.main()
