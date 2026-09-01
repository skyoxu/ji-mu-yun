from __future__ import annotations

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve()
SCRIPTS = HERE.parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from semantic_compiler import compile_plan


def _cache(source_ref: str, owner: str, selector_path: str) -> dict:
    obligation = {
        "source_refs": [source_ref], "subject": "compiler", "trigger": "input changes",
        "state_before": "uncompiled", "state_after": "compiled", "expected_behavior": "compile deterministically",
        "observable_result": "plan ready", "forbidden_result": ["invented runtime evidence"],
        "requirement_type": "Platform", "obligation_kind": "behavior", "unresolved_fragments": [],
        "status": "active", "depends_on": [],
    }
    return {
        "v1-FR-1": {"obligations": [obligation]},
        "v3": {
            "acceptances": [{
                "obligation_ids": [], "source_refs": [source_ref], "given": "a valid requirement", "when": "compiled",
                "then": "a plan is emitted", "oracle": {"observable": "bundle", "expected": "plan-ready", "forbidden": ["future evidence"]},
                "assertion_ids": ["ASSERT-COMPILE"],
            }],
            "failure_intents": [{"obligation_ids": [], "failure_family": "semantic-contract-gap", "selector_intent": selector_path, "expected_outcome": "fail", "failure_id": "COMPILE-RED"}],
            "slice_hints": [{
                "obligation_ids": [], "production_owners": [owner], "verification_lane": "unit",
                "behavior_change": "compile plans", "affected_subjects": ["compiler"], "state_transition": "uncompiled->compiled",
                "rollback_scope": {"production_paths": [owner], "state_or_schema_compatibility": "backward-compatible"},
                "allowed_write_paths": [owner], "execution_snapshot_paths": [selector_path], "planned_new_files": [],
                "terminal_predicate": "all active Acceptance assertions pass", "forbidden_paths": [],
                "validation_commands": [["py", "-3", "-m", "pytest", selector_path]],
            }],
        },
        "v4": {"covered_obligation_ids": [], "missing_obligation_ids": [], "invented_obligation_ids": [], "misaligned_acceptance_ids": [], "oracle_alignment": {}, "repairs": []},
    }


def _rewrite_cache_ids(cache: dict, obligation_id: str) -> None:
    cache["v3"]["acceptances"][0]["obligation_ids"] = [obligation_id]
    cache["v3"]["failure_intents"][0]["obligation_ids"] = [obligation_id]
    cache["v3"]["slice_hints"][0]["obligation_ids"] = [obligation_id]
    cache["v4"]["covered_obligation_ids"] = [obligation_id]


def test_recommendation_only_never_needs_worker(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path
    (root / ".agents").mkdir(); (root / "AGENTS.md").write_text("x", encoding="utf-8")
    req = root / "req.md"; req.write_text("# FR-1\nMust compile.\n", encoding="utf-8")
    result = compile_plan(requirements=req, out_dir=root / "out", recommendation_only=True)
    assert result["status"] == "recommendation-only"
    assert result["model_called"] is False
    assert not (root / "out").exists()


def test_v0_preflight_rejects_missing_requirement_anchor(tmp_path: Path) -> None:
    root = tmp_path
    (root / ".agents").mkdir(); (root / "AGENTS.md").write_text("x", encoding="utf-8")
    req = root / "req.md"; req.write_text("No requirement IDs here.\n", encoding="utf-8")
    try:
        compile_plan(requirements=req, out_dir=root / "out", recommendation_only=True)
    except ValueError as exc:
        assert "requirement" in str(exc)
    else:
        raise AssertionError("missing requirement anchor must fail")
