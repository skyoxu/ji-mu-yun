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

    def _registry(self, payload: dict) -> dict:
        return {"commands": [{"id": "phase-static", "executable": sys.executable, "argv": ["-c", "import json; print(json.dumps(" + repr(payload) + "))"], "cwd": ".", "timeout_seconds": 10, "shell": False}]}

    def test_scan_requires_exact_phase_read_scope(self) -> None:
        import phase_scan

        with tempfile.TemporaryDirectory() as directory:
            result = phase_scan.run_phase_scan(repository_root=Path(directory), kind="static-analysis", execution_mode="controlled_validation", candidate_manifest=self._candidate(), command_registry=self._registry({"status": "passed", "readPaths": ["PhaseA.Platform/Program.cs"], "findings": []}), command_id="phase-static")
        self.assertEqual("passed", result["status"])
        self.assertEqual([], result["missingChangedPaths"])
        self.assertEqual([], result["authorizes"])

    def test_scan_rejects_partial_scope_and_evidence_only_execution(self) -> None:
        import phase_scan
        from acceptance_core import InputError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = phase_scan.run_phase_scan(repository_root=root, kind="security-scan", execution_mode="controlled_validation", candidate_manifest=self._candidate(), command_registry=self._registry({"status": "passed", "readPaths": [], "findings": []}), command_id="phase-static")
            self.assertEqual("incomplete", result["status"])
            with self.assertRaisesRegex(InputError, "controlled_validation"):
                phase_scan.run_phase_scan(repository_root=root, kind="security-scan", execution_mode="evidence_only", candidate_manifest=self._candidate(), command_registry=self._registry({}), command_id="phase-static")

    def test_cli_exposes_scan_command(self) -> None:
        import acceptance_cli

        self.assertTrue(callable(acceptance_cli.run_phase_scan_command))


if __name__ == "__main__":
    unittest.main()
