from __future__ import annotations

import copy
import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PLAN_ROOT = Path(__file__).resolve().parents[2]
TOOLS = PLAN_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from candidate_diff_guards import derive_candidate_snapshot, fold_accepted_attempts, validate_candidate_fixture_suite  # noqa: E402
from candidate_lineage_guards import bytes_hash, load_candidate_lineage, manifest_root_hash, value_hash  # noqa: E402
from contract_guards import contained_file, schema_error  # noqa: E402
from authority_guards import validate_review_reentry  # noqa: E402
from fixture_checks import evaluate_authority_root_self_refresh_fixture, evaluate_lineage_fixture, evaluate_self_refreshed_identity_fixture  # noqa: E402
from rmap_checks import load_machine  # noqa: E402
from evidence_guards import validate_runtime_disposition_sources  # noqa: E402
from protocol_guards import hydrate_protocol_fixture  # noqa: E402


class CandidateDiffGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data, errors = load_machine(PLAN_ROOT)
        if errors:
            raise AssertionError(errors)

    def test_artifact_proof_self_refreshed_identity_is_rejected(self) -> None:
        rules = {item["rule_id"] for item in evaluate_self_refreshed_identity_fixture(PLAN_ROOT)}
        self.assertEqual({"RMAP-ARTIFACT-PROOF-IDENTITY"}, rules)

    def test_artifact_proof_authority_root_cannot_self_refresh_permissions(self) -> None:
        rules = {item["rule_id"] for item in evaluate_authority_root_self_refresh_fixture(PLAN_ROOT)}
        self.assertEqual({"RMAP-ARTIFACT-PROOF-CONSUMER"}, rules)

    def test_artifact_proof_lineage_predecessor_failures_are_isolated(self) -> None:
        for fixture_id in (
            "artifact-proof-lineage-broken-predecessor",
            "artifact-proof-lineage-wrong-predecessor",
            "artifact-proof-lineage-stale-predecessor",
        ):
            with self.subTest(fixture_id=fixture_id):
                rules = {
                    item["rule_id"]
                    for item in evaluate_lineage_fixture(
                        PLAN_ROOT,
                        fixture_id,
                        self.data["artifact_proofs"],
                        self.data["authority_manifest"],
                    )
                }
                self.assertEqual({"RMAP-ARTIFACT-PROOF-LINEAGE"}, rules)

    def test_candidate_diff_mutation_suite_is_exact(self) -> None:
        self.assertEqual([], validate_candidate_fixture_suite(PLAN_ROOT))

    def test_add_then_delete_folds_to_no_candidate_change(self) -> None:
        path = "docs/transient.md"
        bundle = {
            "baseline_file_manifest": {"files": []},
            "attempts": [
                {"adapter_decision": {"attempt_id": "ATTEMPT-001", "decision": "accepted_for_validation"}, "diff_manifest": {"files": [{"path": path, "change_type": "add", "before_sha256": None, "after_sha256": "sha256:" + "1" * 64}]}},
                {"adapter_decision": {"attempt_id": "ATTEMPT-002", "decision": "accepted_for_validation"}, "diff_manifest": {"files": [{"path": path, "change_type": "delete", "before_sha256": "sha256:" + "1" * 64, "after_sha256": None}]}},
            ],
        }
        folded, _, findings = fold_accepted_attempts(bundle)
        self.assertEqual([], findings)
        self.assertEqual([], folded)

    def test_first_add_need_not_be_predicted_by_baseline(self) -> None:
        path = "docs/first-add.md"
        bundle = {
            "baseline_file_manifest": {"files": []},
            "attempts": [{"adapter_decision": {"attempt_id": "ATTEMPT-001", "decision": "accepted_for_validation"}, "diff_manifest": {"files": [{"path": path, "change_type": "add", "before_sha256": None, "after_sha256": "sha256:" + "1" * 64}]}}],
        }
        folded, _, findings = fold_accepted_attempts(bundle)
        self.assertEqual([], findings)
        self.assertEqual("add", folded[0]["change_type"])

    def test_modify_or_delete_without_baseline_identity_fails(self) -> None:
        for change_type, after_hash in (("modify", "sha256:" + "2" * 64), ("delete", None)):
            with self.subTest(change_type=change_type):
                bundle = {
                    "baseline_file_manifest": {"files": []},
                    "attempts": [{"adapter_decision": {"attempt_id": "ATTEMPT-001", "decision": "accepted_for_validation"}, "diff_manifest": {"files": [{"path": "docs/missing.md", "change_type": change_type, "before_sha256": "sha256:" + "1" * 64, "after_sha256": after_hash}]}}],
                }
                _, _, findings = fold_accepted_attempts(bundle)
                self.assertEqual({"RMAP-CANDIDATE-LEDGER-FOLD"}, {item["rule_id"] for item in findings})

    def test_fixture_registry_contains_required_999_counterexamples(self) -> None:
        document = json.loads((PLAN_ROOT / "fixtures" / "candidate-diff-cases.v1.json").read_text(encoding="utf-8"))
        ids = {item["id"] for item in document["cases"]}
        self.assertTrue({
            "candidate-changed-file-omitted", "candidate-extra-changed-file",
            "candidate-deleted-file-missing", "candidate-rename-not-closed",
            "candidate-after-hash-stale", "candidate-test-patch-empty-with-test-change",
            "candidate-test-patch-not-reproducible", "candidate-result-ref-stale",
        }.issubset(ids))

    def test_real_git_for_windows_candidate_snapshot_covers_modify_add_delete_and_binary_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "execution-plans" / "plan"
            plan.mkdir(parents=True)
            (root / "docs").mkdir()
            (root / "Tests.Godot").mkdir()
            (root / "docs" / "delete.md").write_text("delete\n", encoding="utf-8")
            (root / "docs" / "modify.md").write_text("before\n", encoding="utf-8")
            self._git(root, "init")
            self._git(root, "config", "user.email", "rmap@example.invalid")
            self._git(root, "config", "user.name", "RMAP Test")
            self._git(root, "add", ".")
            self._git(root, "commit", "-m", "baseline")
            (root / "docs" / "delete.md").unlink()
            (root / "docs" / "modify.md").write_text("after\n", encoding="utf-8")
            (root / "Tests.Godot" / "binary.bin").write_bytes(bytes(range(256)))
            contract = {"slices": [{"slice_id": "RMAP-S6", "allowed_changes": {"production": [], "tests": ["Tests.Godot/**"], "documentation": ["docs/**"]}, "execution_read_set": [], "dependency_closure": [], "forbidden_changes": []}]}
            entries, patch, exclusions = derive_candidate_snapshot(plan, root, contract)
            self.assertEqual(set(), exclusions)
            by_path = {item.get("candidate_path") or item.get("baseline_path"): item for item in entries}
            self.assertEqual("delete", by_path["docs/delete.md"]["change_type"])
            self.assertEqual("modify", by_path["docs/modify.md"]["change_type"])
            self.assertEqual("add", by_path["Tests.Godot/binary.bin"]["change_type"])
            self.assertIn(b"GIT binary patch", patch)

    def test_contained_file_rejects_junction_escape_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            junction = root / "junction"
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(Path(outside))], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                self.skipTest("junction creation is unavailable for this Windows token")
            try:
                (Path(outside) / "evidence.json").write_text("{}", encoding="utf-8")
                self.assertIsNone(contained_file(root, "junction/evidence.json"))
            finally:
                junction.rmdir()

    def test_successor_policy_and_independent_closure_make_reentry_reachable(self) -> None:
        repository_root = PLAN_ROOT.parents[1]
        run_dir = repository_root / "logs" / "vdd-plan-validation" / f"reentry-{__import__('uuid').uuid4().hex}"
        run_dir.mkdir(parents=True)
        try:
            blocker = json.loads((PLAN_ROOT / "schemas" / "review-blocking-state.v1.json").read_text(encoding="utf-8"))
            reentry = json.loads((PLAN_ROOT / "schemas" / "review-policy-reentry.v1.json").read_text(encoding="utf-8"))
            policy_revision = "sha256:" + "9" * 64; authority_revision = "successor-authority"; input_hash = "sha256:" + "8" * 64
            exclusions = ["plan-ready", "slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"]
            authority_path = run_dir / "successor-authority.json"
            root_path = repository_root / ".agents" / "skills" / "run-phase-bootstrap-review" / "references" / "authority-roots.v1.json"
            root_ref = {"path": root_path.relative_to(repository_root).as_posix(), "sha256": "sha256:" + hashlib.sha256(root_path.read_bytes()).hexdigest()}
            authority = {"schemaVersion": "bootstrap-successor-policy-authority.v1", "authorityId": "successor-authority-001", "rootId": "successor-policy-root.v1", "authorityRootRef": root_ref, "signerId": "repository-operator", "policyRevision": policy_revision, "authorizedActors": [{"actorId": "operator-001", "role": "successor-policy-authorizer", "consumers": ["repository-maintenance-tdd-adapter-plan-reentry"], "scopes": ["plan-reentry"]}], "status": "active", "issuedAt": "2026-07-17T00:00:00Z", "expiresAt": "2099-01-01T00:00:00Z", "predecessorAuthorityRef": root_ref, "authorizes": [], "doesNotAuthorize": exclusions}
            authority_path.write_text(json.dumps(authority), encoding="utf-8")
            authority_ref = {"path": authority_path.relative_to(repository_root).as_posix(), "sha256": "sha256:" + hashlib.sha256(authority_path.read_bytes()).hexdigest()}
            event_path = run_dir / "authorization-event.json"
            event = {"schemaVersion": "bootstrap-successor-policy-authorization.v1", "eventId": "successor-event-001", "decisionId": "successor-decision", "actorId": "operator-001", "authoritySourceRef": authority_ref, "supersededReviewId": blocker["review_id"], "supersededChangeId": blocker["change_id"], "successorChangeId": "successor-change", "policyRevision": policy_revision, "authorityRevision": authority_revision, "consumer": "repository-maintenance-tdd-adapter-plan-reentry", "scope": "plan-reentry", "status": "active", "issuedAt": "2026-07-17T00:01:00Z", "expiresAt": "2098-01-01T00:00:00Z", "predecessorEventRef": None, "revocationEventRef": None, "authorizes": [], "doesNotAuthorize": exclusions}
            event_path.write_text(json.dumps(event), encoding="utf-8")
            decision_path = run_dir / "policy-decision.json"
            decision = {"schemaVersion": "bootstrap-successor-policy-decision.v1", "decisionId": "successor-decision", "supersededReviewId": blocker["review_id"], "supersededChangeId": blocker["change_id"], "successorChangeId": "successor-change", "policyRevision": policy_revision, "authorityRevision": authority_revision, "authorizationEventRef": {"path": event_path.relative_to(repository_root).as_posix(), "sha256": "sha256:" + hashlib.sha256(event_path.read_bytes()).hexdigest()}, "authorizationEventId": "successor-event-001", "consumer": "repository-maintenance-tdd-adapter-plan-reentry", "authorizes": [], "doesNotAuthorize": exclusions, "decidedAt": "2026-07-17T00:02:00Z"}
            decision_path.write_text(json.dumps(decision), encoding="utf-8")
            envelope_path = run_dir / "finalized-run-validation.json"
            envelope = {"schemaVersion": "bootstrap-finalized-run-validation.v1", "validationStatus": "passed", "reviewId": "successor-review", "changeId": "successor-change", "fullReviewRound": 1, "profileName": "bootstrap-implementation-conformance", "reviewProfile": "review-policy://implementation-conformance/v1", "routeVersion": "route-v1", "controlPlaneRevision": "control-v2", "policyRevision": policy_revision, "profileHash": "sha256:" + "7" * 64, "authorityRevision": authority_revision, "inputHash": input_hash, "authorityContextHash": "sha256:" + "6" * 64, "artifactHashes": {key: "sha256:" + "5" * 64 for key in ("reviewInput", "preflightResult", "gateState", "candidates", "rejections", "finalResult", "dispositions", "metrics", "verifierOutput")}, "finalStatus": "clean", "findingClosure": {key: 0 for key in ("candidateCount", "visibleFindingCount", "confirmedCount", "advisoryCount", "unverifiedCount", "refutedCount", "p2FixedCount", "p2DeferredCount", "p2RefutedCount")}, "validatorRevision": "bootstrap-finalized-run-validator.v2", "validatorHash": "sha256:" + "4" * 64, "authorizes": [], "doesNotAuthorize": ["plan-acceptance", "implementation-acceptance", "protected-handoff", "release", "commit", "done"], "generatedAt": "2026-07-17T00:00:00Z"}
            envelope["artifactHashes"]["p2Dispositions"] = None
            envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
            (run_dir / "review-input.json").write_text("{}", encoding="utf-8")
            relative = lambda path: path.relative_to(repository_root).as_posix()
            digest = lambda path: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            reentry.update({"state": "reentry_authorized", "authorizes": ["manual-pause-reentry"], "does_not_authorize": ["plan-ready", "slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"]})
            reentry["successor_policy"] = {"change_id": "successor-change", "policy_revision": policy_revision, "authority_revision": authority_revision, "input_hash": input_hash, "decision_path": relative(decision_path), "decision_sha256": digest(decision_path)}
            reentry["semantic_closure"] = {"review_id": "successor-review", "bootstrap_run_path": relative(run_dir), "envelope_path": relative(envelope_path), "envelope_sha256": digest(envelope_path), "status": "clean"}
            fake = mock.Mock()
            class FakeBootstrapError(Exception):
                pass
            fake.BootstrapError = FakeBootstrapError
            fake.schema_validation_errors.side_effect = lambda name, document: [] if (
                name == "bootstrap-successor-policy-decision.v1.schema.json" and document.get("schemaVersion") == "bootstrap-successor-policy-decision.v1"
            ) or (
                name == "bootstrap-finalized-run-validation.v1.schema.json" and document.get("schemaVersion") == "bootstrap-finalized-run-validation.v1" and "artifactHashes" in document
            ) else ["schema invalid"]
            fake.read_json.return_value = {}
            def validate_event(_root: Path, candidate: dict) -> dict:
                reference = candidate["authorizationEventRef"]
                if reference["sha256"] != digest(event_path):
                    raise ValueError("stale successor authorization event")
                return event
            fake.validate_successor_policy_authorization.side_effect = validate_event
            fake.validate_finalized_run_evidence.return_value = envelope
            with mock.patch("authority_guards._load_bootstrap_runtime", return_value=fake), mock.patch(
                "authority_guards.stable_environment_evidence", return_value=({}, {})
            ):
                self.assertEqual([], validate_review_reentry(PLAN_ROOT, blocker, reentry))

                fake.validate_successor_policy_authorization.side_effect = FakeBootstrapError("untrusted root")
                self.assertEqual(
                    {"RMAP-REVIEW-REENTRY"},
                    {item["rule_id"] for item in validate_review_reentry(PLAN_ROOT, blocker, reentry)},
                )
                fake.validate_successor_policy_authorization.side_effect = validate_event

                decision_path.write_text("{}", encoding="utf-8")
                reentry["successor_policy"]["decision_sha256"] = digest(decision_path)
                self.assertEqual({"RMAP-REVIEW-REENTRY"}, {item["rule_id"] for item in validate_review_reentry(PLAN_ROOT, blocker, reentry)})

                decision_path.write_text(json.dumps(decision), encoding="utf-8")
                reentry["successor_policy"]["decision_sha256"] = digest(decision_path)
                minimal_envelope = {"schemaVersion": "bootstrap-finalized-run-validation.v1", "validationStatus": "passed", "reviewId": "successor-review", "changeId": "successor-change", "finalStatus": "clean"}
                envelope_path.write_text(json.dumps(minimal_envelope), encoding="utf-8")
                reentry["semantic_closure"]["envelope_sha256"] = digest(envelope_path)
                self.assertEqual({"RMAP-REVIEW-REENTRY"}, {item["rule_id"] for item in validate_review_reentry(PLAN_ROOT, blocker, reentry)})

                envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
                reentry["semantic_closure"]["envelope_sha256"] = digest(envelope_path)
                stale_decision = copy.deepcopy(decision)
                stale_decision["authorizationEventRef"]["sha256"] = "sha256:" + "0" * 64
                decision_path.write_text(json.dumps(stale_decision), encoding="utf-8")
                reentry["successor_policy"]["decision_sha256"] = digest(decision_path)
                self.assertEqual({"RMAP-REVIEW-REENTRY"}, {item["rule_id"] for item in validate_review_reentry(PLAN_ROOT, blocker, reentry)})

                decision_path.write_text(json.dumps(decision), encoding="utf-8")
                reentry["successor_policy"]["decision_sha256"] = digest(decision_path)
                mismatched = copy.deepcopy(envelope)
                mismatched["changeId"] = "other-successor-change"
                envelope_path.write_text(json.dumps(mismatched), encoding="utf-8")
                reentry["semantic_closure"]["envelope_sha256"] = digest(envelope_path)
                fake.validate_finalized_run_evidence.return_value = mismatched
                self.assertEqual({"RMAP-REVIEW-REENTRY"}, {item["rule_id"] for item in validate_review_reentry(PLAN_ROOT, blocker, reentry)})
        finally:
            shutil.rmtree(run_dir)

    def test_live_lineage_recomputes_slice_effect_projections(self) -> None:
        for mutation in ("fabricated-effect", "omitted-attempt", "self-asserted-final-event", "effect-not-derived-from-diff"):
            with self.subTest(mutation=mutation):
                root, lineage, current = self._live_lineage_fixture()
                try:
                    last_ref = lineage["slice_runs"][-1]
                    effect_path = PLAN_ROOT.parents[1] / last_ref["run_path"]
                    effect = json.loads(effect_path.read_text(encoding="utf-8"))
                    if mutation == "fabricated-effect":
                        effect["effects"][0]["after_sha256"] = "sha256:" + "e" * 64
                    elif mutation == "omitted-attempt":
                        effect["accepted_attempt_ids"] = effect["accepted_attempt_ids"][:-1]
                    elif mutation == "self-asserted-final-event":
                        effect["final_event_hash"] = "sha256:" + "e" * 64
                        last_ref["final_event_hash"] = effect["final_event_hash"]
                    else:
                        effect["effects"] = []
                    effect["root_hash"] = manifest_root_hash(effect)
                    effect_path.write_text(json.dumps(effect, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                    last_ref["run_artifact_sha256"] = bytes_hash(effect_path.read_bytes())
                    lineage["root_hash"] = manifest_root_hash(lineage)
                    _, _, findings = load_candidate_lineage(PLAN_ROOT, PLAN_ROOT.parents[1], lineage, "RMAP-S6-RUN-001", current)
                    self.assertIn("RMAP-CANDIDATE-LEDGER-FOLD", {item["rule_id"] for item in findings})
                finally:
                    shutil.rmtree(root)

    def test_cross_slice_lineage_fields_are_not_recovery_predecessors(self) -> None:
        root, lineage, current = self._live_lineage_fixture()
        try:
            ref = lineage["slice_runs"][1]
            ref["predecessor_run_id"] = ref.pop("previous_slice_run_id")
            lineage["root_hash"] = manifest_root_hash(lineage)
            _, _, findings = load_candidate_lineage(PLAN_ROOT, PLAN_ROOT.parents[1], lineage, "RMAP-S6-RUN-001", current)
            self.assertEqual({"RMAP-CANDIDATE-LINEAGE"}, {item["rule_id"] for item in findings})
        finally:
            shutil.rmtree(root)

    def test_runtime_p2_source_accepts_current_normal_deferral_and_rejects_high_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review_dir = Path(tmp)
            envelope = {"reviewId": "review-p2", "inputHash": "sha256:" + "1" * 64}
            findings = {"P2-TEST": {"findingId": "P2-TEST", "proposedSeverity": "P2", "status": "advisory"}}
            dispositions = [{"findingId": "P2-TEST", "status": "p2_deferred"}]
            ref = {"path": "logs/evidence.json", "sha256": "sha256:" + "2" * 64}
            p2 = {"schemaVersion": "bootstrap-p2-dispositions.v1", "reviewId": "review-p2", "inputHash": envelope["inputHash"], "candidateHash": "sha256:" + "3" * 64, "policyRevision": "sha256:" + "4" * 64, "authorityRevision": "authority-p2", "findingIds": ["P2-TEST"], "dispositions": [{"findingId": "P2-TEST", "status": "deferred", "risk": "normal", "reason": "bounded", "owner": "owner", "expiry": "2099-01-01T00:00:00Z", "closureCommandId": "test-p2", "closureCommandRegistryRef": ref, "ownerAuthorityRef": ref, "nonImpactEvidenceRef": ref, "recheckEvidenceRef": ref, "recheckTrigger": "expiry"}]}
            p2_path = review_dir / "p2-dispositions.json"; p2_path.write_text(json.dumps(p2), encoding="utf-8")
            metrics = {"p2DispositionHash": "sha256:" + hashlib.sha256(p2_path.read_bytes()).hexdigest()}
            (review_dir / "review-metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
            self.assertEqual([], validate_runtime_disposition_sources(review_dir, envelope, findings, dispositions, "candidate"))
            p2["dispositions"][0]["risk"] = "high"; p2_path.write_text(json.dumps(p2), encoding="utf-8")
            metrics["p2DispositionHash"] = "sha256:" + hashlib.sha256(p2_path.read_bytes()).hexdigest(); (review_dir / "review-metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
            rules = {item["rule_id"] for item in validate_runtime_disposition_sources(review_dir, envelope, findings, dispositions, "candidate")}
            self.assertEqual({"RMAP-REVIEW-P2-DISPOSITION"}, rules)

    def _live_lineage_fixture(self) -> tuple[Path, dict[str, object], dict[str, str]]:
        repository_root = PLAN_ROOT.parents[1]
        root = repository_root / "logs" / "vdd-plan-validation" / f"lineage-{__import__('uuid').uuid4().hex}"
        root.mkdir(parents=True)
        fixtures = json.loads((PLAN_ROOT / "fixtures" / "capsule-attempt-cases.v1.json").read_text(encoding="utf-8"))
        baseline_files: list[dict[str, str]] = []
        slice_runs: list[dict[str, object]] = []
        current_state: dict[str, str | None] = {}
        previous_slice_id = previous_run_id = previous_effect_hash = None
        try:
            for index in range(7):
                slice_id = f"RMAP-S{index}"
                run_id = f"{slice_id}-RUN-001"
                run_dir = root / slice_id / run_id
                run_dir.mkdir(parents=True)
                target = (run_dir / "candidate-source.txt").relative_to(repository_root).as_posix()
                base = copy.deepcopy(fixtures["valid_bundle"])
                base["slice_capsule"].update({"slice_id": slice_id, "run_id": run_id})
                base["slice_capsule"]["boundaries"]["allowed_write_set"] = [root.relative_to(repository_root).as_posix() + "/**"]
                base["context_manifest"].update({"slice_id": slice_id, "run_id": run_id})
                base["attempts"][0]["diff_manifest"]["files"][0]["path"] = target
                bundle, store, file_versions = hydrate_protocol_fixture(
                    base,
                    external_artifacts={
                        "implementation-contract.v1.json": (PLAN_ROOT / "implementation-contract.v1.json").read_bytes(),
                        "schemas/authority-manifest.v1.json": (PLAN_ROOT / "schemas" / "authority-manifest.v1.json").read_bytes(),
                    },
                    initial_bytes=None,
                )
                for (path_type, relative), payload in store.items():
                    if path_type == "run_path":
                        path = run_dir / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(payload)
                (repository_root / target).write_bytes(file_versions[("ATTEMPT-003", "after", target)] or b"")
                effects, fold_hash, fold_findings = fold_accepted_attempts(bundle, current_state)
                self.assertEqual([], fold_findings)
                events_path = run_dir / "run-events.jsonl"
                ledger_path = run_dir / "attempt-ledger-manifest.v1.json"
                effect = {
                    "schema_version": "jimuyun.candidate-slice-effect.v1",
                    "plan_id": "repository-maintenance-tdd-adapter",
                    "slice_id": slice_id,
                    "run_id": run_id,
                    "baseline_files": baseline_files,
                    "effects": effects,
                    "accepted_attempt_ids": ["ATTEMPT-001", "ATTEMPT-002", "ATTEMPT-003"],
                    "attempt_ledger_manifest_hash": bytes_hash(ledger_path.read_bytes()),
                    "run_events_hash": bytes_hash(events_path.read_bytes()),
                    "final_event_hash": value_hash(bundle["events"][-1]),
                    "root_hash": "",
                }
                effect["root_hash"] = manifest_root_hash(effect)
                effect_path = run_dir / "candidate-slice-effect.v1.json"
                effect_path.write_text(json.dumps(effect, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                effect_hash = bytes_hash(effect_path.read_bytes())
                slice_runs.append({
                    "slice_id": slice_id,
                    "run_id": run_id,
                    "previous_slice_id": previous_slice_id,
                    "previous_slice_run_id": previous_run_id,
                    "previous_slice_effect_hash": previous_effect_hash,
                    "run_path": effect_path.relative_to(repository_root).as_posix(),
                    "run_artifact_sha256": effect_hash,
                    "accepted_attempt_fold_hash": fold_hash,
                    "final_event_hash": effect["final_event_hash"],
                })
                for entry in effects:
                    current_state[str(entry.get("candidate_path") or entry.get("baseline_path"))] = entry.get("after_sha256")
                previous_slice_id, previous_run_id, previous_effect_hash = slice_id, run_id, effect_hash
            cumulative = [
                {"change_type": "add", "baseline_path": None, "candidate_path": path, "before_sha256": None, "after_sha256": after}
                for path, after in sorted(current_state.items(), key=lambda item: item[0].casefold()) if after is not None
            ]
            current = {"head": "a" * 40, "index_tree": "b" * 40}
            lineage: dict[str, object] = {
                "schema_version": "jimuyun.candidate-lineage-manifest.v1",
                "plan_id": "repository-maintenance-tdd-adapter",
                "candidate_run_id": "RMAP-S6-RUN-001",
                "baseline_identity": current,
                "slice_runs": slice_runs,
                "baseline_bridges": [],
                "replay_baseline_ref": None,
                "cumulative_fold_hash": value_hash(cumulative),
                "root_hash": "",
            }
            lineage["root_hash"] = manifest_root_hash(lineage)
            _, _, findings = load_candidate_lineage(PLAN_ROOT, repository_root, lineage, "RMAP-S6-RUN-001", current)
            self.assertEqual([], findings)
            return root, lineage, current
        except Exception:
            shutil.rmtree(root)
            raise

    @staticmethod
    def _git(root: Path, *args: str) -> None:
        result = subprocess.run(["git", "-c", "core.autocrlf=false", *args], cwd=root, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise AssertionError(result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
