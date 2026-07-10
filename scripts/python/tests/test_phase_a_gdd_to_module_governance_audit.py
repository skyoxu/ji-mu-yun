#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = REPO_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import phase_a_gdd_to_module_governance_audit as audit  # noqa: E402


class PhaseAGddToModuleGovernanceAuditTests(unittest.TestCase):
    def test_fixture_audit_passes_for_repository(self) -> None:
        failures: list[str] = []

        summary = audit.audit_fixtures(REPO_ROOT, failures)

        self.assertEqual([], failures)
        self.assertGreaterEqual(summary["action_count"], 17)
        self.assertGreaterEqual(summary["contract_count"], 13)

    def test_metadata_audit_requires_governance_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "metadata.sqlite3"
            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE project_admin_review_queue (id TEXT)")
            connection.commit()
            connection.close()

            failures: list[str] = []
            summary = audit.audit_metadata_db(db, failures)

        self.assertEqual("checked", summary["status"])
        self.assertIn("metadata_table_missing:project_diagnostic_spool", failures)
        self.assertIn("metadata_table_missing:project_delete_tombstones", failures)
        self.assertIn("metadata_table_missing:game_type_maintenance_records", failures)

    def test_secret_marker_scan_detects_secret_names(self) -> None:
        violations = audit.find_secret_markers("PHASEA_ADMIN_TOKEN=secret Authorization: Bearer abc")

        self.assertIn("secret_marker:PHASEA_ADMIN_TOKEN", violations)
        self.assertIn("secret_marker:Authorization", violations)
        self.assertIn("secret_marker:Bearer", violations)


if __name__ == "__main__":
    unittest.main()
