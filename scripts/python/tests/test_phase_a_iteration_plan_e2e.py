from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = REPO_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import phase_a_iteration_plan_e2e as e2e  # noqa: E402


class PhaseAIterationPlanE2ETests(unittest.TestCase):
    def test_copy_excludes_repo_local_dotnet_sdk(self) -> None:
        self.assertIn(".dotnet", e2e.EXCLUDED_COPY_DIRS)

    def test_default_dotnet_resolves_to_an_existing_executable(self) -> None:
        self.assertTrue(Path(e2e.DEFAULT_DOTNET).is_file(), e2e.DEFAULT_DOTNET)


if __name__ == "__main__":
    unittest.main()
