from __future__ import annotations

import json
from pathlib import Path
import sys

THIS=Path(__file__).resolve()
TOOLS=THIS.parents[1]
REPO=THIS.parents[5]
VDD=REPO/".agents"/"skills"/"vdd-execution-plan"/"scripts"
for path in (TOOLS,VDD):
    if str(path) not in sys.path:
        sys.path.insert(0,str(path))

from coverage_predicates import publish_implementation_complete,validate_slice_ready
from current_router import materialize_descriptor,successor_descriptor
from runtime_evidence import create_json,sha256_bytes,sha256_value
from semantic_compiler import _normalize_obligation
from semantic_compiler_gate import compile_plan
from stage_pipeline import execute_stage


def _raw_obligation(subject:str,behavior:str,observable:str)->dict:
    return {
        "source_refs":["requirements.md#FR-21"],
        "subject":subject,
        "trigger":"an event arrives",
        "state_before":"rate-limit state before event",
        "state_after":"rate-limit state after event",
        "expected_behavior":behavior,
        "observable_result":observable,
        "forbidden_result":["incorrect allow/deny decision"],
        "requirement_type":"Product",
        "obligation_kind":"behavior",
        "unresolved_fragments":[],
        "status":"active",
        "depends_on":[],
    }


def _worker_cache()->dict:
    raws=[
        _raw_obligation("rate limiter","allow the first two events inside a window","first and second decisions are allow"),
        _raw_obligation("rate limiter","reject the third event inside the same window","third decision is deny"),
        _raw_obligation("rate limiter","reset capacity after the window expires","a later event is allowed after expiry"),
    ]
    ids=[_normalize_obligation({"requirement_id":"FR-21","source_ref":"requirements.md#FR-21"},raw)["obligation_id"] for raw in raws]
    failure_ids=["RL-FIRST-TWO","RL-THIRD-REJECTED","RL-WINDOW-RESET"]
    acceptances=[]; failures=[]; hints=[]
    for index,(oid,failure_id) in enumerate(zip(ids,failure_ids),start=1):
        acceptances.append({
            "obligation_ids":[oid],"source_refs":["requirements.md#FR-21"],
            "given":"a fresh rate limiter","when":"the bound event sequence is applied","then":raws[index-1]["expected_behavior"],
            "oracle":{"observable":raws[index-1]["observable_result"],"expected":"bound behavior holds","forbidden":["incorrect allow/deny decision"]},
            "assertion_ids":[f"ASSERT-RL-{index}"],
        })
        failures.append({
            "obligation_ids":[oid],"failure_family":"semantic-contract-gap","selector_intent":"tests/test_rate_limiter.py","expected_outcome":"fail","failure_id":failure_id,
        })
        hints.append({
            "obligation_ids":[oid],"production_owners":["src/rate_limiter.py"],"verification_lane":"unit",
            "behavior_change":"implement bounded fixed-window rate limiting","affected_subjects":["rate limiter"],
            "state_transition":"incorrect-rate-limit->correct-rate-limit",
            "rollback_scope":{"production_paths":["src/rate_limiter.py"],"state_or_schema_compatibility":"internal implementation only"},
            "allowed_write_paths":["src/rate_limiter.py"],
            "execution_snapshot_paths":["tests/test_rate_limiter.py","tests/fixture.txt"],
            "planned_new_files":[],"terminal_predicate":"all three rate-limit Acceptance assertions pass",
            "forbidden_paths":["tests/test_rate_limiter.py","tests/fixture.txt"],
            "validation_commands":[[sys.executable,"-m","pytest","tests/test_rate_limiter.py","-q"]],
        })
    return {
        "v1-FR-21":{"obligations":raws},
        "v3":{"acceptances":acceptances,"failure_intents":failures,"slice_hints":hints},
        "v4-atomic-recall":{"supported_obligation_ids":ids,"invented_obligation_ids":[],"source_gap_claims":[]},
        "v4":{"covered_obligation_ids":ids,"missing_obligation_ids":[],"invented_obligation_ids":[],"misaligned_acceptance_ids":[],"oracle_alignment":{"mode":"fresh-medium-ground-truth"},"repairs":[]},
    }


