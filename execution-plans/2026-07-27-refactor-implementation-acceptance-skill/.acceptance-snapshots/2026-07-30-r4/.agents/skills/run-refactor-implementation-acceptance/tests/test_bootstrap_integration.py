from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class BootstrapIntegrationTests(unittest.TestCase):
    def minimal_scope_inputs(self) -> dict[str, list[str]]:
        return {
            "implementation_plan": ["execution-plans/example/plan.md"],
            "changed_production_code": ["PhaseA.Platform/Feature.cs"],
            "affected_consumers": ["PhaseA.Platform/Program.cs"],
            "tests_and_acceptance": ["PhaseA.Platform.Tests/FeatureTests.cs"],
            "runtime_evidence": ["logs/ci/example/acceptance.json"],
            "repository_rules": ["AGENTS.md"],
            "referenced_standards": ["docs/standards/phase-service.md"],
        }

    def test_required_decision_binds_profile_companion_identity(self) -> None:
        import bootstrap_integration

        decision = {"requirement": "required", "requiredCompanionCapabilityExpectations": [{"capabilityId": "acceptance-inventory-attestation", "capabilityVersion": "1.0", "producerRole": "acceptance_auditor"}]}
        profile = {"controlPlaneRevision": "bootstrap-control-plane.v2", "routeVersion": "bootstrap-review-route.v2", "reviewProfile": "review-policy://bootstrap-implementation-conformance/v1", "policyRevision": "sha256:" + "a" * 64, "companionCapabilities": [{"capabilityId": "acceptance-inventory-attestation", "capabilityVersion": "1.0", "producerRole": "acceptance_auditor", "schemaPath": "schema.json", "schemaHash": "sha256:" + "b" * 64}]}
        binding = bootstrap_integration.bind_capabilities(decision, profile)
        self.assertEqual("acceptance-inventory-attestation", binding["requiredCompanionCapabilities"][0]["capabilityId"])
        self.assertEqual([], binding["authorizes"])

    def test_attestation_scope_binds_required_decision_binding_and_derived_inputs(self) -> None:
        import bootstrap_integration

        decision = {"requirement": "required", "requiredCompanionCapabilityExpectations": [{"capabilityId": "acceptance-inventory-attestation", "capabilityVersion": "1.0", "producerRole": "acceptance_auditor"}]}
        binding = {"schemaVersion": "bootstrap-capability-binding.v1", "status": "bound", "requiredCompanionCapabilities": [{"capabilityId": "acceptance-inventory-attestation", "capabilityVersion": "1.0", "producerRole": "acceptance_auditor", "schemaPath": "schema.json", "schemaHash": "sha256:" + "a" * 64}], "authorizes": []}
        artifact_view_hash = "sha256:" + "b" * 64
        scope = bootstrap_integration.build_attestation_scope(decision, binding, {"partitions": ["semantic"]}, {"clauses": ["c1"]}, {"checks": ["k1"]}, artifact_view_hash)
        self.assertEqual(artifact_view_hash, scope["scopeHash"])
        self.assertTrue(scope["consumerScopeHash"].startswith("sha256:"))
        self.assertEqual([], scope["authorizes"])

    def test_complete_attestation_must_match_the_frozen_scope_and_capability(self) -> None:
        import bootstrap_integration

        binding = {"schemaVersion": "bootstrap-capability-binding.v1", "status": "bound", "requiredCompanionCapabilities": [{"capabilityId": "acceptance-inventory-attestation", "capabilityVersion": "1.0", "producerRole": "acceptance_auditor", "schemaPath": "schema.json", "schemaHash": "sha256:" + "a" * 64}], "authorizes": []}
        scope = {"scopeHash": "sha256:" + "b" * 64}
        attestation = {"schemaVersion": "bootstrap-acceptance-inventory-attestation.v1", "reviewId": "review-1", "attemptId": "attempt-1", "inputHash": "sha256:" + "c" * 64, "capabilityId": "acceptance-inventory-attestation", "capabilityVersion": "1.0", "producerRole": "acceptance_auditor", "status": "complete", "scopeHash": scope["scopeHash"], "coverage": []}
        bootstrap_integration.validate_inventory_attestation(attestation, binding, scope)
        wrong = copy.deepcopy(attestation)
        wrong["scopeHash"] = "sha256:" + "d" * 64
        with self.assertRaisesRegex(bootstrap_integration.BootstrapBindingError, "scope"):
            bootstrap_integration.validate_inventory_attestation(wrong, binding, scope)

    def test_import_envelope_requires_all_hash_bound_consumer_inputs(self) -> None:
        import bootstrap_integration

        expected = {name: "sha256:" + (character * 64) for name, character in {
            "decisionHash": "a", "bindingHash": "b", "launchAuthorizationHash": "c", "localReceiptHash": "d",
            "reviewInputHash": "e", "artifactViewHash": "f", "roleBundleHash": "0", "attestationHash": "1",
            "candidateHash": "2", "baseMatrixHash": "3", "findingPolicyHash": "4", "profileHash": "5",
            "policyHash": "6", "routeHash": "7", "companionSchemaHash": "8", "finalResultHash": "9",
            "verifierHash": "a", "p2DispositionsHash": "b",
        }.items()}
        envelope = {"schemaVersion": "bootstrap-import-envelope.v1", "controlPlaneRevision": "bootstrap-control-plane.v2", **expected, "authorizes": []}
        bootstrap_integration.validate_import_envelope(envelope, expected)
        incomplete = dict(envelope)
        incomplete.pop("roleBundleHash")
        with self.assertRaisesRegex(bootstrap_integration.BootstrapBindingError, "fields"):
            bootstrap_integration.validate_import_envelope(incomplete, expected)

    def test_execution_projection_keeps_required_bootstrap_awaiting_authorization(self) -> None:
        import bootstrap_integration

        decision = {"requirement": "required", "requiredCompanionCapabilityExpectations": []}
        state = bootstrap_integration.project_bootstrap_execution_state(decision, launch_authorization=None, binding=None)
        self.assertEqual("awaiting_authorization", state["state"])
        self.assertEqual("waiting-external", state["actionStates"]["prepare-bootstrap"])
        deterministic = bootstrap_integration.project_bootstrap_execution_state({"requirement": "not_required", "requiredCompanionCapabilityExpectations": []}, launch_authorization=None, binding=None)
        self.assertEqual("not_applicable", deterministic["state"])
        self.assertTrue(all(value == "not_applicable" for value in deterministic["actionStates"].values()))

    def test_minimal_review_scope_is_explicit_and_profile_complete(self) -> None:
        import bootstrap_integration

        result = bootstrap_integration.build_minimal_review_scope(self.minimal_scope_inputs())
        self.assertEqual("minimal-complete-closure", result["strategy"])
        self.assertEqual("bootstrap-implementation-conformance", result["profile"])
        self.assertEqual(
            {
                "implementation-plan", "changed-production-code", "affected-consumers",
                "tests-and-acceptance", "runtime-evidence", "repository-rules",
                "referenced-standards",
            },
            set(result["contextClasses"]),
        )
        self.assertEqual(7, len(result["scope"]))
        self.assertIsNone(result["directoryScopeAttestation"])

    def test_minimal_review_scope_rejects_directory_or_glob_inputs(self) -> None:
        import bootstrap_integration

        for invalid in ("PhaseA.Platform/", "PhaseA.Platform/**/*.cs", "../outside.cs"):
            inputs = self.minimal_scope_inputs()
            inputs["changed_production_code"] = [invalid]
            with self.subTest(invalid=invalid), self.assertRaises(
                bootstrap_integration.BootstrapBindingError
            ):
                bootstrap_integration.build_minimal_review_scope(inputs)

    def test_prepare_bootstrap_requires_and_publishes_minimal_scope(self) -> None:
        import acceptance_cli

        request = {
            "decision": {"requirement": "required", "requiredCompanionCapabilityExpectations": []},
            "binding": None,
            "launch_authorization": None,
            "scope_inputs": self.minimal_scope_inputs(),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "request.json"
            output_path = root / "route.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            route = acceptance_cli.prepare_bootstrap_command(str(request_path), str(output_path))
        self.assertEqual("minimal-complete-closure", route["reviewScope"]["strategy"])
        self.assertEqual("run-phase-bootstrap-review", route["nextAction"])

        request.pop("scope_inputs")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            with self.assertRaisesRegex(acceptance_cli.InputError, "minimal review scope"):
                acceptance_cli.prepare_bootstrap_command(
                    str(request_path), str(root / "route.json")
                )

    def test_finding_mapping_rejects_unknown_or_tombstoned_check(self) -> None:
        import bootstrap_integration

        mapping = {
            "schemaVersion": "bootstrap-finding-acceptance-map.v1", "findingId": "F-1",
            "findingHash": "sha256:" + "a" * 64, "mappingKind": "check",
            "checkId": "RA-SKILL-001", "authorizes": [],
        }
        bootstrap_integration.validate_finding_mapping(mapping, {"RA-SKILL-001"}, set())
        with self.assertRaisesRegex(bootstrap_integration.BootstrapBindingError, "tombstoned"):
            bootstrap_integration.validate_finding_mapping(mapping, {"RA-SKILL-001"}, {"RA-SKILL-001"})

    def test_mapping_approval_requires_current_authorized_identity_and_lineage(self) -> None:
        import bootstrap_integration

        approval = {
            "schemaVersion": "bootstrap-finding-mapping-approval.v1", "approverRole": "acceptance_owner",
            "identityEvidenceHash": "sha256:" + "a" * 64, "expiresAtUtc": "2099-01-01T00:00:00Z",
            "findingHash": "sha256:" + "b" * 64, "mappingHash": "sha256:" + "c" * 64,
            "matrixHash": "sha256:" + "d" * 64, "lineageHash": "sha256:" + "e" * 64,
            "importEnvelopeHash": "sha256:" + "f" * 64, "authorizes": [],
        }
        bootstrap_integration.validate_mapping_approval(approval, "acceptance_owner", "sha256:" + "b" * 64, "sha256:" + "d" * 64, "sha256:" + "e" * 64, "sha256:" + "f" * 64)
        expired = dict(approval)
        expired["expiresAtUtc"] = "2000-01-01T00:00:00Z"
        with self.assertRaisesRegex(bootstrap_integration.BootstrapBindingError, "expired"):
            bootstrap_integration.validate_mapping_approval(expired, "acceptance_owner", "sha256:" + "b" * 64, "sha256:" + "d" * 64, "sha256:" + "e" * 64, "sha256:" + "f" * 64)


if __name__ == "__main__":
    unittest.main()
