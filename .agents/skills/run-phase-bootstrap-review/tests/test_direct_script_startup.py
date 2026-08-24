import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
COMMAND = ROOT / ".agents" / "skills" / "run-phase-bootstrap-review" / "scripts" / "bootstrap_review.py"


class DirectScriptStartupTests(unittest.TestCase):
    def test_bootstrap_review_direct_script_startup_resolves_repository_toolchain(self):
        result = subprocess.run(
            [sys.executable, "-B", str(COMMAND.relative_to(ROOT)), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertNotIn("ModuleNotFoundError: No module named 'scripts.toolchain'", combined)


if __name__ == "__main__":
    unittest.main()
