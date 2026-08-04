from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PLAN_ROOT = Path(__file__).resolve().parents[2]
TOOLS = PLAN_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import validate_all  # noqa: E402


class ValidationResultGuardTests(unittest.TestCase):
    def test_runtime_type_projection_binds_its_current_negative_test(self) -> None:
        authority = json.loads(
            (PLAN_ROOT / "schemas" / "artifact-proof-authority.v1.json").read_text(
                encoding="utf-8"
            )
        )
        runtime_type = next(
            item
            for item in authority["runtime_types"]
            if item["type_id"] == "validation-result-instance"
        )
        negative_test = (
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/"
            "tools/tests/test_validation_result_guards.py"
        )
        self.assertEqual(
            negative_test,
            runtime_type["independent_recomputation"]["negative_test"],
        )
        self.assertIn(negative_test, runtime_type["staleness_propagation"]["inputs"])
        recovery = runtime_type["recovery_supersession"]
        self.assertEqual(
            "initial-explicit-null-or-successor-recomputed-envelope",
            recovery["predecessor_policy"],
        )
        self.assertEqual(
            ["INITIAL_RUN_NO_PREDECESSOR", "SUPERSEDES_PRIOR_RESULT"],
            recovery["reason_codes"],
        )

    def test_result_lineage_is_recomputed_from_the_predecessor_envelope(self) -> None:
        current = validate_all.validation_snapshot()
        initial = validate_all.build_result(
            "plan-repair-verified", [], [], current, current
        )
        self.assertEqual("initial", initial["lineage_mode"])
        self.assertEqual("INITIAL_RUN_NO_PREDECESSOR", initial["lineage_reason_code"])
        forged = copy.deepcopy(initial)
        forged.update(
            lineage_mode="successor",
            lineage_reason_code="SUPERSEDES_PRIOR_RESULT",
            predecessor_run_id="invented-run",
            supersedes_run_id="invented-run",
            predecessor_result_hash="sha256:" + "7" * 64,
        )
        self.assertEqual(
            {"RMAP-RESULT-LINEAGE"},
            {
                item["rule_id"]
                for item in validate_all.validate_authorizing_result(forged, current)
            },
        )
        successor = validate_all.build_result(
            "plan-repair-verified", [], [], current, current,
            predecessor_result=initial,
        )
        self.assertEqual(
            [],
            validate_all.validate_authorizing_result(
                successor, current, predecessor_result=initial
            ),
        )
        self.assertEqual(initial["run_id"], successor["predecessor_run_id"])
        self.assertEqual(initial["run_id"], successor["supersedes_run_id"])

    def test_validation_drift_prevents_repair_pass(self) -> None:
        before = {
            "candidate_hash": "sha256:" + "1" * 64,
            "source_hash": "sha256:" + "2" * 64,
            "validator_version": "validator-a-sha256:" + "3" * 64,
            "predicate_input_root": "sha256:" + "1" * 64,
            "closure_definition_hash": "sha256:" + "4" * 64,
            "authority_root": "sha256:" + "5" * 64,
            "validator_root": "sha256:" + "3" * 64,
        }
        after = {
            **before,
            "candidate_hash": "sha256:" + "6" * 64,
            "predicate_input_root": "sha256:" + "6" * 64,
        }
        unit_check = {
            "rule_id": "RMAP-UNIT-TESTS",
            "status": "pass",
            "evidence": ["mocked"],
        }
        with patch(
            "validate_all.validation_snapshot", side_effect=[before, after]
        ), patch("validate_all.validate_fixture_suite", return_value=[]), patch(
            "validate_all.validate_candidate_fixture_suite", return_value=[]
        ), patch("validate_all.run_unit_tests", return_value=(unit_check, [])):
            result, exit_code = validate_all.run_predicate("plan-repair-verified")
        self.assertEqual(1, exit_code)
        self.assertEqual("fail", result["status"])
        self.assertIn(
            "RMAP-HASH-VALIDATION-DRIFT",
            {item["rule_id"] for item in result["diagnostics"]},
        )

    def test_authorizing_result_binds_complete_freshness_roots(self) -> None:
        unit_check = {
            "rule_id": "RMAP-UNIT-TESTS",
            "status": "pass",
            "evidence": ["mocked"],
        }
        with patch("validate_all.validate_fixture_suite", return_value=[]), patch(
            "validate_all.validate_candidate_fixture_suite", return_value=[]
        ), patch("validate_all.run_unit_tests", return_value=(unit_check, [])):
            result, exit_code = validate_all.run_predicate("plan-repair-verified")
        self.assertEqual(0, exit_code)
        required = {
            "predicate_input_root",
            "closure_definition_hash",
            "authority_root",
            "validator_root",
            "runtime_evidence_root",
            "lineage_mode",
            "lineage_reason_code",
            "predecessor_run_id",
            "supersedes_run_id",
            "predecessor_result_hash",
        }
        self.assertLessEqual(required, set(result))
        self.assertEqual(
            [],
            validate_all.validate_authorizing_result(
                result, validate_all.validation_snapshot()
            ),
        )
        stale = copy.deepcopy(result)
        stale["predicate_input_root"] = "sha256:" + "0" * 64
        self.assertEqual(
            {"RMAP-RESULT-STALE"},
            {
                item["rule_id"]
                for item in validate_all.validate_authorizing_result(
                    stale, validate_all.validation_snapshot()
                )
            },
        )


if __name__ == "__main__":
    unittest.main()
