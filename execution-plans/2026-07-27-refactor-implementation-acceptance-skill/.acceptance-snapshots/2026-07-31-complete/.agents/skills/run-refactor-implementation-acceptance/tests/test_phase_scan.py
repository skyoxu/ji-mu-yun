from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class PhaseScanTests(unittest.TestCase):
    def _candidate(self) -> dict:
        return {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "Phase code"}]}

    def _baseline(self) -> dict:
        return {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"path": "PhaseA.Platform/Program.cs", "roles": ["implementation"], "sha256": "sha256:" + "a" * 64, "inclusion_reason": "baseline"}]}

    def _modified_candidate(self) -> dict:
        return {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "modified", "roles": ["implementation"], "baseline_path": "PhaseA.Platform/Program.cs", "baseline_sha256": "sha256:" + "a" * 64, "candidate_path": "PhaseA.Platform/Program.cs", "candidate_sha256": "sha256:" + "b" * 64, "inclusion_reason": "repair"}]}

    def _registry(self, payload: dict) -> dict:
        command = {"id": "phase-static", "executable": sys.executable, "argv": ["-c", "import json; print(json.dumps(" + repr(payload) + "))"], "cwd": ".", "timeout_seconds": 10, "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [], "registry_hash": "", "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}}
        material = {"schemaVersion": "acceptance-command-registry.v1", "commands": [{key: value for key, value in command.items() if key != "registry_hash"}]}
        registry_hash = "sha256:" + hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        command["registry_hash"] = registry_hash
        return {"schemaVersion": "acceptance-command-registry.v1", "commands": [command], "registryHash": registry_hash}

    def _snapshot(self, root: Path, candidate: dict) -> Path:
        snapshot = root / "snapshot"
        for item in candidate["files"]:
            path = item.get("candidate_path")
            if path is None:
                continue
            target = snapshot / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("candidate:" + path, encoding="utf-8")
            item["candidate_sha256"] = "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest()
        return snapshot

    def test_scan_requires_exact_phase_read_scope(self) -> None:
        import phase_scan

        with tempfile.TemporaryDirectory() as directory:
            root, candidate = Path(directory), self._candidate()
            result = phase_scan.run_phase_scan(repository_root=root, candidate_snapshot_root=self._snapshot(root, candidate), kind="static-analysis", execution_mode="controlled_validation", baseline_manifest={"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}, candidate_manifest=candidate, command_registry=self._registry({"status": "passed", "readPaths": ["PhaseA.Platform/Program.cs"], "findings": []}), command_id="phase-static")
        self.assertEqual("passed", result["status"])
        self.assertEqual([], result["missingChangedPaths"])
        self.assertEqual([], result["authorizes"])

    def test_scan_rejects_partial_scope_and_evidence_only_execution(self) -> None:
        import phase_scan
        from acceptance_core import InputError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = self._candidate()
            snapshot = self._snapshot(root, candidate)
            result = phase_scan.run_phase_scan(repository_root=root, candidate_snapshot_root=snapshot, kind="security-scan", execution_mode="controlled_validation", baseline_manifest={"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}, candidate_manifest=candidate, command_registry=self._registry({"status": "passed", "readPaths": [], "findings": []}), command_id="phase-static")
            self.assertEqual("incomplete", result["status"])
            with self.assertRaisesRegex(InputError, "controlled_validation"):
                phase_scan.run_phase_scan(repository_root=root, candidate_snapshot_root=snapshot, kind="security-scan", execution_mode="evidence_only", baseline_manifest={"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}, candidate_manifest=candidate, command_registry=self._registry({}), command_id="phase-static")

    def test_scan_accepts_modified_phase_candidate_against_real_baseline(self) -> None:
        import phase_scan

        with tempfile.TemporaryDirectory() as directory:
            root, candidate = Path(directory), self._modified_candidate()
            result = phase_scan.run_phase_scan(repository_root=root, candidate_snapshot_root=self._snapshot(root, candidate), kind="static-analysis", execution_mode="controlled_validation", baseline_manifest=self._baseline(), candidate_manifest=candidate, command_registry=self._registry({"status": "passed", "readPaths": ["PhaseA.Platform/Program.cs"], "findings": []}), command_id="phase-static")
        self.assertEqual("passed", result["status"])

    def test_scan_includes_shared_python_llm_backend(self) -> None:
        import phase_scan

        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "scripts/sc/_llm_backend.py", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "shared Phase backend"}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = phase_scan.run_phase_scan(repository_root=root, candidate_snapshot_root=self._snapshot(root, candidate), kind="static-analysis", execution_mode="controlled_validation", baseline_manifest={"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}, candidate_manifest=candidate, command_registry=self._registry({"status": "passed", "readPaths": ["scripts/sc/_llm_backend.py"], "findings": []}), command_id="phase-static")
        self.assertEqual("passed", result["status"])

    def test_scan_uses_candidate_path_for_phase_to_non_phase_rename(self) -> None:
        import phase_scan

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"path": "PhaseA.Platform/Auth.cs", "roles": ["implementation"], "sha256": "sha256:" + "a" * 64, "inclusion_reason": "baseline"}]}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "renamed", "roles": ["implementation"], "baseline_path": "PhaseA.Platform/Auth.cs", "baseline_sha256": "sha256:" + "a" * 64, "candidate_path": "docs/Auth.cs", "candidate_sha256": "sha256:" + "b" * 64, "inclusion_reason": "boundary crossing rename"}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = phase_scan.run_phase_scan(repository_root=root, candidate_snapshot_root=self._snapshot(root, candidate), kind="security-scan", execution_mode="controlled_validation", baseline_manifest=baseline, candidate_manifest=candidate, command_registry=self._registry({"status": "passed", "readPaths": ["docs/Auth.cs"], "findings": []}), command_id="phase-static")
        self.assertEqual(["docs/Auth.cs"], result["requiredChangedPaths"])
        self.assertEqual("passed", result["status"])

    def test_cli_exposes_scan_command(self) -> None:
        import acceptance_cli

        self.assertTrue(callable(acceptance_cli.run_phase_scan_command))

    def test_scan_rejects_mutable_root_when_frozen_candidate_snapshot_drifts(self) -> None:
        import phase_scan
        from acceptance_core import InputError

        with tempfile.TemporaryDirectory() as directory:
            root, candidate = Path(directory), self._candidate()
            snapshot = self._snapshot(root, candidate)
            (snapshot / "PhaseA.Platform/Program.cs").write_text("drift", encoding="utf-8")
            with self.assertRaisesRegex(InputError, "snapshot bytes drift"):
                phase_scan.run_phase_scan(repository_root=root, candidate_snapshot_root=snapshot, kind="static-analysis", execution_mode="controlled_validation", baseline_manifest={"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}, candidate_manifest=candidate, command_registry=self._registry({}), command_id="phase-static")


if __name__ == "__main__":
    unittest.main()
