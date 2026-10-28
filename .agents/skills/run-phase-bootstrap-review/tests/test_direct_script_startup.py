"""ADR-0062 / ADR-0041: startup import proof with explicit CLI prerequisites."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
COMMAND = ROOT / ".agents" / "skills" / "run-phase-bootstrap-review" / "scripts" / "bootstrap_review.py"


class DirectScriptStartupTests(unittest.TestCase):
    def _help_with_model(self, model_toml):
        # CODEX_HOME is the existing official configuration override. Only this
        # --help subprocess sees the synthetic fixture; no model is launched.
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / "model-routing.toml").write_text(model_toml, encoding="utf-8")
            env = os.environ.copy()
            env["CODEX_HOME"] = str(home)
            return subprocess.run(
                [sys.executable, "-B", str(COMMAND.relative_to(ROOT)), "--help"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
                env=env,
            )

    def test_bootstrap_review_direct_script_startup_resolves_repository_toolchain(self):
        result = self._help_with_model('model = "synthetic-startup-test"\n')
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertNotIn("ModuleNotFoundError: No module named 'scripts.toolchain'", combined)
        self.assertIn("usage:", result.stdout)

    def test_help_does_not_hide_invalid_model_prerequisite(self):
        result = self._help_with_model('model = false\n')
        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Codex model configuration must define a valid model string", combined)
        self.assertNotIn("ModuleNotFoundError: No module named 'scripts.toolchain'", combined)


if __name__ == "__main__":
    unittest.main()
