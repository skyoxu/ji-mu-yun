from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate_implementation.py"
SPEC = importlib.util.spec_from_file_location("quick_dev_repair_implementation_validator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ImplementationValidatorTests(unittest.TestCase):
    def test_terminal_validation_requires_implementation_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plan = Path(temp)
            (plan / "plan-state.v1.json").write_text(
                json.dumps({"state": "plan-ready", "state_owner": "vdd-execution-plan"}),
                encoding="utf-8",
            )
            self.assertEqual(
                ["implementation-authorization-required:plan-ready"],
                MODULE.check_lifecycle_entry(plan),
            )

    def test_maintainer_authorization_is_valid_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plan = Path(temp)
            (plan / "plan-state.v1.json").write_text(
                json.dumps({"state": "implementation-authorized", "state_owner": "maintainer", "authorizes": ["implementation-authorized"]}),
                encoding="utf-8",
            )
            self.assertEqual([], MODULE.check_lifecycle_entry(plan))

    def test_slice_order_is_stable(self) -> None:
        self.assertEqual(["RMAP-S0", "RMAP-S1", "RMAP-S2"], MODULE.SLICE_ORDER)

    def test_preimplementation_s0_is_a_controlled_red(self) -> None:
        errors = MODULE.check_required_files("RMAP-S0")
        schema = MODULE.REPO_ROOT / ".agents/skills/quick-dev-tdd-adapter/schemas/regression-repair-contract.v1.schema.json"
        if schema.exists():
            self.assertIsInstance(errors, list)
        else:
            self.assertIn(
                "missing:.agents/skills/quick-dev-tdd-adapter/schemas/regression-repair-contract.v1.schema.json",
                errors,
            )

    def test_protected_phase_paths_are_not_implementation_outputs(self) -> None:
        for paths in MODULE.SLICE_FILES.values():
            self.assertFalse(any(path.startswith("PhaseA.Platform/") for path in paths))
            self.assertFalse(any(path.startswith("runtime/phase-a/") for path in paths))


if __name__ == "__main__":
    unittest.main()
