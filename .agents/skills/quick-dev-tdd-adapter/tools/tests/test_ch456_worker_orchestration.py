from __future__ import annotations

import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from worker_orchestrator import run_implementation_worker, run_red_author, run_refactor_worker


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path
    (root / "src").mkdir()
    (root / "tests").mkdir()
    plan = root / "plan"
    (plan / "agent-context" / "S1").mkdir(parents=True)
    production = root / "src" / "subject.py"
    target = root / "tests" / "test_subject.py"
    fixture = root / "tests" / "fixture.json"
    production.write_text("def value():\n    return 0\n", encoding="utf-8")
    fixture.write_text('{}\n', encoding="utf-8")
    bundle = {
        "plan_id": "PLAN-X",
        "slices": [{
            "slice_id": "S1",
            "acceptance_ids": ["A-X"],
            "failure_intent_ids": ["FI-X"],
            "production_owners": ["src/subject.py"],
            "allowed_write_paths": ["src/subject.py"],
            "execution_snapshot_paths": ["tests/test_subject.py", "tests/fixture.json"],
            "planned_new_files": ["tests/test_subject.py"],
        }],
        "acceptances": [{"acceptance_id": "A-X", "source_refs": ["requirements.md#FR-1"], "assertion_ids": ["ASSERT-X"]}],
        "failure_intents": [{"failure_intent_id": "FI-X", "acceptance_ids": ["A-X"], "failure_family": "expected-red", "selector_intent": "tests/test_subject.py", "failure_id": "EXPECTED-X"}],
    }
    semantic = plan / "semantic-plan-bundle.v1.json"
    semantic.write_text(json.dumps(bundle), encoding="utf-8")
    context = {
        "slice_id": "S1",
        "requirement_ids": ["FR-1"],
        "obligation_ids": ["O-X"],
        "acceptance_ids": ["A-X"],
        "source_refs": ["requirements.md#FR-1"],
        "contracts": ["vdd.semantic-plan-bundle.v1"],
        "allowed_paths": ["src/subject.py"],
        "forbidden_paths": ["tests/test_subject.py", "tests/fixture.json"],
        "selector_intents": ["tests/test_subject.py"],
        "validation_commands": [[sys.executable, "-m", "pytest", "tests/test_subject.py", "-q"]],
    }
    (plan / "agent-context" / "S1" / "agent-context.json").write_text(json.dumps(context), encoding="utf-8")
    return plan, semantic, production


def _expected_red() -> dict:
    return {
        "stage": "red",
        "predicate_result": True,
        "verification_outcome": "fail",
        "failure_family": "expected-red",
        "failure_id": "EXPECTED-X",
    }


def _green() -> dict:
    return {"stage": "green", "predicate_result": True, "verification_outcome": "pass"}


def test_red_author_can_create_only_bound_test_paths(tmp_path: Path) -> None:
    plan, semantic, _production = _fixture(tmp_path)

    def author(root: Path, _payload) -> None:
        (root / "tests" / "test_subject.py").write_text("def test_subject():\n    assert False\n", encoding="utf-8")

    result = run_red_author(
        workspace=tmp_path, plan_dir=plan, semantic_plan=semantic, slice_id="S1", worker_mutator=author
    )
    assert result["status"] == "worker-changes-valid"
    assert result["changed_paths"] == ["tests/test_subject.py"]
    assert result["authorizes_evidence"] is False


def test_red_author_rejects_production_write(tmp_path: Path) -> None:
    plan, semantic, production = _fixture(tmp_path)

    def bad_author(_root: Path, _payload) -> None:
        production.write_text("def value():\n    return 1\n", encoding="utf-8")

    try:
        run_red_author(workspace=tmp_path, plan_dir=plan, semantic_plan=semantic, slice_id="S1", worker_mutator=bad_author)
    except ValueError as exc:
        assert "write-set violation" in str(exc)
    else:
        raise AssertionError("RED author production write must fail closed")


def test_implementation_requires_expected_red_and_rejects_test_write(tmp_path: Path) -> None:
    plan, semantic, production = _fixture(tmp_path)
    (tmp_path / "tests" / "test_subject.py").write_text("def test_subject():\n    assert False\n", encoding="utf-8")

    def implement(_root: Path, _payload) -> None:
        production.write_text("def value():\n    return 1\n", encoding="utf-8")

    result = run_implementation_worker(
        workspace=tmp_path, plan_dir=plan, semantic_plan=semantic, slice_id="S1",
        red_stage_result=_expected_red(), worker_mutator=implement,
    )
    assert result["status"] == "worker-changes-valid"
    assert result["changed_paths"] == ["src/subject.py"]

    def bad_implement(root: Path, _payload) -> None:
        (root / "tests" / "test_subject.py").write_text("def test_subject():\n    assert True\n", encoding="utf-8")

    try:
        run_implementation_worker(
            workspace=tmp_path, plan_dir=plan, semantic_plan=semantic, slice_id="S1",
            red_stage_result=_expected_red(), worker_mutator=bad_implement,
        )
    except ValueError as exc:
        assert "write-set violation" in str(exc)
    else:
        raise AssertionError("implementation selector write must fail closed")


def test_refactor_requires_clean_green_and_preserves_selector_bytes(tmp_path: Path) -> None:
    plan, semantic, production = _fixture(tmp_path)
    target = tmp_path / "tests" / "test_subject.py"
    target.write_text("def test_subject():\n    assert True\n", encoding="utf-8")

    def refactor(_root: Path, _payload) -> None:
        production.write_text("def value():\n    result = 1\n    return result\n", encoding="utf-8")

    result = run_refactor_worker(
        workspace=tmp_path, plan_dir=plan, semantic_plan=semantic, slice_id="S1",
        green_stage_result=_green(), worker_mutator=refactor,
    )
    assert result["status"] == "worker-changes-valid"
    assert result["changed_paths"] == ["src/subject.py"]

    def bad_refactor(_root: Path, _payload) -> None:
        target.write_text("def test_subject():\n    assert False\n", encoding="utf-8")

    try:
        run_refactor_worker(
            workspace=tmp_path, plan_dir=plan, semantic_plan=semantic, slice_id="S1",
            green_stage_result=_green(), worker_mutator=bad_refactor,
        )
    except ValueError as exc:
        assert "write-set violation" in str(exc)
    else:
        raise AssertionError("refactor selector mutation must fail closed")
