from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class BootstrapIntegrationTests(unittest.TestCase):
    def minimal_scope_inputs(self) -> dict[str, list[str]]:
        return {
            "implementation_plan": ["execution-plans/example/plan.md"],
            "changed_production_code": ["PhaseA.Platform/Feature.cs"],
            "affected_consumers": ["PhaseA.Platform/Program.cs"],
            "tests_and_acceptance": [
                "PhaseA.Platform.Tests/FeatureTests.cs",
                "logs/ci/example/command-registry.json",
            ],
            "runtime_evidence": [
                "logs/ci/example/acceptance.json",
                "logs/ci/example/composition-receipt.json",
            ],
            "repository_rules": ["AGENTS.md"],
            "referenced_standards": ["docs/standards/phase-service.md"],
        }

    def lineage_state(self, family_id: str, rounds: int) -> dict:
        import bootstrap_integration

        value = {
            "schemaVersion": "bootstrap-review-lineage-state.v1",
            "lineageFamilyId": family_id,
            "semanticRoundsConsumed": rounds,
            "consumedRoundNumbers": list(range(1, rounds + 1)),
            "defaultFullReviewRoundLimit": 2,
            "hardFullReviewRoundLimit": 3,
            "nextFullReviewRound": None if rounds == 3 else rounds + 1,
            "state": "manual_pause" if rounds == 3 else "available",
            "runs": [
                {
                    "runDirectory": f"logs/review-{number}",
                    "reviewId": f"review-{number}",
                    "changeId": "stable-change",
                    "fullReviewRound": number,
                    "inputHash": "sha256:" + f"{number}" * 64,
                }
                for number in range(1, rounds + 1)
            ],
            "authorizes": [],
        }
        value["lineageStateHash"] = bootstrap_integration._canonical_hash(value)
        return value

    def repair_completeness(
        self,
        family_id: str,
        rounds: int,
        *,
        novel: list[str] | None = None,
        authority_changed: bool = False,
        boundary_changed: bool = False,
    ) -> dict:
        return {
            "schemaVersion": "acceptance-repair-completeness.v1",
            "status": "passed",
            "acceptanceTarget": "execution-plans/example",
            "lineageFamilyId": family_id,
            "semanticRoundsConsumed": rounds,
            "predecessorRun": f"logs/review-{rounds}" if rounds else None,
            "baselineManifest": {
                "path": "logs/ci/example/baseline.json",
                "sha256": "sha256:" + "1" * 64,
            },
            "candidateManifest": {
                "path": "logs/ci/example/candidate.json",
                "sha256": "sha256:" + "2" * 64,
            },
            "changedPaths": ["PhaseA.Platform/Feature.cs"],
            "changedPathBindings": [{
                "path": "PhaseA.Platform/Feature.cs",
                "state": "present",
                "sha256": "sha256:" + "e" * 64,
            }],
            "directConsumers": [{"path": "PhaseA.Platform/Program.cs", "sha256": "sha256:" + "b" * 64}],
            "targetedTests": [{"path": "PhaseA.Platform.Tests/FeatureTests.cs", "sha256": "sha256:" + "c" * 64}],
            "validationRefs": [{
                "path": "logs/ci/example/composition-receipt.json",
                "sha256": "sha256:" + "0" * 64,
            }],
            "rootCauseInventories": [{
                "inventoryId": "feature-callsites",
                "searchTerm": "Feature",
                "searchRoots": ["PhaseA.Platform"],
                "matches": [{
                    "path": "PhaseA.Platform/Feature.cs",
                    "sha256": "sha256:" + "e" * 64,
                    "lineNumbers": [1],
                }],
                "addressedPaths": ["PhaseA.Platform/Feature.cs"],
                "exclusions": [],
            }],
            "compositionChecks": [{
                "checkId": "feature-composition",
                "bindings": [
                    {
                        "role": "producer",
                        "path": "PhaseA.Platform/Feature.cs",
                        "sha256": "sha256:" + "e" * 64,
                    },
                    {
                        "role": "consumer",
                        "path": "PhaseA.Platform/Program.cs",
                        "sha256": "sha256:" + "b" * 64,
                    },
                ],
                "commandRegistry": {
                    "path": "logs/ci/example/command-registry.json",
                    "sha256": "sha256:" + "f" * 64,
                },
                "receipt": {
                    "path": "logs/ci/example/composition-receipt.json",
                    "sha256": "sha256:" + "0" * 64,
                },
            }],
            "novelP0P1FindingIds": novel or [],
            "authorityGraphChanged": authority_changed,
            "authorityGraphArtifacts": (
                ["PhaseA.Platform/Feature.cs"] if authority_changed else []
            ),
            "highRiskBoundaryChanged": boundary_changed,
            "highRiskBoundaryArtifacts": (
                ["PhaseA.Platform/Feature.cs"] if boundary_changed else []
            ),
            "requestHash": "sha256:" + "a" * 64,
            "authorizes": [],
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
        decision = {"requirement": "required", "requiredCompanionCapabilityExpectations": [{"capabilityId": "acceptance-inventory-attestation", "capabilityVersion": "1.0", "producerRole": "acceptance_auditor"}]}
        scope = bootstrap_integration.build_attestation_scope(
            decision, binding, {"partitions": ["semantic"]}, {"clauses": ["c1"]},
            {"checks": ["k1"]}, "sha256:" + "b" * 64,
        )
        attestation = {"schemaVersion": "bootstrap-acceptance-inventory-attestation.v1", "reviewId": "review-1", "attemptId": "attempt-1", "inputHash": "sha256:" + "c" * 64, "capabilityId": "acceptance-inventory-attestation", "capabilityVersion": "1.0", "producerRole": "acceptance_auditor", "status": "complete", "scopeHash": scope["scopeHash"], "coverage": []}
        bootstrap_integration.validate_inventory_attestation(attestation, binding, scope)
        wrong = copy.deepcopy(attestation)
        wrong["scopeHash"] = "sha256:" + "d" * 64
        with self.assertRaisesRegex(bootstrap_integration.BootstrapBindingError, "scope"):
            bootstrap_integration.validate_inventory_attestation(wrong, binding, scope)
        stale_scope = copy.deepcopy(scope)
        stale_scope["sourceInventoryHash"] = "sha256:" + "d" * 64
        with self.assertRaisesRegex(bootstrap_integration.BootstrapBindingError, "consumer scope hash"):
            bootstrap_integration.validate_inventory_attestation(attestation, binding, stale_scope)

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

    def test_import_v2_producer_output_satisfies_the_only_v2_consumer_contract(self) -> None:
        import acceptance_cli
        import bootstrap_integration

        binding = {
            "schemaVersion": "bootstrap-capability-binding.v1",
            "status": "bound",
            "requiredCompanionCapabilities": [{
                "capabilityId": "acceptance-inventory-attestation",
                "capabilityVersion": "1.0",
                "producerRole": "acceptance_auditor",
                "schemaPath": "schema.json",
                "schemaHash": "sha256:" + "a" * 64,
            }],
            "authorizes": [],
        }
        scope = bootstrap_integration.build_attestation_scope(
            {"requirement": "required"},
            binding,
            {"partitions": []},
            {"clauses": []},
            {"checks": []},
            "sha256:" + "b" * 64,
        )
        attestation = {
            "schemaVersion": "bootstrap-acceptance-inventory-attestation.v1",
            "reviewId": "review-1",
            "attemptId": "attempt-1",
            "inputHash": "sha256:" + "c" * 64,
            "capabilityId": "acceptance-inventory-attestation",
            "capabilityVersion": "1.0",
            "producerRole": "acceptance_auditor",
            "status": "complete",
            "scopeHash": scope["scopeHash"],
            "coverage": [],
        }
        finalized = {
            "schemaVersion": "bootstrap-finalized-run-validation.v1",
            "validationStatus": "passed",
            "finalStatus": "clean",
            "controlPlaneRevision": "bootstrap-control-plane.v2",
            "generatedAt": "2026-07-30T00:00:00Z",
        }
        result = {
            "controlPlaneRevision": "bootstrap-control-plane.v2",
            "bootstrapRunDir": "logs/ci/review-1",
            "finalizedRun": finalized,
            "finalizedRunCoreHash": bootstrap_integration._canonical_hash(
                {key: value for key, value in finalized.items() if key != "generatedAt"}
            ),
            "inventoryAttestation": attestation,
            "inventoryAttestationHash": bootstrap_integration._canonical_hash(attestation),
            "bindingHash": bootstrap_integration._canonical_hash(binding),
            "scopeHash": bootstrap_integration._canonical_hash(scope),
        }
        request = {
            "repositoryRoot": ".",
            "bootstrapRunDir": "logs/ci/review-1",
            "binding": binding,
            "scope": scope,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path, output_path = root / "request.json", root / "output.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            with mock.patch.object(acceptance_cli, "load_verified_bootstrap_import", return_value=result):
                produced = acceptance_cli.import_bootstrap_command(
                    str(request_path), str(output_path)
                )
        bootstrap_integration.validate_import_envelope(
            produced, {"binding": binding, "scope": scope}
        )
        tampered = copy.deepcopy(produced)
        tampered["finalizedRun"]["finalStatus"] = "blocked"
        with self.assertRaisesRegex(
            bootstrap_integration.BootstrapBindingError, "invalid"
        ):
            bootstrap_integration.validate_import_envelope(
                tampered, {"binding": binding, "scope": scope}
            )

    def test_verified_import_reads_acceptance_role_bundle(self) -> None:
        import bootstrap_integration

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "logs" / "review-1"
            bundle_path = run_dir / "reviewer-outputs" / "acceptance_auditor.role-bundle.json"
            bundle_path.parent.mkdir(parents=True)
            (run_dir / "review-input.json").write_text("{}", encoding="utf-8")
            bundle_path.write_text(
                json.dumps({"inventoryAttestation": {"status": "complete"}}),
                encoding="utf-8",
            )
            module = mock.Mock()
            module.read_json.side_effect = lambda path: json.loads(path.read_text(encoding="utf-8"))
            module.validate_finalized_run_evidence.return_value = {
                "schemaVersion": "bootstrap-finalized-run-validation.v2",
                "validationStatus": "passed",
                "finalStatus": "clean",
                "controlPlaneRevision": "bootstrap-control-plane.v2",
                "generatedAt": "2026-07-30T00:00:00Z",
            }
            with (
                mock.patch.object(bootstrap_integration, "_load_bootstrap_module", return_value=module),
                mock.patch.object(bootstrap_integration, "validate_inventory_attestation"),
                mock.patch.object(bootstrap_integration, "validate_import_envelope"),
            ):
                result = bootstrap_integration.load_verified_bootstrap_import(
                    root, "logs/review-1", {}, {}
                )
        self.assertEqual({"status": "complete"}, result["inventoryAttestation"])
        self.assertIn(
            "acceptance_auditor.role-bundle.json",
            str(module.read_json.call_args_list[-1].args[0]),
        )

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
        self.assertEqual(9, len(result["scope"]))
        self.assertIsNone(result["directoryScopeAttestation"])
        self.assertEqual("execution-plans/example", result["lineageAnchor"])
        self.assertTrue(result["lineageFamilyId"].startswith("ria-"))

    def test_lineage_family_is_stable_across_successor_files_in_one_plan(self) -> None:
        import bootstrap_integration

        original = bootstrap_integration.derive_acceptance_lineage(
            ["execution-plans/example/plan.md"]
        )
        successor = bootstrap_integration.derive_acceptance_lineage(
            [
                "execution-plans/example/plan.md",
                "execution-plans/example/successor/round-2/repair-plan.v1.json",
            ]
        )
        self.assertEqual(original, successor)

    def test_lineage_family_is_stable_across_windows_path_casing(self) -> None:
        import bootstrap_integration

        lower = bootstrap_integration.derive_acceptance_lineage(
            ["execution-plans/example/plan.md"]
        )
        upper = bootstrap_integration.derive_acceptance_lineage(
            ["EXECUTION-PLANS/EXAMPLE/plan.md"]
        )
        self.assertEqual(lower["lineageFamilyId"], upper["lineageFamilyId"])

    def test_bounded_route_uses_full_then_focused_then_deterministic_lanes(self) -> None:
        import bootstrap_integration

        decision = {"requirement": "required"}
        scope = bootstrap_integration.build_minimal_review_scope(self.minimal_scope_inputs())
        family = scope["lineageFamilyId"]
        initial = bootstrap_integration.project_bounded_review_route(
            decision, scope, self.lineage_state(family, 0), None
        )
        self.assertEqual("full_implementation_conformance", initial["routeKind"])
        round_two = bootstrap_integration.project_bounded_review_route(
            decision,
            scope,
            self.lineage_state(family, 1),
            self.repair_completeness(family, 1),
        )
        self.assertEqual("focused_repair_review", round_two["routeKind"])
        round_two_with_changed_context = bootstrap_integration.project_bounded_review_route(
            decision,
            scope,
            self.lineage_state(family, 1),
            self.repair_completeness(
                family, 1, authority_changed=True, boundary_changed=True
            ),
        )
        self.assertEqual(
            "focused_repair_review", round_two_with_changed_context["routeKind"]
        )
        deterministic = bootstrap_integration.project_bounded_review_route(
            decision,
            scope,
            self.lineage_state(family, 2),
            self.repair_completeness(family, 2),
        )
        self.assertEqual("deterministic_only", deterministic["routeKind"])
        self.assertIsNone(deterministic["nextFullReviewRound"])

    def test_required_route_rejects_an_omitted_or_tampered_lineage_projection(self) -> None:
        import bootstrap_integration

        decision = {"requirement": "required"}
        scope = bootstrap_integration.build_minimal_review_scope(self.minimal_scope_inputs())
        with self.assertRaisesRegex(
            bootstrap_integration.BootstrapBindingError, "inspect-lineage"
        ):
            bootstrap_integration.project_bounded_review_route(decision, scope, None, None)
        stale = self.lineage_state(scope["lineageFamilyId"], 1)
        stale["semanticRoundsConsumed"] = 0
        with self.assertRaisesRegex(
            bootstrap_integration.BootstrapBindingError, "lineage state"
        ):
            bootstrap_integration.project_bounded_review_route(decision, scope, stale, None)

    def test_round_three_requires_a_typed_escalation_trigger(self) -> None:
        import bootstrap_integration

        decision = {"requirement": "required"}
        scope = bootstrap_integration.build_minimal_review_scope(self.minimal_scope_inputs())
        family = scope["lineageFamilyId"]
        authority = bootstrap_integration.project_bounded_review_route(
            decision,
            scope,
            self.lineage_state(family, 2),
            self.repair_completeness(family, 2, authority_changed=True),
        )
        self.assertEqual("full_implementation_conformance", authority["routeKind"])
        self.assertEqual("authority_context_graph_changed", authority["roundEntryReason"])
        novel = bootstrap_integration.project_bounded_review_route(
            decision,
            scope,
            self.lineage_state(family, 2),
            self.repair_completeness(family, 2, novel=["BSR-NEW-P1"]),
        )
        self.assertEqual("novel_p0_p1", novel["roundEntryReason"])

    def test_bounded_route_rejects_a_partial_repair_projection(self) -> None:
        import bootstrap_integration

        decision = {"requirement": "required"}
        scope = bootstrap_integration.build_minimal_review_scope(self.minimal_scope_inputs())
        family = scope["lineageFamilyId"]
        incomplete = self.repair_completeness(family, 1)
        incomplete["rootCauseInventories"][0].pop("matches")
        with self.assertRaisesRegex(
            bootstrap_integration.BootstrapBindingError,
            "repair completeness projection",
        ):
            bootstrap_integration.project_bounded_review_route(
                decision, scope, self.lineage_state(family, 1), incomplete
            )

    def test_bounded_route_rejects_a_repair_projection_outside_its_review_scope(self) -> None:
        import bootstrap_integration

        decision = {"requirement": "required"}
        scope = bootstrap_integration.build_minimal_review_scope(self.minimal_scope_inputs())
        family = scope["lineageFamilyId"]
        mismatched = self.repair_completeness(family, 1)
        mismatched["directConsumers"][0]["path"] = "PhaseA.Platform/OtherConsumer.cs"
        mismatched["compositionChecks"][0]["bindings"][1]["path"] = (
            "PhaseA.Platform/OtherConsumer.cs"
        )
        with self.assertRaisesRegex(
            bootstrap_integration.BootstrapBindingError,
            "outside the bootstrap review scope",
        ):
            bootstrap_integration.project_bounded_review_route(
                decision, scope, self.lineage_state(family, 1), mismatched
            )

    def test_bounded_route_rejects_a_tampered_review_scope(self) -> None:
        import bootstrap_integration

        decision = {"requirement": "required"}
        scope = bootstrap_integration.build_minimal_review_scope(self.minimal_scope_inputs())
        family = scope["lineageFamilyId"]
        scope["contextClasses"]["affected-consumers"] = ["PhaseA.Platform/Other.cs"]
        with self.assertRaisesRegex(
            bootstrap_integration.BootstrapBindingError,
            "review scope",
        ):
            bootstrap_integration.project_bounded_review_route(
                decision,
                scope,
                self.lineage_state(family, 1),
                self.repair_completeness(family, 1),
            )

    def test_three_consumed_rounds_fail_closed_without_a_successor_reset(self) -> None:
        import bootstrap_integration

        decision = {"requirement": "required"}
        scope = bootstrap_integration.build_minimal_review_scope(self.minimal_scope_inputs())
        route = bootstrap_integration.project_bounded_review_route(
            decision,
            scope,
            self.lineage_state(scope["lineageFamilyId"], 3),
            None,
        )
        self.assertEqual("manual_pause", route["routeKind"])
        self.assertIsNone(route["nextFullReviewRound"])

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
            "repository_root": ".",
            "decision": {"requirement": "required", "requiredCompanionCapabilityExpectations": []},
            "binding": None,
            "launch_authorization": None,
            "scope_inputs": self.minimal_scope_inputs(),
        }
        scope = acceptance_cli.build_minimal_review_scope(request["scope_inputs"])
        request["lineage_state"] = self.lineage_state(scope["lineageFamilyId"], 0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "request.json"
            output_path = root / "route.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            with mock.patch.object(
                acceptance_cli,
                "load_current_lineage_state",
                return_value=request["lineage_state"],
            ):
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

    def test_prepare_bootstrap_rejects_a_self_hashed_stale_lineage_projection(self) -> None:
        import acceptance_cli

        request = {
            "repository_root": ".",
            "decision": {"requirement": "required", "requiredCompanionCapabilityExpectations": []},
            "binding": None,
            "launch_authorization": None,
            "scope_inputs": self.minimal_scope_inputs(),
        }
        scope = acceptance_cli.build_minimal_review_scope(request["scope_inputs"])
        request["lineage_state"] = self.lineage_state(scope["lineageFamilyId"], 0)
        current = self.lineage_state(scope["lineageFamilyId"], 1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            with mock.patch.object(
                acceptance_cli, "load_current_lineage_state", return_value=current
            ), self.assertRaisesRegex(acceptance_cli.InputError, "repository-owned projection"):
                acceptance_cli.prepare_bootstrap_command(
                    str(request_path), str(root / "route.json")
                )

    def test_prepare_bootstrap_rejects_a_stale_repair_projection_after_replay(self) -> None:
        import acceptance_cli

        scope = acceptance_cli.build_minimal_review_scope(self.minimal_scope_inputs())
        family = scope["lineageFamilyId"]
        projection = self.repair_completeness(family, 1)
        request = {
            "repository_root": ".",
            "decision": {"requirement": "required", "requiredCompanionCapabilityExpectations": []},
            "binding": None,
            "launch_authorization": None,
            "scope_inputs": self.minimal_scope_inputs(),
            "lineage_state": self.lineage_state(family, 1),
            "repair_completeness": projection,
            "repair_completeness_request": {"producer": "request"},
        }
        replayed = copy.deepcopy(projection)
        replayed["requestHash"] = "sha256:" + "9" * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            with mock.patch.object(
                acceptance_cli,
                "load_current_lineage_state",
                return_value=request["lineage_state"],
            ), mock.patch.object(
                acceptance_cli, "audit_repair_completeness", return_value=replayed
            ), self.assertRaisesRegex(acceptance_cli.InputError, "producer-reproducible"):
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