def test_fresh_three_behavior_requirement_compiles_and_runs_full_current_lifecycle(tmp_path:Path)->None:
    root=tmp_path
    (root/".agents").mkdir(); (root/"AGENTS.md").write_text("fresh fixture\n",encoding="utf-8")
    (root/"src").mkdir(); (root/"tests").mkdir(); (root/"runs"/"R1"/"descriptors").mkdir(parents=True)
    requirements=root/"requirements.md"
    requirements.write_text(
        "# FR-21\nA fixed-window limiter must allow the first two events, reject the third event inside the same 10-second window, and restore capacity after the window expires.\n",
        encoding="utf-8",
    )
    production=root/"src"/"rate_limiter.py"
    production.write_text(
        "class RateLimiter:\n"
        "    def __init__(self):\n        self.calls=0\n"
        "    def allow(self, now):\n"
        "        if now >= 10: return False\n"
        "        self.calls += 1\n"
        "        return self.calls > 2\n",
        encoding="utf-8",
    )
    (root/"tests"/"fixture.txt").write_text("limit=2;window=10\n",encoding="utf-8")
    (root/"tests"/"test_rate_limiter.py").write_text(
        "from src.rate_limiter import RateLimiter\n\n"
        "def test_first_two_are_allowed():\n"
        "    r=RateLimiter(); ok=r.allow(0) and r.allow(1)\n"
        "    if not ok: print('FAILURE_ID:RL-FIRST-TWO')\n"
        "    assert ok\n\n"
        "def test_third_inside_window_is_rejected():\n"
        "    r=RateLimiter(); r.allow(0); r.allow(1); denied=not r.allow(2)\n"
        "    if not denied: print('FAILURE_ID:RL-THIRD-REJECTED')\n"
        "    assert denied\n\n"
        "def test_capacity_resets_after_window():\n"
        "    r=RateLimiter(); r.allow(0); r.allow(1); allowed=r.allow(12)\n"
        "    if not allowed: print('FAILURE_ID:RL-WINDOW-RESET')\n"
        "    assert allowed\n",
        encoding="utf-8",
    )

    plan=root/"plan"
    result=compile_plan(requirements=requirements,out_dir=plan,worker_cache=_worker_cache())
    assert result["status"]=="plan-ready"
    assert result["atomic_quality_metrics"]=={
        "active_obligation_count":3,"supported_obligation_count":3,"invented_obligation_count":0,"source_gap_count":0,
        "precision":1.0,"recall":1.0,"f1":1.0,
    }
    bundle=json.loads((plan/"semantic-plan-bundle.v1.json").read_text(encoding="utf-8"))
    assert len(bundle["obligations"])==3
    assert len(bundle["slices"])==1
    selected=bundle["slices"][0]
    assert len(selected["obligation_ids"])==3 and len(selected["acceptance_ids"])==3

    (plan/"contract.txt").write_text("fresh contract\n",encoding="utf-8")
    (root/"validators.txt").write_text("current validator/judge v2\n",encoding="utf-8")
    (root/"state.json").write_text("{}\n",encoding="utf-8")
    run=root/"runs"/"R1"
    candidate0=sha256_bytes(production.read_bytes())
    selector=[sys.executable,"-m","pytest","tests/test_rate_limiter.py","-q"]
    red=materialize_descriptor(bundle=bundle,slice_id="S1",stage="red",run_id="R1",candidate_hash=candidate0,argv=selector,cwd=".",timeout_seconds=30,target_refs=["tests/test_rate_limiter.py"],fixture_refs=["tests/fixture.txt"])
    create_json(run/"descriptors"/"red.json",red)
    red_result=execute_stage(workspace=root,semantic_plan=plan/"semantic-plan-bundle.v1.json",run_dir=run,descriptor_path=run/"descriptors"/"red.json",profile_identity="standard")
    assert red_result["predicate_result"] is True and red_result["failure_family"]=="expected-red"

    production.write_text(
        "class RateLimiter:\n"
        "    def __init__(self, limit=2, window=10):\n"
        "        self.limit=limit; self.window=window; self.events=[]\n"
        "    def allow(self, now):\n"
        "        self.events=[t for t in self.events if now-t < self.window]\n"
        "        if len(self.events) >= self.limit: return False\n"
        "        self.events.append(now); return True\n",
        encoding="utf-8",
    )
    candidate1=sha256_bytes(production.read_bytes())
    green=successor_descriptor(red,stage="green",run_id="R1",candidate_hash=candidate1)
    refactor=successor_descriptor(red,stage="refactor",run_id="R1",candidate_hash=candidate1)
    terminal=materialize_descriptor(bundle=bundle,slice_id="S1",stage="terminal",run_id="R1",candidate_hash=candidate1,argv=selector,cwd=".",timeout_seconds=30,target_refs=["tests/test_rate_limiter.py"],fixture_refs=["tests/fixture.txt"])
    for stage,descriptor in (("green",green),("refactor",refactor),("terminal",terminal)):
        create_json(run/"descriptors"/f"{stage}.json",descriptor)
    assert execute_stage(workspace=root,semantic_plan=plan/"semantic-plan-bundle.v1.json",run_dir=run,descriptor_path=run/"descriptors"/"green.json",profile_identity="standard")["predicate_result"] is True
    assert execute_stage(workspace=root,semantic_plan=plan/"semantic-plan-bundle.v1.json",run_dir=run,descriptor_path=run/"descriptors"/"refactor.json",profile_identity="standard")["predicate_result"] is True

    roots=[
        {"root_kind":"candidate_tree","repository_relative_posix_path":"src","inclusion_reason":"fresh candidate"},
        {"root_kind":"plan","repository_relative_posix_path":"plan/semantic-plan-bundle.v1.json","inclusion_reason":"fresh plan"},
        {"root_kind":"contract","repository_relative_posix_path":"plan/contract.txt","inclusion_reason":"fresh contract"},
        {"root_kind":"descriptor","repository_relative_posix_path":"runs/R1/descriptors","inclusion_reason":"frozen descriptors"},
        {"root_kind":"fixture","repository_relative_posix_path":"tests/fixture.txt","inclusion_reason":"fixture"},
        {"root_kind":"source","repository_relative_posix_path":"requirements.md","inclusion_reason":"source"},
        {"root_kind":"validator_judge","repository_relative_posix_path":"validators.txt","inclusion_reason":"validator"},
        {"root_kind":"plan_state_transition","repository_relative_posix_path":"state.json","inclusion_reason":"state"},
    ]
    ready_path=run/"slice-ready.json"
    ready=validate_slice_ready(workspace=root,semantic_plan=plan/"semantic-plan-bundle.v1.json",run_root=run,slice_id="S1",snapshot_roots=roots,source_commit="fresh-fixture-base",out=ready_path)
    assert ready["status"]=="pass"
    assert execute_stage(workspace=root,semantic_plan=plan/"semantic-plan-bundle.v1.json",run_dir=run,descriptor_path=run/"descriptors"/"terminal.json",profile_identity="standard")["predicate_result"] is True
    predecessor={"slice_id":"S1","run_root":"runs/R1","result_ref":"runs/R1/slice-ready.json","result_sha256":sha256_value(ready)}
    complete=publish_implementation_complete(workspace=root,semantic_plan=plan/"semantic-plan-bundle.v1.json",predecessors=[predecessor],snapshot_roots=roots,source_commit="fresh-fixture-base",out=run/"implementation-complete.json",profile="standard")
    assert complete["status"]=="pass"
