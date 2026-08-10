import importlib.util
import inspect
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from skill_input_consumption import validate_contract  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
