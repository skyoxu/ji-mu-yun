"""Real consumer entry boundaries and four repair regressions (ADR-0060).

Only post-gate workflow execution is replaced in entry probes. The actual
entry function, contract validation, current resolver and retention run.
No model or formal workflow is started.
"""
import argparse
import copy
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from scripts.python.tests.test_toolchain_workflow_repair_e2e import fixture, complete, CONSUMERS
from scripts.python import skill_input_v2 as v2
from scripts.python import skill_input_retention as retention
from scripts.python.skill_input_protocol import digest, read_json, identity
from scripts.python.skill_input_selection import selection_identity

ROOT = Path(__file__).resolve().parents[3]
ENTRYPOINTS = {
    'vdd-execution-plan': ('scripts', 'vdd_knowledge_preflight'),
    'quick-dev-tdd-adapter': ('tools', 'adapter'),
    'run-phase-bootstrap-review': ('scripts', 'bootstrap_review'),
    'run-refactor-implementation-acceptance': ('scripts', 'acceptance_cli'),
}


def actual_request(root, consumer):
    request = fixture(root, consumer)
    contract_path = ROOT / '.agents' / 'skills' / consumer / 'references' / 'skill-input-contract.v1.json'
    contract = read_json(contract_path)
    (root / 'contract.json').write_bytes(contract_path.read_bytes())
    request['bindings']['contract']['sha256'] = digest(contract_path.read_bytes())
    request['inputs'] = {}
    request['sources'] = []
    for selector in contract['operations'][request['operation']]['required_inputs']:
        directory = root / ('input-' + selector)
        directory.mkdir()
        file = directory / 'source.md'
        file.write_text('Required input: ' + selector + '\n', encoding='utf-8')
        path = file.relative_to(root).as_posix()
        request['sources'].append({'role': 'authority_source' if selector == 'authority' else 'normative_source',
            'path': path, 'module': selector, 'resource_set': 'core', 'authority': 'repository', 'sha256': digest(file.read_bytes())})
        spec = contract['source_roles'][selector]
        request['inputs'][selector] = [path if 'file' in spec['allowed_kinds'] else directory.name]
    freeze = read_json(root / 'freeze.json')
    freeze['sourceSelectionHash'] = selection_identity(request['sources'], consumer=consumer, policy_revision='v2')['sourceSelectionHash']
    (root / 'freeze.json').write_text(json.dumps(freeze), encoding='utf-8')
    request['bindings']['knowledge_freeze']['sha256'] = digest((root / 'freeze.json').read_bytes())
    return request


@pytest.mark.parametrize('consumer', CONSUMERS)
def test_each_real_contract_required_input_is_enforced(tmp_path, consumer):
    request = actual_request(tmp_path, consumer)
    for selector in request['inputs']:
        invalid = copy.deepcopy(request)
        del invalid['inputs'][selector]
        with pytest.raises(ValueError, match='required input'):
            v2.prepare(tmp_path, invalid)
    complete(tmp_path, request)


def test_directory_input_cannot_omit_untyped_member(tmp_path):
    request = actual_request(tmp_path, 'quick-dev-tdd-adapter')
    request['inputs']['target_files'] = ['input-target_files']
    (tmp_path / 'input-target_files' / 'omitted.md').write_text('Required sibling', encoding='utf-8')
    with pytest.raises(ValueError, match='untyped omitted'):
        v2.prepare(tmp_path, request)


@pytest.mark.parametrize('case', ['omitted', 'forged', 'deleted', 'tracked', 'ignored-untracked'])
def test_knowledge_changes_are_derived_from_git(tmp_path, case):
    request = fixture(tmp_path)
    path = tmp_path / 'knowledge' / 'policy.json'
    path.parent.mkdir()
    path.write_text('{}', encoding='utf-8')
    if case in {'deleted', 'tracked'}:
        subprocess.run(['git', '-C', str(tmp_path), 'add', 'knowledge/policy.json'], check=True)
        subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'knowledge baseline'], check=True)
        authority = read_json(tmp_path / 'authority.json')
        authority['skill_input_baseline'] = subprocess.check_output(['git', '-C', str(tmp_path), 'rev-parse', 'HEAD']).decode().strip()
        (tmp_path / 'authority.json').write_text(json.dumps(authority), encoding='utf-8')
        request['bindings']['authority']['sha256'] = digest((tmp_path / 'authority.json').read_bytes())
        if case == 'deleted':
            path.unlink()
        else:
            path.write_text('{"changed":true}', encoding='utf-8')
    if case == 'forged':
        request['changed_paths'] = []
    if case == 'ignored-untracked':
        (tmp_path / '.gitignore').write_text('knowledge/\n', encoding='utf-8')
    with pytest.raises(ValueError, match='review-required|changed_paths'):
        v2.prepare(tmp_path, request)


