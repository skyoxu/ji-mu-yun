from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest


def _request(tmp_path: Path, *, semantic: bool = False) -> tuple[Path, Path, dict]:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from acceptance_core import canonical_hash

    binding = "sha256:" + ("b" if semantic else "a") * 64
    bundle = {
        "schemaVersion": "compact-vdd-acceptance-prerequisite-bundle.v1",
        "candidateBindingHash": binding,
        "knowledgeContext": {"path": "context.json", "sha256": "sha256:" + "c" * 64},
    }
    bundle["bundleHash"] = canonical_hash(bundle)
    def write(name: str, value: dict) -> dict:
        path = tmp_path / name
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        return {"path": name, "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}

    authority = write("producer-authority.json", {
        "schemaVersion": "acceptance-coordinator-producer-authority.v1",
        "owner": "run-refactor-implementation-acceptance",
        "candidateBindingHash": binding,
        "bundleHash": bundle["bundleHash"],
        "authorizes": [],
    })
    actions = []
    for action_id in ("source-freeze", "consumer-closure", "finalization"):
        receipt = write(f"{action_id}.json", {
            "schemaVersion": "acceptance-coordinator-action-receipt.v1",
            "actionId": action_id,
            "status": "completed",
            "candidateBindingHash": binding,
            "bundleHash": bundle["bundleHash"],
            "authorizes": [],
        })
        actions.append({"actionId": action_id, "receipt": receipt})
    evidence = write("machine-evidence.json", {
        "schemaVersion": "acceptance-coordinator-evidence.v1",
        "producerAuthority": authority,
        "candidateBindingHash": binding,
        "bundleHash": bundle["bundleHash"],
        "deterministicSourceSufficient": True,
        "semanticReviewRequired": semantic,
        "actions": actions,
        "authorizes": [],
    })
    request = {
        "schemaVersion": "acceptance-coordinator-request.v2",
        "candidateBindingHash": binding,
        "bundle": bundle,
        "evidence": evidence,
        "authorizes": [],
    }
    source, output = tmp_path / "request.json", tmp_path / "result.json"
    source.write_text(json.dumps(request), encoding="utf-8")
    return source, output, request


def test_coordinator_projects_machine_deterministic_route_and_replays(tmp_path: Path) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import acceptance_cli

    source, output, request = _request(tmp_path)
    first = acceptance_cli.run_coordinator(str(source), str(output))
    replay = acceptance_cli.run_coordinator(str(source), str(output))
    assert first["route"] == "deterministic_only"
    assert first["status"] == "completed"
    assert first["bootstrapInvoked"] is False
    assert first["bundleHash"] == request["bundle"]["bundleHash"]
    assert isinstance(first["actionDag"]["actions"][0], dict)
    assert replay["candidateBindingHash"] == first["candidateBindingHash"]
    assert replay["authorizes"] == []


def test_coordinator_stops_at_semantic_handoff_without_bootstrap(tmp_path: Path) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import acceptance_cli

    source, output, _ = _request(tmp_path, semantic=True)
    result = acceptance_cli.run_coordinator(str(source), str(output))
    assert result["status"] == "semantic_handoff_required"
    assert result["bootstrapInvoked"] is False
    assert result["typedHandoff"]["authorizes"] == []


def test_coordinator_rejects_caller_route_override(tmp_path: Path) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import acceptance_cli

    source, output, request = _request(tmp_path)
    request["route"] = "semantic_review_required"
    source.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(acceptance_cli.InputError):
        acceptance_cli.run_coordinator(str(source), str(output))


def test_coordinator_rejects_insufficient_deterministic_evidence(tmp_path: Path) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import acceptance_cli

    source, output, request = _request(tmp_path)
    evidence_path = tmp_path / request["evidence"]["path"]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["deterministicSourceSufficient"] = False
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    request["evidence"]["sha256"] = "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    source.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(acceptance_cli.InputError):
        acceptance_cli.run_coordinator(str(source), str(output))
