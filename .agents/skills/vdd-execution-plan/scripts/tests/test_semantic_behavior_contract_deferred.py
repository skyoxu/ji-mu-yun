from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from semantic_behavior_contract import SCHEMA, project_deferred, project_intents, validate_routing_intent


def test_deferred_obligation_is_not_a_quick_dev_intent_and_is_explicitly_blocking() -> None:
    bundle = {
        "obligations": [{
            "obligation_id": "O-DEFERRED", "status": "deferred",
            "unresolved_fragments": ["The frozen source omits the required identity."],
        }],
        "acceptances": [], "slices": [], "agent_contexts": [],
    }
    deferred = project_deferred(bundle)
    bundle["behavior_routing"] = {"schema": SCHEMA, "intents": project_intents(bundle), "deferred": deferred}

    assert project_intents(bundle) == []
    assert deferred[0]["affected_obligation_ids"] == ["O-DEFERRED"]
    assert validate_routing_intent(bundle) == ["deferred:blocks-current-scope:O-DEFERRED"]
