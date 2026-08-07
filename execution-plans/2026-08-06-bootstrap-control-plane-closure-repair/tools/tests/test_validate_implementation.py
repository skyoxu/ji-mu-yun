from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate_implementation.py"
SPEC = importlib.util.spec_from_file_location("implementation_validator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ImplementationValidatorTests(unittest.TestCase):
    def test_plan_ready_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plan = Path(temp)
            (plan / "plan-state.v1.json").write_text(
                json.dumps({"state": "plan-ready"}), encoding="utf-8"
            )
            self.assertEqual([], MODULE.validate(plan))

    def test_non_plan_ready_state_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plan = Path(temp)
            (plan / "plan-state.v1.json").write_text(
                json.dumps({"state": "implementation-authorized"}), encoding="utf-8"
            )
            self.assertEqual(["implementation-requires-plan-ready"], MODULE.validate(plan))

    def test_cli_returns_nonzero_for_invalid_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plan = Path(temp)
            (plan / "plan-state.v1.json").write_text(
                json.dumps({"state": "implementation-authorized"}), encoding="utf-8"
            )
            tools_dir = plan / "tools"
            tools_dir.mkdir()
            script_copy = tools_dir / "validate_implementation.py"
            script_copy.write_bytes(SCRIPT.read_bytes())
            result = subprocess.run([sys.executable, str(script_copy)], capture_output=True)
            self.assertNotEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
