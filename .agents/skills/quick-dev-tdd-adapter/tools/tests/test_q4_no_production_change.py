"""ADR-0041: no-op Q4 cannot authorize a GREEN successor."""
import json
from pathlib import Path
import sys
import pytest
TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import worker_orchestrator as workers
import q4_q6_gates as gates
import stable_runner as runner
from runtime_evidence import sha256_value


@pytest.mark.parametrize('change', ['none', 'restore', 'nonproduction', 'production'])
def test_worker_classifies_actual_production_delta(tmp_path, change):
    (tmp_path / 'owner.py').write_text('value = 0\n')
    (tmp_path / 'notes.txt').write_text('old\n')
    def mutate(root, payload):
        if change in {'restore', 'production'}:
            (root / 'owner.py').write_text('value = 1\n')
        if change == 'restore':
            (root / 'owner.py').write_text('value = 0\n')
        if change == 'nonproduction':
            (root / 'notes.txt').write_text('new\n')
    result = workers._invoke(root=tmp_path, stage='implementation',
        payload={'slice': {'production_owners': ['owner.py']}},
        allowed=['owner.py', 'notes.txt'], forbidden=[], timeout_seconds=10,
        backend=None, worker_mutator=mutate)
    assert result['status'] == ('worker-changes-valid' if change == 'production' else 'task-implementation-failure')
    if change != 'production':
        assert result['reason_code'] == 'no-production-change'
        assert result['authorizes'] == []


def test_noop_refactor_remains_legal(tmp_path):
    (tmp_path / 'owner.py').write_text('value = 1\n')
    result = workers._invoke(root=tmp_path, stage='refactor', payload={'slice': {'production_owners': ['owner.py']}},
        allowed=['owner.py'], forbidden=[], timeout_seconds=10, backend=None, worker_mutator=lambda *_: None)
    assert result['status'] == 'worker-changes-valid'


@pytest.mark.parametrize('changed', [[], ['notes.txt'], ['owner.py']])
def test_finish_uses_resolver_production_delta(tmp_path, monkeypatch, changed):
    red = {'stage': 'red', 'predicate_result': True, 'verification_outcome': 'fail', 'failure_family': 'expected-red'}
    before_snapshot = {'schema': 'current-snapshot-resolver.v1', 'sha256': 'before',
                       'git_delta': {'additions': [], 'deletions': [], 'renames': []}}
    after = {**before_snapshot, 'sha256': 'after', 'git_delta': {
        'additions': [{'path': p, 'after_sha256': 'changed'} for p in changed], 'deletions': [], 'renames': []}}
    monkeypatch.setattr(gates, 'current_snapshot', lambda *args, **kwargs: after)
    result = gates.finish_q4(workspace=tmp_path, snapshot_roots=[], source_commit='HEAD',
        before={'schema': 'quick-dev.q4-before.v1', 'predecessor_red_sha256': sha256_value(red), 'current_snapshot': before_snapshot},
        red_stage_result=red, changed_paths=[], slice_item={'production_owners': ['owner.py'],
        'allowed_write_paths': ['owner.py', 'notes.txt'], 'execution_snapshot_paths': ['test_owner.py']})
    assert result['status'] == ('implementation-successor' if changed == ['owner.py'] else 'task-implementation-failure')


@pytest.mark.parametrize('worker_status', ['task-implementation-failure', 'worker-changes-valid'])
def test_stable_runner_never_creates_green_after_noop(tmp_path, monkeypatch, worker_status):
    run = tmp_path / 'run'
    path = run / 'canonical-evidence/red/stage-result.v2.json'
    path.parent.mkdir(parents=True)
    path.write_text('{}')
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'q4_handoff', lambda **kwargs: {'before': {}})
    monkeypatch.setattr(runner, 'run_implementation_worker', lambda **kwargs: {
        'status': worker_status, 'changed_paths': [], 'reason_code': 'no-production-change'})
    monkeypatch.setattr(runner, 'q4_finish', lambda **kwargs: {
        'status': 'task-implementation-failure', 'failure_family': 'task-implementation-failure', 'reason_code': 'no-production-change'})
    result = runner.q4_implementation_worker(semantic=tmp_path / 'plan.json', slice_id='S1', run_dir=run,
        snapshot_roots=[], source_commit='HEAD', base_commit=None, timeout_seconds=10, backend=None)
    assert result['status'] == 'task-implementation-failure'
    assert result.get('required_next_action') != 'run-green'
    assert not (run / 'descriptors/green.json').exists()


def test_cli_returns_nonzero_for_task_implementation_failure(tmp_path, monkeypatch, capsys):
    roots = tmp_path / 'roots.json'
    roots.write_text('[]')
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, '_semantic_plan', lambda _: tmp_path / 'plan.json')
    monkeypatch.setattr(runner, 'q4_implementation_worker', lambda **kwargs: {
        'status': 'task-implementation-failure', 'reason_code': 'no-production-change'})
    monkeypatch.setattr(sys, 'argv', ['quick-dev', '--plan', str(tmp_path), '--slice', 'S1',
        '--action', 'implement', '--run-dir', str(tmp_path / 'run'),
        '--snapshot-roots', str(roots), '--source-commit', 'HEAD'])
    assert runner.main() == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'task-implementation-failure'


def test_q4_finish_materializes_green_for_a_verified_manual_handoff(tmp_path, monkeypatch):
    run = tmp_path / 'run'
    red_path = run / 'descriptors/red.json'
    red_path.parent.mkdir(parents=True)
    red_path.write_text(json.dumps({'stage': 'red'}), encoding='utf-8')
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'load_json', lambda path: (
        {'plan_id': 'PLAN-X', 'slices': [{'slice_id': 'S1'}]}
        if Path(path).name == 'plan.json' else {'stage': 'red'}))
    monkeypatch.setattr(runner, 'finish_q4', lambda **_: {'status': 'implementation-successor'})
    monkeypatch.setattr(runner, 'candidate_identity', lambda *_: {'candidate_hash': 'sha256:after'})
    monkeypatch.setattr(runner, 'successor_descriptor', lambda *_args, **_kwargs: {'stage': 'green'})
    written = {}
    monkeypatch.setattr(runner, 'create_json', lambda path, value: written.update(path=path, value=value))
    result = runner.q4_finish(
        semantic=tmp_path / 'plan.json', slice_id='S1', run_dir=run,
        before={}, snapshot_roots=[], source_commit='HEAD', base_commit=None,
        claimed_changed_paths=['owner.py'],
    )
    assert result['required_next_action'] == 'run-green'
    assert written['path'] == run / 'descriptors/green.json'
    assert written['value'] == {'stage': 'green'}
