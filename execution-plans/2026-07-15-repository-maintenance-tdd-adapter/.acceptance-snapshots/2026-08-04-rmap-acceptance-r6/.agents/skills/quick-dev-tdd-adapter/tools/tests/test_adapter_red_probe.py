from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


class AdapterRedProbeTests(unittest.TestCase):
    def test_probe_observes_missing_red_guard(self) -> None:
        probe = Path(__file__).with_name("adapter_red_probe.py")
        result = subprocess.run([sys.executable, str(probe)], check=False, capture_output=True, text=True)
        self.assertEqual(1, result.returncode)
        self.assertEqual("RMAP-TDD-RED-NOT-OBSERVED", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
