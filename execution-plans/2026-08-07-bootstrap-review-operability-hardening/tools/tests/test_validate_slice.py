import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


PLAN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLAN_DIR))
SPEC = importlib.util.spec_from_file_location("validate_slice", PLAN_DIR / "validate_slice.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ValidateSliceTests(unittest.TestCase):
    def test_slice_predicate_is_structured_and_non_authorizing(self):
        errors = MODULE.validate_slice("BROH-S0", run_tests=False)
        result = MODULE.result("BROH-S0", errors)
        self.assertEqual([], errors)
        self.assertEqual("slice-ready", result["predicate"])
        self.assertEqual([], result["authorizes"])
        self.assertEqual("pass", result["status"])
        self.assertEqual({}, result["predecessor_result_hashes"])
        for key, value in result["validation_snapshot"].items():
            self.assertEqual(value, result[key])

    def test_unknown_slice_fails_closed(self):
        self.assertEqual(["slice-not-terminal-validatable:BROH-S9"], MODULE.validate_slice("BROH-S9", run_tests=False))

    def test_dependent_slice_requires_current_predecessor_evidence(self):
        class MissingPredecessor:
            @staticmethod
            def predecessor_result_hashes(slice_id):
                return {"BROH-S0": "missing"}

        with mock.patch.object(MODULE, "_validation_module", return_value=MissingPredecessor):
            self.assertIn(
                "slice-predecessor-evidence-missing:BROH-S1:BROH-S0",
                MODULE.validate_slice("BROH-S1", run_tests=False),
            )


if __name__ == "__main__":
    unittest.main()
