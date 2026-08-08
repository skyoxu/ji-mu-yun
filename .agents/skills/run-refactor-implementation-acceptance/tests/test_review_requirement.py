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
    "workflowControlPlanePrefixes": [".agents/skills/", "execution-plans/"],
    "protectedHighRiskPrefixes": ["runtime/phase-a/"],
    "hardTriggers": [
        "workflow_control_plane_changed",
        "protected_high_risk_boundary_changed",
        "explicit_maintainer_review_request",
        "deterministic_evidence_incomplete",
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
            self.assertEqual("bootstrap-skill-route", decision["profile"])

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

    def test_workflow_paths_select_skill_route(self) -> None:
        decision = decide_review_requirement({
            "candidateIdentity": {
                "changedPaths": [".agents/skills/run-phase-bootstrap-review/SKILL.md"],
                "knowledgeArtifacts": [],
            },
            "deterministicEvidence": {"status": "passed", "hash": "sha256:" + "b" * 64},
            "policy": POLICY,
        })
        self.assertEqual("required", decision["requirement"])
        self.assertEqual("bootstrap-skill-route", decision["profile"])

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
        self.assertEqual(required["requirement"], "required")
        self.assertIn("workflow_control_plane_changed", required["reasonCodes"])
        self.assertEqual(required["profile"], "bootstrap-skill-route")
        self.assertEqual(required["decisionVersion"], "v10")
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


if __name__ == "__main__":
    unittest.main()
