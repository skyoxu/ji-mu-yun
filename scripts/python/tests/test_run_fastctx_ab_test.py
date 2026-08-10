import sys
import unittest
from pathlib import Path


PYTHON_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYTHON_ROOT))

from run_fastctx_ab_test import run  # noqa: E402
from validate_fastctx_ab_test import validate  # noqa: E402


class FastCtxAbTestTests(unittest.TestCase):
    def test_controlled_benchmark_is_bounded_and_redacted(self):
        evidence = run(5)
        validate(evidence)
        self.assertLessEqual(evidence["high_output_summary"]["summary_bytes"], 12000)
        self.assertTrue(evidence["high_output_summary"]["redaction_verified"])
        self.assertNotIn("content", str(evidence["fastctx_contract"]["operations"]))
        baseline = evidence["baseline"]["read_estimated_tokens"]
        delta = evidence["delta"]["estimated_tokens"]
        self.assertLessEqual(delta / baseline, 0.10)

    def test_rejects_non_acceptance_iteration_count(self):
        with self.assertRaises(ValueError):
            run(4)


if __name__ == "__main__":
    unittest.main()
