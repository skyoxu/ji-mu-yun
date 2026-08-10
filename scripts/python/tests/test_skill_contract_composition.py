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


if __name__ == "__main__":
    unittest.main()
