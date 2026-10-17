"""Native transport ownership and syntax reuse checks (Accepted ADR-0058)."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sc import skill_replay_runtime as runtime


class NativeProcessOwnershipTests(unittest.TestCase):
    def test_normal_leader_exit_drains_descendants_before_stdio_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ready, leaked = root / "ready", root / "leaked"
            child = "import time;from pathlib import Path;Path(" + repr(str(ready)) + ").write_text('ready');time.sleep(2);Path(" + repr(str(leaked)) + ").write_text('leaked')"
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if runtime.os.name == "nt" else 0
            parent = ("import subprocess,sys,time;from pathlib import Path;subprocess.Popen([sys.executable,'-c'," + repr(child)
                      + "],creationflags=" + str(flags) + ");\nwhile not Path(" + repr(str(ready)) + ").exists(): time.sleep(.01)\n")
            result = runtime.capture_process([sys.executable, "-c", parent], root, timeout=5)
            self.assertEqual(0, result.returncode)
            self.assertTrue(ready.exists(), "the real descendant must hold the inherited stdio files")
            time.sleep(2.2)
            self.assertFalse(leaked.exists(), "the dead leader left its descendant alive")

    def test_native_diagnostic_records_real_pid_and_timeout_without_relabeling_it(self):
        import json
        import os
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "native"
            trace.mkdir()
            with patch.dict(os.environ, {"TC_D1_NATIVE_TRACE_DIR": str(trace)}):
                with self.assertRaises(subprocess.TimeoutExpired):
                    runtime.capture_process([sys.executable, "-c", "import time;time.sleep(10)"], root, .2)
            rows = [json.loads(line) for path in trace.glob("*.jsonl") for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(["started", "unsuccessful"], [row["phase"] for row in rows])
            self.assertEqual(rows[0]["pid"], rows[1]["pid"])
            self.assertNotEqual(os.getpid(), rows[0]["pid"])
            self.assertEqual("TimeoutExpired", rows[1]["exception"])
            self.assertTrue(all(row["authorizes"] == [] for row in rows))

    def test_native_timeout_reaps_a_descendant_in_a_separate_process_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ready, leaked = root / "ready", root / "leaked"
            child = "import time;from pathlib import Path;Path(" + repr(str(ready)) + ").write_text('ready');time.sleep(2);Path(" + repr(str(leaked)) + ").write_text('leaked')"
            parent = "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c'," + repr(child) + "],start_new_session=True);time.sleep(30)"
            with self.assertRaisesRegex(ValueError, "timed out"):
                runtime.execute([sys.executable, "-c", parent], root, timeout=0.5)
            self.assertTrue(ready.exists(), "the real descendant must have started")
            time.sleep(2.2)
            self.assertFalse(leaked.exists(), "native timeout left its actual descendant alive")

    def test_output_exhaustion_terminates_the_running_process(self):
        with tempfile.TemporaryDirectory() as directory:
            started = time.monotonic()
            program = "import sys,time;sys.stdout.buffer.write(b'x'*8192);sys.stdout.flush();time.sleep(10)"
            with self.assertRaisesRegex(ValueError, "output budget exhausted"):
                runtime.execute([sys.executable, "-c", program], Path(directory), output_limit=1024)
            self.assertLess(time.monotonic() - started, 2, "output exhaustion was only checked after execution")


class SyntaxReuseTests(unittest.TestCase):
    def test_dependency_closure_hashes_the_exact_bytes_used_for_import_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "owner" / "entry.py"
            source.parent.mkdir()
            source.write_text("VALUE = 1\n", encoding="utf-8")
            original = Path.read_bytes
            reads = []

            def read(path):
                if path == source:
                    reads.append(path)
                return original(path)

            with patch.object(Path, "read_bytes", read):
                first = runtime.dependency_closure(root, ("owner",))
            self.assertEqual(1, reads.count(source), "one traversal should bind and hash the same observed bytes")
            source.write_text("VALUE = 2\n", encoding="utf-8")
            second = runtime.dependency_closure(root, ("owner",))
            self.assertNotEqual(first[0]["sha256"], second[0]["sha256"], "a later traversal must reread changed bytes")

    def test_repeated_missing_imports_do_not_probe_each_module_on_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = root / "owner"
            owner.mkdir()
            for index in range(12):
                (owner / (str(index) + ".py")).write_text("import absent_policy\n", encoding="utf-8")
            original = Path.is_file
            probed = []
            original_scan = runtime.os.scandir
            scanned = []

            def probe(path):
                if path.name == "absent_policy.py":
                    probed.append(path)
                return original(path)

            def scan(path):
                if Path(path).name == "absent_policy":
                    scanned.append(path)
                return original_scan(path)

            with patch.object(Path, "is_file", probe), patch.object(runtime.os, "scandir", scan):
                closure = runtime.dependency_closure(root, ("owner",))
            self.assertEqual(12, len(closure))
            self.assertEqual([], probed, "absent names caused repeated native filesystem probes")
            self.assertEqual([], scanned, "known-absent directory names still caused native scans")
            (root / "absent_policy.py").write_text("ALLOW = False\n", encoding="utf-8")
            updated = runtime.dependency_closure(root, ("owner",))
            self.assertIn("absent_policy.py", [row["path"] for row in updated], "a prior absence was reused as current authority")

    def test_identical_bytes_in_two_checkouts_reuse_parse_without_hiding_changes(self):
        original = runtime.ast.parse
        runtime._import_names.cache_clear()
        with patch.object(runtime.ast, "parse", wraps=original) as parser:
            first = runtime._import_names(b"import unique_policy_alpha\n", "checkout-one/entry.py")
            second = runtime._import_names(b"import unique_policy_alpha\n", "checkout-two/entry.py")
            self.assertEqual(frozenset({"unique_policy_alpha"}), first)
            self.assertEqual(first, second)
            self.assertEqual(1, parser.call_count, "directory identity caused repeated parsing of identical bytes")
            changed = runtime._import_names(b"import unique_policy_beta\n", "checkout-two/entry.py")
            self.assertEqual(frozenset({"unique_policy_beta"}), changed)
            self.assertEqual(2, parser.call_count, "changed source bytes must be independently parsed")

    def test_warm_consumer_analysis_still_rejects_a_new_undeclared_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for _, name in runtime.CONSUMERS:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("VALUE = True\n", encoding="utf-8")
            caller = root / "scripts/python/new_caller.py"
            caller.parent.mkdir(parents=True, exist_ok=True)
            caller.write_text("VALUE = False\n", encoding="utf-8")
            baseline = runtime.consumer_manifest(root)
            caller.write_text("from package import validate_package as check\ncheck('current')\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "undeclared real call surfaces"):
                runtime.consumer_manifest(root)
            caller.write_text("VALUE = False\n", encoding="utf-8")
            self.assertEqual(baseline, runtime.consumer_manifest(root))


if __name__ == "__main__":
    unittest.main()