def test_missing_trusted_baseline_fails_closed(tmp_path):
    request = fixture(tmp_path)
    (tmp_path / 'authority.json').write_text('{}', encoding='utf-8')
    request['bindings']['authority']['sha256'] = digest((tmp_path / 'authority.json').read_bytes())
    with pytest.raises(ValueError, match='baseline'):
        v2.prepare(tmp_path, request)


def test_unselected_candidate_change_invalidates_current(tmp_path):
    request = fixture(tmp_path)
    complete(tmp_path, request)
    (tmp_path / 'unselected.py').write_text('changed = True\n', encoding='utf-8')
    with pytest.raises(ValueError, match='candidate changed'):
        v2.require_current(tmp_path, tmp_path / request['storage'] / 'current.v1.json', consumer=request['consumer'], operation='execute', contract_path=tmp_path / 'contract.json')


def test_context_budget_is_enforced(tmp_path):
    request = fixture(tmp_path)
    contract = read_json(tmp_path / 'contract.json')
    contract['max_context_bytes'] = 20
    (tmp_path / 'contract.json').write_text(json.dumps(contract), encoding='utf-8')
    request['bindings']['contract']['sha256'] = digest((tmp_path / 'contract.json').read_bytes())
    started = v2.prepare(tmp_path, request)
    v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=lambda p,b: None)
    with pytest.raises(ValueError, match='context exceeds'):
        v2.finish(tmp_path, 'repair', started['attempt_id'])
    assert not (tmp_path / request['storage'] / 'current.v1.json').exists()


@pytest.mark.parametrize('consumer', CONSUMERS)
def test_real_entry_registers_and_protects_generation(tmp_path, consumer):
    request = actual_request(tmp_path, consumer)
    _, result, _ = complete(tmp_path, request)
    store = tmp_path / request['storage']
    pointer = store / 'current.v1.json'
    probe = subprocess.run([sys.executable, str(Path(__file__).resolve()), consumer, str(tmp_path), str(pointer)],
        capture_output=True, text=True, encoding='utf-8', errors='strict', env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH', '')))
    assert probe.returncode == 0, probe.stdout + probe.stderr
    uses = list((store / 'consumer-uses').glob('*.json'))
    assert len(uses) == 1
    use = read_json(uses[0])
    assert use['generation_id'] == result['pointer']['generation_id'] and use['consumer'] == consumer
    assert use['authorizes'] == []
    # Advance current without registering a reference in test code.
    changed = tmp_path / request['sources'][0]['path']
    changed.write_text('Successor input\n', encoding='utf-8')
    started = v2.prepare(tmp_path, request, allow_refresh=True)
    v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=lambda p,b: None)
    v2.finish(tmp_path, 'repair', started['attempt_id'])
    plan = retention.plan_retention(store, repository_root=tmp_path, plan_id='repair', retention_seconds=0)
    assert not any(result['pointer']['generation_id'] in row['path'] for row in plan['candidates'])
    assert any(row['reason'].endswith('-reference') for row in plan['protected'])


