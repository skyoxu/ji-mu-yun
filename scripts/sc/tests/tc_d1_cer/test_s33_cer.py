from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sys
import uuid

import pytest

TOOLS = Path(__file__).resolve().parents[4] / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from current_router import materialize_descriptor
from process_executor_v2 import execute_process


ASSERTION = "A-NFR7-EXTERNAL-PROCESS-BOUNDED"
FAILURE = "F-EXTERNAL-PROCESS-TIMEOUT"


def _bundle() -> dict:
    return {
        "schema_version": "vdd.semantic-plan-bundle.v1",
        "plan_id": "PLAN-7B2637C400E8",
        "obligations": [{
            "obligation_id": "O-A2EB2B214D66",
            "requirement_id": "NFR-7",
            "source_refs": ["assembled-requirements.md#NFR-7"],
            "subject": "Each external process execution",
            "trigger": "execution begins under its configured bound",
            "state_before": "descriptor with timeout/output limit",
            "state_after": "completed or timeout/output-limit terminal state",
            "expected_behavior": "bounded receipt facts",
            "observable_result": "terminal status and bounded elapsed/output facts",
            "forbidden_result": ["process exceeds its time bound", "process remains running"],
            "requirement_type": "Platform",
            "obligation_kind": "non-functional",
            "unresolved_fragments": [],
            "status": "active",
            "depends_on": [],
        }],
        "acceptances": [{
            "acceptance_id": "A-4A962ABEBD9B",
            "obligation_ids": ["O-A2EB2B214D66"],
            "source_refs": ["assembled-requirements.md#NFR-7"],
            "given": "An external process is launched with an applicable timeout and bounded output budget.",
            "when": "The external process execution begins under its configured bound.",
            "then": "The bounded receipt is accepted only for a completed process; timeout is unsuccessful.",
            "oracle": {"observable": "process receipt", "expected": "bounded terminal facts", "forbidden": []},
            "assertion_ids": [ASSERTION],
            "red_intent_ids": ["FI-96B7C538E88C"],
        }],
        "failure_intents": [{
            "failure_intent_id": "FI-96B7C538E88C",
            "acceptance_ids": ["A-4A962ABEBD9B"],
            "failure_id": FAILURE,
            "failure_family": "timeout-no-observation",
            "selector_intent": "sleeping worker exceeds shorter timeout",
            "expected_outcome": "fail",
        }],
        "slices": [{
            "slice_id": "S33",
            "acceptance_ids": ["A-4A962ABEBD9B"],
            "failure_intent_ids": ["FI-96B7C538E88C"],
            "production_owners": [".agents/skills/quick-dev-tdd-adapter/tools/process_executor_v2.py"],
            "allowed_write_paths": ["scripts/sc/tests/tc_d1_cer/test_s33_cer.py"],
            "execution_snapshot_paths": ["worker.py", "fixture.txt"],
            "planned_new_files": ["scripts/sc/tests/tc_d1_cer/test_s33_cer.py"],
            "terminal_predicate": "bounded external process receipt",
        }],
    }


@pytest.mark.cer_assertion("A-NFR7-EXTERNAL-PROCESS-BOUNDED")
def test_external_process_timeout_has_bounded_terminal_receipt() -> None:
    tmp_path = Path.cwd() / f".s33-runtime-{uuid.uuid4().hex}"
    tmp_path.mkdir()
    try:
        worker = tmp_path / "worker.py"
        worker.write_text(
            "import time\nimport pytest\n"
            f"@pytest.mark.cer_assertion('{ASSERTION}')\n"
            "def test_sleeping_worker():\n    time.sleep(2)\n",
            encoding="utf-8",
        )
        fixture = tmp_path / "fixture.txt"
        fixture.write_text("bounded\n", encoding="utf-8")
        descriptor = materialize_descriptor(
            bundle=_bundle(), slice_id="S33", stage="terminal", run_id="RUN-S33",
            candidate_hash="sha256:" + "0" * 64,
            argv=[sys.executable, "-m", "pytest", "worker.py", "-q"], cwd=".",
            timeout_seconds=1, target_refs=["worker.py"], fixture_refs=["fixture.txt"],
        )
        receipt = execute_process(tmp_path, tmp_path / "RUN-S33", "terminal", descriptor, profile_identity="standard")
        started = datetime.fromisoformat(receipt["started_at"].replace("Z", "+00:00")) if receipt.get("started_at") else None
        ended = datetime.fromisoformat(receipt["ended_at"].replace("Z", "+00:00")) if receipt.get("ended_at") else None
        elapsed = (ended - started).total_seconds() if started and ended else None
        bounded = (
            receipt.get("timed_out") is True and receipt.get("process_attempts") == 1
            and receipt.get("exit_code") is None and elapsed is not None
            and elapsed <= descriptor["timeout_seconds"] + 0.5
            and isinstance(receipt.get("elapsed_seconds"), (int, float))
            and receipt["elapsed_seconds"] <= descriptor["timeout_seconds"] + 0.5
            and receipt.get("timeout_seconds") == descriptor["timeout_seconds"]
            and isinstance(receipt.get("output_limit_bytes"), int)
            and receipt["output_limit_bytes"] > 0
            and receipt.get("case_report") is None and receipt.get("cases") == 0
            and len((tmp_path / "RUN-S33" / "canonical-evidence" / "terminal" / "stderr.bin").read_bytes()) < receipt["output_limit_bytes"]
        )
        if not bounded:
            print(f"FAILURE_ID:{FAILURE}")
        assert bounded
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
