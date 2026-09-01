from __future__ import annotations

from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from red_production_entry_guard import validate_red_production_entry


def _bundle(owner: str = "src/service.py") -> dict:
    return {
        "plan_id": "PLAN-RED-GUARD",
        "slices": [
            {
                "slice_id": "S1",
                "production_owners": [owner],
                "execution_snapshot_paths": ["tests/test_service.py", "tests/fixture.txt"],
            }
        ],
    }


def _descriptor() -> dict:
    return {
        "stage": "red",
        "plan_id": "PLAN-RED-GUARD",
        "slice_id": "S1",
        "target_refs": ["tests/test_service.py"],
        "fixture_refs": ["tests/fixture.txt"],
    }


def _workspace(tmp_path: Path, source: str) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "service.py").write_text(
        "class Service:\n    def behavior(self): return False\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_service.py").write_text(source, encoding="utf-8")
    (tmp_path / "tests" / "fixture.txt").write_text("fixture\n", encoding="utf-8")
    return tmp_path


def test_red_guard_requires_and_accepts_real_production_call(tmp_path: Path) -> None:
    workspace = _workspace(
        tmp_path,
        "from src.service import Service\n\ndef test_behavior():\n    assert Service().behavior()\n",
    )
    result = validate_red_production_entry(
        workspace=workspace,
        bundle=_bundle(),
        slice_id="S1",
        descriptor=_descriptor(),
    )
    assert result["status"] == "pass"
    assert result["bindings"] == [
        {"production_owner": "src/service.py", "module": "src.service", "test_ref": "tests/test_service.py"}
    ]
    assert result["tests_executed"] is False and result["writes_performed"] is False


def test_red_guard_rejects_import_without_call(tmp_path: Path) -> None:
    workspace = _workspace(
        tmp_path,
        "from src.service import Service\n\ndef test_behavior():\n    assert 1 == 2\n",
    )
    try:
        validate_red_production_entry(workspace=workspace, bundle=_bundle(), slice_id="S1", descriptor=_descriptor())
    except ValueError as exc:
        assert "does not import and call" in str(exc)
    else:
        raise AssertionError("import-only RED must be rejected")


def test_red_guard_rejects_unconditional_failure_and_evidence_self_judging(tmp_path: Path) -> None:
    unconditional = _workspace(
        tmp_path / "a",
        "from src.service import Service\n\ndef test_behavior():\n    Service()\n    assert False\n",
    )
    try:
        validate_red_production_entry(workspace=unconditional, bundle=_bundle(), slice_id="S1", descriptor=_descriptor())
    except ValueError as exc:
        assert "assert False" in str(exc)
    else:
        raise AssertionError("constant RED must be rejected")

    self_judging = _workspace(
        tmp_path / "b",
        "from src.service import Service\n\ndef test_behavior():\n    Service()\n    marker='implementation-complete'\n    assert marker\n",
    )
    try:
        validate_red_production_entry(workspace=self_judging, bundle=_bundle(), slice_id="S1", descriptor=_descriptor())
    except ValueError as exc:
        assert "plan/evidence" in str(exc)
    else:
        raise AssertionError("evidence-self-judging RED must be rejected")


def test_red_guard_fails_closed_without_supported_python_owner(tmp_path: Path) -> None:
    workspace = _workspace(
        tmp_path,
        "from src.service import Service\n\ndef test_behavior():\n    assert Service().behavior()\n",
    )
    try:
        validate_red_production_entry(
            workspace=workspace,
            bundle=_bundle("src/service.cs"),
            slice_id="S1",
            descriptor=_descriptor(),
        )
    except ValueError as exc:
        assert "no supported Python production owner" in str(exc)
    else:
        raise AssertionError("unsupported production binding must fail closed")
