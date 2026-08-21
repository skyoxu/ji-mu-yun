import importlib.util
import sys
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py"
sys.path.insert(0, str(SCRIPT.parent))


def _load():
    spec = importlib.util.spec_from_file_location("acceptance_cli_r0", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_coordinator_accepts_v3_before_bundle_validation(tmp_path):
    module = _load()
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "schemaVersion": "acceptance-coordinator-request.v3",
        "candidateBindingHash": "sha256:" + "0" * 64,
        "bundle": {}, "evidence": {}, "authorizes": [],
    }), encoding="utf-8")
    with pytest.raises(module.InputError, match="coordinator bundle"):
        module.run_coordinator(str(request), str(tmp_path / "result.json"))
