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
    def current_decision(self) -> dict:
        from review_requirement import decide_review_requirement

        policy = json.loads((SKILL_ROOT / "policies" / "semantic-review-trigger-policy.v1.json").read_text(encoding="utf-8"))

        return decide_review_requirement({
            "candidateIdentity": {
                "changedPaths": ["runtime/phase-a/ensure-phasea.ps1"],
                "knowledgeArtifacts": [],
            },
            "deterministicEvidence": {"status": "passed", "hash": "sha256:" + "a" * 64},
            "policy": policy,
        })

    def test_bootstrap_module_fails_when_requested_repository_has_no_control_plane(self) -> None:
        import bootstrap_integration

        with tempfile.TemporaryDirectory() as temp:
            candidate_root = Path(temp) / "candidate-without-installed-skills"
            candidate_root.mkdir()
            with self.assertRaisesRegex(Exception, "Repository-owned"):
                bootstrap_integration._load_bootstrap_module(candidate_root)

    def test_bootstrap_module_comes_from_requested_repository(self) -> None:
        import bootstrap_integration

        with tempfile.TemporaryDirectory() as temp:
            candidate_root = Path(temp).resolve()
            module_path = candidate_root / ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py"
            module_path.parent.mkdir(parents=True)
            module_path.write_text("REPOSITORY_MARKER = 'requested-root'\n", encoding="utf-8")
            bootstrap = bootstrap_integration._load_bootstrap_module(candidate_root)

        self.assertEqual("requested-root", bootstrap.REPOSITORY_MARKER)
        self.assertEqual(module_path.resolve(), Path(bootstrap.__file__).resolve())

    def test_finalized_replay_uses_bootstrap_historical_mode(self) -> None:
        import bootstrap_integration

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            run_relative = "logs/ci/review-r3"
            run_dir = root / run_relative
            run_dir.mkdir(parents=True)
            envelope = self.finalized_envelope()
            module = mock.Mock()
            module.load_run.return_value = (run_dir, {"reviewId": "review-1"}, root)
            module.validate_finalized_run_evidence.return_value = envelope
            with mock.patch.object(
                bootstrap_integration, "_load_bootstrap_module", return_value=module
            ):
                result = bootstrap_integration.replay_finalized_bootstrap_run(
                    root, run_relative
                )

        self.assertEqual(envelope, result)
        module.load_run.assert_called_once_with(
            str(run_dir), require_fresh_artifacts=False
        )
        module.validate_finalized_run_evidence.assert_called_once_with(
            run_dir,
            {"reviewId": "review-1"},
            root,
            historical_replay=True,
        )

    def test_finalized_replay_uses_focused_envelope_projection(self) -> None:
        import bootstrap_integration

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            run_relative = "logs/ci/focused-review"
            run_dir = root / run_relative
            run_dir.mkdir(parents=True)
            manifest = {
                "reviewId": "focused-review-1",
                "profileName": "bootstrap-focused-repair-verification",
            }
            envelope = {
                "schemaVersion": "bootstrap-focused-repair-validation-envelope.v1",
                "status": "passed",
                "generatedAt": "2026-08-02T00:00:00Z",
            }
            (run_dir / "focused-repair-validation-envelope.json").write_text(
                json.dumps(envelope), encoding="utf-8", newline="\n"
            )
            module = mock.Mock()
            module.load_run.return_value = (run_dir, manifest, root)
            module.focused_repair_validation_envelope.return_value = envelope
            with mock.patch.object(
                bootstrap_integration, "_load_bootstrap_module", return_value=module
            ):
                result = bootstrap_integration.replay_finalized_bootstrap_run(
                    root, run_relative
                )

        self.assertEqual(envelope, result)
        module.focused_repair_validation_envelope.assert_called_once_with(
            run_dir,
            manifest,
            root,
            generated_at="2026-08-02T00:00:00Z",
        )
        module.validate_finalized_run_evidence.assert_not_called()

    def finalized_envelope(
        self,
        *,
        candidate_binding_hash: str = "sha256:" + "2" * 64,
        review_id: str = "review-1",
        input_hash: str = "sha256:" + "1" * 64,
        lineage_family_id: str | None = None,
    ) -> dict:
        hashes = {
            "reviewInput": "sha256:" + "1" * 64,
            "preflightResult": "sha256:" + "2" * 64,
            "gateState": "sha256:" + "3" * 64,
            "candidates": "sha256:" + "4" * 64,
            "rejections": "sha256:" + "5" * 64,
            "finalResult": "sha256:" + "6" * 64,
            "dispositions": "sha256:" + "7" * 64,
            "metrics": "sha256:" + "8" * 64,
            "verifierOutput": "sha256:" + "9" * 64,
            "p2Dispositions": None,
        }
        return {
            "schemaVersion": "bootstrap-finalized-run-validation.v3",
            "validationStatus": "passed",
            "reviewId": review_id,
            "changeId": "stable-change",
            "lineageFamilyId": lineage_family_id or self.review_scope()["lineageFamilyId"],
            "fullReviewRound": 1,
            "profileName": "bootstrap-implementation-conformance",
            "reviewProfile": "review-policy://bootstrap-implementation-conformance/v1",
            "routeVersion": "bootstrap-review-route.v2",
            "controlPlaneRevision": "bootstrap-control-plane.v2",
            "policyRevision": "sha256:" + "a" * 64,
            "profileHash": "sha256:" + "b" * 64,
            "authorityRevision": "0123456789abcdef0123456789abcdef01234567",
            "inputHash": input_hash,
            "authorityContextHash": "sha256:" + "d" * 64,
            "candidateBindingHash": candidate_binding_hash,
            "reviewEntryDecisionHash": None,
            "repairReviewDeltaHash": None,
            "artifactHashes": hashes,
            "finalStatus": "clean",
            "findingClosure": {
                "candidateCount": 0,
                "visibleFindingCount": 0,
                "confirmedCount": 0,
                "advisoryCount": 0,
                "unverifiedCount": 0,
                "refutedCount": 0,
                "p2FixedCount": 0,
                "p2DeferredCount": 0,
                "p2RefutedCount": 0,
            },
            "validatorRevision": "bootstrap-finalized-run-validator.v4",
            "validatorHash": "sha256:" + "e" * 64,
            "authorizes": [],
            "doesNotAuthorize": [
                "plan-acceptance", "implementation-acceptance", "protected-handoff",
                "release", "commit", "done",
            ],
            "generatedAt": "2026-07-30T00:00:00Z",
        }

    def candidate_identity(self) -> dict:
        import bootstrap_integration

        value = {
            "schemaVersion": "acceptance-bootstrap-reuse-candidate.v2",
            "acceptanceRunInputPath": "execution-plans/example/acceptance-run.json",
            "acceptanceRunInputFileHash": "sha256:" + "d" * 64,
            "candidateContentManifestPath": "execution-plans/example/candidate.json",
            "candidateContentManifestFileHash": "sha256:" + "e" * 64,
            "candidateContentManifestHash": "sha256:" + "f" * 64,
            "candidateCustodyHash": "sha256:" + "1" * 64,
            "changedPaths": ["PhaseA.Platform/Feature.cs"],
            "changedPathBindings": [{
                "path": "PhaseA.Platform/Feature.cs",
                "state": "present",
                "sha256": "sha256:" + "0" * 64,
            }],
            "knowledgeArtifacts": [
                {
                    "path": "AGENTS.md",
                    "sha256": "sha256:" + "a" * 64,
                },
                {
                    "path": "execution-plans/example/knowledge-context.json",
                    "sha256": "sha256:" + "b" * 64,
                },
            ],
            "authorizes": [],
        }
        return {**value, "identityHash": bootstrap_integration._canonical_hash(value)}

    def minimal_scope_inputs(self) -> dict[str, list[str]]:
        return {
            "implementation_plan": ["execution-plans/example/plan.md"],
            "changed_production_code": ["PhaseA.Platform/Feature.cs"],
            "affected_consumers": ["PhaseA.Platform/Program.cs"],
            "tests_and_acceptance": [
                "PhaseA.Platform.Tests/FeatureTests.cs",
                "execution-plans/example/acceptance-run.json",
                "execution-plans/example/candidate.json",
                "execution-plans/example/knowledge-context.json",
                "logs/ci/example/command-registry.json",
            ],
            "runtime_evidence": [
                "logs/ci/example/acceptance.json",
                "logs/ci/example/composition-receipt.json",
            ],
            "repository_rules": ["AGENTS.md"],
            "referenced_standards": ["docs/standards/phase-service.md"],
        }

    def skill_scope_inputs(self) -> dict[str, list[str]]:
        return {
            "skill_source": [".agents/skills/run-phase-bootstrap-review/SKILL.md"],
            "operator_guide": ["docs/09-bootstrap-review-operator-guide.md"],
            "route_or_cli": [".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py"],
            "profiles_and_config": [".agents/skills/run-phase-bootstrap-review/references/review-profiles.v1.json"],
            "schemas": [".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-review-input.v1.schema.json"],
            "tests": [".agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py"],
            "usage_evidence": ["logs/ci/example/bootstrap-self-audit.json"],
            "repository_rules": ["AGENTS.md"],
        }

    def review_scope(self) -> dict:
        import bootstrap_integration

        return bootstrap_integration.build_minimal_review_scope(self.minimal_scope_inputs())

    def bootstrap_route(self) -> dict:
        import bootstrap_integration

        scope = self.review_scope()
        lineage = self.lineage_state(scope["lineageFamilyId"], 0)
        projection = bootstrap_integration.project_bounded_review_route(
            {"requirement": "required"}, scope, lineage, None
        )
        route = {
            "schemaVersion": "implementation-acceptance-bootstrap-route.v1",
            "bootstrapExecutionState": {"state": "awaiting_external"},
            "reviewScope": scope,
            **projection,
            "nextAction": "run-phase-bootstrap-review",
            "authorizes": [],
        }
        return {
            "path": "logs/ci/example/bootstrap-route.json",
            "fileHash": "sha256:" + "b" * 64,
            "route": route,
            "routeHash": bootstrap_integration._canonical_hash(route),
        }

    def bootstrap_artifacts(self) -> list[dict]:
        scope = self.review_scope()
        candidate = self.candidate_identity()
        hashes = {path: "sha256:" + "0" * 64 for path in scope["scope"]}
        hashes.update({
            candidate["acceptanceRunInputPath"]: candidate["acceptanceRunInputFileHash"],
            candidate["candidateContentManifestPath"]: candidate["candidateContentManifestFileHash"],
            **{item["path"]: item["sha256"] for item in candidate["knowledgeArtifacts"]},
        })
        return [
            {"artifact": path, "sha256": digest}
            for path, digest in sorted(hashes.items())
        ]

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
                "targetedTests": ["PhaseA.Platform.Tests/FeatureTests.cs"],
                "commandRegistry": {
                    "path": "logs/ci/example/command-registry.json",
                    "sha256": "sha256:" + "f" * 64,
                },
                "receipt": {
                    "path": "logs/ci/example/composition-receipt.json",
                    "sha256": "sha256:" + "0" * 64,
                },
                "controlledReplay": {
                    "schemaVersion": "acceptance-composition-controlled-replay.v1",
                    "authorizes": [],
                    "commandId": "feature-composition",
                    "commandRegistryHash": "sha256:" + "f" * 64,
                    "environmentIdentity": {"names": [], "hash": "sha256:" + "1" * 64},
                    "invocation": {},
                    "invocationHash": "sha256:" + "2" * 64,
                    "exitCode": 0,
                    "writeManifestDelta": {},
                    "writeManifestDeltaHash": "sha256:" + "3" * 64,
                    "inputBindings": [],
                    "inputBindingsHash": "sha256:" + "4" * 64,
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

    def focused_repair_import_fixture(self, root: Path) -> tuple[Path, Path, dict]:
        import acceptance_cli

        family_id = self.review_scope()["lineageFamilyId"]
        completeness = self.repair_completeness(family_id, 1)
        route = {
            "schemaVersion": "implementation-acceptance-bootstrap-route.v1",
            "routeKind": "focused_repair_verification",
            "lineageFamilyId": family_id,
            "semanticRoundsConsumed": 1,
            "nextFullReviewRound": 2,
            "roundEntryReason": None,
            "repairCompletenessHash": acceptance_cli.canonical_hash(completeness),
            "authorizes": [],
        }
        fixture_dir = root / "logs" / "focused-import"
        fixture_dir.mkdir(parents=True)
        run_dir = fixture_dir / "run"
        run_dir.mkdir()
        route_path = fixture_dir / "acceptance-route.json"
        completeness_path = fixture_dir / "repair-completeness.json"
        route_path.write_text(json.dumps(route), encoding="utf-8")
        completeness_path.write_text(json.dumps(completeness), encoding="utf-8")
        envelope = {
            "schemaVersion": "bootstrap-focused-repair-validation-envelope.v1",
            "status": "passed",
            "nextAction": "deterministic-closure",
            "lineageFamilyId": family_id,
            "reviewId": "focused-review-1",
            "fullReviewRound": 2,
            "acceptanceRepairRouteHash": acceptance_cli._file_hash(route_path),
            "repairCompletenessHash": acceptance_cli._file_hash(completeness_path),
            "authorizes": [],
            "doesNotAuthorize": [
                "implementation-acceptance",
                "protected-handoff",
                "release",
                "commit",
                "done",
            ],
        }
        envelope_path = run_dir / "focused-repair-validation-envelope.json"
        envelope_path.write_text(json.dumps(envelope), encoding="utf-8")

        def reference(path: Path) -> dict:
            return {
                "path": path.relative_to(root).as_posix(),
                "sha256": acceptance_cli._file_hash(path),
            }

        request = {
            "repositoryRoot": str(root),
            "focusedRun": run_dir.relative_to(root).as_posix(),
            "acceptanceRepairRoute": reference(route_path),
            "repairCompleteness": reference(completeness_path),
        }
        request_path = fixture_dir / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        return request_path, fixture_dir / "result.json", request

    def test_focused_repair_import_accepts_only_current_passed_bindings(self) -> None:
        import acceptance_cli

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            request_path, output_path, _ = self.focused_repair_import_fixture(root)
            envelope = json.loads(
                (request_path.parent / "run/focused-repair-validation-envelope.json").read_text(
                    encoding="utf-8"
                )
            )
            with mock.patch.object(
                acceptance_cli, "replay_finalized_bootstrap_run", return_value=envelope
            ):
                result = acceptance_cli.import_focused_repair_command(
                    str(request_path), str(output_path)
                )

        self.assertEqual("ready_for_deterministic_evaluation", result["status"])
        self.assertEqual(2, result["fullReviewRound"])
        self.assertEqual([], result["authorizes"])
        self.assertEqual(
            {
                "commit",
                "done",
                "implementation-acceptance",
                "protected-handoff",
                "release",
            },
            set(result["doesNotAuthorize"]),
        )

    def test_focused_repair_import_rejects_stale_references(self) -> None:
        import acceptance_cli

        for reference_name in (
            "acceptanceRepairRoute",
            "repairCompleteness",
        ):
            with self.subTest(reference=reference_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                request_path, output_path, request = self.focused_repair_import_fixture(root)
                request[reference_name]["sha256"] = "sha256:" + "f" * 64
                request_path.write_text(json.dumps(request), encoding="utf-8")
                envelope = json.loads(
                    (request_path.parent / "run/focused-repair-validation-envelope.json").read_text(
                        encoding="utf-8"
                    )
                )
                with mock.patch.object(
                    acceptance_cli, "replay_finalized_bootstrap_run", return_value=envelope
                ):
                    with self.assertRaisesRegex(acceptance_cli.InputError, "missing or stale"):
                        acceptance_cli.import_focused_repair_command(
                            str(request_path), str(output_path)
                        )

    def test_focused_repair_import_rejects_binding_drift_and_escalation(self) -> None:
        import acceptance_cli

        mutations = (
            ("acceptanceRepairRoute", "lineageFamilyId", "wrong-family", "route does not match"),
            ("repairCompleteness", "status", "failed", "completeness does not match"),
        )
        for reference_name, field, value, message in mutations:
            with self.subTest(reference=reference_name, field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                request_path, output_path, request = self.focused_repair_import_fixture(root)
                document_path = root / request[reference_name]["path"]
                document = json.loads(document_path.read_text(encoding="utf-8"))
                document[field] = value
                document_path.write_text(json.dumps(document), encoding="utf-8")
                request[reference_name]["sha256"] = acceptance_cli._file_hash(document_path)
                request_path.write_text(json.dumps(request), encoding="utf-8")
                envelope = json.loads(
                    (request_path.parent / "run/focused-repair-validation-envelope.json").read_text(
                        encoding="utf-8"
                    )
                )
                with mock.patch.object(
                    acceptance_cli, "replay_finalized_bootstrap_run", return_value=envelope
                ):
                    with self.assertRaisesRegex(acceptance_cli.InputError, message):
                        acceptance_cli.import_focused_repair_command(
                            str(request_path), str(output_path)
                        )

    def test_focused_repair_import_rejects_noncanonical_run(self) -> None:
        import acceptance_cli

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            request_path, output_path, _ = self.focused_repair_import_fixture(root)
            with mock.patch.object(
                acceptance_cli,
                "replay_finalized_bootstrap_run",
                side_effect=acceptance_cli.BootstrapBindingError("canonical replay failed"),
            ):
                with self.assertRaisesRegex(acceptance_cli.InputError, "canonical replay failed"):
                    acceptance_cli.import_focused_repair_command(
                        str(request_path), str(output_path)
                    )

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

    def test_current_candidate_identity_revalidates_manifest_bytes_and_custody(self) -> None:
        import acceptance_cli

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "execution-plans" / "example"
            target.mkdir(parents=True)
            baseline = {"baseline": "current"}
            candidate = {
                "candidate": "current",
                "files": [{
                    "change_type": "modified",
                    "baseline_path": "Feature.cs",
                    "baseline_sha256": "sha256:" + "1" * 64,
                    "candidate_path": "Feature.cs",
                    "candidate_sha256": "sha256:" + "2" * 64,
                }],
            }
            (target / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
            (target / "candidate.json").write_text(json.dumps(candidate), encoding="utf-8")
            run_input = {
                "target": str(target),
                "changed_paths": ["Feature.cs"],
                "baseline_content_manifest_path": "baseline.json",
                "baseline_content_manifest_hash": acceptance_cli.canonical_hash(baseline),
                "candidate_content_manifest_path": "candidate.json",
                "candidate_content_manifest_hash": acceptance_cli.canonical_hash(candidate),
            }
            custody = {"schemaVersion": "acceptance-candidate-custody.v1", "authorizes": []}
            knowledge = {
                "path": "knowledge-context.json",
                "sha256": "sha256:" + "a" * 64,
                "acceptedDecisions": [{
                    "candidate": {"path": "AGENTS.md", "source_sha256": "b" * 64}
                }],
            }
            prepared = {
                "schemaVersion": "acceptance-run-input.v1",
                "input": run_input,
                "inputHash": acceptance_cli.canonical_hash(run_input),
                "candidateCustody": custody,
                "knowledgeContext": knowledge,
                "authorizes": [],
            }
            prepared_path = target / "acceptance-run.json"
            prepared_path.write_text(json.dumps(prepared), encoding="utf-8")
            with (
                mock.patch.object(acceptance_cli, "validate_run_input"),
                mock.patch.object(acceptance_cli, "validate_baseline_manifest"),
                mock.patch.object(acceptance_cli, "validate_candidate_manifest"),
                mock.patch.object(
                    acceptance_cli,
                    "candidate_changed_paths",
                    side_effect=lambda value: ["Feature.cs"] if "candidate" in value else self.fail(
                        "changed paths were derived from a non-candidate document"
                    ),
                ),
                mock.patch.object(
                    acceptance_cli, "verify_manifest_bytes", return_value=custody
                ),
                mock.patch.object(
                    acceptance_cli, "freeze_knowledge_context", return_value=knowledge
                ),
            ):
                identity = acceptance_cli.load_current_candidate_identity(
                    root, prepared_path.relative_to(root).as_posix()
                )
                self.assertEqual(
                    "execution-plans/example/candidate.json",
                    identity["candidateContentManifestPath"],
                )
                self.assertEqual(
                    ["AGENTS.md", "execution-plans/example/knowledge-context.json"],
                    [item["path"] for item in identity["knowledgeArtifacts"]],
                )
                self.assertEqual([{
                    "path": "Feature.cs",
                    "state": "present",
                    "sha256": "sha256:" + "2" * 64,
                }], identity["changedPathBindings"])
                with mock.patch.object(
                    acceptance_cli, "candidate_changed_paths", return_value=["unexpected.txt"]
                ):
                    with self.assertRaisesRegex(acceptance_cli.InputError, "changed_paths"):
                        acceptance_cli.load_current_candidate_identity(
                            root, prepared_path.relative_to(root).as_posix()
                        )
                (target / "candidate.json").write_text(
                    json.dumps({"candidate": "drifted"}), encoding="utf-8"
                )
                with self.assertRaisesRegex(
                    acceptance_cli.InputError, "candidate content manifest hash is stale"
                ):
                    acceptance_cli.load_current_candidate_identity(
                        root, prepared_path.relative_to(root).as_posix()
                    )

    def test_current_candidate_identity_revalidates_knowledge_context(self) -> None:
        import acceptance_cli

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "execution-plans" / "example"
            target.mkdir(parents=True)
            baseline = {"baseline": "current"}
            candidate = {"candidate": "current"}
            (target / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
            (target / "candidate.json").write_text(json.dumps(candidate), encoding="utf-8")
            run_input = {
                "target": str(target), "changed_paths": [],
                "baseline_content_manifest_path": "baseline.json",
                "baseline_content_manifest_hash": acceptance_cli.canonical_hash(baseline),
                "candidate_content_manifest_path": "candidate.json",
                "candidate_content_manifest_hash": acceptance_cli.canonical_hash(candidate),
            }
            custody = {"schemaVersion": "acceptance-candidate-custody.v1", "authorizes": []}
            knowledge = {"path": "knowledge-context.v1.json", "sha256": "sha256:" + "a" * 64}
            prepared = {
                "schemaVersion": "acceptance-run-input.v1", "input": run_input,
                "inputHash": acceptance_cli.canonical_hash(run_input),
                "candidateCustody": custody, "knowledgeContext": knowledge, "authorizes": [],
            }
            prepared_path = target / "acceptance-run.json"
            prepared_path.write_text(json.dumps(prepared), encoding="utf-8")
            with (
                mock.patch.object(acceptance_cli, "validate_run_input"),
                mock.patch.object(acceptance_cli, "validate_baseline_manifest"),
                mock.patch.object(acceptance_cli, "validate_candidate_manifest"),
                mock.patch.object(acceptance_cli, "candidate_changed_paths", return_value=[]),
                mock.patch.object(acceptance_cli, "verify_manifest_bytes", return_value=custody),
                mock.patch.object(
                    acceptance_cli, "freeze_knowledge_context",
                    return_value={**knowledge, "sha256": "sha256:" + "b" * 64},
                ),
            ):
                with self.assertRaisesRegex(acceptance_cli.InputError, "knowledge context is stale"):
                    acceptance_cli.load_current_candidate_identity(
                        root, prepared_path.relative_to(root).as_posix()
                    )

    def test_import_v3_producer_output_satisfies_the_exact_reuse_contract(self) -> None:
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
            "inputHash": "sha256:" + "1" * 64,
            "capabilityId": "acceptance-inventory-attestation",
            "capabilityVersion": "1.0",
            "producerRole": "acceptance_auditor",
            "status": "complete",
            "scopeHash": scope["scopeHash"],
            "coverage": [],
        }
        finalized = self.finalized_envelope(candidate_binding_hash="sha256:" + "d" * 64)
        bootstrap_route = self.bootstrap_route()
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
            "candidateIdentity": self.candidate_identity(),
            "candidateIdentityHash": bootstrap_integration._canonical_hash(
                self.candidate_identity()
            ),
            "bootstrapRoutePath": bootstrap_route["path"],
            "bootstrapRouteFileHash": bootstrap_route["fileHash"],
            "bootstrapRouteHash": bootstrap_route["routeHash"],
        }
        request = {
            "repositoryRoot": ".",
            "bootstrapRunDir": "logs/ci/review-1",
            "binding": binding,
            "scope": scope,
            "acceptanceRunInput": "execution-plans/example/acceptance-run.json",
            "bootstrapRoute": bootstrap_route["path"],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path, output_path = root / "request.json", root / "output.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            with (
                mock.patch.object(
                    acceptance_cli, "load_current_candidate_identity",
                    return_value=self.candidate_identity(),
                ),
                mock.patch.object(
                    acceptance_cli, "load_verified_bootstrap_import", return_value=result
                ),
                mock.patch.object(
                    acceptance_cli, "load_current_bootstrap_route",
                    return_value=bootstrap_route,
                ),
            ):
                produced = acceptance_cli.import_bootstrap_command(
                    str(request_path), str(output_path)
                )
        bootstrap_integration.validate_import_envelope(
            produced, {
                "bootstrapRunDir": "logs/ci/review-1",
                "binding": binding,
                "scope": scope,
                "candidateIdentity": self.candidate_identity(),
                "bootstrapRoute": bootstrap_route,
            }
        )
        legacy_finalized = {
            "schemaVersion": "bootstrap-finalized-run-validation.v2",
            "validationStatus": "passed",
            "finalStatus": "clean",
            "controlPlaneRevision": "bootstrap-control-plane.v2",
        }
        legacy = {
            "schemaVersion": "bootstrap-import-envelope.v2",
            "controlPlaneRevision": "bootstrap-control-plane.v2",
            "bootstrapRunDir": "logs/ci/legacy-review",
            "finalizedRun": legacy_finalized,
            "finalizedRunCoreHash": bootstrap_integration._canonical_hash(legacy_finalized),
            "inventoryAttestation": attestation,
            "inventoryAttestationHash": bootstrap_integration._canonical_hash(attestation),
            "bindingHash": bootstrap_integration._canonical_hash(binding),
            "scopeHash": bootstrap_integration._canonical_hash(scope),
            "authorizes": [],
        }
        bootstrap_integration.validate_import_envelope(
            legacy, {"binding": binding, "scope": scope}
        )
        tampered = copy.deepcopy(produced)
        tampered["finalizedRun"]["finalStatus"] = "blocked"
        with self.assertRaisesRegex(
            bootstrap_integration.BootstrapBindingError, "invalid"
        ):
            bootstrap_integration.validate_import_envelope(
                tampered, {
                    "bootstrapRunDir": "logs/ci/review-1",
                    "binding": binding,
                    "scope": scope,
                    "candidateIdentity": self.candidate_identity(),
                    "bootstrapRoute": bootstrap_route,
                }
            )

        drifted_attestation = copy.deepcopy(produced)
        drifted_attestation["inventoryAttestation"]["reviewId"] = "another-review"
        drifted_attestation["inventoryAttestationHash"] = bootstrap_integration._canonical_hash(
            drifted_attestation["inventoryAttestation"]
        )
        with self.assertRaisesRegex(
            bootstrap_integration.BootstrapBindingError, "does not bind"
        ):
            bootstrap_integration.validate_import_envelope(drifted_attestation, {
                "bootstrapRunDir": "logs/ci/review-1",
                "binding": binding,
                "scope": scope,
                "candidateIdentity": self.candidate_identity(),
                "bootstrapRoute": bootstrap_route,
            })

        legacy = copy.deepcopy(produced)
        legacy["finalizedRun"]["schemaVersion"] = "bootstrap-finalized-run-validation.v1"
        legacy["finalizedRun"].pop("candidateBindingHash")
        legacy["finalizedRunCoreHash"] = bootstrap_integration._canonical_hash({
            key: value for key, value in legacy["finalizedRun"].items() if key != "generatedAt"
        })
        with self.assertRaisesRegex(bootstrap_integration.BootstrapBindingError, "invalid"):
            bootstrap_integration.validate_import_envelope(legacy, {
                "bootstrapRunDir": "logs/ci/review-1",
                "binding": binding, "scope": scope,
                "candidateIdentity": self.candidate_identity(),
                "bootstrapRoute": bootstrap_route,
            })

        minimal = copy.deepcopy(produced)
        minimal["finalizedRun"] = {
            "schemaVersion": "bootstrap-finalized-run-validation.v3",
            "validationStatus": "passed",
            "finalStatus": "clean",
            "controlPlaneRevision": "bootstrap-control-plane.v2",
            "candidateBindingHash": "sha256:" + "d" * 64,
        }
        minimal["finalizedRunCoreHash"] = bootstrap_integration._canonical_hash(
            minimal["finalizedRun"]
        )
        with self.assertRaisesRegex(bootstrap_integration.BootstrapBindingError, "invalid"):
            bootstrap_integration.validate_import_envelope(minimal, {
                "bootstrapRunDir": "logs/ci/review-1",
                "binding": binding,
                "scope": scope,
                "candidateIdentity": self.candidate_identity(),
                "bootstrapRoute": bootstrap_route,
            })

        drifted_dir = copy.deepcopy(produced)
        drifted_dir["bootstrapRunDir"] = "logs/ci/another-review"
        with self.assertRaisesRegex(bootstrap_integration.BootstrapBindingError, "invalid"):
            bootstrap_integration.validate_import_envelope(drifted_dir, {
                "bootstrapRunDir": "logs/ci/review-1",
                "binding": binding,
                "scope": scope,
                "candidateIdentity": self.candidate_identity(),
                "bootstrapRoute": bootstrap_route,
            })

        manual_route = copy.deepcopy(bootstrap_route)
        manual_route["route"]["routeKind"] = "manual_pause"
        manual_route["route"]["nextAction"] = "manual-pause"
        manual_route["routeHash"] = bootstrap_integration._canonical_hash(
            manual_route["route"]
        )
        with self.assertRaisesRegex(
            bootstrap_integration.BootstrapBindingError, "not eligible"
        ):
            bootstrap_integration.validate_import_envelope(produced, {
                "bootstrapRunDir": "logs/ci/review-1",
                "binding": binding,
                "scope": scope,
                "candidateIdentity": self.candidate_identity(),
                "bootstrapRoute": manual_route,
            })

    def test_import_v2_schema_remains_legacy_compatible_and_v3_owns_exact_reuse(self) -> None:
        legacy = json.loads(
            (SKILL_ROOT / "schemas" / "bootstrap-import-envelope.v2.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("bootstrap-import-envelope.v2", legacy["properties"]["schemaVersion"]["const"])
        self.assertNotIn("candidateIdentity", legacy["required"])
        self.assertEqual(
            ["bootstrap-finalized-run-validation.v1", "bootstrap-finalized-run-validation.v2"],
            legacy["properties"]["finalizedRun"]["properties"]["schemaVersion"]["enum"],
        )
        exact = json.loads(
            (SKILL_ROOT / "schemas" / "bootstrap-import-envelope.v3.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("bootstrap-import-envelope.v3", exact["properties"]["schemaVersion"]["const"])
        self.assertIn("bootstrapRouteHash", exact["required"])
        self.assertIn("changedPaths", exact["properties"]["candidateIdentity"]["required"])
        self.assertIn(
            "changedPathBindings",
            exact["properties"]["candidateIdentity"]["required"],
        )
        self.assertIn("knowledgeArtifacts", exact["properties"]["candidateIdentity"]["required"])
        self.assertIn("reviewId", exact["$defs"]["finalizedRun"]["required"])
        self.assertIn(
            "capabilityId", exact["$defs"]["inventoryAttestation"]["required"]
        )
        import bootstrap_integration

        bootstrap = bootstrap_integration._load_bootstrap_module(SKILL_ROOT.parents[2])
        runtime = bootstrap.load_schema_runtime()
        invalid = {
            "schemaVersion": "bootstrap-import-envelope.v3",
            "controlPlaneRevision": "bootstrap-control-plane.v2",
            "bootstrapRunDir": "logs/review-1",
            "finalizedRun": {},
            "finalizedRunCoreHash": "sha256:" + "1" * 64,
            "inventoryAttestation": {},
            "inventoryAttestationHash": "sha256:" + "2" * 64,
            "bindingHash": "sha256:" + "3" * 64,
            "scopeHash": "sha256:" + "4" * 64,
            "candidateIdentity": self.candidate_identity(),
            "candidateIdentityHash": "sha256:" + "5" * 64,
            "bootstrapRoutePath": "logs/bootstrap-route.json",
            "bootstrapRouteFileHash": "sha256:" + "6" * 64,
            "bootstrapRouteHash": "sha256:" + "7" * 64,
            "authorizes": [],
        }
        self.assertTrue(runtime.schema_errors(exact, invalid, {}))

    def test_verified_import_reads_acceptance_role_bundle(self) -> None:
        import bootstrap_integration

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "logs" / "review-1"
            bundle_path = run_dir / "reviewer-outputs" / "acceptance_auditor.role-bundle.json"
            bundle_path.parent.mkdir(parents=True)
            (run_dir / "review-input.json").write_text("{}", encoding="utf-8")
            finalized = self.finalized_envelope()
            attestation = {
                "status": "complete",
                "reviewId": finalized["reviewId"],
                "inputHash": finalized["inputHash"],
            }
            bundle_path.write_text(
                json.dumps({"inventoryAttestation": attestation}),
                encoding="utf-8",
            )
            module = mock.Mock()
            module.read_json.side_effect = lambda path: json.loads(path.read_text(encoding="utf-8"))
            candidate_identity = self.candidate_identity()
            bootstrap_route = self.bootstrap_route()
            manifest = {
                "candidateBindingHash": "sha256:" + "2" * 64,
                "profileName": "bootstrap-implementation-conformance",
                "reviewProfile": "review-policy://bootstrap-implementation-conformance/v1",
                "artifacts": self.bootstrap_artifacts(),
                "contextClassArtifacts": bootstrap_route["route"]["reviewScope"][
                    "contextClasses"
                ],
            }
            module.load_run.return_value = (run_dir, manifest, root)
            module.validate_finalized_run_evidence.return_value = finalized
            module.build_lineage_state.return_value = self.lineage_state(
                finalized["lineageFamilyId"], 1
            )
            with (
                mock.patch.object(bootstrap_integration, "_load_bootstrap_module", return_value=module),
                mock.patch.object(bootstrap_integration, "validate_inventory_attestation"),
                mock.patch.object(bootstrap_integration, "validate_import_envelope"),
            ):
                result = bootstrap_integration.load_verified_bootstrap_import(
                    root, "logs/review-1", {}, {}, candidate_identity, bootstrap_route
                )
                deleted_candidate = copy.deepcopy(candidate_identity)
                deleted_path = deleted_candidate["changedPathBindings"][0]["path"]
                deleted_hash = deleted_candidate["changedPathBindings"][0]["sha256"]
                deleted_candidate["changedPathBindings"][0]["state"] = "deleted"
                stable = {
                    key: value
                    for key, value in deleted_candidate.items()
                    if key != "identityHash"
                }
                deleted_candidate["identityHash"] = (
                    bootstrap_integration._canonical_hash(stable)
                )
                deleted_manifest = copy.deepcopy(manifest)
                deleted_manifest["artifacts"] = [
                    item for item in deleted_manifest["artifacts"]
                    if item["artifact"] != deleted_path
                ]
                deleted_manifest["acceptanceCandidateFreeze"] = {
                    "schemaVersion": "bootstrap-acceptance-candidate-freeze.v1",
                    "acceptanceRunInput": {
                        "path": deleted_candidate["acceptanceRunInputPath"],
                        "sha256": deleted_candidate["acceptanceRunInputFileHash"],
                    },
                    "candidateIdentityHash": deleted_candidate["identityHash"],
                    "baselineResolvedCommit": "1" * 40,
                    "deletedArtifacts": [{
                        "artifact": deleted_path,
                        "sha256": deleted_hash,
                    }],
                    "authorizes": [],
                }
                module.load_run.return_value = (run_dir, deleted_manifest, root)
                bootstrap_integration.load_verified_bootstrap_import(
                    root, "logs/review-1", {}, {}, deleted_candidate, bootstrap_route
                )
                tampered_freeze = copy.deepcopy(deleted_manifest)
                tampered_freeze["acceptanceCandidateFreeze"]["candidateIdentityHash"] = (
                    "sha256:" + "9" * 64
                )
                module.load_run.return_value = (run_dir, tampered_freeze, root)
                with self.assertRaisesRegex(
                    bootstrap_integration.BootstrapBindingError,
                    "candidate freeze is invalid",
                ):
                    bootstrap_integration.load_verified_bootstrap_import(
                        root, "logs/review-1", {}, {}, deleted_candidate, bootstrap_route
                    )
                module.load_run.return_value = (run_dir, manifest, root)
                incomplete_manifest = copy.deepcopy(manifest)
                missing_scope_path = "docs/standards/phase-service.md"
                incomplete_manifest["artifacts"] = [
                    artifact
                    for artifact in incomplete_manifest["artifacts"]
                    if artifact["artifact"] != missing_scope_path
                ]
                module.load_run.return_value = (run_dir, incomplete_manifest, root)
                with self.assertRaisesRegex(
                    bootstrap_integration.BootstrapBindingError,
                    "complete review scope",
                ):
                    bootstrap_integration.load_verified_bootstrap_import(
                        root, "logs/review-1", {}, {}, candidate_identity, bootstrap_route
                    )
                outside_candidate = copy.deepcopy(candidate_identity)
                outside_candidate["changedPaths"] = ["PhaseA.Platform/Outside.cs"]
                outside_candidate["changedPathBindings"][0]["path"] = (
                    "PhaseA.Platform/Outside.cs"
                )
                stable = {
                    key: value
                    for key, value in outside_candidate.items()
                    if key != "identityHash"
                }
                outside_candidate["identityHash"] = bootstrap_integration._canonical_hash(stable)
                module.load_run.return_value = (run_dir, manifest, root)
                with self.assertRaisesRegex(
                    bootstrap_integration.BootstrapBindingError,
                    "changed-production scope",
                ):
                    bootstrap_integration.load_verified_bootstrap_import(
                        root, "logs/review-1", {}, {}, outside_candidate, bootstrap_route
                    )
                module.build_lineage_state.return_value = self.lineage_state(
                    finalized["lineageFamilyId"], 2
                )
                with self.assertRaisesRegex(
                    bootstrap_integration.BootstrapBindingError,
                    "current lineage transition",
                ):
                    bootstrap_integration.load_verified_bootstrap_import(
                        root, "logs/review-1", {}, {}, candidate_identity, bootstrap_route
                    )
                module.build_lineage_state.return_value = self.lineage_state(
                    finalized["lineageFamilyId"], 1
                )
                drifted_candidate = copy.deepcopy(candidate_identity)
                drifted_candidate["changedPathBindings"][0]["sha256"] = (
                    "sha256:" + "9" * 64
                )
                stable = {
                    key: value
                    for key, value in drifted_candidate.items()
                    if key != "identityHash"
                }
                drifted_candidate["identityHash"] = (
                    bootstrap_integration._canonical_hash(stable)
                )
                with self.assertRaisesRegex(
                    bootstrap_integration.BootstrapBindingError,
                    "reviewed bytes",
                ):
                    bootstrap_integration.load_verified_bootstrap_import(
                        root, "logs/review-1", {}, {}, drifted_candidate, bootstrap_route
                    )
                alternate_route = copy.deepcopy(bootstrap_route)
                context = alternate_route["route"]["reviewScope"]["contextClasses"]
                tests_path = context["tests-and-acceptance"].pop()
                runtime_path = context["runtime-evidence"].pop()
                context["tests-and-acceptance"].append(runtime_path)
                context["runtime-evidence"].append(tests_path)
                context["tests-and-acceptance"].sort()
                context["runtime-evidence"].sort()
                scope = alternate_route["route"]["reviewScope"]
                stable_scope = {key: value for key, value in scope.items() if key != "scopeHash"}
                scope["scopeHash"] = bootstrap_integration._canonical_hash(stable_scope)
                alternate_route["routeHash"] = bootstrap_integration._canonical_hash(
                    alternate_route["route"]
                )
                with self.assertRaisesRegex(
                    bootstrap_integration.BootstrapBindingError,
                    "context classes",
                ):
                    bootstrap_integration.load_verified_bootstrap_import(
                        root, "logs/review-1", {}, {}, candidate_identity, alternate_route
                    )
                (run_dir / "run-seal.json").write_text(
                    "{}\n", encoding="utf-8", newline="\n"
                )
                with self.assertRaisesRegex(
                    bootstrap_integration.BootstrapBindingError,
                    "active finalized run",
                ):
                    bootstrap_integration.load_verified_bootstrap_import(
                        root, "logs/review-1", {}, {}, candidate_identity, bootstrap_route
                    )
        self.assertEqual(attestation, result["inventoryAttestation"])
        self.assertIn(
            "acceptance_auditor.role-bundle.json",
            str(module.read_json.call_args_list[-1].args[0]),
        )

    def test_verified_import_rejects_candidate_not_bound_by_bootstrap_artifacts(self) -> None:
        import bootstrap_integration

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "logs" / "review-1"
            run_dir.mkdir(parents=True)
            candidate_identity = self.candidate_identity()
            bootstrap_route = self.bootstrap_route()
            manifest = {
                "candidateBindingHash": "sha256:" + "2" * 64,
                "profileName": "bootstrap-implementation-conformance",
                "reviewProfile": "review-policy://bootstrap-implementation-conformance/v1",
                "contextClassArtifacts": bootstrap_route["route"]["reviewScope"][
                    "contextClasses"
                ],
                "artifacts": [{
                    "artifact": candidate_identity["acceptanceRunInputPath"],
                    "sha256": "sha256:" + "9" * 64,
                }],
            }
            module = mock.Mock()
            module.load_run.return_value = (run_dir, manifest, root)
            finalized = self.finalized_envelope()
            module.validate_finalized_run_evidence.return_value = finalized
            module.read_json.return_value = {"inventoryAttestation": {"status": "complete"}}
            module.build_lineage_state.return_value = self.lineage_state(
                finalized["lineageFamilyId"], 1
            )
            with (
                mock.patch.object(
                    bootstrap_integration, "_load_bootstrap_module", return_value=module
                ),
                self.assertRaisesRegex(
                    bootstrap_integration.BootstrapBindingError,
                    "does not bind the current Acceptance candidate",
                ),
            ):
                bootstrap_integration.load_verified_bootstrap_import(
                    root, "logs/review-1", {}, {}, candidate_identity, bootstrap_route
                )

    def test_round_two_import_rejects_a_different_launch_route_binding(self) -> None:
        import bootstrap_integration

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "logs" / "review-2"
            bundle_path = run_dir / "reviewer-outputs" / "acceptance_auditor.role-bundle.json"
            bundle_path.parent.mkdir(parents=True)
            bundle_path.write_text(
                json.dumps({"inventoryAttestation": {"status": "complete"}}),
                encoding="utf-8",
            )
            candidate_identity = self.candidate_identity()
            scope = self.review_scope()
            family_id = scope["lineageFamilyId"]
            predecessor = self.lineage_state(family_id, 1)
            projection = bootstrap_integration.project_bounded_review_route(
                {"requirement": "required"},
                scope,
                predecessor,
                self.repair_completeness(family_id, 1),
            )
            route = {
                "schemaVersion": "implementation-acceptance-bootstrap-route.v1",
                "bootstrapExecutionState": {"state": "awaiting_external"},
                "reviewScope": scope,
                **projection,
                "nextAction": "run-phase-bootstrap-review",
                "authorizes": [],
            }
            bootstrap_route = {
                "path": "logs/ci/example/round-2-route.json",
                "fileHash": "sha256:" + "b" * 64,
                "route": route,
                "routeHash": bootstrap_integration._canonical_hash(route),
            }
            finalized = self.finalized_envelope(
                review_id="review-2",
                input_hash="sha256:" + "2" * 64,
                lineage_family_id=family_id,
            )
            finalized["fullReviewRound"] = 2
            manifest = {
                "candidateBindingHash": finalized["candidateBindingHash"],
                "profileName": "bootstrap-implementation-conformance",
                "reviewProfile": "review-policy://bootstrap-implementation-conformance/v1",
                "contextClassArtifacts": scope["contextClasses"],
                "artifacts": self.bootstrap_artifacts(),
                "acceptanceRepairRoute": {
                    "path": bootstrap_route["path"],
                    "sha256": bootstrap_route["fileHash"],
                },
            }
            module = mock.Mock()
            module.load_run.return_value = (run_dir, manifest, root)
            module.validate_finalized_run_evidence.return_value = finalized
            module.read_json.side_effect = lambda path: json.loads(
                path.read_text(encoding="utf-8")
            )
            module.build_lineage_state.return_value = self.lineage_state(family_id, 2)
            alternate_route = copy.deepcopy(bootstrap_route)
            alternate_route["path"] = "logs/ci/example/other-round-2-route.json"
            alternate_route["fileHash"] = "sha256:" + "c" * 64
            with (
                mock.patch.object(
                    bootstrap_integration, "_load_bootstrap_module", return_value=module
                ),
                self.assertRaisesRegex(
                    bootstrap_integration.BootstrapBindingError,
                    "another Acceptance repair route",
                ),
            ):
                bootstrap_integration.load_verified_bootstrap_import(
                    root,
                    "logs/review-2",
                    {},
                    {},
                    candidate_identity,
                    alternate_route,
                )

    def test_verified_import_rejects_non_conformance_profile(self) -> None:
        import bootstrap_integration

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "logs" / "review-1"
            run_dir.mkdir(parents=True)
            manifest = {
                "candidateBindingHash": "sha256:" + "2" * 64,
                "profileName": "bootstrap-upstream-plan",
                "reviewProfile": "review-policy://bootstrap-upstream-plan/v1",
                "artifacts": [],
            }
            module = mock.Mock()
            module.load_run.return_value = (run_dir, manifest, root)
            module.validate_finalized_run_evidence.return_value = self.finalized_envelope()
            module.read_json.return_value = {"inventoryAttestation": {}}
            with (
                mock.patch.object(
                    bootstrap_integration, "_load_bootstrap_module", return_value=module
                ),
                self.assertRaisesRegex(
                    bootstrap_integration.BootstrapBindingError,
                    "implementation-conformance profile",
                ),
            ):
                bootstrap_integration.load_verified_bootstrap_import(
                    root, "logs/review-1", {}, {}, self.candidate_identity(),
                    self.bootstrap_route(),
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
        self.assertEqual(12, len(result["scope"]))
        self.assertIsNone(result["directoryScopeAttestation"])
        self.assertEqual("execution-plans/example", result["lineageAnchor"])
        self.assertTrue(result["lineageFamilyId"].startswith("ria-"))

    def test_skill_route_scope_binding_and_route_share_the_decision_profile(self) -> None:
        import bootstrap_integration
        from review_requirement import decide_review_requirement

        policy = json.loads(
            (SKILL_ROOT / "policies" / "semantic-review-trigger-policy.v1.json").read_text(
                encoding="utf-8"
            )
        )
        decision = decide_review_requirement({
            "candidateIdentity": {
                "changedPaths": [".agents/skills/run-phase-bootstrap-review/SKILL.md"],
                "knowledgeArtifacts": [],
            },
            "deterministicEvidence": {"status": "passed"},
            "policy": policy,
        })
        scope = bootstrap_integration.build_minimal_review_scope(
            self.skill_scope_inputs(),
            profile="bootstrap-skill-route",
            lineage_paths=["execution-plans/example/acceptance-run.json"],
        )
        self.assertEqual("bootstrap-skill-route", scope["profile"])
        route = bootstrap_integration.project_bounded_review_route(
            decision, scope, self.lineage_state(scope["lineageFamilyId"], 0), None
        )
        self.assertEqual("bootstrap-skill-route", scope["profile"])
        profile = {
            "controlPlaneRevision": "bootstrap-control-plane.v2",
            "routeVersion": "bootstrap-review-route.v2",
            "reviewProfile": "review-policy://bootstrap-skill-route/v1",
            "policyRevision": "sha256:" + "a" * 64,
            "companionCapabilities": [{
                "capabilityId": "acceptance-inventory-attestation",
                "capabilityVersion": "1.0",
                "producerRole": "acceptance_auditor",
                "schemaPath": "schema.json",
                "schemaHash": "sha256:" + "b" * 64,
            }],
        }
        binding = bootstrap_integration.bind_capabilities(decision, profile)
        self.assertEqual("review-policy://bootstrap-skill-route/v1", binding["reviewProfile"])
        self.assertEqual("full_implementation_conformance", route["routeKind"])
        with self.assertRaisesRegex(bootstrap_integration.BootstrapBindingError, "profile"):
            bootstrap_integration.bind_capabilities(
                decision,
                {**profile, "reviewProfile": "review-policy://bootstrap-implementation-conformance/v1"},
            )

    def test_unclassified_changed_path_blocks_review_requirement(self) -> None:
        from review_requirement import decide_review_requirement

        policy = json.loads(
            (SKILL_ROOT / "policies" / "semantic-review-trigger-policy.v1.json").read_text(
                encoding="utf-8"
            )
        )
        decision = decide_review_requirement({
            "candidateIdentity": {
                "changedPaths": ["PhaseA.Platform/UnclassifiedContract.cs"],
                "knowledgeArtifacts": [],
            },
            "deterministicEvidence": {"status": "passed"},
            "policy": policy,
        })
        self.assertEqual("blocked", decision["decisionStatus"])
        self.assertIsNone(decision["requirement"])

    def test_prepare_bootstrap_projects_the_decision_profile_into_scope(self) -> None:
        import acceptance_cli
        from review_requirement import decide_review_requirement

        policy = json.loads(
            (SKILL_ROOT / "policies" / "semantic-review-trigger-policy.v1.json").read_text(
                encoding="utf-8"
            )
        )
        decision = decide_review_requirement({
            "candidateIdentity": {
                "changedPaths": [".agents/skills/run-phase-bootstrap-review/SKILL.md"],
                "knowledgeArtifacts": [],
            },
            "deterministicEvidence": {"status": "passed"},
            "policy": policy,
        })
        scope = acceptance_cli.build_minimal_review_scope(
            self.skill_scope_inputs(),
            profile="bootstrap-skill-route",
            lineage_paths=["execution-plans/example/prepared.json"],
        )
        request = {
            "repository_root": ".",
            "decision": decision,
            "decision_request": {
                "repository_root": ".",
                "prepared_run_input": "execution-plans/example/prepared.json",
                "deterministic_evidence": {"path": "evidence.json", "sha256": "sha256:" + "a" * 64},
                "maintainer_intent": "default",
            },
            "binding": None,
            "launch_authorization": None,
            "scope_inputs": self.skill_scope_inputs(),
            "lineage_state": self.lineage_state(scope["lineageFamilyId"], 0),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            with mock.patch.object(
                acceptance_cli, "_derive_current_bootstrap_decision", return_value=decision
            ), mock.patch.object(
                acceptance_cli, "load_current_lineage_state", return_value=request["lineage_state"]
            ):
                route = acceptance_cli.prepare_bootstrap_command(
                    str(path), str(root / "route.json")
                )
        self.assertEqual("bootstrap-skill-route", route["reviewScope"]["profile"])

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
        self.assertEqual("ai-native-single-maintainer", initial["maintenanceMode"])
        self.assertEqual("discovery", initial["findingMode"])
        self.assertEqual("not_required", initial["findingModeReentry"])
        round_two = bootstrap_integration.project_bounded_review_route(
            decision,
            scope,
            self.lineage_state(family, 1),
            self.repair_completeness(family, 1),
        )
        self.assertEqual("focused_repair_verification", round_two["routeKind"])
        self.assertEqual("verification_only", round_two["findingMode"])
        self.assertEqual("not_applicable", round_two["findingModeReentry"])
        round_two_with_changed_context = bootstrap_integration.project_bounded_review_route(
            decision,
            scope,
            self.lineage_state(family, 1),
            self.repair_completeness(
                family, 1, authority_changed=True, boundary_changed=True
            ),
        )
        self.assertEqual(
            "full_implementation_conformance", round_two_with_changed_context["routeKind"]
        )
        self.assertEqual("discovery", round_two_with_changed_context["findingMode"])
        self.assertEqual(
            "user_confirmation_required",
            round_two_with_changed_context["findingModeReentry"],
        )
        self.assertEqual(
            "authority_context_graph_changed",
            round_two_with_changed_context["roundEntryReason"],
        )
        deterministic = bootstrap_integration.project_bounded_review_route(
            decision,
            scope,
            self.lineage_state(family, 2),
            self.repair_completeness(family, 2),
        )
        self.assertEqual("deterministic_only", deterministic["routeKind"])
        self.assertIsNone(deterministic["nextFullReviewRound"])

    def test_broh_s5_bounded_reentry_compatibility(self) -> None:
        import bootstrap_integration

        decision = {"requirement": "required"}
        scope = bootstrap_integration.build_minimal_review_scope(self.minimal_scope_inputs())
        family = scope["lineageFamilyId"]
        initial = bootstrap_integration.project_bounded_review_route(
            decision, scope, self.lineage_state(family, 0), None
        )
        focused = bootstrap_integration.project_bounded_review_route(
            decision,
            scope,
            self.lineage_state(family, 1),
            self.repair_completeness(family, 1),
        )
        deterministic = bootstrap_integration.project_bounded_review_route(
            decision,
            scope,
            self.lineage_state(family, 2),
            self.repair_completeness(family, 2),
        )
        self.assertEqual("v6", initial["legacyCompatibilityVersion"])
        self.assertEqual("v6", focused["legacyCompatibilityVersion"])
        self.assertEqual("v6", deterministic["legacyCompatibilityVersion"])

        with self.assertRaisesRegex(
            bootstrap_integration.BootstrapBindingError, "decision status"
        ):
            bootstrap_integration.project_bounded_review_route(
                {"requirement": "required", "decisionStatus": "stale"},
                scope,
                self.lineage_state(family, 0),
                None,
            )

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
            "decision": self.current_decision(),
            "decision_request": {"repository_root": ".", "prepared_run_input": "prepared.json", "deterministic_evidence": {"path": "evidence.json", "sha256": "sha256:" + "a" * 64}, "maintainer_intent": "default"},
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
            ), mock.patch.object(
                acceptance_cli,
                "_derive_current_bootstrap_decision",
                return_value=request["decision"],
            ):
                route = acceptance_cli.prepare_bootstrap_command(str(request_path), str(output_path))
        self.assertEqual("minimal-complete-closure", route["reviewScope"]["strategy"])
        self.assertEqual("run-phase-bootstrap-review", route["nextAction"])

        request.pop("scope_inputs")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            with mock.patch.object(
                acceptance_cli,
                "_derive_current_bootstrap_decision",
                return_value=request["decision"],
            ), self.assertRaisesRegex(acceptance_cli.InputError, "minimal review scope"):
                acceptance_cli.prepare_bootstrap_command(
                    str(request_path), str(root / "route.json")
                )

    def test_prepare_bootstrap_rejects_a_self_hashed_stale_lineage_projection(self) -> None:
        import acceptance_cli

        request = {
            "repository_root": ".",
            "decision": self.current_decision(),
            "decision_request": {"repository_root": ".", "prepared_run_input": "prepared.json", "deterministic_evidence": {"path": "evidence.json", "sha256": "sha256:" + "a" * 64}, "maintainer_intent": "default"},
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
            ), mock.patch.object(
                acceptance_cli, "_derive_current_bootstrap_decision", return_value=request["decision"]
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
            "decision": self.current_decision(),
            "decision_request": {"repository_root": ".", "prepared_run_input": "prepared.json", "deterministic_evidence": {"path": "evidence.json", "sha256": "sha256:" + "a" * 64}, "maintainer_intent": "default"},
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
            ), mock.patch.object(
                acceptance_cli, "_derive_current_bootstrap_decision", return_value=request["decision"]
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
