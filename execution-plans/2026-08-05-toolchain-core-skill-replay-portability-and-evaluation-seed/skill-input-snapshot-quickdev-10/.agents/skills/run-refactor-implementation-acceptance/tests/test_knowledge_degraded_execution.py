import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts/knowledge_context.py"
sys.path.insert(0, str(SCRIPT.parent))


def _load():
    spec = importlib.util.spec_from_file_location("acceptance_knowledge_context_r2", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_acceptance_delegates_same_selection_refresh_to_shared_validator(monkeypatch, tmp_path):
    module = _load()
    observed = {}

    class SharedValidator:
        def refresh_context_read_set(self, context, root):
            observed["context"] = context
            observed["root"] = root
            return {"context_status": "successor-refreshed", "publication_authorized": False}

    monkeypatch.setattr(module, "_validator", lambda root: SharedValidator())
    context = {"locator_result": {"candidates": ["fixed"]}}
    assert module.refresh_context_read_set(context, tmp_path) == {"context_status": "successor-refreshed", "publication_authorized": False}
    assert observed == {"context": context, "root": tmp_path.resolve()}
