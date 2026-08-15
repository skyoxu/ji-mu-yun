import importlib.util
import inspect
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from skill_input_consumption import SkillInputError, validate_contract  # noqa: E402


CONTRACTS = {
    "vdd-execution-plan": ("create", {"requirements"}),
    "quick-dev-tdd-adapter": ("execute", {"plan_directory", "target_files"}),
    "run-phase-bootstrap-review": ("review", {"closure_inputs", "authority"}),
    "run-refactor-implementation-acceptance": ("acceptance", {"implementation_target", "acceptance_requirements"}),
}


class SkillContractCompositionTests(unittest.TestCase):
    def test_all_initial_consumers_have_strict_valid_contracts(self):
        for consumer, (operation, required_roles) in CONTRACTS.items():
            with self.subTest(consumer=consumer):
                path = ROOT / ".agents" / "skills" / consumer / "references" / "skill-input-contract.v1.json"
                contract = json.loads(path.read_text(encoding="utf-8"))
                validate_contract(contract, ROOT)
                self.assertEqual("strict", contract["mode"])
                self.assertEqual(consumer, contract["consumer"])
                self.assertEqual(required_roles, set(contract["operations"][operation]["required_inputs"]))
                self.assertIn("logs-as-recovery-source", contract["forbidden_sources"])

    def test_quick_dev_contract_uses_consumer_owned_paged_budget(self):
        contract_path = (
            ROOT
            / ".agents"
            / "skills"
            / "quick-dev-tdd-adapter"
            / "references"
            / "skill-input-contract.v1.json"
        )
        contract = json.loads(contract_path.read_text(encoding="utf-8"))

        validate_contract(contract, ROOT)
        self.assertEqual("paged-frozen-snapshot-stdin", contract["semantic_input_mode"])
        self.assertEqual(1_048_576, contract["max_snapshot_bytes"])
        self.assertEqual(32_768, contract["max_snapshot_chunk_bytes"])
        self.assertEqual(
            ".agents/skills/quick-dev-tdd-adapter/references/skill-input-budget.paged-v1.json",
            contract["budget_basis"]["path"],
        )
        budget_path = ROOT / contract["budget_basis"]["path"]
        budget = json.loads(budget_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["semantic_input_mode"], budget["semantic_input_mode"])
        self.assertEqual(contract["max_snapshot_chunk_bytes"], budget["max_snapshot_chunk_bytes"])

        mutated = dict(contract)
        mutated["max_snapshot_chunk_bytes"] = 16_384
        with self.assertRaisesRegex(SkillInputError, "budget_basis does not bind max_snapshot_chunk_bytes"):
            validate_contract(mutated, ROOT)

    def test_declared_strict_entrypoints_require_receipts(self):
        required_cli_sources = [
            ROOT / ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py",
            ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py",
        ]
        for path in required_cli_sources:
            with self.subTest(path=path):
                source = path.read_text(encoding="utf-8")
                self.assertRegex(
                    source,
                    r'add_argument\("--skill-input-receipt"[^\n]*required=True',
                )

        bootstrap_source = (
            ROOT / ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py"
        ).read_text(encoding="utf-8")
        self.assertIn("if not args.skill_input_receipt:", bootstrap_source)
        self.assertIn("Skill input gate is required", bootstrap_source)

        adapter_path = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/adapter.py"
        spec = importlib.util.spec_from_file_location("strict_quick_dev_adapter", adapter_path)
        assert spec and spec.loader
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        receipt = inspect.signature(adapter.execute).parameters["receipt_path"]
        self.assertIs(inspect.Parameter.empty, receipt.default)
        prepare = inspect.signature(adapter.prepare).parameters["receipt_path"]
        self.assertIs(inspect.Parameter.empty, prepare.default)

    def test_each_initial_consumer_has_a_real_ready_context_composition_test(self):
        composition_tests = {
            "vdd-execution-plan": ROOT / ".agents" / "skills" / "vdd-execution-plan" / "scripts" / "tests" / "test_vdd_knowledge_preflight.py",
            "quick-dev-tdd-adapter": ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools" / "tests" / "test_adapter.py",
            "run-phase-bootstrap-review": ROOT / ".agents" / "skills" / "run-phase-bootstrap-review" / "tests" / "test_bootstrap_review.py",
            "run-refactor-implementation-acceptance": ROOT / ".agents" / "skills" / "run-refactor-implementation-acceptance" / "tests" / "test_package.py",
        }
        for consumer, path in composition_tests.items():
            with self.subTest(consumer=consumer):
                source = path.read_text(encoding="utf-8")
                self.assertIn("publish_ready_receipt", source)
                self.assertRegex(source, r"def test_.*consumes_real_ready_skill_input_context")


if __name__ == "__main__":
    unittest.main()
