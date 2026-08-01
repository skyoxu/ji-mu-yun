from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

import model_routing  # noqa: E402


class QuickDevModelRoutingTests(unittest.TestCase):
    def facts(self, **updates: object) -> dict[str, object]:
        value: dict[str, object] = {
            "changes_adr_or_invariant": False,
            "changes_public_api": False,
            "changes_database_schema": False,
            "changes_auth_security": False,
            "changes_runtime_deployment": False,
            "changes_shared_llm_entrypoint": False,
            "touches_protected_path": False,
            "changes_workflow_control_plane_ownership": False,
            "has_cross_module_consumers": False,
            "changes_state_or_recovery_semantics": False,
            "changes_concurrency_or_idempotency": False,
            "has_unresolved_behavioral_boundary": False,
            "production_write_roots": 1,
            "matching_test_roots": 1,
            "deterministic_transform": False,
            "behavior_fully_specified": True,
            "introduces_contract": False,
            "introduces_dependency": False,
            "unknown_facts": [],
            "contradictory_facts": [],
        }
        value.update(updates)
        return value

    def test_all_four_classes_are_selected_from_typed_facts(self) -> None:
        cases = {
            "small_mechanical": self.facts(deterministic_transform=True),
            "normal": self.facts(),
            "complex": self.facts(has_cross_module_consumers=True),
            "architectural": self.facts(changes_public_api=True),
        }
        for expected, facts in cases.items():
            with self.subTest(expected=expected):
                decision = model_routing.build_route_decision(facts)
                self.assertEqual(expected, decision["classification"])
                self.assertEqual(f"quick_dev.{expected}", decision["routeId"])
                self.assertEqual("observe_only", decision["status"])
                self.assertEqual([], decision["authorizes"])

    def test_every_architectural_fact_wins_over_mechanical_and_complex_facts(self) -> None:
        for fact in model_routing.routing.ARCHITECTURAL_FACTS:
            with self.subTest(fact=fact):
                decision = model_routing.build_route_decision(self.facts(
                    deterministic_transform=True,
                    has_cross_module_consumers=True,
                    **{fact: True},
                ))
                self.assertEqual("architectural", decision["classification"])
                self.assertIn(fact, decision["triggers"])

    def test_unknown_and_contradictory_facts_route_upward_and_block(self) -> None:
        decision = model_routing.build_route_decision(self.facts(
            deterministic_transform=True,
            unknown_facts=["affected_consumer_count"],
            contradictory_facts=["write_root_scope"],
        ))
        self.assertEqual("complex", decision["classification"])
        self.assertEqual("blocked", decision["status"])
        self.assertIn("unknown_typed_facts", decision["blockingReasons"])
        self.assertIn("contradictory_typed_facts", decision["blockingReasons"])

    def test_upgrade_is_accepted_and_downgrade_is_rejected(self) -> None:
        upgraded = model_routing.build_route_decision(
            self.facts(), requested_class="architectural"
        )
        self.assertEqual("architectural", upgraded["classification"])
        self.assertEqual("accepted_upgrade", upgraded["override"]["disposition"])

        rejected = model_routing.build_route_decision(
            self.facts(touches_protected_path=True), requested_class="normal"
        )
        self.assertEqual("architectural", rejected["classification"])
        self.assertEqual("rejected_downgrade", rejected["override"]["disposition"])
        self.assertEqual("blocked", rejected["status"])

    def test_adapter_has_no_execution_or_provider_scheduling_api(self) -> None:
        self.assertFalse(hasattr(model_routing, "execute_decision"))
        self.assertFalse(hasattr(model_routing, "run_llm_exec"))


if __name__ == "__main__":
    unittest.main()
