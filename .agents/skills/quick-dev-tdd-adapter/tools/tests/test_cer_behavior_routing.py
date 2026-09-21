"""ADR-0041: CER-R4--R6 through real controlled cases and current Q7/Q8."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from current_router import materialize_descriptor, successor_descriptor
from stage_pipeline import execute_stage
from runtime_evidence import create_json, sha256_value, sha256_bytes
from coverage_predicates import validate_slice_ready, publish_implementation_complete
from behavior_routing import read_route, validate_plan, production_hashes
from test_coverage_predicates import prepare, semantic_bundle


def fixture(root, present=(True, True)):
    semantic, roots = prepare(root)
    bundle = semantic_bundle()
    base_o, base_a, base_f = bundle["obligations"][0], bundle["acceptances"][0], bundle["failure_intents"][0]
    bundle["obligations"], bundle["acceptances"], bundle["failure_intents"] = [], [], []
    for i in (1, 2):
        o, a, f = deepcopy(base_o), deepcopy(base_a), deepcopy(base_f)
        o.update(obligation_id=f"O-{i}", expected_behavior=f"value({i}) returns {i}")
        a.update(acceptance_id=f"A-{i}", obligation_ids=[f"O-{i}"], assertion_ids=[f"AS-{i}"], red_intent_ids=[f"FI-{i}"])
        f.update(failure_intent_id=f"FI-{i}", acceptance_ids=[f"A-{i}"], failure_id=f"FAIL-{i}")
        bundle["obligations"].append(o); bundle["acceptances"].append(a); bundle["failure_intents"].append(f)
    bundle["final_plan_coverage"] = [{"obligation_id": f"O-{i}", "slice_id": "S1", "acceptance_id": f"A-{i}", "stage_scope": ["red","green","refactor","terminal"]} for i in (1,2)]
    for s in bundle["slices"]:
        s.update(obligation_ids=["O-1","O-2"], acceptance_ids=["A-1","A-2"], failure_intent_ids=["FI-1","FI-2"], production_owners=["candidate.py"], allowed_write_paths=["candidate.py"])
    for c in bundle["agent_contexts"]:
        c.update(obligation_ids=["O-1","O-2"], acceptance_ids=["A-1","A-2"], allowed_paths=["candidate.py"])
    for row in roots:
        if row["root_kind"] == "candidate_tree": row["repository_relative_posix_path"] = "candidate.py"
    sys.path.insert(0, str(TOOLS.parents[1]/"vdd-execution-plan/scripts"))
    from semantic_behavior_contract import SCHEMA, project_intents
    bundle["behavior_routing"] = {"schema": SCHEMA, "intents": project_intents(bundle), "deferred": []}
    semantic.write_text(json.dumps(bundle), encoding="utf-8")
    context = semantic.parent / "agent-context/S1/agent-context.json"
    create_json(context, bundle["agent_contexts"][0])
    source = "import pytest\nfrom candidate import value\n"
    for i in (1,2):
        source += f"@pytest.mark.cer_assertion('AS-{i}')\ndef test_value_{i}():\n actual=value({i})\n if actual!={i}: print('FAILURE_ID:FAIL-{i}')\n assert actual=={i}\n"
    (root/"tests/test_one.py").write_text(source, encoding="utf-8")
    implement(root, present)
    return semantic, roots


def implement(root, present):
    # Distinct source lengths avoid stale Python bytecode when state flips quickly.
    values = {1: 1 if present[0] else -10001, 2: 2 if present[1] else -20002}
    (root/"candidate.py").write_text(f"def value(kind):\n return {values!r}[kind]\n", encoding="utf-8")


def test_runtime_hash_closure_ignores_non_obligation_dependency_labels(tmp_path: Path) -> None:
    semantic, _roots = fixture(tmp_path)
    bundle = json.loads(semantic.read_text(encoding="utf-8"))
    bundle["obligations"][0]["depends_on"] = ["SM-6.1 governance label"]
    from semantic_behavior_contract import project_intents
    bundle["behavior_routing"]["intents"] = project_intents(bundle)
    assert production_hashes(tmp_path, bundle, "S1") == {"candidate.py": sha256_bytes((tmp_path / "candidate.py").read_bytes())}


def execute(root, semantic, stage, route=None, *, run_name="RUN-1", materialize_only=False):
    bundle = json.loads(semantic.read_text())
    run = root/run_name
    descriptor = materialize_descriptor(bundle=bundle, slice_id="S1", stage=stage, run_id=run.name,
        candidate_hash=sha256_bytes((root/"candidate.py").read_bytes()),
        argv=[sys.executable,"-m","pytest","tests/test_one.py","-q"], cwd=".", timeout_seconds=10,
        target_refs=["tests/test_one.py"], fixture_refs=["fixture.txt"], routing_result=route)
    descriptor_path = run/"descriptors"/(stage+".json")
    if not descriptor_path.exists():
        create_json(descriptor_path, descriptor)
    if materialize_only:
        return descriptor
    return execute_stage(workspace=root, semantic_plan=semantic, run_dir=run,
        descriptor_path=run/"descriptors"/(stage+".json"), profile_identity="standard")


def close(root, semantic, roots, route):
    run = root/"RUN-1"
    ready_path = run/"ready.json"
    execute(root, semantic, "terminal", route, materialize_only=True)
    ready = validate_slice_ready(workspace=root, semantic_plan=semantic, run_root=run, slice_id="S1",
        snapshot_roots=roots, source_commit="TEST", out=ready_path)
    assert execute(root, semantic, "terminal", route)["predicate_result"]
    predecessor={"slice_id":"S1","run_root":"RUN-1","result_ref":"RUN-1/ready.json","result_sha256":sha256_value(ready)}
    return publish_implementation_complete(workspace=root, semantic_plan=semantic, predecessors=[predecessor],
        snapshot_roots=roots, source_commit="TEST", out=run/"complete.json")


def test_all_present_closes_regression_without_red_or_implementation(tmp_path):
    semantic, roots = fixture(tmp_path)
    route=execute(tmp_path,semantic,"probe")
    assert [r["disposition"] for r in route["behavior_dispositions"]] == ["present","present"]
    assert route["runtime_edges"] == []
    assert execute(tmp_path,semantic,"regression",route)["predicate_result"]
    result=close(tmp_path,semantic,roots,route)
    assert result["status"]=="pass"
    assert {x["stage"] for x in result["runtime_closure_tuples"]} == {"regression","terminal"}
    assert not (tmp_path/"RUN-1/descriptors/red.json").exists()


def test_mixed_slice_preserves_both_obligations_and_closes_both_paths(tmp_path):
    semantic, roots=fixture(tmp_path,(True,False))
    route=execute(tmp_path,semantic,"probe")
    assert [r["disposition"] for r in route["behavior_dispositions"]] == ["present","missing"]
    red=execute(tmp_path,semantic,"red",route)
    assert red["predicate_result"]
    assert {r["acceptance_id"] for r in red["runtime_edges"]} == {"A-2"}
    implement(tmp_path,(True,True))
    for stage in ("green","refactor","regression"):
        assert execute(tmp_path,semantic,stage,route)["predicate_result"]
    result=close(tmp_path,semantic,roots,route)
    tuples={(x["acceptance_id"],x["stage"]) for x in result["runtime_closure_tuples"]}
    assert tuples=={("A-1","regression"),("A-1","terminal"),("A-2","red"),("A-2","green"),("A-2","refactor"),("A-2","terminal")}


def test_regressed_present_behavior_blocks_and_does_not_authorize_red(tmp_path):
    semantic,_=fixture(tmp_path)
    route=execute(tmp_path,semantic,"probe")
    implement(tmp_path,(True,False))
    result=execute(tmp_path,semantic,"regression",route)
    assert not result["predicate_result"] and result["runtime_edges"]==[]
    with pytest.raises(ValueError,match="no-obligations-for-stage"):
        execute(tmp_path,semantic,"red",route)


def test_stale_regression_cannot_close_after_production_change(tmp_path):
    semantic,roots=fixture(tmp_path)
    route=execute(tmp_path,semantic,"probe")
    assert execute(tmp_path,semantic,"regression",route)["predicate_result"]
    implement(tmp_path,(True,False))
    with pytest.raises(ValueError,match="current-production-or-plan-stale"):
        validate_slice_ready(workspace=tmp_path,semantic_plan=semantic,run_root=tmp_path/"RUN-1",slice_id="S1",
            snapshot_roots=roots,source_commit="TEST",out=tmp_path/"RUN-1/ready.json")


@pytest.mark.parametrize("failure",["setup", "skip", "mixed-cases"])
def test_unverifiable_probe_never_authorizes_implementation(tmp_path,failure):
    semantic,_=fixture(tmp_path)
    path=tmp_path/"tests/test_one.py"
    s=path.read_text()
    if failure=="setup": s="raise ImportError('environment')\n"+s
    elif failure=="skip": s=s.replace("def test_value_1", "@pytest.mark.skip(reason='not observed')\ndef test_value_1")
    else: s += "@pytest.mark.cer_assertion('AS-1')\ndef test_extra():\n print('FAILURE_ID:FAIL-1')\n assert False\n"
    path.write_text(s,encoding="utf-8")
    route=execute(tmp_path,semantic,"probe")
    assert not route["predicate_result"]
    assert any(r["disposition"]=="unverifiable" for r in route["behavior_dispositions"])
    with pytest.raises(ValueError):
        read_route(tmp_path,json.loads(semantic.read_text()),tmp_path/"RUN-1","S1")


def test_forged_present_disposition_cannot_skip_missing_behavior(tmp_path):
    semantic,_=fixture(tmp_path,(True,False))
    route=execute(tmp_path,semantic,"probe")
    route["behavior_dispositions"][1]["disposition"]="present"
    (tmp_path/"RUN-1/canonical-evidence/probe/stage-result.v2.json").write_text(json.dumps(route))
    with pytest.raises(ValueError,match="mutated-disposition"):
        execute(tmp_path,semantic,"regression",route)


@pytest.mark.parametrize("kind",["blocking","external-owner"])
def test_deferred_false_cannot_remove_current_obligation(tmp_path,kind):
    semantic,_=fixture(tmp_path)
    bundle=json.loads(semantic.read_text())
    bundle["behavior_routing"]["deferred"]=[{"type":kind,"reason":"later","resolution_owner":"maintainer",
        "resolution_stage":"acceptance","affected_obligation_ids":["O-1"],"blocking":False}]
    with pytest.raises(ValueError,match="blocks-current-scope"):
        validate_plan(bundle)


def test_implementation_strategy_can_be_deferred_but_proof_cannot(tmp_path):
    semantic,_=fixture(tmp_path)
    bundle=json.loads(semantic.read_text())
    row={"type":"implementation-resolvable","reason":"choose local data structure","resolution_owner":"implementation-worker",
         "resolution_stage":"implementation","affected_obligation_ids":["O-1"]}
    bundle["behavior_routing"]["deferred"]=[row]
    validate_plan(bundle)
    row["resolution_stage"]="acceptance"
    with pytest.raises(ValueError,match="proof-or-write-contract-unresolved"):
        validate_plan(bundle)


def test_deleting_coverage_is_not_a_deferred_escape(tmp_path):
    semantic,_=fixture(tmp_path)
    bundle=json.loads(semantic.read_text())
    bundle["final_plan_coverage"].pop()
    with pytest.raises(ValueError,match="coverage-gap"):
        validate_plan(bundle)


def test_stable_cli_present_route_freezes_terminal_before_q7(tmp_path,monkeypatch,capsys):
    import stable_runner
    semantic,roots=fixture(tmp_path)
    monkeypatch.setattr(stable_runner,"ROOT",tmp_path)
    run=tmp_path/"RUN-1"
    roots_path=tmp_path/"roots.json"
    roots_path.write_text(json.dumps(roots),encoding="utf-8")
    def invoke(action, *extra):
        monkeypatch.setattr(sys,"argv",["quick-dev", "--plan",str(semantic.parent),"--slice","S1",
            "--run-dir",str(run),"--action",action,"--profile","standard",*extra])
        code=stable_runner.main()
        output=json.loads(capsys.readouterr().out)
        assert code==0, output
        return output
    authored=invoke("author-red")
    assert authored["required_next_action"]=="run-probe"
    observed=invoke("run-probe")
    assert observed["required_next_action"]=="run-regression"
    assert invoke("run-regression")["predicate_result"]
    ready=invoke("validate-slice","--snapshot-roots",str(roots_path),"--source-commit","TEST","--out",str(run/"ready.json"))
    assert (run/"descriptors/terminal.json").is_file()
    assert invoke("run-terminal")["predicate_result"]
    pred=tmp_path/"predecessors.json"
    pred.write_text(json.dumps([{"slice_id":"S1","run_root":"RUN-1","result_ref":"RUN-1/ready.json","result_sha256":sha256_value(ready)}]),encoding="utf-8")
    complete=invoke("implementation-complete","--snapshot-roots",str(roots_path),"--source-commit","TEST",
        "--predecessors",str(pred),"--out",str(run/"complete.json"))
    assert complete["status"]=="pass"
    assert not (run/"descriptors/red.json").exists()


def test_probe_production_drift_cannot_authorize_missing_red(tmp_path):
    semantic,_=fixture(tmp_path,(False,False))
    route=execute(tmp_path,semantic,"probe")
    implement(tmp_path,(True,False))
    with pytest.raises(ValueError,match="probe-production-changed"):
        execute(tmp_path,semantic,"red",route)


def test_green_cannot_borrow_present_assertion_or_change_disposition(tmp_path):
    semantic,_=fixture(tmp_path,(True,False))
    route=execute(tmp_path,semantic,"probe")
    assert execute(tmp_path,semantic,"red",route)["predicate_result"]
    implement(tmp_path,(True,True))
    descriptor=execute(tmp_path,semantic,"green",route,materialize_only=True)
    descriptor["acceptance_assertions"][0].update(acceptance_id="A-1",assertion_id="AS-1")
    path=tmp_path/"RUN-1/descriptors/green.json"
    path.write_text(json.dumps(descriptor),encoding="utf-8")
    with pytest.raises(ValueError,match="stage-assertion-universe"):
        execute_stage(workspace=tmp_path,semantic_plan=semantic,run_dir=tmp_path/"RUN-1",descriptor_path=path,profile_identity="standard")


def test_existing_tests_with_new_assertion_ids_route_through_bounded_author(tmp_path,monkeypatch):
    import stable_runner
    semantic,_=fixture(tmp_path)
    bundle=json.loads(semantic.read_text(encoding="utf-8"))
    bundle["slices"][0]["execution_snapshot_paths"]=["tests/test_one.py"]
    semantic.write_text(json.dumps(bundle),encoding="utf-8")
    monkeypatch.setattr(stable_runner,"ROOT",tmp_path)
    test=tmp_path/"tests/test_one.py"
    bound=test.read_text()
    test.write_text(bound.replace("@pytest.mark.cer_assertion('AS-1')\n", ""),encoding="utf-8")
    before=(tmp_path/"candidate.py").read_bytes()
    calls=[]
    def author(**kwargs):
        calls.append(kwargs["slice_id"])
        test.write_text(bound,encoding="utf-8")
        return {"status":"worker-changes-valid","changed_paths":["tests/test_one.py"]}
    monkeypatch.setattr(stable_runner,"run_red_author",author)
    result=stable_runner.q2_author_red(semantic=semantic,slice_id="S1",run_dir=tmp_path/"RUN-1",
        profile="standard",timeout_seconds=10,backend="offline-disabled")
    assert calls==["S1"] and result["required_next_action"]=="run-probe"
    assert (tmp_path/"candidate.py").read_bytes()==before


def test_materialized_planned_test_with_required_assertion_does_not_reinvoke_author(tmp_path,monkeypatch):
    import stable_runner
    semantic,_=fixture(tmp_path)
    bundle=json.loads(semantic.read_text(encoding="utf-8"))
    bundle["slices"][0]["planned_new_files"]=["tests/test_one.py"]
    semantic.write_text(json.dumps(bundle),encoding="utf-8")
    monkeypatch.setattr(stable_runner,"ROOT",tmp_path)
    calls=[]
    monkeypatch.setattr(stable_runner,"run_red_author",lambda **kwargs: calls.append(kwargs) or {"status":"worker-changes-valid"})
    result=stable_runner.q2_author_red(semantic=semantic,slice_id="S1",run_dir=tmp_path/"RUN-1",
        profile="standard",timeout_seconds=10,backend="offline-disabled")
    assert calls==[]
    assert result["worker"]["status"]=="worker-not-required"
    assert result["required_next_action"]=="run-probe"


def test_fixture_assertion_mapping_does_not_reinvoke_author(tmp_path,monkeypatch):
    import stable_runner
    semantic,_=fixture(tmp_path)
    bundle=json.loads(semantic.read_text(encoding="utf-8"))
    bundle["slices"][0]["execution_snapshot_paths"]=["tests/test_one.py","tests/test_fixture.py"]
    semantic.write_text(json.dumps(bundle),encoding="utf-8")
    test=tmp_path/"tests/test_one.py"
    test.write_text(test.read_text(encoding="utf-8").replace("@pytest.mark.cer_assertion('AS-2')\n",""),encoding="utf-8")
    (tmp_path/"tests/test_fixture.py").write_text("import pytest\n@pytest.mark.cer_assertion('AS-2')\ndef test_fixture_mapping():\n assert True\n",encoding="utf-8")
    monkeypatch.setattr(stable_runner,"ROOT",tmp_path)
    calls=[]
    monkeypatch.setattr(stable_runner,"run_red_author",lambda **kwargs: calls.append(kwargs) or {"status":"worker-changes-valid"})
    result=stable_runner.q2_author_red(semantic=semantic,slice_id="S1",run_dir=tmp_path/"RUN-1",
        profile="standard",timeout_seconds=10,backend="offline-disabled")
    assert calls==[]
    assert result["worker"]["status"]=="worker-not-required"


def test_change_impact_invalidates_regression_observations(tmp_path):
    from current_router import recommendation
    semantic,_=fixture(tmp_path)
    result=recommendation(bundle=json.loads(semantic.read_text()),slice_id="S1",state={"state":"regression-observed"},
        changed_paths=["candidate.py"],change_kinds=[],profile="standard",
        observation_index=[{"observation_id":"OBS-REG","stage":"regression","slice_id":"S1"}])
    assert "regression" in result["invalidated_stages"]
    assert result["invalidated_observations"]==["OBS-REG"]
    assert result["reusable_observations"]==[]


def test_present_route_still_runs_declared_extra_regressions(tmp_path):
    semantic,_=fixture(tmp_path)
    bundle=json.loads(semantic.read_text())
    bundle["agent_contexts"][0]["validation_commands"].append([sys.executable,"-c","raise SystemExit(7)"])
    semantic.write_text(json.dumps(bundle),encoding="utf-8")
    route=execute(tmp_path,semantic,"probe")
    with pytest.raises(ValueError,match="regression"):
        execute(tmp_path,semantic,"regression",route)
    assert not (tmp_path/"RUN-1/canonical-evidence/regression/stage-result.v2.json").exists()


def test_mixed_plan_closes_explicit_slices_without_number_order(tmp_path):
    semantic,roots=fixture(tmp_path,(True,False))
    bundle=json.loads(semantic.read_text())
    old_slice,old_context=deepcopy(bundle["slices"][0]),deepcopy(bundle["agent_contexts"][0])
    bundle["slices"],bundle["agent_contexts"]=[],[]
    names={1:"Zeta",2:"Alpha"}
    (tmp_path/"src").mkdir()
    for i in (1,2):
        sid=names[i]
        selected=deepcopy(old_slice)
        selected.update(slice_id=sid,obligation_ids=[f"O-{i}"],acceptance_ids=[f"A-{i}"],failure_intent_ids=[f"FI-{i}"],
            production_owners=[f"src/owner{i}.py"],allowed_write_paths=[f"src/owner{i}.py"])
        context=deepcopy(old_context)
        context.update(slice_id=sid,obligation_ids=[f"O-{i}"],acceptance_ids=[f"A-{i}"],allowed_paths=[f"src/owner{i}.py"],
            validation_commands=[[sys.executable,"-m","pytest",f"tests/test_one.py::test_value_{i}","-q"]])
        bundle["slices"].append(selected);bundle["agent_contexts"].append(context)
        bundle["final_plan_coverage"][i-1]["slice_id"]=sid
        (tmp_path/f"src/owner{i}.py").write_text(f"def value():\n return {i if i==1 else -10000}\n",encoding="utf-8")
    from semantic_behavior_contract import project_intents
    bundle["obligations"][1]["depends_on"]=["O-1"]
    bundle["behavior_routing"]["intents"]=project_intents(bundle)
    semantic.write_text(json.dumps(bundle),encoding="utf-8")
    test=tmp_path/"tests/test_one.py"
    source=test.read_text().replace("from candidate import value","from src import owner1, owner2").replace("actual=value(1)","actual=owner1.value()").replace("actual=value(2)","actual=owner2.value()")
    test.write_text(source,encoding="utf-8")
    roots=[r for r in roots if r["root_kind"] not in {"candidate_tree","descriptor"}]
    roots.extend([
        {"root_kind":"candidate_tree","repository_relative_posix_path":"src","inclusion_reason":"current production tree"},
        {"root_kind":"descriptor","repository_relative_posix_path":"descriptor-index.json","inclusion_reason":"explicit descriptor set"},
    ])
    def stage(i,name,route=None,materialize=False):
        sid=names[i];run=tmp_path/"runs"/sid;path=run/"descriptors"/(name+".json")
        if not path.exists():
            descriptor=materialize_descriptor(bundle=bundle,slice_id=sid,stage=name,run_id=sid,
                candidate_hash=sha256_value(production_hashes(tmp_path,bundle,sid)),argv=bundle["agent_contexts"][i-1]["validation_commands"][0],
                cwd=".",timeout_seconds=10,target_refs=["tests/test_one.py"],fixture_refs=["fixture.txt"],routing_result=route)
            create_json(path,descriptor)
        if not materialize:
            return execute_stage(workspace=tmp_path,semantic_plan=semantic,run_dir=run,descriptor_path=path,profile_identity="standard")
    routes={i:stage(i,"probe") for i in (1,2)}
    assert stage(2,"red",routes[2])["predicate_result"]
    (tmp_path/"src/owner2.py").write_text("def value():\n return 2\n",encoding="utf-8")
    for name in ("green","refactor"):
        assert stage(2,name,routes[2])["predicate_result"]
    assert stage(1,"regression",routes[1])["predicate_result"]
    for i in (1,2): stage(i,"terminal",routes[i],materialize=True)
    descriptor_index={}
    for i in (1,2):
        for name in (("probe","regression","terminal") if i==1 else ("probe","red","green","refactor","terminal")):
            path=tmp_path/"runs"/names[i]/"descriptors"/(name+".json")
            descriptor_index[path.relative_to(tmp_path).as_posix()]=sha256_bytes(path.read_bytes())
    create_json(tmp_path/"descriptor-index.json",descriptor_index)
    predecessors=[]
    for i in (2,1):
        sid=names[i];run=tmp_path/"runs"/sid
        ready=validate_slice_ready(workspace=tmp_path,semantic_plan=semantic,run_root=run,slice_id=sid,
            snapshot_roots=roots,source_commit="TEST",out=run/"ready.json")
        assert stage(i,"terminal",routes[i])["predicate_result"]
        predecessors.append({"slice_id":sid,"run_root":f"runs/{sid}","result_ref":f"runs/{sid}/ready.json","result_sha256":sha256_value(ready)})
    result=publish_implementation_complete(workspace=tmp_path,semantic_plan=semantic,predecessors=predecessors,
        snapshot_roots=roots,source_commit="TEST",out=tmp_path/"complete.json")
    assert result["status"]=="pass" and len(result["runtime_closure_tuples"])==6
