from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class TaskChecklistTests(unittest.TestCase):
    def test_checked_item_requires_current_implementation_test_and_evidence(self) -> None:
        import task_checklist

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "plan.md"
            source.write_text("# Phase One\n- [x] Build the route\n", encoding="utf-8")
            sha = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
            item_id = task_checklist._item_id("plan.md", "phase-one", "Build the route")
            result = task_checklist.audit_task_checklist(repository_root=root, acceptance_run_id="run", candidate_manifest_hash="sha256:" + "a" * 64, sources=[{"path": "plan.md", "sha256": sha}], evidence_by_item={item_id: {"matrixCheckIds": ["C1"], "implementationRefs": ["code"], "testRefs": ["test"], "evidenceIds": ["evidence"]}})
        self.assertEqual("passed", result["status"])
        self.assertEqual("verified", result["items"][0]["status"])

    def test_checkbox_alone_is_not_completion_and_source_hash_is_frozen(self) -> None:
        import task_checklist
        from acceptance_core import InputError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "plan.md"
            source.write_text("# Phase One\n- [x] Build the route\n", encoding="utf-8")
            sha = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
            item_id = task_checklist._item_id("plan.md", "phase-one", "Build the route")
            result = task_checklist.audit_task_checklist(repository_root=root, acceptance_run_id="run", candidate_manifest_hash="sha256:" + "a" * 64, sources=[{"path": "plan.md", "sha256": sha}], evidence_by_item={item_id: {"matrixCheckIds": [], "implementationRefs": [], "testRefs": [], "evidenceIds": []}})
            self.assertEqual("failed", result["status"])
            self.assertEqual("checked_without_evidence", result["items"][0]["status"])
            source.write_text("# Phase One\n- [x] Changed route\n", encoding="utf-8")
            with self.assertRaisesRegex(InputError, "stale"):
                task_checklist.audit_task_checklist(repository_root=root, acceptance_run_id="run", candidate_manifest_hash="sha256:" + "a" * 64, sources=[{"path": "plan.md", "sha256": sha}], evidence_by_item={})

    def test_produced_closure_satisfies_consumer_validator(self) -> None:
        import task_checklist
        from acceptance_core import validate_task_checklist_closure

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "plan.md"
            source.write_text("# Phase One\n- [x] Build the route\n", encoding="utf-8")
            sha = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
            item_id = task_checklist._item_id("plan.md", "phase-one", "Build the route")
            result = task_checklist.audit_task_checklist(repository_root=root, acceptance_run_id="run", candidate_manifest_hash="sha256:" + "a" * 64, sources=[{"path": "plan.md", "sha256": sha}], evidence_by_item={item_id: {"matrixCheckIds": ["C1"], "implementationRefs": ["code"], "testRefs": ["test"], "evidenceIds": ["evidence"]}})
        validate_task_checklist_closure(result)

    def test_consumer_rejects_closure_missing_required_top_level_binding(self) -> None:
        from acceptance_core import InputError, validate_task_checklist_closure

        closure = {"schemaVersion": "task-checklist-closure.v1", "items": [{"taskChecklistItemId": "TASK-CHECK-1", "sourceRef": "plan.md:1", "sectionAnchor": "root", "textSignature": "a", "requiredness": "required", "checked": True, "matrixCheckIds": ["C1"], "implementationRefs": ["code"], "testRefs": ["test"], "evidenceIds": ["evidence"], "status": "verified"}]}
        with self.assertRaisesRegex(InputError, "top-level"):
            validate_task_checklist_closure(closure)

    def test_cli_exposes_task_checklist_audit(self) -> None:
        import acceptance_cli

        self.assertTrue(callable(acceptance_cli.audit_task_checklist_command))

    def test_request_cannot_downgrade_unchecked_authority_item_to_optional(self) -> None:
        import tempfile
        import hashlib
        import task_checklist
        from acceptance_core import InputError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "plan.md"
            source.write_text("# Phase One\n- [ ] Required route closure\n", encoding="utf-8")
            sha = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
            item_id = task_checklist._item_id("plan.md", "phase-one", "Required route closure")
            with self.assertRaisesRegex(InputError, "request-controlled optional"):
                task_checklist.audit_task_checklist(
                    repository_root=root, acceptance_run_id="run", candidate_manifest_hash="sha256:" + "a" * 64,
                    sources=[{"path": "plan.md", "sha256": sha}], evidence_by_item={},
                    optional_items={item_id: "caller waiver"},
                )


if __name__ == "__main__":
    unittest.main()
