from __future__ import annotations

import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SKILL_ROOT.parents[2]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class SourceClauseTests(unittest.TestCase):
    def test_extracts_all_ra_heading_clauses_with_hash_bound_source(self) -> None:
        import source_clauses

        path = REPOSITORY_ROOT / "execution-plans/2026-07-15-refactor-implementation-acceptance-skill-requirements.md"
        result = source_clauses.extract_heading_clauses(path, path.relative_to(REPOSITORY_ROOT).as_posix())
        ra = [item for item in result["clauses"] if item["sourceIdentity"].startswith("RA-SKILL-")]
        self.assertEqual(73, len(ra))
        self.assertEqual([], result["authorizes"])

    def test_cli_rejects_source_outside_repository(self) -> None:
        import acceptance_cli
        from acceptance_core import InputError

        with self.assertRaises(InputError):
            acceptance_cli.extract_source_clauses_command(str(REPOSITORY_ROOT.parent / "outside.md"), str(REPOSITORY_ROOT))


if __name__ == "__main__":
    unittest.main()
