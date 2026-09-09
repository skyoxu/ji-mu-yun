"""Real file-backed W0-W6 integration and negative oracles (ADR-0060)."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from scripts.python import skill_input_v2 as v2
from scripts.python import skill_input_retention as retention
from scripts.python.skill_input_protocol import digest, identity, read_json, atomic_json
from scripts.python.skill_input_current import resolve_current
from scripts.python.skill_input_generation import read_generation
from scripts.python.skill_input_selection import selection_identity, verify_selection
from scripts.python.skill_input_transport import continuation, validate_continuation
from scripts.python.knowledge_gate_projection import project_knowledge_gates

CONSUMERS = ('vdd-execution-plan', 'quick-dev-tdd-adapter', 'run-phase-bootstrap-review', 'run-refactor-implementation-acceptance')


def fixture(root, consumer='quick-dev-tdd-adapter'):
    root.mkdir(exist_ok=True)
    operation = {'vdd-execution-plan': 'create', 'quick-dev-tdd-adapter': 'execute', 'run-phase-bootstrap-review': 'review', 'run-refactor-implementation-acceptance': 'acceptance'}[consumer]
    (root / 'requirements.md').write_text(('Requirements and observable behavior\n' * 10) + '\u5b8c\u6574\u8bfb\u53d6\n', encoding='utf-8')
    for filename, value in [('contract.json', {'consumer': consumer, 'operations': {operation: {}}}), ('registry.json', {'commands': ['test']}), ('authority.json', {'adr': 'ADR-0060'}), ('freeze.json', {'authorizes': []})]:
        (root / filename).write_text(json.dumps(value), encoding='utf-8')
    bindings = {key: {'path': path, 'sha256': digest((root / path).read_bytes())} for key, path in [('contract', 'contract.json'), ('registry', 'registry.json'), ('authority', 'authority.json'), ('knowledge_freeze', 'freeze.json')]}
    source = {'role': 'normative_source', 'path': 'requirements.md', 'module': 'requirements', 'resource_set': 'core', 'authority': 'repository', 'sha256': digest((root / 'requirements.md').read_bytes())}
    freeze = {'schema_version': 'skill-input-direct-source-freeze.v2', 'sourceSelectionHash': selection_identity([source], consumer=consumer, policy_revision='v2')['sourceSelectionHash'], 'authorizes': []}
    (root / 'freeze.json').write_text(json.dumps(freeze), encoding='utf-8')
    bindings['knowledge_freeze']['sha256'] = digest((root / 'freeze.json').read_bytes())
    return {'schema_version': 'skill-input-request.v2', 'plan_id': 'repair', 'consumer': consumer, 'operation': operation, 'policy_revision': 'v2', 'storage': 'plan/skill-input-v2', 'sources': [source], 'bindings': bindings, 'page_bytes': 32, 'max_snapshot_bytes': 8192, 'max_retries': 1}


def complete(root, request):
    started = v2.prepare(root, request)
    delivered = []
    v2.consume(root, started['plan_id'], started['attempt_id'], receiver=lambda page, data: delivered.append((page, data)))
    result = v2.finish(root, started['plan_id'], started['attempt_id'])
    return started, result, delivered


@pytest.mark.parametrize('consumer', CONSUMERS)
def test_real_selection_transport_coverage_current_and_retention(tmp_path, consumer):
    request = fixture(tmp_path, consumer)
    started = v2.prepare(tmp_path, request)
    store = tmp_path / request['storage']
    with pytest.raises(ValueError, match='coverage'):
        v2.finish(tmp_path, 'repair', started['attempt_id'])
    assert resolve_current(store) is None
    delivery = []
    first = v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=lambda p, b: delivery.append(b), max_pages=2)
    assert first['status'] == 'partial'
    with pytest.raises(ValueError, match='coverage'):
        v2.finish(tmp_path, 'repair', started['attempt_id'])
    assert resolve_current(store) is None
    v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=lambda p, b: delivery.append(b), expected_token=first['continuation'])
    assert b''.join(delivery) == (tmp_path / 'requirements.md').read_bytes()
    result = v2.finish(tmp_path, 'repair', started['attempt_id'])
    current = resolve_current(store)
    assert current == result['pointer']
    receipt = read_generation(store, current['generation_id'])['receipt']
    assert receipt['coverage']['byte_count'] == len(b''.join(delivery))
    assert receipt['coverage']['page_count'] > 2
    assert receipt['authorizes'] == [] and receipt['gates']['publication_allowed'] is False
    validated = v2.require_current(tmp_path, store / 'current.v1.json', consumer=consumer, operation=request['operation'], contract_path=tmp_path / 'contract.json')
    assert validated['ready'] is True and validated['context_artifact'].is_file()
    plan = retention.plan_retention(store, repository_root=tmp_path, plan_id='repair', retention_seconds=0)
    assert not any(current['generation_id'] in row['path'] for row in plan['candidates'])
    assert any(row['reason'] == 'current-generation' for row in plan['protected'])


def test_shared_consumer_gate_resolves_v2_pointer(tmp_path):
    request = fixture(tmp_path)
    complete(tmp_path, request)
    sys.path.insert(0, str(Path(v2.__file__).parent))
    from skill_input_gate import require_ready_skill_input
    result = require_ready_skill_input(receipt_path=tmp_path / request['storage'] / 'current.v1.json', repository_root=tmp_path, contract_path=tmp_path / 'contract.json', consumer=request['consumer'], operation='execute')
    assert result['ready'] is True
    with pytest.raises(ValueError):
        require_ready_skill_input(receipt_path=tmp_path / request['storage'] / 'current.v1.json', repository_root=tmp_path, contract_path=tmp_path / 'contract.json', consumer='another-consumer', operation='execute')


def test_identical_replay_reuses_generation(tmp_path):
    request = fixture(tmp_path)
    _, first, _ = complete(tmp_path, request)
    _, second, _ = complete(tmp_path, request)
    assert first['pointer'] == second['pointer']
    assert len(list((tmp_path / request['storage'] / 'skill-input-generations').iterdir())) == 1


@pytest.mark.parametrize('key,value', [('role', 'made-up'), ('path', '../escape'), ('path', '/absolute'), ('path', 'C:/private'), ('authority', ''), ('module', ''), ('sha256', 'invalid')])
def test_typed_selection_rejects_invalid_fields(tmp_path, key, value):
    request = fixture(tmp_path)
    request['sources'][0][key] = value
    with pytest.raises(ValueError):
        v2.prepare(tmp_path, request)


def test_missing_and_ambiguous_selection_fail(tmp_path):
    request = fixture(tmp_path)
    for rows in ([], request['sources'] * 2, [{**request['sources'][0], 'path': 'missing.md'}]):
        with pytest.raises(ValueError):
            v2.prepare(tmp_path, {**request, 'sources': rows})


def test_selection_order_stable_content_drift_independent(tmp_path):
    request = fixture(tmp_path)
    rows = request['sources'] + [{**request['sources'][0], 'path': 'other.md'}]
    args = dict(consumer=request['consumer'], policy_revision='v2')
    assert selection_identity(rows, **args) == selection_identity(rows[::-1], **args)
    before = selection_identity(rows, **args)
    rows[0]['sha256'] = 'sha256:' + 'a' * 64
    after = selection_identity(rows, **args)
    assert before['sourceSelectionHash'] == after['sourceSelectionHash']
    assert before['sourceContentHash'] != after['sourceContentHash']


@pytest.mark.parametrize('file', ['requirements.md', 'contract.json', 'registry.json', 'authority.json', 'freeze.json'])
def test_source_and_binding_drift_blocks_current_and_publication(tmp_path, file):
    request = fixture(tmp_path)
    _, first, _ = complete(tmp_path, request)
    started = v2.prepare(tmp_path, request)
    pointer_bytes = (tmp_path / request['storage'] / 'current.v1.json').read_bytes()
    (tmp_path / file).write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError):
        v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=lambda p, b: None)
    with pytest.raises(ValueError):
        v2.require_current(tmp_path, tmp_path / request['storage'] / 'current.v1.json', consumer=request['consumer'], operation='execute', contract_path=tmp_path / 'contract.json')
    assert (tmp_path / request['storage'] / 'current.v1.json').read_bytes() == pointer_bytes


def test_successor_refresh_preserves_selection_and_does_not_publish_knowledge(tmp_path):
    request = fixture(tmp_path)
    _, first, _ = complete(tmp_path, request)
    freeze = (tmp_path / 'freeze.json').read_bytes()
    (tmp_path / 'requirements.md').write_text('new current requirements\n', encoding='utf-8')
    started = v2.prepare(tmp_path, request, allow_refresh=True)
    v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=lambda p, b: None)
    second = v2.finish(tmp_path, 'repair', started['attempt_id'])
    assert first['pointer']['generation_id'] != second['pointer']['generation_id']
    store = tmp_path / request['storage']
    old = read_generation(store, first['pointer']['generation_id'])['receipt']
    new = read_generation(store, second['pointer']['generation_id'])['receipt']
    assert old['selection']['sourceSelectionHash'] == new['selection']['sourceSelectionHash']
    assert new['gates']['route'] == 'successor-refresh'
    assert (tmp_path / 'freeze.json').read_bytes() == freeze


def test_selection_drift_cannot_replace_current(tmp_path):
    request = fixture(tmp_path)
    complete(tmp_path, request)
    request['sources'][0]['module'] = 'different-authority-scope'
    with pytest.raises(ValueError, match='selection-drift'):
        v2.prepare(tmp_path, request)


def test_stale_continuation_and_tampered_coverage_fail(tmp_path):
    request = fixture(tmp_path)
    started = v2.prepare(tmp_path, request)
    path = retention.attempt_path(tmp_path, 'repair', started['attempt_id'])
    token = read_json(path / 'observed.json')['continuation']
    v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=lambda p, b: None, max_pages=1)
    with pytest.raises(ValueError, match='stale continuation'):
        v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=lambda p, b: None, expected_token=token)
    observed = read_json(path / 'observed.json')
    observed['pages'][0]['end_byte'] += 1
    atomic_json(path / 'observed.json', observed)
    with pytest.raises(ValueError, match='observation prefix'):
        v2.finish(tmp_path, 'repair', started['attempt_id'])


def test_retry_budget_is_persisted_and_bounded(tmp_path):
    request = fixture(tmp_path)
    started = v2.prepare(tmp_path, request)
    def unavailable(page, data):
        raise TimeoutError('transport unavailable')
    with pytest.raises(TimeoutError):
        v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=unavailable)
    with pytest.raises(ValueError, match='retry budget exhausted'):
        v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=unavailable)
    state = read_json(retention.attempt_path(tmp_path, 'repair', started['attempt_id']) / 'attempt.json')
    assert state['status'] == 'failed'
    assert resolve_current(tmp_path / request['storage']) is None


@pytest.mark.parametrize('case', ['missing-generation', 'corrupt-context', 'partial-generation'])
def test_invalid_current_is_rejected(tmp_path, case):
    request = fixture(tmp_path)
    _, result, _ = complete(tmp_path, request)
    store = tmp_path / request['storage']
    gen = store / 'skill-input-generations' / result['pointer']['generation_id']
    if case == 'missing-generation':
        value = read_json(store / 'current.v1.json'); value['generation_id'] = 'nonexistent'; atomic_json(store / 'current.v1.json', value)
    elif case == 'corrupt-context':
        (gen / 'context.json').write_text('{}')
    else:
        (gen / 'receipt.json').unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        resolve_current(store)


@pytest.mark.parametrize('facts,route', [({}, 'ready'), ({'catalog_stale': True}, 'degraded-continuation'), ({'source_bytes_same': False}, 'successor-refresh'), ({'read_set_same': False}, 'repair-required'), ({'authority_same': False}, 'repair-required'), ({'lkg_valid': False}, 'repair-required'), ({'publication_integrity_valid': False}, 'repair-required'), ({'required_sources_present': False}, 'repair-required'), ({'changed_paths': ['knowledge/policies/example.json']}, 'review-required')])
def test_independent_knowledge_gates(facts, route):
    base = {'catalog_stale': False, 'read_set_same': True, 'source_bytes_same': True}
    result = project_knowledge_gates(**{**base, **facts})
    assert result['route'] == route
    assert result['publication_allowed'] is False
    assert result['execution_allowed'] is (route in {'ready', 'degraded-continuation', 'successor-refresh'})


def test_leases_heartbeat_and_terminal_transition(tmp_path):
    retention.start_attempt(tmp_path, 'p', 'a', now=100, lease_seconds=20)
    retention.update_attempt(tmp_path, 'p', 'a', now=110, lease_seconds=20)
    with pytest.raises(ValueError, match='expired'):
        retention.update_attempt(tmp_path, 'p', 'a', now=131)
    retention.update_attempt(tmp_path, 'p', 'a', now=120, status='succeeded')
    with pytest.raises(ValueError):
        retention.update_attempt(tmp_path, 'p', 'a', now=121)


def test_retention_reports_expiry_and_requires_bound_approval(tmp_path):
    request = fixture(tmp_path)
    _, first, _ = complete(tmp_path, request)
    store = tmp_path / request['storage']
    retention.start_attempt(tmp_path, 'repair', 'expired', now=10, lease_seconds=10)
    retention.start_attempt(tmp_path, 'repair', 'active', now=time.time(), lease_seconds=3600)
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    subprocess.run(['git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'add', '.'], cwd=tmp_path, check=True)
    subprocess.run(['git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], cwd=tmp_path, check=True)
    kwargs = dict(repository_root=tmp_path, plan_id='repair', retention_seconds=0)
    plan = retention.plan_retention(store, **kwargs)
    assert any(r['path'].endswith('/expired') for r in plan['candidates'])
    assert not any(r['path'].endswith('/active') for r in plan['candidates'])
    for bad in (False, {}, {'approved_by': 'maintainer'}):
        with pytest.raises(ValueError):
            retention.apply_retention(store, approval=bad, **kwargs)
    approval = {'schema_version': 'skill-input-gc-approval.v1', 'approved_by': 'maintainer', 'plan_hash': plan['plan_hash'], 'predecessor_commit': plan['predecessor_commit']}
    result = retention.apply_retention(store, approval=approval, **kwargs)
    assert result['status'] == 'complete' and result['authorizes'] == []
    assert result['plan']['predecessor_commit'] == plan['predecessor_commit']
    assert not retention.attempt_path(tmp_path, 'repair', 'expired').exists()
    assert retention.attempt_path(tmp_path, 'repair', 'active').exists()
    assert resolve_current(store) == first['pointer']
    assert len(list((store / 'cleanup-receipts').glob('*.json'))) == 2


def test_cli_prepare_consume_finish_validate_without_model(tmp_path):
    request = fixture(tmp_path)
    request_path = tmp_path / 'request.json'; request_path.write_text(json.dumps(request))
    entry = Path(v2.__file__).resolve()
    def run(*argv):
        result = subprocess.run([sys.executable, str(entry), '--repository-root', str(tmp_path), *argv], capture_output=True, text=True, check=True)
        return json.loads(result.stdout.splitlines()[-1])
    start = run('prepare', '--request', str(request_path))
    assert run('consume', '--plan-id', 'repair', '--attempt-id', start['attempt_id'])['status'] == 'complete'
    assert run('finish', '--plan-id', 'repair', '--attempt-id', start['attempt_id'])['status'] == 'ready'
    assert run('validate', '--pointer', str(tmp_path / request['storage'] / 'current.v1.json'), '--consumer', request['consumer'], '--operation', 'execute', '--contract', str(tmp_path / 'contract.json'))['ready'] is True


@pytest.mark.parametrize('kind', ['lifecycle', 'authorization', 'terminal', 'acceptance'])
def test_registered_reference_protects_noncurrent_generation(tmp_path, kind):
    request = fixture(tmp_path)
    _, first, _ = complete(tmp_path, request)
    store = tmp_path / request['storage']
    old_id = first['pointer']['generation_id']
    artifact = tmp_path / (kind + '.json')
    artifact.write_text(json.dumps({'generation_id': old_id}))
    retention.register_reference(store, tmp_path, reference_id=kind, kind=kind, artifact_path=artifact.name, generation_ids=[old_id])
    (tmp_path / 'requirements.md').write_text('successor bytes\n')
    started = v2.prepare(tmp_path, request, allow_refresh=True)
    v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=lambda p, b: None)
    v2.finish(tmp_path, 'repair', started['attempt_id'])
    plan = retention.plan_retention(store, repository_root=tmp_path, plan_id='repair', retention_seconds=0)
    assert not any(old_id in r['path'] for r in plan['candidates'])
    artifact.write_text('{}')
    with pytest.raises(ValueError, match='stale retention reference'):
        retention.plan_retention(store, repository_root=tmp_path, plan_id='repair', retention_seconds=0)


def test_active_lease_protects_noncurrent_generation(tmp_path):
    request = fixture(tmp_path)
    _, first, _ = complete(tmp_path, request)
    store = tmp_path / request['storage']
    retention.start_attempt(tmp_path, 'repair', 'reader', lease_seconds=3600)
    retention.update_attempt(tmp_path, 'repair', 'reader', generation_ids=[first['pointer']['generation_id']], lease_seconds=3600)
    (tmp_path / 'requirements.md').write_text('successor bytes\n')
    started = v2.prepare(tmp_path, request, allow_refresh=True)
    v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=lambda p, b: None)
    v2.finish(tmp_path, 'repair', started['attempt_id'])
    plan = retention.plan_retention(store, repository_root=tmp_path, plan_id='repair', retention_seconds=0)
    assert not any(first['pointer']['generation_id'] in r['path'] for r in plan['candidates'])


def test_failed_pointer_write_preserves_current_and_allows_new_attempt(tmp_path, monkeypatch):
    request = fixture(tmp_path)
    _, first, _ = complete(tmp_path, request)
    store = tmp_path / request['storage']
    pointer_bytes = (store / 'current.v1.json').read_bytes()
    (tmp_path / 'requirements.md').write_text('new bytes\n')
    started = v2.prepare(tmp_path, request, allow_refresh=True)
    v2.consume(tmp_path, 'repair', started['attempt_id'], receiver=lambda p, b: None)
    import importlib
    current = importlib.import_module('scripts.python.skill_input_current')
    original = current.atomic_json
    def failure(*args, **kwargs):
        raise OSError('simulated interrupted pointer write')
    monkeypatch.setattr(current, 'atomic_json', failure)
    with pytest.raises(OSError):
        v2.finish(tmp_path, 'repair', started['attempt_id'])
    assert (store / 'current.v1.json').read_bytes() == pointer_bytes
    monkeypatch.setattr(current, 'atomic_json', original)
    result = v2.finish(tmp_path, 'repair', started['attempt_id'])
    assert result['pointer'] != first['pointer']


def test_symlink_source_is_rejected_without_exposing_content(tmp_path):
    request = fixture(tmp_path)
    secret = tmp_path / 'outside.txt'; secret.write_text('private')
    link = tmp_path / 'link.md'
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip('symlink creation privilege unavailable')
    request['sources'][0]['path'] = 'link.md'
    request['sources'][0]['sha256'] = digest(secret.read_bytes())
    with pytest.raises(ValueError, match='symlink'):
        v2.prepare(tmp_path, request)


def test_redacted_context_contains_no_credential_value(tmp_path):
    request = fixture(tmp_path)
    (tmp_path / 'requirements.md').write_text('Authorization: Bearer test-secret-value\nRequirements\n')
    request['sources'][0]['sha256'] = digest((tmp_path / 'requirements.md').read_bytes())
    _, result, delivered = complete(tmp_path, request)
    assert b'test-secret-value' not in b''.join(data for _, data in delivered)
    context = read_generation(tmp_path / request['storage'], result['pointer']['generation_id'])['context']
    assert 'test-secret-value' not in json.dumps(context)


def test_unverified_knowledge_freeze_is_rejected(tmp_path):
    request = fixture(tmp_path)
    (tmp_path / 'freeze.json').write_text(json.dumps({'ready': True, 'lkg_valid': True}))
    request['bindings']['knowledge_freeze']['sha256'] = digest((tmp_path / 'freeze.json').read_bytes())
    with pytest.raises(ValueError, match='unsupported Knowledge freeze'):
        v2.prepare(tmp_path, request)


@pytest.mark.parametrize('consumer,operation', [('vdd-execution-plan','repair'), ('quick-dev-tdd-adapter','execute'), ('run-phase-bootstrap-review','review'), ('run-refactor-implementation-acceptance','acceptance')])
def test_actual_repository_contract_is_consumed(tmp_path, consumer, operation):
    request = fixture(tmp_path, consumer)
    root = Path(__file__).resolve().parents[3]
    contract_path = root / '.agents' / 'skills' / consumer / 'references' / 'skill-input-contract.v1.json'
    (tmp_path / 'contract.json').write_bytes(contract_path.read_bytes())
    request['bindings']['contract']['sha256'] = digest(contract_path.read_bytes())
    request['operation'] = operation
    _, result, _ = complete(tmp_path, request)
    assert result['status'] == 'ready'


def test_consumer_budget_cannot_be_widened(tmp_path):
    request = fixture(tmp_path)
    contract = read_json(tmp_path / 'contract.json')
    contract['max_snapshot_bytes'] = 100
    (tmp_path / 'contract.json').write_text(json.dumps(contract))
    request['bindings']['contract']['sha256'] = digest((tmp_path / 'contract.json').read_bytes())
    with pytest.raises(ValueError, match='budget exceeds'):
        v2.prepare(tmp_path, request)


def test_legacy_terminal_cannot_publish_completion(tmp_path):
    root = Path(__file__).resolve().parents[3]
    entry = root / 'execution-plans/2026-08-18-toolchain-workflow-repair/tools/terminal_full.py'
    result = subprocess.run([sys.executable, str(entry)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0
    assert json.loads(result.stdout)['authorizes'] == []
    assert list(tmp_path.iterdir()) == []
