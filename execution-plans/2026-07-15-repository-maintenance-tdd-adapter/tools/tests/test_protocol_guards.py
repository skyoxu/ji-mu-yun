from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[2]
TOOLS = PLAN_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from protocol_guards import evaluate_protocol_fixture, validate_protocol_fixture_suite  # noqa: E402


class ProtocolGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = json.loads((PLAN_ROOT / "fixtures" / "capsule-attempt-cases.v1.json").read_text(encoding="utf-8"))

    def _rules(self, fixture_id: str) -> set[str]:
        return {item["rule_id"] for item in evaluate_protocol_fixture(PLAN_ROOT, fixture_id, self.fixtures)}

    def test_protocol_fixture_suite_is_exact(self) -> None:
        self.assertEqual([], validate_protocol_fixture_suite(PLAN_ROOT, self.fixtures))

    def test_capsule_context_hash_stale_is_rejected(self) -> None:
        self.assertEqual({"RMAP-CAPSULE-CONTEXT"}, self._rules("capsule-context-hash-stale"))

    def test_adapter_decision_cannot_authorize_transition(self) -> None:
        self.assertEqual({"RMAP-ATTEMPT-AUTHORITY"}, self._rules("attempt-decision-authority-escalation"))

    def test_partial_attempt_fails_closed(self) -> None:
        self.assertEqual({"RMAP-ATTEMPT-PARTIAL"}, self._rules("attempt-decision-missing"))

    def test_duplicate_accepted_stage_is_rejected(self) -> None:
        self.assertEqual({"RMAP-ATTEMPT-STAGE-UNIQUENESS"}, self._rules("attempt-duplicate-accepted-stage"))


if __name__ == "__main__":
    unittest.main()
