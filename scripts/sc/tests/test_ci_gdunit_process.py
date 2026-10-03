"""Real GdUnit prewarm process regressions (ADR-0005 / ADR-0025)."""
from pathlib import Path
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
import run_gdunit


class CiGdUnitProcessTests(unittest.TestCase):
    def test_completed_wrapper_does_not_wait_for_inherited_stdout_handle(self):
        with tempfile.TemporaryDirectory() as directory:
            code = (
                "import subprocess, sys; from pathlib import Path; "
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(6)']); "
                "Path('owned-child.pid').write_text(str(child.pid)); "
                "print('prewarm-complete', flush=True)"
            )
            started = time.monotonic()
            try:
                rc, output = run_gdunit.run_cmd(
                    [sys.executable, "-c", code], cwd=directory, timeout=4000
                )
                self.assertEqual(0, rc)
                self.assertIn("prewarm-complete", output)
                self.assertLess(time.monotonic() - started, 3)
            finally:
                pid_path = Path(directory) / "owned-child.pid"
                if pid_path.exists():
                    pid = int(pid_path.read_text())
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=10, check=False,
                        )
                    else:
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass

    def test_stale_reports_cannot_satisfy_the_current_invocation(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report_1/results.xml"
            report.parent.mkdir()
            report.write_text('<testsuites tests="74" failures="0"/>', encoding="utf-8")
            old_ns = time.time_ns() - 10_000_000_000
            os.utime(report, ns=(old_ns, old_ns))
            started = time.time_ns()
            self.assertIsNone(run_gdunit._find_latest_results_xml(
                directory, not_before_ns=started
            ))
            fresh_ns = started + 1_000_000_000
            os.utime(report, ns=(fresh_ns, fresh_ns))
            self.assertEqual(str(report), run_gdunit._find_latest_results_xml(
                directory, not_before_ns=started
            ))

    def test_missing_empty_failed_and_timed_out_results_stay_failed(self):
        passed = {"tests": 74, "failures": 0, "errors": 0}
        cases = [
            (0, {}, False, 1),
            (0, {"tests": 0, "failures": 0, "errors": 0}, False, 1),
            (0, {"tests": 74, "skipped": 74, "failures": 0, "errors": 0}, False, 1),
            (0, {"tests": 74, "failures": 1, "errors": 0}, False, 1),
            (0, {"tests": 74, "failures": 0, "errors": 1}, False, 1),
            (124, passed, False, 124),
            (100, passed, True, 100),
            (100, passed, False, 0),
            (0, passed, True, 0),
        ]
        for rc, result, strict, expected in cases:
            with self.subTest(rc=rc, result=result, strict=strict):
                self.assertEqual(
                    expected, run_gdunit._result_exit_code(rc, result, strict=strict)
                )

    def test_environment_output_and_nonzero_exit_remain_observable(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ, GODOT_CI_TEST_VALUE="owned-fixture-value")
            code = (
                "import os, sys; print(os.environ['GODOT_CI_TEST_VALUE']); "
                "print('original-error', file=sys.stderr); sys.exit(7)"
            )
            rc, output = run_gdunit.run_cmd(
                [sys.executable, "-c", code], cwd=directory, timeout=4000, env=environment
            )
            self.assertEqual(7, rc)
            self.assertIn("owned-fixture-value", output)
            self.assertIn("original-error", output)


if __name__ == "__main__":
    unittest.main()
