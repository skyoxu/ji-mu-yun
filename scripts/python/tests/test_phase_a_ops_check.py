#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = REPO_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import phase_a_ops_check  # noqa: E402


class PhaseAOpsCheckTests(unittest.TestCase):
    def test_public_smoke_followup_warns_for_remote_https_url(self) -> None:
        result = phase_a_ops_check.check_public_smoke_followup("https://47.86.160.138:8080")

        self.assertEqual(result["name"], "public_smoke_followup")
        self.assertEqual(result["status"], "warn")
        self.assertIn("py -3 scripts/python/phase_a_public_smoke.py", result["message"])
        self.assertIn("--base-url https://47.86.160.138:8080", result["message"])

    def test_public_smoke_followup_allows_local_https_url(self) -> None:
        result = phase_a_ops_check.check_public_smoke_followup("https://localhost")

        self.assertEqual(result["name"], "public_smoke_followup")
        self.assertEqual(result["status"], "ok")

    def test_public_smoke_followup_allows_missing_url(self) -> None:
        result = phase_a_ops_check.check_public_smoke_followup("")

        self.assertEqual(result["name"], "public_smoke_followup")
        self.assertEqual(result["status"], "ok")


if __name__ == "__main__":
    unittest.main()
