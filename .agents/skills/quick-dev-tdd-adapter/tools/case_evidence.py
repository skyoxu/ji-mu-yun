"""ADR-0041: CER-R1--R3 case proof shared by executor, judge and Q7/Q8."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import uuid
from typing import Mapping

VERSION = "quick-dev.case-contract.v1"
COLLECTOR = Path(__file__).with_name("pytest_case_collector.py")


def contract_for(bundle, assertions):
    from runtime_evidence import sha256_bytes
    bindings = []
    for assertion in assertions:
        aid, sid = assertion["acceptance_id"], assertion["assertion_id"]
        failures = sorted({f["failure_id"] for f in bundle.get("failure_intents", [])
                           if aid in f.get("acceptance_ids", []) and f.get("failure_family") == "expected-red"})
        bindings.append({"acceptance_id": aid, "assertion_id": sid,
                         "marker": sid, "case_ids": [], "expected_failure_ids": failures})
    return {"schema": VERSION, "collector_sha256": sha256_bytes(COLLECTOR.read_bytes()),
            "bindings": bindings}


def validate_contract(descriptor):
    contract = descriptor.get("case_contract")
    if not isinstance(contract, Mapping) or contract.get("schema") != VERSION:
        raise ValueError("case-contract-upgrade-required")
    if set(contract) != {"schema", "collector_sha256", "bindings"}:
        raise ValueError("case-contract-shape")
    from runtime_evidence import HASH_RE
    if not HASH_RE.fullmatch(str(contract.get("collector_sha256", ""))):
        raise ValueError("case-collector-identity-missing")
    rows = contract.get("bindings")
    if not isinstance(rows, list) or not rows:
        raise ValueError("assertion-binding-gap")
    expected = {(a["acceptance_id"], a["assertion_id"]) for a in descriptor["acceptance_assertions"]}
    actual = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {"acceptance_id", "assertion_id", "marker", "case_ids", "expected_failure_ids"}:
            raise ValueError("assertion-binding-shape")
        actual.append((row["acceptance_id"], row["assertion_id"]))
        for field in ("case_ids", "expected_failure_ids"):
            values = row[field]
            if not isinstance(values, list) or any(not isinstance(x, str) or not x for x in values) or len(set(values)) != len(values):
                raise ValueError("assertion-binding-values")
        if row["case_ids"]:
            if row["marker"] is not None or any("::" not in x for x in row["case_ids"]):
                raise ValueError("case-identity-ambiguous")
        elif row["marker"] != row["assertion_id"]:
            raise ValueError("assertion-binding-gap")
    if set(actual) != expected or len(actual) != len(expected):
        raise ValueError("assertion-binding-universe")


def run_cases(descriptor, cwd):
    """Single pytest execution; report is outside the SUT's tracked write set."""
    from runtime_evidence import sha256_bytes, sha256_value
    validate_contract(descriptor)
    if descriptor["case_contract"]["collector_sha256"] != sha256_bytes(COLLECTOR.read_bytes()):
        raise ValueError("case-collector-identity-stale")
    argv = descriptor["argv"]
    try:
        index = argv.index("-m")
    except ValueError as exc:
        raise ValueError("case-adapter-gap: requires Python -m pytest") from exc
    if index + 1 >= len(argv) or argv[index + 1] != "pytest":
        raise ValueError("case-adapter-gap: requires Python -m pytest")
    args = argv[index + 2:]
    if any(x.startswith(("--rootdir", "--reruns", "--count", "--dist", "--numprocesses")) or x in {"-n", "--forked"} for x in args):
        raise ValueError("case-adapter-gap: root override/retry/parallel execution unsupported")
    request = {"run_id": descriptor["run_id"], "stage": descriptor["stage"],
               "descriptor_sha256": sha256_value(descriptor), "nonce": uuid.uuid4().hex}
    with tempfile.TemporaryDirectory(prefix="quick-dev-case-") as raw:
        root = Path(raw)
        request_path, output_path = root / "request.json", root / "report.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        actual_argv = [*argv[:index], str(COLLECTOR), str(request_path), str(output_path),
                       *args, "--rootdir", str(cwd), "-p", "no:cacheprovider"]
        process = subprocess.run(actual_argv, cwd=cwd, shell=False, capture_output=True,
                                 timeout=descriptor["timeout_seconds"], check=False)
        error = None
        report = None
        try:
            report = json.loads(output_path.read_text(encoding="utf-8"))
            if not isinstance(report, dict) or any(report.get(k) != v for k, v in request.items()):
                raise ValueError("stale-case-report")
            if report.get("exit_code") != process.returncode or report.get("complete") is not True:
                raise ValueError("incomplete-case-report")
        except (OSError, UnicodeError, ValueError) as exc:
            report, error = None, "case-report-missing-or-invalid:" + str(exc)
        return process, report, error, actual_argv


