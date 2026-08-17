from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


def test_coordinator_replays_identical_deterministic_binding(tmp_path: Path) -> None:
    import acceptance_cli

    request = {
        "schemaVersion": "acceptance-coordinator-request.v1",
        "candidateBindingHash": "sha256:" + "a" * 64,
        "route": "deterministic_only",
        "authorizes": [],
    }
    source = tmp_path / "request.json"
    output = tmp_path / "result.json"
    source.write_text(json.dumps(request), encoding="utf-8")

    first = acceptance_cli.run_coordinator(str(source), str(output))
    replay = acceptance_cli.run_coordinator(str(source), str(output))

    assert first == replay
    assert first["status"] == "completed"
    assert first["bootstrapInvoked"] is False
    assert first["authorizes"] == []


def test_coordinator_stops_at_semantic_handoff(tmp_path: Path) -> None:
    import acceptance_cli

    source = tmp_path / "request.json"
    output = tmp_path / "result.json"
    source.write_text(json.dumps({
        "schemaVersion": "acceptance-coordinator-request.v1",
        "candidateBindingHash": "sha256:" + "b" * 64,
        "route": "semantic_review_required",
        "authorizes": [],
    }), encoding="utf-8")

    result = acceptance_cli.run_coordinator(str(source), str(output))

    assert result["status"] == "semantic_handoff_required"
    assert result["bootstrapInvoked"] is False
    assert result["typedHandoff"]["candidateBindingHash"] == "sha256:" + "b" * 64
