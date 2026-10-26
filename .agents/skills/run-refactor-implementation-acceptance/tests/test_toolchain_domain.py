from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from acceptance_core import (  # noqa: E402
    InputError,
    canonical_hash,
    resolve_code_review_policy,
    resolve_phase_policy,
    validate_run_input,
)


def baseline(*paths: str) -> dict:
    return {
        "schemaVersion": "acceptance-baseline-content-manifest.v1",
        "status": "complete", "coverageGaps": [], "authorizes": [],
        "files": [{"path": path, "roles": ["implementation"], "sha256": "sha256:" + "a" * 64, "inclusion_reason": "fixture"} for path in paths],
    }


def candidate(*paths: str) -> dict:
    return {
        "schemaVersion": "acceptance-candidate-content-manifest.v1",
        "status": "complete", "coverageGaps": [], "authorizes": [],
        "files": [{"change_type": "added", "roles": ["implementation"], "baseline_path": None, "baseline_sha256": None, "candidate_path": path, "candidate_sha256": "sha256:" + format(index + 1, "064x"), "inclusion_reason": "fixture"} for index, path in enumerate(paths)],
    }


class ToolchainDomainTests(unittest.TestCase):
    def policy(self) -> dict:
        return json.loads((SKILL_ROOT / "policies" / "toolchain-code-review.v1.json").read_text(encoding="utf-8"))

    def test_toolchain_policy_covers_workflows_docs_plan_and_shared_phase_entrypoint(self) -> None:
        paths = (
            ".gitignore",
            ".agents/skills/vdd-execution-plan/SKILL.md",
            "scripts/sc/workflow_model_routing.py",
            "scripts/sc/_llm_backend.py",
            "decision-logs/2026-07-21-example.md",
            "docs/PROJECT_DOCUMENTATION_INDEX.md",
            "docs/adr/ADR-0037-phase-shared-llm-codex-entrypoints.md",
            "docs/architecture/ADR_INDEX_PHASE.md",
            "execution-plans/example/00-index.md",
        )
        binding = resolve_code_review_policy(self.policy(), candidate(*paths), baseline(), "sha256:" + "b" * 64)
        self.assertEqual(sorted(paths), binding["triggeredPaths"])
        self.assertEqual([], binding["unreviewedExternalDomainPaths"])
        self.assertEqual(["scripts/sc/_llm_backend.py"], binding["crossDomainDependencyPaths"])
        self.assertEqual([], binding["authorizes"])

    def test_uncovered_path_fails_closed(self) -> None:
        with self.assertRaisesRegex(InputError, "coverage is incomplete"):
            resolve_code_review_policy(
                self.policy(), candidate("Game.Godot/Player.cs"), baseline(), "sha256:" + "b" * 64
            )

    def test_policy_revision_and_domain_identity_are_bound(self) -> None:
        policy = self.policy()
        policy["targetDomain"] = "phase_service"
        with self.assertRaisesRegex(InputError, "identity is invalid"):
            resolve_code_review_policy(policy, candidate("scripts/sc/tool.py"), baseline(), "sha256:" + "b" * 64)
        policy = self.policy()
        policy["checks"].pop()
        with self.assertRaisesRegex(InputError, "revision is stale"):
            resolve_code_review_policy(policy, candidate("scripts/sc/tool.py"), baseline(), "sha256:" + "b" * 64)

    # ADR-0053: route actual knowledge-query paths without granting write authority.
    def test_knowledge_query_exact_files_are_owned_without_external_partition(self) -> None:
        paths = (
            "scripts/toolchain/knowledge_query/adapter.py",
            "scripts/toolchain/knowledge_query/tests/test_planning_query.py",
            "scripts/vdd/compile_plan.py",
            "tests/toolchain/knowledge_query/test_planning_boundaries.py",
        )
        binding = resolve_code_review_policy(self.policy(), candidate(*paths), baseline(), "sha256:" + "b" * 64)
        self.assertEqual(sorted(paths), binding["triggeredPaths"])
        self.assertEqual([], binding["unreviewedExternalDomainPaths"])
        self.assertEqual([], binding["crossDomainDependencyPaths"])
        self.assertEqual([], binding["authorizes"])

    def test_file_rules_reject_suffixes_and_file_as_directory(self) -> None:
        exact_files = (
            ".gitignore",
            "docs/PROJECT_DOCUMENTATION_INDEX.md",
            "scripts/toolchain/knowledge_query/adapter.py",
            "scripts/toolchain/knowledge_query/tests/test_planning_query.py",
            "scripts/vdd/compile_plan.py",
            "tests/toolchain/knowledge_query/test_planning_boundaries.py",
        )
        for path in exact_files:
            for changed in (path + ".backup", path + "-other", path + "/child.py"):
                with self.subTest(changed=changed), self.assertRaisesRegex(InputError, "coverage is incomplete"):
                    resolve_code_review_policy(self.policy(), candidate(changed), baseline(), "sha256:" + "b" * 64)

    def test_knowledge_query_neighbors_remain_uncovered(self) -> None:
        for path in ("scripts/toolchain/knowledge_query/other.py", "scripts/vdd/other.py",
                     "tests/toolchain/knowledge_query/other.py", "PhaseA.Platform/Program.cs"):
            with self.subTest(path=path), self.assertRaisesRegex(InputError, "coverage is incomplete"):
                resolve_code_review_policy(self.policy(), candidate(path), baseline(), "sha256:" + "b" * 64)

    def test_policy_checks_and_evaluation_modes_are_not_weakened(self) -> None:
        self.assertEqual([
            {"policyCheckId": "TOOLCHAIN-CR-AUTH-001", "evaluationMode": "deterministic"},
            {"policyCheckId": "TOOLCHAIN-CR-SCOPE-001", "evaluationMode": "deterministic"},
            {"policyCheckId": "TOOLCHAIN-CR-COMPAT-001", "evaluationMode": "hybrid"},
            {"policyCheckId": "TOOLCHAIN-CR-TEST-001", "evaluationMode": "deterministic"},
            {"policyCheckId": "TOOLCHAIN-CR-EVIDENCE-001", "evaluationMode": "review_gate"},
        ], self.policy()["checks"])

    def test_run_input_accepts_only_phase_and_toolchain(self) -> None:
        value = {
            "target": str(SKILL_ROOT.resolve()), "run_id": "run", "created_utc": "2026-08-01T00:00:00Z",
            "change_id": "change", "baseline_revision": "base", "candidate_revision": "candidate",
            "candidate_mode": "commit", "target_plan_paths": ["00-index.md"], "execution_mode": "evidence_only",
            "baseline_content_manifest_path": "baseline.json", "baseline_content_manifest_hash": "sha256:" + "a" * 64,
            "candidate_content_manifest_path": "candidate.json", "candidate_content_manifest_hash": "sha256:" + "b" * 64,
            "code_review_domain": "toolchain", "code_review_policy_path": "policy.json", "code_review_policy_hash": "sha256:" + "c" * 64,
            "target_plan_hash": "sha256:" + "d" * 64, "validator_hash": "sha256:" + "e" * 64,
            "adapter_id": "refactor-acceptance", "adapter_version": "1", "adapter_hash": "sha256:" + "f" * 64,
            "allowed_write_roots": [], "forbidden_write_roots": [], "changed_paths": [], "affected_consumer_refs": [],
        }
        validate_run_input(value)
        value["code_review_domain"] = "marketplace"
        with self.assertRaisesRegex(InputError, "unsupported code_review_domain"):
            validate_run_input(value)

    def test_phase_entrypoint_remains_phase_only(self) -> None:
        with self.assertRaisesRegex(InputError, "requires phase_service"):
            resolve_phase_policy(self.policy(), candidate("scripts/sc/tool.py"), baseline(), "sha256:" + "b" * 64)


if __name__ == "__main__":
    unittest.main()
