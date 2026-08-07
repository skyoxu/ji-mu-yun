from __future__ import annotations

import importlib.util
import json
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
        self.assertEqual([], MODULE.validate_plan(implementation_state=True))

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

    def test_duplicate_slice_id_is_rejected(self) -> None:
        slices = [
            {"slice_id": "RMAP-S0", "depends_on": []},
            {"slice_id": "RMAP-S0", "depends_on": ["RMAP-S3"]},
        ]
        errors: list[str] = []
        MODULE.check_dependency_graph(slices, errors)
        self.assertIn("duplicate-slice-id", errors)

    def test_hook_and_loop_contract_is_explicit(self) -> None:
        contract = MODULE.load_json(MODULE.PLAN_DIR / "implementation-contract.v1.json", [])
        coordination = contract["coordination_contract"]
        self.assertEqual("coordinator-only", coordination["post_run_hook"]["scope"])
        self.assertEqual({"user-stop", "manual-pause"}, set(coordination["post_run_hook"]["suppress_on"]))
        self.assertEqual(["recover", "plan", "execute", "verify", "iterate"], coordination["loop"]["stages"])
        self.assertFalse(coordination["fresh_session_recovery"]["assumes_global_new_command"])
        self.assertEqual("project-local-explicit-launcher", coordination["fresh_session_recovery"]["launcher_authority"])

    def test_closed_repair_requires_bootstrap_closure_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "plan"
            shutil.copytree(MODULE.PLAN_DIR, target)
            resume_path = target / "resume-state.v1.json"
            resume = json.loads(resume_path.read_text(encoding="utf-8"))
            resume["repair"]["status"] = "closed"
            resume["repair"]["closure"] = "repair/round-3/repair-closure.json"
            resume_path.write_text(json.dumps(resume), encoding="utf-8")
            errors = MODULE.validate_plan(target, MODULE.REPO_ROOT, check_index=False, check_source_hashes=False)
            self.assertIn("resume-bootstrap-repair-closure-path-invalid", errors)


if __name__ == "__main__":
    unittest.main()
