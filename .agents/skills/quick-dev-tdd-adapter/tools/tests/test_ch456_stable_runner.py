from __future__ import annotations

import json
from pathlib import Path
import sys

TOOLS=Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))

import stable_runner
from runtime_evidence import create_json,sha256_value


def _bundle()->dict:
    return {
        "schema_version":"vdd.semantic-plan-bundle.v1",
        "plan_id":"PLAN-CLI",
        "acceptances":[{"acceptance_id":"A-CLI","assertion_ids":["ASSERT-CLI"]}],
        "failure_intents":[{"failure_intent_id":"FI-CLI","failure_id":"CLI-RED"}],
        "slices":[{
            "slice_id":"S1",
            "acceptance_ids":["A-CLI"],
            "failure_intent_ids":["FI-CLI"],
            "production_owners":["src/value.py"],
            "planned_new_files":[],
            "allowed_write_paths":["src/value.py"],
            "execution_snapshot_paths":["tests/test_value.py","tests/fixture.txt"],
            "terminal_predicate":"all active Acceptance assertions pass",
        }],
    }


def _repo(tmp_path:Path)->tuple[Path,Path]:
    (tmp_path/"src").mkdir(); (tmp_path/"tests").mkdir(); (tmp_path/"plan").mkdir()
    (tmp_path/"src"/"value.py").write_text("VALUE=0\n",encoding="utf-8")
    (tmp_path/"tests"/"test_value.py").write_text("def test_value():\n    assert True\n",encoding="utf-8")
    (tmp_path/"tests"/"fixture.txt").write_text("fixture\n",encoding="utf-8")
    semantic=tmp_path/"plan"/"semantic-plan-bundle.v1.json"
    semantic.write_text(json.dumps(_bundle()),encoding="utf-8")
    return tmp_path,semantic


def test_candidate_identity_changes_only_with_slice_product_execution_bytes(tmp_path:Path)->None:
    root,_semantic=_repo(tmp_path); bundle=_bundle()
    first=stable_runner.candidate_identity(root,bundle,"S1")
    (root/"notes.txt").write_text("governance note\n",encoding="utf-8")
    second=stable_runner.candidate_identity(root,bundle,"S1")
    assert first["candidate_hash"]==second["candidate_hash"]
    (root/"src"/"value.py").write_text("VALUE=1\n",encoding="utf-8")
    third=stable_runner.candidate_identity(root,bundle,"S1")
    assert third["candidate_hash"]!=first["candidate_hash"]


def test_default_preflight_and_recommendation_only_are_distinct(tmp_path:Path,monkeypatch)->None:
    root,semantic=_repo(tmp_path)
    monkeypatch.setattr(stable_runner,"ROOT",root)
    pre=stable_runner.q1_preflight(semantic=semantic,slice_id="S1",profile="standard")
    assert pre["status"]=="preflight-passed"
    assert pre["candidate_identity"]["candidate_hash"].startswith("sha256:")
    rec=stable_runner.q0_recommendation(semantic=semantic,slice_id="S1",profile="standard",state_path=None,changed_paths=[],change_kinds=[])
    assert rec["recommended_action"]=="run-preflight"
    assert "candidate_identity" not in rec


def test_implementation_handoff_requires_clean_expected_red_and_does_not_authorize_evidence(tmp_path:Path,monkeypatch)->None:
    root,semantic=_repo(tmp_path)
    monkeypatch.setattr(stable_runner,"ROOT",root)
    run=root/"runs"/"R1"; (run/"canonical-evidence"/"red").mkdir(parents=True)
    red={
        "schema":"quick-dev.stage-result.v2","plan_id":"PLAN-CLI","slice_id":"S1","run_id":"R1","stage":"red",
        "candidate_hash":"sha256:"+"1"*64,"predicate_result":True,"verification_outcome":"fail","failure_family":"expected-red",
    }
    create_json(run/"canonical-evidence"/"red"/"stage-result.v2.json",red)
    handoff=stable_runner.q4_handoff(semantic=semantic,slice_id="S1",run_dir=run)
    assert handoff["status"]=="implementation-worker-required"
    assert handoff["predecessor_red_sha256"]==sha256_value(red)
    assert handoff["allowed_production_paths"]==["src/value.py"]
    assert handoff["authorizes_evidence"] is False and handoff["authorizes"]==[]
    red["failure_family"]="unexpected-green"
    (run/"canonical-evidence"/"red"/"stage-result.v2.json").write_text(json.dumps(red),encoding="utf-8")
    try:
        stable_runner.q4_handoff(semantic=semantic,slice_id="S1",run_dir=run)
    except ValueError:
        pass
    else:
        raise AssertionError("Q4 handoff must reject non-expected RED")
