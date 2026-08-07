import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "validate_control_plane_repair.py"
SPEC = importlib.util.spec_from_file_location("control_plane_validator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ControlPlaneRepairValidatorTests(unittest.TestCase):
    def test_current_directory_is_complete(self):
        self.assertEqual([], MODULE.validate())


if __name__ == "__main__":
    unittest.main()
