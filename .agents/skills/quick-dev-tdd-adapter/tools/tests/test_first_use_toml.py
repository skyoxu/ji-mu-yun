"""ADR-0041 (2026-10-23): empty TOML preparation is not implementation."""
from copy import deepcopy
import subprocess
import tomllib

import pytest
from test_first_use_entry import setup
from first_use_entry import prepare_entry, validate_prepared_entry
from runtime_evidence import sha256_value
from current_router import validate_expected_red


def toml_setup(root):
    bundle, contract, out = setup(root)
    item = bundle['slices'][0]
    for field in ['production_owners', 'allowed_write_paths', 'planned_new_files']:
        item[field] = ['src/subject.toml']
    item['rollback_scope']['production_paths'] = ['src/subject.toml']
    contract['entries'] = [{'path': 'src/subject.toml', 'exports': []}]
    contract['plan_sha256'] = sha256_value(bundle)
    return bundle, contract, out


def prepare(root, bundle, contract, out):
    return prepare_entry(workspace=root, bundle=bundle, slice_id='S1', contract=contract, out=out)


def test_empty_toml_is_deterministic_and_not_configured_or_red(tmp_path):
    bundle, contract, out = toml_setup(tmp_path)
    receipt = prepare(tmp_path, bundle, contract, out)
    path = tmp_path/'src/subject.toml'
    assert path.read_bytes() == b''
    assert tomllib.loads(path.read_text()) == {}
    assert 'query' not in tomllib.loads(path.read_text())
    assert receipt['authorizes'] == []
    assert receipt['implementation_authorized'] is False
    assert receipt['tests_executed'] is False
    before = path.read_bytes(), out.read_bytes()
    assert prepare(tmp_path, bundle, contract, out) == receipt
    assert (path.read_bytes(), out.read_bytes()) == before
    assert validate_prepared_entry(workspace=tmp_path, bundle=bundle, slice_id='S1', receipt=receipt) == receipt
    with pytest.raises(ValueError, match='expected-red'):
        validate_expected_red(receipt)


@pytest.mark.parametrize('exports', [None, {}, '', ['query'], [{'name': 'query', 'parameters': [], 'keyword_parameters': []}]])
def test_toml_rejects_nonempty_or_nonlist_exports(tmp_path, exports):
    bundle, contract, out = toml_setup(tmp_path)
    contract['entries'][0]['exports'] = exports
    with pytest.raises(ValueError, match='TOML interface'):
        prepare(tmp_path, bundle, contract, out)
    assert not (tmp_path/'src').exists() and not out.exists()


