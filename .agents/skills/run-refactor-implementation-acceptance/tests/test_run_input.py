from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import acceptance_cli


class RunInputTests(unittest.TestCase):
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
            input_value = {"target": "C:/jimuyun/execution-plans/example", "run_id": "run", "created_utc": "2026-07-28T00:00:00Z", "change_id": "change", "baseline_revision": "a", "candidate_revision": "b", "candidate_mode": "commit", "target_plan_paths": ["plan"], "execution_mode": "evidence_only", "baseline_content_manifest_path": "baseline.json", "baseline_content_manifest_hash": canonical_hash(baseline), "candidate_content_manifest_path": "candidate.json", "candidate_content_manifest_hash": "sha256:" + "0" * 64, "code_review_domain": "phase_service", "code_review_policy_path": "policy.json", "code_review_policy_hash": "sha256:" + "1" * 64, "target_plan_hash": "sha256:" + "2" * 64, "validator_hash": "sha256:" + "3" * 64, "adapter_id": "adapter", "adapter_version": "1", "adapter_hash": "sha256:" + "4" * 64, "allowed_write_roots": [], "forbidden_write_roots": [], "changed_paths": [], "affected_consumer_refs": []}
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
            value = {"target": "C:/jimuyun/execution-plans/example", "run_id": "run", "created_utc": "2026-07-28T00:00:00Z", "change_id": "change", "baseline_revision": "a", "candidate_revision": "b", "candidate_mode": "commit", "target_plan_paths": ["plan"], "execution_mode": "evidence_only", "baseline_content_manifest_path": "baseline.json", "baseline_content_manifest_hash": canonical_hash(baseline), "candidate_content_manifest_path": "candidate.json", "candidate_content_manifest_hash": canonical_hash(candidate), "code_review_domain": "phase_service", "code_review_policy_path": "policy.json", "code_review_policy_hash": "sha256:" + "1" * 64, "target_plan_hash": "sha256:" + "2" * 64, "validator_hash": "sha256:" + "3" * 64, "adapter_id": "adapter", "adapter_version": "1", "adapter_hash": "sha256:" + "4" * 64, "allowed_write_roots": [], "forbidden_write_roots": [], "changed_paths": [], "affected_consumer_refs": []}
            (root / "input.json").write_text(json.dumps(value), encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(root)
                result = acceptance_cli.prepare_run("input.json", "run.json")
            finally:
                os.chdir(previous)
            self.assertEqual([], result["authorizes"])
            self.assertTrue((root / "run.json").is_file())

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

    def test_candidate_manifest_rejects_unknown_file_fields(self) -> None:
        from acceptance_core import InputError, validate_candidate_manifest

        baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": []}
        invalid = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": "a.py", "candidate_sha256": "sha256:" + "a" * 64, "inclusion_reason": "source", "untrusted": True}]}
        with self.assertRaisesRegex(InputError, "fields are invalid"):
            validate_candidate_manifest(invalid, baseline)

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
            value = {"target": "C:/jimuyun/execution-plans/example", "run_id": "run", "created_utc": "2026-07-28T00:00:00Z", "change_id": "change", "baseline_revision": "a", "candidate_revision": "b", "candidate_mode": "commit", "target_plan_paths": ["plan"], "execution_mode": "evidence_only", "baseline_content_manifest_path": "baseline.json", "baseline_content_manifest_hash": canonical_hash(baseline), "candidate_content_manifest_path": "candidate.json", "candidate_content_manifest_hash": canonical_hash(candidate), "code_review_domain": "phase_service", "code_review_policy_path": "policy.json", "code_review_policy_hash": "sha256:" + "1" * 64, "target_plan_hash": "sha256:" + "2" * 64, "validator_hash": "sha256:" + "3" * 64, "adapter_id": "adapter", "adapter_version": "1", "adapter_hash": "sha256:" + "4" * 64, "allowed_write_roots": [], "forbidden_write_roots": [], "changed_paths": ["not-in-candidate.cs"], "affected_consumer_refs": []}
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
            resolve_phase_policy(policy, candidate, "sha256:" + "b" * 64)

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
            validate_task_checklist_closure({"schemaVersion": "task-checklist-closure.v1", "items": [{"itemId": "x", "required": True, "checked": True, "matrixCheckRefs": [], "evidenceRefs": []}]})

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
        binding = resolve_phase_policy(policy, candidate, "sha256:" + "c" * 64)
        self.assertIn("PhaseA.Platform/Program.cs", binding["triggeredPaths"])
        self.assertEqual(["Game.Godot/Player.cs"], binding["unreviewedExternalDomainPaths"])
        self.assertEqual([], binding["authorizes"])

    def test_cli_exposes_phase_policy_binding_command(self) -> None:
        self.assertTrue(callable(acceptance_cli.resolve_phase_policy_command))


if __name__ == "__main__":
    unittest.main()
