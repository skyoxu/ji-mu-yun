from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import acceptance_cli
import acceptance_core


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _git(repository_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


def _run_input(
    target_root: Path,
    baseline: dict,
    candidate: dict,
    *,
    baseline_revision: str = "baseline",
    candidate_revision: str = "candidate",
    candidate_mode: str = "commit",
    snapshot_path: str | None = None,
) -> dict:
    changed_paths = sorted(
        item.get("candidate_path") or item.get("baseline_path")
        for item in candidate["files"]
        if item["change_type"] != "unchanged"
    )
    value = {
        "target": str(target_root),
        "run_id": "run",
        "created_utc": "2026-07-28T00:00:00Z",
        "change_id": "change",
        "baseline_revision": baseline_revision,
        "candidate_revision": candidate_revision,
        "candidate_mode": candidate_mode,
        "target_plan_paths": ["plan"],
        "execution_mode": "evidence_only",
        "baseline_content_manifest_path": "baseline.json",
        "baseline_content_manifest_hash": acceptance_cli.canonical_hash(baseline),
        "candidate_content_manifest_path": "candidate.json",
        "candidate_content_manifest_hash": acceptance_cli.canonical_hash(candidate),
        "code_review_domain": "phase_service",
        "code_review_policy_path": "policy.json",
        "code_review_policy_hash": "sha256:" + "1" * 64,
        "target_plan_hash": "sha256:" + "2" * 64,
        "validator_hash": "sha256:" + "3" * 64,
        "adapter_id": "adapter",
        "adapter_version": "1",
        "adapter_hash": "sha256:" + "4" * 64,
        "allowed_write_roots": [],
        "forbidden_write_roots": [],
        "changed_paths": changed_paths,
        "affected_consumer_refs": [],
    }
    if snapshot_path is not None:
        value["candidate_frozen_snapshot_path"] = snapshot_path
    return value


def _write_prepare_inputs(target_root: Path, baseline: dict, candidate: dict, run_input: dict) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    (target_root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    (target_root / "candidate.json").write_text(json.dumps(candidate), encoding="utf-8")
    (target_root / "input.json").write_text(json.dumps(run_input), encoding="utf-8")


class RunInputTests(unittest.TestCase):
    def test_git_lookup_disables_replace_objects(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"ok", stderr=b"")
        with mock.patch.object(acceptance_core.subprocess, "run", return_value=completed) as run:
            self.assertEqual(b"ok", acceptance_core._git(Path.cwd(), "status"))

        self.assertEqual("1", run.call_args.kwargs["env"]["GIT_NO_REPLACE_OBJECTS"])

    def test_run_input_requires_exact_target_and_evidence_only_default(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "acceptance_cli", SKILL_ROOT / "scripts" / "acceptance_cli.py"
        )
        self.assertIsNotNone(spec)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(module.InputError):
            module.parse_run_input({"target": "relative"})
        parsed = module.parse_run_input({"target": "C:/jimuyun/execution-plans/example"})
        self.assertEqual("evidence_only", parsed["execution_mode"])

    def test_full_run_input_rejects_missing_hash_bound_contract(self) -> None:
        from acceptance_core import InputError, validate_run_input

        with self.assertRaises(InputError):
            validate_run_input({"target": "C:/jimuyun/execution-plans/example"})

    def test_prepare_rejects_stale_candidate_manifest_hash(self) -> None:
        from acceptance_core import canonical_hash, InputError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            (root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
            (root / "candidate.json").write_text(json.dumps(candidate), encoding="utf-8")
            input_value = {"target": str(root), "run_id": "run", "created_utc": "2026-07-28T00:00:00Z", "change_id": "change", "baseline_revision": "a", "candidate_revision": "b", "candidate_mode": "commit", "target_plan_paths": ["plan"], "execution_mode": "evidence_only", "baseline_content_manifest_path": "baseline.json", "baseline_content_manifest_hash": canonical_hash(baseline), "candidate_content_manifest_path": "candidate.json", "candidate_content_manifest_hash": "sha256:" + "0" * 64, "code_review_domain": "phase_service", "code_review_policy_path": "policy.json", "code_review_policy_hash": "sha256:" + "1" * 64, "target_plan_hash": "sha256:" + "2" * 64, "validator_hash": "sha256:" + "3" * 64, "adapter_id": "adapter", "adapter_version": "1", "adapter_hash": "sha256:" + "4" * 64, "allowed_write_roots": [], "forbidden_write_roots": [], "changed_paths": [], "affected_consumer_refs": []}
            source = root / "input.json"
            source.write_text(json.dumps(input_value), encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(root)
                with self.assertRaisesRegex(InputError, "candidate content manifest hash is stale"):
                    acceptance_cli.prepare_run("input.json", "run.json")
            finally:
                os.chdir(previous)

    def test_prepare_publishes_hash_bound_non_authorizing_run_input(self) -> None:
        from acceptance_core import canonical_hash

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            (root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
            (root / "candidate.json").write_text(json.dumps(candidate), encoding="utf-8")
            (root / ".acceptance-snapshots" / "run").mkdir(parents=True)
            value = {"target": str(root), "run_id": "run", "created_utc": "2026-07-28T00:00:00Z", "change_id": "change", "baseline_revision": "a", "candidate_revision": "b", "candidate_mode": "dirty_worktree", "candidate_frozen_snapshot_path": ".acceptance-snapshots/run", "target_plan_paths": ["plan"], "execution_mode": "evidence_only", "baseline_content_manifest_path": "baseline.json", "baseline_content_manifest_hash": canonical_hash(baseline), "candidate_content_manifest_path": "candidate.json", "candidate_content_manifest_hash": canonical_hash(candidate), "code_review_domain": "phase_service", "code_review_policy_path": "policy.json", "code_review_policy_hash": "sha256:" + "1" * 64, "target_plan_hash": "sha256:" + "2" * 64, "validator_hash": "sha256:" + "3" * 64, "adapter_id": "adapter", "adapter_version": "1", "adapter_hash": "sha256:" + "4" * 64, "allowed_write_roots": [], "forbidden_write_roots": [], "changed_paths": [], "affected_consumer_refs": []}
            (root / "input.json").write_text(json.dumps(value), encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(root)
                result = acceptance_cli.prepare_run("input.json", "run.json")
            finally:
                os.chdir(previous)
            self.assertEqual([], result["authorizes"])
            self.assertTrue((root / "run.json").is_file())

    def test_prepare_commit_reads_candidate_bytes_from_immutable_git_blob(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory)
            _git(repository_root, "init", "--quiet")
            _git(repository_root, "config", "user.email", "acceptance@example.invalid")
            _git(repository_root, "config", "user.name", "Acceptance Test")
            _git(repository_root, "config", "core.autocrlf", "false")
            _git(repository_root, "commit", "--allow-empty", "--quiet", "-m", "baseline")
            baseline_revision = _git(repository_root, "rev-parse", "HEAD")
            candidate_bytes = b"candidate bytes\n"
            source = repository_root / "PhaseA.Platform" / "Program.cs"
            source.parent.mkdir(parents=True)
            source.write_bytes(candidate_bytes)
            _git(repository_root, "add", "PhaseA.Platform/Program.cs")
            _git(repository_root, "commit", "--quiet", "-m", "candidate")
            candidate_revision = _git(repository_root, "rev-parse", "HEAD")
            source.write_bytes(b"live worktree bytes must not be read\n")

            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": _sha256(candidate_bytes), "inclusion_reason": "candidate commit"}]}
            target = repository_root / "execution-plans" / "acceptance"
            value = _run_input(target, baseline, candidate, baseline_revision=baseline_revision, candidate_revision=candidate_revision)
            _write_prepare_inputs(target, baseline, candidate, value)

            result = acceptance_cli.prepare_run(str(target / "input.json"), str(target / "run.json"))

            self.assertEqual([], result["authorizes"])
            self.assertEqual(baseline_revision, result["candidateCustody"]["baselineResolvedCommit"])
            self.assertEqual(candidate_revision, result["candidateCustody"]["candidateResolvedCommit"])

    def test_git_blob_resolves_object_id_before_reading_long_repository_path(self) -> None:
        import acceptance_core

        object_id = "a" * 40
        relative = "nested/" + ("long-segment/" * 24) + "artifact.json"
        tree_entry = f"100644 blob {object_id}\t{relative}\0".encode("utf-8")
        with mock.patch.object(
            acceptance_core, "_git", side_effect=[tree_entry, b"immutable bytes"]
        ) as git_call:
            payload = acceptance_core._git_blob(Path("."), "b" * 40, relative, "candidate")

        self.assertEqual(b"immutable bytes", payload)
        self.assertEqual(
            (Path("."), "cat-file", "blob", object_id),
            git_call.call_args_list[1].args,
        )

    def test_prepare_commit_rejects_complete_manifest_that_omits_changed_file(self) -> None:
        from acceptance_core import InputError

        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory)
            _git(repository_root, "init", "--quiet")
            _git(repository_root, "config", "user.email", "acceptance@example.invalid")
            _git(repository_root, "config", "user.name", "Acceptance Test")
            _git(repository_root, "config", "core.autocrlf", "false")
            _git(repository_root, "commit", "--allow-empty", "--quiet", "-m", "baseline")
            baseline_revision = _git(repository_root, "rev-parse", "HEAD")
            for name in ("Declared.cs", "Omitted.cs"):
                source = repository_root / "PhaseA.Platform" / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(f"class {Path(name).stem} {{}}\n", encoding="utf-8")
            _git(repository_root, "add", "PhaseA.Platform")
            _git(repository_root, "commit", "--quiet", "-m", "candidate")
            candidate_revision = _git(repository_root, "rev-parse", "HEAD")
            declared = (repository_root / "PhaseA.Platform" / "Declared.cs").read_bytes()
            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform/Declared.cs", "candidate_sha256": _sha256(declared), "inclusion_reason": "declared only"}]}
            target = repository_root / "execution-plans" / "acceptance"
            _write_prepare_inputs(target, baseline, candidate, _run_input(target, baseline, candidate, baseline_revision=baseline_revision, candidate_revision=candidate_revision))

            with self.assertRaisesRegex(InputError, "exactly match the immutable commit diff"):
                acceptance_cli.prepare_run(str(target / "input.json"), str(target / "run.json"))

    def test_prepare_commit_rejects_current_manifest_with_stale_candidate_file_hash(self) -> None:
        from acceptance_core import InputError

        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory)
            _git(repository_root, "init", "--quiet")
            _git(repository_root, "config", "user.email", "acceptance@example.invalid")
            _git(repository_root, "config", "user.name", "Acceptance Test")
            source = repository_root / "PhaseA.Platform" / "Program.cs"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"current candidate\n")
            _git(repository_root, "add", "PhaseA.Platform/Program.cs")
            _git(repository_root, "commit", "--quiet", "-m", "candidate")
            candidate_revision = _git(repository_root, "rev-parse", "HEAD")

            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": _sha256(b"stale candidate\n"), "inclusion_reason": "stale bytes"}]}
            target = repository_root / "execution-plans" / "acceptance"
            value = _run_input(target, baseline, candidate, baseline_revision=candidate_revision, candidate_revision=candidate_revision)
            _write_prepare_inputs(target, baseline, candidate, value)

            with self.assertRaisesRegex(InputError, "candidate manifest hash.*declared file bytes"):
                acceptance_cli.prepare_run(str(target / "input.json"), str(target / "run.json"))
            self.assertFalse((target / "run.json").exists())

    def test_prepare_commit_binds_deletion_only_candidate_and_rejects_missing_tombstone(self) -> None:
        from acceptance_core import InputError

        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory)
            _git(repository_root, "init", "--quiet")
            _git(repository_root, "config", "user.email", "acceptance@example.invalid")
            _git(repository_root, "config", "user.name", "Acceptance Test")
            source = repository_root / "PhaseA.Platform" / "Removed.cs"
            source.parent.mkdir(parents=True)
            baseline_bytes = b"remove me\n"
            source.write_bytes(baseline_bytes)
            _git(repository_root, "add", "PhaseA.Platform/Removed.cs")
            _git(repository_root, "commit", "--quiet", "-m", "baseline")
            baseline_revision = _git(repository_root, "rev-parse", "HEAD")
            source.unlink()
            _git(repository_root, "add", "--all")
            _git(repository_root, "commit", "--quiet", "-m", "delete")
            candidate_revision = _git(repository_root, "rev-parse", "HEAD")

            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"path": "PhaseA.Platform/Removed.cs", "roles": ["implementation"], "sha256": _sha256(baseline_bytes), "inclusion_reason": "baseline"}]}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "deleted", "roles": ["implementation"], "baseline_path": "PhaseA.Platform/Removed.cs", "baseline_sha256": _sha256(baseline_bytes), "candidate_path": None, "candidate_sha256": None, "inclusion_reason": "deleted"}]}
            target = repository_root / "execution-plans" / "acceptance"
            value = _run_input(target, baseline, candidate, baseline_revision=baseline_revision, candidate_revision=candidate_revision)
            _write_prepare_inputs(target, baseline, candidate, value)

            result = acceptance_cli.prepare_run(str(target / "input.json"), str(target / "run.json"))
            self.assertEqual(candidate_revision, result["candidateCustody"]["candidateResolvedCommit"])

            stale_value = _run_input(target, baseline, candidate, baseline_revision=baseline_revision, candidate_revision=baseline_revision)
            (target / "input.json").write_text(json.dumps(stale_value), encoding="utf-8")
            with self.assertRaisesRegex(InputError, "still contains removed path"):
                acceptance_cli.prepare_run(str(target / "input.json"), str(target / "stale-run.json"))

    def test_run_input_rejects_nul_in_revision_or_relative_path(self) -> None:
        from acceptance_core import InputError, validate_run_input

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            invalid_revision = _run_input(target, baseline, candidate, baseline_revision="HEAD\0bad")
            with self.assertRaisesRegex(InputError, "revisions cannot contain NUL"):
                validate_run_input(invalid_revision)
            invalid_path = _run_input(target, baseline, candidate, candidate_mode="dirty_worktree", snapshot_path=".acceptance-snapshots/run\0bad")
            with self.assertRaisesRegex(InputError, "repository-relative path"):
                validate_run_input(invalid_path)

    def test_prepare_dirty_worktree_reads_only_contained_frozen_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            frozen_bytes = b"frozen candidate\n"
            snapshot = target / ".acceptance-snapshots" / "run" / "PhaseA.Platform" / "Program.cs"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_bytes(frozen_bytes)
            live_file = target / "PhaseA.Platform" / "Program.cs"
            live_file.parent.mkdir(parents=True)
            live_file.write_bytes(b"live workspace bytes must not be read\n")

            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "untracked", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": _sha256(frozen_bytes), "inclusion_reason": "frozen dirty candidate"}]}
            value = _run_input(target, baseline, candidate, candidate_mode="dirty_worktree", snapshot_path=".acceptance-snapshots/run")
            _write_prepare_inputs(target, baseline, candidate, value)

            result = acceptance_cli.prepare_run(str(target / "input.json"), str(target / "run.json"))

            self.assertEqual([], result["authorizes"])
            self.assertTrue(result["candidateCustody"]["snapshotManifestHash"].startswith("sha256:"))

    def test_prepare_dirty_worktree_rejects_complete_snapshot_with_undeclared_file(self) -> None:
        from acceptance_core import InputError

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            snapshot_root = target / ".acceptance-snapshots" / "run" / "PhaseA.Platform"
            snapshot_root.mkdir(parents=True)
            declared = snapshot_root / "Declared.cs"
            declared.write_bytes(b"class Declared {}\n")
            (snapshot_root / "Omitted.cs").write_bytes(b"class Omitted {}\n")
            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "untracked", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform/Declared.cs", "candidate_sha256": _sha256(declared.read_bytes()), "inclusion_reason": "declared only"}]}
            _write_prepare_inputs(target, baseline, candidate, _run_input(target, baseline, candidate, candidate_mode="dirty_worktree", snapshot_path=".acceptance-snapshots/run"))

            with self.assertRaisesRegex(InputError, "exactly match its manifest"):
                acceptance_cli.prepare_run(str(target / "input.json"), str(target / "run.json"))

    def test_prepare_proposed_commit_set_reads_contained_frozen_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            frozen_bytes = b"proposed candidate\n"
            snapshot = target / ".acceptance-snapshots" / "run" / "PhaseA.Platform" / "Program.cs"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_bytes(frozen_bytes)
            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "untracked", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": _sha256(frozen_bytes), "inclusion_reason": "frozen proposed candidate"}]}
            value = _run_input(target, baseline, candidate, candidate_mode="proposed_commit_set", snapshot_path=".acceptance-snapshots/run")
            _write_prepare_inputs(target, baseline, candidate, value)

            result = acceptance_cli.prepare_run(str(target / "input.json"), str(target / "run.json"))

            self.assertEqual([], result["authorizes"])

    def test_prepare_dirty_worktree_rejects_current_manifest_with_stale_snapshot_bytes(self) -> None:
        from acceptance_core import InputError

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            snapshot = target / ".acceptance-snapshots" / "run" / "PhaseA.Platform" / "Program.cs"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_bytes(b"new snapshot bytes\n")
            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "untracked", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": _sha256(b"old snapshot bytes\n"), "inclusion_reason": "stale frozen candidate"}]}
            value = _run_input(target, baseline, candidate, candidate_mode="dirty_worktree", snapshot_path=".acceptance-snapshots/run")
            _write_prepare_inputs(target, baseline, candidate, value)

            with self.assertRaisesRegex(InputError, "candidate manifest hash.*declared file bytes"):
                acceptance_cli.prepare_run(str(target / "input.json"), str(target / "run.json"))
            self.assertFalse((target / "run.json").exists())

    def test_prepare_dirty_worktree_requires_a_proper_frozen_snapshot_directory(self) -> None:
        from acceptance_core import InputError

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            missing = _run_input(target, baseline, candidate, candidate_mode="dirty_worktree")
            _write_prepare_inputs(target, baseline, candidate, missing)
            with self.assertRaisesRegex(InputError, "candidate_frozen_snapshot_path"):
                acceptance_cli.prepare_run(str(target / "input.json"), str(target / "missing-run.json"))

            target_root = _run_input(target, baseline, candidate, candidate_mode="dirty_worktree", snapshot_path=".")
            (target / "input.json").write_text(json.dumps(target_root), encoding="utf-8")
            with self.assertRaisesRegex(InputError, "acceptance-snapshots namespace"):
                acceptance_cli.prepare_run(str(target / "input.json"), str(target / "root-run.json"))

    def test_prepare_dirty_worktree_rejects_escaped_or_missing_snapshot_file(self) -> None:
        from acceptance_core import InputError

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "untracked", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": _sha256(b"missing\n"), "inclusion_reason": "missing frozen file"}]}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / ".acceptance-snapshots" / "run").mkdir(parents=True)
            missing_file = _run_input(target, baseline, candidate, candidate_mode="dirty_worktree", snapshot_path=".acceptance-snapshots/run")
            _write_prepare_inputs(target, baseline, candidate, missing_file)
            with self.assertRaisesRegex(InputError, "candidate snapshot file is missing"):
                acceptance_cli.prepare_run(str(target / "input.json"), str(target / "missing-file-run.json"))

            escaped = _run_input(target, baseline, candidate, candidate_mode="dirty_worktree", snapshot_path="../outside")
            (target / "input.json").write_text(json.dumps(escaped), encoding="utf-8")
            with self.assertRaisesRegex(InputError, "repository-relative path"):
                acceptance_cli.prepare_run(str(target / "input.json"), str(target / "escaped-run.json"))

    def test_prepare_dirty_worktree_rejects_shared_hardlink_bytes(self) -> None:
        from acceptance_core import InputError

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            relative_path = Path("PhaseA.Platform") / "Program.cs"
            live_file = target / relative_path
            live_file.parent.mkdir(parents=True)
            live_file.write_text("class Live {}\n", encoding="utf-8")
            snapshot_file = target / ".acceptance-snapshots" / "run" / relative_path
            snapshot_file.parent.mkdir(parents=True)
            os.link(live_file, snapshot_file)
            candidate = {
                "schemaVersion": "acceptance-candidate-content-manifest.v1",
                "status": "complete",
                "coverageGaps": [],
                "authorizes": [],
                "files": [
                    {
                        "change_type": "added",
                        "roles": ["implementation"],
                        "baseline_path": None,
                        "baseline_sha256": None,
                        "candidate_path": relative_path.as_posix(),
                        "candidate_sha256": _sha256(live_file.read_bytes()),
                        "inclusion_reason": "candidate",
                    }
                ],
            }
            run_input = _run_input(
                target,
                baseline,
                candidate,
                candidate_mode="dirty_worktree",
                snapshot_path=".acceptance-snapshots/run",
            )
            _write_prepare_inputs(target, baseline, candidate, run_input)

            with self.assertRaisesRegex(InputError, "shared hardlink"):
                acceptance_cli.prepare_run(str(target / "input.json"), str(target / "hardlink-run.json"))

    def test_git_path_lookup_fails_closed_for_invalid_object(self) -> None:
        from acceptance_core import InputError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _git(root, "init")
            _git(root, "config", "user.email", "acceptance@example.invalid")
            _git(root, "config", "user.name", "Acceptance Test")
            (root / "tracked.txt").write_text("base\n", encoding="utf-8")
            _git(root, "add", "tracked.txt")
            _git(root, "commit", "-m", "base")
            commit = _git(root, "rev-parse", "HEAD")

            self.assertFalse(acceptance_core._git_path_exists(root, commit, "missing.txt", "missing path"))
            with self.assertRaises(InputError):
                acceptance_core._git_path_exists(root, "0" * 40, "missing.txt", "invalid object")

    def test_candidate_manifest_requires_deleted_tombstone_to_match_baseline(self) -> None:
        from acceptance_core import InputError, validate_candidate_manifest

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"path": "a.py", "roles": ["implementation"], "sha256": "sha256:" + "a" * 64, "inclusion_reason": "source"}]}
        invalid = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "deleted", "roles": ["implementation"], "baseline_path": "a.py", "baseline_sha256": "sha256:" + "b" * 64, "candidate_path": None, "candidate_sha256": None}]}
        with self.assertRaises(InputError):
            validate_candidate_manifest(invalid, baseline)

    def test_candidate_manifest_requires_modified_path_to_close_against_baseline(self) -> None:
        from acceptance_core import InputError, validate_candidate_manifest

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"path": "a.py", "roles": ["implementation"], "sha256": "sha256:" + "a" * 64, "inclusion_reason": "source"}]}
        invalid = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "modified", "roles": ["implementation"], "baseline_path": "a.py", "baseline_sha256": "sha256:" + "b" * 64, "candidate_path": "a.py", "candidate_sha256": "sha256:" + "c" * 64, "inclusion_reason": "modified source"}]}
        with self.assertRaisesRegex(InputError, "close against the baseline"):
            validate_candidate_manifest(invalid, baseline)

    def test_complete_candidate_manifest_rejects_omitted_baseline_path(self) -> None:
        from acceptance_core import InputError, validate_candidate_manifest

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"path": "PhaseA.Platform/A.cs", "roles": ["implementation"], "sha256": "sha256:" + "a" * 64, "inclusion_reason": "baseline"}]}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        with self.assertRaisesRegex(InputError, "cover every baseline"):
            validate_candidate_manifest(candidate, baseline)

    def test_complete_candidate_manifest_rejects_unknown_unchanged_baseline_path(self) -> None:
        from acceptance_core import InputError, validate_candidate_manifest

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "unchanged", "roles": ["implementation"], "baseline_path": "PhaseA.Platform/Invented.cs", "baseline_sha256": "sha256:" + "a" * 64, "candidate_path": "PhaseA.Platform/Invented.cs", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "spoofed baseline"}]}
        with self.assertRaisesRegex(InputError, "close against the baseline"):
            validate_candidate_manifest(candidate, baseline)

    def test_candidate_manifest_rejects_unknown_file_fields(self) -> None:
        from acceptance_core import InputError, validate_candidate_manifest

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        invalid = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "a.py", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "source", "untrusted": True}]}
        with self.assertRaisesRegex(InputError, "fields are invalid"):
            validate_candidate_manifest(invalid, baseline)

    def test_candidate_manifest_rejects_non_hex_sha256_digest(self) -> None:
        from acceptance_core import InputError, validate_candidate_manifest

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        invalid = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": "sha256:" + "z" * 64, "inclusion_reason": "invalid digest"}]}
        with self.assertRaisesRegex(InputError, "sha256 hash"):
            validate_candidate_manifest(invalid, baseline)

    def test_rename_and_copy_changed_paths_include_both_git_identities(self) -> None:
        from acceptance_core import _git_changed_paths, candidate_changed_paths

        for change_type in ("renamed", "copied"):
            with self.subTest(change_type=change_type), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _git(root, "init")
                _git(root, "config", "user.email", "acceptance@example.invalid")
                _git(root, "config", "user.name", "Acceptance Test")
                source = root / "source.txt"
                source.write_text("same content\n", encoding="utf-8")
                _git(root, "add", "source.txt")
                _git(root, "commit", "-m", "baseline")
                baseline_commit = _git(root, "rev-parse", "HEAD")
                target = root / "target.txt"
                if change_type == "renamed":
                    source.rename(target)
                else:
                    target.write_bytes(source.read_bytes())
                _git(root, "add", "-A")
                _git(root, "commit", "-m", change_type)
                candidate_commit = _git(root, "rev-parse", "HEAD")
                manifest = {
                    "files": [{
                        "change_type": change_type,
                        "baseline_path": "source.txt",
                        "candidate_path": "target.txt",
                    }]
                }
                self.assertEqual(
                    _git_changed_paths(root, baseline_commit, candidate_commit),
                    set(candidate_changed_paths(manifest)),
                )

    def test_candidate_manifest_rejects_unknown_top_level_fields(self) -> None:
        from acceptance_core import InputError, validate_candidate_manifest

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        invalid = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [], "untrusted": True}
        with self.assertRaisesRegex(InputError, "top-level fields"):
            validate_candidate_manifest(invalid, baseline)

    def test_prepare_rejects_run_input_changed_paths_not_in_candidate_manifest(self) -> None:
        from acceptance_core import canonical_hash, InputError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
            (root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
            (root / "candidate.json").write_text(json.dumps(candidate), encoding="utf-8")
            value = {"target": str(root), "run_id": "run", "created_utc": "2026-07-28T00:00:00Z", "change_id": "change", "baseline_revision": "a", "candidate_revision": "b", "candidate_mode": "commit", "target_plan_paths": ["plan"], "execution_mode": "evidence_only", "baseline_content_manifest_path": "baseline.json", "baseline_content_manifest_hash": canonical_hash(baseline), "candidate_content_manifest_path": "candidate.json", "candidate_content_manifest_hash": canonical_hash(candidate), "code_review_domain": "phase_service", "code_review_policy_path": "policy.json", "code_review_policy_hash": "sha256:" + "1" * 64, "target_plan_hash": "sha256:" + "2" * 64, "validator_hash": "sha256:" + "3" * 64, "adapter_id": "adapter", "adapter_version": "1", "adapter_hash": "sha256:" + "4" * 64, "allowed_write_roots": [], "forbidden_write_roots": [], "changed_paths": ["not-in-candidate.cs"], "affected_consumer_refs": []}
            (root / "input.json").write_text(json.dumps(value), encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(root)
                with self.assertRaisesRegex(InputError, "changed_paths"):
                    acceptance_cli.prepare_run("input.json", "run.json")
            finally:
                os.chdir(previous)

    def test_semantic_partition_cannot_claim_deterministic_completion(self) -> None:
        from acceptance_core import InputError, validate_source_inventory

        value = {"schemaVersion": "acceptance-source-inventory.v1", "overallCompleteness": "deterministic_complete", "partitions": [{"partition_id": "semantic", "source_refs": [{"path": "authority.md", "sha256": "sha256:" + "a" * 64}], "extraction_mode": "semantic_candidate", "completeness": "deterministic_complete"}]}
        with self.assertRaises(InputError):
            validate_source_inventory(value)

    def test_semantically_attested_partition_requires_current_attestation_bindings(self) -> None:
        from acceptance_core import InputError, validate_source_inventory

        value = {"schemaVersion": "acceptance-source-inventory.v1", "overallCompleteness": "semantically_attested_complete", "partitions": [{"partition_id": "semantic", "source_refs": [{"path": "authority.md", "sha256": "sha256:" + "a" * 64}], "extraction_mode": "semantic_candidate", "completeness": "semantically_attested_complete"}]}
        with self.assertRaisesRegex(InputError, "attestationHash"):
            validate_source_inventory(value)

    def test_source_inventory_rejects_unknown_top_level_fields(self) -> None:
        from acceptance_core import InputError, validate_source_inventory

        value = {"schemaVersion": "acceptance-source-inventory.v1", "overallCompleteness": "candidate", "partitions": [{"partition_id": "source", "source_refs": [{"path": "authority.md", "sha256": "sha256:" + "a" * 64}], "extraction_mode": "parser_backed", "completeness": "candidate"}], "untrusted": True}
        with self.assertRaisesRegex(InputError, "top-level fields"):
            validate_source_inventory(value)

    def test_pure_godot_candidate_is_not_a_phase_code_review_domain(self) -> None:
        from acceptance_core import InputError, resolve_phase_policy

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "Game.Godot/Player.cs", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "test"}]}
        with self.assertRaisesRegex(InputError, "unsupported_code_review_domain"):
            resolve_phase_policy(policy, candidate, {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}, "sha256:" + "b" * 64)

    def test_policy_revision_is_bound_to_policy_content(self) -> None:
        from acceptance_core import InputError, validate_policy_pack

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        policy["checks"].pop()
        with self.assertRaisesRegex(InputError, "revision is stale"):
            validate_policy_pack(policy)

    def test_policy_pack_rejects_unknown_top_level_fields_even_with_recomputed_revision(self) -> None:
        from acceptance_core import InputError, canonical_hash, validate_policy_pack

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        policy["untrusted"] = True
        policy["policyRevision"] = canonical_hash({key: value for key, value in policy.items() if key != "policyRevision"})
        with self.assertRaisesRegex(InputError, "fields are invalid"):
            validate_policy_pack(policy)

    def test_policy_pack_rejects_unknown_check_fields(self) -> None:
        from acceptance_core import InputError, canonical_hash, validate_policy_pack

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        policy["checks"][0]["untrusted"] = True
        policy["policyRevision"] = canonical_hash({key: value for key, value in policy.items() if key != "policyRevision"})
        with self.assertRaisesRegex(InputError, "check fields"):
            validate_policy_pack(policy)

    def test_diff_coverage_rejects_repo_wide_or_below_threshold_result(self) -> None:
        from acceptance_core import InputError, validate_diff_coverage

        result = {"schemaVersion": "phase-diff-coverage-result.v1", "status": "passed", "minimumChangedLineCoveragePct": 85.0, "counts": {"measurableChangedExecutableLines": 20, "coveredChangedExecutableLines": 16}, "changedLineCoveragePct": 80.0}
        with self.assertRaisesRegex(InputError, "required threshold"):
            validate_diff_coverage(result)

    def test_task_checklist_requires_evidence_not_checkbox_only(self) -> None:
        from acceptance_core import InputError, validate_task_checklist_closure

        with self.assertRaisesRegex(InputError, "not closed"):
            validate_task_checklist_closure({"schemaVersion": "task-checklist-closure.v1", "acceptanceRunId": "run", "candidateContentManifestHash": "sha256:" + "a" * 64, "sources": [{"path": "plan.md", "sha256": "sha256:" + "b" * 64}], "items": [{"taskChecklistItemId": "x", "sourceRef": "plan.md:1", "sectionAnchor": "root", "textSignature": "a", "requiredness": "required", "checked": True, "matrixCheckIds": [], "implementationRefs": [], "testRefs": [], "evidenceIds": [], "status": "checked_without_evidence"}], "requiredItemCount": 1, "checkedRequiredItemCount": 1, "verifiedRequiredItemCount": 0, "status": "failed", "authorizes": []})

    def test_policy_matrix_rejects_missing_activated_check(self) -> None:
        from acceptance_core import InputError, validate_policy_matrix_coverage

        binding = {"activatedCheckIds": ["PHASE-CR-ARCH-001", "PHASE-CR-ARCH-002"], "bindingHash": "sha256:" + "a" * 64}
        with self.assertRaisesRegex(InputError, "exact matrix coverage"):
            validate_policy_matrix_coverage(binding, [{"policyCheckId": "PHASE-CR-ARCH-001", "check_id": "check", "policyBindingHash": binding["bindingHash"]}])

    def test_scan_scope_rejects_partial_phase_path_coverage(self) -> None:
        from acceptance_core import InputError, validate_scan_scope

        result = {"schemaVersion": "phase-scan-bundle-result.v1", "bundleId": "phase-security-scan", "status": "passed", "candidateContentManifestHash": "sha256:" + "a" * 64, "requiredChangedPaths": ["PhaseA.Platform/A.cs"], "readChangedPaths": ["PhaseA.Platform/A.cs"], "missingChangedPaths": [], "commandId": "phase-security", "toolHash": "sha256:" + "c" * 64, "commandRegistryHash": "sha256:" + "d" * 64, "processResultHash": "sha256:" + "e" * 64, "processResult": {"exitCode": 0}}
        with self.assertRaisesRegex(InputError, "scope is incomplete"):
            validate_scan_scope(result, ["PhaseA.Platform/A.cs", "PhaseA.Platform/B.cs"], "security-scan")

    def test_phase_policy_binding_retains_external_partition_without_authorization(self) -> None:
        from acceptance_core import resolve_phase_policy

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "phase"}, {"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "Game.Godot/Player.cs", "candidate_sha256": "sha256:" + "b" * 64, "inclusion_reason": "external"}]}
        binding = resolve_phase_policy(policy, candidate, {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}, "sha256:" + "c" * 64)
        self.assertIn("PhaseA.Platform/Program.cs", binding["triggeredPaths"])
        self.assertEqual(["Game.Godot/Player.cs"], binding["unreviewedExternalDomainPaths"])
        self.assertEqual([], binding["authorizes"])

    def test_phase_policy_accepts_self_hosted_control_plane_and_retains_docs_partition(self) -> None:
        from acceptance_core import resolve_phase_policy

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [
            {"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_core.py", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "self-hosted control plane"},
            {"change_type": "added", "roles": ["authority"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "docs/standards/acceptance.md", "candidate_sha256": "sha256:" + "b" * 64, "inclusion_reason": "external documentation"},
        ]}
        binding = resolve_phase_policy(policy, candidate, baseline, "sha256:" + "c" * 64)
        self.assertEqual([".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_core.py"], binding["triggeredPaths"])
        self.assertEqual(["docs/standards/acceptance.md"], binding["unreviewedExternalDomainPaths"])

    def test_cli_json_publisher_rejects_existing_output_without_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence.json"
            output.write_text('{"old":true}\n', encoding="utf-8")
            with self.assertRaisesRegex(acceptance_core.InputError, "append-only"):
                acceptance_cli._publish_new_json(str(output), {"new": True})
            self.assertEqual('{"old":true}\n', output.read_text(encoding="utf-8"))

    def test_phase_policy_ignores_unchanged_phase_entries(self) -> None:
        from acceptance_core import InputError, resolve_phase_policy

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"path": "PhaseA.Platform/Program.cs", "roles": ["implementation"], "sha256": "sha256:" + "a" * 64, "inclusion_reason": "baseline"}]}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "unchanged", "roles": ["implementation"], "baseline_path": "PhaseA.Platform/Program.cs", "baseline_sha256": "sha256:" + "a" * 64, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "retained"}, {"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "Game.Godot/Player.cs", "candidate_sha256": "sha256:" + "b" * 64, "inclusion_reason": "godot"}]}
        with self.assertRaisesRegex(InputError, "unsupported_code_review_domain"):
            resolve_phase_policy(policy, candidate, baseline, "sha256:" + "c" * 64)

    def test_phase_policy_accepts_modified_phase_candidate_with_real_baseline(self) -> None:
        from acceptance_core import resolve_phase_policy

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"path": "PhaseA.Platform/Program.cs", "roles": ["implementation"], "sha256": "sha256:" + "a" * 64, "inclusion_reason": "baseline"}]}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "modified", "roles": ["implementation"], "baseline_path": "PhaseA.Platform/Program.cs", "baseline_sha256": "sha256:" + "a" * 64, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": "sha256:" + "b" * 64, "inclusion_reason": "repair"}]}
        binding = resolve_phase_policy(policy, candidate, baseline, "sha256:" + "c" * 64)
        self.assertEqual(["PhaseA.Platform/Program.cs"], binding["triggeredPaths"])

    def test_phase_policy_includes_deleted_phase_baseline_path(self) -> None:
        from acceptance_core import resolve_phase_policy

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"path": "PhaseA.Platform/Auth.cs", "roles": ["implementation"], "sha256": "sha256:" + "a" * 64, "inclusion_reason": "baseline"}]}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "deleted", "roles": ["implementation"], "baseline_path": "PhaseA.Platform/Auth.cs", "baseline_sha256": "sha256:" + "a" * 64, "candidate_path": None, "candidate_sha256": None, "inclusion_reason": "removed"}]}
        binding = resolve_phase_policy(policy, candidate, baseline, "sha256:" + "c" * 64)
        self.assertEqual(["PhaseA.Platform/Auth.cs"], binding["triggeredPaths"])

    def test_phase_policy_includes_candidate_path_for_phase_to_non_phase_rename(self) -> None:
        from acceptance_core import resolve_phase_policy

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"path": "PhaseA.Platform/Auth.cs", "roles": ["implementation"], "sha256": "sha256:" + "a" * 64, "inclusion_reason": "baseline"}]}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "renamed", "roles": ["implementation"], "baseline_path": "PhaseA.Platform/Auth.cs", "baseline_sha256": "sha256:" + "a" * 64, "candidate_path": "docs/Auth.cs", "candidate_sha256": "sha256:" + "b" * 64, "inclusion_reason": "boundary crossing rename"}]}
        binding = resolve_phase_policy(policy, candidate, baseline, "sha256:" + "c" * 64)
        self.assertEqual(["docs/Auth.cs"], binding["triggeredPaths"])

    def test_phase_policy_includes_shared_python_llm_backend(self) -> None:
        from acceptance_core import resolve_phase_policy

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "scripts/sc/_llm_backend.py", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "shared Phase backend"}]}
        binding = resolve_phase_policy(policy, candidate, baseline, "sha256:" + "c" * 64)
        self.assertEqual(["scripts/sc/_llm_backend.py"], binding["triggeredPaths"])

    def test_phase_policy_normalizes_windows_separator_before_classification(self) -> None:
        from acceptance_core import resolve_phase_policy

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform\\Program.cs", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "Windows path"}]}
        binding = resolve_phase_policy(policy, candidate, baseline, "sha256:" + "c" * 64)
        self.assertEqual(["PhaseA.Platform/Program.cs"], binding["triggeredPaths"])

    def test_phase_policy_preserves_all_non_phase_paths_as_external_partition(self) -> None:
        from acceptance_core import resolve_phase_policy

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "Phase"}, {"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "docs\\external.md", "candidate_sha256": "sha256:" + "b" * 64, "inclusion_reason": "external"}]}
        binding = resolve_phase_policy(policy, candidate, baseline, "sha256:" + "c" * 64)
        self.assertEqual(["docs/external.md"], binding["unreviewedExternalDomainPaths"])

    def test_game_core_tests_are_classified_as_external_godot_domain(self) -> None:
        from acceptance_core import InputError, resolve_phase_policy

        policy = json.loads((SKILL_ROOT / "policies/phase-service-code-review.v1.json").read_text(encoding="utf-8"))
        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["test"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "Game.Core.Tests/KernelTests.cs", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "kernel test"}]}
        with self.assertRaisesRegex(InputError, "unsupported_code_review_domain"):
            resolve_phase_policy(policy, candidate, baseline, "sha256:" + "c" * 64)

    def test_cli_phase_policy_requires_and_consumes_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"path": "PhaseA.Platform/Program.cs", "roles": ["implementation"], "sha256": "sha256:" + "a" * 64, "inclusion_reason": "baseline"}]}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "modified", "roles": ["implementation"], "baseline_path": "PhaseA.Platform/Program.cs", "baseline_sha256": "sha256:" + "a" * 64, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": "sha256:" + "b" * 64, "inclusion_reason": "repair"}]}
            baseline_path, candidate_path = root / "baseline.json", root / "candidate.json"
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            result = acceptance_cli.resolve_phase_policy_command(str(SKILL_ROOT / "policies/phase-service-code-review.v1.json"), str(baseline_path), str(candidate_path), "sha256:" + "c" * 64)
        self.assertEqual(["PhaseA.Platform/Program.cs"], result["triggeredPaths"])

    def test_cli_exposes_phase_policy_binding_command(self) -> None:
        self.assertTrue(callable(acceptance_cli.resolve_phase_policy_command))


if __name__ == "__main__":
    unittest.main()
