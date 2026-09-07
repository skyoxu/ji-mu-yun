from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from current_router import materialize_descriptor
from runtime_evidence import create_json
from stage_pipeline import execute_stage,semantic_assertions


def digest() -> str:
    return "sha256:" + "a" * 64


def bundle() -> dict:
    return {
        "schema_version": "vdd.semantic-plan-bundle.v1",
        "plan_id": "P1",
        "acceptances": [{"acceptance_id": "A-ONE", "assertion_ids": ["AS-1"]}],
        "failure_intents": [
            {"failure_intent_id": "FI-RED-1", "failure_id": "EXPECTED-RED", "failure_family": "expected-red", "acceptance_ids": ["A-ONE"]},
            {"failure_intent_id": "FI-HARNESS", "failure_id": "HARNESS-FAILURE", "failure_family": "test-harness-failure"},
            {"failure_intent_id": "FI-SCOPE", "failure_id": "SCOPE-FAILURE", "failure_family": "artifact-integrity"},
            {"failure_intent_id": "FI-SIGNAL", "failure_id": "SIGNAL-FAILURE", "failure_family": "semantic-contract-gap"},
            {"failure_intent_id": "FI-RED-2", "failure_id": "EXPECTED-RED", "failure_family": "expected-red", "acceptance_ids": ["A-ONE"]},
        ],
        "slices": [{
            "slice_id": "S1",
            "acceptance_ids": ["A-ONE"],
            "failure_intent_ids": ["FI-RED-1", "FI-HARNESS", "FI-SCOPE", "FI-SIGNAL", "FI-RED-2"],
            "execution_snapshot_paths": ["tests/test_one.py", "tests/test_slow.py", "tests/fixture.py"],
            "allowed_write_paths": ["src/value.py"],
        }],
        "final_plan_coverage": [{"slice_id": "S1", "acceptance_id": "A-ONE", "stage_scope": ["red", "green", "refactor", "terminal"]}],
        "agent_contexts": [],
    }


def setup(tmp_path: Path) -> Path:
    (tmp_path / "tests").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "tests" / "fixture.py").write_text("fixture = True\n", encoding="utf-8")
    (tmp_path / "src" / "value.py").write_text("VALUE = 0\n", encoding="utf-8")
    semantic = tmp_path / "semantic.json"
    semantic.write_text(json.dumps(bundle()), encoding="utf-8")
    return semantic


def _red_descriptor(tmp_path: Path, *, run_id: str, target: str, timeout_seconds: int = 10) -> Path:
    descriptor = materialize_descriptor(
        bundle=bundle(),
        slice_id="S1",
        stage="red",
        run_id=run_id,
        candidate_hash=digest(),
        argv=[sys.executable, "-m", "pytest", target, "-q"],
        cwd=".",
        timeout_seconds=timeout_seconds,
        target_refs=[target],
        fixture_refs=["tests/fixture.py"],
    )
    run = tmp_path / run_id
    path = run / "descriptors" / "red.json"
    create_json(path, descriptor)
    return path


def test_red_projection_uses_only_expected_red_family() -> None:
    assertions, expected = semantic_assertions(bundle(), "S1")
    assert assertions == {("A-ONE", "AS-1")}
    assert expected == ["EXPECTED-RED"]


def test_failure_intent_family_is_required() -> None:
    value = bundle()
    del value["failure_intents"][0]["failure_family"]
    with pytest.raises(ValueError, match="failure intent family missing"):
        semantic_assertions(value, "S1")


def test_red_receipt_and_judge_are_separate(tmp_path: Path) -> None:
    semantic = setup(tmp_path)
    (tmp_path / "tests" / "test_one.py").write_text(
        "import pytest\n@pytest.mark.cer_assertion('AS-1')\n"
        "def test_one():\n"
        "    print('FAILURE_ID:EXPECTED-RED')\n"
        "    assert False\n",
        encoding="utf-8",
    )
    path = _red_descriptor(tmp_path, run_id="RUN-1", target="tests/test_one.py")
    run = tmp_path / "RUN-1"
    result = execute_stage(
        workspace=tmp_path,
        semantic_plan=semantic,
        run_dir=run,
        descriptor_path=path,
        profile_identity="standard",
    )
    receipt = json.loads((run / "canonical-evidence/red/process-receipt.v2.json").read_text(encoding="utf-8"))
    observation = json.loads((run / "canonical-evidence/red/observation.v2.json").read_text(encoding="utf-8"))
    assert "verification_outcome" not in receipt
    assert receipt["test_executions"] == 1 and receipt["cases"] == 1
    assert observation["verification_outcome"] == "fail"
    assert observation["failure_family"] == "expected-red"
    assert result["predicate_result"] is True


def test_red_rejects_extra_guard_failure_marker(tmp_path: Path) -> None:
    semantic = setup(tmp_path)
    (tmp_path / "tests" / "test_one.py").write_text(
        "import pytest\n@pytest.mark.cer_assertion('AS-1')\n"
        "def test_one():\n"
        "    print('FAILURE_ID:EXPECTED-RED')\n"
        "    print('FAILURE_ID:SCOPE-FAILURE')\n"
        "    assert False\n",
        encoding="utf-8",
    )
    path = _red_descriptor(tmp_path, run_id="RUN-GUARD", target="tests/test_one.py")
    run = tmp_path / "RUN-GUARD"
    result = execute_stage(
        workspace=tmp_path,
        semantic_plan=semantic,
        run_dir=run,
        descriptor_path=path,
        profile_identity="standard",
    )
    assert result["predicate_result"] is False
    assert result["failure_family"] == "semantic-contract-gap"


def test_timeout_has_zero_cases(tmp_path: Path) -> None:
    semantic = setup(tmp_path)
    (tmp_path / "tests" / "test_slow.py").write_text(
        "import time\n"
        "def test_slow():\n"
        "    time.sleep(5)\n"
        "    print('FAILURE_ID:EXPECTED-RED')\n"
        "    assert False\n",
        encoding="utf-8",
    )
    path = _red_descriptor(tmp_path, run_id="RUN-2", target="tests/test_slow.py", timeout_seconds=1)
    run = tmp_path / "RUN-2"
    result = execute_stage(
        workspace=tmp_path,
        semantic_plan=semantic,
        run_dir=run,
        descriptor_path=path,
        profile_identity="standard",
    )
    receipt = json.loads((run / "canonical-evidence/red/process-receipt.v2.json").read_text(encoding="utf-8"))
    assert receipt["timed_out"] is True
    assert receipt["test_executions"] == 0
    assert receipt["cases"] == 0
    assert result["predicate_result"] is False
    assert result["failure_family"] == "timeout-no-observation"
