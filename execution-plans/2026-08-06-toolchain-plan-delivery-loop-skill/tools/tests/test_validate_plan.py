from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate_plan.py"
SPEC = importlib.util.spec_from_file_location("plan_validator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PlanValidatorTests(unittest.TestCase):
    def test_current_plan_is_valid(self) -> None:
        self.assertEqual([], MODULE.validate_plan())

    def test_missing_required_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "plan"
            shutil.copytree(MODULE.PLAN_DIR, target)
            (target / "requirements.v1.json").unlink()
            errors = MODULE.validate_plan(
                target,
                MODULE.REPO_ROOT,
                check_index=False,
                check_source_hashes=False,
            )
            self.assertIn("missing-plan-file:requirements.v1.json", errors)

    def test_cycle_is_rejected(self) -> None:
        slices = [
            {"slice_id":"RMAP-S0","depends_on":["RMAP-S3"]},
            {"slice_id":"RMAP-S1","depends_on":["RMAP-S0"]},
            {"slice_id":"RMAP-S2","depends_on":["RMAP-S1"]},
            {"slice_id":"RMAP-S3","depends_on":["RMAP-S2"]},
        ]
        errors: list[str] = []
        MODULE.check_dependency_graph(slices, errors)
        self.assertTrue(any(item.startswith("slice-cycle:") for item in errors))


if __name__ == "__main__":
    unittest.main()

