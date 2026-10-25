"""ADR-0041: real tiny pytest executions; no model backend or historical receipts."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_cer_behavior_routing import fixture, execute
from runtime_evidence import create_json, load_json, sha256_value
from current_router import materialize_descriptor
from shared_execution import (execute_with_reuse, input_manifest, validate_use,
                              environment_identity, admissible)
from case_evidence import assertion_cases
from regression_gate import run_regression_gate, validate_regression_references


def setup(root):
    semantic, roots = fixture(root)
    bundle = load_json(semantic)
    sibling = deepcopy(bundle['slices'][0]); sibling['slice_id'] = 'S2'
    bundle['slices'].append(sibling)
    sibling = deepcopy(bundle['agent_contexts'][0]); sibling['slice_id'] = 'S2'
    bundle['agent_contexts'].append(sibling)
    semantic.write_text(json.dumps(bundle), encoding='utf-8')
    (root/'.gitignore').write_text('logs/\n__pycache__/\n*.pyc\n', encoding='utf-8')
    subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    return semantic, bundle, roots


def descriptor(bundle, slice_id='S1', stage='regression', run='run1', candidate='a'):
    # The raw execution proof is independent of lifecycle routing; actual public
    # stage/Q7/Q8 integration is exercised separately below.
    return materialize_descriptor(bundle={k:v for k,v in bundle.items() if k != 'behavior_routing'},
        slice_id=slice_id, stage=stage, run_id=run, candidate_hash='sha256:'+candidate*64,
        argv=[sys.executable, '-m', 'pytest', 'tests/test_one.py', '-q'], cwd='.', timeout_seconds=10,
        target_refs=['tests/test_one.py'], fixture_refs=['fixture.txt'])


def run(root, semantic, bundle, desc):
    return execute_with_reuse(workspace=root, bundle=bundle, semantic_plan=semantic,
        run_dir=root/'logs'/desc['run_id'], descriptor=desc, profile='standard')


def measured(monkeypatch):
    import process_executor_v2
    real = process_executor_v2._run_cases_bounded
    calls=[]
    def call(*a, **kw):
        calls.append(1)
        return real(*a, **kw)
    monkeypatch.setattr(process_executor_v2, '_run_cases_bounded', call)
    return calls


def test_cross_slice_terminal_references_one_original_and_keeps_report_identity(tmp_path, monkeypatch):
    semantic,bundle,_ = setup(tmp_path)
    calls=measured(monkeypatch)
    first=run(tmp_path,semantic,bundle,descriptor(bundle))
    other=descriptor(bundle,'S2','terminal','run2', 'b')
    second=run(tmp_path,semantic,bundle,other)
    assert len(calls)==1 and second['process_attempts']==0
    assert first['case_report']==second['case_report']
    assert second['case_report']['run_id']=='run1'
    assert second['descriptor_sha256'] != first['descriptor_sha256']
    assert assertion_cases(other,second)
    assert validate_use(other,second)['run_id']=='run1'


def test_git_only_commit_change_reuses(tmp_path, monkeypatch):
    semantic,bundle,_=setup(tmp_path); calls=measured(monkeypatch)
    run(tmp_path,semantic,bundle,descriptor(bundle))
    subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                    'commit','-qm','fixture'],cwd=tmp_path,check=True)
    second=run(tmp_path,semantic,bundle,descriptor(bundle,'S2','terminal','run2','b'))
    assert second['process_attempts']==0 and len(calls)==1


def test_private_supervisor_routing_does_not_invalidate_test_environment(tmp_path, monkeypatch):
    from workflow_unit_budget import EVENT_ENV, TOTAL_ENV, IDLE_ENV
    semantic, bundle, _ = setup(tmp_path)
    (tmp_path / 'logs').mkdir(exist_ok=True)
    calls = measured(monkeypatch)
    monkeypatch.setenv(EVENT_ENV, str(tmp_path / 'logs' / 'events-a.jsonl'))
    monkeypatch.setenv(TOTAL_ENV, '1800')
    monkeypatch.setenv(IDLE_ENV, '600')
    first = run(tmp_path, semantic, bundle, descriptor(bundle))
    monkeypatch.setenv(EVENT_ENV, str(tmp_path / 'logs' / 'events-b.jsonl'))
    second = run(tmp_path, semantic, bundle, descriptor(bundle, 'S2', 'terminal', 'run2', 'b'))
    assert second['process_attempts'] == 0 and len(calls) == 1
    assert first['case_report'] == second['case_report']


@pytest.mark.parametrize('kind',['code','dependency','test','contract','environment','windows'])
def test_content_or_environment_change_invalidates(tmp_path,monkeypatch,kind):
    semantic,bundle,_=setup(tmp_path); calls=measured(monkeypatch)
    (tmp_path/'helper.py').write_text('VALUE=1\n')
    first=run(tmp_path,semantic,bundle,descriptor(bundle))
    if kind in {'code','dependency','test'}:
        name={'code':'candidate.py','dependency':'helper.py','test':'tests/test_one.py'}[kind]
        with (tmp_path/name).open('a') as stream: stream.write('\n# changed implementation input\n')
    elif kind=='contract':
        bundle['acceptances'][0]['oracle']='changed semantics'
        semantic.write_text(json.dumps(bundle))
    else:
        import shared_execution
        actual=environment_identity()
        if kind=='windows': actual['system']='Windows'
        else: actual['environment']='changed'
        monkeypatch.setattr(shared_execution,'environment_identity',lambda:actual)
    second=run(tmp_path,semantic,bundle,descriptor(bundle,'S2','terminal','run2'))
    assert second['process_attempts']==1 and len(calls)==2


@pytest.mark.parametrize('kind',['missing','tampered','index','receipt'])
def test_original_loss_or_corruption_rejected_at_use_and_closure(tmp_path,monkeypatch,kind):
    semantic,bundle,_=setup(tmp_path); calls=measured(monkeypatch)
    run(tmp_path,semantic,bundle,descriptor(bundle))
    desc=descriptor(bundle,'S2','terminal','run2')
    reused=run(tmp_path,semantic,bundle,desc)
    if kind=='index':
        path=tmp_path/reused['execution_reference']['index_ref']; path.write_text('{}')
    else:
        name='process-receipt.v2.json' if kind=='receipt' else 'stdout.bin'
        path=tmp_path/'logs/run1/canonical-evidence/regression'/name
        if kind=='missing': path.unlink()
        else: path.write_bytes(b'corrupted')
    with pytest.raises((ValueError,KeyError)):
        assertion_cases(desc,reused)
    with pytest.raises((ValueError,KeyError)):
        run(tmp_path,semantic,bundle,descriptor(bundle,'S2','terminal','run3'))
    assert len(calls)==1


def test_case_coverage_cannot_be_filled_by_another_assertion(tmp_path):
    semantic,bundle,_=setup(tmp_path)
    run(tmp_path,semantic,bundle,descriptor(bundle))
    desc=descriptor(bundle,'S2','terminal','run2')
    desc['case_contract']['bindings'][0]['case_ids']=['tests/test_one.py::test_missing']
    desc['case_contract']['bindings'][0]['marker']=None
    receipt=run(tmp_path,semantic,bundle,desc)
    with pytest.raises(ValueError,match='case-missing-or-deselected'):
        assertion_cases(desc,receipt)


@pytest.mark.parametrize('mutation',['fail','timeout','zero','skip','legacy'])
def test_non_success_and_legacy_not_admissible(tmp_path,mutation):
    semantic,bundle,_=setup(tmp_path)
    receipt=run(tmp_path,semantic,bundle,descriptor(bundle))
    if mutation=='fail': receipt['exit_code']=1
    elif mutation=='timeout': receipt['timed_out']=True
    elif mutation=='zero': receipt['case_report']['selected']=[]
    elif mutation=='skip': receipt['case_report']['events'][0]['outcome']='skipped'
    else: receipt.pop('case_report')
    with pytest.raises(ValueError): admissible(receipt)


def test_q6_cross_slice_and_terminal_share_raw_execution(tmp_path,monkeypatch):
    semantic,bundle,_=setup(tmp_path); calls=measured(monkeypatch)
    primary=descriptor(bundle)
    narrow=deepcopy(primary); narrow['argv'][-2]='tests/test_one.py::test_value_1'
    primary_receipt=run(tmp_path,semantic,bundle,narrow)
    for sid in ('S1','S2'):
        context=next(c for c in bundle['agent_contexts'] if c['slice_id']==sid)
        context['validation_commands']=[primary['argv']]
    semantic.write_text(json.dumps(bundle))
    gates=[]
    for sid in ('S1','S2'):
        current=deepcopy(narrow);current['slice_id']=sid
        gate=run_regression_gate(workspace=tmp_path,bundle=bundle,slice_id=sid,profile='standard',
            primary_argv=narrow['argv'],primary_receipt=primary_receipt,timeout_seconds=10,
            out=tmp_path/'logs'/sid/'gate.json',semantic_plan=semantic,primary_descriptor=current)
        gates.append(gate)
        validate_regression_references(tmp_path,gate)
    terminal=run(tmp_path,semantic,bundle,descriptor(bundle,'S2','terminal','terminal'))
    assert len(calls)==2 and terminal['process_attempts']==0
    assert gates[1]['commands'][0]['status']=='covered-by-shared-execution'


def test_duplicate_original_and_reference_requests_are_idempotent(tmp_path,monkeypatch):
    semantic,bundle,_=setup(tmp_path);calls=measured(monkeypatch)
    desc=descriptor(bundle)
    original=run(tmp_path,semantic,bundle,desc)
    assert run(tmp_path,semantic,bundle,desc)==original
    desc=descriptor(bundle,'S2','terminal','second')
    reference=run(tmp_path,semantic,bundle,desc)
    assert run(tmp_path,semantic,bundle,desc)==reference
    assert len(calls)==1


def test_native_terminal_and_q8_accept_reference_but_reject_missing_original(tmp_path,monkeypatch):
    # Use the unmodified public stage dispatcher and Q7/Q8 predicates.
    from coverage_predicates import validate_slice_ready, publish_implementation_complete
    semantic,roots=fixture(tmp_path)
    (tmp_path/'.gitignore').write_text('logs/\n__pycache__/\n*.pyc\n')
    subprocess.run(['git','init','-q'],cwd=tmp_path,check=True)
    subprocess.run(['git','add','.'],cwd=tmp_path,check=True)
    calls=measured(monkeypatch)
    subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                    'commit','-qm','fixture'],cwd=tmp_path,check=True)
    source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=tmp_path,text=True).strip()
    run_name='logs/RUN-1'; run_root=tmp_path/run_name
    for row in roots:
        if row['root_kind']=='descriptor': row['repository_relative_posix_path']=run_name+'/descriptors'
    route=execute(tmp_path,semantic,'probe',run_name=run_name)
    assert execute(tmp_path,semantic,'regression',route,run_name=run_name)['predicate_result']
    execute(tmp_path,semantic,'terminal',route,run_name=run_name,materialize_only=True)
    ready=validate_slice_ready(workspace=tmp_path,semantic_plan=semantic,run_root=run_root,slice_id='S1',
        snapshot_roots=roots,source_commit=source_commit,out=run_root/'ready.json')
    result=execute(tmp_path,semantic,'terminal',route,run_name=run_name)
    assert result['predicate_result']
    receipt=load_json(run_root/'canonical-evidence/terminal/process-receipt.v2.json')
    assert receipt['process_attempts']==0 and len(calls)==2 # probe + regression, no terminal process
    assert execute(tmp_path,semantic,'terminal',route,run_name=run_name)==result
    pred={'slice_id':'S1','run_root':run_name,'result_ref':run_name+'/ready.json','result_sha256':sha256_value(ready)}
    def close(out):
        return publish_implementation_complete(workspace=tmp_path,semantic_plan=semantic,predecessors=[pred],
            snapshot_roots=roots,source_commit=source_commit,out=run_root/out)
    assert close('complete.json')['status']=='pass'
    (run_root/'canonical-evidence/regression/stdout.bin').unlink()
    with pytest.raises(ValueError,match='bound file is missing'):
        close('recheck.json')
    assert len(calls)==2


@pytest.mark.parametrize('kind',['external-read','child-process','failed','timeout'])
def test_unknown_dependencies_and_actual_failures_never_publish_success(tmp_path,kind):
    semantic,bundle,_=setup(tmp_path)
    test=tmp_path/'tests/test_one.py'
    if kind=='external-read':
        (tmp_path/'execution-plans').mkdir()
        (tmp_path/'execution-plans/undeclared.txt').write_text('external input')
        with test.open('a') as stream:
            stream.write("\ndef test_undeclared_read():\n from pathlib import Path\n assert Path('execution-plans/undeclared.txt').read_text()\n")
    elif kind=='child-process':
        with test.open('a') as stream:
            stream.write("\ndef test_child():\n import subprocess, sys\n assert subprocess.run([sys.executable,'-c','pass'],shell=False).returncode==0\n")
    elif kind=='failed':
        with test.open('a') as stream: stream.write('\ndef test_failed():\n assert False\n')
    else:
        with test.open('a') as stream: stream.write('\ndef test_timeout():\n import time\n time.sleep(3)\n')
    desc=descriptor(bundle)
    if kind=='timeout':desc['timeout_seconds']=1
    receipt=run(tmp_path,semantic,bundle,desc)
    assert not (tmp_path/'logs/quick-dev-shared-executions').exists()
    publication=load_json(tmp_path/'logs/run1/canonical-evidence/regression/reuse-publication.v1.json')
    assert publication['published'] is False
    if kind=='external-read': assert 'unbound-read-or-import' in publication['reason']
    elif kind=='child-process': assert 'unobserved-external-effect' in publication['reason']
    elif kind=='timeout': assert receipt['timed_out'] is True
    else: assert receipt['exit_code']!=0


def test_reference_explains_undeclared_dependency_and_os_drift(tmp_path,monkeypatch):
    semantic,bundle,_=setup(tmp_path)
    helper=tmp_path/'implicit_helper.py';helper.write_text('VALUE=1\n')
    run(tmp_path,semantic,bundle,descriptor(bundle))
    desc=descriptor(bundle,'S2','terminal','run2')
    receipt=run(tmp_path,semantic,bundle,desc)
    helper.write_text('VALUE=2\n')
    with pytest.raises(ValueError,match='reuse-dependency-content-changed:implicit_helper.py'):
        validate_use(desc,receipt)
    helper.write_text('VALUE=1\n')
    import shared_execution
    current=environment_identity();current['system']='Windows'
    monkeypatch.setattr(shared_execution,'environment_identity',lambda:current)
    with pytest.raises(ValueError,match='reuse-environment-changed:system'):
        validate_use(desc,receipt)


def test_missing_declared_input_is_a_specific_nonreuse_reason(tmp_path):
    from shared_execution import validate_observed_dependencies
    manifest={"files":{"new.py":None},"environment":{"files":{}},"engine":{}}
    receipt={"case_report":{"dependency_errors":[],"dependency_files":{str(tmp_path/'new.py'):'sha256:'+'a'*64}}}
    with pytest.raises(ValueError,match='reuse-unbound-read-or-import'):
        validate_observed_dependencies(tmp_path,manifest,receipt)
