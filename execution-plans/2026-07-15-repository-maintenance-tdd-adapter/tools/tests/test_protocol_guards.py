from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[2]
TOOLS = PLAN_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from protocol_guards import evaluate_protocol_fixture, validate_protocol_fixture_suite  # noqa: E402
from protocol_artifact_guards import capsule_artifact_refs, validate_context_artifacts, value_hash  # noqa: E402
from protocol_fixture_support import hydrate_protocol_fixture  # noqa: E402


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

    def test_capsule_object_must_match_referenced_bytes(self) -> None:
        bundle, store, _ = hydrate_protocol_fixture(self.fixtures["valid_bundle"])
        context = copy.deepcopy(bundle["contexts"][0]["context_manifest"])
        capsule = copy.deepcopy(bundle["contexts"][1]["slice_capsule"])
        context["capsule_id"] = capsule["capsule_id"]
        context["stage"] = capsule["stage"]
        context["artifact_refs"] = capsule_artifact_refs(capsule)
        context["context_hash"] = value_hash({
            "capsule_hash": context["capsule_ref"]["sha256"],
            "artifact_refs": context["artifact_refs"],
        })
        self.assertEqual(
            {"RMAP-CAPSULE-CONTEXT"},
            {item["rule_id"] for item in validate_context_artifacts(context, capsule, store)},
        )

    def test_adapter_decision_cannot_authorize_transition(self) -> None:
        self.assertEqual({"RMAP-ATTEMPT-AUTHORITY"}, self._rules("attempt-decision-authority-escalation"))

    def test_partial_attempt_fails_closed(self) -> None:
        self.assertEqual({"RMAP-ATTEMPT-PARTIAL"}, self._rules("attempt-decision-missing"))

    def test_duplicate_accepted_stage_is_rejected(self) -> None:
        self.assertEqual({"RMAP-ATTEMPT-STAGE-UNIQUENESS"}, self._rules("attempt-duplicate-accepted-stage"))

    def test_single_green_attempt_cannot_satisfy_complete_slice_exit(self) -> None:
        self.assertEqual({"RMAP-ATTEMPT-STAGE-ORDER"}, self._rules("attempt-stage-set-incomplete"))

    def test_capsule_manifest_must_equal_actual_reference_union(self) -> None:
        self.assertEqual(
            {"RMAP-CAPSULE-ARTIFACT-CLOSURE"},
            self._rules("capsule-reference-omitted-from-manifest"),
        )

    def test_event_lifecycle_requires_response_recorded(self) -> None:
        self.assertEqual(
            {"RMAP-ATTEMPT-EVENT-LIFECYCLE"},
            self._rules("attempt-event-lifecycle-missing"),
        )

    def test_forbidden_path_cannot_be_self_labelled_allowed(self) -> None:
        self.assertEqual(
            {"RMAP-ATTEMPT-DIFF-SCOPE"},
            self._rules("attempt-forbidden-path-labelled-allowed"),
        )

    def test_candidate_binds_attempt_ledger_root(self) -> None:
        self.assertEqual(
            {"RMAP-ATTEMPT-LEDGER"},
            self._rules("candidate-ledger-root-stale"),
        )


if __name__ == "__main__":
    unittest.main()
