"""Real subprocess regression for the ADR-0005 CI timeout boundary."""
from pathlib import Path
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

PYTHON_DIR = Path(__file__).resolve().parents[2] / 'python'
sys.path.insert(0, str(PYTHON_DIR))
from ci_process import env_timeout_ms, run_logged_command


class CiProcessTests(unittest.TestCase):
    def test_success_and_failure_keep_separate_output(self):
        with tempfile.TemporaryDirectory() as directory:
            rc, out, err = run_logged_command(
                [sys.executable, '-c', 'import sys; print("stdout"); print("stderr", file=sys.stderr); sys.exit(7)'],
                cwd=directory, timeout=3000, separate_stderr=True,
            )
            self.assertEqual(7, rc)
            self.assertIn('stdout', out)
            self.assertIn('stderr', err)
            logs = list(Path(directory).rglob('*.log'))
            self.assertEqual(2, len(logs))
            self.assertTrue(any('stdout' in p.read_text() for p in logs))

    def test_timeout_stops_descendant_and_preserves_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            # An inherited stdout handle used to keep communicate() blocked.
            # The child must not create the marker after its parent times out.
            code = ('import subprocess, sys, time; '
                    'subprocess.Popen([sys.executable, "-c", '
                    '"import time; from pathlib import Path; time.sleep(2); Path(\'escaped\').touch()"]); '
                    'print("before-timeout", flush=True); time.sleep(30)')
            started = time.monotonic()
            rc, out, _ = run_logged_command([sys.executable, '-c', code], cwd=directory, timeout=1000)
            self.assertEqual(124, rc)
            self.assertIn('before-timeout', out)
            self.assertLess(time.monotonic() - started, 20)
            time.sleep(2.1)
            self.assertFalse((Path(directory) / 'escaped').exists())

    def test_stage_timeout_override_is_validated(self):
        with mock.patch.dict(os.environ, {'CI_DOTNET_STAGE_TIMEOUT_MS': '4200000'}):
            self.assertEqual(4200000, env_timeout_ms('CI_DOTNET_STAGE_TIMEOUT_MS', 900000))
        for value in ('0', '-1', 'invalid'):
            with self.subTest(value=value), mock.patch.dict(os.environ, {'CI_DOTNET_STAGE_TIMEOUT_MS': value}):
                with self.assertRaises(ValueError):
                    env_timeout_ms('CI_DOTNET_STAGE_TIMEOUT_MS', 900000)


if __name__ == '__main__':
    unittest.main()
