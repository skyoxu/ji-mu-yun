import re
import unittest
from pathlib import Path


class GameTypeGuideModuleMatrixTests(unittest.TestCase):
    SPECIALIZED_ALWAYS_GUIDES = {
        "action-platformer.md",
        "card-game.md",
        "rhythm.md",
        "rpg.md",
        "strategy.md",
        "tower-defense.md",
    }

    def test_all_game_type_guides_should_keep_english_matrix_contract(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        guides_root = repo_root / "docs" / "game-type-guides"
        allowed_defaults = {"Always", "Conditional", "Optional", "Out of Scope"}

        for guide in sorted(guides_root.glob("*.md")):
            if guide.name == "README.md":
                continue
            with self.subTest(guide=guide.name):
                text = guide.read_text(encoding="utf-8")
                self.assertIn("### Module Matrix", text)
                matrix = text.split("### Module Matrix", 1)[1]
                rows = [
                    line.strip()
                    for line in matrix.splitlines()
                    if line.strip().startswith("|") and not line.strip().startswith("| ---")
                ]

                self.assertGreaterEqual(len(rows), 3)
                header = [cell.strip(" `") for cell in rows[0].strip("|").split("|")]
                self.assertEqual(["No", "id", "Module", "Default", "Purpose", "Acceptance"], header)

                ids = []
                for row in rows[1:]:
                    cells = [cell.strip() for cell in row.strip("|").split("|")]
                    self.assertEqual(6, len(cells))
                    self.assertRegex(cells[0], r"^[0-9]+$")
                    module_id = cells[1].strip(" `")
                    ids.append(module_id)
                    self.assertRegex(module_id, r"^[a-z0-9_]+$")
                    self.assertIn(cells[3], allowed_defaults)
                    self.assertTrue(cells[2])
                    self.assertTrue(cells[4])
                    self.assertTrue(cells[5])

                self.assertEqual(len(ids), len(set(ids)))
                self.assertTrue(any(module_id.startswith("final_") or module_id == "final_first_loop_acceptance" for module_id in ids))
                self.assertNotRegex(matrix, r"[\u4e00-\u9fff]")

                for row in rows[1:]:
                    cells = [cell.strip() for cell in row.strip("|").split("|")]
                    if cells[3] == "Always":
                        module_id = cells[1].strip(" `")
                        if guide.name not in self.SPECIALIZED_ALWAYS_GUIDES:
                            self.assertTrue(
                                module_id == "first_loop_context" or module_id.startswith("final_"),
                                f"{guide.name} should not promote generic module {module_id!r} to Always",
                            )
                        self.assertNotIn("If included", cells[4])
                        self.assertNotIn("If included", cells[5])

    def test_readme_should_document_english_matrix_columns(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        readme = repo_root / "docs" / "game-type-guides" / "README.md"
        text = readme.read_text(encoding="utf-8")

        self.assertIn("| `Module` | Yes | Human-readable module name. |", text)
        self.assertIn("| `Default` | Yes | One of `Always`, `Conditional`, `Optional`, or `Out of Scope`. |", text)
        self.assertIn("| `Purpose` | Yes | Why the module matters to the game type. |", text)
        self.assertIn("| `Acceptance` | Yes | GDD or route-plan acceptance anchor, not final runtime evidence. |", text)
        self.assertIn("Each guide includes a `Module Matrix` section.", text)
        self.assertNotIn("Some guides may include a Module Matrix section.", text)

        column_contract = text.split("When a matrix is present, keep this column contract:", 1)[1].split("Canonical ids:", 1)[0]
        self.assertNotRegex(column_contract, r"[\u4e00-\u9fff]")

    def test_rpg_module_matrix_should_be_english_and_keep_key_ids(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        guide = repo_root / "docs" / "game-type-guides" / "rpg.md"
        text = guide.read_text(encoding="utf-8")
        matrix = text.split("### Module Matrix", 1)[1]

        self.assertNotRegex(matrix, r"[\u4e00-\u9fff]")
        self.assertIn("Opening context, player identity, and current objective", matrix)
        self.assertIn("field_navigation", matrix)
        self.assertIn("final_first_loop_acceptance", matrix)
        self.assertIn("later execution scope must be confirmed by the type kit or route contract", matrix)


if __name__ == "__main__":
    unittest.main()
