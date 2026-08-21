from __future__ import annotations

import json
import importlib
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[5]
TOOLS = ROOT / "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools"


def _legacy_candidate_identity(slice_id: str) -> dict[str, str]:
    """Load the legacy validator without leaking its sibling modules globally."""
    module_names = ("validate_all", "protocol_guards")
    previous_modules = {name: sys.modules.get(name) for name in module_names}
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(TOOLS))
        for name in module_names:
            sys.modules.pop(name, None)
        module = importlib.import_module("validate_all")
        return module.current_candidate_identity(slice_id)
    finally:
        sys.path[:] = original_path
        for name in module_names:
            sys.modules.pop(name, None)
            if previous_modules[name] is not None:
                sys.modules[name] = previous_modules[name]


class CandidateIdentityTests(unittest.TestCase):
    def test_candidate_identity_is_complete(self) -> None:
        identity = _legacy_candidate_identity("RMAP-S6")
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
