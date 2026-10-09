"""CER checks for replay freshness, independent bindings, and isolation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.sc import skill_replay_runtime as runtime

_CER_ASSERTION_BINDINGS = [pytest.mark.cer_assertion("A-6F1570D39AE8-1")]


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return runtime.capture_process([sys.executable, '-B', str(ENTRY), *args], ROOT, timeout=runtime.PROCESS_TRANSPORT_SECONDS if args[0] == "replay-package" else 150 if args[0] == "replay-matrix" else 60)


def _json(result: subprocess.CompletedProcess[str]) -> dict:
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"production replay entrypoint did not produce a JSON receipt: {exc}")
    if not isinstance(value, dict):
        pytest.fail("production replay entrypoint did not produce an object receipt")
    return value


def _assert_observed(condition: bool, failure_id: str, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, message


@pytest.mark.cer_assertion("A-6F1570D39AE8-1")
@pytest.mark.cer_assertion("ASSERT-PINNED-FRESH-VERDICT-REPRODUCTION")
def test_pinned_fresh_checkout_reproduces_semantic_verdict() -> None:
    receipt = _json(_run("replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", "fresh"))
    replay = receipt.get("current_wrapper_replay", {})
    _assert_observed(
        replay.get("fresh_checkout") is True
        and replay.get("pinned_semantic_verdict") is not None
        and replay.get("fresh_semantic_verdict") is not None
        and replay.get("pinned_semantic_verdict") == replay.get("fresh_semantic_verdict"),
        "PINNED_FRESH_VERDICT_MISMATCH",
        "fresh replay must reproduce the pinned semantic verdict and coverage",
    )


@pytest.mark.cer_assertion("A-O-171D94D47E51-PINNED-INPUT-FRESH-CHECKOUT-REPRODUCTION")
def test_pinned_input_fresh_checkout_reproduces_verdict_and_coverage() -> None:
    receipt = _json(_run("replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", "fresh"))
    replay = receipt.get("current_wrapper_replay", {})
    _assert_observed(
        replay.get("fresh_checkout") is True
        and replay.get("semantic_verdict") == replay.get("pinned_semantic_verdict")
        and replay.get("coverage_result") is not None
        and replay.get("pinned_coverage") is not None
        and replay.get("coverage_result") == replay.get("pinned_coverage"),
        "PINNED_INPUT_FRESH_CHECKOUT_MISMATCH",
        "pinned inputs must be evaluated in a fresh checkout with matching verdict and coverage",
    )


@pytest.mark.cer_assertion("A-O-1BF52DFD1858-CANDIDATE-EXTERNAL-TRUST-INDEPENDENCE")
def test_candidate_external_trust_has_distinct_independent_verification() -> None:
    receipt = _json(_run("replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", "trust"))
    trust = receipt.get("current_wrapper_replay", {}).get("candidate_external_trust_verification")
    _assert_observed(
        isinstance(trust, dict)
        and trust.get("independent") is True
        and trust.get("complete") is True
        and trust.get("candidate_controlled") is False
        and trust.get("inherited") is False,
        "CANDIDATE_EXTERNAL_TRUST_NOT_INDEPENDENT",
        "candidate-external trust must have a distinct independent verification",
    )


@pytest.mark.cer_assertion("A-O-F53D7DB64BB9-1")
def test_reused_evidence_is_non_success_with_a_diagnostic() -> None:
    receipt = _json(_run("replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", "reused-evidence"))
    replay = receipt.get("current_wrapper_replay", {})
    diagnostic = receipt.get("diagnostic") or replay.get("diagnostic") or receipt.get("rejection_reason")
    _assert_observed(
        receipt.get("status") not in {"success", "pass"}
        and isinstance(diagnostic, str)
        and "reused" in diagnostic.lower(),
        "FI_O-F53D7DB64BB9_REUSED_EVIDENCE_ACCEPTED",
        "reused evidence must be rejected with an auditable diagnostic",
    )


@pytest.mark.cer_assertion("ASSERT-O-CC96C206074F-EVIDENCE-ISOLATION")
def test_cross_component_evidence_substitution_cannot_create_success() -> None:
    receipt = _json(_run("replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", "isolation"))
    isolation = receipt.get("current_wrapper_replay", {}).get("evidence_isolation")
    required_components = {"Subjects", "Probes", "Matrix Cases", "Consumers", "rollback stages"}
    components = isolation.get("components", []) if isinstance(isolation, dict) else []
    _assert_observed(
        isinstance(isolation, dict)
        and isolation.get("independently_attributable") is True
        and isolation.get("cross_component_reuse_rejected") is True
        and isinstance(components, (list, tuple, set))
        and required_components.issubset(set(components)),
        "CROSS_COMPONENT_EVIDENCE_REUSE",
        "evidence ownership must remain isolated across components",
    )


@pytest.mark.cer_assertion("ASSERT-EFFECTIVE-INSPECTION-WITNESS")
def test_inspection_receipt_contains_an_independent_effective_read_witness() -> None:
    receipt = _json(_run("validate-package", "--target", TARGET, "--capability", CAPABILITY))
    effective = receipt.get("effective_inspected_content", {})
    witness = receipt.get("effective_read_witness")
    _assert_observed(
        isinstance(witness, dict)
        and witness.get("observed") is True
        and effective.get("path") == TARGET
        and witness.get("target_identity") == effective.get("identity"),
        "EFFECTIVE_INSPECTION_UNPROVEN",
        "inspection success requires an independent observed-read witness",
    )


@pytest.mark.cer_assertion("ASSERT-REPLAY-CONSUMER-INDEPENDENT-VERIFICATION")
def test_successful_replay_has_independent_consumer_verification() -> None:
    receipt = _json(_run("replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", "consumer"))
    binding = receipt.get("current_wrapper_replay", {}).get("consumer_verification")
    _assert_observed(
        isinstance(binding, dict)
        and binding.get("independent") is True
        and binding.get("executed") is True,
        "CONSUMER_VERIFICATION_ABSENT",
        "successful replay must carry independent Consumer verification",
    )


@pytest.mark.cer_assertion("A-O-D0E9D60AA620-1")
def test_successful_replay_records_independent_dependency_verification() -> None:
    receipt = _json(_run("replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", "dependencies"))
    verification = receipt.get("current_wrapper_replay", {}).get("dependency_verification")
    _assert_observed(
        isinstance(verification, dict) and verification.get("independent") is True,
        "DEPENDENCY_VERIFICATION_MISSING",
        "successful replay must record independent dependency verification",
    )


@pytest.mark.cer_assertion("A-F397-PLATFORM-BEHAVIOR-DECLARED")
def test_platform_specific_behavior_is_declared_in_the_replay_artifact() -> None:
    receipt = _json(_run("replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", "platform"))
    declaration = receipt.get("current_wrapper_replay", {}).get("platform_behavior")
    _assert_observed(
        isinstance(declaration, dict)
        and bool(declaration.get("behavior"))
        and bool(declaration.get("platform")),
        "RED_F397_UNDECLARED_PLATFORM_BEHAVIOR",
        "platform-differing behavior requires an explicit platform declaration",
    )


@pytest.mark.cer_assertion("ASSERT-SM5-INDEPENDENT-TARGET-VERIFICATION")
def test_successful_replay_records_independent_target_verification() -> None:
    receipt = _json(_run("replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", "target"))
    verification = receipt.get("current_wrapper_replay", {}).get("target_verification")
    _assert_observed(
        isinstance(verification, dict)
        and verification.get("independent") is True
        and verification.get("target") == TARGET,
        "SM5_TARGET_BINDING_MISSING",
        "successful replay must independently verify its target binding",
    )
