from __future__ import annotations

import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


def _identities() -> dict[str, str]:
    return {key: "sha256:" + chr(97 + index) * 64 for index, key in enumerate((
        "baselineIdentityHash", "candidateIdentityHash", "consumerClosureHash",
        "requiredChecksHash", "policyHash", "specSelectionHash",
    ))}


def _decision(identities: dict[str, str]) -> dict:
    from acceptance_core import canonical_hash

    value = {
        "schemaVersion": "acceptance-supervised-decision.v1",
        "decision": "semantic_review_satisfied",
        "owner": "maintainer",
        "acceptanceMode": "supervised",
        "route": "deterministic_only",
        "triggerIds": [],
        **identities,
        "authorizes": [],
    }
    return {**value, "decisionHash": canonical_hash(value)}


def _bootstrap(identities: dict[str, str]) -> dict:
    return {
        "schemaVersion": "bootstrap-import-envelope.v3",
        "candidateIdentityHash": identities["candidateIdentityHash"],
        "scopeHash": "sha256:" + "d" * 64,
        "bootstrapRouteHash": "sha256:" + "e" * 64,
        "finalizedRunCoreHash": "sha256:" + "f" * 64,
        "finalizedRun": {"validationStatus": "passed", "finalStatus": "clean"},
        "completedRoles": ["acceptance_auditor", "blind_hunter", "edge_case_hunter"],
        "authorizes": [],
    }


def test_rejects_supervised_decision_when_any_identity_is_stale() -> None:
    from semantic_import import validate_supervised_decision

    identities = _identities()
    decision = _decision(identities)
    decision["candidateIdentityHash"] = "sha256:" + "z" * 64
    with pytest.raises(Exception, match="stale"):
        validate_supervised_decision(decision, identities)


def test_rejects_advisory_text_and_false_bootstrap_boolean() -> None:
    from semantic_import import finalize_acceptance

    identities = _identities()
    with pytest.raises(Exception, match="decision"):
        finalize_acceptance({
            "acceptanceMode": "supervised", "route": "deterministic_only", "triggerIds": [],
            "identities": identities, "supervisedDecision": {"webSolText": "passed"},
            "bootstrapImport": None,
        })


def test_rejects_bootstrap_route_without_current_import() -> None:
    from semantic_import import finalize_acceptance

    with pytest.raises(Exception, match="Bootstrap"):
        finalize_acceptance({
            "acceptanceMode": "unattended", "route": "full_implementation_conformance", "triggerIds": [],
            "identities": _identities(), "supervisedDecision": None, "bootstrapImport": None,
        })


def test_rejects_bootstrap_import_without_complete_review_roles() -> None:
    from semantic_import import validate_bootstrap_import

    identities = _identities()
    imported = _bootstrap(identities)
    imported["completedRoles"] = ["blind_hunter", "edge_case_hunter"]
    with pytest.raises(Exception, match="role"):
        validate_bootstrap_import(imported, identities)


def test_mode_route_matrix_and_acceptance_owner_finalization() -> None:
    from semantic_import import finalize_acceptance, project_route

    identities = _identities()
    assert project_route("supervised", "deterministic_only", ["explicit_request"])["route"] == "full_implementation_conformance"
    result = finalize_acceptance({
        "acceptanceMode": "supervised", "route": "deterministic_only", "triggerIds": [],
        "identities": identities, "supervisedDecision": _decision(identities), "bootstrapImport": None,
    })
    assert result["lifecycleTransition"] == "acceptance-passed"
    assert result["authorizes"] == ["acceptance-passed"]
