"""Verify original native files before publishing append-only evidence (ADR-0058)."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
SOURCE = "8d9893054d7fdbb3120e4457128e6ac0bca83bde"
ORIGINAL_MANIFEST_SHA256 = "6a6f4ac8c8825522c83c44410b9de8cfdf7fd50e1ea5b5a52b7f91169eac7232"


def read(path):
    return json.loads(path.read_bytes())


def save_new(path, value):
    raw = (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(raw)


def inspect(name, expected_count, require_unittest=False):
    run = RUN / name
    summary = read(run / "summary.json")
    assert summary["status"] == "direct-validation-passed", summary
    assert summary["platform"] == "linux", summary
    assert summary["collected_count"] == expected_count
    assert summary["expected_count_requested"] == expected_count
    assert summary["source_stable"] is True
    assert summary["C3"] == "OPEN" and summary["authorizes"] == []
    assert not summary["formal_workflow_called"] and not summary["live_backend_called"]
    assert summary["pytest"] == {
        "pass": True, "expected_count": expected_count,
        "finished_count": expected_count, "exact_node_coverage": True,
        "all_phases_passed": True, "skipped_reports": 0, "authorizes": [],
    }
    before = read(run / "source-before.json")
    after = read(run / "source-after.json")
    assert before == after and before["head"] == SOURCE
    assert (run / "source-before.json").read_bytes() == (run / "source-after.json").read_bytes()
    nodes = read(run / "selected-nodeids.json")
    assert len(nodes) == len(set(nodes)) == expected_count
    events = [json.loads(line) for line in (run / "pytest-events.jsonl").read_bytes().splitlines()]
    process = read(run / "pytest/process-result.json")
    assert process["records"] == events
    assert process["exit_code"] == 0 and process["reason"] is None and process["cleanup"] is None
    assert summary["process"]["exit_code"] == 0 and summary["process"]["reason"] is None
    assert summary["process"]["cleanup"] is None
    assert [e["nodeids"] for e in events if e["kind"] == "collection"] == [nodes]
    assert [e["nodeid"] for e in events if e["kind"] == "start"] == nodes
    assert [e["nodeid"] for e in events if e["kind"] == "finish"] == nodes
    reports = [e for e in events if e["kind"] == "report"]
    assert len(reports) == 3 * expected_count
    assert all(e["outcome"] == "passed" and not e.get("wasxfail") for e in reports)
    assert Counter((e["nodeid"], e["phase"]) for e in reports) == Counter(
        (node, phase) for node in nodes for phase in ("setup", "call", "teardown")
    )
    assert [e["exit_code"] for e in events if e["kind"] == "session-finish"] == [0]
    xml = ET.parse(run / "junit.xml").getroot()
    counts = {key: sum(int(s.attrib[key]) for s in xml.iter("testsuite"))
              for key in ("tests", "errors", "failures", "skipped")}
    assert counts == {"tests": expected_count, "errors": 0, "failures": 0, "skipped": 0}
    cases = list(xml.iter("testcase"))
    assert len(cases) == expected_count
    assert all(not list(case.iter(tag)) for case in cases for tag in ("failure", "error", "skipped"))
    junit_ids = [case.attrib["classname"] + "::" + case.attrib["name"] for case in cases]
    expected_ids = [node.split("::")[0][:-3].replace("/", ".")
                    + ("." + ".".join(node.split("::")[1:-1]) if len(node.split("::")) > 2 else "")
                    + "::" + node.split("::")[-1] for node in nodes]
    assert junit_ids == expected_ids
    starts = {e["nodeid"]: e for e in events if e["kind"] == "start"}
    finishes = {e["nodeid"]: e for e in events if e["kind"] == "finish"}
    durations = [{"nodeid": node, "native_event_duration_seconds": round(
        (datetime.fromisoformat(finishes[node]["utc"]) - datetime.fromisoformat(starts[node]["utc"])).total_seconds(), 6)}
        for node in nodes if "/test_s17.py::" in node or "/test_s44.py::test_fresh_checkout_contains_coverage_and_identity" in node]
    audit = {
        "schema": "jimuyun.direct-evidence-consistency.v1", "source_commit": SOURCE,
        "status": summary["status"], "finished_nodes": expected_count,
        "phase_reports": len(reports), "junit": counts,
        "junit_ordered_identity_matches_manifest": True,
        "source_before_after_raw_bytes_equal": True, "bound_source_files": len(before["files"]),
        "native_pytest_elapsed_seconds": process["elapsed_seconds"],
        "timeout_regression_nodes": durations, "independently_inspected_native_files": True,
        "native_windows_verified": False, "C3": "OPEN", "Acceptance": "blocked", "authorizes": [],
    }
    if require_unittest:
        assert summary["unittest"] == {"exit_code": 0, "reason": None, "tests": 36}
        unit = read(run / "unittest/process-result.json")
        assert unit["exit_code"] == 0 and unit["reason"] is None
        raw = (run / "unittest/stderr.txt").read_bytes()
        assert re.search(rb"^Ran 36 tests\b", raw, re.M) and re.search(rb"^OK$", raw, re.M)
        assert not re.search(rb"skipped=[1-9]", raw)
        audit["unittest_passed"] = 36
        node_bytes = (run / "selected-nodeids.json").read_bytes()
        assert hashlib.sha256(node_bytes).hexdigest() == ORIGINAL_MANIFEST_SHA256
        assert node_bytes == (RUN / "recovered-interrupted-run/selected-nodeids.json").read_bytes()
        audit["ordered_manifest_raw_sha256"] = ORIGINAL_MANIFEST_SHA256
        audit["original_340_node_manifest_byte_identical"] = True
    save_new(run / "consistency-audit.json", audit)
    return audit


if __name__ == "__main__":
    full = inspect("full", 340, require_unittest=True)
    targeted = inspect("targeted", 5)
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == SOURCE
    assert subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ROOT).returncode == 0
    observation = read(RUN / "recovered-interrupted-run/recovery-observation.json")
    assert observation["status"] == "incomplete-no-native-terminal-result" and observation["finished_nodes"] == 292
    for row in observation["copy_sha256_manifest"]:
        path = RUN / "recovered-interrupted-run" / row["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    save_new(RUN / "closeout.json", {
        "schema": "jimuyun.direct-repair-closeout.v1", "source_commit": SOURCE,
        "full": full, "targeted": targeted, "recovered_interrupted_run_finished_nodes": 292,
        "historical_evidence_rewritten": False, "formal_workflow_called": False,
        "live_backend_called": False, "native_windows_verified": False,
        "C3": "OPEN", "Acceptance": "blocked", "authorizes": [],
    })
    print(json.dumps({"source_commit": SOURCE, "unittest": 36, "pytest": 340,
                      "targeted": 5, "native_junit_verified": True, "source_stable": True,
                      "C3": "OPEN", "Acceptance": "blocked"}))
