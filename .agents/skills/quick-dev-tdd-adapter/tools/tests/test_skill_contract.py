import json
from pathlib import Path
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[2]


class SkillContractTests(unittest.TestCase):
    def test_required_contract_documents_exist(self) -> None:
        required = {
            "SKILL.md": "plan-directory execution loop",
            "references/implementation-backend-contract.md": "not select a plan",
            "references/tdd-run-protocol.md": "prepare -> RED -> GREEN -> REFACTOR -> candidate",
            "references/evidence-and-freshness.md": "logs/tdd-adapter",
            "references/repair-review-handoff.md": "audit-repair-completeness",
            "tools/build_repair_review_handoff.py": "acceptance-repair-completeness-request.v1",
        }
        for relative, marker in required.items():
            with self.subTest(relative=relative):
                content = (SKILL_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(marker, content)

    def test_plan_directory_contract_is_explicit_and_local(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--plan-dir", content)
        self.assertIn("Do not enumerate, index", content)
        self.assertIn("run-state.v1.json", content)
        self.assertIn("root-cause callsite inventory", content)
        self.assertIn("controlled producer/consumer composition receipts", content)
        self.assertIn("Do not select an acceptance route", content)

    def test_version_currency_commit_gate_is_conditional_and_non_authoritative(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Version Currency Commit Gate", content)
        self.assertIn("Context7", content)
        self.assertIn("exact target version", content)
        self.assertIn("not commit authority", content)
        self.assertIn("do not create a network dependency", content)


if __name__ == "__main__":
    unittest.main()
