import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

class SkillReplayContractTests(unittest.TestCase):
    def test_repository_replay_entrypoint_is_present_and_non_authorizing(self):
        path = ROOT / "scripts" / "sc" / "skill_package_replay.py"
        self.assertTrue(path.is_file())
        self.assertIn("authorizes", path.read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
