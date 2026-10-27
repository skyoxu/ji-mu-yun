"""ADR-0041: owned pytest adapter; stdout markers never create case results."""
from __future__ import annotations

import json
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys

import pytest


class DependencyReads:
    """Bounded observation, never an execution sandbox or a test verdict."""
    def __init__(self):
        self.reads = {}
        self.writes = set()
        self.errors = set()
        self.busy = False
        self.bytes = 0

    def audit(self, event, args):
        if self.busy:
            return
        if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "socket.connect"}:
            self.errors.add("reuse-unobserved-external-effect:" + event)
        if event != "open" or not isinstance(args[0], (str, bytes)):
            return
        self.busy = True
        try:
            path = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1:3]
            if (isinstance(mode, str) and any(c in mode for c in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR):
                self.writes.add(str(path))
                return
            if str(path) in self.writes or path.suffix == ".pyc" or not path.is_file():
                return
            if str(path) not in self.reads:
                self.bytes += path.stat().st_size
                if len(self.reads) >= 50000 or self.bytes > 512 * 1024 * 1024:
                    self.errors.add("reuse-read-observation-budget-exceeded")
                    return
                self.reads[str(path)] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, ValueError):
            self.errors.add("reuse-read-observation-incomplete")
        finally:
            self.busy = False


class Collector:
    def __init__(self):
        self.collected = {}
        self.selected = []
        self.events = []
        self.errors = []

    def pytest_configure(self, config):
        config.addinivalue_line("markers", "cer_assertion(*ids): bind cases to semantic assertions")

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_collection_modifyitems(self, session, config, items):
        # Snapshot before -k/-m deselection. Missing parameter instances remain visible.
        for item in items:
            if item.nodeid in self.collected:
                self.errors.append("duplicate-case:" + item.nodeid)
            self.collected[item.nodeid] = sorted({
                str(arg) for mark in item.iter_markers("cer_assertion") for arg in mark.args
            })
        yield
        self.selected = [item.nodeid for item in items]

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append("collection-error:" + report.nodeid)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        assertion_failure = bool(call.excinfo and call.excinfo.errisinstance(AssertionError))
        output = "\n".join(text for name, text in report.sections if name in {"Captured stdout call", "Captured stderr call"})
        self.events.append({
            "node_id": report.nodeid, "phase": report.when, "outcome": report.outcome,
            "xfail": hasattr(report, "wasxfail") or bool(list(item.iter_markers("xfail"))),
            "assertion_failure": assertion_failure,
            "failure_ids": sorted(set(re.findall(r"FAILURE_ID:([A-Z0-9][A-Z0-9._-]*)", output)))
            if report.when == "call" and report.failed and assertion_failure else [],
        })


def main():
    sys.path.insert(0, str(Path.cwd()))
    request_path, output_path, *args = sys.argv[1:]
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    collector = Collector()
    reads = DependencyReads()
    sys.addaudithook(reads.audit)
    code = int(pytest.main(args, plugins=[collector]))
    reads.busy = True  # Freeze observation before hashing/report output.
    dependencies = dict(reads.reads)
    for module in list(sys.modules.values()):
        raw = getattr(module, "__file__", None)
        if not isinstance(raw, str):
            continue
        path = Path(raw)
        if path.suffix == ".pyc":
            try:
                path = Path(importlib.util.source_from_cache(str(path)))
            except ValueError:
                pass
        if path.is_file():
            dependencies[str(path.resolve())] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    report = {**request, "dependency_files": dependencies, "dependency_errors": sorted(reads.errors), "schema": "quick-dev.pytest-case-report.v1", "complete": True,
              "exit_code": code, "collected": collector.collected,
              "selected": collector.selected, "events": collector.events,
              "errors": collector.errors}
    with Path(output_path).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, sort_keys=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
