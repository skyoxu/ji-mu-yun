"""CER coverage for closed target resolution when the target is absent."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / ".agents" / "skills" / "vdd-conformance-exact-cover" / "tests" / "validators" / "readonly_target.py"


def _load_entry():
    spec = importlib.util.spec_from_file_location("readonly_target_entry", ENTRY)
    if spec is None or spec.loader is None:
        raise RuntimeError("production entry import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.cer_assertion("A-FR1-MISSING-TARGET-1")
def test_missing_target_is_rejected_before_target_content_is_accepted(tmp_path: Path) -> None:
    module = _load_entry()
    module.TARGET = tmp_path / "missing-target.json"

    with pytest.raises(FileNotFoundError):
        module.main()