@pytest.mark.parametrize('consumer', CONSUMERS)
def test_real_entry_rejects_legacy_receipt(tmp_path, consumer):
    request = actual_request(tmp_path, consumer)
    legacy = tmp_path / 'legacy.json'
    legacy.write_text(json.dumps({'schema_version':'skill-input-consumption.v1','ready':True}), encoding='utf-8')
    probe = subprocess.run([sys.executable, str(Path(__file__).resolve()), consumer, str(tmp_path), str(legacy)],
        capture_output=True, text=True, encoding='utf-8', errors='strict', env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH', '')))
    assert probe.returncode != 0 and 'v2 current pointer' in probe.stderr
    assert not (tmp_path / request['storage'] / 'consumer-uses').exists()


def entry_probe(consumer, root, pointer):
    """Execute actual entry functions; stop only after the Skill-input boundary."""
    directory, module = ENTRYPOINTS[consumer]
    sys.path.insert(0, str(ROOT / '.agents' / 'skills' / consumer / directory))
    entry = importlib.import_module(module)
    contract = root / 'contract.json'
    if consumer == 'quick-dev-tdd-adapter':
        result = entry.prepare_with_skill_input({'backend':{'hidden_state':False}, 'slices':[{'slice_id':'probe'}]},
            'probe', {'contract_hash':'probe','validator_hash':'probe'}, receipt_path=pointer,
            repository_root=root, skill_contract_path=contract)
        assert result['state'] == 'prepared' and result['skill_input']['binding_hash']
    elif consumer == 'vdd-execution-plan':
        # Evaluate downstream Knowledge independently; do not start the workflow.
        payload = root / 'plan' / 'skill-input-v2' / 'probe-input.json'
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.write_text('{}', encoding='utf-8')
        entry.evaluate_preflight = lambda *a, **k: {'status':'ready'}
        sys.argv = ['probe','--input',str(payload),'--repository-root',str(root),
            '--skill-input-receipt',str(pointer),'--skill-input-contract',str(contract)]
        assert entry.main() == 0
    elif consumer == 'run-phase-bootstrap-review':
        # A deliberately invalid post-gate review id prevents any review start.
        args = argparse.Namespace(repository_root=root, skill_input_receipt=pointer,
            skill_input_contract=contract, out_dir='logs/probe', review_id='INVALID')
        try:
            entry.command_prepare(args)
        except entry.BootstrapError as exc:
            if 'Review ID must' not in str(exc):
                raise
        else:
            raise AssertionError('post-gate review validation did not execute')
    else:
        observed = []
        def downstream(*a, **kwargs):
            observed.append(kwargs)
            assert Path(root / kwargs['skill_input_context_path']).is_file()
            return {'status':'probe-only'}
        entry.start_or_resume_target_run = downstream
        sys.argv = ['probe','start-or-resume','--repository-root',str(root),'--target-plan','plan',
            '--run-input-hash','sha256:'+'0'*64,'--contract-hash','sha256:'+'1'*64,
            '--knowledge-context-hash','sha256:'+'2'*64,'--skill-input-receipt',str(pointer),
            '--skill-input-contract',str(contract)]
        assert entry.main() == 0 and len(observed) == 1


if __name__ == '__main__':
    entry_probe(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]))


def test_existing_producer_cli_defaults_to_v2(tmp_path):
    request = fixture(tmp_path)
    request_file = tmp_path / 'request.json'
    request_file.write_text(json.dumps(request), encoding='utf-8')
    def run(script, *args):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'python' / script),
            '--repository-root', str(tmp_path), *args], capture_output=True, text=True,
            encoding='utf-8', errors='strict')
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout.splitlines()[-1])
    start = run('prepare_skill_input_consumption.py', '--request', str(request_file))
    assert run('launch_skill_input_consumer.py', '--plan-id', 'repair', '--attempt-id', start['attempt_id'])['status'] == 'complete'
    assert v2.finish(tmp_path, 'repair', start['attempt_id'])['status'] == 'ready'


@pytest.mark.parametrize('storage', ['knowledge', 'knowledge/skill-input-v2', 'plan'])
def test_storage_cannot_hide_candidate_authority(tmp_path, storage):
    request = fixture(tmp_path)
    request['storage'] = storage
    with pytest.raises(ValueError, match='storage'):
        v2.prepare(tmp_path, request)


def test_native_custody_tampering_blocks_gc(tmp_path):
    request = fixture(tmp_path)
    complete(tmp_path, request)
    from skill_input_gate import require_ready_skill_input
    store = tmp_path / request['storage']
    kwargs = dict(receipt_path=store / 'current.v1.json', repository_root=tmp_path,
        contract_path=tmp_path / 'contract.json', consumer=request['consumer'], operation='execute')
    first = require_ready_skill_input(**kwargs)
    assert require_ready_skill_input(**kwargs)['retention_reference'] == first['retention_reference']
    use = next((store / 'consumer-uses').glob('*.json'))
    use.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='stale retention reference'):
        retention.plan_retention(store, repository_root=tmp_path, plan_id='repair', retention_seconds=0)


