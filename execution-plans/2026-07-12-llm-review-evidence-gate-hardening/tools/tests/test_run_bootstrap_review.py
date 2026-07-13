from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "run_bootstrap_review.py"
SPEC = importlib.util.spec_from_file_location("run_bootstrap_review", MODULE_PATH)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


class BootstrapReviewCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.scope = self.repo / "upstream-plan"
        self.scope.mkdir(parents=True)
        self.target = self.scope / "plan.md"
        self.target.write_text("# Plan\n\nUnsafe authority rule.\n", encoding="utf-8", newline="\n")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "bootstrap@example.invalid"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Bootstrap Test"], cwd=self.repo, check=True)
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=self.repo, check=True)
        self.run_dir = self.repo / "bootstrap-run"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def read_json(self, relative: str) -> dict:
        return json.loads((self.run_dir / relative).read_text(encoding="utf-8"))

    def write_json(self, relative: str, value: dict) -> None:
        (self.run_dir / relative).write_text(
            json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

    def prepare(self) -> None:
        result = bootstrap.main(
            [
                "prepare",
                "--repository-root", str(self.repo),
                "--review-id", "upstream-manual-001",
                "--profile", "bootstrap-upstream-plan",
                "--scope", str(self.scope),
                "--out-dir", str(self.run_dir),
            ]
        )
        self.assertEqual(0, result)

    def complete_layers(self, candidates_by_layer: dict[str, list[dict]] | None = None) -> None:
        candidates_by_layer = candidates_by_layer or {}
        for layer in bootstrap.LAYERS:
            output = self.read_json(f"reviewer-outputs/{layer}.json")
            output["status"] = "completed"
            output["coverage"]["readArtifacts"] = output["coverage"]["requiredArtifacts"]
            output["coverage"]["missingArtifacts"] = []
            output["candidates"] = candidates_by_layer.get(layer, [])
            self.write_json(f"reviewer-outputs/{layer}.json", output)

    def candidate(self, candidate_id: str = "BOOT-CANDIDATE-001", severity: str = "P1") -> dict:
        manifest = self.read_json("review-input.json")
        artifact = manifest["artifacts"][0]
        return {
            "candidateId": candidate_id,
            "artifactKind": "plan",
            "artifact": artifact["artifact"],
            "artifactHash": artifact["sha256"],
            "startLine": 3,
            "endLine": 3,
            "exactEvidence": "Unsafe authority rule.",
            "triggerInput": "An implementer follows the plan",
            "requiredState": "The quoted rule is treated as authority",
            "badOutcome": "The implementer mutates the wrong owner",
            "contextRead": ["upstream-plan/plan.md:1"],
            "existingGuardAnalysis": "No validator checks this authority assignment",
            "proposedSeverity": severity,
            "severityRationale": "The reachable workflow executes the wrong required work",
            "confidence": 0.95,
            "dimension": "plan",
            "authorityOwner": "upstream plan",
            "consumer": "implementation operator",
            "validatorRef": "manual phase exit",
        }

    def test_prepare_creates_hash_bound_manual_materials_without_mutating_scope(self) -> None:
        before = self.target.read_bytes()
        self.prepare()
        self.assertEqual(before, self.target.read_bytes())
        manifest = self.read_json("review-input.json")
        self.assertEqual("bootstrap-review-input.v1", manifest["schemaVersion"])
        self.assertEqual("supplemental_bootstrap", manifest["authorityClass"])
        self.assertEqual(list(bootstrap.LAYERS), manifest["requiredLayers"])
        for layer in bootstrap.LAYERS:
            self.assertTrue((self.run_dir / "reviewer-prompts" / f"{layer}.md").is_file())
            output = self.read_json(f"reviewer-outputs/{layer}.json")
            self.assertEqual("pending", output["status"])
            self.assertEqual(
                [item["artifact"] for item in manifest["artifacts"]],
                output["coverage"]["requiredArtifacts"],
            )
            self.assertEqual([], output["coverage"]["readArtifacts"])
            self.assertEqual(output["coverage"]["requiredArtifacts"], output["coverage"]["missingArtifacts"])
            prompt = (self.run_dir / "reviewer-prompts" / f"{layer}.md").read_text(encoding="utf-8")
            self.assertIn("There is no minimum finding quota", prompt)
            self.assertIn("completed` requires every required artifact to be read", prompt)
            self.assertIn("Each candidate object must contain exactly these fields", prompt)
            self.assertIn("`candidateId`, `artifactKind`, `artifact`, `artifactHash`", prompt)
            self.assertIn("`path:start-end`", prompt)
            self.assertIn("Do not add any other candidate fields", prompt)

    def test_prepare_records_binary_artifacts_without_decoding_them(self) -> None:
        binary = self.scope / "sample.bin"
        binary.write_bytes(b"\xff\xfe\x00\x01")
        self.prepare()
        artifacts = {item["artifact"]: item for item in self.read_json("review-input.json")["artifacts"]}
        entry = artifacts["upstream-plan/sample.bin"]
        self.assertIsNone(entry["textEncoding"])
        self.assertIsNone(entry["lineCount"])

    def test_prepare_rejects_unsafe_review_id(self) -> None:
        result = bootstrap.main(
            [
                "prepare", "--repository-root", str(self.repo), "--review-id", "../bad",
                "--profile", "bootstrap-upstream-plan", "--scope", str(self.scope),
                "--out-dir", str(self.run_dir),
            ]
        )
        self.assertEqual(1, result)
        self.assertFalse(self.run_dir.exists())

    def test_machine_contract_files_are_valid_json(self) -> None:
        plan_root = MODULE_PATH.parents[1]
        for relative in (
            "schemas/bootstrap-reviewer-output.v1.schema.json",
            "schemas/bootstrap-verifier-output.v1.schema.json",
            "bootstrap/review-profiles.v1.json",
        ):
            value = json.loads((plan_root / relative).read_text(encoding="utf-8"))
            self.assertIsInstance(value, dict)

    def test_prepare_rejects_scope_outside_repository_before_writing(self) -> None:
        outside = Path(self.temp.name) / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        result = bootstrap.main(
            [
                "prepare", "--repository-root", str(self.repo), "--review-id", "bad",
                "--profile", "bootstrap-upstream-plan", "--scope", str(outside),
                "--out-dir", str(self.run_dir),
            ]
        )
        self.assertEqual(1, result)
        self.assertFalse(self.run_dir.exists())

    def test_gate_allows_zero_findings_only_when_all_layers_complete(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual("clean", self.read_json("review-gate-result.json")["status"])
        self.assertEqual([], self.read_json("review-candidates.json")["findings"])

    def test_gate_missing_required_layer_is_incomplete(self) -> None:
        self.prepare()
        self.complete_layers()
        output = self.read_json("reviewer-outputs/acceptance_auditor.json")
        output["status"] = "pending"
        self.write_json("reviewer-outputs/acceptance_auditor.json", output)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("incomplete", gate["status"])
        self.assertEqual(["acceptance_auditor"], gate["failedLayers"])

    def test_gate_rejects_completed_layer_with_incomplete_coverage(self) -> None:
        self.prepare()
        self.complete_layers()
        output = self.read_json("reviewer-outputs/acceptance_auditor.json")
        output["coverage"]["readArtifacts"] = []
        output["coverage"]["missingArtifacts"] = output["coverage"]["requiredArtifacts"]
        self.write_json("reviewer-outputs/acceptance_auditor.json", output)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("incomplete", gate["status"])
        self.assertEqual(["acceptance_auditor"], gate["failedLayers"])
        self.assertIn("coverage_invalid", gate["layerFailures"][0]["reason"])

    def test_gate_maps_failed_missing_context_layer_to_incomplete(self) -> None:
        self.prepare()
        self.complete_layers()
        output = self.read_json("reviewer-outputs/acceptance_auditor.json")
        output["status"] = "failed"
        output["failureReason"] = "Required acceptance authority is absent from the prepared manifest"
        output["candidates"] = []
        self.write_json("reviewer-outputs/acceptance_auditor.json", output)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("incomplete", gate["status"])
        self.assertEqual(["acceptance_auditor"], gate["failedLayers"])
        self.assertIn("Required acceptance authority", gate["layerFailures"][0]["reason"])

    def test_gate_rejects_stale_or_wrong_exact_evidence(self) -> None:
        self.prepare()
        candidate = self.candidate()
        candidate["exactEvidence"] = "A line that is not present."
        self.complete_layers({"blind_hunter": [candidate]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        rejection = self.read_json("review-rejections.json")["rejections"][0]
        self.assertEqual("stale_evidence", rejection["reasonCode"])
        self.assertEqual("clean", self.read_json("review-gate-result.json")["status"])

    def test_gate_rejects_context_outside_prepared_scope(self) -> None:
        self.prepare()
        candidate = self.candidate()
        candidate["contextRead"] = ["README.md:1"]
        self.complete_layers({"blind_hunter": [candidate]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        rejection = self.read_json("review-rejections.json")["rejections"][0]
        self.assertEqual("missing_context", rejection["reasonCode"])

    def test_gate_applies_reviewer_json_schema(self) -> None:
        self.prepare()
        self.complete_layers()
        output = self.read_json("reviewer-outputs/blind_hunter.json")
        output["unexpected"] = True
        self.write_json("reviewer-outputs/blind_hunter.json", output)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("incomplete", gate["status"])
        self.assertIn("schema_invalid", gate["layerFailures"][0]["reason"])

    def test_gate_fails_closed_when_prepared_scope_changes(self) -> None:
        self.prepare()
        self.complete_layers()
        self.target.write_text("# Plan\n\nChanged after prepare.\n", encoding="utf-8", newline="\n")
        self.assertEqual(1, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertFalse((self.run_dir / "review-gate-result.json").exists())

    def test_gate_deduplicates_same_evidence_and_preserves_sources(self) -> None:
        self.prepare()
        first = self.candidate("BOOT-CANDIDATE-001")
        second = self.candidate("BOOT-CANDIDATE-002")
        self.complete_layers({"blind_hunter": [first], "edge_case_hunter": [second]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        findings = self.read_json("review-candidates.json")["findings"]
        self.assertEqual(1, len(findings))
        self.assertEqual(["blind_hunter", "edge_case_hunter"], findings[0]["sourceReviewers"])
        self.assertEqual("duplicate", self.read_json("review-rejections.json")["rejections"][0]["reasonCode"])
        self.assertEqual("awaiting_verification", self.read_json("review-gate-result.json")["status"])

    def test_finalize_rejects_changed_gate_sidecars(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        candidates = self.read_json("review-candidates.json")
        candidates["findings"].append({"findingId": "INJECTED"})
        self.write_json("review-candidates.json", candidates)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))

    def test_finalize_rejects_reviewer_output_changed_after_gate(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        output = self.read_json("reviewer-outputs/blind_hunter.json")
        output["candidates"] = [self.candidate()]
        self.write_json("reviewer-outputs/blind_hunter.json", output)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))

    def test_finalize_requires_exact_blocker_decisions_and_writes_sidecars(self) -> None:
        self.prepare()
        self.complete_layers({"blind_hunter": [self.candidate()]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        finding_id = self.read_json("review-candidates.json")["findings"][0]["findingId"]
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [
            {
                "findingId": finding_id,
                "decision": "confirmed",
                "reason": "The exact evidence and authority path reproduce the failure",
                "evidenceChecked": ["upstream-plan/plan.md:3"],
            }
        ]
        self.write_json("verifier-output.json", verifier)
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        self.assertEqual("blocked", self.read_json("review-gate-result.json")["status"])
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        self.assertEqual(
            "supplemental_bootstrap",
            self.read_json("review-dispositions.json")["authorityClass"],
        )
        self.assertTrue((self.run_dir / "review-dispositions.json").is_file())
        self.assertTrue((self.run_dir / "review-metrics.json").is_file())
        self.assertTrue((self.run_dir / "review-report.md").is_file())

    def test_finalize_clean_run_accepts_empty_verifier_decisions(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        self.assertEqual("clean", self.read_json("review-gate-result.json")["status"])
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))

    def test_finalize_rejects_verifier_evidence_outside_scope(self) -> None:
        self.prepare()
        self.complete_layers({"blind_hunter": [self.candidate()]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        finding_id = self.read_json("review-candidates.json")["findings"][0]["findingId"]
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [
            {
                "findingId": finding_id,
                "decision": "confirmed",
                "reason": "Unsupported external evidence",
                "evidenceChecked": ["README.md:1"],
            }
        ]
        self.write_json("verifier-output.json", verifier)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))


if __name__ == "__main__":
    unittest.main()
