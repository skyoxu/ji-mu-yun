from __future__ import annotations

import hashlib
from pathlib import Path
import sys

TOOLS=Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))
from closure_predicate import validate_runtime_closure
from current_router import stop_loss
from detached_promotion import validate_detached_bundle
from process_executor_v2 import _counts


def test_zero_case_success_is_not_invented()->None:
    assert _counts("plain success",timed_out=False)==(0,0)
    assert _counts("1 passed in 0.01s",timed_out=False)==(1,1)
    assert _counts("1 failed, 2 passed in 0.02s",timed_out=False)==(1,3)


def test_terminal_selector_may_differ_from_tdd_selector()->None:
    snapshot="sha256:"+"a"*64; edge_hash="sha256:"+"b"*64; tuples=[]
    for stage in ("red","green","refactor","terminal"): tuples.append({"tuple_key":f"S1|A-X|{stage}","slice_id":"S1","acceptance_id":"A-X","stage":stage,"runtime_edge_sha256":edge_hash,"selector_identity":"TDD" if stage!="terminal" else "TERMINAL","current_snapshot_sha256":snapshot})
    valid,findings=validate_runtime_closure(tuples,{x["tuple_key"] for x in tuples},snapshot); assert valid,findings


def test_duplicate_tuple_fails()->None:
    snapshot="sha256:"+"a"*64; edge_hash="sha256:"+"b"*64; item={"tuple_key":"S1|A-X|red","slice_id":"S1","acceptance_id":"A-X","stage":"red","runtime_edge_sha256":edge_hash,"selector_identity":"X","current_snapshot_sha256":snapshot}; valid,findings=validate_runtime_closure([item,dict(item)],{item["tuple_key"]},snapshot); assert not valid and "tuple-key-duplicate" in findings


def test_repeated_fingerprint_stops_second_identical_failure()->None:
    assert stop_loss([],"x")["stop"] is False; assert stop_loss(["x"],"x")["stop"] is True


def test_detached_bundle_rejects_candidate_tree_and_accepts_external(tmp_path:Path)->None:
    candidate=tmp_path/"candidate"; detached=tmp_path/"detached"; candidate.mkdir(); detached.mkdir(); artifacts=[]
    for role in ("judge","oracle","fixture"):
        path=detached/f"{role}.txt"; path.write_text(f"{role}\n",encoding="utf-8"); artifacts.append({"role":role,"path":str(path),"sha256":"sha256:"+hashlib.sha256(path.read_bytes()).hexdigest(),"read_only":True})
    bundle={"schema":"detached-judge-bundle.v1","source_commit":"c","source_tree":"t","judge_identity":"j","judge_version":"1","read_only_open_result":True,"promotion_revalidation_result":True,"artifacts":artifacts}; valid,findings=validate_detached_bundle(bundle,candidate_root=candidate); assert valid,findings
    artifacts[0]["path"]=str(candidate/"judge.txt"); (candidate/"judge.txt").write_text("judge",encoding="utf-8"); artifacts[0]["sha256"]="sha256:"+hashlib.sha256((candidate/"judge.txt").read_bytes()).hexdigest(); valid,findings=validate_detached_bundle(bundle,candidate_root=candidate); assert not valid and any("inside-candidate" in item for item in findings)
