from pathlib import Path
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[2]


class SkillContractTests(unittest.TestCase):
    def test_required_current_contract_documents_exist(self) -> None:
        required = {
            "SKILL.md": "stable `scripts/quick_dev/run.py`",
            "references/implementation-backend-contract.md": "not select a plan",
            "references/tdd-run-protocol.md": "`tools/process_executor_v2.py` owns process facts",
            "references/evidence-and-freshness.md": "logs/tdd-adapter",
            "references/repair-review-handoff.md": "audit-repair-completeness",
            "tools/build_repair_review_handoff.py": "acceptance-repair-completeness-request.v1",
        }
        for relative, marker in required.items():
            with self.subTest(relative=relative):
                content = (SKILL_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(marker, content)

    def test_current_plan_contract_is_explicit_and_local(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--plan <plan-dir>", content)
        self.assertIn("--slice <slice-id>", content)
        self.assertIn("--recommendation-only", content)
        self.assertIn("--action execute-stage|implementation-handoff|slice-ready|implementation-complete|recover", content)
        self.assertIn("Never infer current authority from glob, mtime", content)
        self.assertIn("Historical v1 plans are read-only compatibility inputs", content)
        self.assertIn("legacy combined receipt/observation fields", content)
        self.assertIn("never authorizes current evidence", content)

    def test_q6_and_authority_boundaries_are_explicit(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`tools/regression_gate.py`", content)
        self.assertIn("agent-context.validation_commands", content)
        self.assertIn("zero-case pytest regression blocks publication", content)
        self.assertIn("not review, acceptance, commit, PR, release, or archive authority", content)
        self.assertIn("Model/backend text is never evidence authority", content)
        self.assertIn("Never let governance bytes become runtime truth by default", content)
        self.assertIn("acceptance-passed | external Acceptance Skill", content)


if __name__ == "__main__":
    unittest.main()
