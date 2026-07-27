from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ria_plan_validator", TOOLS / "validate_plan.py")
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class RefactorAcceptancePlanTests(unittest.TestCase):
    def test_draft_directory_is_structurally_valid(self) -> None:
        self.assertEqual([], validator.validate())

    def test_required_ra_ids_are_unique_and_complete(self) -> None:
        ledger = validator.load("requirements-ledger.v1.json")
        ids = [value for item in ledger["coverage"] for value in item["ra_ids"]]
        self.assertEqual(list(range(1, 74)), sorted(ids))


if __name__ == "__main__":
    unittest.main()
