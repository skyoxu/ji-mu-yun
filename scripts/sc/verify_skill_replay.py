"""Observable direct replay verification; no lifecycle authority (ADR-0058).

This file is also the explicitly loaded pytest progress plugin. It observes
reports without changing collection, fixtures, outcomes, skips or assertions.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

if __package__:
    from . import skill_replay_runtime as runtime
else:
    import skill_replay_runtime as runtime

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCOPE = ["scripts/sc/tests/test_skill_package_replay.py",
                 "scripts/sc/tests/test_skill_package_replay_source_identity.py",
                 "scripts/sc/tests/tc_d1_cer"]


def emit(value):
    print(json.dumps(value, ensure_ascii=True, sort_keys=True), flush=True)


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write("\n")


class Progress:
    def __init__(self, path):
        self.stream = path.open("x", encoding="utf-8", newline="\n")
        self.trace = path.with_suffix(".traceback.txt").open("x", encoding="utf-8")
        self.trace_stop, self.trace_thread = None, None

    def start_trace(self, interval=60):
        # Accepted ADR-0058: snapshot under the GIL instead of using the C
        # faulthandler watchdog to walk concurrently changing interpreter
        # frames. Pytest's fatal exception handler remains enabled.
        self.stop_trace()
        self.trace_stop = threading.Event()
        stopped = self.trace_stop

        def sample():
            while not stopped.wait(interval):
                self.trace.write("Periodic Python stack snapshot\n")
                for identity, frame in sys._current_frames().items():
                    self.trace.write("Thread " + str(identity) + " (most recent call last):\n")
                    traceback.print_stack(frame, limit=100, file=self.trace)
                self.trace.flush()

        self.trace_thread = threading.Thread(target=sample, name="tc-d1-stack-sampler", daemon=True)
        self.trace_thread.start()

    def stop_trace(self):
        if self.trace_stop is not None:
            self.trace_stop.set()
            self.trace_thread.join(timeout=5)
            if self.trace_thread.is_alive():
                raise RuntimeError("periodic stack sampler did not stop")
            self.trace_stop, self.trace_thread = None, None

    def event(self, kind, **fields):
        value = {"kind": kind, "pid": os.getpid(), "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), **fields}
        self.stream.write(json.dumps(value, ensure_ascii=True) + "\n")
        self.stream.flush()

    def pytest_collection_finish(self, session):
        self.event("collection", nodeids=[item.nodeid for item in session.items])

    def pytest_runtest_logstart(self, nodeid, location):
        self.event("start", nodeid=nodeid)
        self.start_trace()

    def pytest_runtest_setup(self, item):
        self.event("phase", nodeid=item.nodeid, phase="setup")

    def pytest_runtest_call(self, item):
        self.event("phase", nodeid=item.nodeid, phase="call")

    def pytest_runtest_teardown(self, item):
        self.event("phase", nodeid=item.nodeid, phase="teardown")

    def pytest_runtest_logreport(self, report):
        diagnostic = {}
        if report.failed:
            # Pytest prints its failure summary at session end, which may
            # never happen after a later timeout. Preserve bounded details
            # immediately without changing the report or its verdict.
            full = report.longreprtext
            diagnostic = {"failure_detail": full[:32768], "failure_detail_truncated": len(full) > 32768}
        self.event("report", nodeid=report.nodeid, phase=report.when, outcome=report.outcome,
                   duration=report.duration, wasxfail=bool(getattr(report, "wasxfail", False)), **diagnostic)

    def pytest_runtest_logfinish(self, nodeid, location):
        self.stop_trace()
        self.event("finish", nodeid=nodeid)

    def pytest_sessionfinish(self, session, exitstatus):
        self.event("session-finish", exit_code=int(exitstatus))

    def pytest_unconfigure(self, config):
        self.stop_trace()
        self.stream.close()
        self.trace.close()


def pytest_addoption(parser):
    parser.addoption("--tc-d1-progress", action="store", default=None)


def pytest_configure(config):
    destination = config.getoption("--tc-d1-progress")
    if destination:
        config.pluginmanager.register(Progress(Path(destination)), "tc-d1-direct-progress")


def terminate_owned(process, directory):
    """Terminate this launched process tree, never an unrelated worker."""
    if os.name == "nt":
        runtime._terminate_owned(process)
        details = {"method": "terminate-owned-windows-job", "pid": process.pid, "exit_code": 0}
    else:
        runtime._terminate_owned(process)
        details = {"method": "kill-owned-process-tree", "pid": process.pid, "exit_code": 0}
    process.wait(timeout=10)
    return details


def supervise(command, root, directory, *, events=None, test_timeout=300, startup_timeout=300, heartbeat=10):
    directory.mkdir(parents=True, exist_ok=False)
    environment = runtime.child_environment()
    # A verification must not inherit selectors or plugin injection from env.
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    native_traces = directory / "native-processes"
    native_traces.mkdir()
    environment["TC_D1_NATIVE_TRACE_DIR"] = str(native_traces.resolve())
    started, last_print, active_started = time.monotonic(), 0, None
    started_idle = started
    active, phase, offset, pending, records, reason, cleanup = None, "startup", 0, b"", [], None, None
    diagnostic = None
    process = None

    def read_events(now):
        nonlocal offset, pending, active, active_started, phase, started_idle
        if events is None or not events.exists():
            return
        with events.open("rb") as stream:
            stream.seek(offset)
            chunk = stream.read()
        offset += len(chunk)
        lines = (pending + chunk).split(b"\n")
        pending = lines.pop()
        for line in lines:
            record = json.loads(line.decode("utf-8"))
            records.append(record)
            if record["kind"] == "start":
                active, active_started, phase = record["nodeid"], now, "setup"
                emit({"stage": directory.name, "event": "test-start", "nodeid": active})
            elif record["kind"] == "phase":
                phase = record["phase"]
            elif record["kind"] == "finish":
                emit({"stage": directory.name, "event": "test-finish", "nodeid": record["nodeid"]})
                active, active_started, phase, started_idle = None, None, "between-tests", now

    with (directory / "stdout.txt").open("wb") as out, (directory / "stderr.txt").open("wb") as err:
        try:
            process = runtime.start_owned(command, cwd=root, env=environment, stdout=out, stderr=err)
            while True:
                now = time.monotonic()
                read_events(now)
                code = process.poll()
                if code is not None:
                    # The exit can race the preceding read by a few bytes.
                    read_events(time.monotonic())
                    break
                elapsed = now - (active_started if active_started is not None else started_idle)
                if elapsed > (test_timeout if active_started is not None else startup_timeout):
                    reason = "test-timeout" if active_started is not None else "startup-or-idle-timeout"
                    cleanup = terminate_owned(process, directory)
                    break
                if (directory / "stdout.txt").stat().st_size + (directory / "stderr.txt").stat().st_size > 64 * 1024 * 1024:
                    reason = "verification-output-budget-exhausted"
                    cleanup = terminate_owned(process, directory)
                    break
                if now - last_print >= heartbeat:
                    emit({"stage": directory.name, "event": "heartbeat", "pid": process.pid,
                          "nodeid": active, "phase": phase, "elapsed_seconds": round(elapsed, 1)})
                    last_print = now
                time.sleep(0.1)
        except KeyboardInterrupt:
            reason = "operator-interrupted"
            if process is not None and process.poll() is None:
                cleanup = terminate_owned(process, directory)
        except Exception as exc:
            reason, diagnostic = "supervisor-error", str(exc)
            if process is not None and process.poll() is None:
                try:
                    cleanup = terminate_owned(process, directory)
                except Exception as cleanup_error:
                    cleanup = {"error": str(cleanup_error), "pid": process.pid}
        finally:
            if process is not None:
                try:
                    runtime.close_owned(process)
                except Exception as cleanup_error:
                    reason, diagnostic = "supervisor-error", str(cleanup_error)
    result = {"command": command, "exit_code": process.returncode if process else None,
              "reason": reason, "active_nodeid": active, "active_phase": phase, "cleanup": cleanup,
              "records": records, "diagnostic": diagnostic,
              "elapsed_seconds": round(time.monotonic() - started, 3), "authorizes": []}
    save(directory / "process-result.json", result)
    return result


def evaluate_reports(result, expected):
    records = result["records"]
    collection = [r["nodeids"] for r in records if r["kind"] == "collection"]
    finished = [r["nodeid"] for r in records if r["kind"] == "finish"]
    reports = [r for r in records if r["kind"] == "report"]
    phases = {(r["nodeid"], r["phase"]): r for r in reports}
    exact = bool(expected) and len(set(expected)) == len(expected) and collection == [expected] and sorted(finished) == sorted(expected)
    outcomes = all(phases.get((node, phase), {}).get("outcome") == "passed"
                   and not phases.get((node, phase), {}).get("wasxfail", False)
                   for node in expected for phase in ("setup", "call", "teardown"))
    # Subtest reports can precede a passing parent call report. Do not hide
    # their failures/skips by retaining only the last report for that phase.
    outcomes = outcomes and all(r["outcome"] == "passed" and not r["wasxfail"] for r in reports)
    session = [r["exit_code"] for r in records if r["kind"] == "session-finish"]
    valid = exact and outcomes and session == [0] and result["exit_code"] == 0 and result["reason"] is None
    return {"pass": valid, "expected_count": len(expected), "finished_count": len(finished),
            "exact_node_coverage": exact, "all_phases_passed": outcomes,
            "skipped_reports": sum(r["outcome"] == "skipped" for r in reports), "authorizes": []}


def scope_paths(root, scope):
    if not isinstance(scope, list) or not scope or any(not isinstance(s, str) for s in scope):
        raise ValueError("scope must be a nonempty list of repository-relative pytest selectors")
    for selector in scope:
        name = selector.split("::", 1)[0]
        path = runtime.relative(root, name)
        if not path.exists() or not (name.startswith("scripts/sc/tests/") or name.startswith(".agents/skills/")):
            raise ValueError("scope selector is outside repository toolchain tests: " + name)
    return scope


def source_binding(root, scope):
    names = (*runtime.SOURCE_ROOTS, "conftest.py", *(s.split("::", 1)[0] for s in scope))
    return {"head": runtime.git(root, "rev-parse", "HEAD").decode().strip(), "files": runtime.bindings(root, names)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir")
    parser.add_argument("--scope-file", help="JSON array preserving the actual r2 pytest selectors")
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--pytest-only", action="store_true")
    parser.add_argument("--test-timeout", type=float, default=300)
    args = parser.parse_args()
    if not 0 < args.test_timeout <= 3600:
        parser.error("test timeout must be positive and at most 3600 seconds")
    scope = scope_paths(ROOT, json.loads(runtime.relative(ROOT, args.scope_file).read_text(encoding="utf-8")) if args.scope_file else DEFAULT_SCOPE)
    name = args.output_dir or "logs/08-05-real-skill-replay/observable-verification-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    output = runtime.relative(ROOT, name)
    output.mkdir(parents=True, exist_ok=False)
    summary = {"schema": "jimuyun.direct-replay-verification.v1", "status": "incomplete", "scope": scope,
               "expected_count_requested": args.expected_count, "unittest_selected": not args.pytest_only,
               "platform": sys.platform, "formal_workflow_called": False, "live_backend_called": False,
               "C3": "OPEN", "authorizes": []}
    before = None
    try:
        before = source_binding(ROOT, scope)
        save(output / "source-before.json", before)
        emit({"event": "verification-start", "output": name, "scope": scope})
        if not args.pytest_only:
            unit = supervise([sys.executable, "-u", "-B", "-m", "unittest", "discover", "-s", "scripts/sc/tests", "-p", "test_skill_replay_*regressions.py", "-v"], ROOT, output / "unittest")
            summary["unittest"] = {k: unit[k] for k in ("exit_code", "reason")}
            if unit["exit_code"] != 0 or unit["reason"] is not None:
                raise ValueError("unittest did not complete successfully")
            import re
            text = (output / "unittest/stderr.txt").read_text(encoding="utf-8")
            count = re.search(r"^Ran ([0-9]+) tests?\b", text, re.MULTILINE)
            if not count or int(count[1]) < 1 or re.search(r"\bskipped=[1-9][0-9]*", text):
                raise ValueError("unittest scope is empty or contains skipped tests")
            summary["unittest"]["tests"] = int(count[1])
        collection_path = output / "collection-events.jsonl"
        common = [sys.executable, "-u", "-B", "-m", "pytest", "-p", "scripts.sc.verify_skill_replay", "-p", "no:cacheprovider"]
        collected = supervise([*common, "--collect-only", "-q", "--tc-d1-progress", str(collection_path), *scope], ROOT, output / "collection", events=collection_path)
        manifests = [r["nodeids"] for r in collected["records"] if r["kind"] == "collection"]
        if collected["exit_code"] != 0 or collected["reason"] or len(manifests) != 1 or not manifests[0]:
            raise ValueError("pytest collection did not produce one complete nonempty manifest")
        expected = manifests[0]
        summary["collected_count"] = len(expected)
        save(output / "selected-nodeids.json", expected)
        if args.expected_count is not None and args.expected_count != len(expected):
            raise ValueError("collection count differs from the requested verification scope")
        events = output / "pytest-events.jsonl"
        result = supervise([*common, "-vv", "--tb=short", "--tc-d1-progress", str(events), "--junitxml=" + str(output / "junit.xml"), *scope], ROOT, output / "pytest", events=events, test_timeout=args.test_timeout)
        summary["pytest"] = evaluate_reports(result, expected)
        summary["process"] = {k: result[k] for k in ("exit_code", "reason", "active_nodeid", "active_phase", "cleanup")}
        summary["status"] = "direct-validation-passed" if summary["pytest"]["pass"] else "direct-validation-failed"
    except KeyboardInterrupt:
        summary.update(status="operator-interrupted")
    except Exception as exc:
        summary.update(status="blocked", diagnostic=str(exc))
    finally:
        if before is not None:
            try:
                after = source_binding(ROOT, scope)
                save(output / "source-after.json", after)
                summary["source_stable"] = before == after
                if not summary["source_stable"]:
                    summary.update(status="source-changed")
            except Exception as exc:
                summary.update(status="source-check-failed", diagnostic=str(exc))
        save(output / "summary.json", summary)
        emit({"event": "verification-finish", "summary": str(output / "summary.json"), "status": summary["status"]})
    return 0 if summary["status"] == "direct-validation-passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
