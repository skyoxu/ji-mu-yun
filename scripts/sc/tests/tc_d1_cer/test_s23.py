"""CER checks for FR-3 independent support-policy and compatibility results."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[4]
MODULE_PATH = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/governance_policy.py"


def _governance_policy_module() -> Any:
    spec = importlib.util.spec_from_file_location("governance_policy", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_policy() -> dict[str, Any]:
    resolver = getattr(_governance_policy_module(), "resolve_governance_policy", None)
    assert callable(resolver)
    policy = resolver(environment={"PHASEA_SERVICE_STATE": "test"})
    assert isinstance(policy, dict)
    return policy


def _independent_result(value: object, *, key: str) -> tuple[bool, object]:
    if not isinstance(value, dict):
        return False, value
    result = value.get(key)
    if not isinstance(result, dict):
        return False, result
    status = result.get("status")
    status_ok = status in {"pass", "passed", "ok"}
    independent_ok = result.get("independent") is True
    rules = result.get("required_rule_checks")
    rules_ok = isinstance(rules, dict) and bool(rules) and all(rules.values())
    return status_ok and independent_ok and rules_ok, result


@pytest.mark.cer_assertion("A-SUPPORT-POLICY-INDEPENDENT-CHECK")
def test_support_policy_records_independent_verification() -> None:
    policy = _resolve_policy()
    valid, verification = _independent_result(
        policy, key="independent_support_policy_verification"
    )
    authoring = policy.get("support_policy_verification")
    independent_source = verification.get("source") if isinstance(verification, dict) else None
    authoring_source = authoring.get("source") if isinstance(authoring, dict) else None
    valid = valid and independent_source is not None and independent_source != authoring_source
    if not valid:
        print("FAILURE_ID:F-SUPPORT-POLICY-NO-INDEPENDENT-VERIFICATION")
    assert valid, "support policy lacks a separately attributable independent verification result"


@pytest.mark.cer_assertion("compatibility-independent-result")
def test_compatibility_records_dedicated_independent_result() -> None:
    policy = _resolve_policy()
    valid, verification = _independent_result(
        policy, key="independent_compatibility_verification"
    )
    authoring = policy.get("compatibility_verification")
    independent_source = verification.get("source") if isinstance(verification, dict) else None
    authoring_source = authoring.get("source") if isinstance(authoring, dict) else None
    valid = (
        valid
        and independent_source is not None
        and independent_source != authoring_source
        and verification is not authoring
    )
    if not valid:
        print("FAILURE_ID:COMPATIBILITY-INDEPENDENT-CHECK-MISSING")
    assert valid, "compatibility must expose a dedicated independently derived result"
