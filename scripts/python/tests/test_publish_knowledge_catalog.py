from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PYTHON_ROOT = REPOSITORY_ROOT / "scripts" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

import publish_knowledge_catalog as publication
from _knowledge_catalog_builder import build_layers
from _knowledge_locator_core import verify_current_publication


class KnowledgePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        policy = json.loads((REPOSITORY_ROOT / publication.INPUT_PATHS["policy"]).read_text(encoding="utf-8"))
        exclusions = json.loads((REPOSITORY_ROOT / publication.INPUT_PATHS["exclusions"]).read_text(encoding="utf-8"))
        cls.layers = build_layers(REPOSITORY_ROOT, policy=policy, exclusions=exclusions)
        cls.policy = policy
        cls.exclusions = exclusions

    def test_layer_gate_accepts_current_builder_output_and_rejects_hash_drift(self) -> None:
        snapshot, catalog, projections, legacy = self.layers
        publication._validate_layers(snapshot, catalog, projections, legacy, self.policy, self.exclusions)
        broken = json.loads(json.dumps(projections))
        broken["catalog_sha256"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "projection_binding_invalid"):
            publication._validate_layers(snapshot, catalog, broken, legacy, self.policy, self.exclusions)

    def test_publication_controls_must_match_pinned_main_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path in publication.CONTROL_PATHS:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"current")
            with mock.patch.object(publication, "_main_blob", return_value=b"current"):
                publication._require_main_controls(root, "a" * 40)
            changed = root / publication.CONTROL_PATHS[0]
            changed.write_bytes(b"dirty")
            with mock.patch.object(publication, "_main_blob", return_value=b"current"):
                with self.assertRaisesRegex(ValueError, "dirty_or_stale_publication_control"):
                    publication._require_main_controls(root, "a" * 40)

    def test_evaluation_gate_requires_full_adapter_decision_coverage(self) -> None:
        suite = {"cases": [{} for _ in range(100)]}
        categories = {
            name: {"matched_cases": 25, "failed": 0}
            for name in ("adr", "execution-plan", "architecture", "toolchain")
        }
        results = [
            {
                "status": "passed",
                "expected_result_status": "matched",
                "candidate_count": 1,
                "consumption_decisions": [{"decision": "accepted"}],
            }
            for _ in range(100)
        ]
        report = {
            "schema_version": "jimuyun.repository-knowledge-query-report.v1",
            "summary": {"status": "passed", "total": 100, "passed": 100, "failed": 0, "protocol_total": 4, "protocol_passed": 4},
            "categories": categories,
            "results": results,
        }
        publication._validate_evaluation(report, suite)
        report["results"][0]["consumption_decisions"] = []
        with self.assertRaisesRegex(ValueError, "adapter_consumption_decision_gate_failed"):
            publication._validate_evaluation(report, suite)

    def test_generation_pointer_verifies_all_runtime_artifact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            layer_bytes = {name: b"{}\n" for name in publication.LAYER_PATHS}
            input_bytes = {name: b"{}\n" for name in publication.INPUT_PATHS}
            report = {
                "snapshot": {"snapshot_id": "sha256:" + "1" * 64},
                "policy_revision": "policy-v1",
                "summary": {"status": "passed"},
            }
            for name, path in publication.INPUT_PATHS.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(input_bytes[name])
            with mock.patch.object(publication, "_main_commit", return_value="a" * 40), mock.patch.object(publication, "_locator_smoke"):
                publication._publish_bundle(
                    root,
                    main_commit="a" * 40,
                    layer_bytes=layer_bytes,
                    input_bytes=input_bytes,
                    report_bytes=b"{}\n",
                    report=report,
                )
            self.assertTrue(
                verify_current_publication(
                    root,
                    catalog_path=root / publication.LAYER_PATHS["catalog_v2"],
                    policy_path=root / publication.INPUT_PATHS["policy"],
                    projections_path=root / publication.LAYER_PATHS["projections"],
                )
            )
            (root / publication.LAYER_PATHS["projections"]).write_bytes(b"tampered\n")
            self.assertFalse(
                verify_current_publication(
                    root,
                    catalog_path=root / publication.LAYER_PATHS["catalog_v2"],
                    policy_path=root / publication.INPUT_PATHS["policy"],
                    projections_path=root / publication.LAYER_PATHS["projections"],
                )
            )

    def test_lock_conflict_preserves_current_and_last_known_good(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            index_root = root / "knowledge" / "indexes"
            index_root.mkdir(parents=True)
            current = b'{"generation_id":"current"}\n'
            last_known_good = b'{"generation_id":"lkg"}\n'
            (index_root / "current.json").write_bytes(current)
            (index_root / "last-known-good.json").write_bytes(last_known_good)
            (index_root / "publication.lock").write_text("{}\n", encoding="utf-8", newline="\n")
            result = publication.run(root, publish=True, repeat=1)
            self.assertEqual("blocked", result["status"])
            self.assertEqual("knowledge_publication_lock_conflict", result["error"])
            self.assertEqual(current, (index_root / "current.json").read_bytes())
            self.assertEqual(last_known_good, (index_root / "last-known-good.json").read_bytes())

    def test_dead_pid_lock_is_recovered_with_append_only_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            index_root = root / "knowledge" / "indexes"
            index_root.mkdir(parents=True)
            lock = index_root / "publication.lock"
            lock.write_text(json.dumps({"pid": 2147483647, "token": "stale"}) + "\n", encoding="utf-8")
            with mock.patch.object(publication, "_pid_alive", return_value=False):
                with publication._single_writer(index_root):
                    self.assertTrue(lock.is_file())
            self.assertFalse(lock.exists())
            evidence = list((root / "logs/knowledge-context").rglob("*.json"))
            self.assertEqual(1, len(evidence))
            self.assertEqual("recovered", json.loads(evidence[0].read_text(encoding="utf-8"))["status"])

    def test_old_malformed_lock_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            index_root = root / "knowledge" / "indexes"
            index_root.mkdir(parents=True)
            lock = index_root / "publication.lock"
            lock.write_bytes(b"")
            old = publication.time.time() - publication.MALFORMED_LOCK_GRACE_SECONDS - 1
            os.utime(lock, (old, old))
            with publication._single_writer(index_root):
                self.assertTrue(lock.is_file())
            self.assertFalse(lock.exists())
            evidence = list((root / "logs/knowledge-context").rglob("*.json"))
            self.assertEqual(1, len(evidence))

    def test_reused_pid_lock_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            index_root = root / "knowledge" / "indexes"
            index_root.mkdir(parents=True)
            lock = index_root / "publication.lock"
            lock.write_text(json.dumps({"pid": 42, "process_identity": "old", "token": "stale"}), encoding="utf-8")
            with mock.patch.object(publication, "_pid_alive", return_value=True), mock.patch.object(publication, "_process_identity", return_value="new"):
                with publication._single_writer(index_root):
                    self.assertTrue(lock.is_file())
            self.assertFalse(lock.exists())

    def test_generation_payloads_reject_tampered_immutable_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            layer_bytes = {name: b"{}\n" for name in publication.LAYER_PATHS}
            input_bytes = {name: b"{}\n" for name in publication.INPUT_PATHS}
            report = {
                "snapshot": {"snapshot_id": "sha256:" + "1" * 64},
                "policy_revision": "policy-v1",
                "summary": {"status": "passed"},
            }
            with mock.patch.object(publication, "_main_commit", return_value="a" * 40), mock.patch.object(publication, "_locator_smoke"), mock.patch.object(publication, "verify_current_publication", return_value=True):
                _, pointer = publication._publish_bundle(
                    root,
                    main_commit="a" * 40,
                    layer_bytes=layer_bytes,
                    input_bytes=input_bytes,
                    report_bytes=b"{}\n",
                    report=report,
                )
            manifest, payloads = publication._generation_payloads(root, pointer)
            self.assertEqual(pointer["generation_id"], manifest["generation_id"])
            self.assertEqual(set(publication.REQUIRED_ARTIFACTS), set(payloads))
            generation_root = root / "knowledge" / "indexes" / "generations" / pointer["generation_id"]
            (generation_root / "layers" / publication.LAYER_PATHS["catalog_v2"].name).write_bytes(b"tampered\n")
            with self.assertRaisesRegex(ValueError, "lkg_artifact_hash_invalid:catalog_v2"):
                publication._generation_payloads(root, pointer)

    def test_activate_lkg_restores_four_layers_and_rolls_back_on_verification_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payloads = {name: f'{{"layer":"{name}"}}\n'.encode() for name in publication.LAYER_PATHS}
            old_values: dict[Path, bytes] = {}
            for path in publication.LAYER_PATHS.values():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"old\n")
                old_values[target] = b"old\n"
            current = root / "knowledge" / "indexes" / "current.json"
            current.parent.mkdir(parents=True, exist_ok=True)
            current.write_bytes(b"old-pointer\n")
            old_values[current] = b"old-pointer\n"
            pointer = {
                "schema_version": publication.POINTER_SCHEMA_VERSION,
                "generation_id": "a" * 64,
                "generation_sha256": "sha256:" + "b" * 64,
                "main_commit": "c" * 40,
                "source_snapshot_id": "sha256:" + "d" * 64,
            }
            pointer_bytes = publication._render(pointer)
            layers = {"snapshot": {"ref": "refs/heads/main", "commit": "c" * 40}}
            inputs = {"query_suite": {}}
            with mock.patch.object(publication, "verify_current_publication", return_value=False), mock.patch.object(publication, "_main_commit", return_value="c" * 40):
                with self.assertRaisesRegex(ValueError, "restored_publication_verification_failed"):
                    publication._activate_lkg(
                        root,
                        pointer=pointer,
                        pointer_bytes=pointer_bytes,
                        manifest={"policy_revision": "policy-v1"},
                        payloads=payloads,
                        layers=layers,
                        inputs=inputs,
                        repeat=1,
                        expected_main="c" * 40,
                    )
            for path, expected in old_values.items():
                self.assertEqual(expected, path.read_bytes())

            evaluation = {"summary": {"status": "passed"}}
            with (
                mock.patch.object(publication, "verify_current_publication", return_value=True),
                mock.patch.object(publication, "evaluate", return_value=evaluation),
                mock.patch.object(publication, "_validate_evaluation"),
                mock.patch.object(publication, "_locator_smoke"),
                mock.patch.object(publication, "_main_commit", return_value="c" * 40),
            ):
                result = publication._activate_lkg(
                    root,
                    pointer=pointer,
                    pointer_bytes=pointer_bytes,
                    manifest={"policy_revision": "policy-v1"},
                    payloads=payloads,
                    layers=layers,
                    inputs=inputs,
                    repeat=1,
                    expected_main="c" * 40,
                )
            self.assertEqual(evaluation, result)
            self.assertEqual(pointer_bytes, current.read_bytes())
            for name, path in publication.LAYER_PATHS.items():
                self.assertEqual(payloads[name], (root / path).read_bytes())

    def test_publish_rolls_back_all_formal_state_when_lkg_pointer_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            layer_bytes = {name: f'{{"layer":"{name}"}}\n'.encode() for name in publication.LAYER_PATHS}
            input_bytes = {name: b"{}\n" for name in publication.INPUT_PATHS}
            for name, path in publication.INPUT_PATHS.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(input_bytes[name])
            index_root = root / "knowledge/indexes"
            index_root.mkdir(parents=True, exist_ok=True)
            tracked = [*(root / path for path in publication.LAYER_PATHS.values()), index_root / "current.json", index_root / "last-known-good.json"]
            for path in tracked:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"before\n")
            original_atomic = publication._atomic_bytes

            def fail_lkg(path: Path, payload: bytes) -> None:
                if path == index_root / "last-known-good.json" and payload != b"before\n":
                    raise OSError("injected lkg write failure")
                original_atomic(path, payload)

            report = {"snapshot": {"snapshot_id": "sha256:" + "1" * 64}, "policy_revision": "policy-v1", "summary": {"status": "passed"}}
            with mock.patch.object(publication, "_main_commit", return_value="a" * 40), mock.patch.object(publication, "_atomic_bytes", side_effect=fail_lkg):
                with self.assertRaisesRegex(OSError, "injected lkg"):
                    publication._publish_bundle(root, main_commit="a" * 40, layer_bytes=layer_bytes, input_bytes=input_bytes, report_bytes=b"{}\n", report=report)
            for path in tracked:
                self.assertEqual(b"before\n", path.read_bytes())

    def test_current_pointer_is_the_last_activation_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            layer_bytes = {name: b"{}\n" for name in publication.LAYER_PATHS}
            input_bytes = {name: b"{}\n" for name in publication.INPUT_PATHS}
            for name, path in publication.INPUT_PATHS.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(input_bytes[name])
            writes: list[Path] = []
            real_atomic = publication._atomic_bytes

            def record(path: Path, payload: bytes) -> None:
                writes.append(path)
                real_atomic(path, payload)

            report = {"snapshot": {"snapshot_id": "sha256:" + "1" * 64}, "policy_revision": "policy-v1", "summary": {"status": "passed"}}
            with mock.patch.object(publication, "_main_commit", return_value="a" * 40), mock.patch.object(publication, "_atomic_bytes", side_effect=record), mock.patch.object(publication, "verify_current_publication", return_value=True), mock.patch.object(publication, "_locator_smoke"):
                publication._publish_bundle(root, main_commit="a" * 40, layer_bytes=layer_bytes, input_bytes=input_bytes, report_bytes=b"{}\n", report=report)
            current = root / "knowledge/indexes/current.json"
            self.assertEqual(current, writes[-1])

    def test_runtime_rollback_failure_is_returned_with_structured_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            index_root = root / "knowledge/indexes"
            index_root.mkdir(parents=True)
            failure = Path("logs/knowledge-context/failure.json")
            with mock.patch.object(publication, "_single_writer", return_value=nullcontext()), mock.patch.object(publication, "_main_commit", return_value="a" * 40), mock.patch.object(publication, "_load_pointer", side_effect=RuntimeError("rollback failed")), mock.patch.object(publication, "_write_failure", return_value=failure):
                result = publication.restore_last_known_good(root, repeat=1)
            self.assertEqual("blocked", result["status"])
            self.assertEqual("rollback failed", result["error"])
            self.assertEqual(failure.as_posix(), result["evidence"])

    def test_lkg_restore_rolls_back_when_main_advances_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payloads = {name: f'{{"layer":"{name}"}}\n'.encode() for name in publication.LAYER_PATHS}
            tracked: dict[Path, bytes] = {}
            for path in publication.LAYER_PATHS.values():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"before\n")
                tracked[target] = b"before\n"
            current = root / "knowledge/indexes/current.json"
            current.parent.mkdir(parents=True, exist_ok=True)
            current.write_bytes(b"before-pointer\n")
            tracked[current] = b"before-pointer\n"
            pointer = {"main_commit": "c" * 40}
            with (
                mock.patch.object(publication, "_main_commit", side_effect=["c" * 40, "d" * 40]),
                mock.patch.object(publication, "verify_current_publication", return_value=True),
                mock.patch.object(publication, "evaluate", return_value={"summary": {"status": "passed"}}),
                mock.patch.object(publication, "_validate_evaluation"),
                mock.patch.object(publication, "_locator_smoke"),
            ):
                with self.assertRaisesRegex(ValueError, "main_advanced"):
                    publication._activate_lkg(
                        root,
                        pointer=pointer,
                        pointer_bytes=b"new-pointer\n",
                        manifest={"policy_revision": "policy-v1"},
                        payloads=payloads,
                        layers={"snapshot": {}},
                        inputs={"query_suite": {}},
                        repeat=1,
                        expected_main="c" * 40,
                    )
            for path, expected in tracked.items():
                self.assertEqual(expected, path.read_bytes())

    def test_restore_lkg_rejects_generation_from_stale_main_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(publication, "_git", return_value=SimpleNamespace(returncode=1)):
                with self.assertRaisesRegex(ValueError, "lkg_main_commit_stale"):
                    publication._require_generation_compatible_with_main(
                        root,
                        generation_main="c" * 40,
                        current_main="e" * 40,
                        snapshot={"sources": []},
                        payloads={},
                    )

    def test_restore_lkg_runs_real_evaluator_and_locator_in_temporary_clone(self) -> None:
        source_index = REPOSITORY_ROOT / "knowledge" / "indexes"
        pointer_path = source_index / "last-known-good.json"
        if not pointer_path.is_file():
            self.fail("repository LKG pointer is required for restore integration coverage")
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        generation_id = pointer["generation_id"]
        source_generation = source_index / "generations" / generation_id
        if not source_generation.is_dir():
            self.fail("repository LKG generation is required for restore integration coverage")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            subprocess.run(["git", "clone", "--quiet", "--shared", "--no-checkout", str(REPOSITORY_ROOT), str(root)], check=True)
            current_main = subprocess.run(
                ["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                encoding="ascii",
            ).stdout.strip()
            subprocess.run(["git", "config", "core.sparseCheckout", "true"], cwd=root, check=True)
            sparse_checkout = root / ".git" / "info" / "sparse-checkout"
            sparse_checkout.parent.mkdir(parents=True, exist_ok=True)
            sparse_checkout.write_text("/*\n!**/.acceptance-snapshots/\n", encoding="ascii", newline="\n")
            subprocess.run(
                ["git", "-c", "core.longpaths=true", "checkout", "--quiet", "-B", "main", current_main],
                cwd=root,
                check=True,
            )
            target_index = root / "knowledge" / "indexes"
            target_generation = target_index / "generations" / generation_id
            target_generation.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_generation, target_generation, dirs_exist_ok=True)
            shutil.copy2(pointer_path, target_index / "last-known-good.json")
            for path in publication.LAYER_PATHS.values():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"corrupt\n")
            result = publication.restore_last_known_good(root, repeat=1)
            self.assertEqual("restored", result["status"], result)
            self.assertTrue(
                verify_current_publication(
                    root,
                    catalog_path=root / publication.LAYER_PATHS["catalog_v2"],
                    policy_path=root / publication.INPUT_PATHS["policy"],
                    projections_path=root / publication.LAYER_PATHS["projections"],
                )
            )


if __name__ == "__main__":
    unittest.main()
