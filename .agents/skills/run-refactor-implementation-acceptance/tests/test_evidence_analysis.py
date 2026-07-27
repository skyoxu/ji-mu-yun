from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class EvidenceAnalysisTests(unittest.TestCase):
    def _line_set(self, lines: list[dict]) -> dict:
        return {"schemaVersion": "phase-changed-line-set.v1", "candidateContentManifestHash": "sha256:" + "a" * 64, "lines": lines}

    def _report(self, directory: Path, hits: str) -> Path:
        report = directory / "coverage.xml"
        report.write_text(f'<coverage><packages><package><classes><class filename="PhaseA.Platform/Service.cs"><lines>{hits}</lines></class></classes></package></packages></coverage>', encoding="utf-8")
        return report

    def test_analyzer_calculates_changed_line_coverage_only(self) -> None:
        import evidence_analysis

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._report(root, '<line number="10" hits="1"/><line number="11" hits="0"/>')
            result = evidence_analysis.analyze_diff_coverage(
                acceptance_run_id="run", baseline_revision="base", candidate_revision="candidate",
                candidate_manifest_hash="sha256:" + "a" * 64,
                changed_line_set=self._line_set([
                    {"path": "PhaseA.Platform/Service.cs", "line": 10, "classification": "measurable", "exclusionReason": None},
                    {"path": "PhaseA.Platform/Service.cs", "line": 11, "classification": "measurable", "exclusionReason": None},
                    {"path": "PhaseA.Platform/Service.cs", "line": 12, "classification": "excluded", "exclusionReason": "comment_only"},
                ]),
                cobertura_path=report, source_map={"PhaseA.Platform/Service.cs": "PhaseA.Platform/Service.cs"}, test_run_evidence_id="test",
            )
        self.assertEqual("failed", result["status"])
        self.assertEqual(2, result["counts"]["measurableChangedExecutableLines"])
        self.assertEqual([], result["authorizes"])

    def test_analyzer_refuses_to_exclude_missing_coverage_source(self) -> None:
        import evidence_analysis

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._report(root, '<line number="10" hits="1"/>')
            result = evidence_analysis.analyze_diff_coverage(
                acceptance_run_id="run", baseline_revision="base", candidate_revision="candidate",
                candidate_manifest_hash="sha256:" + "a" * 64,
                changed_line_set=self._line_set([{"path": "PhaseA.Platform/Missing.cs", "line": 10, "classification": "measurable", "exclusionReason": None}]),
                cobertura_path=report, source_map={"PhaseA.Platform/Missing.cs": "PhaseA.Platform/Missing.cs"}, test_run_evidence_id="test",
            )
        self.assertEqual("incomplete", result["status"])
        self.assertEqual(["PhaseA.Platform/Missing.cs"], result["missingSourcePaths"])

    def test_changed_line_set_rejects_non_replayable_exclusion(self) -> None:
        import evidence_analysis
        from acceptance_core import InputError

        with self.assertRaisesRegex(InputError, "invalid reason"):
            evidence_analysis.validate_changed_line_set(self._line_set([
                {"path": "PhaseA.Platform/Service.cs", "line": 1, "classification": "excluded", "exclusionReason": "because"},
            ]))

    def test_cli_exposes_append_only_coverage_command(self) -> None:
        import acceptance_cli

        self.assertTrue(callable(acceptance_cli.analyze_diff_coverage_command))


if __name__ == "__main__":
    unittest.main()
