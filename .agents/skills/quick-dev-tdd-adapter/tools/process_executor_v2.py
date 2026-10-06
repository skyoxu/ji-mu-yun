"""Executor trust zone for current Quick Dev lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
import uuid
from typing import Any, Mapping

from runtime_evidence import create_immutable, create_json, hash_refs, sha256_bytes, sha256_value, validate_descriptor

PYTEST_COUNT_RE = re.compile(r"(\d+)\s+(passed|failed|errors?|skipped)\b", re.I)
FAILURE_RE = re.compile(r"FAILURE_ID:([A-Z0-9][A-Z0-9._-]*)")
ASSERTION_RE = re.compile(r"ASSERTION_ID:([A-Z0-9][A-Z0-9._-]*)")
OUTPUT_LIMIT_BYTES = 1024 * 1024


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
        "elapsed_seconds":None,"timeout_seconds":descriptor.get("timeout_seconds"),
        "output_limit_bytes":OUTPUT_LIMIT_BYTES,
    }


def _run_cases_bounded(descriptor: Mapping[str, Any], cwd: Path, *, timeout_seconds: int):
    """Run the CER collector with bounded pipes and owned termination."""
    from case_evidence import COLLECTOR
    from runtime_evidence import sha256_value
    argv = descriptor["argv"]
    index = argv.index("-m")
    args = argv[index + 2:]
    request = {"run_id": descriptor["run_id"], "stage": descriptor["stage"],
               "descriptor_sha256": sha256_value(descriptor), "nonce": uuid.uuid4().hex}
    with tempfile.TemporaryDirectory(prefix="quick-dev-case-") as raw:
        root = Path(raw)
        request_path, output_path = root / "request.json", root / "report.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        actual_argv = [*argv[:index], str(COLLECTOR), str(request_path), str(output_path),
                       *args, "--rootdir", str(cwd), "-p", "no:cacheprovider"]
        process = subprocess.Popen(actual_argv, cwd=cwd, shell=False,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        outputs = {"stdout": bytearray(), "stderr": bytearray()}
        overflow = threading.Event()
        terminated = threading.Event()

        def terminate_owned() -> None:
            if terminated.is_set():
                return
            terminated.set()
            if process.poll() is None:
                process.kill()
            if __import__("os").name == "nt":
                # ADR-0041: OS cleanup must not escape the worker time budget.
                try:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   check=False, timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass

        def drain(name: str, pipe) -> None:
            try:
                while True:
                    chunk = pipe.read(65536)
                    if not chunk:
                        break
                    outputs[name].extend(chunk)
                    if len(outputs[name]) > OUTPUT_LIMIT_BYTES:
                        overflow.set()
                        terminate_owned()
                        break
            finally:
                pipe.close()

        threads = [threading.Thread(target=drain, args=(name, pipe), daemon=True)
                   for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr))]
        for thread in threads:
            thread.start()
        timed_out = False
        deadline = time.monotonic() + timeout_seconds
        while process.poll() is None:
            if overflow.is_set():
                terminate_owned()
                break
            if time.monotonic() >= deadline:
                timed_out = True
                terminate_owned()
                break
            time.sleep(0.01)
        if overflow.is_set() or timed_out:
            terminate_owned()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)
        for thread in threads:
            thread.join(timeout=1)
        stdout = bytes(outputs["stdout"][:OUTPUT_LIMIT_BYTES])
        stderr = bytes(outputs["stderr"][:OUTPUT_LIMIT_BYTES])
        result_code = None if timed_out else process.returncode
        if overflow.is_set() and result_code == 0:
            result_code = 74
        completed = subprocess.CompletedProcess(actual_argv, result_code, stdout, stderr)
        report, error = None, None
        try:
            report = json.loads(output_path.read_text(encoding="utf-8"))
            if (not isinstance(report, dict)
                    or any(report.get(key) != value for key, value in request.items())
                    or report.get("exit_code") != (74 if overflow.is_set() and process.returncode == 0 else result_code)
                    or report.get("complete") is not True):
                raise ValueError("incomplete-case-report")
        except (OSError, UnicodeError, ValueError) as exc:
            report, error = None, "case-report-missing-or-invalid:" + str(exc)
        return completed, report, error, actual_argv, overflow.is_set(), timed_out


def _is_run_evidence_path(path: str, run_dir: Path, root: Path) -> bool:
    """Evidence produced by this runner is append-only run state, not SUT noise."""
    try:
        candidate = (root / path).resolve()
        candidate.relative_to(run_dir.resolve())
        return True
    except (OSError, ValueError):
        return False


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
    from case_evidence import validate_contract
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
    started = datetime.now(timezone.utc); started_monotonic = time.monotonic()
    stdout = b""; stderr = b""; timed_out = False; output_budget_exhausted = False; exit_code: int | None
    try:
        (completed, case_report, case_error, actual_argv,
         output_budget_exhausted, timed_out) = _run_cases_bounded(
            descriptor, cwd, timeout_seconds=descriptor["timeout_seconds"])
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
        # ADR-0041: forced termination is not an observed task exit verdict.
        if timed_out:
            exit_code = None
            case_report = None
    except (OSError, ValueError) as exc:
        exit_code = None
        case_error = str(exc)
    except subprocess.TimeoutExpired as exc:
        timed_out, exit_code = True, None; stdout, stderr = exc.stdout or b"", exc.stderr or b""
        if isinstance(stdout,str): stdout=stdout.encode("utf-8",errors="replace")
        if isinstance(stderr,str): stderr=stderr.encode("utf-8",errors="replace")
    ended = datetime.now(timezone.utc); elapsed_seconds = time.monotonic() - started_monotonic
    after_status = _status_paths(root)
    # The current run is deliberately an untracked append-only tree.  Its
    # receipts, observations and outputs are expected writes by this process;
    # only changes outside that tree can be repository noise.
    repo_noise_paths = sorted(
        path for path in (after_status - before_status)
        if not _is_run_evidence_path(path, run_dir, root)
    )
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
        "elapsed_seconds":elapsed_seconds,"timeout_seconds":descriptor["timeout_seconds"],
        "output_limit_bytes":OUTPUT_LIMIT_BYTES,"output_budget_exhausted":output_budget_exhausted,
    }
    create_json(evidence/"process-receipt.v2.json",receipt); return receipt
