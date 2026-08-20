from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from acceptance_core import verify_manifest_bytes  # noqa: E402
from compact_vdd_projection import InputError, project, project_or_quick_dev_recovery  # noqa: E402


class CompactVddProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        (self.root / "scripts/sc").mkdir(parents=True)
        (self.root / "scripts/sc/tool.py").write_text("old\n", encoding="utf-8")
        (self.root / "scripts/sc/deleted.py").write_text("delete\n", encoding="utf-8")
        (self.root / "unrelated.txt").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "baseline"], cwd=self.root, check=True)
        self.head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()
        (self.root / "scripts/sc/tool.py").write_text("new\n", encoding="utf-8")
        (self.root / "scripts/sc/deleted.py").unlink()
        (self.root / "scripts/sc/added.py").write_text("added\n", encoding="utf-8")
        (self.root / "unrelated.txt").write_text("dirty but excluded\n", encoding="utf-8")
        self.target = self.root / "execution-plans/target"
        (self.target / "tools").mkdir(parents=True)
        (self.target / "00-index.md").write_text("# Target\n", encoding="utf-8")
        (self.target / "plan-state.v1.json").write_text(json.dumps({"state":"implementation-authorized","authorizes":["implementation-authorized"]}), encoding="utf-8")
        (self.target / "tools/terminal_runner.py").write_text("print('pass')\n", encoding="utf-8")
        (self.target / "implementation-contract.v1.json").write_text(json.dumps({
            "plan_id": "target",
            "terminal": {"command_id": "validate", "runner": "tools/terminal_runner.py", "predicate": "implementation-complete"},
        }), encoding="utf-8")
        (self.target / "command-registry.v1.json").write_text(json.dumps({"commands": []}), encoding="utf-8")
        (self.target / "knowledge-context.refactor-acceptance.v1.json").write_text("{}\n", encoding="utf-8")
        policy = self.root / "toolchain-code-review.v1.json"
        policy.write_text("{}\n", encoding="utf-8")
        self.receipt_path = self.target / "repair/implementation-complete.json"
        self.receipt_path.parent.mkdir(parents=True)
        contract_hash = "sha256:" + hashlib.sha256((self.target / "implementation-contract.v1.json").read_bytes()).hexdigest()
        registry_hash = "sha256:" + hashlib.sha256((self.target / "command-registry.v1.json").read_bytes()).hexdigest()
        self.receipt_path.write_text(json.dumps({
            "schema_version": "quick-dev-implementation-complete.v1",
            "predicate": "implementation-complete",
            "status": "pass",
            "plan_id": "target",
            "contract_hash": contract_hash,
            "command_registry_hash": registry_hash,
            "terminal_command_id": "validate",
            "validated_command_ids": ["validate"],
            "authorizes": ["implementation-complete"],
        }), encoding="utf-8")
        self.request_path = self.root / "request.json"
        self.request = {
            "schemaVersion":"compact-vdd-acceptance-projection-request.v1",
            "targetPlan":"execution-plans/target",
            "runId":"acceptance-test",
            "changeId":"compact-target",
            "baselineRevision":self.head,
            "changedPaths":["scripts/sc/added.py","scripts/sc/deleted.py","scripts/sc/tool.py"],
            "affectedConsumerRefs":["scripts/sc/tool.py"],
            "targetPlanPaths":["00-index.md"],
            "knowledgeContextPath":"knowledge-context.refactor-acceptance.v1.json",
            "codeReviewDomain":"toolchain",
            "codeReviewPolicyPath":"toolchain-code-review.v1.json",
            "implementationReceiptPath":"execution-plans/target/repair/implementation-complete.json",
            "implementationReceiptHash":"sha256:" + hashlib.sha256(self.receipt_path.read_bytes()).hexdigest(),
            "commands":[{"id":"validate","executable":"py","argv":["-3","tools/validate_implementation.py"],"cwd":".","timeout_seconds":30,"shell":False}],
            "actions":[{"actionId":"validate","dependsOn":[],"order":1,"commandId":"validate","activation":True}],
            "authorizes":[],
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_request(self) -> None:
        self.request_path.write_text(json.dumps(self.request), encoding="utf-8")

    def test_projection_freezes_only_explicit_paths_and_reproduces_manifest_custody(self) -> None:
        self.write_request()
        result = project(self.root, self.request_path)
        self.assertEqual("ready", result["status"])
        bundle = json.loads((self.root / result["bundle"]).read_text(encoding="utf-8"))
        self.assertEqual([], bundle["authorizes"])
        self.assertEqual("repair/implementation-complete.json", bundle["implementationReceipt"]["path"])
        snapshot = self.target / bundle["candidateSnapshotPath"]
        observed = sorted(path.relative_to(snapshot).as_posix() for path in snapshot.rglob("*") if path.is_file())
        self.assertEqual(["scripts/sc/added.py", "scripts/sc/tool.py"], observed)
        self.assertNotIn("unrelated.txt", observed)
        request = json.loads((self.root / result["runRequest"]).read_text(encoding="utf-8"))
        baseline = json.loads((self.target / request["baseline_content_manifest_path"]).read_text(encoding="utf-8"))
        candidate = json.loads((self.target / request["candidate_content_manifest_path"]).read_text(encoding="utf-8"))
        custody = verify_manifest_bytes(self.target, request, baseline, candidate)
        self.assertTrue(custody["snapshotManifestHash"].startswith("sha256:"))
        kinds = {item["candidate_path"] or item["baseline_path"]: item["change_type"] for item in candidate["files"]}
        self.assertEqual("deleted", kinds["scripts/sc/deleted.py"])

    def test_projection_rejects_unchanged_or_ambiguous_paths(self) -> None:
        self.request["changedPaths"] = ["unrelated.txt"]
        baseline_bytes = subprocess.check_output(
            ["git", "show", f"{self.head}:unrelated.txt"], cwd=self.root
        )
        (self.root / "unrelated.txt").write_bytes(baseline_bytes)
        self.write_request()
        with self.assertRaisesRegex(InputError, "unchanged bytes"):
            project(self.root, self.request_path)
        self.request["changedPaths"] = ["scripts/sc/tool.py", "scripts/sc/tool.py"]
        self.write_request()
        with self.assertRaisesRegex(InputError, "sorted and unique"):
            project(self.root, self.request_path)

    def test_projection_uses_quick_dev_handoff_without_claiming_plan_state_and_is_append_only(self) -> None:
        self.write_request()
        project(self.root, self.request_path)
        with self.assertRaisesRegex(InputError, "already exists"):
            project(self.root, self.request_path)

    def test_projection_accepts_a_clean_explicit_commit_candidate(self) -> None:
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "candidate"], cwd=self.root, check=True)
        candidate = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()
        self.request["candidateRevision"] = candidate
        self.write_request()

        result = project(self.root, self.request_path)
        request = json.loads((self.root / result["runRequest"]).read_text(encoding="utf-8"))

        self.assertEqual("commit", request["candidate_mode"])
        self.assertEqual(candidate, request["candidate_revision"])
        self.assertNotIn("candidate_frozen_snapshot_path", request)

    def test_projection_rejects_handoff_that_no_longer_matches_the_terminal_contract(self) -> None:
        receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        receipt["terminal_command_id"] = "other"
        self.receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        self.request["implementationReceiptHash"] = "sha256:" + hashlib.sha256(self.receipt_path.read_bytes()).hexdigest()
        self.write_request()
        with self.assertRaisesRegex(InputError, "does not match"):
            project(self.root, self.request_path)

    def test_projection_rejects_legacy_or_unbound_implementation_receipts(self) -> None:
        receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        receipt["schema_version"] = "toolchain-workflow-repair.terminal-result.v2"
        receipt.pop("command_registry_hash")
        self.receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        self.request["implementationReceiptHash"] = "sha256:" + hashlib.sha256(self.receipt_path.read_bytes()).hexdigest()
        self.write_request()
        with self.assertRaisesRegex(InputError, "does not match"):
            project(self.root, self.request_path)

    def test_projection_can_emit_non_authorizing_quick_dev_recovery_route(self) -> None:
        receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        receipt["schema_version"] = "toolchain-workflow-repair.terminal-result.v2"
        self.receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        self.request["implementationReceiptHash"] = "sha256:" + hashlib.sha256(self.receipt_path.read_bytes()).hexdigest()
        self.write_request()
        result = project_or_quick_dev_recovery(self.root, self.request_path)
        self.assertEqual("quick-dev-terminal-recovery-required.v1", result["schemaVersion"])
        self.assertEqual("quick-dev-tdd-adapter", result["recoveryOwner"])
        self.assertFalse(result["bootstrapInvoked"])
        self.assertEqual([], result["authorizes"])

    def test_projection_uses_explicit_baseline_overlay_without_absorbing_prior_dirty_bytes(self) -> None:
        overlay = self.target / "repair/baseline/tool.py"
        overlay.parent.mkdir(parents=True)
        overlay.write_bytes(b"prior dirty baseline\n")
        self.request["changedPaths"] = ["scripts/sc/tool.py"]
        self.request["baselineOverlaySources"] = {
            "scripts/sc/tool.py": "execution-plans/target/repair/baseline/tool.py"
        }
        self.write_request()
        result = project(self.root, self.request_path)
        request = json.loads((self.root / result["runRequest"]).read_text(encoding="utf-8"))
        self.assertNotEqual(self.head, request["baseline_revision"])
        baseline = json.loads((self.target / request["baseline_content_manifest_path"]).read_text(encoding="utf-8"))
        self.assertEqual(
            "sha256:" + __import__("hashlib").sha256(b"prior dirty baseline\n").hexdigest(),
            baseline["files"][0]["sha256"],
        )


if __name__ == "__main__":
    unittest.main()
