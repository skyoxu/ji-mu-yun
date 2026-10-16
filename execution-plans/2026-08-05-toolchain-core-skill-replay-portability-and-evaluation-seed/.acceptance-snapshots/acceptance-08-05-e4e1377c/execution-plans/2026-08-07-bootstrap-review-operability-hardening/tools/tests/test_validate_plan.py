import importlib.util
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location("plan",Path(__file__).resolve().parents[1]/"validate_plan.py")
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
class PlanTests(unittest.TestCase):
    def test_plan_is_valid(self): self.assertEqual([],module.validate_plan())
    def test_round4_repair_contract_is_part_of_plan_readiness(self):
        repair_validator = (
            Path(__file__).resolve().parents[2]
            / "repair" / "round-4" / "tools" / "validate_repair_plan.py"
        )
        self.assertTrue(repair_validator.is_file())
        self.assertFalse(any(error.startswith("repair-round-4:") for error in module.validate_plan()))
    def test_round4_repair_contract_is_part_of_plan_readiness(self):
        repair_validator = (
            Path(__file__).resolve().parents[2]
            / "repair" / "round-4" / "tools" / "validate_repair_plan.py"
        )
        self.assertTrue(repair_validator.is_file())
        self.assertFalse(any(error.startswith("repair-round-4:") for error in module.validate_plan()))
    def test_implementation_authorization_is_a_valid_post_plan_ready_state(self):
        import json
        state=json.loads((module.PLAN_DIR/"plan-state.v1.json").read_text(encoding="utf-8"))
        self.assertIn(state["state"], {"implementation-authorized", "implementation-complete"})
        self.assertEqual(
            ["plan-ready", "implementation-authorized"]
            if state["state"] == "implementation-authorized"
            else ["implementation-complete"],
            state["authorizes"],
        )
    def test_plan_never_authorizes(self):
        import json
        self.assertEqual([],json.loads((module.PLAN_DIR/"requirements.v1.json").read_text()) ["authorizes"])
    def test_reviewer_operability_cases_are_required(self):
        self.assertIn("readonly-repository-access",module.REQUIRED_CASES)
        self.assertIn("exact-evidence-crlf-range",module.REQUIRED_CASES)
        self.assertIn("repeated-stale-evidence-stop-loss",module.REQUIRED_CASES)
    def test_cross_skill_cases_and_slices_are_required(self):
        self.assertIn("workflow-control-plane-required",module.REQUIRED_CASES)
        self.assertIn("discovery-wave-partial-transport-failure",module.REQUIRED_CASES)
        self.assertIn("current-target-post-implementation-review",module.REQUIRED_CASES)
        self.assertIn("clean-discovery-zero-findings-valid",module.REQUIRED_CASES)
        self.assertIn("typed-trigger-required-for-later-discovery",module.REQUIRED_CASES)
        self.assertEqual({f"BROH-S{i}" for i in range(8)},module.SLICE_IDS)
    def test_each_slice_uses_one_real_target_test_for_red_and_green(self):
        import json
        contract=json.loads((module.PLAN_DIR/"implementation-contract.v1.json").read_text(encoding="utf-8"))
        for item in contract["slices"]:
            red=item["tdd"]["red"]
            self.assertEqual(red["command_id"],item["tdd"]["green"]["command_id"])
            self.assertTrue(red["command_id"].endswith("-target-test"))
            self.assertNotIn("controlled",red["test_selector"])
    def test_each_slice_snapshots_its_complete_exact_write_set(self):
        import json
        contract=json.loads((module.PLAN_DIR/"implementation-contract.v1.json").read_text(encoding="utf-8"))
        for item in contract["slices"]:
            allowed=[path for values in item["allowed_changes"].values() for path in values]
            self.assertCountEqual(allowed,item["execution_snapshot_paths"])
            self.assertEqual(len(allowed),len(set(allowed)))

    def test_planned_new_files_are_explicit_and_scoped(self):
        import json
        contract=json.loads((module.PLAN_DIR/"implementation-contract.v1.json").read_text(encoding="utf-8"))
        s4=next(item for item in contract["slices"] if item["slice_id"] == "BROH-S4")
        self.assertEqual(
            {
                ".agents/skills/run-refactor-implementation-acceptance/scripts/review_requirement.py",
                ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-semantic-review-requirement-decision.v1.schema.json",
                ".agents/skills/run-refactor-implementation-acceptance/tests/test_review_requirement.py",
            },
            set(s4["planned_new_files"]),
        )
        for item in contract["slices"]:
            allowed={path for values in item["allowed_changes"].values() for path in values}
            self.assertTrue(set(item["planned_new_files"]).issubset(allowed))
    def test_adapter_bridge_is_single_maintainer_and_current_session_owned(self):
        import json
        contract=json.loads((module.PLAN_DIR/"implementation-contract.v1.json").read_text(encoding="utf-8"))
        self.assertEqual("current-session-four-phase",contract["adapter_bridge"]["mode"])
        self.assertFalse(contract["adapter_bridge"]["parallel_owners"])
        self.assertFalse(contract["adapter_bridge"]["external_requirement_injection"])
if __name__ == "__main__": unittest.main()
