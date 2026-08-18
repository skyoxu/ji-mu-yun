import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest import mock


TOOLS = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("knowledge_context_successor_test", TOOLS / "knowledge_context.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _context(source_hash: str) -> dict:
    candidate = {"path": "AGENTS.md", "source_sha256": source_hash}
    return {
        "locator_request": {"consumer": "vdd", "request_id": "request-1", "query": "adapter"},
        "required_modules": ["repository-rules"],
        "decisions": [{"decision": "accepted", "candidate": candidate, "satisfies": ["repository-rules"]}],
    }


def test_successor_refresh_accepts_rehashed_same_selection():
    module = _load()
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        plan = root / "execution-plans" / "plan"
        plan.mkdir(parents=True)
        context_path = plan / "knowledge-context.v1.json"
        freeze_path = plan / "knowledge-context.freeze.v1.json"
        before = _context("old")
        context_path.write_text(json.dumps(before), encoding="utf-8")
        freeze_path.write_text(json.dumps({"context_sha256": "ignored"}), encoding="utf-8")

        def publish(*_args, **_kwargs):
            context_path.write_text(json.dumps(_context("new")), encoding="utf-8")
            freeze_path.write_text(json.dumps({"supersedes": {"context_sha256": "sha256:old"}}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch.object(module.subprocess, "run", side_effect=publish):
            result = module.refresh_successor_context(root, plan)

        assert result == {"status": "refreshed", "authorizes": []}


def test_successor_refresh_rejects_selection_drift():
    module = _load()
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        plan = root / "execution-plans" / "plan"
        plan.mkdir(parents=True)
        context_path = plan / "knowledge-context.v1.json"
        freeze_path = plan / "knowledge-context.freeze.v1.json"
        context_path.write_text(json.dumps(_context("old")), encoding="utf-8")
        freeze_path.write_text(json.dumps({"context_sha256": "ignored"}), encoding="utf-8")

        def publish(*_args, **_kwargs):
            changed = _context("new")
            changed["decisions"][0]["satisfies"] = ["other-module"]
            context_path.write_text(json.dumps(changed), encoding="utf-8")
            freeze_path.write_text(json.dumps({"supersedes": {"context_sha256": "sha256:old"}}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch.object(module.subprocess, "run", side_effect=publish):
            result = module.refresh_successor_context(root, plan)

        assert result["status"] == "vdd-repair"
        assert result["failure_code"] == "KWI-QUICK-SCOPE-EXPANSION"
