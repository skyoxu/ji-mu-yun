from __future__ import annotations
import json
from pathlib import Path
import sys
TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path: sys.path.insert(0, str(TOOLS))
from stage_pipeline import execute_stage


def digest(): return "sha256:" + "a" * 64

def bundle(): return {"schema_version":"vdd.semantic-plan-bundle.v1","plan_id":"P1","acceptances":[{"acceptance_id":"A-ONE","assertion_ids":["AS-1"]}],"failure_intents":[{"failure_intent_id":"FI-ONE","failure_id":"EXPECTED-RED"}],"slices":[{"slice_id":"S1","acceptance_ids":["A-ONE"],"failure_intent_ids":["FI-ONE"]}],"final_plan_coverage":[{"slice_id":"S1","acceptance_id":"A-ONE","stage_scope":["red","green","refactor","terminal"]}]}
def descriptor(script, name): return {"id":name,"executable":sys.executable,"argv":["-c",script],"cwd":".","timeout_seconds":10,"shell":False}

def setup(tmp_path):
    semantic=tmp_path/"semantic.json"; semantic.write_text(json.dumps(bundle()),encoding="utf-8"); (tmp_path/"target.py").write_text("target",encoding="utf-8"); (tmp_path/"fixture.py").write_text("fixture",encoding="utf-8"); return semantic

def test_red_receipt_and_judge_are_separate(tmp_path: Path):
    semantic=setup(tmp_path); path=tmp_path/"red.json"; path.write_text(json.dumps(descriptor("print('FAILURE_ID:EXPECTED-RED'); raise SystemExit(1)","red")),encoding="utf-8"); run=tmp_path/"RUN-1"
    result=execute_stage(workspace=tmp_path,semantic_plan=semantic,slice_id="S1",run_dir=run,stage="red",descriptor_path=path,candidate_hash=digest(),profile_identity="standard",selector="tests/test_one.py",target_refs=["target.py"],fixture_refs=["fixture.py"])
    receipt=json.loads((run/"canonical-evidence/red/process-receipt.v2.json").read_text(encoding="utf-8")); observation=json.loads((run/"canonical-evidence/red/observation.v2.json").read_text(encoding="utf-8"))
    assert "verification_outcome" not in receipt; assert observation["verification_outcome"]=="fail"; assert observation["failure_family"]=="expected-red"; assert result["predicate_result"] is True

def test_timeout_has_zero_cases(tmp_path: Path):
    semantic=setup(tmp_path); value=descriptor("import time; time.sleep(2)","red"); value["timeout_seconds"]=1; path=tmp_path/"red.json"; path.write_text(json.dumps(value),encoding="utf-8"); run=tmp_path/"RUN-2"
    try: execute_stage(workspace=tmp_path,semantic_plan=semantic,slice_id="S1",run_dir=run,stage="red",descriptor_path=path,candidate_hash=digest(),profile_identity="standard",selector="tests/test_one.py",target_refs=["target.py"],fixture_refs=["fixture.py"])
    except RuntimeError: pass
    receipt=json.loads((run/"canonical-evidence/red/process-receipt.v2.json").read_text(encoding="utf-8")); assert receipt["timed_out"] is True; assert receipt["test_executions"]==0; assert receipt["cases"]==0
