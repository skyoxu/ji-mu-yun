import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[5]
SCRIPT = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/knowledge_context.py"


def _load():
    spec = importlib.util.spec_from_file_location("quick_dev_knowledge_context_r2", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_quick_dev_delegates_same_selection_refresh_to_shared_validator(monkeypatch, tmp_path):
    module = _load()
    observed = {}

    class SharedValidator:
        def refresh_context_read_set(self, context, root):
            observed["context"] = context
            observed["root"] = root
            return {"source_refresh": {"mode": "current_worktree_read_set"}}

    monkeypatch.setattr(module, "_validator", lambda root: SharedValidator())
    context = {"locator_result": {"candidates": ["fixed"]}}
    assert module.refresh_context_read_set(context, tmp_path) == {"source_refresh": {"mode": "current_worktree_read_set"}}
    assert observed == {"context": context, "root": tmp_path.resolve()}


def test_quick_dev_rejects_authority_scope_expansion():
    module = _load()
    frozen = {"accepted": [{"path": "a.md", "source_sha256": "old", "satisfies": ["module.a"]}]}
    proposed = {"accepted": [{"path": "a.md", "source_sha256": "new", "satisfies": ["module.a", "module.b"]}]}
    assert module.verify_frozen_context(frozen, proposed) == {"status": "vdd-repair", "failure_code": "KWI-QUICK-SCOPE-EXPANSION"}
