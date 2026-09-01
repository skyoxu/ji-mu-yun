#!/usr/bin/env python3
"""Measure VDD source-to-V6A semantic-chain mutation rejection."""
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
from semantic_chain_audit import audit_bundle

REQUIRED_REJECTION_RATE = 0.95
STAGES = ["red", "green", "refactor", "terminal"]


def _obligation(oid: str, rid: str, source: str, subject: str) -> dict:
    return {"obligation_id": oid, "requirement_id": rid, "source_refs": [source], "subject": subject,
            "trigger": "trigger", "state_before": f"{subject}-before", "state_after": f"{subject}-after",
            "expected_behavior": f"behavior {oid}", "observable_result": f"observable {oid}",
            "forbidden_result": [], "requirement_type": "Platform", "obligation_kind": "behavior",
            "unresolved_fragments": [], "status": "active", "depends_on": []}


def _baseline() -> dict:
    obs = [_obligation("O1", "FR-1", "SPEC:FR-1", "compiler"), _obligation("O2", "FR-2", "SPEC:FR-2", "runtime")]
    acc = [
        {"acceptance_id": "A1", "obligation_ids": ["O1"], "source_refs": ["SPEC:FR-1"], "assertion_ids": ["AS1"], "red_intent_ids": ["FI1"], "verification_lane": "unit"},
        {"acceptance_id": "A2", "obligation_ids": ["O2"], "source_refs": ["SPEC:FR-2"], "assertion_ids": ["AS2"], "red_intent_ids": ["FI2"], "verification_lane": "runtime"},
    ]
    failures = [
        {"failure_intent_id": "FI1", "acceptance_ids": ["A1"], "selector_intent": "tests/test_unit.py"},
        {"failure_intent_id": "FI2", "acceptance_ids": ["A2"], "selector_intent": "tests/test_runtime.py"},
    ]
    v5 = [
        {"requirement_id": "FR-1", "obligation_id": "O1", "acceptance_id": "A1", "source_ref": "SPEC:FR-1", "failure_intent_id": "FI1"},
        {"requirement_id": "FR-2", "obligation_id": "O2", "acceptance_id": "A2", "source_ref": "SPEC:FR-2", "failure_intent_id": "FI2"},
    ]
    slices = [
        {"slice_id": "S1", "obligation_ids": ["O1"], "acceptance_ids": ["A1"], "failure_intent_ids": ["FI1"], "verification_lane": "unit", "terminal_predicate": "unit terminal", "proof": {"acceptance_ids": ["A1"], "assertion_ids": ["AS1"], "selector_intents": ["tests/test_unit.py"]}},
        {"slice_id": "S2", "obligation_ids": ["O2"], "acceptance_ids": ["A2"], "failure_intent_ids": ["FI2"], "verification_lane": "runtime", "terminal_predicate": "runtime terminal", "proof": {"acceptance_ids": ["A2"], "assertion_ids": ["AS2"], "selector_intents": ["tests/test_runtime.py"]}},
    ]
    v6a = [
        {**v5[0], "slice_id": "S1", "verification_lane": "unit", "terminal_predicate": "unit terminal", "stage_scope": STAGES},
        {**v5[1], "slice_id": "S2", "verification_lane": "runtime", "terminal_predicate": "runtime terminal", "stage_scope": STAGES},
    ]
    return {"obligations": obs, "acceptances": acc, "failure_intents": failures, "pre_slice_coverage": v5, "slices": slices, "final_plan_coverage": v6a}


