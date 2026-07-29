from __future__ import annotations

import json
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
        return {"commands": [{"id": "phase-static", "executable": sys.executable, "argv": ["-c", "import json; print(json.dumps(" + repr(payload) + "))"], "cwd": ".", "timeout_seconds": 10, "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [], "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}}]}

    def test_scan_requires_exact_phase_read_scope(self) -> None:
        import phase_scan

        with tempfile.TemporaryDirectory() as directory:
            result = phase_scan.run_phase_scan(repository_root=Path(directory), kind="static-analysis", execution_mode="controlled_validation", baseline_manifest={"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}, candidate_manifest=self._candidate(), command_registry=self._registry({"status": "passed", "readPaths": ["PhaseA.Platform/Program.cs"], "findings": []}), command_id="phase-static")
        self.assertEqual("passed", result["status"])
        self.assertEqual([], result["missingChangedPaths"])
        self.assertEqual([], result["authorizes"])

    def test_scan_rejects_partial_scope_and_evidence_only_execution(self) -> None:
        import phase_scan
        from acceptance_core import InputError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = phase_scan.run_phase_scan(repository_root=root, kind="security-scan", execution_mode="controlled_validation", baseline_manifest={"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}, candidate_manifest=self._candidate(), command_registry=self._registry({"status": "passed", "readPaths": [], "findings": []}), command_id="phase-static")
            self.assertEqual("incomplete", result["status"])
            with self.assertRaisesRegex(InputError, "controlled_validation"):
                phase_scan.run_phase_scan(repository_root=root, kind="security-scan", execution_mode="evidence_only", baseline_manifest={"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}, candidate_manifest=self._candidate(), command_registry=self._registry({}), command_id="phase-static")

    def test_scan_accepts_modified_phase_candidate_against_real_baseline(self) -> None:
        import phase_scan

        with tempfile.TemporaryDirectory() as directory:
            result = phase_scan.run_phase_scan(repository_root=Path(directory), kind="static-analysis", execution_mode="controlled_validation", baseline_manifest=self._baseline(), candidate_manifest=self._modified_candidate(), command_registry=self._registry({"status": "passed", "readPaths": ["PhaseA.Platform/Program.cs"], "findings": []}), command_id="phase-static")
        self.assertEqual("passed", result["status"])

    def test_scan_includes_shared_python_llm_backend(self) -> None:
        import phase_scan

        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "scripts/sc/_llm_backend.py", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "shared Phase backend"}]}
        with tempfile.TemporaryDirectory() as directory:
            result = phase_scan.run_phase_scan(repository_root=Path(directory), kind="static-analysis", execution_mode="controlled_validation", baseline_manifest={"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}, candidate_manifest=candidate, command_registry=self._registry({"status": "passed", "readPaths": ["scripts/sc/_llm_backend.py"], "findings": []}), command_id="phase-static")
        self.assertEqual("passed", result["status"])

    def test_scan_uses_candidate_path_for_phase_to_non_phase_rename(self) -> None:
        import phase_scan

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"path": "PhaseA.Platform/Auth.cs", "roles": ["implementation"], "sha256": "sha256:" + "a" * 64, "inclusion_reason": "baseline"}]}
        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "renamed", "roles": ["implementation"], "baseline_path": "PhaseA.Platform/Auth.cs", "baseline_sha256": "sha256:" + "a" * 64, "candidate_path": "docs/Auth.cs", "candidate_sha256": "sha256:" + "b" * 64, "inclusion_reason": "boundary crossing rename"}]}
        with tempfile.TemporaryDirectory() as directory:
            result = phase_scan.run_phase_scan(repository_root=Path(directory), kind="security-scan", execution_mode="controlled_validation", baseline_manifest=baseline, candidate_manifest=candidate, command_registry=self._registry({"status": "passed", "readPaths": ["docs/Auth.cs"], "findings": []}), command_id="phase-static")
        self.assertEqual(["docs/Auth.cs"], result["requiredChangedPaths"])
        self.assertEqual("passed", result["status"])

    def test_cli_exposes_scan_command(self) -> None:
        import acceptance_cli

        self.assertTrue(callable(acceptance_cli.run_phase_scan_command))


if __name__ == "__main__":
    unittest.main()
