from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


def _policy() -> dict:
    return json.loads(
        (SKILL_ROOT / "policies" / "semantic-review-trigger-policy.v1.json").read_text(encoding="utf-8")
    )


def test_rejects_incomplete_changed_set_before_review_route() -> None:
    import acceptance_core

    baseline = {
        "schemaVersion": "acceptance-baseline-content-manifest.v1",
        "baselineRevision": "a" * 40,
        "files": [{"path": "src/a.py", "sha256": "sha256:" + "a" * 64}],
        "authorizes": [],
    }
    candidate = {
        "schemaVersion": "acceptance-candidate-content-manifest.v1",
        "status": "complete",
        "files": [],
        "authorizes": [],
    }
    with pytest.raises(acceptance_core.InputError, match="top-level fields"):
        acceptance_core.validate_candidate_manifest(candidate, baseline)


def test_mandatory_control_plane_trigger_cannot_be_downgraded() -> None:
    from review_requirement import decide_review_requirement

    result = decide_review_requirement({
        "candidateIdentity": {
            "changedPaths": [".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_core.py"],
            "knowledgeArtifacts": [],
        },
        "deterministicEvidence": {"status": "passed", "hash": "sha256:" + "b" * 64},
        "policy": _policy(),
    })

    assert result["decisionStatus"] == "ready"
    assert result["requirement"] == "required"
    assert "workflow_control_plane_changed" in result["reasonCodes"]
    assert result["authorizes"] == []


def test_required_check_emits_process_bound_receipt(tmp_path: Path) -> None:
    import execution_control

    descriptor = {
        "id": "evidence-pipeline-probe",
        "executable": sys.executable,
        "argv": ["-c", "print('ok')"],
        "cwd": ".",
        "timeout_seconds": 10,
        "shell": False,
        "allowed_write_roots": [],
        "forbidden_write_roots": [],
        "registry_hash": "sha256:" + "c" * 64,
        "environment_allowlist": [],
        "typed_placeholders": {},
        "placeholder_values": {},
    }
    receipt = execution_control.run_controlled_command(tmp_path, descriptor)

    assert receipt["exitCode"] == 0
    assert receipt["commandRegistryHash"] == descriptor["registry_hash"]
    assert receipt["processResultHash"].startswith("sha256:")
    assert receipt["authorizes"] == []
