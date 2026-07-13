#!/usr/bin/env python3
from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
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
EVIDENCE_INDEX_PATH = (
    REPO_ROOT
    / "execution-plans"
    / "2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening"
    / "schemas"
    / "implementation-acceptance-evidence-index.v1.json"
)
ALLOWED_STATUSES = {
    "verified",
    "partial",
    "missing",
    "not_applicable",
    "explicitly_deferred",
    "blocked",
}
SPEC = importlib.util.spec_from_file_location("gdd_matrix_builder", BUILDER)
BUILDER_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(BUILDER_MODULE)


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

        self.assertRegex(document["source_inputs_hash"], r"^[0-9a-f]{64}$")
        self.assertNotIn("source_commit", document)
        self.assertNotIn("worktree_dirty", document)
        self.assertNotIn("source_tree_hash", document)
        self.assertEqual(826, len(rows))
        self.assertEqual(len(rows), len({row["check_id"] for row in rows}))
        self.assertLessEqual({row["status"] for row in rows}, ALLOWED_STATUSES)
        self.assertNotIn("looks_complete", {row["status"] for row in rows})
        self.assertNotIn("mostly_complete", {row["status"] for row in rows})

    def test_matrix_exposes_current_phase_and_capability_gaps(self) -> None:
        rows = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))["checks"]
        by_id = {row["check_id"]: row for row in rows}

        self.assertEqual("verified", by_id["GTM-AC-P0A-001"]["status"])
        self.assertEqual("", by_id["GTM-AC-P0A-001"]["gap"])
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
        self.assertEqual("verified", by_id["GTM-SAR-DOD-LAYERING"]["status"])
        self.assertEqual(
            "explicitly_deferred",
            by_id["GTM-SAR-WORKFLOW-ACTION-IMPORT-GDD-FORM"]["status"],
        )
        self.assertIn(
            "recheck=",
            by_id["GTM-SAR-WORKFLOW-ACTION-IMPORT-GDD-FORM"]["gap"],
        )

    def test_matrix_verification_is_driven_by_explicit_check_id_evidence(self) -> None:
        rows = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))["checks"]
        evidence_entries = json.loads(EVIDENCE_INDEX_PATH.read_text(encoding="utf-8"))["entries"]
        evidence_by_id = {entry["check_id"]: entry for entry in evidence_entries}
        verified_rows = [row for row in rows if row["status"] == "verified"]

        self.assertEqual(207, len(verified_rows))
        self.assertTrue(all(evidence_by_id[row["check_id"]]["status"] == "verified" for row in verified_rows))
        self.assertEqual(
            1,
            len([row for row in rows if row["phase"] == "Phase 0A" and row["status"] == "explicitly_deferred"]),
        )
        self.assertTrue(all(row["status"] == "blocked" for row in rows if row["phase"] != "Phase 0A"))

    def test_evidence_index_rejects_duplicate_check_ids(self) -> None:
        rows = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))["checks"][:1]
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_path = Path(temp_dir) / "evidence.json"
            evidence_path.write_text(
                json.dumps({"entries": [{"check_id": rows[0]["check_id"]}, {"check_id": rows[0]["check_id"]}]}),
                encoding="utf-8",
            )
            original = BUILDER_MODULE.EVIDENCE_INDEX
            BUILDER_MODULE.EVIDENCE_INDEX = evidence_path
            try:
                with self.assertRaisesRegex(SystemExit, "duplicate check IDs"):
                    BUILDER_MODULE.apply_evidence_index(rows)
            finally:
                BUILDER_MODULE.EVIDENCE_INDEX = original

    def test_verified_rows_reject_unimported_external_evidence(self) -> None:
        row = dict(json.loads(MATRIX_PATH.read_text(encoding="utf-8"))["checks"][0])
        row["status"] = "verified"
        row["code_refs"] = ["PhaseA.Platform/Program.cs"]
        row["test_refs"] = ["PhaseA.Platform.Tests/Browser/AdminReviewQueueHttpIntegrationTests.cs"]
        row["evidence_refs"] = ["https://example.invalid/unverifiable"]
        row["gap"] = ""
        with self.assertRaisesRegex(SystemExit, "external evidence refs require imported local evidence"):
            BUILDER_MODULE.validate_rows(REPO_ROOT, [row])


if __name__ == "__main__":
    unittest.main()
