"""Executor trust zone for current Quick Dev lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

from runtime_evidence import create_immutable, create_json, hash_refs, sha256_bytes, sha256_value, validate_descriptor

PYTEST_COUNT_RE = re.compile(r"(\d+)\s+(passed|failed|errors?|skipped)\b", re.I)
FAILURE_RE = re.compile(r"FAILURE_ID:([A-Z0-9][A-Z0-9._-]*)")
ASSERTION_RE = re.compile(r"ASSERTION_ID:([A-Z0-9][A-Z0-9._-]*)")


def _status_paths(root: Path) -> set[str]:
    if not (root / ".git").exists():
        return set()
    proc = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=root, shell=False, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise ValueError("git status probe failed")
    result: set[str] = set()
    for line in proc.stdout.splitlines():
        raw = line[3:] if len(line) >= 4 else ""
        raw = raw.split(" -> ", 1)[-1].replace("\\", "/").strip()
        if raw:
            result.add(raw)
    return result


def _counts(output: str, *, timed_out: bool) -> tuple[int, int]:
    # Historical summary parser only; current execution never uses it as proof.
    if timed_out:
        return 0, 0
    total = sum(int(match.group(1)) for match in PYTEST_COUNT_RE.finditer(output))
    return (1 if total > 0 else 0), total


def _pre_execution_receipt(descriptor: Mapping[str, Any], stage: str, profile: str, error_code: str) -> dict[str, Any]:
    return {
        "schema":"quick-dev.process-receipt.v2","stage":stage,"descriptor_ref":"frozen-descriptor",
        "descriptor_sha256":sha256_value(dict(descriptor)),"argv":list(descriptor.get("argv",[])),"cwd":descriptor.get("cwd"),
        "started_at":None,"ended_at":None,"process_attempts":0,"test_executions":0,"cases":0,"exit_code":None,"timed_out":False,
        "stdout_sha256":sha256_bytes(b""),"stderr_sha256":sha256_bytes(b""),"candidate_hash":descriptor.get("candidate_hash"),
        "target_hashes":{},"fixture_hashes":{},"observed_failure_ids":[],"observed_assertion_ids":[],"repo_noise_paths":[],
        "profile_identity":profile,"executor_identity":"quick-dev-process-executor.v2","pre_execution_error_code":error_code,
    }


def execute_process(workspace: Path, run_dir: Path, stage: str, descriptor: Mapping[str, Any], *, profile_identity: str) -> dict[str, Any]:
    evidence = run_dir.resolve() / "canonical-evidence" / stage
    try:
        validate_descriptor(descriptor)
    except ValueError:
        receipt = _pre_execution_receipt(descriptor, stage, profile_identity, "ARTIFACT_INTEGRITY")
        create_immutable(evidence/"stdout.bin",b""); create_immutable(evidence/"stderr.bin",b""); create_json(evidence/"process-receipt.v2.json",receipt); return receipt
    if descriptor["stage"] != stage or descriptor["run_id"] != run_dir.name:
        receipt = _pre_execution_receipt(descriptor, stage, profile_identity, "ARTIFACT_INTEGRITY")
        create_immutable(evidence/"stdout.bin",b""); create_immutable(evidence/"stderr.bin",b""); create_json(evidence/"process-receipt.v2.json",receipt); return receipt
    root = workspace.resolve(); cwd = root if descriptor["cwd"] == "." else (root / descriptor["cwd"]).resolve()
    try:
        cwd.relative_to(root)
        if not cwd.is_dir(): raise ValueError
        target_hashes = hash_refs(root, descriptor["target_refs"]); fixture_hashes = hash_refs(root, descriptor["fixture_refs"])
    except (OSError, ValueError):
        receipt = _pre_execution_receipt(descriptor, stage, profile_identity, "TARGET_BINDING")
        create_immutable(evidence/"stdout.bin",b""); create_immutable(evidence/"stderr.bin",b""); create_json(evidence/"process-receipt.v2.json",receipt); return receipt
    from case_evidence import run_cases, validate_contract
    try:
        validate_contract(descriptor)
    except ValueError:
        receipt = _pre_execution_receipt(descriptor, stage, profile_identity, "CASE_CONTRACT")
        create_immutable(evidence/"stdout.bin", b"")
        create_immutable(evidence/"stderr.bin", b"")
        create_json(evidence/"process-receipt.v2.json", receipt)
        return receipt
    case_report, case_error, actual_argv = None, None, []
    before_status = _status_paths(root)
    started = datetime.now(timezone.utc); stdout = b""; stderr = b""; timed_out = False; exit_code: int | None
    try:
        completed, case_report, case_error, actual_argv = run_cases(descriptor, cwd)
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except (OSError, ValueError) as exc:
        exit_code = None
        case_error = str(exc)
    except subprocess.TimeoutExpired as exc:
        timed_out, exit_code = True, None; stdout, stderr = exc.stdout or b"", exc.stderr or b""
        if isinstance(stdout,str): stdout=stdout.encode("utf-8",errors="replace")
        if isinstance(stderr,str): stderr=stderr.encode("utf-8",errors="replace")
    ended = datetime.now(timezone.utc); after_status = _status_paths(root); repo_noise_paths = sorted(after_status - before_status)
    create_immutable(evidence/"stdout.bin",stdout); create_immutable(evidence/"stderr.bin",stderr)
    output = (stdout+b"\n"+stderr).decode("utf-8",errors="replace")
    if case_report is not None:
        events = case_report.get("events")
        calls = [e for e in events if isinstance(e, Mapping) and e.get("phase") == "call"
                 and isinstance(e.get("node_id"), str)] if isinstance(events, list) else []
        cases = len({e["node_id"] for e in calls})
        executions = int(cases > 0)
    else:
        cases = executions = 0
    receipt = {
        "case_report": case_report, "case_report_error": case_error,
        "case_report_sha256": sha256_value(case_report) if case_report is not None else None,
        "executed_argv": actual_argv,
        "schema":"quick-dev.process-receipt.v2","stage":stage,"descriptor_ref":"frozen-descriptor","descriptor_sha256":sha256_value(dict(descriptor)),
        "argv":list(descriptor["argv"]),"cwd":descriptor["cwd"],"started_at":started.isoformat().replace("+00:00","Z"),"ended_at":ended.isoformat().replace("+00:00","Z"),
        "process_attempts":1,"test_executions":executions,"cases":cases,"exit_code":exit_code,"timed_out":timed_out,
        "stdout_sha256":sha256_bytes(stdout),"stderr_sha256":sha256_bytes(stderr),"candidate_hash":descriptor["candidate_hash"],
        "target_hashes":target_hashes,"fixture_hashes":fixture_hashes,"observed_failure_ids":sorted(set(FAILURE_RE.findall(output))),
        "observed_assertion_ids":sorted(set(ASSERTION_RE.findall(output))),"repo_noise_paths":repo_noise_paths,
        "profile_identity":profile_identity,"executor_identity":"quick-dev-process-executor.v2","pre_execution_error_code":None,
    }
    create_json(evidence/"process-receipt.v2.json",receipt); return receipt
