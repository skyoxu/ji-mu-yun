"""ADR-0041: declarations-only handoff; no models, business tests or BMAD."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
from quick_dev_handoff import declare_planned_tests
from test_public_source_cache_resume import fixture, run_public

TARGET='tests/test_contract.py'


def git(root,*args):
    return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True,text=True)


def small(root):
    git(root,'init','-q')
    (root/'base.txt').write_text('base')
    git(root,'add','base.txt')
    git(root,'-c','user.name=Fixture','-c','user.email=test@example.invalid','commit','-qm','base')
    return {'slices':[{'slice_id':'S1','production_owners':['src/owner.py'],
                     'rollback_scope':{'production_paths':['src/owner.py']},
                     'execution_snapshot_paths':[TARGET],'planned_new_files':[],
                     'allowed_write_paths':['src/owner.py'],'slice_input_hash':'old'}],
            'agent_contexts':[{'slice_id':'S1','forbidden_paths':[],
                              'selector_intents':[TARGET+'::test_contract'],
                              'validation_commands':[['python3','-B','-m','pytest',TARGET,'-q']]}]}


def test_only_planned_field_and_slice_identity_change_and_idempotent(tmp_path):
    old=small(tmp_path);snapshot=deepcopy(old)
    new,delta=declare_planned_tests(old,tmp_path,[TARGET])
    assert old==snapshot and new['slices'][0]['planned_new_files']==[TARGET]
    assert new['slices'][0]['slice_input_hash']!='old'
    restored=deepcopy(new);restored['slices'][0]['planned_new_files']=[];restored['slices'][0]['slice_input_hash']='old'
    assert restored==old
    assert delta['added_expected_red_intents']==[] and delta['command_dispositions']==[]
    assert declare_planned_tests(new,tmp_path,[TARGET])[0]==new
    assert not (tmp_path/TARGET).exists()


@pytest.mark.parametrize('path',['.','../tests/test_escape.py','/tmp/tests/test_escape.py',
                                 'tests/../test_escape.py','tests//test_escape.py',
                                 'tests\\test_escape.py','C:/tests/test_escape.py',
                                 'tests/config.toml','scripts/production.py','tests/not_a_test.py'])
def test_unsafe_or_non_test_paths_refused(tmp_path,path):
    b=small(tmp_path)
    with pytest.raises(ValueError):declare_planned_tests(b,tmp_path,[path])
    assert b['slices'][0]['planned_new_files']==[]


@pytest.mark.parametrize('case',['unreferenced','no-command','no-selector','forbidden','owner','rollback','existing','symlink','parent-symlink','tracked-deleted','staged-deleted','duplicate'])
def test_denials_before_any_authority_mutation(tmp_path,case):
    b=small(tmp_path);target=tmp_path/TARGET;target.parent.mkdir()
    if case=='unreferenced':b['slices'][0]['execution_snapshot_paths']=[]
    elif case=='no-command':b['agent_contexts'][0]['validation_commands']=[['python3','-m','pytest','tests/test_other.py']]
    elif case=='no-selector':b['agent_contexts'][0]['selector_intents']=['tests/test_other.py::test_other']
    elif case=='forbidden':b['agent_contexts'][0]['forbidden_paths']=['tests']
    elif case=='owner':b['slices'][0]['production_owners']=[TARGET]
    elif case=='rollback':b['slices'][0]['rollback_scope']['production_paths']=[TARGET]
    elif case=='existing':target.write_text('not executed')
    elif case=='symlink':target.symlink_to(tmp_path/'absent-target')
    elif case=='parent-symlink':
        target.parent.rmdir();(tmp_path/'other-tests').mkdir();target.parent.symlink_to(tmp_path/'other-tests',target_is_directory=True)
    elif case in {'tracked-deleted','staged-deleted'}:
        target.write_text('tracked original');git(tmp_path,'add',TARGET)
        git(tmp_path,'-c','user.name=Fixture','-c','user.email=test@example.invalid','commit','-qm','tracked test')
        if case=='staged-deleted':git(tmp_path,'rm',TARGET)
        else:target.unlink()
    before=deepcopy(b)
    with pytest.raises(ValueError):declare_planned_tests(b,tmp_path,[TARGET,TARGET] if case=='duplicate' else [TARGET])
    assert b==before


def test_public_declarations_successor_reuses_semantics_without_workers(tmp_path):
    req,expected=fixture(tmp_path)
    git(tmp_path,'add','requirements.md','src/compiler.py')
    git(tmp_path,'-c','user.name=Fixture','-c','user.email=test@example.invalid','commit','-qm','fixture inputs')
    initial,_,_=run_public(tmp_path,expected,'initial')
    assert initial['status']=='plan-ready',initial
    target='tests/test_compile.py';(tmp_path/target).unlink()  # untracked fixture, not an actual business test
    predecessor=tmp_path/'plan';original=json.loads((predecessor/'semantic-plan-bundle.v1.json').read_text())
    successor=tmp_path/'repaired'
    command=[sys.executable,'-B',str(tmp_path/'scripts/vdd/compile_plan.py'),
             '--requirements',str(req),'--out-dir',str(successor),
             '--repair-quick-dev-handoff-from',str(predecessor),'--handoff-planned-test',target]
    result=subprocess.run(command,cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,(result.stdout,result.stderr)
    native=json.loads(result.stdout);assert native['status']=='plan-ready' and not native['model_called']
    new=json.loads((successor/'semantic-plan-bundle.v1.json').read_text())
    for key in original:
        if key!='slices':assert new[key]==original[key],key
    for old,current in zip(original['slices'],new['slices']):
        assert {k:v for k,v in current.items() if k not in {'planned_new_files','slice_input_hash'}}=={k:v for k,v in old.items() if k not in {'planned_new_files','slice_input_hash'}}
        assert current['planned_new_files']==[target]
    report=json.loads((successor/'handoff-repair.v1.json').read_text())
    assert report['repair_mode']=='declare-planned-tests-only'
    assert report['reused_stages']==['V1','V4'] and not report['model_called']
    assert not list((successor/'.compiler-work').glob('*'))
    assert not (tmp_path/target).exists()


@pytest.mark.parametrize('extra',[[],['--runtime-red-intent','FI-UNKNOWN'],['--handoff-test-root','scripts/sc/tests/another']])
def test_public_option_boundaries(tmp_path,extra):
    fixture(tmp_path)
    command=[sys.executable,'-B',str(tmp_path/'scripts/vdd/compile_plan.py'),'--requirements',str(tmp_path/'requirements.md'),
             '--out-dir',str(tmp_path/'new'),'--handoff-planned-test',TARGET]
    if extra:command+=['--repair-quick-dev-handoff-from',str(tmp_path/'missing'),*extra]
    result=subprocess.run(command,cwd=tmp_path,capture_output=True,text=True,timeout=10)
    assert result.returncode==2 and not (tmp_path/'new').exists()


@pytest.mark.parametrize('path',['.git/tests/test_contract.py','.codex/tests/test_contract.py','.aws/tests/test_contract.py'])
def test_referenced_metadata_paths_still_refused(tmp_path,path):
    b=small(tmp_path)
    b['slices'][0]['execution_snapshot_paths']=[path]
    b['agent_contexts'][0]['validation_commands']=[['python3','-m','pytest',path]]
    b['agent_contexts'][0]['selector_intents']=[path+'::test_contract']
    with pytest.raises(ValueError):declare_planned_tests(b,tmp_path,[path])


def test_missing_child_of_existing_file_is_not_authorable(tmp_path):
    b=small(tmp_path);(tmp_path/'tests').write_text('not a directory')
    with pytest.raises(ValueError,match='ancestor'):declare_planned_tests(b,tmp_path,[TARGET])


def test_partial_declarations_cannot_leave_another_q1_gap(tmp_path):
    b=small(tmp_path);other='tests/test_other.py'
    b['slices'][0]['execution_snapshot_paths'].append(other)
    before=deepcopy(b)
    with pytest.raises(ValueError,match='undeclared missing snapshot'):
        declare_planned_tests(b,tmp_path,[TARGET])
    assert b==before
