from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PYTHON_ROOT = REPOSITORY_ROOT / "scripts" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

import prune_knowledge_generations as pruning
import publish_knowledge_catalog as publication


class KnowledgeGenerationPruningTests(unittest.TestCase):
    def policy(self, keep: int = 2) -> dict:
        return {
            "schema_version": "jimuyun.knowledge-generation-retention-policy.v1",
            "policy_revision": "test-retention-v1",
            "keep_recent_successful": keep,
            "protect_current": True,
            "protect_last_known_good": True,
            "pruning_mode": "explicit-only",
            "failure_evidence_root": "logs/knowledge-context",
        }

    def generation_dirs(self, root: Path, count: int = 5) -> list[str]:
        generation_root = root / "knowledge" / "indexes" / "generations"
        generation_root.mkdir(parents=True)
        index_root = generation_root.parent
        (index_root / "current.json").write_bytes(b"current")
        (index_root / "last-known-good.json").write_bytes(b"lkg")
        ids = [f"{value:064x}" for value in range(1, count + 1)]
        for generation_id in ids:
            (generation_root / generation_id).mkdir()
        return ids

    def inventory_patches(self, ids: list[str]):
        pointers = [
            ({"generation_id": ids[0]}, b"current"),
            ({"generation_id": ids[1]}, b"lkg"),
        ]
        return (
            mock.patch.object(pruning, "_load_valid_pointer", side_effect=pointers),
            mock.patch.object(pruning, "_main_commit_order", return_value={f"c{i}": i for i in range(len(ids))}),
            mock.patch.object(pruning, "_validated_generation", side_effect=lambda _root, generation_id: ({}, int(generation_id, 16))),
            mock.patch.object(pruning, "_generation_first_commit", side_effect=lambda _root, generation_id, _order: int(generation_id, 16)),
            mock.patch.object(publication, "_generation_payloads", return_value=({}, {})),
            mock.patch.object(publication, "_validate_generation_payloads"),
        )

    def test_inventory_always_protects_current_lkg_and_recent_successful(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ids = self.generation_dirs(root)
            patches = self.inventory_patches(ids)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                report = pruning.inventory(root, self.policy())
            self.assertEqual({ids[0], ids[1], ids[3], ids[4]}, set(report["protected_generation_ids"]))
            self.assertEqual([ids[2]], report["candidate_generation_ids"])

    def test_invalid_or_uncommitted_generation_is_reported_and_never_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ids = self.generation_dirs(root, 4)
            patches = self.inventory_patches(ids)
            validator = mock.patch.object(
                pruning,
                "_validated_generation",
                side_effect=lambda _root, generation_id: (_ for _ in ()).throw(ValueError("invalid")) if generation_id == ids[2] else ({}, 1),
            )
            with patches[0], patches[1], validator, patches[3], patches[4], patches[5]:
                report = pruning.inventory(root, self.policy(keep=1))
            self.assertIn(ids[2], report["invalid_generation_ids"])
            self.assertNotIn(ids[2], report["candidate_generation_ids"])

    def test_empty_shell_generation_fails_full_publication_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generation_id = "a" * 64
            shell = root / "knowledge" / "indexes" / "generations" / generation_id
            shell.mkdir(parents=True)
            (shell / "manifest.json").write_text(json.dumps({
                "schema_version": publication.SCHEMA_VERSION,
                "generation_id": generation_id,
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                pruning._validated_generation(root, generation_id)

    def test_canonical_policy_must_match_main_blob(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "retention@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Retention Test"], cwd=root, check=True)
            path = root / pruning.DEFAULT_POLICY
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(self.policy()) + "\n", encoding="utf-8")
            subprocess.run(["git", "add", path.relative_to(root)], cwd=root, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "policy"], cwd=root, check=True)
            subprocess.run(["git", "branch", "-M", "main"], cwd=root, check=True)
            path.write_text(json.dumps(self.policy(keep=1)) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "dirty_or_stale"):
                pruning._canonical_policy(root)

    def test_check_is_read_only_and_prune_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ids = self.generation_dirs(root, 3)
            report = {
                "schema_version": "jimuyun.knowledge-generation-prune-report.v1",
                "status": "checked",
                "policy_revision": "test-retention-v1",
                "candidate_generation_ids": [ids[2]],
            }
            canonical = (self.policy(), b"policy", "a" * 40)
            with mock.patch.object(pruning, "_canonical_policy", return_value=canonical), mock.patch.object(pruning, "inventory", return_value=report), mock.patch.object(publication, "_main_commit", return_value="a" * 40), mock.patch.object(pruning, "_validated_generation", return_value=({}, 1)):
                checked = pruning.run(root, prune=False)
                self.assertTrue((root / "knowledge/indexes/generations" / ids[2]).is_dir())
                pruned = pruning.run(root, prune=True)
            self.assertEqual("checked", checked["status"])
            self.assertEqual("pruned", pruned["status"])
            self.assertFalse((root / "knowledge/indexes/generations" / ids[2]).exists())
            self.assertTrue((root / pruned["evidence"]).is_file())

    def test_partial_delete_failure_preserves_audit_sets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ids = self.generation_dirs(root, 2)
            report = {
                "schema_version": "jimuyun.knowledge-generation-prune-report.v1",
                "status": "checked",
                "policy_revision": "test-retention-v1",
                "candidate_generation_ids": ids,
            }
            real_rmtree = pruning.shutil.rmtree
            calls = 0

            def fail_second(path: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected delete failure")
                real_rmtree(path)

            with mock.patch.object(pruning, "_canonical_policy", return_value=(self.policy(), b"policy", "a" * 40)), mock.patch.object(pruning, "inventory", return_value=report), mock.patch.object(publication, "_main_commit", return_value="a" * 40), mock.patch.object(pruning, "_validated_generation", return_value=({}, 1)), mock.patch.object(pruning.shutil, "rmtree", side_effect=fail_second):
                result = pruning.run(root, prune=True)
            self.assertEqual("failed", result["status"])
            self.assertEqual(ids, result["removed_generation_ids"])
            self.assertEqual([], result["remaining_generation_ids"])
            self.assertEqual([ids[1]], result["cleanup_failed_generation_ids"])
            self.assertTrue((root / result["evidence"]).is_file())

    def test_main_advance_before_prune_commit_restores_quarantined_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ids = self.generation_dirs(root, 1)
            report = {
                "schema_version": "jimuyun.knowledge-generation-prune-report.v1",
                "status": "checked",
                "policy_revision": "test-retention-v1",
                "candidate_generation_ids": ids,
            }
            with mock.patch.object(pruning, "_canonical_policy", return_value=(self.policy(), b"policy", "a" * 40)), mock.patch.object(pruning, "inventory", return_value=report), mock.patch.object(publication, "_main_commit", side_effect=["a" * 40, "a" * 40, "b" * 40]), mock.patch.object(pruning, "_validated_generation", return_value=({}, 1)):
                result = pruning.run(root, prune=True)
            self.assertEqual("failed", result["status"])
            self.assertEqual([], result["removed_generation_ids"])
            self.assertEqual(ids, result["remaining_generation_ids"])
            self.assertTrue((root / "knowledge/indexes/generations" / ids[0]).is_dir())

    def test_cli_has_no_policy_override_and_publication_never_prunes(self) -> None:
        pruning_source = (PYTHON_ROOT / "prune_knowledge_generations.py").read_text(encoding="utf-8")
        publication_source = (PYTHON_ROOT / "publish_knowledge_catalog.py").read_text(encoding="utf-8")
        self.assertNotIn('add_argument("--policy"', pruning_source)
        self.assertNotIn("prune_knowledge_generations", publication_source)


if __name__ == "__main__":
    unittest.main()
