from __future__ import annotations

import sys
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[5]
TOOLS = ROOT / "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from validate_all import current_candidate_identity  # noqa: E402


class CandidateIdentityTests(unittest.TestCase):
    def test_candidate_identity_is_complete(self) -> None:
        identity = current_candidate_identity("RMAP-S6")
        required = {"head", "index_tree", "tracked_diff_hash", "untracked_manifest_hash", "contract_hash", "command_registry_hash", "validator_hash", "authority_manifest_hash", "candidate_worktree_hash"}
        self.assertTrue(required.issubset(identity), "RMAP-REVIEW-CANDIDATE-NOT-BOUND")
        self.assertTrue(all(identity[key] for key in required), "RMAP-REVIEW-CANDIDATE-NOT-BOUND")

    def test_candidate_identity_fixture_is_complete(self) -> None:
        fixture = Path(__file__).with_name("fixtures") / "candidate-identity.v1.json"
        self.assertTrue(fixture.is_file(), "RMAP-REVIEW-CANDIDATE-NOT-BOUND")
        value = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertTrue(all(value.get(key) for key in ("head", "contract_hash", "validator_hash")), "RMAP-REVIEW-CANDIDATE-NOT-BOUND")


if __name__ == "__main__":
    unittest.main()
