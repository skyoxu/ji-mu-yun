"""ADR-0041: neutral entry preparation never substitutes for real behavioral RED."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from first_use_entry import prepare_entry, validate_prepared_entry, SCHEMA
from runtime_evidence import sha256_value, create_json
from current_router import materialize_descriptor, validate_expected_red
from stage_pipeline import execute_stage
from test_ch456_full_lifecycle import _bundle


def setup(root):
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    'commit', '--allow-empty', '-qm', 'base'], cwd=root, check=True)
    bundle = _bundle()
    item = bundle['slices'][0]
    item.update(production_owners=['src/subject.py'], allowed_write_paths=['src/subject.py'],
                planned_new_files=['src/subject.py'], execution_snapshot_paths=['tests/test_behavior.py'])
    item['rollback_scope']['production_paths'] = ['src/subject.py']
    bundle['agent_contexts'][0]['forbidden_paths'] = ['blocked/**']
    contract = {'schema': SCHEMA, 'plan_sha256': sha256_value(bundle), 'slice_id': 'S1',
                'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                'entries': [{'path': 'src/subject.py', 'exports': [
                    {'name': 'answer', 'parameters': ['request'], 'keyword_parameters': ['mode']}]}]}
    return bundle, contract, root/'logs/entry.json'


def test_prepare_and_exact_resume_do_not_authorize_implementation(tmp_path):
    b, c, out = setup(tmp_path)
    result = prepare_entry(workspace=tmp_path, bundle=b, slice_id='S1', contract=c, out=out)
    assert result['status'] == 'entry-prepared'
    assert result['authorizes'] == [] and not result['implementation_authorized']
    assert result['tests_executed'] is False
    source = tmp_path/'src/subject.py'
    before = source.read_bytes(), out.read_bytes()
    assert prepare_entry(workspace=tmp_path, bundle=b, slice_id='S1', contract=c, out=out) == result
    assert (source.read_bytes(), out.read_bytes()) == before
    namespace = {}
    exec(source.read_text(), namespace)
    assert namespace['answer']('input', mode='strict') is None
    with pytest.raises(ValueError, match='expected-red'):
        validate_expected_red(result)
    source.write_text('def answer(request, *, mode=None): return 42\n')
    with pytest.raises(ValueError, match='changed before test authoring'):
        validate_prepared_entry(workspace=tmp_path, bundle=b, slice_id='S1', receipt=result)


@pytest.mark.parametrize('mutation', ['not-planned', 'not-owner', 'frozen', 'forbidden', 'body', 'wrong-plan', 'wrong-slice', 'existing', 'tracked', 'duplicate'])
def test_prepare_rejects_unbounded_input_before_writing(tmp_path, mutation):
    b, c, out = setup(tmp_path)
    item = b['slices'][0]
    if mutation == 'not-planned': item['planned_new_files'] = []
    elif mutation == 'not-owner': item['production_owners'] = []
    elif mutation == 'frozen': item['execution_snapshot_paths'].append('src/subject.py')
    elif mutation == 'forbidden': b['agent_contexts'][0]['forbidden_paths'] = ['src/**']
    elif mutation == 'body': c['entries'][0]['exports'][0]['body'] = 'return 42'
    elif mutation == 'wrong-plan': c['plan_sha256'] = 'sha256:'+'f'*64
    elif mutation == 'wrong-slice': c['slice_id'] = 'S2'
    elif mutation == 'duplicate': c['entries'] *= 2
    elif mutation in {'existing', 'tracked'}:
        (tmp_path/'src').mkdir(); (tmp_path/'src/subject.py').write_text('KEEP\n')
        if mutation == 'tracked':
            subprocess.run(['git', 'add', 'src/subject.py'], cwd=tmp_path, check=True)
            subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'existing'], cwd=tmp_path, check=True)
            c['source_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=tmp_path, text=True).strip()
            (tmp_path/'src/subject.py').unlink()
    if mutation != 'wrong-plan': c['plan_sha256'] = sha256_value(b)
    with pytest.raises(ValueError):
        prepare_entry(workspace=tmp_path, bundle=b, slice_id='S1', contract=c, out=out)
    assert not out.exists()
    assert not (tmp_path/'src/subject.py').exists() or (tmp_path/'src/subject.py').read_text() == 'KEEP\n'


def test_symlink_and_multi_file_prevalidation_leave_no_new_file(tmp_path):
    b, c, out = setup(tmp_path)
    (tmp_path/'actual').mkdir()
    (tmp_path/'src').symlink_to(tmp_path/'actual', target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        prepare_entry(workspace=tmp_path, bundle=b, slice_id='S1', contract=c, out=out)
    assert not (tmp_path/'actual/subject.py').exists()
    (tmp_path/'src').unlink()
    c['entries'].append({'path': 'unplanned.py', 'exports': c['entries'][0]['exports']})
    with pytest.raises(ValueError):
        prepare_entry(workspace=tmp_path, bundle=b, slice_id='S1', contract=c, out=out)
    assert not (tmp_path/'src/subject.py').exists()


def test_prepared_real_entry_still_needs_controlled_red_and_detects_harness_error(tmp_path, monkeypatch):
    b, c, out = setup(tmp_path)
    prepare_entry(workspace=tmp_path, bundle=b, slice_id='S1', contract=c, out=out)
    (tmp_path/'tests').mkdir()
    source = ("import sys\nfrom pathlib import Path\nimport pytest\n"
              "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
              "from src.subject import answer\n"
              "@pytest.mark.cer_assertion('ASSERT-X')\n"
              "def test_behavior():\n"
              "    value=answer('question', mode='strict')\n"
              "    if value != 42: print('FAILURE_ID:EXPECTED-BEHAVIOR')\n"
              "    assert value == 42\n")
    (tmp_path/'tests/test_behavior.py').write_text(source)
    semantic = tmp_path/'plan.json'; semantic.write_text(json.dumps(b))
    descriptor = materialize_descriptor(bundle=b, slice_id='S1', stage='red', run_id='R1',
        candidate_hash='sha256:'+'0'*64, argv=[sys.executable, '-B', '-m', 'pytest', 'tests/test_behavior.py', '-q'],
        cwd='.', timeout_seconds=30, target_refs=['tests/test_behavior.py'], fixture_refs=['tests/test_behavior.py'])
    run = tmp_path/'logs/R1'; create_json(run/'descriptors/red.json', descriptor)
    result = execute_stage(workspace=tmp_path, semantic_plan=semantic, run_dir=run,
        descriptor_path=run/'descriptors/red.json', profile_identity='standard')
    assert result['predicate_result'] and result['failure_family'] == 'expected-red'
    validate_expected_red(result)
    # A missing import remains a harness failure, even with a prepared entry.
    (tmp_path/'tests/test_behavior.py').write_text(source.replace('from src.subject import answer', 'from nonexistent_owner import answer'))
    run2 = tmp_path/'logs/R2'; descriptor['run_id']='R2'; create_json(run2/'descriptors/red.json', descriptor)
    # ADR-0041: the strengthened static binding now refuses this before a
    # harness process can run; it still cannot create expected-RED evidence.
    with pytest.raises(ValueError, match='does not import and call'):
        execute_stage(workspace=tmp_path, semantic_plan=semantic, run_dir=run2,
            descriptor_path=run2/'descriptors/red.json', profile_identity='standard')
    assert not (run2/'canonical-evidence').exists()


def test_json_interface_has_no_candidate_supplied_data(tmp_path):
    b, c, out = setup(tmp_path)
    item=b['slices'][0]
    for field in ['production_owners','allowed_write_paths','planned_new_files']:
        item[field].append('src/contract.json')
    c['plan_sha256']=sha256_value(b)
    c['entries'].append({'path':'src/contract.json','exports':[]})
    prepare_entry(workspace=tmp_path,bundle=b,slice_id='S1',contract=c,out=out)
    assert (tmp_path/'src/contract.json').read_bytes()==b'{}\n'