def _cases(base: dict) -> list[tuple[str, dict]]:
    rows: list[tuple[str, dict]] = []
    def add(name: str, fn) -> None:
        value = deepcopy(base); fn(value); rows.append((name, value))
    add("acceptance-source-drift", lambda b: b["acceptances"][0].__setitem__("source_refs", ["SPEC:OTHER"]))
    add("failure-multiple-acceptance", lambda b: b["failure_intents"][0].__setitem__("acceptance_ids", ["A1", "A2"]))
    add("failure-unknown-acceptance", lambda b: b["failure_intents"][0].__setitem__("acceptance_ids", ["A404"]))
    add("red-intent-cover-drift", lambda b: b["acceptances"][0].__setitem__("red_intent_ids", ["FI2"]))
    add("assertion-empty", lambda b: b["acceptances"][0].__setitem__("assertion_ids", []))
    add("overbroad-independent-behavior", lambda b: b["acceptances"][0].__setitem__("obligation_ids", ["O1", "O2"]))
    add("active-obligation-no-acceptance", lambda b: b["acceptances"].__setitem__(slice(None), b["acceptances"][:1]))
    add("v5-edge-missing", lambda b: b["pre_slice_coverage"].pop())
    add("v5-edge-duplicate", lambda b: b["pre_slice_coverage"].append(deepcopy(b["pre_slice_coverage"][0])))
    add("acceptance-multiple-slices", lambda b: b["slices"][1]["acceptance_ids"].append("A1"))
    add("slice-obligation-projection", lambda b: b["slices"][0].__setitem__("obligation_ids", ["O2"]))
    add("slice-failure-projection", lambda b: b["slices"][0].__setitem__("failure_intent_ids", ["FI2"]))
    def mix_lane(b: dict) -> None:
        b["slices"][0]["acceptance_ids"] = ["A1", "A2"]
        b["slices"][0]["obligation_ids"] = ["O1", "O2"]
        b["slices"][0]["failure_intent_ids"] = ["FI1", "FI2"]
        b["slices"][0]["proof"] = {"acceptance_ids": ["A1", "A2"], "assertion_ids": ["AS1", "AS2"], "selector_intents": ["tests/test_unit.py", "tests/test_runtime.py"]}
        b["slices"] = [b["slices"][0]]
        b["final_plan_coverage"][1].update({"slice_id": "S1", "verification_lane": "unit", "terminal_predicate": "unit terminal"})
    add("incompatible-verification-lanes", mix_lane)
    add("slice-proof-missing", lambda b: b["slices"][0].pop("proof"))
    add("proof-acceptance-drift", lambda b: b["slices"][0]["proof"].__setitem__("acceptance_ids", ["A2"]))
    add("proof-assertion-drift", lambda b: b["slices"][0]["proof"].__setitem__("assertion_ids", ["AS404"]))
    add("proof-selector-drift", lambda b: b["slices"][0]["proof"].__setitem__("selector_intents", ["tests/other.py"]))
    add("acceptance-no-slice", lambda b: b["slices"].pop())
    add("v6a-stage-scope-swallowed", lambda b: b["final_plan_coverage"][0].__setitem__("stage_scope", ["terminal"]))
    add("v6a-lane-drift", lambda b: b["final_plan_coverage"][0].__setitem__("verification_lane", "runtime"))
    add("v6a-terminal-drift", lambda b: b["final_plan_coverage"][0].__setitem__("terminal_predicate", "different terminal"))
    return rows


def evaluate() -> dict:
    base = _baseline()
    baseline = audit_bundle(base)
    rows = []
    rejected = 0
    for name, value in _cases(base):
        result = audit_bundle(value)
        ok = result.get("valid") is False
        rejected += int(ok)
        rows.append({"case": name, "rejected": ok, "findings": result.get("findings", [])})
    total = len(rows); rate = rejected / total if total else 0.0
    return {"schema": "vdd.semantic-chain-mutation-metric.v1", "baseline_valid": baseline.get("valid") is True,
            "baseline_chain_coverage": baseline.get("metrics", {}).get("obligation_chain_coverage"),
            "mutation_cases": total, "rejected_cases": rejected, "rejection_rate": round(rate, 6),
            "required_rejection_rate": REQUIRED_REJECTION_RATE,
            "threshold_passed": baseline.get("valid") is True and rate >= REQUIRED_REJECTION_RATE,
            "cases": rows, "authorizes": []}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path); args = parser.parse_args()
    result = evaluate(); text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(text, encoding="utf-8")
    print(text, end=""); return 0 if result["threshold_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
