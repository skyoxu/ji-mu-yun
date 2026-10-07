from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.sc import skill_replay_runtime as runtime


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
FAILURE_ID = "F-F5A025B7814C-1"


def _negative_label_case() -> dict[str, object]:
    return {"case_id": "s38-case", "matrix_case_id": "other-case", "target": TARGET, "capability": CAPABILITY, "expected_exit": 0, "error_label": "mislabeled"}


@pytest.mark.cer_assertion("A-F5A025B7814C-1")
def test_matrix_error_label_invalidates_aggregate_and_is_preserved() -> None:
    matrix = {"schema_version": "jimuyun.stable-candidate-replay-matrix.v2", "cases": [_negative_label_case()], "authorizes": []}
    matrix_path = Path(__file__).with_name(".s38-matrix.json")
    try:
        matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
        result = runtime.capture_process([sys.executable, '-B', str(ENTRY), 'replay-matrix', '--matrix', str(matrix_path.relative_to(ROOT))], ROOT, timeout=90)
    finally:
        matrix_path.unlink(missing_ok=True)
    receipt = json.loads(result.stdout)
    assert isinstance(receipt, dict), "Production entry must return a structured result"
    assertion = (
        result.returncode != 0
        and receipt.get("aggregate_status") == "invalid"
        and "mislabeled" in receipt.get("invalid_reasons", [])
    )
    if not assertion:
        print(f"FAILURE_ID:{FAILURE_ID}")
    assert assertion, receipt
