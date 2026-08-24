from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TerminalFullIsolationTests(unittest.TestCase):
    def test_acceptance_terminal_rejects_out_path_without_creating_file(self) -> None:
        runner = Path(__file__).resolve().parents[4] / "execution-plans" / "2026-08-17-acceptance-coordinator-efficiency" / "tools" / "terminal_full.py"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "terminal-results" / "unexpected.json"
            result = subprocess.run([sys.executable, "-B", str(runner), "--out", str(output)], capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("unrecognized arguments", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
