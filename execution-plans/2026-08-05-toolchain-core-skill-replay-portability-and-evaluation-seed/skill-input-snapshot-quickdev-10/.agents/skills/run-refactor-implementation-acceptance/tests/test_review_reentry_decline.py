from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


class ReviewReentryDeclineTests(unittest.TestCase):
    def setUp(self) -> None:
        import acceptance_core

        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.target = "execution-plans/target"
        (self.root / self.target).mkdir(parents=True)
        self.completeness = {
            "schemaVersion": "acceptance-repair-completeness.v1",
            "status": "passed",
            "acceptanceTarget": self.target,
            "lineageFamilyId": "ria-" + "a" * 32,
            "semanticRoundsConsumed": 1,
            "novelP0P1FindingIds": [],
            "authorityGraphChanged": True,
            "highRiskBoundaryChanged": False,
            "authorizes": [],
        }
        repair_request = {"producer": "test"}
        self.route = {
            "schemaVersion": "implementation-acceptance-bootstrap-route.v1",
            "routeKind": "full_implementation_conformance",
            "nextAction": "run-phase-bootstrap-review",
            "findingMode": "discovery",
            "findingModeReentry": "user_confirmation_required",
            "semanticRoundsConsumed": 1,
            "nextFullReviewRound": 2,
            "roundEntryReason": "authority_context_graph_changed",
            "maintenanceMode": "ai-native-single-maintainer",
            "lineageFamilyId": self.completeness["lineageFamilyId"],
            "repairCompletenessRequest": repair_request,
            "repairCompletenessRequestHash": acceptance_core.canonical_hash(repair_request),
            "repairCompletenessHash": acceptance_core.canonical_hash(self.completeness),
            "authorizes": [],
        }
        self.route_path = self.root / self.target / "route.json"
        self.completeness_path = self.root / self.target / "repair.json"
        self.route_path.write_text(json.dumps(self.route), encoding="utf-8", newline="\n")
        self.completeness_path.write_text(json.dumps(self.completeness), encoding="utf-8", newline="\n")
        self.request = {
            "schemaVersion": "acceptance-review-reentry-decline-request.v1",
            "repositoryRoot": str(self.root),
            "acceptanceTarget": self.target,
            "acceptanceRepairRoute": {"path": f"{self.target}/route.json", "sha256": file_hash(self.route_path)},
            "repairCompleteness": {"path": f"{self.target}/repair.json", "sha256": file_hash(self.completeness_path)},
            "decision": "decline-finding-mode-reentry",
            "userConfirmed": True,
            "authorityRole": "maintainer",
            "rationale": "Existing review and deterministic repair evidence are sufficient.",
            "recordedAt": "2026-08-04T00:00:00Z",
            "authorizes": ["review-reentry-decline-closure"],
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def close(self, request: dict | None = None) -> dict:
        import review_reentry_decline

        with mock.patch.object(
            review_reentry_decline,
            "audit_repair_completeness",
            return_value=self.completeness,
        ):
            return review_reentry_decline.close_declined_review_reentry(request or self.request)

    def test_closes_declined_round_two_discovery_without_model_authority(self) -> None:
        result = self.close()
        self.assertEqual("acceptance-passed", result["lifecycleTransition"])
        self.assertEqual(["acceptance-passed"], result["authorizes"])
        self.assertEqual("round-2-finding-discovery", result["skippedAction"])
        self.assertTrue(result["residualRiskAccepted"])
        self.assertEqual(["commit", "release", "archived"], result["doesNotAuthorize"])

    def test_rejects_novel_blocker_or_unconfirmed_maintainer_decision(self) -> None:
        request = copy.deepcopy(self.request)
        request["userConfirmed"] = False
        with self.assertRaisesRegex(Exception, "acknowledgement"):
            self.close(request)

        self.completeness["novelP0P1FindingIds"] = ["BSR-NEW"]
        import acceptance_core

        self.completeness_path.write_text(
            json.dumps(self.completeness), encoding="utf-8", newline="\n"
        )
        self.route["repairCompletenessHash"] = acceptance_core.canonical_hash(
            self.completeness
        )
        self.route_path.write_text(json.dumps(self.route), encoding="utf-8", newline="\n")
        self.request["repairCompleteness"]["sha256"] = file_hash(self.completeness_path)
        self.request["acceptanceRepairRoute"]["sha256"] = file_hash(self.route_path)
        with self.assertRaisesRegex(Exception, "cannot close"):
            self.close()

    def test_rejects_a_non_proposal_route(self) -> None:
        self.route["findingModeReentry"] = "not_applicable"
        self.route_path.write_text(json.dumps(self.route), encoding="utf-8", newline="\n")
        self.request["acceptanceRepairRoute"]["sha256"] = file_hash(self.route_path)
        with self.assertRaisesRegex(Exception, "eligible later-discovery proposal"):
            self.close()


if __name__ == "__main__":
    unittest.main()
