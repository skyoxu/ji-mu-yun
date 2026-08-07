import importlib.util
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location("plan",Path(__file__).resolve().parents[1]/"validate_plan.py")
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
class PlanTests(unittest.TestCase):
    def test_plan_is_valid(self): self.assertEqual([],module.validate_plan())
    def test_plan_never_authorizes(self):
        import json
        self.assertEqual([],json.loads((module.PLAN_DIR/"requirements.v1.json").read_text()) ["authorizes"])
    def test_reviewer_operability_cases_are_required(self):
        self.assertIn("readonly-repository-access",module.REQUIRED_CASES)
        self.assertIn("exact-evidence-crlf-range",module.REQUIRED_CASES)
        self.assertIn("repeated-stale-evidence-stop-loss",module.REQUIRED_CASES)
if __name__ == "__main__": unittest.main()
