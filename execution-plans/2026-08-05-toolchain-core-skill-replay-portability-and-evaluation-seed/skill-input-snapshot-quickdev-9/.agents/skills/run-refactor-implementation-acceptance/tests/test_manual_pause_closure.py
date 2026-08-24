from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class ManualPauseClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.target = "execution-plans/example"
        from bootstrap_integration import build_minimal_review_scope

        scope_inputs = {
            "implementation_plan": [f"{self.target}/00-index.md"],
            "changed_production_code": ["src/fix.py"],
            "affected_consumers": ["src/fix.py"],
            "tests_and_acceptance": ["tests/test_fix.py", "logs/fix.json"],
            "runtime_evidence": ["logs/fix.json"],
            "repository_rules": ["AGENTS.md"],
            "referenced_standards": ["docs/standards/bootstrap-review-control-plane.md"],
        }
        self.scope = build_minimal_review_scope(scope_inputs)
        self.family = self.scope["lineageFamilyId"]
        (self.root / self.target).mkdir(parents=True)
        self.run_relative = "logs/ci/review-r3"
        self.run_dir = self.root / self.run_relative
        self.run_dir.mkdir(parents=True)
        self.findings = ["BSR-A", "BSR-B", "BSR-C"]
        candidates = {"findings": [{"findingId": item} for item in self.findings]}
        verifier = {
            "decisions": [
                {"findingId": item, "decision": "confirmed"}
                for item in self.findings
            ]
        }
        artifacts = {
            "reviewInput": "review-input.json",
            "preflightResult": "preflight-result.json",
            "gateState": "review-gate-state.json",
            "candidates": "review-candidates.json",
            "rejections": "review-rejections.json",
            "finalResult": "review-gate-result.json",
            "dispositions": "review-dispositions.json",
            "metrics": "review-metrics.json",
            "verifierOutput": "verifier-output.json",
        }
        for key, filename in artifacts.items():
            value = candidates if key == "candidates" else verifier if key == "verifierOutput" else {"value": key}
            self._write(self.run_dir / filename, value)
        envelope = {
            "schemaVersion": "bootstrap-finalized-run-validation.v3",
            "validationStatus": "passed",
            "reviewId": "review-r3",
            "changeId": "legacy-change",
            "profileName": "bootstrap-implementation-conformance",
            "lineageFamilyId": self.family,
            "fullReviewRound": 3,
            "inputHash": "sha256:" + "1" * 64,
            "artifactHashes": {
                **{key: self._hash(self.run_dir / filename) for key, filename in artifacts.items()},
                "p2Dispositions": None,
            },
            "finalStatus": "blocked",
            "findingClosure": {"confirmedCount": 3},
            "validatorHash": "sha256:" + "7" * 64,
            "generatedAt": "2026-08-01T00:00:00Z",
            "authorizes": [],
        }
        self.envelope = envelope
        self.envelope_relative = f"{self.run_relative}/finalized-run-validation.v3.json"
        self._write(self.root / self.envelope_relative, envelope)
        self.lineage = {
            "semanticRoundsConsumed": 3,
            "state": "manual_pause",
            "nextFullReviewRound": None,
            "lineageStateHash": "sha256:" + "2" * 64,
            "runs": [
                {"runDirectory": "logs/ci/review-r1", "reviewId": "review-r1", "changeId": "legacy-change", "fullReviewRound": 1, "inputHash": "sha256:" + "3" * 64},
                {"runDirectory": "logs/ci/review-r2", "reviewId": "review-r2", "changeId": "legacy-change", "fullReviewRound": 2, "inputHash": "sha256:" + "4" * 64},
                {"runDirectory": self.run_relative, "reviewId": "review-r3", "changeId": "legacy-change", "fullReviewRound": 3, "inputHash": "sha256:" + "1" * 64},
            ],
        }
        self.route_relative = f"{self.target}/manual-pause-route.json"
        for relative in (
            ".agents/skills/run-phase-bootstrap-review/SKILL.md",
            ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-hard-limit-focused-recovery.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-hard-limit-focused-repair-validation-envelope.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-hard-limit-protocol-repair-authority.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-focused-repair-verifier-output.v1.schema.json",
            ".agents/skills/run-refactor-implementation-acceptance/SKILL.md",
            ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py",
            ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_core.py",
            ".agents/skills/run-refactor-implementation-acceptance/scripts/bootstrap_integration.py",
            ".agents/skills/run-refactor-implementation-acceptance/scripts/execution_control.py",
            ".agents/skills/run-refactor-implementation-acceptance/scripts/manual_pause_closure.py",
            ".agents/skills/run-refactor-implementation-acceptance/scripts/repair_completeness.py",
            ".agents/skills/run-refactor-implementation-acceptance/scripts/review_cycle_policy.py",
            ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-manual-pause-closure-request.v1.schema.json",
            ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-manual-pause-closure-challenge.v1.schema.json",
            ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-manual-pause-closure.v1.schema.json",
            ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-repair-completeness.v1.schema.json",
            "docs/adr/ADR-0054-refactor-acceptance-manual-pause-closure.md",
            "docs/standards/bootstrap-review-control-plane.md",
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative.endswith("acceptance-manual-pause-closure.v1.schema.json"):
                path.write_bytes((SKILL_ROOT / "schemas" / path.name).read_bytes())
            else:
                path.write_text(relative + "\n", encoding="utf-8", newline="\n")
        self.repair = {
            "acceptanceTarget": self.target,
            "lineageFamilyId": self.family,
            "semanticRoundsConsumed": 3,
            "predecessorRun": self.run_relative,
            "changedPaths": ["src/fix.py"],
            "targetedTests": [{"path": "tests/test_fix.py", "sha256": "sha256:" + "5" * 64}],
            "validationRefs": [{"path": "logs/fix.json", "sha256": "sha256:" + "6" * 64}],
            "compositionChecks": [{
                "checkId": "fixture-check",
                "bindings": [
                    {"role": "producer", "path": "src/fix.py", "sha256": "sha256:" + "7" * 64},
                    {"role": "consumer", "path": "src/fix.py", "sha256": "sha256:" + "7" * 64},
                ],
                "targetedTests": ["tests/test_fix.py"],
                "receipt": {"path": "logs/fix.json", "sha256": "sha256:" + "6" * 64},
            }],
        }
        self.protocol_run_relative = "logs/ci/protocol-review"
        protocol_run = self.root / self.protocol_run_relative
        protocol_artifacts = [
            {
                "artifact": relative,
                "sha256": self._hash(self.root / relative),
            }
            for relative in sorted(
                relative
                for relative in (
                    ".agents/skills/run-phase-bootstrap-review/SKILL.md",
                    ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py",
                    ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-hard-limit-focused-recovery.v1.schema.json",
                    ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-hard-limit-focused-repair-validation-envelope.v1.schema.json",
                    ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-hard-limit-protocol-repair-authority.v1.schema.json",
                    ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-focused-repair-verifier-output.v1.schema.json",
                    ".agents/skills/run-refactor-implementation-acceptance/SKILL.md",
                    ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py",
                    ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_core.py",
                    ".agents/skills/run-refactor-implementation-acceptance/scripts/bootstrap_integration.py",
                    ".agents/skills/run-refactor-implementation-acceptance/scripts/execution_control.py",
                    ".agents/skills/run-refactor-implementation-acceptance/scripts/manual_pause_closure.py",
                    ".agents/skills/run-refactor-implementation-acceptance/scripts/repair_completeness.py",
                    ".agents/skills/run-refactor-implementation-acceptance/scripts/review_cycle_policy.py",
                    ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-manual-pause-closure-request.v1.schema.json",
                    ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-manual-pause-closure-challenge.v1.schema.json",
                    ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-manual-pause-closure.v1.schema.json",
                    ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-repair-completeness.v1.schema.json",
                    "docs/adr/ADR-0054-refactor-acceptance-manual-pause-closure.md",
                    "docs/standards/bootstrap-review-control-plane.md",
                )
            )
        ]
        self._write(protocol_run / "review-input.json", {"artifacts": protocol_artifacts})
        self.protocol_envelope = {
            "schemaVersion": "bootstrap-finalized-run-validation.v3",
            "validationStatus": "passed",
            "profileName": "bootstrap-skill-route",
            "finalStatus": "clean",
            "artifactHashes": {"reviewInput": self._hash(protocol_run / "review-input.json")},
            "validatorHash": "sha256:" + "9" * 64,
            "generatedAt": "2026-08-01T00:00:00Z",
            "authorizes": [],
        }
        self.protocol_envelope_relative = (
            f"{self.protocol_run_relative}/finalized-run-validation.v3.json"
        )
        self._write(self.root / self.protocol_envelope_relative, self.protocol_envelope)
        self.protocol_review = {
            "runDirectory": self.protocol_run_relative,
            "envelopePath": self.protocol_envelope_relative,
            "envelopeSha256": self._hash(self.root / self.protocol_envelope_relative),
        }
        self.route_request_relative = f"{self.target}/manual-pause-route.request.json"
        self.route_request = {
            "decision": {"requirement": "required"},
            "binding": {},
            "launch_authorization=<redacted>,
            "repository_root": str(self.root),
            "scope_inputs": scope_inputs,
            "lineage_state": self.lineage,
            "repair_completeness": self.repair,
            "repair_completeness_request": {"request": "fixture"},
        }
        self._write(self.root / self.route_request_relative, self.route_request)
        self.route_state = {
            "schemaVersion": "bootstrap-execution-state.v1",
            "state": "prepared",
            "actionStates": {},
            "authorizes": [],
        }
        self.bounded_route = {
            "routeKind": "manual_pause",
            "lineageAnchor": self.target,
            "lineageFamilyId": self.family,
            "semanticRoundsConsumed": 3,
            "nextFullReviewRound": None,
            "roundEntryReason": None,
            "lineageStateHash": self.lineage["lineageStateHash"],
            "repairCompletenessHash": "sha256:" + "8" * 64,
        }
        self._write(self.root / self.route_relative, {
            "schemaVersion": "implementation-acceptance-bootstrap-route.v1",
            "bootstrapExecutionState": self.route_state,
            "reviewScope": self.scope,
            **self.bounded_route,
            "repairCompletenessRequest": {"request": "fixture"},
            "repairCompletenessRequestHash": "sha256:" + hashlib.sha256(
                json.dumps(
                    {"request": "fixture"}, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest(),
            "nextAction": "manual-pause",
            "authorizes": [],
        })
        self.request_relative = f"{self.target}/manual-pause-closure.request.json"
        self.request = {
            "schemaVersion": "acceptance-manual-pause-closure-request.v1",
            "repositoryRoot": str(self.root),
            "acceptanceTarget": self.target,
            "lineageFamilyId": self.family,
            "manualPauseRoute": {"path": self.route_relative, "sha256": self._hash(self.root / self.route_relative)},
            "manualPauseRouteRequest": {"path": self.route_request_relative, "sha256": self._hash(self.root / self.route_request_relative)},
            "finalizedRun": {
                "runDirectory": self.run_relative,
                "envelopePath": self.envelope_relative,
                "envelopeSha256": self._hash(self.root / self.envelope_relative),
            },
            "repairCompletenessRequest": {"request": "fixture"},
            "repairCompleteness": self.repair,
            "findingRepairs": [
                {
                    "findingId": item,
                    "changedPaths": ["src/fix.py"],
                    "targetedTests": ["tests/test_fix.py"],
                    "validationRefs": ["logs/fix.json"],
                }
                for item in self.findings
            ],
            "protocolAuthorities": [
                {"path": relative, "sha256": self._hash(self.root / relative)}
                for relative in sorted((
                    ".agents/skills/run-refactor-implementation-acceptance/SKILL.md",
                    "docs/adr/ADR-0054-refactor-acceptance-manual-pause-closure.md",
                    "docs/standards/bootstrap-review-control-plane.md",
                ))
            ],
            "protocolReview": self.protocol_review,
            "authorizes": [],
        }
        self._write(self.root / self.request_relative, self.request)
        import manual_pause_closure

        self.validate_protocol_review = manual_pause_closure._validate_protocol_review

        for patcher in (
            mock.patch.object(manual_pause_closure, "audit_repair_completeness", return_value=self.repair),
            mock.patch.object(manual_pause_closure, "project_bootstrap_execution_state", return_value=self.route_state),
            mock.patch.object(manual_pause_closure, "project_bounded_review_route", return_value=self.bounded_route),
            mock.patch.object(
                manual_pause_closure,
                "_validate_protocol_review",
                return_value=self.protocol_review,
            ),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _write(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8", newline="\n")

    @staticmethod
    def _hash(path: Path) -> str:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    def _prepare(self, request: dict | None = None) -> dict:
        import manual_pause_closure

        with (
            mock.patch.object(manual_pause_closure, "load_current_lineage_state", return_value=self.lineage),
            mock.patch.object(manual_pause_closure, "audit_repair_completeness", return_value=self.repair),
            mock.patch.object(manual_pause_closure, "project_bootstrap_execution_state", return_value=self.route_state),
            mock.patch.object(manual_pause_closure, "project_bounded_review_route", return_value=self.bounded_route),
            mock.patch.object(
                manual_pause_closure,
                "replay_finalized_bootstrap_run",
                return_value=self.envelope,
            ),
        ):
            return manual_pause_closure.prepare_manual_pause_closure(
                request or self.request, self.request_relative
            )

    def test_prepare_and_finalize_exact_repaired_finding_set(self) -> None:
        import manual_pause_closure

        challenge = self._prepare()
        challenge_relative = f"{self.target}/challenge.json"
        self._write(self.root / challenge_relative, challenge)
        acknowledgement = {
            "schemaVersion": "acceptance-manual-pause-maintainer-ack.v1",
            "decision": "accept-repaired-target",
            "closureBindingHash": challenge["closureBindingHash"],
            "acknowledgedFindingIds": self.findings,
            "authorityRole": "maintainer",
            "rationale": "All confirmed findings have current deterministic repair evidence.",
            "recordedAt": "2026-08-01T00:00:00Z",
            "authorizes": ["manual-pause-closure"],
        }
        with (
            mock.patch.object(manual_pause_closure, "load_current_lineage_state", return_value=self.lineage),
            mock.patch.object(manual_pause_closure, "audit_repair_completeness", return_value=self.repair),
            mock.patch.object(manual_pause_closure, "project_bootstrap_execution_state", return_value=self.route_state),
            mock.patch.object(manual_pause_closure, "project_bounded_review_route", return_value=self.bounded_route),
            mock.patch.object(
                manual_pause_closure,
                "replay_finalized_bootstrap_run",
                return_value=self.envelope,
            ),
        ):
            result = manual_pause_closure.finalize_manual_pause_closure(
                self.root, challenge_relative, acknowledgement
            )
        self.assertEqual("passed", result["status"])
        self.assertEqual(["acceptance-passed"], result["authorizes"])

    def test_prepare_accepts_blocked_upstream_plan_lineage(self) -> None:
        self.envelope["profileName"] = "bootstrap-upstream-plan"
        self._write(self.root / self.envelope_relative, self.envelope)
        self.request["finalizedRun"]["envelopeSha256"] = self._hash(
            self.root / self.envelope_relative
        )
        self._write(self.root / self.request_relative, self.request)

        challenge = self._prepare()

        self.assertEqual(self.findings, challenge["confirmedFindingIds"])

    def test_protocol_review_binds_current_protocol_bytes(self) -> None:
        with mock.patch(
            "manual_pause_closure.replay_finalized_bootstrap_run",
            return_value=self.protocol_envelope,
        ):
            result = self.validate_protocol_review(
                self.root, self.protocol_review, self.request["protocolAuthorities"]
            )
        self.assertEqual(self.protocol_review, result)

    def test_protocol_review_accepts_only_exact_hard_limit_composite_chain(self) -> None:
        focused_run_relative = "logs/ci/protocol-focused-recovery"
        focused_run = self.root / focused_run_relative
        protocol_input = json.loads(
            (self.root / self.protocol_run_relative / "review-input.json").read_text(
                encoding="utf-8"
            )
        )
        self._write(focused_run / "review-input.json", protocol_input)
        blocked_envelope_relative = "logs/ci/protocol-blocked-r3/finalized-run-validation.v3.json"
        blocked_envelope = {
            "schemaVersion": "bootstrap-finalized-run-validation.v3",
            "validationStatus": "passed",
            "profileName": "bootstrap-skill-route",
            "fullReviewRound": 3,
            "finalStatus": "blocked",
            "findingClosure": {"unverifiedCount": 0},
        }
        self._write(self.root / blocked_envelope_relative, blocked_envelope)
        finding_ids = ["BSR-PROTOCOL-ONE"]
        focused_envelope_relative = f"{focused_run_relative}/focused-repair-validation-envelope.json"
        focused_envelope = {
            "schemaVersion": "bootstrap-hard-limit-focused-repair-validation-envelope.v1",
            "status": "passed",
            "nextAction": "deterministic-closure",
            "lineageFamilyId": "protocol-family",
            "inputHash": "sha256:" + "1" * 64,
            "hardLimitRecoveryHash": "sha256:" + "2" * 64,
            "deterministicRepairClosureHash": "sha256:" + "3" * 64,
            "findingIds": finding_ids,
            "outputHash": "sha256:" + "4" * 64,
            "gateHash": "sha256:" + "5" * 64,
            "authorizes": [],
            "generatedAt": "2026-08-03T00:00:00Z",
        }
        self._write(self.root / focused_envelope_relative, focused_envelope)
        authority_relative = f"{focused_run_relative}/hard-limit-protocol-repair-authority.json"
        authority = {
            "schemaVersion": "bootstrap-hard-limit-protocol-repair-authority.v1",
            "status": "passed",
            "maintenanceMode": "ai-native-single-maintainer",
            "lineageFamilyId": "protocol-family",
            "fullReviewRound": 3,
            "predecessorRun": "logs/ci/protocol-blocked-r3",
            "predecessorInputHash": "sha256:" + "6" * 64,
            "blockedPredecessorEnvelope": {
                "path": blocked_envelope_relative,
                "sha256": self._hash(self.root / blocked_envelope_relative),
                "finalStatus": "blocked",
            },
            "focusedRun": focused_run_relative,
            "focusedInputHash": focused_envelope["inputHash"],
            "hardLimitRecoveryHash": focused_envelope["hardLimitRecoveryHash"],
            "deterministicRepairClosureHash": focused_envelope["deterministicRepairClosureHash"],
            "findingIds": finding_ids,
            "focusedValidationEnvelope": {
                "path": focused_envelope_relative,
                "sha256": self._hash(self.root / focused_envelope_relative),
            },
            "verifierOutputHash": focused_envelope["outputHash"],
            "gateHash": focused_envelope["gateHash"],
            "generatedAt": "2026-08-03T00:00:01Z",
            "authorizes": ["manual-pause-protocol-review"],
            "doesNotAuthorize": [
                "acceptance-passed", "round-4", "finding-discovery", "commit", "release"
            ],
        }
        self._write(self.root / authority_relative, authority)
        binding = {
            "runDirectory": focused_run_relative,
            "envelopePath": focused_envelope_relative,
            "envelopeSha256": self._hash(self.root / focused_envelope_relative),
            "hardLimitAuthorityPath": authority_relative,
            "hardLimitAuthoritySha256": self._hash(self.root / authority_relative),
        }

        def replay(_root, run):
            self.assertEqual(focused_run_relative, run)
            return focused_envelope

        with mock.patch(
            "manual_pause_closure.replay_finalized_bootstrap_run", side_effect=replay
        ):
            self.assertEqual(
                binding,
                self.validate_protocol_review(
                    self.root, binding, self.request["protocolAuthorities"]
                ),
            )
        authority["authorizes"] = ["acceptance-passed"]
        self._write(self.root / authority_relative, authority)
        binding["hardLimitAuthoritySha256"] = self._hash(self.root / authority_relative)
        with (
            mock.patch(
                "manual_pause_closure.replay_finalized_bootstrap_run", side_effect=replay
            ),
            self.assertRaisesRegex(Exception, "authority is invalid"),
        ):
            self.validate_protocol_review(
                self.root, binding, self.request["protocolAuthorities"]
            )

    def test_protocol_review_rejects_stale_protocol_artifact(self) -> None:
        path = (
            self.root
            / ".agents/skills/run-refactor-implementation-acceptance/scripts/manual_pause_closure.py"
        )
        path.write_text("changed\n", encoding="utf-8", newline="\n")
        with (
            mock.patch(
                "manual_pause_closure.replay_finalized_bootstrap_run",
                return_value=self.protocol_envelope,
            ),
            self.assertRaisesRegex(Exception, "current protocol bytes"),
        ):
            self.validate_protocol_review(
                self.root, self.protocol_review, self.request["protocolAuthorities"]
            )

    def test_protocol_review_rejects_stale_public_cli_consumer(self) -> None:
        path = (
            self.root
            / ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py"
        )
        path.write_text("changed\n", encoding="utf-8", newline="\n")
        with (
            mock.patch(
                "manual_pause_closure.replay_finalized_bootstrap_run",
                return_value=self.protocol_envelope,
            ),
            self.assertRaisesRegex(Exception, "current protocol bytes"),
        ):
            self.validate_protocol_review(
                self.root, self.protocol_review, self.request["protocolAuthorities"]
            )

    def test_finding_repairs_are_order_independent(self) -> None:
        import manual_pause_closure

        repair = copy.deepcopy(self.repair)
        repair["changedPaths"] = ["src/a.py", "src/b.py"]
        repair["targetedTests"] = [
            {"path": "tests/test_a.py", "sha256": "sha256:" + "a" * 64},
            {"path": "tests/test_b.py", "sha256": "sha256:" + "b" * 64},
        ]
        repair["validationRefs"] = [
            {"path": "logs/a.json", "sha256": "sha256:" + "a" * 64},
            {"path": "logs/b.json", "sha256": "sha256:" + "b" * 64},
        ]
        repair["compositionChecks"] = [
            {"bindings": [{"role": "producer", "path": "src/a.py", "sha256": "sha256:" + "a" * 64}, {"role": "consumer", "path": "src/a_consumer.py", "sha256": "sha256:" + "c" * 64}], "targetedTests": ["tests/test_a.py"], "receipt": {"path": "logs/a.json", "sha256": "sha256:" + "a" * 64}},
            {"bindings": [{"role": "producer", "path": "src/b.py", "sha256": "sha256:" + "b" * 64}, {"role": "consumer", "path": "src/b_consumer.py", "sha256": "sha256:" + "d" * 64}], "targetedTests": ["tests/test_b.py"], "receipt": {"path": "logs/b.json", "sha256": "sha256:" + "b" * 64}},
        ]
        mappings = [
            {"findingId": "BSR-B", "changedPaths": ["src/b.py"], "targetedTests": ["tests/test_b.py"], "validationRefs": ["logs/b.json"]},
            {"findingId": "BSR-A", "changedPaths": ["src/a.py"], "targetedTests": ["tests/test_a.py"], "validationRefs": ["logs/a.json"]},
        ]

        result = manual_pause_closure._validate_repairs(
            mappings, ["BSR-A", "BSR-B"], repair
        )

        self.assertEqual(["BSR-A", "BSR-B"], [item["findingId"] for item in result])

    def test_cli_normalizes_absolute_request_inside_repository(self) -> None:
        import acceptance_cli

        request_path = self.root / self.target / "manual-pause-cli-request.json"
        output_path = self.root / self.target / "manual-pause-cli-output.json"
        request = {"repositoryRoot": str(self.root)}
        self._write(request_path, request)
        expected = {"status": "fixture"}
        with mock.patch.object(
            acceptance_cli, "prepare_manual_pause_closure", return_value=expected
        ) as prepare:
            result = acceptance_cli.prepare_manual_pause_closure_command(
                str(request_path), str(output_path)
            )

        self.assertEqual(expected, result)
        prepare.assert_called_once_with(
            request, f"{self.target}/manual-pause-cli-request.json"
        )

    def test_finding_repair_rejects_cross_associated_receipt(self) -> None:
        import manual_pause_closure

        repair = copy.deepcopy(self.repair)
        repair["changedPaths"] = ["src/a.py", "src/b.py"]
        repair["compositionChecks"] = [
            {
                "bindings": [
                    {"role": "producer", "path": "src/a.py", "sha256": "sha256:" + "a" * 64},
                    {"role": "consumer", "path": "src/a.py", "sha256": "sha256:" + "a" * 64},
                ],
                "targetedTests": ["tests/test_fix.py"],
                "receipt": {"path": "logs/a.json", "sha256": "sha256:" + "a" * 64},
            },
            {
                "bindings": [
                    {"role": "producer", "path": "src/b.py", "sha256": "sha256:" + "b" * 64},
                    {"role": "consumer", "path": "src/b.py", "sha256": "sha256:" + "b" * 64},
                ],
                "targetedTests": ["tests/test_fix.py"],
                "receipt": {"path": "logs/b.json", "sha256": "sha256:" + "b" * 64},
            },
        ]
        repair["validationRefs"] = [
            {"path": "logs/a.json", "sha256": "sha256:" + "a" * 64},
            {"path": "logs/b.json", "sha256": "sha256:" + "b" * 64},
        ]
        mappings = [{
            "findingId": "BSR-B",
            "changedPaths": ["src/b.py"],
            "targetedTests": ["tests/test_fix.py"],
            "validationRefs": ["logs/a.json"],
        }]
        with self.assertRaisesRegex(Exception, "does not cover its changed paths"):
            manual_pause_closure._validate_repairs(mappings, ["BSR-B"], repair)

    def test_prepare_accepts_adopted_legacy_envelope_family(self) -> None:
        self.envelope["lineageFamilyId"] = "legacy-change"
        self._write(self.root / self.envelope_relative, self.envelope)
        self.request["finalizedRun"]["envelopeSha256"] = self._hash(
            self.root / self.envelope_relative
        )
        self._write(self.root / self.request_relative, self.request)

        challenge = self._prepare()

        self.assertEqual(self.family, challenge["lineageFamilyId"])

    def test_prepare_rejects_unrelated_bootstrap_profile(self) -> None:
        self.envelope["profileName"] = "bootstrap-skill-route"
        self._write(self.root / self.envelope_relative, self.envelope)
        self.request["finalizedRun"]["envelopeSha256"] = self._hash(
            self.root / self.envelope_relative
        )
        self._write(self.root / self.request_relative, self.request)

        with self.assertRaisesRegex(Exception, "finalized envelope is invalid"):
            self._prepare()

    def test_prepare_rejects_incomplete_finding_repairs(self) -> None:
        request = copy.deepcopy(self.request)
        request["findingRepairs"] = request["findingRepairs"][:-1]
        self._write(self.root / self.request_relative, request)
        with self.assertRaisesRegex(Exception, "exact confirmed set"):
            self._prepare(request)

    def test_prepare_rejects_finalized_envelope_that_fails_canonical_replay(self) -> None:
        import manual_pause_closure

        replayed = copy.deepcopy(self.envelope)
        replayed["validatorRevision"] = "different-validator"
        with (
            mock.patch.object(
                manual_pause_closure,
                "load_current_lineage_state",
                return_value=self.lineage,
            ),
            mock.patch.object(
                manual_pause_closure,
                "replay_finalized_bootstrap_run",
                return_value=replayed,
            ),
            self.assertRaisesRegex(Exception, "canonical replay"),
        ):
            manual_pause_closure.prepare_manual_pause_closure(
                self.request, self.request_relative
            )

    def test_prepare_accepts_validator_rotation_after_canonical_replay(self) -> None:
        import manual_pause_closure

        replayed = copy.deepcopy(self.envelope)
        replayed["validatorHash"] = "sha256:" + "8" * 64
        replayed["generatedAt"] = "2026-08-01T01:00:00Z"
        with (
            mock.patch.object(
                manual_pause_closure,
                "load_current_lineage_state",
                return_value=self.lineage,
            ),
            mock.patch.object(
                manual_pause_closure,
                "audit_repair_completeness",
                return_value=self.repair,
            ),
            mock.patch.object(
                manual_pause_closure,
                "replay_finalized_bootstrap_run",
                return_value=replayed,
            ),
        ):
            challenge = manual_pause_closure.prepare_manual_pause_closure(
                self.request, self.request_relative
            )
        self.assertEqual(
            "sha256:" + hashlib.sha256(
                json.dumps(
                    {key: value for key, value in replayed.items() if key != "generatedAt"},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            challenge["finalizedEnvelopeCoreHash"],
        )

    def test_prepare_rejects_unverified_blocking_finding(self) -> None:
        verifier_path = self.run_dir / "verifier-output.json"
        verifier = json.loads(verifier_path.read_text(encoding="utf-8"))
        verifier["decisions"][1] = {
            "findingId": self.findings[1],
            "decision": "unverified",
            "unverifiedClass": "security",
        }
        self._write(verifier_path, verifier)
        envelope = copy.deepcopy(self.envelope)
        envelope["artifactHashes"]["verifierOutput"] = self._hash(verifier_path)
        envelope["findingClosure"]["confirmedCount"] = 2
        self._write(self.root / self.envelope_relative, envelope)
        request = copy.deepcopy(self.request)
        request["finalizedRun"]["envelopeSha256"] = self._hash(
            self.root / self.envelope_relative
        )
        self._write(self.root / self.request_relative, request)
        self.envelope = envelope
        with self.assertRaisesRegex(Exception, "confirmed finding set"):
            self._prepare(request)

    def test_prepare_rejects_non_manual_pause_route(self) -> None:
        request = copy.deepcopy(self.request)
        route = json.loads((self.root / self.route_relative).read_text(encoding="utf-8"))
        route["routeKind"] = "deterministic_only"
        self._write(self.root / self.route_relative, route)
        request["manualPauseRoute"]["sha256"] = self._hash(self.root / self.route_relative)
        self._write(self.root / self.request_relative, request)
        with self.assertRaisesRegex(Exception, "route is invalid"):
            self._prepare(request)

    def test_prepare_rejects_target_relabelled_onto_another_lineage(self) -> None:
        request = copy.deepcopy(self.request)
        request["acceptanceTarget"] = "execution-plans/other"
        (self.root / request["acceptanceTarget"]).mkdir(parents=True)
        repair = copy.deepcopy(self.repair)
        repair["acceptanceTarget"] = request["acceptanceTarget"]
        request["repairCompleteness"] = repair
        route_request = copy.deepcopy(self.route_request)
        route_request["repair_completeness"] = repair
        self._write(self.root / self.route_request_relative, route_request)
        request["manualPauseRouteRequest"]["sha256"] = self._hash(
            self.root / self.route_request_relative
        )
        self._write(self.root / self.request_relative, request)
        import manual_pause_closure

        with (
            mock.patch.object(manual_pause_closure, "load_current_lineage_state", return_value=self.lineage),
            mock.patch.object(manual_pause_closure, "audit_repair_completeness", return_value=repair),
            mock.patch.object(manual_pause_closure, "replay_finalized_bootstrap_run", return_value=self.envelope),
            self.assertRaisesRegex(Exception, "target lineage is invalid"),
        ):
            manual_pause_closure.prepare_manual_pause_closure(
                request, self.request_relative
            )

    def test_prepare_accepts_path_equivalent_repository_root(self) -> None:
        request = copy.deepcopy(self.request)
        route_request = copy.deepcopy(self.route_request)
        route_request["repository_root"] = str(self.root) + "/"
        self._write(self.root / self.route_request_relative, route_request)
        request["manualPauseRouteRequest"]["sha256"] = self._hash(
            self.root / self.route_request_relative
        )
        self._write(self.root / self.request_relative, request)
        challenge = self._prepare(request)
        self.assertEqual(self.target, challenge["acceptanceTarget"])

    def test_prepare_resolves_relative_repository_root_independently_of_cwd(self) -> None:
        request = copy.deepcopy(self.request)
        route_request = copy.deepcopy(self.route_request)
        route_request["repository_root"] = "."
        self._write(self.root / self.route_request_relative, route_request)
        request["manualPauseRouteRequest"]["sha256"] = self._hash(
            self.root / self.route_request_relative
        )
        self._write(self.root / self.request_relative, request)
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as other_cwd:
            try:
                os.chdir(other_cwd)
                challenge = self._prepare(request)
            finally:
                os.chdir(original_cwd)
        self.assertEqual(self.target, challenge["acceptanceTarget"])

    def test_finalize_hashes_the_validated_challenge_snapshot(self) -> None:
        import manual_pause_closure

        challenge = self._prepare()
        challenge_relative = f"{self.target}/challenge-snapshot.json"
        challenge_path = self.root / challenge_relative
        self._write(challenge_path, challenge)
        original_hash = self._hash(challenge_path)
        acknowledgement = {
            "schemaVersion": "acceptance-manual-pause-maintainer-ack.v1",
            "decision": "accept-repaired-target",
            "closureBindingHash": challenge["closureBindingHash"],
            "acknowledgedFindingIds": self.findings,
            "authorityRole": "maintainer",
            "rationale": "Fixture",
            "recordedAt": "2026-08-01T00:00:00Z",
            "authorizes": ["manual-pause-closure"],
        }

        def replace_after_replay(*_args: object) -> dict:
            self._write(challenge_path, {"replacement": True})
            return challenge

        with (
            mock.patch.object(manual_pause_closure, "load_current_lineage_state", return_value=self.lineage),
            mock.patch.object(manual_pause_closure, "replay_finalized_bootstrap_run", return_value=self.envelope),
            mock.patch.object(manual_pause_closure, "prepare_manual_pause_closure", side_effect=replace_after_replay),
        ):
            result = manual_pause_closure.finalize_manual_pause_closure(
                self.root, challenge_relative, acknowledgement
            )
        self.assertEqual(original_hash, result["challengeHash"])

    def test_finalize_rejects_acknowledgement_binding_drift(self) -> None:
        import manual_pause_closure

        challenge = self._prepare()
        challenge_relative = f"{self.target}/challenge.json"
        self._write(self.root / challenge_relative, challenge)
        acknowledgement = {
            "schemaVersion": "acceptance-manual-pause-maintainer-ack.v1",
            "decision": "accept-repaired-target",
            "closureBindingHash": "sha256:" + "f" * 64,
            "acknowledgedFindingIds": self.findings,
            "authorityRole": "maintainer",
            "rationale": "Fixture",
            "recordedAt": "2026-08-01T00:00:00Z",
            "authorizes": ["manual-pause-closure"],
        }
        with (
            mock.patch.object(manual_pause_closure, "load_current_lineage_state", return_value=self.lineage),
            mock.patch.object(manual_pause_closure, "audit_repair_completeness", return_value=self.repair),
            mock.patch.object(
                manual_pause_closure,
                "replay_finalized_bootstrap_run",
                return_value=self.envelope,
            ),
            self.assertRaisesRegex(Exception, "acknowledgement is invalid"),
        ):
            manual_pause_closure.finalize_manual_pause_closure(
                self.root, challenge_relative, acknowledgement
            )

    def test_finalize_rejects_reviewed_closure_schema_drift(self) -> None:
        import manual_pause_closure

        challenge = self._prepare()
        challenge_relative = f"{self.target}/challenge-schema-drift.json"
        self._write(self.root / challenge_relative, challenge)
        acknowledgement = {
            "schemaVersion": "acceptance-manual-pause-maintainer-ack.v1",
            "decision": "accept-repaired-target",
            "closureBindingHash": challenge["closureBindingHash"],
            "acknowledgedFindingIds": self.findings,
            "authorityRole": "maintainer",
            "rationale": "Fixture",
            "recordedAt": "2026-08-01T00:00:00Z",
            "authorizes": ["manual-pause-closure"],
        }
        schema_path = self.root / manual_pause_closure._CLOSURE_SCHEMA_PATH
        schema_path.write_bytes(schema_path.read_bytes() + b"\n")
        with (
            mock.patch.object(manual_pause_closure, "load_current_lineage_state", return_value=self.lineage),
            mock.patch.object(
                manual_pause_closure,
                "replay_finalized_bootstrap_run",
                return_value=self.envelope,
            ),
            self.assertRaisesRegex(Exception, "violates its reviewed schema"),
        ):
            manual_pause_closure.finalize_manual_pause_closure(
                self.root, challenge_relative, acknowledgement
            )


if __name__ == "__main__":
    unittest.main()
