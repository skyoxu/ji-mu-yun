from __future__ import annotations

import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from current_router import materialize_descriptor, successor_descriptor
from regression_gate import run_regression_gate
from runtime_evidence import create_json
from stage_pipeline import execute_stage


def _bundle(validation_commands: list[list[str]] | None, *, include_context: bool = True) -> dict:
    contexts = []
    if include_context:
        contexts = [{
            "slice_id": "S1",
            "requirement_ids": ["FR-1"],
            "obligation_ids": ["O-1"],
            "acceptance_ids": ["A-1"],
            "source_refs": ["requirements.md#FR-1"],
            "contracts": ["semantic-plan-bundle.v1.json"],
            "allowed_paths": ["src/value.txt"],
            "forbidden_paths": [],
            "selector_intents": ["tests/test_behavior.py"],
            "validation_commands": validation_commands or [],
        }]
    return {
        "schema_version": "vdd.semantic-plan-bundle.v1",
        "plan_id": "PLAN-Q6",
        "obligations": [{"obligation_id": "O-1", "requirement_id": "FR-1", "source_refs": ["requirements.md#FR-1"]}],
        "acceptances": [{"acceptance_id": "A-1", "obligation_ids": ["O-1"], "assertion_ids": ["ASSERT-1"]}],
        "failure_intents": [{"failure_intent_id": "FI-1", "acceptance_ids": ["A-1"], "failure_id": "EXPECTED-Q6", "failure_family": "expected-red", "selector_intent": "tests/test_behavior.py", "expected_outcome": "fail"}],
        "slices": [{
            "slice_id": "S1",
            "acceptance_ids": ["A-1"],
            "failure_intent_ids": ["FI-1"],
            "execution_snapshot_paths": ["tests/test_behavior.py", "tests/fixture.txt"],
            "allowed_write_paths": ["src/value.txt"],
        }],
        "final_plan_coverage": [{"slice_id": "S1", "acceptance_id": "A-1", "stage_scope": ["red", "green", "refactor", "terminal"]}],
        "agent_contexts": contexts,
    }


def _prepare(root: Path, bundle: dict) -> tuple[Path, Path]:
    (root / "src").mkdir()
    (root / "tests").mkdir()
    run = root / "runs" / "R1"
    (run / "descriptors").mkdir(parents=True)
    (root / "src" / "value.txt").write_text("red\n", encoding="utf-8")
    (root / "tests" / "fixture.txt").write_text("fixture\n", encoding="utf-8")
    (root / "tests" / "test_behavior.py").write_text(
        "from pathlib import Path\n"
        "import pytest\n@pytest.mark.cer_assertion('ASSERT-1')\n"
        "def test_behavior():\n"
        " root=Path(__file__).resolve().parents[1]\n"
        " value=(root/'src'/'value.txt').read_text(encoding='utf-8').strip()\n"
        " if value!='green': print('FAILURE_ID:EXPECTED-Q6')\n"
        " assert value=='green'\n",
        encoding="utf-8",
    )
    semantic = root / "semantic-plan-bundle.v1.json"
    semantic.write_text(json.dumps(bundle), encoding="utf-8")
    red = materialize_descriptor(
        bundle=bundle,
        slice_id="S1",
        stage="red",
        run_id="R1",
        candidate_hash="sha256:" + "1" * 64,
        argv=[sys.executable, "-m", "pytest", "tests/test_behavior.py", "-q"],
        cwd=".",
        timeout_seconds=30,
        target_refs=["tests/test_behavior.py"],
        fixture_refs=["tests/fixture.txt"],
    )
    refactor = successor_descriptor(red, stage="refactor", run_id="R1", candidate_hash="sha256:" + "2" * 64)
    create_json(run / "descriptors" / "red.json", red)
    create_json(run / "descriptors" / "refactor.json", refactor)
    red_result = execute_stage(workspace=root, semantic_plan=semantic, run_dir=run, descriptor_path=run / "descriptors" / "red.json", profile_identity="standard")
    assert red_result["failure_family"] == "expected-red" and red_result["predicate_result"] is True
    (root / "src" / "value.txt").write_text("green\n", encoding="utf-8")
    return semantic, run


def test_standard_q6_requires_agent_context_and_publishes_no_refactor_result_without_it(tmp_path: Path) -> None:
    semantic, run = _prepare(tmp_path, _bundle([], include_context=False))
    try:
        execute_stage(workspace=tmp_path, semantic_plan=semantic, run_dir=run, descriptor_path=run / "descriptors" / "refactor.json", profile_identity="standard")
    except ValueError as exc:
        assert "agent-context regression projection" in str(exc)
    else:
        raise AssertionError("standard Q6 must reject missing agent-context regression projection")
    assert not (run / "canonical-evidence" / "refactor" / "stage-result.v2.json").exists()
    assert not (run / "canonical-evidence" / "refactor" / "runtime-edges").exists()


