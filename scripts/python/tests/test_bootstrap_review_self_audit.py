#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = REPO_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import bootstrap_review_self_audit as audit  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def reviewer_output(role: str, count: int, status: str = "completed") -> dict[str, object]:
    return {
        "status": status,
        "reviewerLayer": role,
        "candidates": [{"id": f"{role}-{index}"} for index in range(count)],
    }


class BootstrapReviewSelfAuditTests(unittest.TestCase):
    def make_finalized_run(self, root: Path) -> Path:
        run = root / "logs" / "ci" / "2026-07-16" / "review-gateway-bootstrap-final"
        write_json(
            run / "review-input.json",
            {
                "reviewId": "final",
                "profileName": "bootstrap-upstream-plan",
                "worktreeDirty": True,
                "artifacts": [{"artifact": "plan.md"}],
                "reviewCostEstimate": {"totalBytes": 100},
            },
        )
        write_json(run / "reviewer-outputs" / "blind_hunter.json", reviewer_output("blind_hunter", 1))
        write_json(run / "reviewer-outputs" / "edge_case_hunter.json", reviewer_output("edge_case_hunter", 1))
        write_json(run / "reviewer-outputs" / "acceptance_auditor.json", reviewer_output("acceptance_auditor", 1))
        write_json(
            run / "review-gate-result.json",
            {
                "schemaVersion": "review-result.v1",
                "status": "blocked",
                "findings": [
                    {
                        "proposedSeverity": "P1",
                        "status": "confirmed",
                        "sourceReviewers": ["blind_hunter"],
                    },
                    {
                        "proposedSeverity": "P2",
                        "status": "advisory",
                        "sourceReviewers": ["edge_case_hunter"],
                    },
                ],
            },
        )
        write_json(
            run / "review-metrics.json",
            {
                "rawCandidateCount": 3,
                "acceptedUniqueCount": 2,
                "rejectedCount": 1,
                "confirmedCount": 1,
                "advisoryCount": 1,
                "unverifiedCount": 0,
                "refutedCount": 0,
            },
        )
        write_json(
            run / "process-leases.json",
            {
                "leases": [
                    {
                        "operationId": "reviewer:blind_hunter",
                        "state": "completed",
                        "acquiredAt": "2026-07-16T00:00:00Z",
                        "updatedAt": "2026-07-16T00:01:00Z",
                    }
                ]
            },
        )
        (run / "blind.stderr.txt").write_text("tokens used\n1,000\n", encoding="utf-8", newline="\n")
        (run / "model-probe.txt").write_text("tokens used\n100\n", encoding="utf-8", newline="\n")
        return run

    def make_non_finalized_run(self, root: Path) -> Path:
        run = root / "logs" / "ci" / "2026-07-16" / "review-gateway-bootstrap-prepared"
        write_json(run / "review-input.json", {"reviewId": "prepared", "artifacts": []})
        write_json(run / "reviewer-outputs" / "blind_hunter.json", reviewer_output("blind_hunter", 0, "pending"))
        write_json(run / "reviewer-outputs" / "edge_case_hunter.json", reviewer_output("edge_case_hunter", 1))
        write_json(run / "reviewer-outputs" / "acceptance_auditor.json", reviewer_output("acceptance_auditor", 0, "pending"))
        (run / "edge-retry.stderr.txt").write_text("tokens used\n200\n", encoding="utf-8", newline="\n")
        return run

    def test_run_audit_separates_all_and_finalized_candidate_populations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_finalized_run(root)
            self.make_non_finalized_run(root)
            out = root / "audit"

            with patch.object(
                audit,
                "implementation_hashes",
                return_value=[{"path": "scripts/python/bootstrap_review_self_audit.py", "sha256": "sha256:test"}],
            ):
                result = audit.run_audit(root, out, "test-audit")

            funnel = json.loads((out / "candidate-funnel.json").read_text(encoding="utf-8"))
            tokens = json.loads((out / "token-and-duration-summary.json").read_text(encoding="utf-8"))
            output_names = {path.name for path in out.iterdir()}

        self.assertEqual("pass", result["status"])
        self.assertEqual(2, result["run_count"])
        self.assertEqual(4, funnel["all_run_reviewer_submissions"])
        self.assertEqual(3, funnel["finalized_run_reviewer_submissions"])
        self.assertEqual(3, funnel["gateway"]["rawCandidateCount"])
        self.assertEqual(2, funnel["gateway"]["acceptedUniqueCount"])
        self.assertEqual(1, funnel["gateway"]["rejectedCount"])
        self.assertEqual({"P1": 1, "P2": 1}, funnel["final_findings_by_severity"])
        self.assertEqual(1300, tokens["token_total"])
        self.assertEqual(200, tokens["tokens_by_run_finality"]["non-finalized"])
        self.assertEqual(200, tokens["tokens_by_execution_kind"]["retry-labelled"])
        self.assertEqual(1, tokens["lease_states"]["completed"])
        self.assertEqual(
            {
                "audit-input-manifest.json",
                "per-run-classification.json",
                "candidate-funnel.json",
                "token-and-duration-summary.json",
                "audit-result.json",
            },
            output_names,
        )

    def test_unreadable_json_fails_audit_without_rewriting_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "logs" / "ci" / "2026-07-16" / "review-gateway-bootstrap-invalid"
            run.mkdir(parents=True)
            invalid = run / "review-input.json"
            invalid.write_text("{invalid", encoding="utf-8", newline="\n")
            out = root / "audit"

            with patch.object(audit, "implementation_hashes", return_value=[]):
                result = audit.run_audit(root, out, "invalid-audit")

            manifest = json.loads((out / "audit-input-manifest.json").read_text(encoding="utf-8"))
            invalid_after = invalid.read_text(encoding="utf-8")

        self.assertEqual("fail", result["status"])
        self.assertEqual("{invalid", invalid_after)
        self.assertEqual(1, len(manifest["unreadable_inputs"]))


if __name__ == "__main__":
    unittest.main()
