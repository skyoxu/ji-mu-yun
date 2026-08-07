from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate_plan.py"
SPEC = importlib.util.spec_from_file_location("quick_dev_repair_plan_validator", SCRIPT)
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
            {"slice_id": "RMAP-S0", "depends_on": ["RMAP-S2"]},
            {"slice_id": "RMAP-S1", "depends_on": ["RMAP-S0"]},
            {"slice_id": "RMAP-S2", "depends_on": ["RMAP-S1"]},
        ]
        errors: list[str] = []
        MODULE.check_dependency_graph(slices, errors)
        self.assertTrue(any(item.startswith("slice-cycle:") for item in errors))

    def test_protocol_fixture_set_is_complete(self) -> None:
        fixtures = MODULE.load_json(
            MODULE.PLAN_DIR / "fixtures/regression-repair-contract-cases.v1.json", []
        )
        self.assertEqual(
            MODULE.REQUIRED_CASES,
            {item["case_id"] for item in fixtures["cases"]},
        )

    def test_existing_test_files_are_selected(self) -> None:
        contract = MODULE.load_json(MODULE.PLAN_DIR / "implementation-contract.v1.json", [])
        for slice_item in contract["slices"]:
            for relative in slice_item["allowed_changes"]["tests"]:
                self.assertTrue((MODULE.REPO_ROOT / relative).is_file(), relative)

    def test_plan_delivery_consumer_is_read_only(self) -> None:
        contract = MODULE.load_json(MODULE.PLAN_DIR / "implementation-contract.v1.json", [])
        for slice_item in contract["slices"]:
            self.assertIn(
                "execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/**",
                slice_item["forbidden_changes"],
            )


if __name__ == "__main__":
    unittest.main()