@pytest.mark.parametrize('case', ['ready', 'target', 'pointer-hash', 'legacy',
                                'context', 'source', 'prepared', 'pointer-race'])
def test_coordinator_resolves_v2_before_run_validation(tmp_path, monkeypatch, case):
    """Exercise the actual coordinator loader; never start an action DAG.

    Only the subsequent run-input validator is replaced by a stop sentinel.
    Pointer, generation, contract, source and retention checks are real.
    """
    consumer = 'run-refactor-implementation-acceptance'
    request = actual_request(tmp_path, consumer)
    target = 'input-implementation_target'
    request['inputs']['implementation_target'] = [target]
    complete(tmp_path, request)
    store = tmp_path / request['storage']
    pointer = store / 'current.v1.json'
    prepared = store / 'coordinator-prepared.json'
    prepared.write_text(json.dumps({'schemaVersion': 'acceptance-run-input.v1', 'input': {}}), encoding='utf-8')
    monkeypatch.syspath_prepend(str(ROOT / '.agents' / 'skills' / consumer / 'scripts'))
    entry = importlib.import_module('acceptance_cli')
    monkeypatch.setattr(entry, 'REPOSITORY_ROOT', tmp_path)
    refs = {key: {'path': path.relative_to(tmp_path).as_posix(), 'sha256': entry._file_hash(path)}
            for key, path in [('preparedRunInput', prepared), ('skillInputReceipt', pointer),
                              ('skillInputContract', tmp_path / 'contract.json')]}
    coordinator = {'schemaVersion': 'jimuyun.acceptance-coordinator-request.v3',
                   'targetPlan': target, 'authorizes': [], **refs}
    expected = None
    if case == 'target':
        coordinator['targetPlan'] = 'another-plan'
        expected = 'target mismatch'
    elif case == 'pointer-hash':
        coordinator['skillInputReceipt']['sha256'] = 'sha256:' + '0' * 64
        expected = 'skillInputReceipt is stale'
    elif case == 'legacy':
        pointer.write_text(json.dumps({'ready': True, 'authorizes': []}), encoding='utf-8')
        coordinator['skillInputReceipt']['sha256'] = entry._file_hash(pointer)
        expected = 'pointer schema'
    elif case == 'context':
        generation = read_json(pointer)['generation_id']
        (store / 'skill-input-generations' / generation / 'context.json').write_text('{}', encoding='utf-8')
        expected = 'generation integrity'
    elif case == 'source':
        (tmp_path / request['sources'][0]['path']).write_text('Changed source', encoding='utf-8')
        expected = 'drift'
    elif case == 'prepared':
        prepared.write_text('{}', encoding='utf-8')
        coordinator['preparedRunInput']['sha256'] = entry._file_hash(prepared)
        expected = 'prepared run input is invalid'
    elif case == 'pointer-race':
        real_gate = entry.require_ready_skill_input
        def gate_then_change(**kwargs):
            ready = real_gate(**kwargs)
            pointer.write_text('{}', encoding='utf-8')
            return ready
        monkeypatch.setattr(entry, 'require_ready_skill_input', gate_then_change)
        expected = 'pointer changed'

    class ReachedRunValidation(Exception):
        pass

    def stop_after_input_resolution(value):
        assert value == {}
        raise ReachedRunValidation()

    monkeypatch.setattr(entry, 'validate_run_input', stop_after_input_resolution)
    if expected:
        with pytest.raises(entry.InputError, match=expected):
            entry._load_current_coordinator_inputs(tmp_path / 'request.json', coordinator)
    else:
        with pytest.raises(ReachedRunValidation):
            entry._load_current_coordinator_inputs(tmp_path / 'request.json', coordinator)
        uses = list((store / 'consumer-uses').glob('*.json'))
        assert len(uses) == 1 and read_json(uses[0])['authorizes'] == []
