"""ADR-0041: permanent native lifecycle regressions for the first skill baseline."""
from functools import partial
import json
import subprocess
import sys

import pytest

from test_cer_behavior_routing import fixture, execute, implement
from test_execution_session import setup_session
from runtime_evidence import load_json, sha256_value


def test_actual_production_refactor_preserves_green_and_closes_q7_q8(tmp_path, monkeypatch):
    import stable_runner as api
    from worker_orchestrator import run_refactor_worker
    from coverage_predicates import validate_slice_ready, publish_implementation_complete

    semantic, roots = fixture(tmp_path, (False, False))
    (tmp_path / '.gitignore').write_text('logs/\n__pycache__/\n', encoding='utf-8')
    for args in (['init', '-q'], ['add', '.'], ['-c', 'user.name=Fixture', '-c',
                 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture']):
        subprocess.run(['git', *args], cwd=tmp_path, check=True, capture_output=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=tmp_path, text=True).strip()
    run = tmp_path / 'logs/baseline/S1'
    for row in roots:
        if row['root_kind'] == 'descriptor':
            row['repository_relative_posix_path'] = 'logs/baseline/S1/descriptors'
    roots_path = tmp_path / 'roots.json'
    roots_path.write_text(json.dumps(roots), encoding='utf-8')
    route = execute(tmp_path, semantic, 'probe', run_name='logs/baseline/S1')
    assert {r['disposition'] for r in route['behavior_dispositions']} == {'missing'}
    assert execute(tmp_path, semantic, 'red', route, run_name='logs/baseline/S1')['predicate_result']
    implement(tmp_path, (True, True))
    assert execute(tmp_path, semantic, 'green', route, run_name='logs/baseline/S1')['predicate_result']
    green_path = run / 'canonical-evidence/green/process-receipt.v2.json'
    green_before = green_path.read_bytes()
    request = load_json(run / 'canonical-evidence/green/reuse-request.v1.json')
    assert request['input'] is not None, 'This case must exercise content-bound GREEN.'
    production_before = (tmp_path / 'candidate.py').read_bytes()

    def refactor(root, _payload):
        (root / 'candidate.py').write_text(
            'def value(kind):\n values = {1: 1, 2: 2}\n return values[kind]\n', encoding='utf-8')

    monkeypatch.setattr(api, 'ROOT', tmp_path)
    monkeypatch.setattr(api, 'run_refactor_worker', partial(run_refactor_worker, worker_mutator=refactor))
    refactored = api.q6_refactor_worker_and_run(
        semantic=semantic, slice_id='S1', run_dir=run, profile='standard', timeout_seconds=30, backend=None)
    assert refactored['stage_result']['predicate_result']
    assert production_before != (tmp_path / 'candidate.py').read_bytes()
    assert green_path.read_bytes() == green_before
    ready_path = tmp_path / 'logs/baseline/S1-ready.json'
    # The public Q6 owner binds its candidate identity, so its public Q7 owner
    # must also materialize the terminal descriptor (not the low-level fixture).
    monkeypatch.setattr(sys, 'argv', ['run.py', '--plan', str(semantic.parent), '--slice', 'S1',
        '--run-dir', str(run), '--action', 'validate-slice', '--snapshot-roots', str(roots_path),
        '--source-commit', commit, '--base-commit', commit, '--out', str(ready_path)])
    assert api.main() == 0
    ready = load_json(ready_path)
    assert execute(tmp_path, semantic, 'terminal', route, run_name='logs/baseline/S1')['predicate_result']
    predecessor = {'slice_id': 'S1', 'run_root': 'logs/baseline/S1',
                   'result_ref': 'logs/baseline/S1-ready.json', 'result_sha256': sha256_value(ready)}
    completed = publish_implementation_complete(workspace=tmp_path, semantic_plan=semantic,
        predecessors=[predecessor], snapshot_roots=roots, source_commit=commit, base_commit=commit,
        out=tmp_path / 'logs/baseline/complete.json')
    assert completed['status'] == 'pass'
    assert green_path.read_bytes() == green_before


@pytest.mark.parametrize('change', ['dependency', 'test', 'engine', 'environment', 'mode', 'owner-deleted'])
def test_historical_green_retains_other_freshness_boundaries(change):
    from copy import deepcopy
    from shared_execution import _consumption_reason, ENVIRONMENT_SCHEMA
    before = {'files': {'owner.py': {'sha256': 'old', 'executable': False},
                        'dependency.py': {'sha256': 'same'}, 'test.py': {'sha256': 'same'}},
              'environment': {'schema': ENVIRONMENT_SCHEMA}, 'engine': {'judge.py': 'same'}}
    after = deepcopy(before)
    after['files']['owner.py']['sha256'] = 'refactored'
    bundle = {'slices': [{'slice_id': 'S1', 'production_owners': ['owner.py']}]}
    descriptor = {'stage': 'green', 'slice_id': 'S1'}
    assert _consumption_reason(before, after, bundle, descriptor, historical_green=True) is None
    assert _consumption_reason(before, after, bundle, descriptor)
    if change in {'dependency', 'test'}:
        after['files'][change + '.py']['sha256'] = 'changed'
    elif change == 'engine':
        after['engine']['judge.py'] = 'changed'
    elif change == 'environment':
        after['environment']['platform'] = 'changed'
    elif change == 'mode':
        after['files']['owner.py']['executable'] = True
    else:
        after['files']['owner.py'] = None
    assert _consumption_reason(before, after, bundle, descriptor, historical_green=True)
    with pytest.raises(ValueError, match='must-be-green'):
        _consumption_reason(before, after, bundle, {**descriptor, 'stage': 'refactor'}, historical_green=True)


def test_session_public_main_accepts_array_failure_history(tmp_path, monkeypatch, capsys):
    import stable_runner as api
    semantic, request = setup_session(tmp_path, monkeypatch)
    (tmp_path / 'history.json').write_text('[]\n', encoding='utf-8')
    request['failure_history'] = 'history.json'
    path = tmp_path / 'session.json'
    path.write_text(json.dumps(request), encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['run.py', '--plan', str(semantic.parent),
        '--action', 'preflight-session', '--execution-request', str(path)])
    assert api.main() == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'preflight-passed'
    assert not (tmp_path / 'logs').exists()
    from execution_session import advance_session
    assert advance_session(api, semantic, request, max_steps=1)['status'] == 'paused'


@pytest.mark.parametrize('payload', [{}, None, 'history', [None]])
def test_session_invalid_failure_history_is_rejected_before_run(tmp_path, monkeypatch, payload):
    import stable_runner as api
    from execution_session import preflight_session
    semantic, request = setup_session(tmp_path, monkeypatch)
    (tmp_path / 'history.json').write_text(json.dumps(payload), encoding='utf-8')
    request['failure_history'] = 'history.json'
    with pytest.raises(ValueError):
        preflight_session(api, semantic, request)
    assert not (tmp_path / 'logs').exists()
