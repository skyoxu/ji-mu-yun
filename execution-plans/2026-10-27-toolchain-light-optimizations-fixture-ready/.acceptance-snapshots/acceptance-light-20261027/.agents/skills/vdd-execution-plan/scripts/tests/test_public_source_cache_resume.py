"""ADR-0041: public CLI + real native host protocol, deterministic fake author.

No model, BMAD, original plan, historical receipt rewriting or cache injection.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
REPO = SCRIPTS.parents[3]
for path in (SCRIPTS, Path(__file__).parent, REPO / 'scripts/sc'):
    sys.path.insert(0, str(path))
import host_session as host
import semantic_resume_cache as replay
import semantic_worker_transport_patch as transport
from semantic_worker_errors import WorkerTransportError
from test_ch456_compiler_closure import _repo, _cache


def fixture(root):
    _, req, owner, selector = _repo(root)
    shutil.copytree(SCRIPTS, root / '.agents/skills/vdd-execution-plan/scripts',
                    ignore=shutil.ignore_patterns('tests', '__pycache__'))
    # ADR-0041: use the actual shared consumer in the isolated public repo.
    shutil.copytree(REPO / '.agents/skills/quick-dev-tdd-adapter/tools',
                    root / '.agents/skills/quick-dev-tdd-adapter/tools',
                    ignore=shutil.ignore_patterns('tests', '__pycache__'))
    shutil.copytree(REPO / 'scripts/quick_dev', root / 'scripts/quick_dev',
                    ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('vdd/compile_plan.py', 'workflow_unit_budget.py',
                 'sc/_llm_backend.py', 'sc/model_config.py', 'sc/host_session.py'):
        target = root / 'scripts' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / 'scripts' / name, target)
    adapter = root / 'scripts/toolchain/knowledge_query/adapter.py'
    adapter.parent.mkdir(parents=True)
    adapter.write_text('''import json
def prepare_consumption(payload, root):
    record = root / 'query-count.txt'
    count = int(record.read_text()) + 1 if record.exists() else 1
    record.write_text(str(count))
    if (root / 'deny-query').exists():
        return {'status':'blocked','query_result':{'reason_code':'permission_denied'},'authorizes':[]}
    return {'status':'prepared','queried':True,'authorizes':[],
            'query_result':{'stage':payload['stage'],'attempt':count,'request_id':str(count)}}
def consumption_instructions(prepared):
    return ('\\nPlanning source observations (advisory, not requirement authority):\\n'
            + json.dumps(prepared,ensure_ascii=False,sort_keys=True) + '\\nKeep required gates.\\n')
''', encoding='utf-8')
    subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
    return req, _cache(owner, selector)


def run_public(root, expected, session_name, *, cancel_v3=False, prior=None):
    session = root / 'logs' / session_name
    host.initialize(root, session, 'deterministic-test-author')
    cmd = [sys.executable, '-B', str(root/'scripts/vdd/compile_plan.py'),
           '--requirements', str(root/'requirements.md'), '--out-dir', str(root/'plan'),
           '--result-json', str(session/'native.json')]
    if prior:
        cmd += ['--resume-from', 'first-failed-stage', '--resume-worker-session', str(prior)]
    env = dict(os.environ, SC_LLM_BACKEND='host-session', JIMUYUN_HOST_SESSION_DIR=str(session),
               JIMUYUN_HOST_TIMEOUT_SECONDS='10')
    calls = []
    handled = set()
    with (session/'stdout.txt').open('wb') as stdout, (session/'stderr.txt').open('wb') as stderr:
        process = subprocess.Popen(cmd, cwd=root, env=env, stdout=stdout, stderr=stderr)
        deadline = time.monotonic() + 30
        try:
            while process.poll() is None and time.monotonic() < deadline:
                for row in host.pending(session):
                    if row['request_id'] in handled:
                        continue
                    handled.add(row['request_id'])
                    request = json.loads(Path(row['request_path']).read_text())
                    name = Path(request['output_path']).name
                    calls.append(name)
                    raw = json.loads(request['prompt'].rsplit('\n\nINPUT:\n', 1)[1])
                    if name.startswith('v3') and cancel_v3:
                        subprocess.run([sys.executable, str(root/'scripts/sc/host_session.py'),
                            'cancel', '--session', str(session), '--request-id', request['request_id']],
                            check=True, stdout=subprocess.DEVNULL)
                        continue
                    if name.startswith('v1-'):
                        answer = deepcopy(expected['v1-FR-1'])
                        for obligation in answer['obligations']:
                            obligation['source_refs'] = [raw['source']['source_ref']]
                            if 'stable plan' in raw['source']['source_text']:
                                obligation['expected_behavior'] = 'emit a stable plan'
                    elif name.startswith('v4-atomic-recall'):
                        payload = raw.get('input', raw)
                        answer = {'supported_obligation_ids':[o['obligation_id'] for o in payload['obligations']],
                                  'invented_obligation_ids':[], 'source_gap_claims':[]}
                    elif name.startswith('v3'):
                        answer = expected['v3']
                    else:
                        answer = expected['v4']
                    host.respond(session, request['request_id'], host.digest(request), json.dumps(answer))
                time.sleep(.01)
            assert process.poll() is not None, 'public fixture exceeded its bounded test budget'
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
    result_path = session/'native.json'
    assert result_path.exists(), (session/'stderr.txt').read_text()
    return json.loads(result_path.read_text()), calls, session


def hashes(directory):
    return {str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file()}


def test_public_resume_preserves_native_v1_and_source_checks(tmp_path):
    _, expected = fixture(tmp_path)
    first, calls, old = run_public(tmp_path, expected, 'first', cancel_v3=True)
    assert first['status'] == 'repair-vdd' and first['transport_exit_code'] == 130
    assert any(n.startswith('v1-') for n in calls)
    before = hashes(old)
    # Emulate pre-upgrade r3: it has the raw native cache/receipt but no new
    # source-replay metadata. Only this disposable test namespace is changed.
    metadata = tmp_path/'plan/.compiler-cache/source-replay'
    shutil.rmtree(metadata)
    second, calls, _ = run_public(tmp_path, expected, 'resume', prior=old)
    assert second['status'] == 'plan-ready', second
    assert second['worker_cache_reuse']['legacy_v1_replays'] >= 1
    assert not any(n.startswith('v1-') or n.startswith('v4-atomic-recall') for n in calls), calls
    assert any(n.startswith('v3') for n in calls)
    assert hashes(old) == before


def source(text='Required behavior.'):
    return {'source_ref':'req.md#FR-1', 'requirement_id':'FR-1', 'source_text':text,
            'text_sha256':transport.sc.sha256_bytes(text.encode()), 'source_sha256':'file-old',
            'source_order':1, 'line':1}


def test_source_identity_ignores_query_git_position_but_binds_context():
    a = {'source':source(), 'planning_source_observations':{'git':'old'}}
    b = deepcopy(a)
    b['planning_source_observations'] = {'git':'new'}
    b['source'].update(line=90, source_order=30, source_sha256='file-new')
    prompt = '\nPlanning source observations (advisory, not requirement authority):\n{}\nRead source.'
    identity = replay.content_identity('v1-FR-1', a, prompt, 'role')
    assert identity == replay.content_identity('v1-FR-1', b, prompt, 'role')
    b['companions'] = [{'source_text':'Changed interpretation context'}]
    assert identity != replay.content_identity('v1-FR-1', b, prompt, 'role')
    b = {'source':source('Changed required behavior.')}
    assert identity != replay.content_identity('v1-FR-1', b, prompt, 'role')
    assert identity != replay.content_identity('v1-FR-1', a, prompt, 'new-role')


def test_public_changed_anchor_only_reextracts_that_anchor_and_git_only_reuses(tmp_path):
    req, expected = fixture(tmp_path)
    req.write_text(req.read_text() + '\n# FR-2\nThe compiler must emit a deterministic plan.\n')
    first, _, old = run_public(tmp_path, expected, 'first', cancel_v3=True)
    assert first['transport_exit_code'] == 130
    req.write_text(req.read_text().replace('deterministic plan', 'stable plan', 1))
    changed, calls, _ = run_public(tmp_path, expected, 'changed', cancel_v3=True, prior=old)
    assert changed['transport_exit_code'] == 130, changed
    v1_calls = [name for name in calls if name.startswith('v1-')]
    assert len(v1_calls) == 1 and v1_calls[0].startswith('v1-FR-1-'), calls
    assert changed['worker_cache_reuse']['source_content_replays'] >= 1
    subprocess.run(['git', 'add', 'requirements.md'], cwd=tmp_path, check=True)
    subprocess.run(['git','-c','user.name=Fixture','-c','user.email=test@example.invalid',
                    'commit','-qm','Git provenance only'], cwd=tmp_path, check=True)
    again, calls, _ = run_public(tmp_path, expected, 'git-only', cancel_v3=True, prior=old)
    assert again['transport_exit_code'] == 130, again
    assert not any(n.startswith('v1-') or n.startswith('v4-atomic-recall') for n in calls), calls


@pytest.mark.parametrize('mutation', ['receipt', 'cache', 'response'])
def test_public_legacy_tampering_blocks_without_reexecuting(tmp_path, mutation):
    _, expected = fixture(tmp_path)
    _, _, old = run_public(tmp_path, expected, 'first', cancel_v3=True)
    shutil.rmtree(tmp_path/'plan/.compiler-cache/source-replay')
    if mutation == 'receipt':
        path = next((tmp_path/'plan/.compiler-work/worker-receipts').glob('v1-*.json'))
        data = json.loads(path.read_text()); data['schema_valid'] = False
    elif mutation == 'cache':
        path = next((tmp_path/'plan/.compiler-cache').glob('v1-*.json'))
        data = json.loads(path.read_text()); data['obligations'][0]['expected_behavior'] = 'tampered'
    else:
        path = next(p for p in old.glob('*/response.json')
                    if 'v1-' in json.loads((p.parent/'request.json').read_text())['output_path'])
        data = json.loads(path.read_text()); data['request_sha256'] = 'wrong'
    path.write_text(json.dumps(data))
    result, calls, _ = run_public(tmp_path, expected, 'refused', prior=old)
    assert result['status'] == 'repair-vdd' and result['transport_category'] == 'artifact-integrity', result
    assert calls == []


@pytest.mark.parametrize('state', ['timeout', 'unconsumed'])
def test_public_timeout_or_unconsumed_response_is_not_adopted(tmp_path, state):
    _, expected = fixture(tmp_path)
    _, _, old = run_public(tmp_path, expected, 'first', cancel_v3=True)
    shutil.rmtree(tmp_path/'plan/.compiler-cache/source-replay')
    path = next(p.parent/'result.json' for p in old.glob('*/request.json')
                if 'v1-' in json.loads(p.read_text())['output_path'])
    if state == 'timeout':
        data = json.loads(path.read_text()); data['status'] = 'timeout'; path.write_text(json.dumps(data))
    else:
        path.unlink()
    result, calls, _ = run_public(tmp_path, expected, 'fresh', cancel_v3=True, prior=old)
    assert result['transport_exit_code'] == 130, result
    assert result['worker_cache_reuse']['legacy_v1_replays'] == 0
    assert sum(n.startswith('v1-') for n in calls) == 1


def test_public_current_query_refusal_precedes_reuse(tmp_path):
    _, expected = fixture(tmp_path)
    _, _, old = run_public(tmp_path, expected, 'first', cancel_v3=True)
    (tmp_path/'deny-query').touch()
    result, calls, _ = run_public(tmp_path, expected, 'refused', prior=old)
    assert result['status'] == 'repair-vdd' and 'PLANNING_QUERY_BLOCKED:permission_denied' in result['reason']
    assert calls == []


def test_public_cached_candidate_still_runs_v2_and_dependency_guard(tmp_path):
    _, expected = fixture(tmp_path)
    expected['v1-FR-1']['obligations'][0]['depends_on'] = ['O-NOT-IN-CURRENT-SOURCE']
    first, _, old = run_public(tmp_path, expected, 'first')
    assert first['status'] == 'repair-vdd' and first['stage'] == 'V3-execution-preflight', first
    second, calls, _ = run_public(tmp_path, expected, 'guarded', prior=old)
    assert second['status'] == 'repair-vdd' and second['stage'] == 'V3-execution-preflight', second
    assert any('dependency:target-not-in-plan' in item for item in second['findings'])
    assert second['worker_cache_reuse']['source_content_replays'] == 1
    assert not any(n.startswith('v1-') for n in calls)
    progress = [json.loads(line) for line in (tmp_path/'plan/.compiler-work/compiler-progress.jsonl').read_text().splitlines()]
    assert sum(row.get('stage') == 'V2' and row['event'] == 'stage-returned' for row in progress) == 2
    assert not (tmp_path/'plan/compiler-state.v1.json').exists()


def test_content_cache_tampering_blocks_before_model(tmp_path):
    replay.configure(root=tmp_path, out_dir=tmp_path/'plan', session=None)
    args = dict(root=tmp_path, out_dir=tmp_path/'plan', stage='v1-FR-1', payload={'source':source()},
                prompt='Extract.', role_contract='role')
    value, identity = replay.lookup(**args)
    assert value is None
    replay.save(out_dir=args['out_dir'], identity=identity, value={'obligations':[]}, origin='test-candidate')
    path = replay._path(args['out_dir'], identity)
    bad = json.loads(path.read_text()); bad['candidate'] = {'obligations':['changed']}
    path.write_text(json.dumps(bad))
    with pytest.raises(WorkerTransportError, match='artifact-integrity'):
        replay.lookup(**args)
