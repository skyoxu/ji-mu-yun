import csv
import importlib.util
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
        "survivorslike.md",
        "tower-defense.md",
    }

    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    @staticmethod
    def read_catalog(path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    @staticmethod
    def markdown_table(text: str, heading: str, next_heading: str | None = None) -> list[list[str]]:
        section = text.split(heading, 1)[1]
        if next_heading is not None:
            section = section.split(next_heading, 1)[0]
        rows = [
            line.strip()
            for line in section.splitlines()
            if line.strip().startswith("|") and not line.strip().startswith("| ---")
        ]
        return [[cell.strip(" `") for cell in row.strip("|").split("|")] for row in rows]

    def test_all_effective_game_type_guides_should_keep_repo_contracts(self) -> None:
        repo_root = self.repo_root()
        guides_root = repo_root / "docs" / "game-type-guides"
        catalog_rows = self.read_catalog(guides_root / "game-types.csv")
        allowed_defaults = {"Always", "Conditional", "Optional", "Out of Scope"}

        self.assertEqual(25, len(catalog_rows))
        for catalog_row in catalog_rows:
            guide = guides_root / catalog_row["fragment_file"]
            with self.subTest(guide=guide.name):
                self.assertTrue(guide.is_file())
                text = guide.read_text(encoding="utf-8")
                self.assertIn("## Default Prototype Contract", text)
                self.assertIn("### Default Scenes", text)
                self.assertIn("### Required Modules", text)
                self.assertIn("## Module Matrix", text)
                scenes = self.markdown_table(text, "### Default Scenes", "### Required Modules")
                modules = self.markdown_table(text, "### Required Modules", "## Module Matrix")
                matrix = text.split("## Module Matrix", 1)[1]
                matrix_rows = self.markdown_table(text, "## Module Matrix")

                self.assertGreaterEqual(len(scenes), 2)
                self.assertEqual(
                    ["scene_id", "scene_name", "purpose", "required", "entry_from", "exits_to", "minimum_playable_content"],
                    scenes[0],
                )
                scene_ids = [row[0] for row in scenes[1:]]
                self.assertEqual(len(scene_ids), len(set(scene_ids)))
                self.assertTrue(any(row[3] == "Always" for row in scenes[1:]))
                for row in scenes[1:]:
                    self.assertEqual(7, len(row))
                    self.assertRegex(row[0], r"^[a-z0-9_]+$")
                    self.assertIn(row[3], {"Always", "Conditional", "Optional"})
                    for edge in [token.strip() for value in row[4:6] for token in value.split(",") if token.strip()]:
                        self.assertIn(edge, set(scene_ids) | {"start", "end"})

                self.assertGreaterEqual(len(modules), 2)
                self.assertEqual(
                    ["module_id", "module_name", "required_by_default", "purpose", "minimum_acceptance"],
                    modules[0],
                )
                module_ids = [row[0] for row in modules[1:]]
                self.assertEqual(len(module_ids), len(set(module_ids)))
                self.assertTrue(any(row[2] == "Always" for row in modules[1:]))
                for row in modules[1:]:
                    self.assertEqual(5, len(row))
                    self.assertRegex(row[0], r"^[a-z0-9_]+$")
                    self.assertIn(row[2], {"Always", "Conditional", "Optional"})

                self.assertGreaterEqual(len(matrix_rows), 3)
                header = matrix_rows[0]
                self.assertEqual(["No", "id", "Module", "Default", "Purpose", "Acceptance"], header)

                ids = []
                for row in matrix_rows[1:]:
                    cells = row
                    self.assertEqual(6, len(cells))
                    self.assertRegex(cells[0], r"^[0-9]+$")
                    module_id = cells[1]
                    ids.append(module_id)
                    self.assertRegex(module_id, r"^[a-z0-9_]+$")
                    self.assertIn(cells[3], allowed_defaults)
                    self.assertTrue(cells[2])
                    self.assertTrue(cells[4])
                    self.assertTrue(cells[5])

                self.assertEqual(len(ids), len(set(ids)))
                self.assertTrue(any(module_id.startswith("final_") for module_id in ids))
                self.assertNotRegex(matrix, r"[\u4e00-\u9fff]")

                for row in matrix_rows[1:]:
                    cells = row
                    if cells[3] == "Always":
                        module_id = cells[1]
                        if guide.name not in self.SPECIALIZED_ALWAYS_GUIDES:
                            self.assertTrue(
                                module_id == "first_loop_context" or module_id.startswith("final_"),
                                f"{guide.name} should not promote generic module {module_id!r} to Always",
                            )
                        self.assertNotIn("If included", cells[4])
                        self.assertNotIn("If included", cells[5])

    def test_upstream_guide_prefixes_should_match_canonical_gds_assets(self) -> None:
        repo_root = self.repo_root()
        canonical_root = repo_root / ".agents" / "skills" / "gds-gdd" / "assets"
        docs_root = repo_root / "docs" / "game-type-guides"
        canonical_rows = self.read_catalog(canonical_root / "game-types.csv")

        self.assertEqual(24, len(canonical_rows))
        for row in canonical_rows:
            with self.subTest(game_type=row["id"]):
                canonical = (canonical_root / "game-types" / row["fragment_file"]).read_text(encoding="utf-8").rstrip()
                docs = (docs_root / row["fragment_file"]).read_text(encoding="utf-8")
                docs_prefix = docs.split("## Default Prototype Contract", 1)[0].rstrip()
                self.assertEqual(canonical, docs_prefix)

    def test_docs_catalog_should_extend_upstream_tags_and_register_one_extension(self) -> None:
        repo_root = self.repo_root()
        canonical_root = repo_root / ".agents" / "skills" / "gds-gdd" / "assets"
        docs_root = repo_root / "docs" / "game-type-guides"
        canonical_list = self.read_catalog(canonical_root / "game-types.csv")
        docs_list = self.read_catalog(docs_root / "game-types.csv")
        canonical_rows = {row["id"]: row for row in canonical_list}
        docs_rows = {row["id"]: row for row in docs_list}
        localized_ids = {row["id"] for row in self.read_catalog(docs_root / "game-types.zh-CN.csv")}

        self.assertEqual(24, len(canonical_list))
        self.assertEqual(24, len(canonical_rows))
        self.assertEqual(25, len(docs_list))
        self.assertEqual(25, len(docs_rows))
        self.assertEqual({"survivorslike"}, set(docs_rows) - set(canonical_rows))
        self.assertEqual(set(), set(canonical_rows) - set(docs_rows))
        self.assertEqual(set(docs_rows), localized_ids)
        for game_type, canonical in canonical_rows.items():
            with self.subTest(game_type=game_type):
                docs = docs_rows[game_type]
                self.assertEqual(canonical["name"], docs["name"])
                self.assertEqual(canonical["description"], docs["description"])
                self.assertEqual(canonical["fragment_file"], docs["fragment_file"])
                canonical_tags = {tag.strip() for tag in canonical["genre_tags"].split(",") if tag.strip()}
                docs_tags = {tag.strip() for tag in docs["genre_tags"].split(",") if tag.strip()}
                self.assertTrue(canonical_tags.issubset(docs_tags))

        readme = (docs_root / "README.md").read_text(encoding="utf-8")
        self.assertIn("24 upstream GDS game types plus the Ji Mu Yun `survivorslike` extension", readme)

    def test_compatibility_mirror_should_match_canonical_gds_assets(self) -> None:
        repo_root = self.repo_root()
        canonical_root = repo_root / ".agents" / "skills" / "gds-gdd" / "assets"
        compatibility_root = repo_root / ".agents" / "skills" / "gds-create-gdd"
        canonical_rows = self.read_catalog(canonical_root / "game-types.csv")

        self.assertEqual(
            (canonical_root / "game-types.csv").read_text(encoding="utf-8"),
            (compatibility_root / "game-types.csv").read_text(encoding="utf-8"),
        )
        for row in canonical_rows:
            with self.subTest(game_type=row["id"]):
                self.assertEqual(
                    (canonical_root / "game-types" / row["fragment_file"]).read_text(encoding="utf-8"),
                    (compatibility_root / "game-types" / row["fragment_file"]).read_text(encoding="utf-8"),
                )

    def test_readme_should_document_english_matrix_columns(self) -> None:
        readme = self.repo_root() / "docs" / "game-type-guides" / "README.md"
        text = readme.read_text(encoding="utf-8")

        self.assertIn("| `Module` | Yes | Human-readable module name. |", text)
        self.assertIn("| `Default` | Yes | One of `Always`, `Conditional`, `Optional`, or `Out of Scope`. |", text)
        self.assertIn("| `Purpose` | Yes | Why the module matters to the game type. |", text)
        self.assertIn("| `Acceptance` | Yes | GDD or route-plan acceptance anchor, not final runtime evidence. |", text)
        self.assertIn("Each guide includes a `Default Prototype Contract` section and a `Module Matrix` section.", text)
        self.assertIn("Canonical upstream source: `.agents/skills/gds-gdd/assets/game-types/`", text)

        column_contract = text.split("When a matrix is present, keep this column contract:", 1)[1].split("Runtime-effective ids", 1)[0]
        self.assertNotRegex(column_contract, r"[\u4e00-\u9fff]")

    def test_phase_a_frontend_skill_references_should_resolve_to_installed_skills(self) -> None:
        repo_root = self.repo_root()
        source_root = repo_root / "PhaseA.Platform"
        token_pattern = re.compile(
            r"\$((?:bmad|gds)-[a-z0-9-]+|prototype-[a-z0-9-]+-zh)"
            r'|"((?:bmad|gds)-[a-z0-9-]+|prototype-[a-z0-9-]+-zh)"'
        )
        references: set[str] = set()
        for source in source_root.rglob("*.cs"):
            text = source.read_text(encoding="utf-8")
            for match in token_pattern.finditer(text):
                references.add(match.group(1) or match.group(2))

        expected = {
            "bmad-agent-game-designer",
            "gds-agent-game-designer",
            "gds-create-gdd",
            "gds-gdd",
            "prototype-7day-playable-godot-zh",
            "prototype-deckbuilder-godot-zh",
            "prototype-rpg-godot-zh",
            "prototype-rpg-ui-optimizer-zh",
            "prototype-survivorslike-godot-zh",
        }
        retired = {
            "bmad-create-ux-design",
            "bmad-distillator",
            "gds-create-prd",
            "gds-create-ux-design",
            "gds-edit-gdd",
            "gds-edit-prd",
            "gds-validate-gdd",
            "gds-validate-prd",
        }
        self.assertTrue(expected.issubset(references))
        missing = sorted(
            skill_name
            for skill_name in references - retired
            if not (repo_root / ".agents" / "skills" / skill_name / "SKILL.md").is_file()
        )
        self.assertEqual([], missing)
        self.assertTrue(retired.issubset(references))
        self.assertTrue(all(not (repo_root / ".agents" / "skills" / skill_name).exists() for skill_name in retired))

        alias = (repo_root / ".agents" / "skills" / "bmad-agent-game-designer" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Canonical skill name: `gds-agent-game-designer`", alias)

    def test_chapter2_skill_generator_should_preserve_game_metadata_contract(self) -> None:
        repo_root = self.repo_root()
        script_path = repo_root / "scripts" / "python" / "update_workflow_chapter_skills.py"
        spec = importlib.util.spec_from_file_location("update_workflow_chapter_skills", script_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        name = "workflow-chapter2-repository-bootstrap"
        generated = module.skill_markdown(name, module.SKILLS[name])
        managed = (repo_root / ".agents" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")

        for invariant in [
            "two separate steps",
            "25 runtime-effective ids",
            "24 upstream GDS ids plus the Ji Mu Yun survivorslike extension",
            "Game Name, Game Type, Game Type Source, and Game Type Guide",
            "missing, unparsable, contains duplicate ids, or points to a missing guide",
            "display the project-health URL",
            "codex exec` in read-only mode",
            "Require JSON with exactly one `game_type` id",
            "classify by gameplay fit rather than title similarity",
            "must be in Chinese",
            "Do not use PowerShell or Windows-native text commands",
        ]:
            self.assertIn(invariant, generated)
        self.assertEqual(generated, managed)

    def test_rpg_module_matrix_should_be_english_and_keep_key_ids(self) -> None:
        guide = self.repo_root() / "docs" / "game-type-guides" / "rpg.md"
        text = guide.read_text(encoding="utf-8")
        matrix = text.split("## Module Matrix", 1)[1]

        self.assertNotRegex(matrix, r"[\u4e00-\u9fff]")
        self.assertIn("Opening context, player identity, and current objective", matrix)
        self.assertIn("field_navigation", matrix)
        self.assertIn("final_first_loop_acceptance", matrix)
        self.assertIn("later execution scope must be confirmed by the type kit or route contract", matrix)


if __name__ == "__main__":
    unittest.main()
