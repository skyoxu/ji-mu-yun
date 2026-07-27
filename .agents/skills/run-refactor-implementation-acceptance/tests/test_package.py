from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class PackageTests(unittest.TestCase):
    def test_package_validator_requires_all_slice_modules(self) -> None:
        import package_validation

        self.assertEqual([], package_validation.validate_package(SKILL_ROOT))

    def test_fixture_catalog_covers_required_execution_contexts(self) -> None:
        import package_validation

        fixture = json.loads((SKILL_ROOT / "fixtures" / "negative-cases.v1.json").read_text(encoding="utf-8"))
        self.assertEqual([], package_validation.validate_fixture_catalog(fixture))
        fixture["categories"].remove("fresh-context")
        self.assertIn("missing-fixture-category:fresh-context", package_validation.validate_fixture_catalog(fixture))

    def test_cli_exposes_required_workflow_transitions(self) -> None:
        expected = {
            "prepare", "resolve-code-review-policy", "inventory", "audit-task-checklist",
            "collect-evidence", "run-command", "run-static-analysis", "run-security-scan",
            "analyze-diff-coverage", "evaluate", "render", "decide-bootstrap",
            "bind-bootstrap-capabilities", "prepare-attestation", "prepare-bootstrap",
            "import-bootstrap-launch-authorization", "import-bootstrap", "map-findings",
            "import-mapping-approval", "project-acceptance-impact", "finalize", "inspect-run", "resume",
        }
        result = subprocess.run(
            [sys.executable, "-B", str(SKILL_ROOT / "scripts" / "acceptance_cli.py"), "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(all(command in result.stdout for command in expected))


if __name__ == "__main__":
    unittest.main()
