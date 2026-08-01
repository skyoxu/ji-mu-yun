from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import model_routing  # noqa: E402


class VddModelRoutingTests(unittest.TestCase):
    def test_existing_profiles_project_without_a_second_classifier(self) -> None:
        for profile, route_suffix in {
            "standard": "standard",
            "resumable": "resumable",
            "self-hosted": "self_hosted",
        }.items():
            with self.subTest(profile=profile):
                decision = model_routing.build_route_decision(profile)
                self.assertEqual(profile, decision["classification"])
                self.assertEqual(f"vdd.{route_suffix}", decision["routeId"])
                self.assertEqual("gpt-5.6-sol", decision["requestedExecution"]["model"])
                self.assertEqual("high", decision["requestedExecution"]["effort"])
                self.assertEqual("observe_only", decision["status"])

    def test_max_recovery_requires_a_closed_trigger_and_exact_capability_proof(self) -> None:
        blocked = model_routing.build_route_decision(
            "self-hosted", complex_recovery_trigger="bounded_repair_exhausted"
        )
        self.assertEqual("gpt-5.6-sol", blocked["requestedExecution"]["model"])
        self.assertEqual("max", blocked["requestedExecution"]["effort"])
        self.assertEqual("blocked", blocked["status"])

        proof = model_routing.routing.build_capability_proof(
            model="gpt-5.6-sol",
            effort="max",
            backend="codex-cli",
            sandbox="workspace-write",
            probe_status="passed",
            shadow_predicate_status="passed",
            observed_model="gpt-5.6-sol",
            observed_effort="max",
        )
        observed = model_routing.build_route_decision(
            "self-hosted",
            complex_recovery_trigger="bounded_repair_exhausted",
            capability_proof=proof,
        )
        self.assertEqual("observe_only", observed["status"])
        self.assertEqual("passed", observed["capability"]["state"])
        self.assertEqual("passed", observed["capability"]["shadowPredicateState"])

    def test_arbitrary_recovery_reason_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            model_routing.routing.RoutingError, "trigger is invalid"
        ):
            model_routing.build_route_decision(
                "self-hosted", complex_recovery_trigger="free_form_reason"
            )


if __name__ == "__main__":
    unittest.main()
