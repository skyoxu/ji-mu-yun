from __future__ import annotations

import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SKILL_ROOT.parents[2]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class RequirementInventoryTests(unittest.TestCase):
    def test_extracts_the_complete_atomic_ra_set_from_authoritative_source(self) -> None:
        from requirement_inventory import extract_requirement_inventory

        source = REPOSITORY_ROOT / "execution-plans/2026-07-15-refactor-implementation-acceptance-skill-requirements.md"
        inventory = extract_requirement_inventory(source, source.relative_to(REPOSITORY_ROOT).as_posix())
        self.assertEqual(73, len(inventory["requirements"]))
        self.assertEqual("RA-SKILL-001", inventory["requirements"][0]["id"])
        self.assertEqual("RA-SKILL-073", inventory["requirements"][-1]["id"])
        self.assertEqual([], inventory["authorizes"])

    def test_rejects_missing_or_duplicate_ra_identity(self) -> None:
        from requirement_inventory import RequirementInventoryError, extract_requirement_inventory_text

        with self.assertRaisesRegex(RequirementInventoryError, "missing"):
            extract_requirement_inventory_text("### RA-SKILL-001: only\n", "source.md")
        duplicate = "\n".join(f"### RA-SKILL-{index:03d}: clause" for index in range(1, 74)) + "\n### RA-SKILL-073: duplicate\n"
        with self.assertRaisesRegex(RequirementInventoryError, "duplicate"):
            extract_requirement_inventory_text(duplicate, "source.md")

    def test_cli_helper_rejects_source_outside_the_repository(self) -> None:
        from acceptance_cli import InputError, extract_requirements_command

        outside = REPOSITORY_ROOT.parent / "outside-requirements.md"
        with self.assertRaises(InputError):
            extract_requirements_command(str(outside), str(REPOSITORY_ROOT))

    def test_inventory_can_be_published_once_as_an_immutable_artifact(self) -> None:
        from acceptance_cli import extract_requirements_command

        source = REPOSITORY_ROOT / "execution-plans/2026-07-15-refactor-implementation-acceptance-skill-requirements.md"
        output = self._testMethodName + ".json"
        artifact = SKILL_ROOT / "fixtures" / output
        self.addCleanup(artifact.unlink, missing_ok=True)
        published = extract_requirements_command(str(source), str(REPOSITORY_ROOT), str(artifact))
        self.assertTrue(artifact.is_file())
        self.assertEqual([], published["authorizes"])
        with self.assertRaisesRegex(Exception, "append-only"):
            extract_requirements_command(str(source), str(REPOSITORY_ROOT), str(artifact))


if __name__ == "__main__":
    unittest.main()
