#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SC_ROOT = REPOSITORY_ROOT / "scripts" / "sc"
if str(SC_ROOT) not in sys.path:
    sys.path.insert(0, str(SC_ROOT))

import workflow_model_routing as routing  # noqa: E402


class PolicyContractTests(unittest.TestCase):
    def test_canonical_policy_covers_every_route_with_full_model_ids(self) -> None:
        policy = routing.load_policy()
        routing.validate_policy(policy)
        self.assertEqual("observe_only", policy["rolloutMode"])
        self.assertEqual([], policy["authorizes"])
        self.assertEqual(11, len(policy["routes"]))
        for route in policy["routes"].values():
            if route["launchMode"] == "child":
                self.assertTrue(policy["models"][route["model"]]["modelId"].startswith("gpt-"))

    def test_policy_schema_and_decision_schema_are_parseable(self) -> None:
        schema = json.loads(
            (SC_ROOT / "schemas" / "workflow-model-route-decision.v1.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual("object", schema["type"])
        self.assertIn("decisionId", schema["required"])

    def test_short_runtime_model_alias_is_rejected(self) -> None:
        policy = routing.load_policy()
        policy["models"]["sol"]["modelId"] = "sol"
        with self.assertRaisesRegex(routing.RoutingError, "full model IDs"):
            routing.validate_policy(policy)


class LauncherTests(unittest.TestCase):
    def _normal_facts(self) -> dict[str, object]:
        facts: dict[str, object] = {
            name: False for name in (*routing.ARCHITECTURAL_FACTS, *routing.COMPLEX_FACTS)
        }
        facts.update({
            "production_write_roots": 1,
            "matching_test_roots": 2,
            "deterministic_transform": False,
            "behavior_fully_specified": True,
            "introduces_contract": False,
            "introduces_dependency": False,
            "unknown_facts": [],
            "contradictory_facts": [],
        })
        return facts

    def test_observe_only_never_invokes_runner_or_replaces_current_session(self) -> None:
        decision = routing.quick_dev_decision(self._normal_facts())
        runner = mock.Mock()
        result = routing.execute_decision(
            decision,
            root=REPOSITORY_ROOT,
            prompt="secret prompt",
            output_last_message=REPOSITORY_ROOT / "unused.txt",
            timeout_sec=10,
            runner=runner,
        )
        runner.assert_not_called()
        self.assertEqual("observed", result["status"])
        self.assertIsNone(result["actualExecution"])
        self.assertNotIn("secret prompt", json.dumps(result))

    def test_active_launcher_binds_stdin_model_effort_sandbox_and_no_fallback(self) -> None:
        policy = routing.load_policy()
        policy["rolloutMode"] = "active"
        decision = routing.quick_dev_decision(self._normal_facts(), policy=policy)
        runner = mock.Mock(return_value=(0, "ok", [
            "codex", "exec", "-m", "gpt-5.6-terra", "-c", 'model_reasoning_effort="medium"',
            "--sandbox", "workspace-write", "-",
        ]))
        result = routing.execute_decision(
            decision,
            root=REPOSITORY_ROOT,
            prompt="stdin prompt",
            output_last_message=REPOSITORY_ROOT / "unused.txt",
            timeout_sec=10,
            policy=policy,
            runner=runner,
        )
        self.assertEqual("completed", result["status"])
        kwargs = runner.call_args.kwargs
        self.assertEqual("stdin prompt", kwargs["prompt"])
        self.assertEqual("gpt-5.6-terra", kwargs["codex_model"])
        self.assertEqual("workspace-write", kwargs["codex_sandbox"])
        self.assertEqual(['model_reasoning_effort="medium"'], kwargs["codex_configs"])
        self.assertNotIn("fallback", json.dumps(result).lower())

    def test_unsupported_max_capability_leaves_route_blocked(self) -> None:
        proof = routing.build_capability_proof(
            model="gpt-5.6-sol",
            effort="max",
            backend="codex-cli",
            sandbox="workspace-write",
            probe_status="unavailable",
            shadow_predicate_status="missing",
            observed_model=None,
            observed_effort=None,
        )
        decision = routing.vdd_decision(
            "self-hosted", complex_recovery=True, recovery_trigger="bounded_repair_exhausted",
            capability_proof=proof,
        )
        self.assertEqual("blocked", decision["status"])
        self.assertEqual("failed", decision["capability"]["state"])

    def test_requested_actual_identity_drift_fails_execution(self) -> None:
        policy = routing.load_policy()
        policy["rolloutMode"] = "active"
        decision = routing.quick_dev_decision(self._normal_facts(), policy=policy)
        runner = mock.Mock(return_value=(0, "ok", ["codex", "exec", "-"]))
        result = routing.execute_decision(
            decision,
            root=REPOSITORY_ROOT,
            prompt="prompt",
            output_last_message=REPOSITORY_ROOT / "unused.txt",
            timeout_sec=10,
            policy=policy,
            runner=runner,
        )
        self.assertEqual("failed", result["status"])
        self.assertIsNone(result["actualExecution"]["model"])

    def test_shadow_model_cannot_become_an_active_route(self) -> None:
        policy = routing.load_policy()
        policy["routes"]["quick_dev.normal"]["model"] = "luna"
        with self.assertRaisesRegex(routing.RoutingError, "shadow model"):
            routing.validate_policy(policy)

    def test_max_route_requires_capability_probe(self) -> None:
        policy = routing.load_policy()
        del policy["routes"]["vdd.complex_recovery"]["requiresCapabilityProbe"]
        with self.assertRaisesRegex(routing.RoutingError, "capability probe"):
            routing.validate_policy(policy)

    def test_unknown_or_duplicate_policy_ownership_is_rejected(self) -> None:
        policy = routing.load_policy()
        policy["routes"]["bootstrap_review.external_profile"] = copy.deepcopy(
            policy["routes"]["quick_dev.normal"]
        )
        with self.assertRaises(routing.RoutingError):
            routing.validate_policy(policy)


if __name__ == "__main__":
    unittest.main()