def assertion_cases(descriptor, receipt, *, keys=None, expected=None):
    """Return admissible node IDs per assertion or precise fail-closed diagnostics."""
    from runtime_evidence import sha256_value, sha256_bytes
    validate_contract(descriptor)
    if descriptor["case_contract"]["collector_sha256"] != sha256_bytes(COLLECTOR.read_bytes()):
        raise ValueError("case-collector-identity-stale")
    report = receipt.get("case_report")
    if not isinstance(report, Mapping):
        raise ValueError(receipt.get("case_report_error") or "case-report-missing")
    if report.get("schema") != "quick-dev.pytest-case-report.v1" or report.get("complete") is not True:
        raise ValueError("case-report-incomplete")
    report_descriptor = descriptor
    if receipt.get("execution_reference") is not None:
        from shared_execution import validate_use
        report_descriptor = validate_use(descriptor, receipt)
    if (report.get("descriptor_sha256") != sha256_value(report_descriptor)
            or report.get("run_id") != report_descriptor["run_id"] or report.get("stage") != report_descriptor["stage"]
            or report.get("exit_code") != receipt.get("exit_code")
            or receipt.get("case_report_sha256") != sha256_value(report)):
        raise ValueError("stale-case-evidence")
    collected, selected, events = report.get("collected"), report.get("selected"), report.get("events")
    if not isinstance(collected, dict) or not isinstance(selected, list) or not isinstance(events, list) or report.get("errors") != []:
        raise ValueError("case-report-shape-or-collection-error")
    if any(not isinstance(node, str) or not isinstance(marks, list)
           or any(not isinstance(mark, str) for mark in marks) for node, marks in collected.items()):
        raise ValueError("case-collection-shape")
    if any(not isinstance(node, str) for node in selected):
        raise ValueError("case-selection-shape")
    if len(set(selected)) != len(selected) or not set(selected) <= set(collected):
        raise ValueError("case-selection-invalid")
    phases = {}
    for event in events:
        if not isinstance(event, Mapping):
            raise ValueError("case-event-shape")
        node, phase = event.get("node_id"), event.get("phase")
        if not isinstance(node, str) or not isinstance(phase, str):
            raise ValueError("case-event-shape")
        if node not in selected or phase not in {"setup", "call", "teardown"}:
            raise ValueError("case-event-identity")
        key = (node, phase)
        if key in phases:
            raise ValueError("case-attempt-ambiguous:" + node)
        phases[key] = event
    result = {}
    mode = expected or ("partial-red" if descriptor["stage"] == "red" and "behavior_route" in descriptor
                        else "red" if descriptor["stage"] == "red" else "pass")
    failed = False
    for row in descriptor["case_contract"]["bindings"]:
        if keys is not None and (row["acceptance_id"], row["assertion_id"]) not in keys:
            continue
        nodes = row["case_ids"] or sorted(node for node, marks in collected.items() if row["marker"] in marks)
        if not nodes:
            raise ValueError("assertion-binding-gap:" + row["assertion_id"])
        for node in nodes:
            if node not in collected or node not in selected:
                raise ValueError("case-missing-or-deselected:" + node)
            from runtime_evidence import safe_relative
            file_ref = safe_relative(node.split("::", 1)[0])
            if descriptor["cwd"] != ".":
                file_ref = safe_relative(descriptor["cwd"] + "/" + file_ref)
            if file_ref not in receipt.get("target_hashes", {}):
                raise ValueError("case-target-unbound:" + node)
            parts = [phases.get((node, p)) for p in ("setup", "call", "teardown")]
            if any(p is not None and p.get("outcome") == "skipped" for p in parts):
                raise ValueError("case-skipped:" + node)
            if any(p is None for p in parts):
                raise ValueError("case-not-executed:" + node)
            setup, call, teardown = parts
            if any(p.get("xfail") is not False for p in parts):
                raise ValueError("case-xfail-unsupported:" + node)
            if setup.get("outcome") != "passed" or teardown.get("outcome") != "passed":
                raise ValueError("case-setup-or-teardown-error:" + node)
            if call.get("outcome") == "skipped":
                raise ValueError("case-skipped:" + node)
            if mode == "partial-red" and call.get("outcome") == "passed":
                continue
            if mode in {"red", "partial-red"}:
                required = row["expected_failure_ids"]
                if not isinstance(call.get("failure_ids"), list):
                    raise ValueError("case-failure-identity-invalid:" + node)
                if (call.get("outcome") != "failed" or call.get("assertion_failure") is not True
                        or not required or not set(required) <= set(call.get("failure_ids", []))):
                    raise ValueError("case-unexpected-red:" + node)
                failed = True
            elif call.get("outcome") != "passed":
                raise ValueError("case-unexpected-outcome:" + node)
        result[(row["acceptance_id"], row["assertion_id"])] = sorted(nodes)
    if mode == "partial-red" and not failed:
        raise ValueError("case-unexpected-green")
    return result


def case_outcomes(receipt, cases):
    """Project call outcomes only after assertion_cases validated the receipt."""
    calls = {e["node_id"]: e["outcome"] for e in receipt["case_report"]["events"] if e["phase"] == "call"}
    return [{"acceptance_id": a, "assertion_id": s, "case_id": node, "outcome": calls[node]}
            for (a, s), nodes in sorted(cases.items()) for node in nodes]


def reread_stage_cases(run_root, stage):
    """Prevent current successors from reusing pre-CER stage-only proof."""
    from runtime_evidence import load_json, sha256_value
    descriptor = load_json(run_root / "descriptors" / (stage + ".json"))
    receipt = load_json(run_root / "canonical-evidence" / stage / "process-receipt.v2.json")
    result = load_json(run_root / "canonical-evidence" / stage / "stage-result.v2.json")
    if result.get("receipt_sha256") != sha256_value(receipt) or result.get("descriptor_sha256") != sha256_value(descriptor):
        raise ValueError("case-predecessor-stale")
    return assertion_cases(descriptor, receipt)