@pytest.mark.parametrize('mutation', [
    'not-owner', 'not-write', 'not-planned', 'frozen', 'forbidden', 'body', 'content',
    'defaults', 'unknown-top', 'wrong-plan', 'wrong-slice', 'wrong-head', 'existing',
    'tracked-deleted', 'duplicate', 'symlink', 'parent-symlink', 'escape', 'absolute',
    'test-path', 'log-path', 'unsupported',
])
def test_toml_keeps_all_input_and_path_rejections(tmp_path, mutation):
    bundle, contract, out = toml_setup(tmp_path)
    item = bundle['slices'][0]
    path = tmp_path/'src/subject.toml'
    if mutation in ['not-owner', 'not-write', 'not-planned']:
        item[{'not-owner': 'production_owners', 'not-write': 'allowed_write_paths',
              'not-planned': 'planned_new_files'}[mutation]] = []
    elif mutation == 'frozen': item['execution_snapshot_paths'].append('src/subject.toml')
    elif mutation == 'forbidden': bundle['agent_contexts'][0]['forbidden_paths'] = ['src/**']
    elif mutation in ['body', 'content', 'defaults']: contract['entries'][0][mutation] = 'enabled=true'
    elif mutation == 'unknown-top': contract['content'] = 'enabled=true'
    elif mutation == 'wrong-slice': contract['slice_id'] = 'S2'
    elif mutation == 'wrong-head': contract['source_commit'] = '0'*40
    elif mutation == 'duplicate': contract['entries'] *= 2
    elif mutation in ['existing', 'tracked-deleted']:
        path.parent.mkdir(); path.write_bytes(b'KEEP')
        if mutation == 'tracked-deleted':
            subprocess.run(['git', 'add', 'src/subject.toml'], cwd=tmp_path, check=True)
            subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                            'commit', '-qm', 'existing'], cwd=tmp_path, check=True)
            contract['source_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=tmp_path, text=True).strip()
            path.unlink()
    elif mutation in ['symlink', 'parent-symlink']:
        target = tmp_path/'actual'; target.mkdir()
        if mutation == 'parent-symlink': path.parent.symlink_to(target, target_is_directory=True)
        else:
            path.parent.mkdir(); (target/'file').write_bytes(b'KEEP'); path.symlink_to(target/'file')
    elif mutation in ['escape', 'absolute', 'test-path', 'log-path', 'unsupported']:
        ref = {'escape': '../subject.toml', 'absolute': str(tmp_path/'absolute.toml'),
               'test-path': 'tests/subject.toml', 'log-path': 'logs/subject.toml',
               'unsupported': 'src/subject.yaml'}[mutation]
        contract['entries'][0]['path'] = ref
        for field in ['production_owners', 'allowed_write_paths', 'planned_new_files']: item[field] = [ref]
    contract['plan_sha256'] = 'sha256:'+'0'*64 if mutation == 'wrong-plan' else sha256_value(bundle)
    before = {str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file() and '.git' not in p.parts}
    with pytest.raises(ValueError):
        prepare(tmp_path, bundle, contract, out)
    after = {str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file() and '.git' not in p.parts}
    assert before == after and not out.exists()


@pytest.mark.parametrize('mutation', ['bytes', 'missing', 'hash', 'input-hash', 'input-data', 'plan', 'slice', 'head', 'authority', 'symlink'])
def test_toml_receipt_revalidation_rejects_drift(tmp_path, mutation):
    bundle, contract, out = toml_setup(tmp_path)
    receipt = deepcopy(prepare(tmp_path, bundle, contract, out))
    path = tmp_path/'src/subject.toml'
    if mutation == 'bytes': path.write_bytes(b'\n')  # Even equivalent empty TOML bytes differ.
    elif mutation == 'missing': path.unlink()
    elif mutation == 'hash': receipt['production_hashes']['src/subject.toml'] = 'sha256:'+'0'*64
    elif mutation == 'input-hash': receipt['input_sha256'] = 'sha256:'+'0'*64
    elif mutation == 'input-data':
        receipt['input']['entries'][0]['content'] = '[query]'
        receipt['input_sha256'] = sha256_value(receipt['input'])
    elif mutation == 'plan': bundle['plan_id'] += '-changed'
    elif mutation == 'slice': receipt['slice_id'] = 'S2'
    elif mutation == 'head':
        subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                        'commit', '--allow-empty', '-qm', 'new head'], cwd=tmp_path, check=True)
    elif mutation == 'authority': receipt['implementation_authorized'] = True
    elif mutation == 'symlink':
        path.unlink(); (tmp_path/'other.toml').write_bytes(b''); path.symlink_to(tmp_path/'other.toml')
    with pytest.raises(ValueError):
        validate_prepared_entry(workspace=tmp_path, bundle=bundle, slice_id='S1', receipt=receipt)


def test_mixed_preparation_prevalidates_before_creating_toml(tmp_path):
    bundle, contract, out = toml_setup(tmp_path)
    contract['entries'].append({'path': 'src/unapproved.json', 'exports': []})
    with pytest.raises(ValueError): prepare(tmp_path, bundle, contract, out)
    assert not (tmp_path/'src/subject.toml').exists() and not out.exists()
