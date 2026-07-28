from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class EvidenceAnalysisTests(unittest.TestCase):
    def _candidate(self, paths: list[str]) -> dict:
        return {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": path, "candidate_sha256": "sha256:" + chr(97 + index) * 64, "inclusion_reason": "test"} for index, path in enumerate(paths)]}

    def _line_set(self, lines: list[dict], candidate_hash: str = "sha256:" + "a" * 64) -> dict:
        return {"schemaVersion": "phase-changed-line-set.v1", "candidateContentManifestHash": candidate_hash, "phaseChangedSourcePaths": sorted({line["path"] for line in lines}), "lines": lines}

    def _report(self, directory: Path, hits: str) -> Path:
        report = directory / "coverage.xml"
        report.write_text(f'<coverage><packages><package><classes><class filename="PhaseA.Platform/Service.cs"><lines>{hits}</lines></class></classes></package></packages></coverage>', encoding="utf-8")
        return report

    def test_analyzer_calculates_changed_line_coverage_only(self) -> None:
        import evidence_analysis
        from acceptance_core import canonical_hash

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._report(root, '<line number="10" hits="1"/><line number="11" hits="0"/>')
            candidate = self._candidate(["PhaseA.Platform/Service.cs"])
            result = evidence_analysis.analyze_diff_coverage(
                acceptance_run_id="run", baseline_revision="base", candidate_revision="candidate",
                candidate_manifest_hash=canonical_hash(candidate), candidate_manifest=candidate,
                changed_line_set=self._line_set([
                    {"path": "PhaseA.Platform/Service.cs", "line": 10, "classification": "measurable", "exclusionReason": None},
                    {"path": "PhaseA.Platform/Service.cs", "line": 11, "classification": "measurable", "exclusionReason": None},
                    {"path": "PhaseA.Platform/Service.cs", "line": 12, "classification": "excluded", "exclusionReason": "comment_only"},
                ], canonical_hash(candidate)),
                cobertura_path=report, source_map={"PhaseA.Platform/Service.cs": "PhaseA.Platform/Service.cs"}, test_run_evidence_id="test",
            )
        self.assertEqual("failed", result["status"])
        self.assertEqual(2, result["counts"]["measurableChangedExecutableLines"])
        self.assertEqual([], result["authorizes"])

    def test_analyzer_refuses_to_exclude_missing_coverage_source(self) -> None:
        import evidence_analysis
        from acceptance_core import canonical_hash

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._report(root, '<line number="10" hits="1"/>')
            candidate = self._candidate(["PhaseA.Platform/Missing.cs"])
            result = evidence_analysis.analyze_diff_coverage(
                acceptance_run_id="run", baseline_revision="base", candidate_revision="candidate",
                candidate_manifest_hash=canonical_hash(candidate), candidate_manifest=candidate,
                changed_line_set=self._line_set([{"path": "PhaseA.Platform/Missing.cs", "line": 10, "classification": "measurable", "exclusionReason": None}], canonical_hash(candidate)),
                cobertura_path=report, source_map={"PhaseA.Platform/Missing.cs": "PhaseA.Platform/Missing.cs"}, test_run_evidence_id="test",
            )
        self.assertEqual("incomplete", result["status"])
        self.assertEqual(["PhaseA.Platform/Missing.cs"], result["missingSourcePaths"])

    def test_changed_line_set_rejects_non_replayable_exclusion(self) -> None:
        import evidence_analysis
        from acceptance_core import InputError, canonical_hash

        with self.assertRaisesRegex(InputError, "invalid reason"):
            evidence_analysis.validate_changed_line_set(self._line_set([
                {"path": "PhaseA.Platform/Service.cs", "line": 1, "classification": "excluded", "exclusionReason": "because"},
            ]))

    def test_phase_candidate_cannot_use_empty_changed_line_set(self) -> None:
        import evidence_analysis
        from acceptance_core import InputError, canonical_hash

        with self.assertRaisesRegex(InputError, "cannot be empty"):
            evidence_analysis.validate_changed_line_set({"schemaVersion": "phase-changed-line-set.v1", "candidateContentManifestHash": "sha256:" + "a" * 64, "lines": [], "phaseChangedSourcePaths": ["PhaseA.Platform/Service.cs"]})

    def test_changed_line_set_requires_a_line_for_each_declared_phase_source(self) -> None:
        import evidence_analysis
        from acceptance_core import InputError

        value = self._line_set([{"path": "PhaseA.Platform/Service.cs", "line": 4, "classification": "measurable", "exclusionReason": None}])
        value["phaseChangedSourcePaths"] = ["PhaseA.Platform/Other.cs", "PhaseA.Platform/Service.cs"]
        with self.assertRaisesRegex(InputError, "does not cover"):
            evidence_analysis.validate_changed_line_set(value)

    def test_coverage_requires_changed_line_set_to_match_candidate_phase_sources(self) -> None:
        import evidence_analysis
        from acceptance_core import InputError, canonical_hash

        candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [
            {"change_type": "modified", "roles": ["implementation"], "baseline_path": "PhaseA.Platform/Auth.cs", "baseline_sha256": "sha256:" + "a" * 64, "candidate_path": "PhaseA.Platform/Auth.cs", "candidate_sha256": "sha256:" + "b" * 64, "inclusion_reason": "repair"},
            {"change_type": "modified", "roles": ["implementation"], "baseline_path": "PhaseA.Platform/Service.cs", "baseline_sha256": "sha256:" + "c" * 64, "candidate_path": "PhaseA.Platform/Service.cs", "candidate_sha256": "sha256:" + "d" * 64, "inclusion_reason": "repair"},
        ]}
        line_set = self._line_set([{"path": "PhaseA.Platform/Service.cs", "line": 4, "classification": "measurable", "exclusionReason": None}], canonical_hash(candidate))
        with tempfile.TemporaryDirectory() as directory:
            report = self._report(Path(directory), "<line number='4' hits='1'/>")
            with self.assertRaisesRegex(InputError, "candidate Phase paths"):
                evidence_analysis.analyze_diff_coverage(acceptance_run_id="run", baseline_revision="a", candidate_revision="b", candidate_manifest_hash=line_set["candidateContentManifestHash"], candidate_manifest=candidate, changed_line_set=line_set, cobertura_path=report, source_map={"PhaseA.Platform/Service.cs": "Service.cs"}, test_run_evidence_id="test")

    def test_cli_exposes_append_only_coverage_command(self) -> None:
        import acceptance_cli

        self.assertTrue(callable(acceptance_cli.analyze_diff_coverage_command))


if __name__ == "__main__":
    unittest.main()
