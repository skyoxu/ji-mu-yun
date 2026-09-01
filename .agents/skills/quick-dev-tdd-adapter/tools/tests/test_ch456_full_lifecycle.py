from __future__ import annotations

import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path: sys.path.insert(0, str(TOOLS))

from coverage_predicates import publish_implementation_complete, validate_slice_ready
from current_router import materialize_descriptor, successor_descriptor
from runtime_evidence import create_json, sha256_value
from stage_pipeline import execute_stage


def _bundle() -> dict:
    return {
        "schema_version":"vdd.semantic-plan-bundle.v1","plan_id":"PLAN-TEST",
        "obligations":[{"obligation_id":"O-X","requirement_id":"FR-1","source_refs":["requirements.md#FR-1"],"subject":"value","trigger":"run","state_before":"red","state_after":"green","expected_behavior":"pass","observable_result":"exit zero","forbidden_result":[],"requirement_type":"Platform","obligation_kind":"behavior","unresolved_fragments":[],"status":"active","depends_on":[]}],
        "acceptances":[{"acceptance_id":"A-X","obligation_ids":["O-X"],"source_refs":["requirements.md#FR-1"],"given":"red value","when":"executed","then":"green value passes","oracle":{"observable":"process","expected":"pass","forbidden":["wrong value"]},"assertion_ids":["ASSERT-X"],"red_intent_ids":["FI-X"]}],
        "failure_intents":[{"failure_intent_id":"FI-X","acceptance_ids":["A-X"],"failure_id":"EXPECTED-BEHAVIOR","failure_family":"expected-red","selector_intent":"tests/test_behavior.py","expected_outcome":"fail"}],
        "pre_slice_coverage":[{"requirement_id":"FR-1","obligation_id":"O-X","acceptance_id":"A-X","source_ref":"requirements.md#FR-1","failure_intent_id":"FI-X"}],
        "slices":[{"slice_id":"S1","slice_input_hash":"sha256:"+"1"*64,"obligation_ids":["O-X"],"acceptance_ids":["A-X"],"failure_intent_ids":["FI-X"],"production_owners":["src/value.txt"],"verification_lane":"unit","behavior_change":"change value","affected_subjects":["value"],"state_transition":"red->green","proof":{"acceptance_ids":["A-X"],"selector_intents":["tests/test_behavior.py"],"assertion_ids":["ASSERT-X"]},"rollback_scope":{"production_paths":["src/value.txt"],"state_or_schema_compatibility":"compatible"},"allowed_write_paths":["src/value.txt"],"execution_snapshot_paths":["tests/test_behavior.py","tests/terminal.py","tests/fixture.txt"],"planned_new_files":[],"terminal_predicate":"all pass"}],
        "final_plan_coverage":[{"requirement_id":"FR-1","obligation_id":"O-X","acceptance_id":"A-X","source_ref":"requirements.md#FR-1","failure_intent_id":"FI-X","slice_id":"S1","verification_lane":"unit","terminal_predicate":"all pass","stage_scope":["red","green","refactor","terminal"]}],
        "agent_contexts":[]
    }


