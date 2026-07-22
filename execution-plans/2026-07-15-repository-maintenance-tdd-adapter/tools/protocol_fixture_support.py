from __future__ import annotations

import importlib.util
from pathlib import Path


_CORE_PATH = Path(__file__).resolve().parents[3] / ".agents/skills/quick-dev-tdd-adapter/tools/protocol_fixture_support.py"
_SPEC = importlib.util.spec_from_file_location("quick_dev_tdd_protocol_fixture_support", _CORE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("Skill-owned protocol fixture core is unavailable")
_CORE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CORE)

hydrate_protocol_fixture = _CORE.hydrate_protocol_fixture
load_protocol_run = _CORE.load_protocol_run
