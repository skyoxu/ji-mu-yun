"""ADR-0041: unit budgets, not whole-workflow deadlines; no model calls."""
import importlib.util
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
import workflow_unit_budget as wb


class ClockTests(unittest.TestCase):
    def start(self, b, at, call, key=None, parent="entry", container=False):
        b.apply(dict(event="start", at=at, call=call, key=key or call,
                     label=call, parent=parent, container=container))

    def end(self, b, at, call):
        b.apply(dict(event="end", at=at, call=call))

    def test_independent_units_exceed_round_budget_without_timeout(self):
        b = wb.Budget()
        self.start(b, 0, "entry", container=True)
        self.start(b, 0, "V3", container=True)
        for i in range(4):
            t = i * 550
            self.start(b, t, str(i))
            self.end(b, t + 550, str(i))
        self.assertIsNone(b.violation)
        self.assertEqual(sum(b.spent.values()), 2200)

    def test_unit_total_survives_real_output(self):
        b = wb.Budget()
        self.start(b, 0, "x")
        for t in (500, 1000, 1500):
            b.apply(dict(event="progress", at=t, call="x", digest=str(t)))
        self.assertEqual(b.tick(1800)["reason"], "unit-total")

    def test_idle_and_duplicate_output_do_not_extend_budget(self):
        b = wb.Budget()
        self.start(b, 0, "x")
        b.apply(dict(event="progress", at=1, call="x", digest="same"))
        b.apply(dict(event="progress", at=500, call="x", digest="same"))
        self.assertEqual(b.tick(601)["reason"], "unit-idle")

    def test_retry_spends_same_allowance_and_cannot_renew(self):
        b = wb.Budget(total=10, idle=20)
        self.start(b, 0, "attempt1", "same")
        self.end(b, 6, "attempt1")
        self.start(b, 6, "attempt2", "same")
        self.assertEqual(b.tick(10)["reason"], "unit-total")
        resumed = wb.Budget(total=10, idle=20, spent=b.spent, now=20)
        self.start(resumed, 20, "attempt3", "same")
        self.assertEqual(resumed.violation["reason"], "unit-total")

    def test_parallel_v3_batches_are_independent(self):
        b = wb.Budget(total=10, idle=20)
        self.start(b, 0, "V3", container=True)
        self.start(b, 0, "a")
        self.start(b, 0, "b")
        self.end(b, 6, "a")
        self.end(b, 6, "b")
        self.assertIsNone(b.violation)
        self.assertEqual(b.spent["a"], 6)
        self.assertEqual(b.spent["b"], 6)
        self.assertEqual(b.spent.get("V3", 0), 0)

    def test_advisory_attempt_identity_does_not_renew_budget(self):
        a = {'input': {'obligations': ['O-1'], 'planning_source_observations': {'episode': 'create'}}}
        b = {'input': {'obligations': ['O-1'], 'planning_source_observations': {'episode': 'repair'}}}
        self.assertEqual(wb.worker_input('prompt\n\nINPUT:\n' + json.dumps(a), None),
                         wb.worker_input('prompt\n\nINPUT:\n' + json.dumps(b), None))
        b['input']['obligations'] = ['O-2']
        self.assertNotEqual(wb.worker_input('prompt\n\nINPUT:\n' + json.dumps(a), None),
                            wb.worker_input('prompt\n\nINPUT:\n' + json.dumps(b), None))
        a['validator_findings'] = ['first diagnostic']
        previous = wb.worker_input('prompt\n\nINPUT:\n' + json.dumps(a), None)
        a['validator_findings'] = ['next diagnostic']
        self.assertEqual(previous, wb.worker_input('prompt\n\nINPUT:\n' + json.dumps(a), None))


class ProcessTests(unittest.TestCase):
    def test_silent_process_timeout_retains_diagnostic_and_cleans_child(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            code = wb.supervise([sys.executable, "-c", "import time;time.sleep(10)"],
                                cwd=root, directory=root/"budget", total=2, idle=.1)
            self.assertEqual(code, 124)
            report = next(p for p in (root/"budget").glob("*.json") if p.name != "budget-ledger.json")
            self.assertEqual(json.loads(report.read_text())["reason"]["reason"], "unit-idle")

    def test_cancel_terminates_owned_descendant(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            pidfile = root / "pid"
            source = ("import subprocess,sys,time;from pathlib import Path;"
                      "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)'],start_new_session=True);"
                      f"Path({str(pidfile)!r}).write_text(str(p.pid));time.sleep(20)")
            cancel = threading.Event()
            timer = threading.Timer(.3, cancel.set)
            timer.start()
            try:
                code = wb.supervise([sys.executable, "-c", source], cwd=root,
                                    directory=root/"budget", total=2, idle=1, cancel=cancel)
            finally:
                timer.cancel()
            self.assertEqual(code, 130)
            if os.name != "nt" and pidfile.exists():
                status = Path('/proc') / pidfile.read_text() / 'stat'
                self.assertTrue(not status.exists() or status.read_text().split()[2] == 'Z')

    def test_recommendation_has_no_supervision_writes(self):
        with patch.object(wb, 'supervise', side_effect=AssertionError('must not launch')):
            self.assertIsNone(wb.public_entry('vdd', SCRIPTS.parent,
                              ['scripts/vdd/compile_plan.py', '--recommendation-only']))

    def test_windows_cleanup_targets_owned_tree_before_parent_reap(self):
        with patch.object(wb.os, 'name', 'nt'), patch.object(wb.subprocess, 'run') as run:
            wb.terminate_tree(12345)
        self.assertEqual(run.call_args.args[0], ['taskkill', '/PID', '12345', '/T', '/F'])
        self.assertLessEqual(run.call_args.kwargs['timeout'], 10)

    @unittest.skipIf(os.name == 'nt', 'POSIX termination signal test')
    def test_sigterm_stops_supervisor_and_owned_process(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            pidfile = root / 'pid'
            worker = f"from pathlib import Path;import os,time;Path({str(pidfile)!r}).write_text(str(os.getpid()));time.sleep(20)"
            code = (f"import sys;sys.path.insert(0,{str(SCRIPTS)!r});from workflow_unit_budget import supervise;"
                    f"raise SystemExit(supervise([sys.executable,'-c',{worker!r}],cwd={str(root)!r},directory={str(root/'budget')!r}))")
            process = subprocess.Popen([sys.executable, '-c', code])
            try:
                deadline = time.monotonic() + 3
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(pidfile.exists())
                process.send_signal(signal.SIGTERM)
                self.assertEqual(process.wait(timeout=3), 130)
                status = Path('/proc') / pidfile.read_text() / 'stat'
                self.assertTrue(not status.exists() or status.read_text().split()[2] == 'Z')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_real_subunit_events_prevent_round_deadline(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = (f"import sys,time;sys.path.insert(0,{str(SCRIPTS)!r});"
                      "from workflow_unit_budget import unit\n"
                      "for i in range(3):\n with unit(i,str(i)):time.sleep(.08)\n")
            self.assertEqual(wb.supervise([sys.executable, '-c', source], cwd=root,
                             directory=root/'budget', total=.15, idle=.12), 0)


if __name__ == '__main__':
    unittest.main()
