"""ADR-0041: opt-in primary binding repair, with no business/model execution."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from quick_dev_handoff import repair_static_primary_bindings
from test_public_source_cache_resume import fixture, run_public

REPO = SCRIPTS.parents[3]
TARGET = 'tests/test_compile.py'


def install_reader(root):
    tools = root / '.agents/skills/quick-dev-tdd-adapter/tools'
    tools.mkdir(parents=True, exist_ok=True)
    for name in ['case_selection.py', 'runtime_evidence.py']:
        shutil.copy2(REPO / '.agents/skills/quick-dev-tdd-adapter/tools' / name, tools / name)


def small(root):
    install_reader(root)
    target = root / TARGET
    target.parent.mkdir(exist_ok=True)
    target.write_text('import pytest\n@pytest.mark.cer_assertion("ASSERT-X")\ndef test_compile(): pass\n')
    return {'acceptances':[{'acceptance_id':'A','assertion_ids':['ASSERT-X']}],
        'slices':[{'slice_id':s, 'acceptance_ids':['A'], 'production_owners':['src/owner.py'],
                   'execution_snapshot_paths':[TARGET], 'allowed_write_paths':['src/owner.py'],
                   'rollback_scope':{'production_paths':['src/owner.py']}}
                  for s in ['S1','S12','S3']],
        'agent_contexts':[{'slice_id':s, 'forbidden_paths':[], 'validation_commands':[
            ['python3','-B','-m','pytest',TARGET,'-q','-k','test_compile'], ['python3','extra.py']]}
            for s in ['S1','S12','S3']]}


def test_only_explicit_primary_fields_change(tmp_path):
    old = small(tmp_path); before = deepcopy(old)
    new, delta = repair_static_primary_bindings(old, tmp_path, ['S1','S12'])
    assert old == before
    for c in new['agent_contexts']:
        if c['slice_id'] in {'S1','S12'}:
            assert c['validation_commands'][0] == ['python3','-B','-m','pytest',TARGET,'-q']
            c['validation_commands'][0] += ['-k','test_compile']
    assert new == old  # every oracle, write boundary, extra command and other slice
    assert delta['added_expected_red_intents'] == []


@pytest.mark.parametrize('case',['unknown','duplicate','empty','missing','unbound','owner','rollback',
    'forbidden','unsafe','symlink','parent-symlink','options','expression','wrong-filter','mapping','launcher'])
def test_invalid_repair_never_mutates_original(tmp_path, case):
    b = small(tmp_path); ids = ['S1']; c = b['agent_contexts'][0]; s = b['slices'][0]
    if case == 'unknown': ids = ['S4']
    elif case == 'duplicate': ids = ['S1','S1']
    elif case == 'empty': ids = []
    elif case == 'missing': (tmp_path/TARGET).unlink()
    elif case == 'unbound': s['execution_snapshot_paths'] = []
    elif case == 'owner': s['production_owners'] = [TARGET]
    elif case == 'rollback': s['rollback_scope']['production_paths'] = [TARGET]
    elif case == 'forbidden': c['forbidden_paths'] = ['tests']
    elif case == 'unsafe': c['validation_commands'][0][4] = '../test_escape.py'
    elif case == 'symlink':
        (tmp_path/TARGET).unlink(); (tmp_path/TARGET).symlink_to(tmp_path/'missing')
    elif case == 'parent-symlink':
        (tmp_path/TARGET).unlink(); (tmp_path/'tests').rmdir(); (tmp_path/'other').mkdir()
        (tmp_path/'other/test_compile.py').write_text('')
        (tmp_path/'tests').symlink_to(tmp_path/'other', target_is_directory=True)
    elif case == 'options': c['validation_commands'][0].insert(5, '--disable-warnings')
    elif case == 'expression': c['validation_commands'][0][-1] = 'test_compile or not test_other'
    elif case == 'wrong-filter': c['validation_commands'][0][-1] = 'test_other'
    elif case == 'mapping': b['acceptances'][0]['assertion_ids'] = ['ASSERT-MISSING']
    elif case == 'launcher': c['validation_commands'][0][0] = 'arbitrary-python'
    before = deepcopy(b)
    with pytest.raises(ValueError): repair_static_primary_bindings(b, tmp_path, ids)
    assert b == before


def test_public_successor_preserves_every_other_field_and_native_gates(tmp_path):
    req, expected = fixture(tmp_path); install_reader(tmp_path)
    expected['v3']['slice_hints'][0]['validation_commands'] = [
        ['python3','-B','-m','pytest',TARGET,'-q','-k','test_compile']]
    subprocess.run(['git','add','requirements.md','src/compiler.py'],cwd=tmp_path,check=True)
    subprocess.run(['git','-c','user.name=Fixture','-c','user.email=test@example.invalid',
                    'commit','-qm','fixture inputs'],cwd=tmp_path,check=True)
    initial, _, _ = run_public(tmp_path,expected,'initial')
    assert initial['status'] == 'plan-ready', initial
    old = json.loads((tmp_path/'plan/semantic-plan-bundle.v1.json').read_text())
    cmd = [sys.executable,'-B',str(tmp_path/'scripts/vdd/compile_plan.py'),
        '--requirements',str(req),'--out-dir',str(tmp_path/'successor'),
        '--repair-quick-dev-handoff-from',str(tmp_path/'plan'),'--handoff-static-primary-slice','S1']
    result = subprocess.run(cmd,cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert result.returncode == 0, (result.stdout,result.stderr)
    new = json.loads((tmp_path/'successor/semantic-plan-bundle.v1.json').read_text())
    new['agent_contexts'][0]['validation_commands'][0] += ['-k','test_compile']
    assert new == old
    report = json.loads((tmp_path/'successor/handoff-repair.v1.json').read_text())
    assert report['reused_stages'] == ['V1','V4'] and report['model_called'] is False
    assert all(v['valid'] for v in report['checks'].values())
    # Same public path must reject corrupted predecessor lineage before publication.
    state = tmp_path/'plan/compiler-state.v1.json'
    body = json.loads(state.read_text()); body['semantic_plan_sha256'] = 'wrong'
    state.write_text(json.dumps(body)); cmd[cmd.index('--out-dir')+1] = str(tmp_path/'rejected')
    bad = subprocess.run(cmd,cwd=tmp_path,capture_output=True,text=True,timeout=10)
    assert bad.returncode == 1 and not (tmp_path/'rejected').exists()


@pytest.mark.parametrize('extra',[[],['--runtime-red-intent','FI-X'],['--handoff-planned-test',TARGET],
    ['--handoff-windows-launcher-slice','S1'],['--handoff-test-root','tests/other']])
def test_cli_rejects_unscoped_or_combined_modes(tmp_path, extra):
    fixture(tmp_path)
    cmd = [sys.executable,'-B',str(tmp_path/'scripts/vdd/compile_plan.py'),
        '--requirements',str(tmp_path/'requirements.md'),'--out-dir',str(tmp_path/'new'),
        '--handoff-static-primary-slice','S1']
    if extra: cmd += ['--repair-quick-dev-handoff-from',str(tmp_path/'missing'),*extra]
    result = subprocess.run(cmd,cwd=tmp_path,capture_output=True,text=True,timeout=10)
    assert result.returncode == 2 and not (tmp_path/'new').exists()
