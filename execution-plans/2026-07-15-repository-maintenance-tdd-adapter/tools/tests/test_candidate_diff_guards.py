from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[2]
TOOLS = PLAN_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from candidate_diff_guards import derive_candidate_snapshot, fold_accepted_attempts, validate_candidate_fixture_suite  # noqa: E402
from contract_guards import contained_file  # noqa: E402
from authority_guards import validate_review_reentry  # noqa: E402
from evidence_guards import validate_runtime_disposition_sources  # noqa: E402


class CandidateDiffGuardTests(unittest.TestCase):
    def test_candidate_diff_mutation_suite_is_exact(self) -> None:
        self.assertEqual([], validate_candidate_fixture_suite(PLAN_ROOT))

    def test_add_then_delete_folds_to_no_candidate_change(self) -> None:
        path = "docs/transient.md"
        bundle = {
            "baseline_file_manifest": {"files": [{"path": path, "sha256": None}]},
            "attempts": [
                {"adapter_decision": {"attempt_id": "ATTEMPT-001", "decision": "accepted_for_validation"}, "diff_manifest": {"files": [{"path": path, "before_sha256": None, "after_sha256": "sha256:" + "1" * 64}]}},
                {"adapter_decision": {"attempt_id": "ATTEMPT-002", "decision": "accepted_for_validation"}, "diff_manifest": {"files": [{"path": path, "before_sha256": "sha256:" + "1" * 64, "after_sha256": None}]}},
            ],
        }
        folded, _, findings = fold_accepted_attempts(bundle)
        self.assertEqual([], findings)
        self.assertEqual([], folded)

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
            entries, patch = derive_candidate_snapshot(plan, root, contract)
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
            decision_path = run_dir / "policy-decision.json"; decision_path.write_text("{}", encoding="utf-8")
            policy_revision = "sha256:" + "9" * 64; authority_revision = "successor-authority"
            envelope_path = run_dir / "finalized-run-validation.json"
            envelope = {"reviewId": "successor-review", "policyRevision": policy_revision, "authorityRevision": authority_revision, "validationStatus": "passed", "finalStatus": "clean"}
            envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
            relative = lambda path: path.relative_to(repository_root).as_posix()
            digest = lambda path: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            reentry.update({"state": "reentry_authorized", "authorizes": ["plan-ready"], "does_not_authorize": ["slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"]})
            reentry["successor_policy"] = {"change_id": "successor-change", "policy_revision": policy_revision, "authority_revision": authority_revision, "decision_path": relative(decision_path), "decision_sha256": digest(decision_path)}
            reentry["semantic_closure"] = {"review_id": "successor-review", "run_path": relative(envelope_path), "envelope_sha256": digest(envelope_path), "independent": True, "status": "clean"}
            self.assertEqual([], validate_review_reentry(PLAN_ROOT, blocker, reentry))
        finally:
            shutil.rmtree(run_dir)

    def test_runtime_p2_source_accepts_current_normal_deferral_and_rejects_high_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review_dir = Path(tmp)
            envelope = {"reviewId": "review-p2", "inputHash": "sha256:" + "1" * 64}
            findings = {"P2-TEST": {"findingId": "P2-TEST", "proposedSeverity": "P2", "status": "advisory"}}
            dispositions = [{"findingId": "P2-TEST", "status": "p2_deferred"}]
            p2 = {"schemaVersion": "bootstrap-p2-dispositions.v1", "reviewId": "review-p2", "inputHash": envelope["inputHash"], "findingIds": ["P2-TEST"], "dispositions": [{"findingId": "P2-TEST", "status": "deferred", "risk": "normal", "reason": "bounded", "owner": "owner", "expiry": "2099-01-01T00:00:00Z", "closureTest": "test-p2"}]}
            p2_path = review_dir / "p2-dispositions.json"; p2_path.write_text(json.dumps(p2), encoding="utf-8")
            metrics = {"p2DispositionHash": "sha256:" + hashlib.sha256(p2_path.read_bytes()).hexdigest()}
            (review_dir / "review-metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
            self.assertEqual([], validate_runtime_disposition_sources(review_dir, envelope, findings, dispositions, "candidate"))
            p2["dispositions"][0]["risk"] = "high"; p2_path.write_text(json.dumps(p2), encoding="utf-8")
            metrics["p2DispositionHash"] = "sha256:" + hashlib.sha256(p2_path.read_bytes()).hexdigest(); (review_dir / "review-metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
            rules = {item["rule_id"] for item in validate_runtime_disposition_sources(review_dir, envelope, findings, dispositions, "candidate")}
            self.assertEqual({"RMAP-REVIEW-P2-DISPOSITION"}, rules)

    @staticmethod
    def _git(root: Path, *args: str) -> None:
        result = subprocess.run(["git", "-c", "core.autocrlf=false", *args], cwd=root, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise AssertionError(result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
