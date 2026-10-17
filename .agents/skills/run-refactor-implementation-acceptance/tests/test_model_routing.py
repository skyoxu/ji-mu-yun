from __future__ import annotations

import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import model_routing  # noqa: E402


class RefactorAcceptanceModelRoutingTests(unittest.TestCase):
    def test_ordinary_orchestration_has_no_model_execution(self) -> None:
        decision = model_routing.build_route_decision()
        self.assertEqual("refactor_acceptance.deterministic", decision["routeId"])
        self.assertEqual("none", decision["requestedExecution"]["launchMode"])
        self.assertIsNone(decision["requestedExecution"]["model"])
        self.assertEqual("disabled", decision["status"])
        self.assertEqual([], decision["authorizes"])

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
                self.assertEqual("gpt-6-sol", decision["requestedExecution"]["model"])
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
            override_model="gpt-6-sol"
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
