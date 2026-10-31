"""ADR-0041/0048 and approved unpublished-classification boundary: no caller self-approval."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
import semantic_compiler as sc
from test_ch456_v3_expected_red_eligibility import _obligation


def module():
    # A missing public capability is an explicit functional assertion, not an
    # import/setup failure masquerading as RED.
    assert (SCRIPTS/'semantic_v1_classification_repair.py').is_file(), 'No source-checked unpublished V1 classification capability exists'
    return importlib.import_module('semantic_v1_classification_repair')


def test_required_source_checked_classification_capability_exists():
    module()

from test_planning_observation_resume import delivered, published_vdd_base, run_public
from test_plain_repair_observation_compat import correction
import semantic_phase_source_scope as phase


def request_value(root, original):
    req = root/'requirements.md'
    return {'schema':'vdd.v1-classification-repair.v1','authorizes':[],
        'repository_root':str(root),'task_id':'execution-plans/plan',
        'requirements_sha256':sc.sha256_bytes(req.read_bytes()),
        'source_index_sha256':sc.build_source_index(root,req,[])['sha256'],
        'source_scope':phase.description(root),
        'original_obligations_sha256':sc.sha256_value(sorted(original,key=lambda o:(o['requirement_id'],o['obligation_id']))),
        'kind_changes':{original[0]['obligation_id']:'constraint'}}


@pytest.mark.parametrize('delivered',['classification'],indirect=True)
@pytest.mark.parametrize('out_style',['absolute','relative'])
def test_public_source_checked_classification_with_plain_repair_and_reference(delivered,out_style):
    root,expected,_,_=delivered
    original=sc._normalize_obligation({'requirement_id':'FR-1','source_ref':'requirements.md#FR-1'},expected['v1-FR-1']['obligations'][0])
    value=request_value(root,[original]);path=root/'logs/classification.json';path.write_text(json.dumps(value))
    _,_,options=correction(delivered)
    record=root/'execution-plans/plan/execution-record.md';before=record.read_bytes()
    code,result,seen,stderr,stdout=run_public(
        delivered,options=[*options,'--v1-classification-repair',str(path)],
        out_dir='execution-plans/plan' if out_style=='relative' else None)
    argv=json.loads((root/'logs/resume/argv.json').read_text())
    assert argv.count('--out-dir')==1
    assert argv[argv.index('--out-dir')+1]==(
        'execution-plans/plan' if out_style=='relative' else str(root/'execution-plans/plan'))
    assert code==0 and result['status']=='plan-ready',(result,stderr,stdout)
    bundle=json.loads((root/'execution-plans/plan/semantic-plan-bundle.v1.json').read_text())
    assert bundle['obligations']==[{**original,'obligation_kind':'constraint'}]
    assert seen
    assert any('requested_kind_changes' in payload for _,payload in seen)
    assert record.read_bytes().startswith(before)


@pytest.fixture
def tiny(tmp_path):
    req=tmp_path/'requirements.md';req.write_text('# FR-1\nThe delivery report retains every original ID and its unproved limits.\n')
    plan=tmp_path/'execution-plans/plan';plan.mkdir(parents=True);(plan/'execution-record.md').write_text('Existing native task record.\n')
    index=sc.build_source_index(tmp_path,req,[])
    raw=_obligation('unused',kind='quality',requirement_type='Platform')
    raw['source_refs']=['requirements.md#FR-1']
    original=[sc._normalize_obligation(index['entries'][0],raw)]
    value=request_value(tmp_path,original);path=tmp_path/'classification.json';path.write_text(json.dumps(value))
    return tmp_path,req,plan,index,original,value,path


def judge_reply(original,kind='constraint'):
    fields=['source_refs','subject','trigger','state_before','state_after','expected_behavior','observable_result',
            'forbidden_result','requirement_type','obligation_kind','unresolved_fragments','status','depends_on']
    return {'obligations':[{**{k:deepcopy(o[k]) for k in fields},'obligation_kind':kind} for o in original]}


def test_real_original_domain_and_every_nonkind_field_are_retained(tiny,monkeypatch):
    root,req,out,index,original,value,path=tiny;m=module();seen=[]
    def actor(**kwargs):
        seen.append(kwargs);return judge_reply(original)
    monkeypatch.setattr(sc,'invoke_worker',actor)
    loaded=m.load(path,root=root,requirements=req,out_dir=out)
    result=m.apply(loaded,root=root,requirements=req,out_dir=out,source_index=index,original=original)
    assert result==[{**original[0],'obligation_kind':'constraint'}] and original[0]['obligation_kind']=='quality'
    assert seen[0]['stage'].startswith('v1-classification-review-')
    assert 'execution_context_text' not in seen[0]['payload']['source']
    assert 'repository_root' not in seen[0]['payload'] and 'task_id' not in seen[0]['payload']
    assert len(list((out/'.compiler-work/v1-classification-repairs').glob('*.json')))==1


@pytest.mark.parametrize('defect',['root','task','req','index','scope','published','shape','kind','unknown','old-domain'])
def test_binding_and_typed_inputs_reject_before_judgment(tiny,monkeypatch,defect):
    root,req,out,index,original,value,path=tiny;m=module()
    if defect=='root':value['repository_root']=str(root/'other')
    elif defect=='task':value['task_id']='execution-plans/other'
    elif defect=='req':value['requirements_sha256']='sha256:'+'0'*64
    elif defect=='index':value['source_index_sha256']='sha256:'+'0'*64
    elif defect=='scope':value['source_scope']={'authorizes':[]}
    elif defect=='published':(out/'semantic-plan-bundle.v1.json').write_text('{}')
    elif defect=='shape':value['requirement_type']='Governance'
    elif defect=='kind':value['kind_changes']={original[0]['obligation_id']:'governance'}
    elif defect=='unknown':value['kind_changes']={'O-UNKNOWN':'constraint'}
    else:value['original_obligations_sha256']='sha256:'+'0'*64
    path.write_text(json.dumps(value));calls=[];monkeypatch.setattr(sc,'invoke_worker',lambda **kw:calls.append(kw))
    with pytest.raises(ValueError,match='V1_CLASSIFICATION_REPAIR_BLOCKED:'):
        loaded=m.load(path,root=root,requirements=req,out_dir=out)
        m.apply(loaded,root=root,requirements=req,out_dir=out,source_index=index,original=original)
    assert not calls


@pytest.mark.parametrize('defect',['quality','status','type','dependency','behavior','drop','duplicate'])
def test_native_judgment_is_required_and_cannot_change_other_fields(tiny,monkeypatch,defect):
    root,req,out,index,original,value,path=tiny;m=module();reply=judge_reply(original)
    if defect=='quality':reply['obligations'][0]['obligation_kind']='quality'
    elif defect=='status':reply['obligations'][0]['status']='deferred'
    elif defect=='type':reply['obligations'][0]['requirement_type']='Governance'
    elif defect=='dependency':reply['obligations'][0]['depends_on']=['OTHER']
    elif defect=='behavior':reply['obligations'][0]['expected_behavior']='Weakened behavior'
    elif defect=='drop':reply['obligations']=[]
    else:reply['obligations']*=2
    monkeypatch.setattr(sc,'invoke_worker',lambda **kw:reply)
    with pytest.raises(ValueError):m.apply(value,root=root,requirements=req,out_dir=out,source_index=index,original=original)
    assert not (out/'.compiler-work/v1-classification-repairs').exists()


def test_semantic_formatting_keeps_existing_native_identity(tiny,monkeypatch):
    from semantic_resume_cache import content_identity
    from semantic_worker_transport_patch import _source_role_contract
    from workflow_unit_budget import worker_input
    root,req,out,index,original,value,path=tiny;m=module();calls=[]
    def actor(**kw):calls.append(kw);return judge_reply(original)
    monkeypatch.setattr(sc,'invoke_worker',actor)
    for pretty in [False,True]:
        path.write_text(json.dumps(value,indent=2 if pretty else None,sort_keys=pretty))
        loaded=m.load(path,root=root,requirements=req,out_dir=out)
        m.apply(loaded,root=root,requirements=req,out_dir=out,source_index=index,original=original)
    a,b=calls
    assert content_identity(a['stage'],a['payload'],a['prompt'],_source_role_contract(a['stage']))==content_identity(b['stage'],b['payload'],b['prompt'],_source_role_contract(b['stage']))
    def prompt(c):return c['prompt']+'\n\nINPUT:\n'+json.dumps(c['payload'])
    assert worker_input(prompt(a),'output-a')==worker_input(prompt(b),'output-b')
    assert len(list((out/'.compiler-work/v1-classification-repairs').glob('*.json')))==1


def test_native_reset_and_default_are_preserved(tiny,monkeypatch):
    import semantic_v3_contract_repair as native
    root,req,out,index,original,value,path=tiny;m=module();base=lambda **kw:deepcopy(original)
    monkeypatch.setattr(sc,'compile_obligations',base)
    monkeypatch.setattr(native,'reset_published_overlays',lambda:setattr(sc,'compile_obligations',base))
    monkeypatch.setattr(sc,'invoke_worker',lambda **kw:judge_reply(original))
    with m.session(value,root=root,requirements=req,out_dir=out):
        native.reset_published_overlays()
        result=sc.compile_obligations(root=root,out_dir=out,source_index=index,worker_cache=None)
        assert result[0]['obligation_kind']=='constraint'
    assert sc.compile_obligations is base
    assert base()[0]['obligation_kind']=='quality'


@pytest.mark.parametrize('delivered',['classification-runtime'],indirect=True)
def test_public_runtime_quality_refusal_is_not_a_classification_approval(delivered):
    root,expected,_,_=delivered
    original=sc._normalize_obligation({'requirement_id':'FR-1','source_ref':'requirements.md#FR-1'},expected['v1-FR-1']['obligations'][0])
    value=request_value(root,[original]);path=root/'logs/classification.json';path.write_text(json.dumps(value));_,_,options=correction(delivered)
    code,result,seen,stderr,_=run_public(delivered,options=[*options,'--v1-classification-repair',str(path)])
    assert code==1 and 'source-unsupported' in result['reason'],(result,stderr)
    assert any('requested_kind_changes' in p for _,p in seen)
    assert not (root/'execution-plans/plan/semantic-plan-bundle.v1.json').exists()


def test_raw_review_cannot_hide_status_changes_behind_v1_normalization(tiny,monkeypatch):
    root,req,out,index,original,value,path=tiny;m=module();reply=judge_reply(original)
    reply['obligations'][0].update(status='deferred',unresolved_fragments=['pending independent witness'])
    monkeypatch.setattr(sc,'invoke_worker',lambda **kw:reply)
    with pytest.raises(ValueError,match='review-changed-frozen-fields'):
        m.apply(value,root=root,requirements=req,out_dir=out,source_index=index,original=original)


@pytest.mark.parametrize('delivered',['classification'],indirect=True)
def test_public_equivalent_format_reuses_native_classification_judge(delivered):
    root,expected,_,_=delivered
    original=sc._normalize_obligation({'requirement_id':'FR-1','source_ref':'requirements.md#FR-1'},expected['v1-FR-1']['obligations'][0])
    value=request_value(root,[original]);path=root/'logs/classification.json';_,_,options=correction(delivered)
    # A real V4 refusal keeps this isolated candidate unpublished. It does not
    # approve any real S2 source or consume an actual S2 compiler budget.
    expected['v4'].update(covered_obligation_ids=[],missing_obligation_ids=[original['obligation_id']],
                          invented_obligation_ids=['O-OUTSIDE'])
    for index in [0,1]:
        path.write_text(json.dumps(value,indent=2 if index else None,sort_keys=bool(index)))
        code,result,seen,stderr,_=run_public(delivered,options=[*options,'--v1-classification-repair',str(path)],session_name='format-'+str(index))
        assert code==1 and result['stage']=='V4',(result,stderr)
        judgments=[p for _,p in seen if 'requested_kind_changes' in p]
        assert len(judgments)==(1 if index==0 else 0)


def test_owned_constraint_guard_has_no_q4_authority(tiny,monkeypatch):
    tools=SCRIPTS.parents[3]/'.agents/skills/quick-dev-tdd-adapter/tools';sys.path.insert(0,str(tools))
    from quick_dev_handoff import handoff_findings
    from case_evidence import contract_for
    from current_router import validate_expected_red
    root,req,out,index,original,value,path=tiny;m=module();monkeypatch.setattr(sc,'invoke_worker',lambda **kw:judge_reply(original))
    changed=m.apply(value,root=root,requirements=req,out_dir=out,source_index=index,original=original)
    bundle={'behavior_routing':{},'obligations':changed,
       'acceptances':[{'acceptance_id':'A1','obligation_ids':[changed[0]['obligation_id']],'assertion_ids':['ASSERT-GUARD'],'red_intent_ids':['F1']}],
       'failure_intents':[{'failure_intent_id':'F1','acceptance_ids':['A1'],'failure_id':'GUARD','failure_family':'artifact-integrity'}],
       'slices':[{'slice_id':'S1','acceptance_ids':['A1'],'production_owners':['src/owner.py'],'execution_snapshot_paths':['tests/test_guard.py'],'planned_new_files':['tests/test_guard.py']}],
       'agent_contexts':[{'slice_id':'S1','validation_commands':[['python','-m','pytest','tests/test_guard.py']],'forbidden_paths':[]}]}
    assert handoff_findings(bundle)==[]
    assert contract_for(bundle,[{'acceptance_id':'A1','assertion_id':'ASSERT-GUARD'}])['bindings'][0]['expected_failure_ids']==[]
    with pytest.raises(ValueError,match='Q4 requires clean expected-red'):
        validate_expected_red({'stage':'red','predicate_result':False,'verification_outcome':'blocked','failure_family':'artifact-integrity'})


@pytest.mark.parametrize('defect',['symlink','traversal'])
def test_input_path_escape_is_rejected(tiny,defect):
    root,req,out,index,original,value,path=tiny;m=module()
    outside=root.parent/'outside-classification.json';outside.write_text(json.dumps(value))
    if defect=='symlink':
        selected=root/'link.json';selected.symlink_to(outside)
    else:selected=root/'..'/'outside-classification.json'
    with pytest.raises(ValueError):m.load(selected,root=root,requirements=req,out_dir=out)


from test_phase_source_scope import approved


def test_current_loaded_scope_and_six_dependency_bytes_are_bound(tmp_path,approved):
    _,req,path,definition=approved
    for name in ['PhaseA.Platform/PhaseA.Platform.csproj','PhaseA.Platform/packages.lock.json']:
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('{}')
    definition['read_paths']=['PhaseA.Platform/PhaseA.Platform.csproj','PhaseA.Platform/packages.lock.json']
    path.write_text(json.dumps(definition));selected=phase.load(tmp_path,req,path)
    plan=tmp_path/'execution-plans/plan';plan.mkdir(parents=True);(plan/'execution-record.md').write_text('Existing native record.')
    raw=_obligation('unused',kind='quality');raw['source_refs']=['requirements.md#FR-1']
    original=[sc._normalize_obligation(sc.build_source_index(tmp_path,req)['entries'][0],raw)]
    m=module()
    with phase.session(tmp_path,selected):
        value=request_value(tmp_path,original);request=tmp_path/'request.json';request.write_text(json.dumps(value))
        assert len(value['source_scope']['inputs'])==6
        assert m.load(request,root=tmp_path,requirements=req,out_dir=plan)==value
        (tmp_path/'PhaseA.Platform/packages.lock.json').write_text('Changed metadata')
        with pytest.raises(ValueError,match='dependency changed'):
            m.load(request,root=tmp_path,requirements=req,out_dir=plan)


@pytest.mark.parametrize('delivered',['classification'],indirect=True)
def test_public_without_plain_v3_repair_preserves_native_reset_and_reference(delivered):
    root,expected,_,_=delivered
    original=sc._normalize_obligation({'requirement_id':'FR-1','source_ref':'requirements.md#FR-1'},expected['v1-FR-1']['obligations'][0])
    path=root/'logs/classification.json';path.write_text(json.dumps(request_value(root,[original])))
    code,result,seen,stderr,_=run_public(delivered,options=['--v1-classification-repair',str(path)])
    assert code==0 and result['status']=='plan-ready',(result,stderr)
    assert seen and all(p.get('planning_source_observations',{}).get('status')=='reference-only' for _,p in seen)


@pytest.mark.parametrize('delivered',['classification'],indirect=True)
def test_public_alternate_modes_cannot_enable_classification(delivered):
    root,expected,_,_=delivered
    original=sc._normalize_obligation({'requirement_id':'FR-1','source_ref':'requirements.md#FR-1'},expected['v1-FR-1']['obligations'][0])
    path=root/'logs/classification.json';path.write_text(json.dumps(request_value(root,[original])))
    _,_,plain=correction(delivered);(root/'extra.md').write_text('Unselected source.')
    cases=[]
    for mode in [['--worker-cache',str(path)],['--recommendation-only'],['--admission-only'],
                 ['--companion',str(root/'extra.md')],['--repair-published-v3-from',str(root/'execution-plans/plan')],
                 ['--repair-quick-dev-handoff-from',str(root/'execution-plans/plan')],
                 ['--v1-reuse-from-plan',str(root/'execution-plans/plan')],
                 ['--v3-contract-repair-addendum',str(path)],['--stop-after','v3']]:
        code,result,seen,stderr,_=run_public(delivered,options=[*plain,'--v1-classification-repair',str(path),*mode],session_name='deny-'+str(len(cases)))
        cases.append({'mode':mode,'actual_returncode':code,'stderr':stderr})
        assert code==2 and result is None and not seen
        assert 'V1 classification repair requires same-target unpublished ordinary resume' in stderr
    (root/'logs/denied-modes.json').write_text(json.dumps(cases,indent=2))


@pytest.mark.parametrize('outside',[False,True])
def test_projection_directory_symlink_cannot_redirect_metadata(tiny,monkeypatch,outside):
    root,req,out,index,original,value,path=tiny;m=module()
    target=(root.parent if outside else root)/'redirected-projections'
    target.mkdir()
    work=out/'.compiler-work';work.mkdir()
    (work/'v1-classification-repairs').symlink_to(target,target_is_directory=True)
    monkeypatch.setattr(sc,'invoke_worker',lambda **kw:judge_reply(original))
    with pytest.raises(ValueError,match='source-scope: symlink path'):
        m.apply(value,root=root,requirements=req,out_dir=out,source_index=index,original=original)
    assert list(target.iterdir())==[]
