import importlib.util
import json
from pathlib import Path

import pytest


TOOLS = Path(__file__).resolve().parents[3] / "tools"


def _module():
    spec = importlib.util.spec_from_file_location("finalize_repair_round", TOOLS / "finalize_repair_round.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_close_repair_state_is_non_authorizing(tmp_path):
    state_path = tmp_path / "repair-state.v1.json"
    state_path.write_text(json.dumps({
        "schema_version": "toolchain-workflow-repair.repair-state.v1",
        "plan_id": "toolchain-workflow-repair",
        "round": 1,
        "status": "validating",
        "blocks_execution": True,
        "authorizes": [],
    }), encoding="utf-8")

    closed = _module().close_repair_state(state_path)

    assert closed["status"] == "closed"
    assert closed["blocks_execution"] is False
    assert closed["authorizes"] == []


def test_close_repair_state_rejects_non_validating_or_authorizing_state(tmp_path):
    state_path = tmp_path / "repair-state.v1.json"
    state_path.write_text(json.dumps({
        "schema_version": "toolchain-workflow-repair.repair-state.v1",
        "plan_id": "toolchain-workflow-repair",
        "round": 1,
        "status": "closed",
        "blocks_execution": False,
        "authorizes": ["implementation-authorized"],
    }), encoding="utf-8")

    with pytest.raises(ValueError, match="not a closable"):
        _module().close_repair_state(state_path)
