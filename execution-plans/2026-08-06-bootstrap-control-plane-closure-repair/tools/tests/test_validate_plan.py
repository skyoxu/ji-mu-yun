from __future__ import annotations

import importlib.util
import json
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
        self.assertEqual([], MODULE.validate())

    def test_missing_required_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "plan"
            target.mkdir()
            for required in MODULE.REQUIRED:
                source = MODULE.ROOT / required
                destination = target / required
                destination.parent.mkdir(parents=True, exist_ok=True)
                if source.is_file():
                    destination.write_bytes(source.read_bytes())
            (target / "requirements.v1.json").unlink()
            errors = MODULE.validate(target)
            self.assertIn("missing:requirements.v1.json", errors)

    def test_duplicate_slice_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "plan"
            target.mkdir()
            for required in MODULE.REQUIRED:
                source = MODULE.ROOT / required
                destination = target / required
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
            contract_path = target / "implementation-contract.v1.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["slices"][1]["slice_id"] = contract["slices"][0]["slice_id"]
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            self.assertIn("slice-set-invalid", MODULE.validate(target))

    def test_hook_and_loop_contract_is_explicit(self) -> None:
        contract = json.loads((MODULE.ROOT / "implementation-contract.v1.json").read_text(encoding="utf-8"))
        coordination = contract["coordination_contract"]
        self.assertEqual("coordinator-only", coordination["post_run_hook"]["scope"])
        self.assertEqual({"user-stop", "manual-pause"}, set(coordination["post_run_hook"]["suppress_on"]))
        self.assertEqual(["recover", "plan", "execute", "verify", "iterate"], coordination["loop"]["stages"])
        self.assertFalse(coordination["fresh_session_recovery"]["assumes_global_new_command"])
        self.assertEqual("project-local-explicit-launcher", coordination["fresh_session_recovery"]["launcher_authority"])

if __name__ == "__main__":
    unittest.main()
