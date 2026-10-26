"""ADR-0041: public pause/resume with fake author; no real models or BMAD."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from test_public_source_cache_resume import fixture, hashes, host


def run(root, expected, name, *, pause=True, resume=False, cancel=False):
    session = root / 'logs' / name
    host.initialize(root, session, 'deterministic-pause-author')
    cmd = [sys.executable, '-B', str(root/'scripts/vdd/compile_plan.py'),
           '--requirements', str(root/'requirements.md'), '--out-dir', str(root/'plan'),
           '--result-json', str(session/'native.json')]
    if pause:
        cmd += ['--stop-after', 'v3']
    if resume:
        cmd += ['--resume-from', 'first-failed-stage']
    env = dict(os.environ, SC_LLM_BACKEND='host-session',
               JIMUYUN_HOST_SESSION_DIR=str(session), JIMUYUN_HOST_TIMEOUT_SECONDS='10')
    calls, handled = [], set()
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
                    stage = Path(request['output_path']).name
                    calls.append(stage)
                    raw = json.loads(request['prompt'].rsplit('\n\nINPUT:\n', 1)[1])
                    if stage.startswith('v3') and cancel:
                        (Path(row['request_path']).parent/'cancel.json').write_text('{"authorizes":[]}')
                        continue
                    if stage.startswith('v1-'):
                        answer = deepcopy(expected['v1-FR-1'])
                        for ob in answer['obligations']:
                            ob['source_refs'] = [raw['source']['source_ref']]
                            if 'stable plan' in raw['source']['source_text']:
                                ob['expected_behavior'] = 'emit a stable plan'
                    elif stage.startswith('v4-atomic-recall'):
                        payload = raw.get('input', raw)
                        answer = {'supported_obligation_ids':[o['obligation_id'] for o in payload['obligations']],
                                  'invented_obligation_ids':[], 'source_gap_claims':[]}
                    elif stage.startswith('v3'):
                        answer = expected['v3']
                    else:
                        answer = expected['v4']
                    host.respond(session, request['request_id'], host.digest(request), json.dumps(answer))
                time.sleep(.01)
            assert process.poll() is not None, 'bounded public fixture did not finish'
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
    result = session/'native.json'
    assert result.exists(), (session/'stderr.txt').read_text()
    return json.loads(result.read_text()), calls, session, process.returncode


def test_public_pause_then_resume_reuses_v3_and_preserves_history(tmp_path):
    _, expected = fixture(tmp_path)
    first, calls, session, code = run(tmp_path, expected, 'pause')
    assert code == 0 and first['status'] == 'paused', first
    assert first['authorizes'] == [] and first['acceptance_count'] == 1
    assert first['completed_checks'] == ['V3','V3A','V3-execution-preflight']
    assert any(s.startswith('v3') for s in calls)
    assert not (tmp_path/'plan/compiler-state.v1.json').exists()
    progress = [json.loads(s) for s in (tmp_path/'plan/.compiler-work/compiler-progress.jsonl').read_text().splitlines()]
    assert not any(p['stage'].startswith('V4') for p in progress)
    before_session = hashes(session)
    checkpoint = Path(first['checkpoint']['path'])
    before_checkpoint = checkpoint.read_bytes()
    result, calls, _, code = run(tmp_path, expected, 'resume', pause=False, resume=True)
    assert code == 0 and result['status'] == 'plan-ready', result
    assert result['v3_checkpoint_reused'] is True
    assert not any(s.startswith('v3') or s.startswith('v1-') for s in calls), calls
    assert result['worker_cache_reuse']['source_content_replays'] > 0
    resumed_progress = [json.loads(s) for s in (tmp_path/'plan/.compiler-work/compiler-progress.jsonl').read_text().splitlines()][len(progress):]
    assert {'V0A','V2','V3A','V3-execution-preflight'} <= {p['stage'] for p in resumed_progress}
    assert before_session == hashes(session)
    assert checkpoint.read_bytes() == before_checkpoint


def test_public_default_still_runs_through_publication(tmp_path):
    _, expected = fixture(tmp_path)
    result, _, _, code = run(tmp_path, expected, 'default', pause=False)
    assert code == 0 and result['status'] == 'plan-ready', result
    assert not list((tmp_path/'plan/.compiler-work').glob('v3-checkpoints/*.json'))


def test_public_git_only_resume_can_pause_idempotently(tmp_path):
    _, expected = fixture(tmp_path)
    first, _, _, code = run(tmp_path, expected, 'first')
    assert code == 0 and first['status'] == 'paused', first
    subprocess.run(['git','-c','user.name=Fixture','-c','user.email=test@example.invalid',
                    'commit','--allow-empty','-qm','Git-only provenance'], cwd=tmp_path, check=True)
    second, calls, _, code = run(tmp_path, expected, 'second', resume=True)
    assert code == 0 and second['status'] == 'paused', second
    assert second['v3_checkpoint_reused'] and not calls, calls
    assert second['checkpoint'] == first['checkpoint']


def test_public_changed_source_revalidates_and_requests_new_contract(tmp_path):
    req, expected = fixture(tmp_path)
    first, _, _, _ = run(tmp_path, expected, 'first')
    old = Path(first['checkpoint']['path']); old_bytes = old.read_bytes()
    req.write_text(req.read_text().replace('deterministic plan','stable plan'))
    # The fake author must bind its changed V3 result to the newly frozen ID.
    from semantic_compiler import _normalize_obligation
    ob = deepcopy(expected['v1-FR-1']['obligations'][0])
    ob['expected_behavior'] = 'emit a stable plan'
    oid = _normalize_obligation({'requirement_id':'FR-1','source_ref':'requirements.md#FR-1'},ob)['obligation_id']
    for key in ('acceptances','failure_intents','slice_hints'):
        for item in expected['v3'][key]:
            item['obligation_ids'] = [oid]
    second, calls, _, code = run(tmp_path, expected, 'changed', resume=True)
    assert code == 0 and second['status'] == 'paused', second
    assert not second['v3_checkpoint_reused']
    assert any(s.startswith('v1-') for s in calls) and any(s.startswith('v3') for s in calls), calls
    assert second['source_index_sha256'] != first['source_index_sha256']
    assert old.read_bytes() == old_bytes


@pytest.mark.parametrize('mutation', ['candidate','invalid-body-with-updated-digest','deleted-owner'])
def test_public_invalid_candidate_or_current_owner_never_successfully_pauses(tmp_path, mutation):
    _, expected = fixture(tmp_path)
    first, _, _, _ = run(tmp_path, expected, 'first')
    if mutation in {'candidate','invalid-body-with-updated-digest'}:
        path = Path(first['checkpoint']['path']); record = json.loads(path.read_text())
        record['candidate']['acceptances'][0]['then'] = 'tampered'
        if mutation == 'invalid-body-with-updated-digest':
            from semantic_compiler import sha256_value
            record['candidate']['acceptances'][0]['oracle']['observable'] = ''
            record['candidate_sha256'] = sha256_value(record['candidate'])
        path.write_text(json.dumps(record))
    else:
        (tmp_path/'src/compiler.py').unlink()
    second, calls, _, code = run(tmp_path, expected, 'rejected', resume=True)
    assert code != 0 and second['status'] == 'repair-vdd', second
    assert not any(s.startswith('v3') for s in calls), calls
    assert not (tmp_path/'plan/compiler-state.v1.json').exists()


def test_public_cancel_is_failure_without_pause_checkpoint(tmp_path):
    _, expected = fixture(tmp_path)
    result, _, _, code = run(tmp_path, expected, 'cancel', cancel=True)
    assert code == 130 and result['status'] == 'repair-vdd', result
    assert not list((tmp_path/'plan/.compiler-work').glob('v3-checkpoints/*.json'))


def test_public_native_v3_failure_never_saves_pause(tmp_path):
    _, expected = fixture(tmp_path)
    expected['v3']['acceptances'][0]['oracle']['observable'] = ''
    result, _, _, code = run(tmp_path, expected, 'invalid-native')
    assert code != 0 and result['status'] == 'repair-vdd', result
    assert not list((tmp_path/'plan/.compiler-work').glob('v3-checkpoints/*.json'))


def test_public_completed_plan_is_not_relabeled_paused(tmp_path):
    _, expected = fixture(tmp_path)
    result, _, _, code = run(tmp_path, expected, 'complete', pause=False)
    assert code == 0 and result['status'] == 'plan-ready'
    original_state = (tmp_path/'plan/compiler-state.v1.json').read_bytes()
    result, calls, _, code = run(tmp_path, expected, 'not-a-pause', resume=True)
    assert code != 0 and result['status'] == 'repair-vdd', result
    assert not calls
    assert (tmp_path/'plan/compiler-state.v1.json').read_bytes() == original_state


def test_public_current_security_gate_still_precedes_pause_reuse(tmp_path):
    _, expected = fixture(tmp_path)
    first, _, _, code = run(tmp_path, expected, 'first')
    assert code == 0 and first['status'] == 'paused'
    (tmp_path/'deny-query').write_text('deny')
    result, calls, _, code = run(tmp_path, expected, 'denied', resume=True)
    assert code != 0 and result['status'] == 'repair-vdd'
    assert 'permission_denied' in result['reason'] and not calls


def test_public_failed_execution_preflight_cannot_pause(tmp_path):
    _, expected = fixture(tmp_path)
    expected['v1-FR-1']['obligations'][0]['depends_on'] = ['O-NOT-IN-CURRENT-SOURCE']
    result, _, _, code = run(tmp_path, expected, 'dependency')
    assert code != 0 and result['status'] == 'repair-vdd', result
    assert result['stage'] == 'V3-execution-preflight'
    assert any('dependency:target-not-in-plan' in s for s in result['findings'])
    assert not list((tmp_path/'plan/.compiler-work').glob('v3-checkpoints/*.json'))


@pytest.mark.parametrize('other', ['--recommendation-only', '--worker-cache'])
def test_public_pause_rejects_non_native_modes(tmp_path, other):
    fixture(tmp_path)
    command = [sys.executable, '-B', str(tmp_path/'scripts/vdd/compile_plan.py'),
               '--requirements',str(tmp_path/'requirements.md'), '--out-dir',str(tmp_path/'plan'),
               '--stop-after','v3',other]
    if other == '--worker-cache':
        command += [str(tmp_path/'not-loaded.json')]
    result = subprocess.run(command,cwd=tmp_path,capture_output=True,text=True,timeout=10)
    assert result.returncode == 2
    assert 'without fixture or contract repair modes' in result.stderr
    assert not (tmp_path/'plan').exists()
