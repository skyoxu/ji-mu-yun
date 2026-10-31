"""ADR-0041/0048 and adopted query AD-8: resume a delivery reference, not advice."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import pytest

REPO = Path(__file__).resolve().parents[5]
SCRIPTS = Path(__file__).resolve().parents[1]
for path in (REPO, SCRIPTS, Path(__file__).parent, REPO / 'scripts/sc',
             REPO / 'scripts/toolchain/knowledge_query/tests'):
    sys.path.insert(0, str(path))
import host_session as host
import semantic_compiler as sc
import semantic_worker_v3_group_repair_patch as group
from scripts.toolchain.knowledge_query import adapter
from test_planning_query import published_vdd_base, _switch_fixture_generation
from test_public_source_cache_resume import fixture as public_fixture


def wire(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def public_request(root):
    return {'stage': 'vdd-repair', 'operation': 'repair', 'task_id': 'execution-plans/plan',
            'inputs': ['requirements.md'], 'scope': ['requirements.md'],
            'query': 'current source callers tests contracts requirements.md',
            'record_path': 'execution-plans/plan/execution-record.md'}


@pytest.fixture
def delivered(published_vdd_base, tmp_path, monkeypatch, request):
    root = tmp_path / 'repo'
    root.mkdir()
    _, expected = public_fixture(root)
    shutil.copytree(published_vdd_base, root, dirs_exist_ok=True)
    pointer = json.loads((root / 'knowledge/indexes/current.json').read_text())
    generation = Path('knowledge/indexes/generations') / pointer['generation_id']
    manifest = json.loads((root / generation / 'manifest.json').read_text())
    for item in manifest['artifacts'].values():
        target = root / generation / item['bundle_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((published_vdd_base / generation / item['bundle_path']).read_bytes())
    # Actual adapter/core and actual published permissions; only semantic answers
    # are supplied by the deterministic native host actor below.
    for name in ('toolchain/knowledge_query', 'python'):
        shutil.copytree(REPO / 'scripts' / name, root / 'scripts' / name,
                        dirs_exist_ok=True, ignore=shutil.ignore_patterns('tests', '__pycache__'))
    shutil.copytree(REPO / 'scripts/toolchain/bmad_native', root / 'scripts/toolchain/bmad_native',
                    dirs_exist_ok=True, ignore=shutil.ignore_patterns('tests', '__pycache__'))
    (root / 'execution-plans/plan').mkdir(parents=True, exist_ok=True)
    if getattr(request, 'param', None) in {'classification', 'classification-runtime'}:
        original = expected['v1-FR-1']['obligations'][0]
        original['obligation_kind'] = 'quality'
        if request.param == 'classification':
            (root/'requirements.md').write_text('# FR-1\nThe delivery report must preserve every requirement ID and disclose unproved scope; this is a delivery constraint, not runtime behavior.\n')
            original.update(subject='delivery report scope', trigger='delivery report is evaluated',
                state_before='report is unverified', state_after='original IDs and limits are retained',
                expected_behavior='Preserve every requirement ID and disclose unproved scope in the delivery report.',
                observable_result='Report maps all original IDs and names unproved scope.')
        expected['v3']['failure_intents'][0]['failure_family'] = 'semantic-contract-gap'
        expected['classification-review'] = {'obligations': [deepcopy(original)]}
        if request.param == 'classification':
            expected['classification-review']['obligations'][0]['obligation_kind'] = 'constraint'
        expected['v4']['covered_obligation_ids'] = [sc._normalize_obligation(
            {'requirement_id':'FR-1','source_ref':'requirements.md#FR-1'},original)['obligation_id']]
        for category in ['acceptances','failure_intents','slice_hints']:
            for item in expected['v3'][category]:
                item['obligation_ids'] = expected['v4']['covered_obligation_ids']
    selected_scope = None
    phase_candidate = None
    if getattr(request, 'param', None) == 'phase':
        from test_phase_source_scope import approved, candidate
        import semantic_phase_source_scope as phase
        _, requirement, scope_file, definition = approved.__wrapped__(root)
        definition['read_paths'] = ['PhaseA.Platform/PhaseA.Platform.csproj', 'PhaseA.Platform/packages.lock.json']
        for name in definition['read_paths']:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO / name).read_bytes())
        scope_file.write_text(json.dumps(definition), encoding='utf-8')
        selected_scope = phase.load(root, requirement, scope_file)
        assert len(selected_scope.dependencies) == 6
        phase_candidate = candidate(root)
    req = public_request(root)
    if selected_scope:
        req['scope'] = list(dict.fromkeys([*req['inputs'], *[p for p, _ in selected_scope.dependencies]]))
    paths = [root / p for p in adapter._CANONICAL]
    catalog, policy, projections = [json.loads(p.read_text()) for p in paths]
    envelope = {'consumer': 'vdd', 'query': req['query'], 'policy_revision': policy['policy_revision']}
    selected = adapter.core.locate(envelope, catalog, policy=adapter.core._policy_for(envelope, policy),
        max_candidates=12, eligible_module_ids=adapter.core._projection_for(envelope, catalog, policy, projections))
    pointer = json.loads((root / 'knowledge/indexes/current.json').read_text())
    for row in selected['candidates']:
        target = root / row['path']
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(subprocess.check_output(['git', '-C', str(REPO), 'show',
                pointer['main_commit'] + ':' + row['path']], timeout=10))
    changed = root / selected['candidates'][0]['path']
    with changed.open('a', encoding='utf-8') as stream:
        stream.write('\n# Changed source for UTF-8 degraded reuse fixture.\n')
    prepared = adapter.prepare_consumption(req, root)
    assert prepared['status'] == 'prepared', prepared
    q = prepared['query_result']
    assert q['read_set'] and not q['diagnostic']['closed']
    assert q['outcome'] == 'degraded' and q['reason_code'] == 'source_changed'
    assert not q['candidates'] and q['result']['candidates']
    obligation = sc._normalize_obligation({'source_ref': 'requirements.md#FR-1',
        'requirement_id': 'FR-1'}, expected['v1-FR-1']['obligations'][0])
    payload = {'original_stage': 'v3', 'input': {'obligations': [obligation],
        'planning_source_observations': prepared}, 'validator_findings': []}
    oid = obligation['obligation_id']
    contract = {'acceptance': deepcopy(expected['v3']['acceptances'][0]),
                'failure_intents': deepcopy(expected['v3']['failure_intents']),
                'slice_hint': deepcopy(expected['v3']['slice_hints'][0])}
    for item in [contract['acceptance'], contract['slice_hint'], *contract['failure_intents']]:
        item.pop('obligation_ids', None)
    if selected_scope:
        import semantic_phase_source_scope as phase
        with phase.session(root, selected_scope):
            payload['input']['source_scope'] = phase.description(root)
        contract['slice_hint'] = deepcopy(phase_candidate['slice_hints'][0])
        contract['slice_hint'].pop('obligation_ids', None)
        contract['slice_hint']['execution_snapshot_paths'] += [p for p, _ in selected_scope.dependencies]
    answer = {'obligation_contracts': {oid: contract}}
    session = root / 'logs/origin'
    host.initialize(root, session, 'deterministic-semantic-actor')
    monkeypatch.setenv('SC_LLM_BACKEND', 'host-session')
    monkeypatch.setenv('JIMUYUN_HOST_SESSION_DIR', str(session))
    monkeypatch.setenv('JIMUYUN_HOST_TIMEOUT_SECONDS', '2')
    errors = []
    def invoke():
        try:
            import semantic_phase_source_scope as phase
            with phase.session(root, selected_scope):
                group._live_group_repair_one(root=root, out_dir=root / 'execution-plans/plan', payload=payload,
                    prompt='Compile the frozen contract.' + adapter.consumption_instructions(prepared))
        except BaseException as exc:
            errors.append(exc)
    thread = threading.Thread(target=invoke)
    thread.start()
    end = time.monotonic() + 20
    origin = None
    while thread.is_alive() and time.monotonic() < end:
        for row in host.pending(session):
            origin = Path(row['request_path'])
            r = json.loads(origin.read_text())
            host.respond(session, r['request_id'], host.digest(r), json.dumps(answer))
        time.sleep(.01)
    thread.join(2)
    assert not thread.is_alive() and not errors, errors
    assert origin and json.loads((origin.parent / 'result.json').read_text())['status'] == 'returned'
    # A real repeated delivery consumes the original budget and closes the same
    # episode. Neither the origin nor this terminal row is rewritten by reuse.
    for _ in range(5):
        terminal = adapter.prepare_consumption(req, root)
        if terminal['status'] == 'blocked':
            break
    assert terminal['query_result']['diagnostic']['closed']
    assert terminal['query_result']['episode_id'] == q['episode_id']
    return root, expected, origin, prepared


def run_public(delivered, *, reuse=True, options=(), session_name=None, out_dir=None):
    root, expected, origin, _ = delivered
    session = root / 'logs' / (session_name or ('resume' if reuse else 'default'))
    host.initialize(root, session, 'deterministic-semantic-actor')
    cmd = [sys.executable, '-B', str(root / 'scripts/vdd/compile_plan.py'),
           '--requirements', str(root / 'requirements.md'), '--out-dir', str(out_dir or root / 'execution-plans/plan'),
           '--resume-from', 'first-failed-stage', '--result-json', str(session / 'native.json')]
    if reuse:
        cmd += ['--resume-planning-observation-from', str(origin)]
    cmd += list(options)
    env = dict(os.environ, SC_LLM_BACKEND='host-session', JIMUYUN_HOST_SESSION_DIR=str(session),
               JIMUYUN_HOST_TIMEOUT_SECONDS='15', PYTHONDONTWRITEBYTECODE='1')
    process = subprocess.Popen(cmd, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    seen, handled = [], set()
    end = time.monotonic() + 35
    try:
        while process.poll() is None and time.monotonic() < end:
            for row in host.pending(session):
                if row['request_id'] in handled:
                    continue
                handled.add(row['request_id'])
                request = json.loads(Path(row['request_path']).read_text())
                prompt = request['prompt']
                value, _ = json.JSONDecoder().raw_decode(prompt.split('\n\nINPUT:\n', 1)[1])
                seen.append((prompt, value))
                name = Path(request['output_path']).name
                if name.startswith('v1-classification-review-'):
                    answer = expected['classification-review']
                elif name.startswith('v1-'):
                    answer = expected['v1-FR-1']
                elif name.startswith('v4-atomic-recall'):
                    item = value.get('input', value)
                    answer = {'supported_obligation_ids': [o['obligation_id'] for o in item['obligations']],
                              'invented_obligation_ids': [], 'source_gap_claims': []}
                else:
                    answer = expected['v3'] if name.startswith('v3') else expected['v4']
                host.respond(session, request['request_id'], host.digest(request), json.dumps(answer))
            time.sleep(.01)
        assert process.poll() is not None, 'bounded public fixture timed out'
    finally:
        if process.poll() is None:
            process.terminate()
    stdout, stderr = process.communicate(timeout=5)
    (session / 'stdout.txt').write_bytes(stdout)
    (session / 'stderr.txt').write_bytes(stderr)
    (session / 'argv.json').write_text(json.dumps(cmd), encoding='utf-8')
    (session / 'process-result.json').write_text(json.dumps({'argv':cmd,'cwd':str(root),
        'actual_returncode':process.returncode,'stdout':stdout.decode(),'stderr':stderr.decode(),
        'semantic_actor':'deterministic isolated fixture only; not real S2 checker'},indent=2))
    result = json.loads((session / 'native.json').read_text()) if (session / 'native.json').exists() else None
    return process.returncode, result, seen, stderr.decode(), stdout.decode()


def test_public_resume_uses_only_delivered_reference_and_keeps_closed_budget(delivered):
    root, _, _, prepared = delivered
    record = root / 'execution-plans/plan/execution-record.md'
    before = record.read_bytes()
    code, result, seen, stderr, stdout = run_public(delivered)
    assert code == 0, (result, stderr, stdout)
    assert result['status'] == 'plan-ready' and seen
    assert record.read_bytes().startswith(before)
    assert record.read_bytes().count(b'<!-- planning-query.v1 ') == before.count(b'<!-- planning-query.v1 ')
    decisions = [json.loads(s) for s in record.read_text().splitlines() if s.startswith('{')
                 and json.loads(s).get('kind') == 'planning-source-decision']
    assert decisions, 'The actual final candidate must record native source consumption decisions'
    accepted = [r for r in decisions if r['decision'] == 'accepted']
    rejected = [r for r in decisions if r['decision'] == 'rejected']
    assert any(r['path'] == 'requirements.md' for r in accepted) and rejected
    original_reads = {r['path']: r for r in prepared['query_result']['read_set']}
    for row in decisions:
        original = original_reads[row['path']]
        assert row['sha256'] == original['sha256'] and row['read_identity'] == original['read_identity']
        assert row['origin'] == original['origin']
        assert row['episode_id'] == prepared['query_result']['episode_id']
        assert row['outcome'] == 'degraded' and row['raw_status'] == prepared['query_result']['diagnostic']['raw_status']
        assert row['stage'] == 'vdd-repair' and row['authorizes'] == []
        contract = root / 'execution-plans/plan' / row['actual_use']['contract']
        assert contract.is_file()
        candidate = json.loads(contract.read_text())
        used = row['path'] == 'requirements.md' or any(row['path'] in s.get(key, [])
            for s in candidate.get('slice_hints', candidate.get('slices', []))
            for key in ('production_owners', 'execution_snapshot_paths'))
        assert (row['decision'] == 'accepted') == used
        assert row['actual_use']['effect'] == ('retained input/source/test scope' if used else 'excluded from scope adoption')
    for prompt, payload in seen:
        context = payload['planning_source_observations']
        assert context['status'] == 'reference-only'
        assert context['original_outcome'] == prepared['query_result']['outcome']
        assert context['episode_closed'] is True
        assert 'query_result' not in context and 'excerpt' not in context
        assert 'read_set' not in context and 'candidates' not in context
        assert json.dumps(prepared, ensure_ascii=False, sort_keys=True) not in prompt


def test_default_resume_keeps_real_closed_query_block(delivered):
    code, result, seen, _, _ = run_public(delivered, reuse=False)
    assert code == 1 and result['reason'] == 'PLANNING_QUERY_BLOCKED:budget_exhausted'
    assert not seen


@pytest.mark.parametrize('defect', ['source-change', 'new-scope', 'different-task', 'different-root',
    'request-tamper', 'response-tamper', 'cache-tamper', 'output-tamper', 'not-returned',
    'missing-result', 'missing-progress-return', 'publication-corrupt', 'configuration-change',
    'caller-authored', 'symlink', 'changed-reference'])
def test_public_optin_rejects_invalid_current_binding(delivered, defect):
    root, expected, origin, prepared = delivered
    before = (root / 'execution-plans/plan/execution-record.md').read_bytes()
    if defect == 'source-change':
        (root / prepared['query_result']['read_set'][0]['path']).write_text('Changed after consumption.')
    elif defect == 'changed-reference':
        # A valid new referenced file changes the required input bytes and must
        # not create a new episode or be treated as already-consumed material.
        (root / 'new-reference.md').write_text('New fact.')
        with (root / 'requirements.md').open('a') as stream:
            stream.write('\nNew reference `new-reference.md`.\n')
    elif defect in {'new-scope', 'different-task', 'different-root'}:
        import planning_observation_resume as reuse
        request = public_request(root)
        if defect == 'new-scope':
            request['scope'].append('AGENTS.md')
        elif defect == 'different-task':
            request['task_id'] = 'execution-plans/other'
        else:
            root = root.parent
        with pytest.raises(ValueError, match='PLANNING_OBSERVATION_REUSE_BLOCKED:'):
            reuse.reference(root=root, out_dir=delivered[0] / 'execution-plans/plan',
                            origin=origin, request=request)
        assert (delivered[0] / 'execution-plans/plan/execution-record.md').read_bytes() == before
        return
    elif defect == 'request-tamper':
        request = json.loads(origin.read_text()); request['prompt'] += 'New material'
        origin.write_text(json.dumps(request))
    elif defect == 'response-tamper':
        path = origin.parent / 'response.json'; data = json.loads(path.read_text())
        data['output_text'] = '{}'; path.write_text(json.dumps(data))
    elif defect in {'cache-tamper', 'output-tamper'}:
        r = json.loads(origin.read_text()); output = Path(r['output_path'])
        if defect == 'output-tamper':
            output.write_text('{}')
        else:
            value, _ = json.JSONDecoder().raw_decode(r['prompt'].split('\n\nINPUT:\n', 1)[1])
            stage = output.name.removesuffix('-last-message.json').rsplit('-', 1)[0]
            (root / 'execution-plans/plan/.compiler-cache' / sc._worker_cache_key(stage, value)).write_text('{}')
    elif defect in {'not-returned', 'missing-result'}:
        path = origin.parent / 'result.json'
        if defect == 'missing-result':
            path.unlink()  # A late submitted answer is not an observed delivery.
        else:
            data = json.loads(path.read_text()); data['status'] = 'timeout'; path.write_text(json.dumps(data))
    elif defect == 'missing-progress-return':
        p = root / 'execution-plans/plan/.compiler-work/compiler-progress.jsonl'
        p.write_text('\n'.join(s for s in p.read_text().splitlines() if json.loads(s)['event'] != 'worker-returned') + '\n')
    elif defect == 'publication-corrupt':
        (root / 'knowledge/indexes/current.json').write_text('{invalid')
    elif defect == 'configuration-change':
        p = root / 'knowledge/planning-query.toml'
        p.write_text(p.read_text().replace('enabled = true', 'enabled = false'))
    elif defect == 'caller-authored':
        path = root / 'logs/caller-authored/request.json'; path.parent.mkdir(parents=True)
        path.write_bytes(origin.read_bytes()); origin = path
        delivered = (root, expected, origin, prepared)
    elif defect == 'symlink':
        path = root / 'logs/link'; path.symlink_to(origin.parent, target_is_directory=True)
        delivered = (root, expected, path / 'request.json', prepared)
    code, result, seen, stderr, _ = run_public(delivered)
    assert code == 1 and result and result['status'] == 'repair-vdd', (result, stderr)
    assert not seen
    assert not stderr or 'Traceback' not in stderr
    assert (root / 'execution-plans/plan/execution-record.md').read_bytes() == before


@pytest.mark.parametrize('change', ['unrelated-generation', 'permission-revoked'])
def test_valid_new_publication_rechecks_located_permissions(delivered, change):
    root, _, origin, prepared = delivered
    paths = [root / p for p in adapter._CANONICAL]
    old_generation = prepared['query_result']['index_identity']['generation_id']
    _, _, pointer = _switch_fixture_generation(root, paths, restrict_vdd=change == 'permission-revoked')
    assert pointer['generation_id'] != old_generation
    assert not prepared['query_result']['candidates'] and prepared['query_result']['result']['candidates']
    code, result, seen, stderr, _ = run_public(delivered)
    if change == 'permission-revoked':
        assert code == 1 and result['reason'] == 'PLANNING_OBSERVATION_REUSE_BLOCKED:current_permission_denied'
        assert not seen
    else:
        assert code == 0 and result['status'] == 'plan-ready', (result, stderr)
        assert seen and all(v['planning_source_observations']['original_outcome'] == 'degraded' for _, v in seen)


def test_returned_origin_stays_valid_after_its_deadline(delivered):
    root, _, origin, _ = delivered
    # Do not rewrite the historical request/digest to manufacture an expired
    # witness. Time alone does not undo a native returned delivery.
    import planning_observation_resume as reuse
    deadline = json.loads(origin.read_text())['deadline']
    if deadline >= time.time():
        time.sleep(deadline - time.time() + .01)
    assert time.time() > deadline
    result, _ = reuse.reference(root=root, out_dir=root / 'execution-plans/plan',
                             origin=origin, request=public_request(root))
    assert result['status'] == 'reference-only' and result['episode_closed']


def test_reference_advice_keeps_native_budget_input_identity(delivered):
    root, _, origin, prepared = delivered
    import planning_observation_resume as reuse
    from workflow_unit_budget import worker_input
    reference, _ = reuse.reference(root=root, out_dir=root / 'execution-plans/plan',
                               origin=origin, request=public_request(root))
    original = json.loads(origin.read_text())['prompt']
    header, raw = original.split('\n\nINPUT:\n', 1)
    payload, _ = json.JSONDecoder().raw_decode(raw)
    changed = deepcopy(payload)
    changed['input']['planning_source_observations'] = reference
    replaced = header + '\n\nINPUT:\n' + json.dumps(changed)
    assert worker_input(original, 'old-output') == worker_input(replaced, 'new-output')


@pytest.mark.parametrize('delivered', ['phase'], indirect=True)
@pytest.mark.parametrize('change', ['absent', 'changed'])
def test_public_phase_origin_requires_current_exact_scope(delivered, change):
    root, _, origin, prepared = delivered
    assert len(prepared['query_result']['diagnostic']['source_hashes']) == 6
    options = []
    if change == 'changed':
        path = root / 'scope.json'
        scope = json.loads(path.read_text())
        scope['support_paths'].append('tests/changed.py')
        path.write_text(json.dumps(scope))
        options = ['--source-scope', str(path)]
    code, result, seen, stderr, _ = run_public(delivered, options=options)
    assert code == 1 and result and result['status'] == 'repair-vdd', (result, stderr)
    assert result['reason'] == 'PLANNING_OBSERVATION_REUSE_BLOCKED:current_source_scope_changed'
    assert not seen


@pytest.mark.parametrize('mode', ['--recommendation-only', '--worker-cache', '--admission-only'])
def test_reference_mode_cannot_select_alternate_execution_routes(delivered, mode):
    root, _, _, _ = delivered
    options = [mode]
    if mode == '--worker-cache':
        path = root / 'fixture-cache.json'; path.write_text('{}')
        options.append(str(path))
    code, result, seen, stderr, _ = run_public(delivered, options=options)
    assert code == 2 and result is None and not seen
    assert 'requires ordinary native resume' in stderr and 'unrecognized arguments' not in stderr


@pytest.mark.parametrize('delivered', ['phase'], indirect=True)
def test_current_phase_scope_rechecks_all_six_inputs(delivered):
    root, _, origin, _ = delivered
    import planning_observation_resume as reuse
    import semantic_phase_source_scope as phase
    selected = phase.load(root, root / 'requirements.md', root / 'scope.json')
    request = public_request(root)
    request['scope'] = list(dict.fromkeys([*request['inputs'], *[p for p, _ in selected.dependencies]]))
    with phase.session(root, selected):
        result, _ = reuse.reference(root=root, out_dir=root / 'execution-plans/plan', origin=origin, request=request)
    assert result['status'] == 'reference-only' and len(selected.dependencies) == 6


def test_reference_fixture_reads_its_own_published_generation(published_vdd_base, tmp_path, monkeypatch, request):
    """ADR-0048: native recovery fixtures cannot borrow device generation bytes."""
    original = Path.read_bytes
    private_generations = (REPO / 'knowledge/indexes/generations').resolve()
    def reject_device_generation(path):
        assert not path.resolve().is_relative_to(private_generations), 'device generation read'
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', reject_device_generation)
    root, _, origin, prepared = delivered.__wrapped__(published_vdd_base, tmp_path, monkeypatch, request)
    pointer = json.loads((root / 'knowledge/indexes/current.json').read_text())
    assert pointer == json.loads((published_vdd_base / 'knowledge/indexes/current.json').read_text())
    assert origin.is_file() and json.loads((origin.parent / 'result.json').read_text())['status'] == 'returned'
    assert prepared['query_result']['read_set']
    assert prepared['query_result']['outcome'] == 'degraded'
