"""ADR-0041: native session admission, real progression and failure boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stable_runner as api
from execution_session import preflight_session, advance_session, SCHEMA
from runtime_evidence import sha256_bytes
from test_cer_behavior_routing import fixture


def setup_session(root, monkeypatch, present=(True, True)):
    semantic, roots = fixture(root, present)
    bundle = json.loads(semantic.read_text())
    fields = dict(complexity_class='simple', verification_lane='unit', context_lookup_required=False,
                  context_lookup_reason='Single fixture', minimum_red_scope='Bound cases', upgrade_conditions=['New owner'])
    bundle['slices'][0].update(fields, proof={'selector_intents': ['tests/test_one.py']})
    semantic.write_text(json.dumps(bundle), encoding='utf-8')
    for row in roots:
        if row['root_kind'] == 'descriptor': row['repository_relative_posix_path'] = 'logs/session/S1/descriptors'
    (root/'.gitignore').write_text('logs/\n__pycache__/\n.pytest_cache/\n', encoding='utf-8')
    for cmd in (['init','-q'], ['add','.'], ['-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture']):
        subprocess.run(['git',*cmd], cwd=root, check=True, capture_output=True)
    commit = subprocess.check_output(['git','rev-parse','HEAD'], cwd=root, text=True).strip()
    monkeypatch.setattr(api, 'ROOT', root)
    monkeypatch.chdir(root)
    request = {'schema': SCHEMA, 'plan_sha256': sha256_bytes(semantic.read_bytes()), 'profile': 'standard',
               'source_commit': commit, 'base_commit': commit, 'targeted_timeout_seconds': 20,
               'slices': [{'slice_id':'S1','run_dir':'logs/session/S1','snapshot_roots':roots,'ready_path':'logs/session/S1-ready.json'}],
               'snapshot_roots':roots,'out':'logs/session/closure/complete.json'}
    return semantic, request


def test_readonly_preflight_and_real_present_session_resume(tmp_path, monkeypatch):
    semantic, request = setup_session(tmp_path, monkeypatch)
    assert preflight_session(api, semantic, request)['status'] == 'preflight-passed'
    assert not (tmp_path/'logs').exists()
    for _ in range(3): assert advance_session(api, semantic, request, max_steps=1)['status'] == 'paused'
    finished = advance_session(api, semantic, request, max_steps=1)
    assert finished['status'] == 'implementation-complete'
    receipts = {str(p): p.read_bytes() for p in (tmp_path/'logs').rglob('process-receipt.v2.json')}
    monkeypatch.setattr(api, 'run_red_author', lambda **kw: pytest.fail('no worker permitted'))
    assert advance_session(api, semantic, request, max_steps=1)['status'] == 'implementation-complete'
    assert receipts == {str(p): p.read_bytes() for p in (tmp_path/'logs').rglob('process-receipt.v2.json')}
    binding = json.loads((tmp_path/finished['acceptance_binding']).read_text())
    assert binding['baseCommit'] == request['base_commit']
    assert finished['completion']['authorizes'] == []


def test_missing_route_stops_before_implementation_worker(tmp_path, monkeypatch):
    semantic, request = setup_session(tmp_path, monkeypatch, (False, True))
    monkeypatch.setattr(api, 'run_implementation_worker', lambda **kw: pytest.fail('no worker permitted'))
    result = advance_session(api, semantic, request)
    assert (result['status'],result['required_next_action']) == ('worker-required','implement')
    assert not (tmp_path/'logs/session/S1/descriptors/green.json').exists()


@pytest.mark.parametrize('change,match', [('baseline','base_commit'), ('profile','detached_bundle'), ('hash','identity'),
    ('escape','relative|escapes|outside|path'), ('duplicate','exactly once'), ('collision','collide'), ('roots','eight'), ('timeout','timeout')])
def test_preflight_rejects_before_any_run(tmp_path, monkeypatch, change, match):
    semantic, request = setup_session(tmp_path, monkeypatch)
    if change == 'baseline': request['base_commit'] = None
    elif change == 'profile': request['profile'] = 'self-hosted'
    elif change == 'hash': request['plan_sha256'] = 'sha256:'+'0'*64
    elif change == 'escape': request['slices'][0]['run_dir'] = '../escape'
    elif change == 'duplicate': request['slices'].append(deepcopy(request['slices'][0]))
    elif change == 'collision': request['out'] = request['slices'][0]['ready_path']
    elif change == 'roots': request['snapshot_roots'] = []
    elif change == 'timeout': request['targeted_timeout_seconds'] = 0
    with pytest.raises(ValueError, match=match): advance_session(api, semantic, request)
    assert not (tmp_path/'logs').exists()


def test_changed_product_cannot_reuse_completed_session(tmp_path, monkeypatch):
    semantic, request = setup_session(tmp_path, monkeypatch)
    assert advance_session(api, semantic, request)['status'] == 'implementation-complete'
    (tmp_path/'candidate.py').write_text('def value(kind): return -99\n', encoding='utf-8')
    with pytest.raises(ValueError): advance_session(api, semantic, request)


def test_public_cli_session_preflight_is_readonly(tmp_path, monkeypatch, capsys):
    semantic, request = setup_session(tmp_path, monkeypatch)
    input_path = tmp_path/'session.json'; input_path.write_text(json.dumps(request), encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['run.py','--plan',str(semantic.parent),'--action','preflight-session','--execution-request',str(input_path)])
    assert api.main() == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'preflight-passed'
    assert not (tmp_path/'logs').exists()


def test_missing_root_is_rejected_before_execution(tmp_path, monkeypatch):
    semantic, request = setup_session(tmp_path, monkeypatch)
    request['snapshot_roots'][0]['repository_relative_posix_path'] = 'absent-input.txt'
    with pytest.raises(ValueError, match='snapshot input missing'):
        advance_session(api, semantic, request)
    assert not (tmp_path/'logs').exists()


def test_session_request_cannot_change_on_resume(tmp_path, monkeypatch):
    semantic, request = setup_session(tmp_path, monkeypatch)
    assert advance_session(api, semantic, request, max_steps=1)['status'] == 'paused'
    request['targeted_timeout_seconds'] = 30
    with pytest.raises(ValueError):
        advance_session(api, semantic, request)


def test_session_completion_is_consumed_by_acceptance(tmp_path, monkeypatch):
    semantic, request = setup_session(tmp_path, monkeypatch)
    finished = advance_session(api, semantic, request)
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'run-refactor-implementation-acceptance/scripts'))
    from current_quick_dev_handoff import verify_current_handoff
    binding = json.loads((tmp_path/finished['acceptance_binding']).read_text())
    verified = verify_current_handoff(tmp_path, binding)
    assert verified


def test_documentary_guard_allows_only_valid_empty_owner(tmp_path, monkeypatch):
    semantic, request = setup_session(tmp_path, monkeypatch)
    bundle = json.loads(semantic.read_text())
    for obligation in bundle['obligations']:
        obligation.update(obligation_kind='governance', requirement_type='Governance')
    bundle['slices'][0]['production_owners'] = []
    from semantic_behavior_contract import project_intents
    bundle['behavior_routing']['intents'] = project_intents(bundle)
    semantic.write_text(json.dumps(bundle), encoding='utf-8')
    request['plan_sha256'] = sha256_bytes(semantic.read_bytes())
    assert preflight_session(api, semantic, request)['status'] == 'preflight-passed'
    bundle['obligations'][0]['obligation_kind'] = 'behavior'
    bundle['behavior_routing']['intents'] = project_intents(bundle)
    semantic.write_text(json.dumps(bundle), encoding='utf-8')
    request['plan_sha256'] = sha256_bytes(semantic.read_bytes())
    with pytest.raises(ValueError):
        preflight_session(api, semantic, request)
