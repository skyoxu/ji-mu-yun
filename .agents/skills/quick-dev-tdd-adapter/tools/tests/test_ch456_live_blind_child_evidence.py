from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "scripts" / "quick_dev" / "run_live_blind_benchmark.py"
SPEC = importlib.util.spec_from_file_location("ch456_live_blind", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_failed_child_structured_evidence_is_preserved() -> None:
    evidence = {
        "schema": MODULE.SCHEMA,
        "task_id": MODULE.TASK_ID,
        "status": "failed",
        "execution_attempted": True,
        "source_head": "a" * 40,
        "under_60_minutes": None,
        "product_acceptance_proven": False,
        "error_type": "RuntimeError",
        "error": "Q2 RED author failed: worker output invalid",
        "authorizes": [],
    }
    stdout = "worker trace\n" + json.dumps(evidence, sort_keys=True) + "\n"
    parsed = MODULE._parse_child_evidence(stdout)
    assert parsed is not None
    assert parsed["status"] == "failed"
    assert parsed["error_type"] == "RuntimeError"
    assert parsed["error"].startswith("Q2 RED author failed")


def test_unstructured_or_wrong_schema_child_output_is_rejected() -> None:
    assert MODULE._parse_child_evidence("plain failure\n") is None
    assert MODULE._parse_child_evidence(json.dumps({"schema": "other.v1", "status": "failed"}) + "\n") is None
