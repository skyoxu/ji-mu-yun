from __future__ import annotations

import unittest
import sys
import json
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from review_requirement import decide_review_requirement


POLICY = {
    "schemaVersion": "acceptance-semantic-review-trigger-policy.v1",
    "workflowControlPlanePrefixes": [".agents/skills/", "scripts/sc/"],
    "protectedHighRiskPrefixes": ["runtime/phase-a/"],
    "typedRiskPrefixes": {
        "public_api_contract_changed": ["PhaseA.Platform/Program.cs"],
        "database_schema_or_migration_changed": ["PhaseA.Platform/Data/"],
        "runtime_or_deployment_boundary_changed": ["runtime/phase-a/"],
        "shared_execution_entrypoint_changed": ["scripts/sc/_llm_backend.py"],
    },
    "knownLowRiskPrefixes": ["docs/", "execution-plans/", "decision-logs/", "README.md", "AGENTS.md"],
    "hardTriggers": [
        "workflow_control_plane_changed",
        "protected_high_risk_boundary_changed",
        "public_api_contract_changed",
        "database_schema_or_migration_changed",
        "runtime_or_deployment_boundary_changed",
        "shared_execution_entrypoint_changed",
        "explicit_maintainer_review_request",
        "deterministic_evidence_incomplete",
        "risk_classification_unknown",
    ],
    "authorizes": [],
}


