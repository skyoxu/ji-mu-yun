"""ADR-0041: owned pytest adapter; stdout markers never create case results."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

import pytest


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
    code = int(pytest.main(args, plugins=[collector]))
    report = {**request, "schema": "quick-dev.pytest-case-report.v1", "complete": True,
              "exit_code": code, "collected": collector.collected,
              "selected": collector.selected, "events": collector.events,
              "errors": collector.errors}
    with Path(output_path).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, sort_keys=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
