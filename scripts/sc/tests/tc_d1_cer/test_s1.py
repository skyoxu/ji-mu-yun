from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
MODULE_PATH = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/candidate_workspace.py"
FIXTURE_PATH = (
    ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/tests/fixtures/candidate-identity.v1.json"
)
FAILURE_ID = "UNVERIFIED-CANDIDATE-EXTERNAL-TRUST-REJECTED"


def _candidate_workspace_module():
    spec = importlib.util.spec_from_file_location("candidate_workspace", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.cer_assertion("FR-3-candidate-external-trust-independent-verification")
def test_candidate_external_trust_without_independent_verification_is_rejected() -> None:
    candidate_identity = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    verifier = getattr(_candidate_workspace_module(), "verify_candidate_external_trust", None)
    verification_result = verifier(candidate_identity) if callable(verifier) else None
    rejected = verification_result is False
    if not rejected:
        print(f"FAILURE_ID:{FAILURE_ID}")
    assert rejected, "candidate without independently established external trust was accepted or left unverified"
