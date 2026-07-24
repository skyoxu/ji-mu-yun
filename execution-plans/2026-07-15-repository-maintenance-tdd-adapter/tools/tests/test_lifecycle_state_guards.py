from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLAN_ROOT / "tools"))
from lifecycle_state_guards import validate_implementation_authorization, validate_legacy_migration  # noqa: E402


class LifecycleStateGuardTests(unittest.TestCase):
    def test_legacy_marker_cannot_retroactively_authorize_implementation(self) -> None:
        marker = json.loads((PLAN_ROOT / "schemas" / "legacy-lifecycle-migration.v1.json").read_text(encoding="utf-8"))
        self.assertEqual([], validate_legacy_migration(PLAN_ROOT, marker))
        marker["authorizes"] = ["implementation-authorized"]
        self.assertEqual(["RMAP-LEGACY-NOT-RETROACTIVE"], [item["rule_id"] for item in validate_legacy_migration(PLAN_ROOT, marker)])

    def test_override_is_implementation_only_and_outside_quick_dev(self) -> None:
        override = {
            "schema_version": "rmap.implementation-authorization.v1",
            "plan_id": "repository-maintenance-tdd-adapter",
            "state": "implementation-authorized",
            "mode": "user-confirmed-override",
            "candidate_hash": "sha256:" + "a" * 64,
            "operator_override_path": "decision-logs/operator-overrides/rmap.json",
            "authorizes": ["implementation-authorized"],
            "does_not_authorize": ["implementation-complete", "acceptance-passed", "protected-handoff", "archived"],
        }
        self.assertEqual([], validate_implementation_authorization(PLAN_ROOT, override, "decision-logs/operator-overrides/rmap.json"))
        invalid = copy.deepcopy(override)
        invalid["operator_override_path"] = "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/override.json"
        self.assertEqual(["RMAP-IMPLEMENTATION-AUTHORIZATION"], [item["rule_id"] for item in validate_implementation_authorization(PLAN_ROOT, invalid, invalid["operator_override_path"])])


if __name__ == "__main__":
    unittest.main()
