#!/usr/bin/env python3
"""Measure VDD agent-context projection mutation rejection."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".agents" / "skills" / "vdd-execution-plan" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from semantic_plan_contract import STAGE_SCOPE, validate_semantic_bundle

# ADR-0041: every critical anti-false-green mutation must be rejected.
REQUIRED_REJECTION_RATE = 1.0


def _bundle() -> dict:
    return {
        "schema_version": "vdd.semantic-plan-bundle.v1",
        "obligations": [{"obligation_id":"O1","requirement_id":"FR-1","source_refs":["SPEC:FR-1"],"subject":"runner","trigger":"execute","state_before":"planned","state_after":"verified","expected_behavior":"execute real process","observable_result":"receipt","forbidden_result":["fabricated pass"],"requirement_type":"Platform","obligation_kind":"behavior","unresolved_fragments":[],"status":"active","depends_on":[]}],
        "acceptances": [{"acceptance_id":"A1","obligation_ids":["O1"],"source_refs":["SPEC:FR-1"],"given":"descriptor","when":"executed","then":"receipt","oracle":{"observable":"receipt","expected":"process-derived","forbidden":["fabricated"]},"assertion_ids":["AS1"],"red_intent_ids":["FI1"]}],
        "failure_intents": [{"failure_intent_id":"FI1","acceptance_ids":["A1"],"failure_id":"EXPECTED-RED","failure_family":"expected-red","selector_intent":"tests/test_one.py","expected_outcome":"fail"}],
        "pre_slice_coverage": [{"requirement_id":"FR-1","obligation_id":"O1","acceptance_id":"A1","source_ref":"SPEC:FR-1","failure_intent_id":"FI1"}],
        "slices": [{"slice_id":"S1","obligation_ids":["O1"],"acceptance_ids":["A1"],"failure_intent_ids":["FI1"],"production_owners":["runner"],"verification_lane":"unit","behavior_change":"execute process","affected_subjects":["runner"],"state_transition":"planned->verified","proof":{"acceptance_ids":["A1"],"selector_intents":["tests/test_one.py"],"assertion_ids":["AS1"]},"rollback_scope":{"production_paths":["runner.py"],"state_or_schema_compatibility":"none"},"allowed_write_paths":["runner.py"],"execution_snapshot_paths":["runner.py"],"planned_new_files":[],"terminal_predicate":"all acceptance closed"}],
        "final_plan_coverage": [{"requirement_id":"FR-1","obligation_id":"O1","acceptance_id":"A1","source_ref":"SPEC:FR-1","failure_intent_id":"FI1","slice_id":"S1","verification_lane":"unit","terminal_predicate":"all acceptance closed","stage_scope":list(STAGE_SCOPE)}],
        "agent_contexts": [{"slice_id":"S1","requirement_ids":["FR-1"],"obligation_ids":["O1"],"acceptance_ids":["A1"],"source_refs":["SPEC:FR-1"],"contracts":["SPEC"],"allowed_paths":["runner.py"],"forbidden_paths":[],"selector_intents":["tests/test_one.py"],"validation_commands":[["py","-3","-m","pytest","tests/test_one.py"]]}],
    }


def _cases(base: dict) -> list[tuple[str, dict]]:
    rows: list[tuple[str, dict]] = []
    def add(name: str, fn) -> None:
        value = deepcopy(base); fn(value); rows.append((name, value))
    add("context-missing", lambda b: b.__setitem__("agent_contexts", []))
    add("context-duplicate-slice", lambda b: b["agent_contexts"].append(deepcopy(b["agent_contexts"][0])))
    add("context-unknown-slice", lambda b: b["agent_contexts"][0].__setitem__("slice_id", "S404"))
    add("context-shape-missing-contracts", lambda b: b["agent_contexts"][0].pop("contracts"))
    add("obligation-projection-drift", lambda b: b["agent_contexts"][0].__setitem__("obligation_ids", ["O404"]))
    add("acceptance-projection-drift", lambda b: b["agent_contexts"][0].__setitem__("acceptance_ids", ["A404"]))
    add("selector-projection-drift", lambda b: b["agent_contexts"][0].__setitem__("selector_intents", ["tests/other.py"]))
    add("validation-commands-empty", lambda b: b["agent_contexts"][0].__setitem__("validation_commands", []))
    add("validation-command-empty-argv", lambda b: b["agent_contexts"][0].__setitem__("validation_commands", [[]]))
    add("validation-command-non-string", lambda b: b["agent_contexts"][0].__setitem__("validation_commands", [["py", 3]]))
    return rows


def evaluate() -> dict:
    base = _bundle(); baseline_valid, baseline_findings = validate_semantic_bundle(base)
    rows = []; rejected = 0
    for name, value in _cases(base):
        valid, findings = validate_semantic_bundle(value); ok = not valid
        rejected += int(ok); rows.append({"case":name,"rejected":ok,"findings":findings})
    total = len(rows); rate = rejected / total if total else 0.0
    return {"schema":"vdd.agent-context-mutation-metric.v1","baseline_valid":baseline_valid,"baseline_findings":baseline_findings,"mutation_cases":total,"rejected_cases":rejected,"rejection_rate":round(rate,6),"required_rejection_rate":REQUIRED_REJECTION_RATE,"threshold_passed":baseline_valid and rate >= REQUIRED_REJECTION_RATE,"cases":rows,"authorizes":[]}


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--out",type=Path); args=parser.parse_args()
    result=evaluate(); text=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    if args.out: args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(text,encoding="utf-8")
    print(text,end=""); return 0 if result["threshold_passed"] else 1

if __name__ == "__main__": raise SystemExit(main())
