from __future__ import annotations

import sys
import tempfile
from unittest.mock import patch, Mock
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import model_routing  # noqa: E402


class RefactorAcceptanceModelRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        # A configured child route is a unit-test fixture, never a runtime fallback.
        fixture = patch.object(model_routing.routing, "load_model", return_value="fixture-model")
        fixture.start()
        self.addCleanup(fixture.stop)

    def test_ordinary_orchestration_has_no_model_execution(self) -> None:
        decision = model_routing.build_route_decision()
        self.assertEqual("refactor_acceptance.deterministic", decision["routeId"])
        self.assertEqual("none", decision["requestedExecution"]["launchMode"])
        self.assertIsNone(decision["requestedExecution"]["model"])
        self.assertEqual("disabled", decision["status"])
        self.assertEqual([], decision["authorizes"])

    def test_no_launch_without_codex_configuration_replays_without_a_model(self) -> None:
        # ADR-0041: deterministic online operation has no Codex configuration dependency.
        with patch.object(model_routing.routing, "load_model", side_effect=ValueError("configuration missing")) as configured:
            decision = model_routing.build_route_decision()
            model_routing.routing.validate_decision(decision)
            runner = Mock()
            with tempfile.TemporaryDirectory() as raw:
                result = model_routing.routing.execute_decision(
                    decision, root=Path(raw), prompt="unused", output_last_message=Path(raw) / "unused.txt",
                    timeout_sec=1, runner=runner,
                )
            configured.assert_not_called()
            runner.assert_not_called()
            self.assertIsNone(result["actualExecution"])
            self.assertEqual("blocked", result["status"])
            self.assertEqual([], result["authorizes"])

    def test_recovery_still_requires_real_model_configuration(self) -> None:
        with patch.object(model_routing.routing, "load_model", side_effect=ValueError("configuration missing")):
            with self.assertRaisesRegex(ValueError, "configuration missing"):
                model_routing.build_route_decision(complex_recovery_trigger="candidate_binding_recovery_failed")

    def test_no_launch_policy_tamper_and_child_identity_fail_closed(self) -> None:
        decision = model_routing.build_route_decision()
        policy = model_routing.routing.load_policy(resolve_models=False)
        policy["consumerControls"]["refactor_acceptance"] = "disabled"
        with self.assertRaisesRegex(model_routing.routing.RoutingError, "policy binding is stale"):
            model_routing.routing.validate_decision(decision, policy)
        decision["requestedExecution"].update(launchMode="child", model="fixture-model")
        decision["decisionId"] = model_routing.routing.canonical_hash({k: v for k, v in decision.items() if k != "decisionId"})
        with self.assertRaisesRegex(model_routing.routing.RoutingError, "cannot request model execution"):
            model_routing.routing.validate_decision(decision)

    def test_closed_complex_recovery_requests_sol_high_observe_only(self) -> None:
        for trigger in model_routing.routing.load_policy()[
            "refactorAcceptanceComplexRecoveryTriggers"
        ]:
            with self.subTest(trigger=trigger):
                decision = model_routing.build_route_decision(
                    complex_recovery_trigger=trigger
                )
                self.assertEqual(
                    "refactor_acceptance.complex_recovery", decision["routeId"]
                )
                self.assertEqual(model_routing.routing.load_model(), decision["requestedExecution"]["model"])
                self.assertEqual("high", decision["requestedExecution"]["effort"])
                self.assertEqual("observe_only", decision["status"])

    def test_unknown_recovery_trigger_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            model_routing.routing.RoutingError, "trigger is invalid"
        ):
            model_routing.build_route_decision(
                complex_recovery_trigger="free_form_recovery"
            )

    def test_bootstrap_model_authority_remains_external(self) -> None:
        profile_path = (
            SKILL_ROOT.parent / "run-phase-bootstrap-review" / "references"
            / "review-profiles.v1.json"
        )
        before = profile_path.read_bytes()
        external = model_routing.routing.bootstrap_external_decision()
        rejected = model_routing.routing.bootstrap_external_decision(
            override_model=model_routing.routing.load_model()
        )
        self.assertEqual("external_profile", external["requestedExecution"]["launchMode"])
        self.assertIsNone(external["requestedExecution"]["model"])
        self.assertIn("bootstrap_profile_override_forbidden", rejected["blockingReasons"])
        self.assertEqual(before, profile_path.read_bytes())

    def test_acceptance_consumer_can_be_disabled_independently(self) -> None:
        policy = model_routing.routing.load_policy()
        policy["rolloutMode"] = "active"
        policy["consumerControls"]["refactor_acceptance"] = "disabled"
        decision = model_routing.routing.refactor_acceptance_decision(
            complex_recovery_trigger="candidate_binding_recovery_failed",
            policy=policy,
        )
        self.assertEqual("disabled", decision["status"])
        self.assertEqual("disabled", decision["consumerState"])
        self.assertEqual("enabled", policy["consumerControls"]["vdd"])
        self.assertEqual("enabled", policy["consumerControls"]["quick_dev"])


if __name__ == "__main__":
    unittest.main()
