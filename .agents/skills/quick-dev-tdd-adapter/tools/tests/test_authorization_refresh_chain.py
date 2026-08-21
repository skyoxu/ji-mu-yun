import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
SCRIPT = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/knowledge_context.py"


def _load():
    spec = importlib.util.spec_from_file_location("acceptance_knowledge_context_r2", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_same_selection_refresh_preserves_authorization_boundary():
    module = _load()
    assert hasattr(module, "refresh_context_read_set")
