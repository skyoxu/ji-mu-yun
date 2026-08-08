import importlib.util
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


PLAN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLAN_DIR))
SPEC = importlib.util.spec_from_file_location("validate_implementation", PLAN_DIR / "validate_implementation.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ValidateImplementationTests(unittest.TestCase):
    def test_terminal_validation_requires_explicit_maintainer_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = Path(temp)
            (plan / "plan-state.v1.json").write_text(json.dumps({"state": "plan-ready", "state_owner": "vdd-execution-plan"}), encoding="utf-8")
            self.assertEqual(["implementation-authorization-required:plan-ready"], MODULE.check_lifecycle_entry(plan))

    def test_terminal_validation_accepts_implementation_authorized(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = Path(temp)
            (plan / "plan-state.v1.json").write_text(json.dumps({"state": "implementation-authorized", "state_owner": "maintainer"}), encoding="utf-8")
            self.assertEqual([], MODULE.check_lifecycle_entry(plan))

    def test_terminal_result_is_not_acceptance_authority(self):
        result = MODULE.result(["slice-evidence-missing:BROH-S0"])
        self.assertEqual("implementation-complete", result["predicate"])
        self.assertEqual("v6", result["terminalPredicateVersion"])
        self.assertIsInstance(result["terminalPredicateVersion"], str)
        self.assertEqual("BROH-S7", result["slice_id"])
        self.assertEqual(MODULE._contract_hash(), result["contract_hash"])
        self.assertEqual([], result["authorizes"])
        self.assertIn("acceptance-passed", result["does_not_authorize"])
        for key, value in result["validation_snapshot"].items():
            self.assertEqual(value, result[key])

    def test_contract_and_fixture_checks_are_deterministic(self):
        self.assertEqual([], MODULE.check_contract_consistency())
        self.assertEqual([], MODULE.check_composition_fixtures())

    def test_composition_fixtures_require_declared_cross_skill_cases(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = Path(temp)
            fixtures = plan / "fixtures"
            fixtures.mkdir()
            (fixtures / "operability-cases.v1.json").write_text(
                json.dumps({
                    "cases": [{"case_id": "pre-review-skipped-maintainer-authorized", "authorizes": []}],
                    "authorizes": [],
                }),
                encoding="utf-8",
            )
            with mock.patch.object(MODULE, "PLAN_DIR", plan):
                errors = MODULE.check_composition_fixtures()
            self.assertIn(
                "composition-fixture-case-missing:discovery-wave-partial-transport-failure",
                errors,
            )

    def test_missing_stage_artifacts_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "RUN-TEST"
            run_dir.mkdir()
            errors = MODULE._validate_run(run_dir, "BROH-S0", MODULE._contract_hash())
            self.assertIn("slice-artifact-missing:BROH-S0:red-result.json", errors)
            self.assertIn("slice-artifact-missing:BROH-S0:attempt-ledger-manifest.v1.json", errors)

    def test_tampered_stage_documents_fail_binding_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "RUN-TEST"
            run_dir.mkdir()
            for name in (
                "red-result.json", "green-result.json", "refactor-result.json",
                "stage-evidence-projection.v1.json", "recovery-state.json",
                "attempt-ledger-manifest.v1.json", "baseline-file-manifest.v1.json",
                "slice-ready-result.json",
            ):
                (run_dir / name).write_text("{}", encoding="utf-8")
            (run_dir / "run-events.jsonl").write_text("{}\n", encoding="utf-8")
            errors = MODULE._validate_run(run_dir, "BROH-S0", MODULE._contract_hash())
            self.assertIn("slice-stage-binding-invalid:BROH-S0:red", errors)
            self.assertIn("slice-attempt-ledger-invalid:BROH-S0", errors)

    def test_terminal_consumer_closure_is_explicit(self):
        self.assertEqual(
            {
                "skill-tests",
                "acceptance-review-requirement-tests",
                "acceptance-bootstrap-integration-tests",
                "plan-validator-tests",
            },
            set(MODULE.TERMINAL_COMMAND_IDS),
        )

    def test_terminal_rejects_incomplete_consumer_closure(self):
        self.assertEqual("v6", MODULE.result([])["terminalPredicateVersion"])
        with mock.patch.object(MODULE, "TERMINAL_COMMAND_IDS", ["skill-tests"]):
            self.assertEqual(
                [
                    "terminal-consumer-closure-missing:acceptance-bootstrap-integration-tests",
                    "terminal-consumer-closure-missing:acceptance-review-requirement-tests",
                    "terminal-consumer-closure-missing:plan-validator-tests",
                ],
                MODULE.check_terminal_consumer_closure(),
            )
        with tempfile.TemporaryDirectory() as temp:
            plan = Path(temp)
            fixtures = plan / "fixtures"
            fixtures.mkdir()
            (fixtures / "operability-cases.v1.json").write_text(
                json.dumps({
                    "cases": [{"case_id": "pre-review-skipped-maintainer-authorized", "authorizes": []}],
                    "authorizes": [],
                }),
                encoding="utf-8",
            )
            with mock.patch.object(MODULE, "PLAN_DIR", plan):
                errors = MODULE.check_composition_fixtures()
            self.assertIn(
                "composition-fixture-case-missing:discovery-wave-partial-transport-failure",
                errors,
            )

    def test_terminal_requires_current_s7_stage_evidence(self):
        self.assertEqual(
            ["terminal-slice-evidence-missing:BROH-S7"],
            MODULE.check_terminal_slice_evidence(None),
        )
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(
                ["terminal-slice-run-outside-evidence-root:BROH-S7"],
                MODULE.check_terminal_slice_evidence(Path(temp)),
            )


if __name__ == "__main__":
    unittest.main()
