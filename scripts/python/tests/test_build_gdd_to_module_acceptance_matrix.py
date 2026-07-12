#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = (
    REPO_ROOT
    / "execution-plans"
    / "2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening"
    / "schemas"
    / "implementation-acceptance-matrix.v1.json"
)
BUILDER = REPO_ROOT / "scripts" / "python" / "build_gdd_to_module_acceptance_matrix.py"
ALLOWED_STATUSES = {
    "verified",
    "partial",
    "missing",
    "not_applicable",
    "explicitly_deferred",
    "blocked",
}


class GddToModuleAcceptanceMatrixTests(unittest.TestCase):
    def test_committed_matrix_is_current_and_valid(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BUILDER), "--repository-root", str(REPO_ROOT), "--check-only"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('"check_count": 826', result.stdout)

    def test_matrix_uses_only_strict_statuses_and_unique_ids(self) -> None:
        document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        rows = document["checks"]

        self.assertEqual(826, len(rows))
        self.assertEqual(len(rows), len({row["check_id"] for row in rows}))
        self.assertLessEqual({row["status"] for row in rows}, ALLOWED_STATUSES)
        self.assertNotIn("looks_complete", {row["status"] for row in rows})
        self.assertNotIn("mostly_complete", {row["status"] for row in rows})

    def test_matrix_exposes_current_phase_and_capability_gaps(self) -> None:
        rows = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))["checks"]
        by_id = {row["check_id"]: row for row in rows}

        self.assertEqual("partial", by_id["GTM-AC-P0A-001"]["status"])
        self.assertIn("check_id", by_id["GTM-AC-P0A-001"]["gap"])
        self.assertEqual("blocked", by_id["GTM-AC-P0B-001"]["status"])
        self.assertEqual("blocked", by_id["GTM-AC-P3-010"]["status"])
        self.assertEqual("blocked", by_id["GTM-AC-P4-001"]["status"])
        self.assertEqual(
            "blocked",
            by_id["GTM-AC-CAP-GODOT-INTERACTION-REGION-GATE"]["status"],
        )
        self.assertIn(
            "closure ledger",
            by_id["GTM-AC-CAP-GODOT-INTERACTION-REGION-GATE"]["gap"],
        )
        self.assertEqual("partial", by_id["GTM-SAR-DOD-LAYERING"]["status"])

    def test_matrix_does_not_infer_verified_from_broad_phase_evidence(self) -> None:
        rows = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))["checks"]

        self.assertFalse([row for row in rows if row["status"] == "verified"])
        self.assertTrue(all(row["status"] == "partial" for row in rows if row["phase"] == "Phase 0A"))
        self.assertTrue(all(row["status"] == "blocked" for row in rows if row["phase"] != "Phase 0A"))


if __name__ == "__main__":
    unittest.main()
