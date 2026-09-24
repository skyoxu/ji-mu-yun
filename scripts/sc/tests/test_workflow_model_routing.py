#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import tempfile
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
        schema_root = SC_ROOT / "schemas"
        schema = json.loads((schema_root / "workflow-model-route-decision.v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual("object", schema["type"])
        self.assertIn("decisionId", schema["required"])
        self.assertIn("consumerState", schema["required"])
        for name in (
            "workflow-model-capability-probe-receipt.v1.schema.json",
            "workflow-model-shadow-execution-receipt.v1.schema.json",
        ):
            receipt_schema = json.loads((schema_root / name).read_text(encoding="utf-8"))
            self.assertFalse(receipt_schema["additionalProperties"])
            self.assertIn("producerId", receipt_schema["required"])

    def test_each_owned_consumer_can_be_disabled_independently(self) -> None:
        cases = {
            "vdd": lambda policy: routing.vdd_decision("standard", policy=policy),
            "quick_dev": lambda policy: routing.quick_dev_decision(
                LauncherTests()._normal_facts(), policy=policy
            ),
            "refactor_acceptance": lambda policy: routing.refactor_acceptance_decision(
                complex_recovery_trigger="candidate_binding_recovery_failed", policy=policy
            ),
        }
        for consumer, decide in cases.items():
            with self.subTest(consumer=consumer):
                policy = routing.load_policy()
                policy["rolloutMode"] = "active"
                policy["consumerControls"][consumer] = "disabled"
                decision = decide(policy)
                self.assertEqual("disabled", decision["status"])
                self.assertEqual("disabled", decision["consumerState"])
                self.assertEqual(
                    {"enabled"},
                    {state for name, state in policy["consumerControls"].items() if name != consumer},
                )

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
            "codex", "exec", "-m", "gpt-6-sol", "-c", 'model_reasoning_effort="medium"',
            "--sandbox", "workspace-write", "-",
        ]))
        with mock.patch.object(routing, "load_policy", return_value=policy):
            result = routing.execute_decision(
                decision,
                root=REPOSITORY_ROOT,
                prompt="stdin prompt",
                output_last_message=REPOSITORY_ROOT / "unused.txt",
                timeout_sec=10,
                runner=runner,
            )
        self.assertEqual("completed", result["status"])
        kwargs = runner.call_args.kwargs
        self.assertEqual("stdin prompt", kwargs["prompt"])
        self.assertEqual("gpt-6-sol", kwargs["codex_model"])
        self.assertEqual("workspace-write", kwargs["codex_sandbox"])
        self.assertEqual(['model_reasoning_effort="medium"'], kwargs["codex_configs"])
        self.assertNotIn("fallback", json.dumps(result).lower())

    def test_unsupported_max_capability_leaves_route_blocked(self) -> None:
        decision = routing.vdd_decision(
            "self-hosted", complex_recovery=True, recovery_trigger="bounded_repair_exhausted",
        )
        self.assertEqual("blocked", decision["status"])
        self.assertEqual("missing", decision["capability"]["state"])

    def test_caller_cannot_self_attest_capability_or_shadow_evidence(self) -> None:
        forged = {
            "status": "passed",
            "model": "gpt-6-sol",
            "effort": "high",
            "backend": "codex-cli",
            "sandbox": "workspace-write",
            "shadowPredicateStatus": "passed",
        }
        with self.assertRaises(TypeError):
            routing.vdd_decision(
                "self-hosted",
                complex_recovery=True,
                recovery_trigger="bounded_repair_exhausted",
                capability_proof=forged,
            )

    def test_capability_proof_requires_policy_bound_producer_receipts(self) -> None:
        with self.assertRaisesRegex(routing.RoutingError, "policy-bound"):
            routing.build_capability_proof(route_id="vdd.complex_recovery")

    def test_policy_bound_probe_and_representative_execution_build_proof(self) -> None:
        policy = routing.load_policy()
        route_id = "vdd.complex_recovery"
        route = policy["routes"][route_id]
        requested = {
            "launchMode": "child",
            "backend": "codex-cli",
            "model": "gpt-6-sol",
            "effort": "high",
            "sandbox": "workspace-write",
        }
        actual = {
            "launched": True,
            "backend": "codex-cli",
            "model": "gpt-6-sol",
            "effort": "high",
            "sandbox": "workspace-write",
            "exitCode": 0,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence_root = root / "logs" / "workflow-model-routing" / "capability-evidence"
            evidence_root.mkdir(parents=True)

            process_path = evidence_root / "execution-result.json"
            process_path.write_text(json.dumps({
                "schemaVersion": "jimuyun.workflow-model-execution-result.v1",
                "requestedExecution": requested,
                "actualExecution": actual,
                "status": "completed",
                "authorizes": [],
            }), encoding="utf-8", newline="\n")
            process_ref = {
                "path": process_path.relative_to(root).as_posix(),
                "sha256": routing._file_hash(process_path),
            }
            common = {
                "producerId": policy["capabilityEvidencePolicy"]["producerId"],
                "routeId": route_id,
                "policyRevision": policy["policyRevision"],
                "observedAt": "2026-08-01T00:00:00Z",
                "authorizes": [],
            }
            probe_path = evidence_root / "probe.json"
            probe_path.write_text(json.dumps({
                "schemaVersion": policy["capabilityEvidencePolicy"]["probeReceiptSchemaVersion"],
                "receiptId": "probe-001",
                **common,
                "status": "passed",
                "processResultRef": process_ref,
            }), encoding="utf-8", newline="\n")
            shadow_path = evidence_root / "shadow.json"
            shadow_path.write_text(json.dumps({
                "schemaVersion": policy["capabilityEvidencePolicy"]["shadowReceiptSchemaVersion"],
                "receiptId": "shadow-001",
                **common,
                "cohortId": "representative-recovery-001",
                "predicateStatus": "passed",
                "representativeExecutionRefs": [process_ref],
            }), encoding="utf-8", newline="\n")
            route["capabilityEvidence"] = {
                "probeReceipt": {
                    "path": probe_path.relative_to(root).as_posix(),
                    "sha256": routing._file_hash(probe_path),
                },
                "shadowReceipt": {
                    "path": shadow_path.relative_to(root).as_posix(),
                    "sha256": routing._file_hash(shadow_path),
                },
            }

            proof = routing.build_capability_proof(
                route_id=route_id, policy=policy, repository_root=root
            )
            self.assertEqual("passed", proof["status"])
            self.assertEqual(1, proof["representativeExecutionCount"])
            self.assertEqual(
                routing.canonical_hash(policy["capabilityEvidencePolicy"]),
                proof["producerBindingHash"],
            )

    def test_requested_actual_identity_drift_fails_execution(self) -> None:
        policy = routing.load_policy()
        policy["rolloutMode"] = "active"
        decision = routing.quick_dev_decision(self._normal_facts(), policy=policy)
        runner = mock.Mock(return_value=(0, "ok", ["codex", "exec", "-"]))
        with mock.patch.object(routing, "load_policy", return_value=policy):
            result = routing.execute_decision(
                decision,
                root=REPOSITORY_ROOT,
                prompt="prompt",
                output_last_message=REPOSITORY_ROOT / "unused.txt",
                timeout_sec=10,
                runner=runner,
            )
        self.assertEqual("failed", result["status"])
        self.assertIsNone(result["actualExecution"]["model"])

    def test_unknown_model_cannot_become_an_active_route(self) -> None:
        policy = routing.load_policy()
        policy["routes"]["quick_dev.normal"]["model"] = "luna"
        with self.assertRaisesRegex(routing.RoutingError, "route model or effort is invalid"):
            routing.validate_policy(policy)

    def test_complex_recovery_route_retains_capability_probe_contract(self) -> None:
        policy = routing.load_policy()
        route = policy["routes"]["vdd.complex_recovery"]
        self.assertEqual("gpt-6-sol", policy["models"][route["model"]]["modelId"])
        self.assertEqual("high", route["effort"])
        self.assertTrue(route["requiresCapabilityProbe"])
        self.assertTrue(route["requiresShadowPredicate"])

    def test_unknown_or_duplicate_policy_ownership_is_rejected(self) -> None:
        policy = routing.load_policy()
        policy["routes"]["bootstrap_review.external_profile"] = copy.deepcopy(
            policy["routes"]["quick_dev.normal"]
        )
        with self.assertRaises(routing.RoutingError):
            routing.validate_policy(policy)

    def test_execution_rejects_a_caller_supplied_noncanonical_policy(self) -> None:
        policy = routing.load_policy()
        policy["rolloutMode"] = "active"
        decision = routing.quick_dev_decision(self._normal_facts(), policy=policy)
        with self.assertRaisesRegex(routing.RoutingError, "canonical policy"):
            routing.execute_decision(
                decision,
                root=REPOSITORY_ROOT,
                prompt="prompt",
                output_last_message=REPOSITORY_ROOT / "unused.txt",
                timeout_sec=10,
                policy=policy,
            )


if __name__ == "__main__":
    unittest.main()
