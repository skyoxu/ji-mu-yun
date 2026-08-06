from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "validate_implementation.py"
SPEC = importlib.util.spec_from_file_location("implementation_validator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ImplementationValidatorTests(unittest.TestCase):
    def test_current_red_reports_missing_skill(self) -> None:
        errors = MODULE.check_required_files("RMAP-S0")
        if MODULE.SKILL_ROOT.exists():
            self.assertIsInstance(errors, list)
        else:
            self.assertIn("missing:.agents/skills/orchestrate-plan-delivery/SKILL.md", errors)

    def test_missing_quick_validate_capability_is_typed(self) -> None:
        with mock.patch.dict(MODULE.os.environ, {"CODEX_HOME": str(Path("Z:/missing-codex"))}):
            self.assertIsNone(MODULE.quick_validate_command())

    def test_slice_order_is_stable(self) -> None:
        self.assertEqual(["RMAP-S0", "RMAP-S1", "RMAP-S2", "RMAP-S3"], MODULE.SLICE_ORDER)


if __name__ == "__main__":
    unittest.main()