def test_q6_failed_declared_regression_blocks_refactor_result(tmp_path: Path) -> None:
    primary = [sys.executable, "-m", "pytest", "tests/test_behavior.py", "-q"]
    failing = [sys.executable, "-c", "raise SystemExit(7)"]
    semantic, run = _prepare(tmp_path, _bundle([primary, failing]))
    try:
        execute_stage(workspace=tmp_path, semantic_plan=semantic, run_dir=run, descriptor_path=run / "descriptors" / "refactor.json", profile_identity="standard")
    except ValueError as exc:
        assert "regression/schema command failed" in str(exc)
    else:
        raise AssertionError("failing Q6 regression command must block REFACTOR publication")
    assert not (run / "canonical-evidence" / "refactor" / "stage-result.v2.json").exists()
    assert not (run / "canonical-evidence" / "refactor" / "runtime-edges").exists()


def test_fast_ship_skips_extra_declared_regressions_but_keeps_primary_truth_floor(tmp_path: Path) -> None:
    primary = [sys.executable, "-m", "pytest", "tests/test_behavior.py", "-q"]
    failing_extra = [sys.executable, "-c", "raise SystemExit(7)"]
    bundle = _bundle([primary, failing_extra])
    result = run_regression_gate(
        workspace=tmp_path,
        bundle=bundle,
        slice_id="S1",
        profile="fast-ship",
        primary_argv=primary,
        primary_receipt={
            "exit_code": 0,
            "timed_out": False,
            "test_executions": 1,
            "cases": 1,
            "stdout_sha256": "sha256:" + "a" * 64,
            "stderr_sha256": "sha256:" + "b" * 64,
        },
        timeout_seconds=30,
        out=tmp_path / "q6.json",
    )
    assert result["status"] == "pass"
    assert result["declared_command_count"] == 2
    assert len(result["commands"]) == 1
    assert result["commands"][0]["status"] == "covered-by-primary-refactor-selector"


def test_standard_q6_defers_terminal_whole_tree_pytest_command(tmp_path: Path) -> None:
    primary = [sys.executable, "-m", "pytest", "tests/test_behavior.py", "-q"]
    terminal = [sys.executable, "-m", "pytest", "scripts/sc"]
    bundle = _bundle([primary, terminal])
    result = run_regression_gate(
        workspace=tmp_path,
        bundle=bundle,
        slice_id="S1",
        profile="standard",
        primary_argv=primary,
        primary_receipt={
            "exit_code": 0,
            "timed_out": False,
            "test_executions": 1,
            "cases": 1,
            "stdout_sha256": "sha256:" + "a" * 64,
            "stderr_sha256": "sha256:" + "b" * 64,
        },
        timeout_seconds=30,
        out=tmp_path / "q6.json",
    )
    assert result["status"] == "pass"
    assert result["deferred_terminal_command_count"] == 1
    assert result["commands"][0]["status"] == "covered-by-primary-refactor-selector"


def test_standard_q6_defers_shared_consumer_regression_file(tmp_path: Path) -> None:
    primary = [sys.executable, "-m", "pytest", "tests/test_behavior.py", "-q"]
    shared = [sys.executable, "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_candidate_review_binding.py"]
    bundle = _bundle([primary, shared])
    result = run_regression_gate(
        workspace=tmp_path,
        bundle=bundle,
        slice_id="S1",
        profile="standard",
        primary_argv=primary,
        primary_receipt={
            "exit_code": 0,
            "timed_out": False,
            "test_executions": 1,
            "cases": 1,
            "stdout_sha256": "sha256:" + "a" * 64,
            "stderr_sha256": "sha256:" + "b" * 64,
        },
        timeout_seconds=30,
        out=tmp_path / "q6.json",
    )
    assert result["status"] == "pass"
    assert result["deferred_terminal_commands"] == [shared]


def test_standard_q6_runs_explicit_single_file_consumer_fixture(tmp_path: Path) -> None:
    primary = [sys.executable, "-m", "pytest", "tests/test_behavior.py", "-q"]
    fixture = [sys.executable, "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_plan_directory_loop.py", "-q"]
    bundle = _bundle([primary, fixture])
    result = run_regression_gate(
        workspace=Path(__file__).resolve().parents[5], bundle=bundle, slice_id="S1",
        profile="standard", primary_argv=primary,
        primary_receipt={"exit_code": 0, "timed_out": False, "test_executions": 1, "cases": 1,
                         "stdout_sha256": "sha256:" + "a" * 64, "stderr_sha256": "sha256:" + "b" * 64},
        timeout_seconds=60, out=tmp_path / "q6.json",
    )
    assert result["deferred_terminal_command_count"] == 0
    assert result["commands"][-1]["exit_code"] == 0
    assert result["commands"][-1]["cases"] >= 1