class ReviewRequirementTests(unittest.TestCase):
    def test_cli_rejects_caller_authored_current_decision(self) -> None:
        import acceptance_cli

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = root / "request.json"
            request.write_text(json.dumps({"requirement": "not_required", "requirementSources": ["caller"], "authorizes": []}), encoding="utf-8")
            with self.assertRaisesRegex(acceptance_cli.InputError, "repository-bound"):
                acceptance_cli.decide_bootstrap_command(str(request), str(root / "out.json"))

    def test_cli_replays_candidate_identity_before_deciding(self) -> None:
        import acceptance_cli

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy_path = root / ".agents/skills/run-refactor-implementation-acceptance/policies/semantic-review-trigger-policy.v1.json"
            policy_path.parent.mkdir(parents=True)
            policy_path.write_text(json.dumps({
                "schemaVersion": "acceptance-semantic-review-trigger-policy.v1",
                "workflowControlPlanePrefixes": [".agents/skills/"],
                "protectedHighRiskPrefixes": ["runtime/phase-a/"],
                "typedRiskPrefixes": POLICY["typedRiskPrefixes"],
                "knownLowRiskPrefixes": POLICY["knownLowRiskPrefixes"],
                "hardTriggers": list(POLICY["hardTriggers"]),
                "authorizes": [],
            }), encoding="utf-8")
            evidence = root / "evidence.json"
            evidence.write_text(json.dumps({"status": "passed", "authorizes": []}), encoding="utf-8")
            evidence_hash = "sha256:" + __import__("hashlib").sha256(evidence.read_bytes()).hexdigest()
            request = root / "request.json"
            request.write_text(json.dumps({
                "repository_root": str(root),
                "prepared_run_input": "prepared.json",
                "deterministic_evidence": {"path": "evidence.json", "sha256": evidence_hash},
                "maintainer_intent": "default",
            }), encoding="utf-8")
            with mock.patch.object(acceptance_cli, "load_current_candidate_identity", return_value={
                "changedPaths": [".agents/skills/run-phase-bootstrap-review/SKILL.md"],
                "knowledgeArtifacts": [],
            }):
                decision = acceptance_cli.decide_bootstrap_command(str(request), str(root / "out.json"))
            self.assertIsNone(decision["profile"])

    def test_real_candidate_manifest_preserves_repository_paths_for_skill_route_decision(self) -> None:
        import acceptance_cli

        from test_run_input import _git, _run_input, _sha256, _write_prepare_inputs

        # ADR-0058: preserve the real Git custody/path test without depending on
        # an old remote commit that may be absent from a shallow/local checkout.
        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory).resolve()
            _git(repository_root, "init", "--quiet")
            _git(repository_root, "config", "core.autocrlf", "false")
            _git(repository_root, "config", "user.email", "acceptance@example.invalid")
            _git(repository_root, "config", "user.name", "Acceptance Test")
            _git(repository_root, "commit", "--allow-empty", "-qm", "baseline")
            baseline_revision = _git(repository_root, "rev-parse", "HEAD")
            source_relative = ".agents/skills/quick-dev-tdd-adapter/SKILL.md"
            source = repository_root / source_relative
            source.parent.mkdir(parents=True)
            payload = b"# Quick Dev fixture\n"
            source.write_bytes(payload)
            _git(repository_root, "add", source_relative)
            _git(repository_root, "commit", "-qm", "candidate")
            candidate_revision = _git(repository_root, "rev-parse", "HEAD")
            baseline = {"schemaVersion": "acceptance-baseline-content-manifest.v1",
                        "status": "complete", "coverageGaps": [], "files": [], "authorizes": []}
            candidate = {"schemaVersion": "acceptance-candidate-content-manifest.v1",
                         "status": "complete", "coverageGaps": [], "authorizes": [],
                         "files": [{"change_type": "added", "roles": ["implementation"],
                                    "baseline_path": None, "baseline_sha256": None,
                                    "candidate_path": source_relative, "candidate_sha256": _sha256(payload),
                                    "inclusion_reason": "candidate commit"}]}
            target = repository_root / "execution-plans/2026-08-01-workflow-model-routing-control-plane"
            run_input = _run_input(target, baseline, candidate,
                                   baseline_revision=baseline_revision, candidate_revision=candidate_revision)
            _write_prepare_inputs(target, baseline, candidate, run_input)
            knowledge_path = target / "knowledge.json"
            knowledge_path.write_bytes(b"{}\n")
            context = {"path": "knowledge.json", "sha256": _sha256(knowledge_path.read_bytes()),
                       "acceptedDecisions": []}
            prepared_path = target / "prepared.json"
            # Catalog freshness is independent of repository-relative path identity.
            # Git bytes, manifest validation and the identity producer remain real.
            with mock.patch.object(acceptance_cli, "freeze_knowledge_context", return_value=context):
                acceptance_cli.prepare_run(str(target / "input.json"), str(prepared_path), "knowledge.json")
                identity = acceptance_cli.load_current_candidate_identity(
                    repository_root, prepared_path.relative_to(repository_root).as_posix())
            policy = POLICY

        from review_requirement import decide_review_requirement

        decision = decide_review_requirement({
            "candidateIdentity": identity,
            "deterministicEvidence": {"status": "passed"},
            "policy": policy,
        })
        self.assertIn(
            ".agents/skills/quick-dev-tdd-adapter/SKILL.md",
            identity["changedPaths"],
        )
        self.assertNotIn(
            "execution-plans/2026-08-01-workflow-model-routing-control-plane/"
            ".agents/skills/quick-dev-tdd-adapter/SKILL.md",
            identity["changedPaths"],
        )
        self.assertEqual("not_required", decision["requirement"])
        self.assertIsNone(decision["profile"])
        self.assertIn("workflow_control_plane_changed", decision["reasonCodes"])

    def test_prepare_route_rejects_handwritten_decision_when_replay_differs(self) -> None:
        import acceptance_cli

        decision = decide_review_requirement({
            "candidateIdentity": {"changedPaths": ["docs/ordinary-note.md"], "knowledgeArtifacts": []},
            "deterministicEvidence": {"status": "passed"},
            "policy": POLICY,
        })
        request = {
            "decision": decision,
            "decision_request": {"repository_root": ".", "prepared_run_input": "prepared.json", "deterministic_evidence": {"path": "evidence.json", "sha256": "sha256:" + "a" * 64}, "maintainer_intent": "default"},
            "binding": None,
            "launch_authorization": None,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            with mock.patch.object(acceptance_cli, "_derive_current_bootstrap_decision", return_value=dict(decision, requirement="required")):
                with self.assertRaisesRegex(acceptance_cli.InputError, "does not replay"):
                    acceptance_cli.prepare_bootstrap_command(str(path), str(Path(directory) / "out.json"))
    def test_caller_authored_semantic_facts_are_not_accepted(self) -> None:
        with self.assertRaisesRegex(ValueError, "repository-bound"):
            decide_review_requirement({
                "candidate": {
                    "changedPaths": [".agents/skills/run-phase-bootstrap-review/SKILL.md"],
                    "workflowControlPlaneChange": False,
                },
                "deterministicEvidence": {"status": "passed"},
                "protectedFacts": {"highRiskBoundary": False},
            })

    def test_incomplete_deterministic_evidence_is_blocked(self) -> None:
        decision = decide_review_requirement({
            "candidateIdentity": {
                "changedPaths": ["docs/ordinary-note.md"],
                "knowledgeArtifacts": [],
            },
            "deterministicEvidence": {"status": "incomplete", "hash": "sha256:" + "b" * 64},
            "policy": POLICY,
        })
        self.assertEqual("blocked", decision["decisionStatus"])
        self.assertIsNone(decision["requirement"])

    def test_unknown_trigger_policy_fails_closed(self) -> None:
        policy = dict(POLICY, hardTriggers=["caller_defined_trigger"])
        with self.assertRaisesRegex(ValueError, "policy enum"):
            decide_review_requirement({
                "candidateIdentity": {"changedPaths": ["docs/ordinary-note.md"], "knowledgeArtifacts": []},
                "deterministicEvidence": {"status": "passed"},
                "policy": policy,
            })

    def test_workflow_paths_do_not_implicitly_select_skill_route(self) -> None:
        decision = decide_review_requirement({
            "candidateIdentity": {
                "changedPaths": [".agents/skills/run-phase-bootstrap-review/SKILL.md"],
                "knowledgeArtifacts": [],
            },
            "deterministicEvidence": {"status": "passed", "hash": "sha256:" + "b" * 64},
            "policy": POLICY,
        })
        self.assertEqual("not_required", decision["requirement"])
        self.assertIsNone(decision["profile"])

    def test_execution_plan_metadata_is_known_low_risk(self) -> None:
        decision = decide_review_requirement({
            "candidateIdentity": {
                "changedPaths": ["execution-plans/example/95-report.md"],
                "knowledgeArtifacts": [],
            },
            "deterministicEvidence": {"status": "passed"},
            "policy": POLICY,
        })
        self.assertEqual("ready", decision["decisionStatus"])
        self.assertEqual("not_required", decision["requirement"])

    def test_repository_authority_paths_do_not_implicitly_require_review(self) -> None:
        policy = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "policies/semantic-review-trigger-policy.v1.json"
            ).read_text(encoding="utf-8")
        )
        for path in (
            "AGENTS.md",
            "docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md",
            "docs/standards/bootstrap-review-control-plane.md",
        ):
            decision = decide_review_requirement({
                "candidateIdentity": {"changedPaths": [path], "knowledgeArtifacts": []},
                "deterministicEvidence": {"status": "passed"},
                "policy": policy,
            })
            self.assertEqual("not_required", decision["requirement"])
            self.assertIn(
                "protected_high_risk_boundary_changed", decision["reasonCodes"]
            )

    def test_typed_public_api_boundary_does_not_implicitly_require_bootstrap(self) -> None:
        decision = decide_review_requirement({
            "candidateIdentity": {
                "changedPaths": ["PhaseA.Platform/Program.cs"],
                "knowledgeArtifacts": [],
            },
            "deterministicEvidence": {"status": "passed"},
            "policy": POLICY,
        })
        self.assertEqual("not_required", decision["requirement"])
        self.assertIsNone(decision["profile"])
        self.assertIn("public_api_contract_changed", decision["reasonCodes"])

    def test_broh_s4_acceptance_owns_review_requirement(self) -> None:
        required = decide_review_requirement({
            "candidateIdentity": {
                "changedPaths": [".agents/skills/run-phase-bootstrap-review/SKILL.md"],
                "knowledgeArtifacts": [],
            },
            "deterministicEvidence": {"status": "passed", "hash": "sha256:" + "b" * 64},
            "policy": POLICY,
            "maintainerIntent": "default",
        })
        self.assertEqual(required["requirement"], "not_required")
        self.assertIn("workflow_control_plane_changed", required["reasonCodes"])
        self.assertIsNone(required["profile"])
        self.assertEqual(required["decisionVersion"], "v11")
        self.assertRegex(required["decisionHash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(required["authorizes"], [])

        low_risk = decide_review_requirement({
            "candidateIdentity": {
                "changedPaths": ["docs/ordinary-note.md"],
                "knowledgeArtifacts": [],
            },
            "deterministicEvidence": {"status": "passed", "hash": "sha256:" + "d" * 64},
            "policy": POLICY,
            "maintainerIntent": "default",
        })
        self.assertEqual(low_risk["requirement"], "not_required")
        self.assertIn("deterministic_low_risk", low_risk["reasonCodes"])
        self.assertRegex(low_risk["decisionHash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(low_risk["authorizes"], [])

        near_miss = decide_review_requirement({
            "candidateIdentity": {
                "changedPaths": ["README.md.bak"],
                "knowledgeArtifacts": [],
            },
            "deterministicEvidence": {"status": "passed", "hash": "sha256:" + "e" * 64},
            "policy": POLICY,
            "maintainerIntent": "default",
        })
        self.assertEqual("blocked", near_miss["decisionStatus"])
        self.assertIsNone(near_miss["requirement"])
        self.assertIn("risk_classification_unknown", near_miss["reasonCodes"])


if __name__ == "__main__":
    unittest.main()

