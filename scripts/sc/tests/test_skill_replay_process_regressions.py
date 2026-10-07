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
