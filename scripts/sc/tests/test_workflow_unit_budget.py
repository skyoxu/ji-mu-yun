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
    def test_supervision_preserves_captured_standard_streams_and_exit_code(self):
        root = Path(tempfile.mkdtemp(prefix="owned-stdio-"))
        nonce = "owned-stdio-" + os.urandom(12).hex()
        known_input = nonce + "-input\n"
        worker = ("import json,os,sys,threading\n"
                  # The fixture cannot leak a blocked reader on any platform.
                  "timer=threading.Timer(4,lambda:os._exit(91));timer.daemon=True;timer.start()\n"
                  "received=sys.stdin.read()\n"
                  f"sys.stdout.write(json.dumps({{'nonce':{nonce!r},'received':received,'channel':'stdout'}},sort_keys=True)+'\\n');sys.stdout.flush()\n"
                  f"sys.stderr.write({(nonce+'-stderr'+chr(10))!r});sys.stderr.flush()\n"
                  "timer.cancel()\nraise SystemExit(7)\n")
        worker_path = root / "worker.py"
        worker_path.write_text(worker, encoding="utf-8", newline="\n")
        supervisor = (f"import sys;sys.path.insert(0,{str(SCRIPTS)!r});"
                      "from workflow_unit_budget import supervise;"
                      f"raise SystemExit(supervise([sys.executable,'-B',{str(worker_path)!r}],"
                      f"cwd={str(root)!r},directory={str(root/'budget')!r},total=5,idle=5))")
        supervisor_path = root / "supervisor.py"
        supervisor_path.write_text(supervisor, encoding="utf-8", newline="\n")
        guard, process = None, None
        try:
            if os.name == "nt":
                from scripts.sc.skill_replay_windows_job import WindowsJob
                guard = WindowsJob()
                options = {"creationflags": subprocess.CREATE_NO_WINDOW | 0x4}
            else:
                options = {"start_new_session": True}
            process = subprocess.Popen([sys.executable, "-B", str(supervisor_path)], cwd=root,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       **options)
            if guard is not None:
                guard.assign_and_resume(process)
            stdout, stderr = process.communicate(input=known_input.encode("utf-8"), timeout=8)
            (root / "captured-stdout.bin").write_bytes(stdout)
            (root / "captured-stderr.bin").write_bytes(stderr)
            (root / "capture-result.json").write_text(json.dumps({"authorizes": [], "nonce": nonce,
                "known_input": known_input, "exit_code": process.returncode}, sort_keys=True) + "\n", encoding="utf-8")
            self.assertEqual(7, process.returncode, stderr.decode("utf-8", errors="replace"))
            self.assertEqual({"nonce": nonce, "received": known_input, "channel": "stdout"},
                             json.loads(stdout.decode("utf-8")))
            self.assertEqual(nonce + "-stderr\n", stderr.decode("utf-8").replace("\r\n", "\n"))
            reports = [path for path in (root / "budget").glob("*.json") if path.name != "budget-ledger.json"]
            self.assertEqual(1, len(reports))
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            self.assertEqual(7, report["exit_code"])
            self.assertIsNone(report["reason"])
            self.assertEqual([], report["authorizes"])
        finally:
            try:
                if guard is not None:
                    # All transport assertions precede this failure guard.
                    guard.terminate()
                elif process is not None and process.poll() is None:
                    wb.terminate_tree(process)
            finally:
                try:
                    if process is not None:
                        if process.poll() is None:
                            process.kill()
                        stdout, stderr = process.communicate(timeout=3)
                        if not (root / "captured-stdout.bin").exists():
                            (root / "captured-stdout.bin").write_bytes(stdout)
                            (root / "captured-stderr.bin").write_bytes(stderr)
                finally:
                    if guard is not None:
                        guard.close()

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

    def test_sigterm_stops_supervisor_and_owned_process(self):
        if os.name == "nt":
            # Windows SIGTERM terminates directly. Exercise the existing
            # headless cancellation API instead of claiming signal support.
            self._headless_cancel_stops_supervisor_and_owned_processes()
            return
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

    def _headless_cancel_stops_supervisor_and_owned_processes(self):
        import ctypes
        from scripts.sc.skill_replay_windows_job import WindowsJob

        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        api.OpenProcess.restype = ctypes.c_void_p
        api.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        api.WaitForSingleObject.restype = ctypes.c_uint32
        api.IsProcessInJob.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        api.IsProcessInJob.restype = ctypes.c_int
        api.CloseHandle.argtypes = [ctypes.c_void_p]
        api.CloseHandle.restype = ctypes.c_int

        # Retain this fixture's actual startup/cleanup evidence on failure.
        root = Path(tempfile.mkdtemp(prefix="owned-cancel-"))
        with (root / "supervisor-stdout.txt").open("wb") as out, \
             (root / "supervisor-stderr.txt").open("wb") as err:
            ready, descendant_ready = root / "owned.json", root / "descendant-ready"
            descendant = ("import os,time;from pathlib import Path;"
                          f"path=Path({str(descendant_ready)!r});"
                          "temporary=path.with_suffix('.tmp');temporary.write_text(str(os.getpid()));"
                          "temporary.replace(path);time.sleep(30)")
            # ADR-0041: this stdlib-only leaf must expose the actual launch PID.
            leaf_python = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
            self.assertEqual(Path(sys.base_prefix).resolve(), leaf_python.parent)
            self.assertTrue(leaf_python.is_file())
            worker = ("import json,os,subprocess,sys,time;from pathlib import Path;"
                      f"Path({str(root/'worker-started')!r}).write_text(str(os.getpid()));"
                      f"child=subprocess.Popen([{str(leaf_python)!r},'-I','-S','-c',{descendant!r}],"
                      "creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW);"
                      f"path=Path({str(ready)!r});temporary=path.with_suffix('.tmp');"
                      "temporary.write_text(json.dumps({'worker':os.getpid(),'descendant':child.pid}));"
                      "temporary.replace(path);time.sleep(30)")
            code = ("import os,sys,threading;from pathlib import Path;"
                    f"Path({str(root/'supervisor-started')!r}).write_text(str(os.getpid()));"
                    f"sys.path.insert(0,{str(SCRIPTS)!r});from workflow_unit_budget import supervise;"
                    f"Path({str(root/'supervisor-imported')!r}).write_text(str(os.getpid()));"
                    "cancel=threading.Event()\n"
                    "def request_cancel():\n"
                    # Match the parent's post-readiness cancel handshake.
                    "    import time\n"
                    f"    while not (Path({str(ready)!r}).exists() and Path({str(descendant_ready)!r}).exists()):\n"
                    "        time.sleep(.01)\n"
                    "    if sys.stdin.buffer.readline() == b'cancel\\n':\n"
                    "        cancel.set()\n"
                    "threading.Thread(target=request_cancel,daemon=True).start()\n"
                    f"raise SystemExit(supervise([sys.executable,'-c',{worker!r}],"
                    f"cwd={str(root)!r},directory={str(root/'budget')!r},"
                    "total=15,idle=15,cancel=cancel))")
            (root / "fixture-input.json").write_text(json.dumps({"authorizes": [], "sources": {
                "supervisor": code, "worker": worker, "descendant": descendant}}, sort_keys=True) + "\n", encoding="utf-8")
            process, handles = None, []
            guard = WindowsJob()
            try:
                # The dedicated job is a failure guard only. Product cleanup
                # must finish before this test terminates or closes the job.
                started = time.monotonic()
                process = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE,
                                           stdout=out, stderr=err,
                                           creationflags=subprocess.CREATE_NO_WINDOW | 0x4)
                guard.assign_and_resume(process)
                deadline = time.monotonic() + 5
                while not (ready.exists() and descendant_ready.exists()) and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(.01)
                worker_ready_at_stop, descendant_ready_at_stop = ready.exists(), descendant_ready.exists()
                observation = {"schema": "workflow.cancel-fixture-startup.v1", "authorizes": [],
                               "supervisor_pid": process.pid, "supervisor_exit_code": process.poll(),
                               "elapsed_seconds": time.monotonic() - started,
                               "startup_limit_seconds": 5,
                               "worker_ready_at_stop": worker_ready_at_stop,
                               "descendant_ready_at_stop": descendant_ready_at_stop,
                               "milestones": {name: {"exists": (root / name).exists(),
                                                     "mtime_ns": (root / name).stat().st_mtime_ns if (root / name).exists() else None}
                                              for name in ("supervisor-started", "supervisor-imported", "worker-started", "owned.json", "descendant-ready")}}
                (root / "startup-observation.json").write_text(json.dumps(observation, sort_keys=True) + "\n", encoding="utf-8")
                self.assertTrue(descendant_ready_at_stop, f"the actual owned descendant must start; retained diagnostics: {root}")
                self.assertTrue(worker_ready_at_stop, "the actual owned worker must identify its tree")
                owned = json.loads(ready.read_text())
                self.assertEqual(owned["descendant"], int(descendant_ready.read_text()))
                self.assertEqual(2, len(set(owned.values())))
                for pid in owned.values():
                    # Read-only handles retain these exact live identities;
                    # neither exit checks nor failure cleanup reopen a PID.
                    handle = api.OpenProcess(0x100000 | 0x1000, False, pid)
                    if not handle:
                        raise ctypes.WinError(ctypes.get_last_error())
                    handles.append(handle)
                    belongs = ctypes.c_int()
                    if not api.IsProcessInJob(handle, guard.handle, ctypes.byref(belongs)):
                        raise ctypes.WinError(ctypes.get_last_error())
                    self.assertTrue(belongs.value, "the process must belong to this test's dedicated job")
                    self.assertEqual(0x102, api.WaitForSingleObject(handle, 0),
                                     "the owned process must be alive before cancellation")
                process.stdin.write(b"cancel\n")
                process.stdin.flush()
                self.assertEqual(130, process.wait(timeout=10))
                reports = [p for p in (root / "budget").glob("*.json") if p.name != "budget-ledger.json"]
                self.assertEqual(1, len(reports))
                report = json.loads(reports[0].read_text())
                self.assertEqual(130, report["exit_code"])
                self.assertEqual({"reason": "cancelled"}, report["reason"])
                self.assertEqual([], report["authorizes"])
                self.assertTrue((root / "budget" / "budget-ledger.json").is_file())
                for handle in handles:
                    self.assertEqual(0, api.WaitForSingleObject(handle, 3000),
                                     "product cancellation must stop the owned worker and descendant")
            finally:
                try:
                    # This can never supply the preceding success evidence.
                    guard.terminate()
                finally:
                    try:
                        if process is not None:
                            if process.poll() is None:
                                # A failed assignment leaves only the exact
                                # suspended Popen process outside this job.
                                process.kill()
                            process.wait(timeout=5)
                            process.stdin.close()
                    finally:
                        try:
                            close_error = None
                            for handle in handles:
                                if not api.CloseHandle(handle):
                                    close_error = close_error or ctypes.get_last_error()
                            if close_error is not None:
                                raise ctypes.WinError(close_error)
                        finally:
                            guard.close()

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
