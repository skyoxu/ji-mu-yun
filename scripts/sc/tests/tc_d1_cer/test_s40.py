"""CER check for finite external-process output enforcement."""
from __future__ import annotations

import shutil
import json
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from current_router import materialize_descriptor
from process_executor_v2 import OUTPUT_LIMIT_BYTES, execute_process

ASSERTION = "NFR7-EXTERNAL-PROCESS-OUTPUT-BOUND"
FAILURE = "NFR7-OUTPUT-BOUND-NOT-ENFORCED"


def _bundle() -> dict:
    return {
        "schema_version": "vdd.semantic-plan-bundle.v1",
        "plan_id": "PLAN-7B2637C400E8",
        "obligations": [{"obligation_id": "O-48EFE4CFB48E", "status": "active"}],
        "acceptances": [{"acceptance_id": "A-223EB5F5B10F", "obligation_ids": ["O-48EFE4CFB48E"], "assertion_ids": [ASSERTION]}],
        "slices": [{"slice_id": "S40", "acceptance_ids": ["A-223EB5F5B10F"], "obligation_ids": ["O-48EFE4CFB48E"], "execution_snapshot_paths": ["worker.py", "fixture.txt"]}],
    }


def _execute_output_case(root: Path, stream: int, count: int, *, pause: bool = False) -> tuple[dict, Path]:
    root.mkdir()
    worker = root / "worker.py"
    worker.write_text(
        "import os, time, pytest\n"
        f"@pytest.mark.cer_assertion('{ASSERTION}')\n"
        "def test_output():\n"
        f"    os.write({stream}, b'x' * {count})\n"
        + ("    time.sleep(8)\n" if pause else ""),
        encoding="utf-8",
    )
    (root / "fixture.txt").write_text("bounded-output\n", encoding="utf-8")
    descriptor = materialize_descriptor(
        bundle=_bundle(), slice_id="S40", stage="terminal", run_id="RUN-S40",
        candidate_hash="sha256:" + "0" * 64,
        argv=[sys.executable, "-m", "pytest", "worker.py", "-q", "-s"], cwd=".",
        timeout_seconds=10, target_refs=["worker.py"], fixture_refs=["fixture.txt"],
    )
    run = root / "RUN-S40"
    return execute_process(root, run, "terminal", descriptor, profile_identity="standard"), run


@pytest.mark.cer_assertion(ASSERTION)
def test_external_process_excess_output_is_unsuccessful_and_bounded() -> None:
    root = ROOT / f".s40-runtime-{uuid.uuid4().hex}"
    root.mkdir()
    try:
        positive, positive_run = _execute_output_case(root / "positive", 1, 128)
        positive_output = (positive_run / "canonical-evidence/terminal/stdout.bin").read_bytes()
        bounded = (positive["exit_code"] == 0 and positive["cases"] == 1
                   and positive["pre_execution_error_code"] is None
                   and b'x' * 128 in positive_output)
        for stream in (1, 2):
            receipt, run = _execute_output_case(
                root / f"excess-{stream}", stream, OUTPUT_LIMIT_BYTES + 4096,
            )
            evidence = run / "canonical-evidence/terminal"
            print(json.dumps({"stream": stream, "exit_code": receipt["exit_code"],
                              "elapsed_seconds": receipt["elapsed_seconds"],
                              "output_budget_exhausted": receipt.get("output_budget_exhausted"),
                              "case_report_exit_code": (receipt["case_report"] or {}).get("exit_code"),
                              "stdout_bytes": (evidence / "stdout.bin").stat().st_size,
                              "stderr_bytes": (evidence / "stderr.bin").stat().st_size}))
            bounded = bounded and (
                receipt["process_attempts"] == 1
                and receipt["pre_execution_error_code"] is None
                and receipt["exit_code"] is not None and receipt["exit_code"] != 0
                and receipt["timed_out"] is False
                and receipt.get("output_budget_exhausted") is True
                and receipt["elapsed_seconds"] < 6
                and receipt["case_report"] is None
                and "case-report-missing-or-invalid" in (receipt.get("case_report_error") or "")
                and receipt.get("output_limit_bytes") == OUTPUT_LIMIT_BYTES
                and len((evidence / "stdout.bin").read_bytes()) <= OUTPUT_LIMIT_BYTES
                and len((evidence / "stderr.bin").read_bytes()) <= OUTPUT_LIMIT_BYTES
                and b'x' * 128 in (evidence / ("stdout.bin" if stream == 1 else "stderr.bin")).read_bytes()
            )
        if not bounded:
            print(f"FAILURE_ID:{FAILURE}")
        assert bounded
    finally:
        shutil.rmtree(root, ignore_errors=True)