def test_real_red_green_refactor_q7_terminal_q8(tmp_path: Path) -> None:
    root = tmp_path; (root / "src").mkdir(); (root / "tests").mkdir(); (root / "plan").mkdir(parents=True); (root / "runs" / "R1" / "descriptors").mkdir(parents=True)
    (root / "requirements.md").write_text("# FR-1\nChange value.\n", encoding="utf-8")
    (root / "src" / "value.txt").write_text("red\n", encoding="utf-8")
    (root / "tests" / "fixture.txt").write_text("fixture\n", encoding="utf-8")
    behavior = """from pathlib import Path\nimport sys\nroot=Path(__file__).resolve().parents[1]\nprint('TEST_EXECUTIONS:1')\nprint('CASES:1')\nif (root/'src'/'value.txt').read_text(encoding='utf-8').strip()!='green':\n print('FAILURE_ID:EXPECTED-BEHAVIOR')\n raise SystemExit(1)\n"""
    terminal = """from pathlib import Path\nroot=Path(__file__).resolve().parents[1]\nprint('TEST_EXECUTIONS:1')\nprint('CASES:1')\nraise SystemExit(0 if (root/'src'/'value.txt').read_text(encoding='utf-8').strip()=='green' else 1)\n"""
    (root / "tests" / "test_behavior.py").write_text(behavior, encoding="utf-8")
    (root / "tests" / "terminal.py").write_text(terminal, encoding="utf-8")
    bundle = _bundle(); semantic = root / "plan" / "semantic-plan-bundle.v1.json"; semantic.write_text(json.dumps(bundle), encoding="utf-8")
    (root / "plan" / "contract.txt").write_text("contract\n", encoding="utf-8"); (root / "validators.txt").write_text("validator\n", encoding="utf-8"); (root / "state.json").write_text("{}\n", encoding="utf-8")
    run = root / "runs" / "R1"; candidate0 = "sha256:" + "0"*64; candidate1 = "sha256:" + "1"*64
    red = materialize_descriptor(bundle=bundle,slice_id="S1",stage="red",run_id="R1",candidate_hash=candidate0,argv=[sys.executable,"tests/test_behavior.py"],cwd=".",timeout_seconds=30,target_refs=["tests/test_behavior.py"],fixture_refs=["tests/fixture.txt"])
    green = successor_descriptor(red,stage="green",run_id="R1",candidate_hash=candidate1)
    refactor = successor_descriptor(red,stage="refactor",run_id="R1",candidate_hash=candidate1)
    terminal_d = materialize_descriptor(bundle=bundle,slice_id="S1",stage="terminal",run_id="R1",candidate_hash=candidate1,argv=[sys.executable,"tests/terminal.py"],cwd=".",timeout_seconds=30,target_refs=["tests/terminal.py"],fixture_refs=["tests/fixture.txt"])
    for stage, descriptor in (("red",red),("green",green),("refactor",refactor),("terminal",terminal_d)):
        create_json(run / "descriptors" / f"{stage}.json", descriptor)
    red_result = execute_stage(workspace=root,semantic_plan=semantic,run_dir=run,descriptor_path=run/"descriptors"/"red.json",profile_identity="standard")
    assert red_result["predicate_result"] is True and red_result["failure_family"] == "expected-red"
    (root / "src" / "value.txt").write_text("green\n", encoding="utf-8")
    assert execute_stage(workspace=root,semantic_plan=semantic,run_dir=run,descriptor_path=run/"descriptors"/"green.json",profile_identity="standard")["predicate_result"] is True
    assert execute_stage(workspace=root,semantic_plan=semantic,run_dir=run,descriptor_path=run/"descriptors"/"refactor.json",profile_identity="standard")["predicate_result"] is True
    roots = [
        {"root_kind":"candidate_tree","repository_relative_posix_path":"src","inclusion_reason":"candidate"},
        {"root_kind":"plan","repository_relative_posix_path":"plan/semantic-plan-bundle.v1.json","inclusion_reason":"plan"},
        {"root_kind":"contract","repository_relative_posix_path":"plan/contract.txt","inclusion_reason":"contract"},
        {"root_kind":"descriptor","repository_relative_posix_path":"runs/R1/descriptors","inclusion_reason":"descriptors"},
        {"root_kind":"fixture","repository_relative_posix_path":"tests/fixture.txt","inclusion_reason":"fixture"},
        {"root_kind":"source","repository_relative_posix_path":"requirements.md","inclusion_reason":"source"},
        {"root_kind":"validator_judge","repository_relative_posix_path":"validators.txt","inclusion_reason":"validator"},
        {"root_kind":"plan_state_transition","repository_relative_posix_path":"state.json","inclusion_reason":"state"},
    ]
    ready_path = run / "slice-ready.json"
    ready = validate_slice_ready(workspace=root,semantic_plan=semantic,run_root=run,slice_id="S1",snapshot_roots=roots,source_commit="fixture-base",out=ready_path)
    assert ready["status"] == "pass"
    terminal_result = execute_stage(workspace=root,semantic_plan=semantic,run_dir=run,descriptor_path=run/"descriptors"/"terminal.json",profile_identity="standard")
    assert terminal_result["predicate_result"] is True
    predecessor = {"slice_id":"S1","run_root":"runs/R1","result_ref":"runs/R1/slice-ready.json","result_sha256":sha256_value(ready)}
    complete = publish_implementation_complete(workspace=root,semantic_plan=semantic,predecessors=[predecessor],snapshot_roots=roots,source_commit="fixture-base",out=run/"implementation-complete.json",profile="standard")
    assert complete["status"] == "pass"
    assert {t["stage"] for t in complete["runtime_closure_tuples"]} == {"red","green","refactor","terminal"}
