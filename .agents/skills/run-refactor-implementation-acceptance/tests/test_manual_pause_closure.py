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
                {"runDirectory": "logs/ci/review-r1", "reviewId": "review-r1", "inputHash": "sha256:" + "3" * 64},
                {"runDirectory": "logs/ci/review-r2", "reviewId": "review-r2", "inputHash": "sha256:" + "4" * 64},
                {"runDirectory": self.run_relative, "reviewId": "review-r3", "inputHash": "sha256:" + "1" * 64},
            ],
        }
        self.route_relative = f"{self.target}/manual-pause-route.json"
        for relative in (
            ".agents/skills/run-refactor-implementation-acceptance/SKILL.md",
            "docs/adr/ADR-0054-refactor-acceptance-manual-pause-closure.md",
            "docs/standards/bootstrap-review-control-plane.md",
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(relative + "\n", encoding="utf-8", newline="\n")
        self.repair = {
            "acceptanceTarget": self.target,
            "lineageFamilyId": self.family,
            "semanticRoundsConsumed": 3,
            "predecessorRun": self.run_relative,
            "changedPaths": ["src/fix.py"],
            "targetedTests": [{"path": "tests/test_fix.py", "sha256": "sha256:" + "5" * 64}],
            "validationRefs": [{"path": "logs/fix.json", "sha256": "sha256:" + "6" * 64}],
        }
        self.route_request_relative = f"{self.target}/manual-pause-route.request.json"
        self.route_request = {
            "decision": {"requirement": "required"},
            "binding": {},
            "launch_authorization": {},
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
            "authorizes": [],
        }
        self._write(self.root / self.request_relative, self.request)
        import manual_pause_closure

        for patcher in (
            mock.patch.object(manual_pause_closure, "audit_repair_completeness", return_value=self.repair),
            mock.patch.object(manual_pause_closure, "project_bootstrap_execution_state", return_value=self.route_state),
            mock.patch.object(manual_pause_closure, "project_bounded_review_route", return_value=self.bounded_route),
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


if __name__ == "__main__":
    unittest.main()
