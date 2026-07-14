#!/usr/bin/env python3
from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = (
    REPO_ROOT
    / "execution-plans"
    / "2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening"
    / "schemas"
    / "implementation-acceptance-matrix.v1.json"
)
MATRIX_MARKDOWN_PATH = MATRIX_PATH.parents[1] / "100-implementation-acceptance-matrix.md"
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
VALID_PHASE6_CLOSURE_TEST = (
    "PhaseA.Platform.Tests/Workflow/GddToModuleImplementationPhasesTests.cs::"
    "ImportGddFormDeferral_Phase6ClosureGuard_ShouldRemainFailClosed"
)


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
        self.assertTrue(BUILDER_MODULE.phase0a_exit_satisfied(rows))
        deferred = next(row for row in rows if row["status"] == "explicitly_deferred")
        self.assertEqual("P2", deferred["deferral"]["severity"])
        self.assertTrue(deferred["deferral"]["affected_routes"])
        self.assertTrue(deferred["deferral"]["current_scope_non_impact_proof"])
        self.assertIn("Phase6ClosureGuard", deferred["deferral"]["phase6_closure_test"])
        self.assertFalse(
            any(
                "Phase 0A has not" in row["gap"] or "unverified Phase 0A" in row["gap"]
                for row in rows
                if row["phase"] != "Phase 0A"
            )
        )

    def test_phase0a_permitted_deferral_satisfies_only_the_predecessor_gate(self) -> None:
        rows = [
            {
                "check_id": "P0A-VERIFIED",
                "phase": "Phase 0A",
                "status": "verified",
                "owner": "backend",
                "evidence_refs": ["logs/verified.json"],
                "gap": "",
            },
            {
                "check_id": "P0A-DEFERRED",
                "phase": "Phase 0A",
                "status": "explicitly_deferred",
                "owner": "frontend",
                "evidence_refs": ["logs/deferred.json"],
                "gap": "owner=frontend; recheck=before activation",
                "deferral": {
                    "owner": "frontend",
                    "affected_routes": ["import_gdd_form"],
                    "severity": "P2",
                    "expires_utc": "",
                    "recheck_trigger": "before activation",
                    "current_scope_non_impact_proof": "non-action only",
                    "phase6_closure_test": VALID_PHASE6_CLOSURE_TEST,
                },
            },
            {
                "check_id": "P0B-OWN-EVIDENCE-MISSING",
                "phase": "Phase 0B",
                "status": "blocked",
                "owner": "standards",
                "evidence_refs": [],
                "gap": "No current reviewed check-ID evidence accepts this requirement.",
            },
        ]

        projected = BUILDER_MODULE.apply_phase0a_predecessor_gate(rows)

        self.assertTrue(BUILDER_MODULE.phase0a_exit_satisfied(projected))
        self.assertEqual("explicitly_deferred", projected[1]["status"])
        self.assertEqual("blocked", projected[2]["status"])
        self.assertEqual(
            "No current reviewed check-ID evidence accepts this requirement.",
            projected[2]["gap"],
        )

    def test_incomplete_phase0a_deferral_fails_closed(self) -> None:
        valid_deferral = {
            "check_id": "P0A-DEFERRED",
            "phase": "Phase 0A",
            "status": "explicitly_deferred",
            "owner": "frontend",
            "evidence_refs": ["logs/deferred.json"],
            "gap": "owner=frontend; recheck=before activation",
            "deferral": {
                "owner": "frontend",
                "affected_routes": ["import_gdd_form"],
                "severity": "P2",
                "expires_utc": "",
                "recheck_trigger": "before activation",
                "current_scope_non_impact_proof": "non-action only",
                "phase6_closure_test": VALID_PHASE6_CLOSURE_TEST,
            },
        }
        later = {
            "check_id": "P1-CLAUSE",
            "phase": "Phase 1",
            "status": "verified",
            "owner": "backend",
            "evidence_refs": ["logs/phase1.json"],
            "gap": "",
        }

        for field, invalid_value in (("owner", ""), ("evidence_refs", []), ("gap", "owner=frontend")):
            with self.subTest(field=field):
                deferral = dict(valid_deferral)
                deferral[field] = invalid_value
                projected = BUILDER_MODULE.apply_phase0a_predecessor_gate([deferral, dict(later)])
                self.assertFalse(BUILDER_MODULE.phase0a_exit_satisfied(projected))
                self.assertEqual("blocked", projected[1]["status"])
                self.assertIn("Phase 0A has not satisfied", projected[1]["gap"])

        for field, invalid_value in (
            ("affected_routes", []),
            ("severity", ""),
            ("recheck_trigger", ""),
            ("current_scope_non_impact_proof", ""),
            ("phase6_closure_test", ""),
        ):
            with self.subTest(deferral_field=field):
                deferral = dict(valid_deferral)
                deferral["deferral"] = dict(valid_deferral["deferral"])
                deferral["deferral"][field] = invalid_value
                projected = BUILDER_MODULE.apply_phase0a_predecessor_gate([deferral, dict(later)])
                self.assertFalse(BUILDER_MODULE.phase0a_exit_satisfied(projected))
                self.assertEqual("blocked", projected[1]["status"])

    def test_deferral_contract_rejects_malformed_routes_recheck_and_closure_test(self) -> None:
        row = {
            "phase": "Phase 0A",
            "status": "explicitly_deferred",
            "owner": "frontend",
            "evidence_refs": ["logs/deferred.json"],
            "gap": "owner=frontend; recheck=before activation",
            "deferral": {
                "owner": "frontend",
                "affected_routes": ["import_gdd_form"],
                "severity": "P2",
                "expires_utc": "",
                "recheck_trigger": "before activation",
                "current_scope_non_impact_proof": "non-action only",
                "phase6_closure_test": VALID_PHASE6_CLOSURE_TEST,
            },
        }
        now = datetime(2026, 7, 13, tzinfo=timezone.utc)
        self.assertTrue(BUILDER_MODULE.is_exit_permitted_deferral(row, REPO_ROOT, now))

        mutations = [
            ("affected_routes", ["import_gdd_form", " "]),
            ("affected_routes", "import_gdd_form"),
            ("recheck_trigger", "   "),
            ("phase6_closure_test", "missing.cs::MissingTest"),
            (
                "phase6_closure_test",
                "PhaseA.Platform.Tests/Workflow/GddToModuleImplementationPhasesTests.cs::MissingTest",
            ),
        ]
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                candidate = dict(row)
                candidate["deferral"] = dict(row["deferral"])
                candidate["deferral"][field] = value
                self.assertFalse(BUILDER_MODULE.is_exit_permitted_deferral(candidate, REPO_ROOT, now))

        expired = dict(row)
        expired["deferral"] = dict(row["deferral"])
        expired["deferral"]["recheck_trigger"] = ""
        expired["deferral"]["expires_utc"] = "2026-07-12T00:00:00Z"
        self.assertFalse(BUILDER_MODULE.is_exit_permitted_deferral(expired, REPO_ROOT, now))

        future = dict(row)
        future["deferral"] = dict(row["deferral"])
        future["deferral"]["recheck_trigger"] = ""
        future["deferral"]["expires_utc"] = "2026-07-14T00:00:00Z"
        self.assertTrue(BUILDER_MODULE.is_exit_permitted_deferral(future, REPO_ROOT, now))

    def test_matrix_binds_commit_readiness_as_a_separate_phase0a_gate(self) -> None:
        document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        gate = document["phase0a_predecessor_gate"]
        commit_gate = gate["additional_required_checks"][0]

        self.assertFalse(gate["matrix_row_dispositions_alone_are_sufficient"])
        self.assertEqual("GTM-GATE-P0A-COMMIT-READINESS", commit_gate["check_id"])
        self.assertEqual("passed", commit_gate["required_result"])
        self.assertEqual("passed", gate["row_disposition_status"])
        self.assertEqual("post_generation_external_result", gate["evaluation_mode"])
        self.assertEqual(["failed", "not_evaluated", "passed", "stale"], gate["effective_commit_readiness_status_values"])
        self.assertEqual("not_evaluated", gate["commit_readiness_status"])
        self.assertEqual("blocked", gate["complete_predecessor_status"])
        self.assertFalse(gate["phase1_authorized"])
        self.assertEqual("not_evaluated", commit_gate["evaluation"]["status"])
        self.assertEqual("post_generation_result_required", commit_gate["evaluation"]["reason_code"])
        self.assertFalse(commit_gate["evaluation"]["evidence_refs"])
        self.assertIn("<run_id>", commit_gate["effective_result_authority"])
        self.assertEqual(4, len(commit_gate["required_result_bindings"]))
        self.assertTrue(any(ref.endswith("00-index.md:26") for ref in commit_gate["source_refs"]))
        self.assertTrue(any(ref.endswith("10-recommended-first-slice.md:9") for ref in commit_gate["source_refs"]))
        self.assertTrue(any("COMMIT-PROPOSED-SET-COMPLETE" in ref for ref in commit_gate["validator_refs"]))

        markdown = MATRIX_MARKDOWN_PATH.read_text(encoding="utf-8")
        self.assertIn("## Phase 0A Predecessor Gate", markdown)
        self.assertIn("Evaluation mode: `post_generation_external_result`", markdown)
        self.assertIn("Row-disposition gate: `passed`", markdown)
        self.assertIn("Commit-readiness gate: `not_evaluated`", markdown)
        self.assertIn("Complete predecessor gate: `blocked`", markdown)
        self.assertIn("Phase 1 authorized: `false`", markdown)
        self.assertIn("External result authority:", markdown)
        self.assertIn("implementation_acceptance_matrix_sha256", markdown)

    def test_embedded_commit_readiness_contract_rejects_mutations(self) -> None:
        evaluation = json.loads(EVIDENCE_INDEX_PATH.read_text(encoding="utf-8"))[
            "phase0a_commit_readiness_evaluation"
        ]
        BUILDER_MODULE.validate_commit_readiness_evaluation(REPO_ROOT, evaluation)

        mutations = [
            ("status", "failed", "must remain not_evaluated"),
            ("required_result_bindings", evaluation["required_result_bindings"][:-1], "exactly match"),
            ("required_result_bindings", evaluation["required_result_bindings"] + ["extra"], "exactly match"),
            ("result_path_pattern", "", "must be non-empty"),
            ("result_path_pattern", "logs/result.json", "contain <run_id>"),
        ]
        for field, value, message in mutations:
            with self.subTest(field=field, value=value):
                candidate = dict(evaluation)
                candidate[field] = value
                with self.assertRaisesRegex(SystemExit, message):
                    BUILDER_MODULE.validate_commit_readiness_evaluation(REPO_ROOT, candidate)

    def test_recommended_sidecar_schemas_declare_status_dimensions_and_subsets(self) -> None:
        text = (
            REPO_ROOT
            / "execution-plans"
            / "2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening"
            / "02a-route-state-artifacts.md"
        ).read_text(encoding="utf-8")

        for schema_version in ("gdd-requirements.v1", "scene-route.v1", "ui-wiring-closure.v1"):
            with self.subTest(schema_version=schema_version):
                start = text.index(f'"schema_version": "{schema_version}"')
                end = text.index("```", start)
                block = text[start:end]
                self.assertIn('"status_dimension":', block)
                self.assertIn('"status_allowed_values":', block)

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
