import json
from pathlib import Path
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[2]


class SkillContractTests(unittest.TestCase):
    def test_required_contract_documents_exist(self) -> None:
        required = {
            "SKILL.md": "stateless, in-session protocol adapter",
            "references/implementation-backend-contract.md": "not select a plan",
            "references/tdd-run-protocol.md": "prepare -> RED -> GREEN -> REFACTOR -> candidate",
            "references/evidence-and-freshness.md": "logs/tdd-adapter",
        }
        for relative, marker in required.items():
            with self.subTest(relative=relative):
                content = (SKILL_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(marker, content)

    def test_target_report_index_contract_is_current(self) -> None:
        repository_root = SKILL_ROOT.parents[2]
        index_path = repository_root / "execution-plans/95-implementation-report-index.v1.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(
            "jimuyun.execution-plan-95-report-index.v1",
            index.get("schema_version"),
        )
        entries = index.get("entries")
        self.assertIsInstance(entries, list)
        self.assertEqual(
            sorted(entries, key=lambda item: item["plan_directory"].casefold()),
            entries,
        )
        self.assertEqual(
            len(entries),
            len({item["plan_directory"].casefold() for item in entries}),
        )
        for entry in entries:
            self.assertEqual({"plan_directory", "report_filename"}, set(entry))
            report_name = entry["report_filename"]
            self.assertEqual(report_name, Path(report_name).name)
            self.assertTrue(report_name.startswith("95-") and report_name.endswith(".md"))
            report = repository_root / "execution-plans" / entry["plan_directory"] / report_name
            self.assertTrue(report.is_file(), report)
        self.assertIn(
            {
                "plan_directory": "2026-07-15-repository-maintenance-tdd-adapter",
                "report_filename": "95-implementation-evolution-and-completion-report.md",
            },
            entries,
        )

    def test_report_creation_requires_same_change_index_registration(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("95-implementation-report-index.v1.json", content)
        self.assertIn("same pre-implementation change", content)
        self.assertIn("inspect only the named target directory", content)
        self.assertIn("non-authoritative path hint", content)


if __name__ == "__main__":
    unittest.main()
