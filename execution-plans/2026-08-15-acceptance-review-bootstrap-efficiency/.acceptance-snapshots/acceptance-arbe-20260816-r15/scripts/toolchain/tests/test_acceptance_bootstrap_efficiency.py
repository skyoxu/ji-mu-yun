from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _report() -> dict:
    return {
        "schemaVersion": "acceptance-bootstrap-efficiency-rollout.v1",
        "historicalRuns": [
            {"runId": run_id, "outcome": "abandoned", "classification": "historical-runtime-failure", "reusable": False, "authorizes": []}
            for run_id in ("vcec-r1", "vcec-r1m", "vcec-r1n")
        ],
        "deterministicFailure": {"status": "failed", "reviewerCalls": 0, "authorizes": []},
        "semanticCorpus": {"status": "passed", "falseAuthorization": False, "authorizes": []},
        "telemetry": {"closureBytes": 10, "segments": 1, "attempts": 3, "retries": 0, "tokens": 20, "wallTimeSeconds": 5},
        "gates": {"M0": "passed", "M1": "passed", "M2": "passed"},
        "defaultSwitch": False,
        "authorizes": [],
    }


def test_rejects_historical_rewrite_and_reviewer_call_on_deterministic_failure() -> None:
    from acceptance_bootstrap_efficiency import validate_rollout_evidence

    report = _report()
    report["historicalRuns"][0]["reusable"] = True
    with pytest.raises(Exception, match="historical"):
        validate_rollout_evidence(report)


def test_rejects_false_authorization_and_premature_default_switch() -> None:
    from acceptance_bootstrap_efficiency import validate_rollout_evidence

    report = _report()
    report["semanticCorpus"]["falseAuthorization"] = True
    with pytest.raises(Exception, match="false authorization"):
        validate_rollout_evidence(report)
    report = _report()
    report["gates"]["M2"] = "blocked"
    report["defaultSwitch"] = True
    with pytest.raises(Exception, match="default switch"):
        validate_rollout_evidence(report)


def test_accepts_non_authorizing_evidence_and_keeps_default_off() -> None:
    from acceptance_bootstrap_efficiency import validate_rollout_evidence

    result = validate_rollout_evidence(_report())
    assert result["authorizes"] == []
    assert result["defaultSwitch"] is False
