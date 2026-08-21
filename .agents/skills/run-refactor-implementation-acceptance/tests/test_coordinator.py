from __future__ import annotations

import json
from pathlib import Path

import pytest


def _legacy_request(tmp_path: Path) -> Path:
    path = tmp_path / "legacy-request.json"
    path.write_text(json.dumps({
        "schemaVersion": "acceptance-coordinator-request.v3",
        "candidateBindingHash": "sha256:" + "a" * 64,
        "bundle": {}, "evidence": {}, "authorizes": [],
    }), encoding="utf-8")
    return path


def test_coordinator_rejects_legacy_caller_owned_v3_request(tmp_path: Path) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import acceptance_cli

    with pytest.raises(acceptance_cli.InputError, match="caller control"):
        acceptance_cli.run_coordinator(str(_legacy_request(tmp_path)), str(tmp_path / "result.json"))


def test_coordinator_does_not_accept_caller_route_override(tmp_path: Path) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import acceptance_cli

    request = _legacy_request(tmp_path)
    value = json.loads(request.read_text(encoding="utf-8"))
    value["route"] = "deterministic_only"
    request.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(acceptance_cli.InputError, match="caller control"):
        acceptance_cli.run_coordinator(str(request), str(tmp_path / "result.json"))
