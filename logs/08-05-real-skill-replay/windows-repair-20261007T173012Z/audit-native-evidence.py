"""Audit exact fixed-source native files; no execution authority (ADR-0058)."""
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
SOURCE = "ae311a29b15c8c75fb0dcaaa1c57c8cb9bd5ac7e"
ORIGINAL_MANIFEST_SHA256 = "6a6f4ac8c8825522c83c44410b9de8cfdf7fd50e1ea5b5a52b7f91169eac7232"


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write("\n")


def junit(path, count):
    xml = ET.parse(path).getroot()
    counts = {key: sum(int(s.attrib[key]) for s in xml.iter("testsuite"))
              for key in ("tests", "errors", "failures", "skipped")}
    assert counts == {"tests": count, "errors": 0, "failures": 0, "skipped": 0}
    cases = list(xml.iter("testcase"))
    assert len(cases) == count and all(not list(case.iter(tag))
        for case in cases for tag in ("failure", "error", "skipped"))
    return counts, [case.attrib["classname"] + "::" + case.attrib["name"] for case in cases]


if __name__ == "__main__":
    run = RUN / "full"
    summary = read(run / "summary.json")
    assert summary["status"] == "direct-validation-passed", summary
    assert summary["platform"] == "linux" and summary["source_stable"] is True
    assert summary["collected_count"] == summary["expected_count_requested"] == 340
    assert summary["C3"] == "OPEN" and summary["authorizes"] == []
    assert not summary["formal_workflow_called"] and not summary["live_backend_called"]
    assert summary["pytest"] == {"pass": True, "expected_count": 340,
        "finished_count": 340, "exact_node_coverage": True, "all_phases_passed": True,
        "skipped_reports": 0, "authorizes": []}
    before, after = read(run / "source-before.json"), read(run / "source-after.json")
    assert before == after and before["head"] == SOURCE
    assert (run / "source-before.json").read_bytes() == (run / "source-after.json").read_bytes()
    node_bytes = (run / "selected-nodeids.json").read_bytes()
    assert hashlib.sha256(node_bytes).hexdigest() == ORIGINAL_MANIFEST_SHA256
    nodes = json.loads(node_bytes)
    assert len(nodes) == len(set(nodes)) == 340
    events = [json.loads(line) for line in (run / "pytest-events.jsonl").read_bytes().splitlines()]
    process = read(run / "pytest/process-result.json")
    assert process["records"] == events and process["exit_code"] == 0
    assert process["reason"] is None and process["cleanup"] is None
    assert summary["process"]["exit_code"] == 0 and summary["process"]["reason"] is None
    assert [e["nodeids"] for e in events if e["kind"] == "collection"] == [nodes]
    assert [e["nodeid"] for e in events if e["kind"] == "start"] == nodes
    assert [e["nodeid"] for e in events if e["kind"] == "finish"] == nodes
    reports = [e for e in events if e["kind"] == "report"]
    assert len(reports) == 1020 and all(e["outcome"] == "passed" and not e.get("wasxfail") for e in reports)
    assert Counter((e["nodeid"], e["phase"]) for e in reports) == Counter(
        (node, phase) for node in nodes for phase in ("setup", "call", "teardown"))
    assert [e["exit_code"] for e in events if e["kind"] == "session-finish"] == [0]
    counts, ids = junit(run / "junit.xml", 340)
    expected_ids = [node.split("::")[0][:-3].replace("/", ".")
        + ("." + ".".join(node.split("::")[1:-1]) if len(node.split("::")) > 2 else "")
        + "::" + node.split("::")[-1] for node in nodes]
    assert ids == expected_ids
    assert summary["unittest"] == {"exit_code": 0, "reason": None, "tests": 41}
    unit = read(run / "unittest/process-result.json")
    assert unit["exit_code"] == 0 and unit["reason"] is None
    raw = (run / "unittest/stderr.txt").read_bytes()
    assert re.search(rb"^Ran 41 tests\b", raw, re.M) and re.search(rb"^OK$", raw, re.M)
    assert not re.search(rb"skipped=[1-9]", raw)
    controls, _ = junit(RUN / "process-controls-junit.xml", 22)
    original_failed = {row["nodeid"] for row in read(RUN / "failure-analysis.json")["failed_nodes"]}
    assert len(original_failed) == 54 and original_failed.issubset(set(nodes))
    native = []
    for path in sorted(run.glob("*/native-processes/*.jsonl")):
        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
        assert rows[0]["phase"] == "started" and rows[0]["pid"] != rows[0]["parent_pid"]
        assert all(row["pid"] == rows[0]["pid"] and row["parent_pid"] == rows[0]["parent_pid"]
                   and row["authorizes"] == [] for row in rows)
        assert len(rows) == 2 and rows[1]["phase"] in {"exited", "unsuccessful"}, (path, rows)
        native.append({"path": path.relative_to(RUN).as_posix(), "pid": rows[0]["pid"],
                       "parent_pid": rows[0]["parent_pid"], "terminal_phase": rows[1]["phase"],
                       "exit_code": rows[1].get("exit_code"), "exception": rows[1].get("exception")})
    starts = {e["nodeid"]: e for e in events if e["kind"] == "start"}
    finishes = {e["nodeid"]: e for e in events if e["kind"] == "finish"}
    durations = [{"nodeid": node, "native_seconds": (
        datetime.fromisoformat(finishes[node]["utc"]) - datetime.fromisoformat(starts[node]["utc"])).total_seconds()}
        for node in nodes if node in original_failed or "/test_s17.py::" in node
        or node.endswith("test_s7_detached_probe_binds_input_target_outcome_and_output")]
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == SOURCE
    assert subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ROOT).returncode == 0
    audit = {"schema": "jimuyun.direct-evidence-consistency.v1", "source_commit": SOURCE,
        "status": summary["status"], "platform": "linux", "unittest_passed": 41,
        "pytest_passed": 340, "phase_reports": 1020, "junit": counts,
        "targeted_process_controls": controls, "ordered_manifest_raw_sha256": ORIGINAL_MANIFEST_SHA256,
        "original_340_node_manifest_byte_identical": True, "junit_ordered_identity_matches_manifest": True,
        "source_before_after_raw_bytes_equal": True, "bound_source_files": len(before["files"]),
        "native_pytest_elapsed_seconds": process["elapsed_seconds"],
        "windows_previously_failed_nodes_passed_on_linux": 54, "observed_node_durations": durations,
        "native_diagnostic_file_count": len(native), "native_diagnostic_lifecycle_counts": dict(Counter(row["terminal_phase"] for row in native)),
        "native_windows_verified": False, "historical_evidence_rewritten": False,
        "formal_workflow_called": False, "live_backend_called": False,
        "C3": "OPEN", "Acceptance": "blocked", "authorizes": []}
    save(run / "native-process-diagnostic-audit.json", {"processes": native, "authorizes": []})
    save(run / "consistency-audit.json", audit)
    save(RUN / "closeout.json", audit)
    print(json.dumps({key: audit[key] for key in ("source_commit", "unittest_passed", "pytest_passed",
        "phase_reports", "native_diagnostic_file_count", "native_windows_verified", "C3", "Acceptance")}))
