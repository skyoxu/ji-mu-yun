"""ADR-0041/0048, query FR09/AD8: plain native correction consumes only a reference."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_planning_observation_resume import delivered, published_vdd_base, run_public
from test_planning_query import _switch_fixture_generation
import semantic_worker_v3_group_repair_patch as group
from scripts.toolchain.knowledge_query import adapter


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def correction(delivered):
    root, expected, origin, _ = delivered
    request = json.loads(origin.read_text())
    payload, _ = json.JSONDecoder().raw_decode(request['prompt'].split('\n\nINPUT:\n', 1)[1])
    raw = json.loads(Path(request['output_path']).read_text())
    # Only the semantic actor's V3 reply changes in the Phase fixture. Source,
    # current permissions, native load/apply and all consumers stay real.
    expected['v3'] = group._project_current_output(raw, group._obligation_refs(payload))
    contracts = deepcopy(raw['obligation_contracts'])
    for item in contracts.values():
        item['failure_intents'][0]['failure_id'] = 'EXPLICIT_REPAIR_RED'
        item['slice_hint']['planned_new_files'].sort()
    value = {'schema': 'vdd.v3-candidate-repair.v1',
        'requirements_sha256': 'sha256:'+digest(root/'requirements.md'),
        'authorizes': [], 'obligation_contracts': contracts}
    path = root/'logs/plain-repair.json'
    path.write_text(json.dumps(value))
    options = ['--v3-contract-repair', str(path)]
    scope = root/'scope.json'
    if scope.exists():
        options += ['--source-scope', str(scope)]
    return path, value, options


@pytest.mark.parametrize('delivered', [None, 'phase'], indirect=True)
def test_plain_repair_and_reference_use_real_native_consumer(delivered):
    root, _, origin, prepared = delivered
    path, value, options = correction(delivered)
    plan = root/'execution-plans/plan'
    record = plan/'execution-record.md'
    before = record.read_bytes()
    caches = {p: digest(p) for p in (plan/'.compiler-cache').glob('*.json')}
    request = json.loads(origin.read_text())
    witness = [origin, origin.parent/'response.json', origin.parent/'result.json', Path(request['output_path'])]
    hashes = {p: digest(p) for p in witness}
    code, result, seen, stderr, stdout = run_public(delivered, options=options)
    assert code == 0 and result['status'] == 'plan-ready', (result, stderr, stdout)
    bundle = json.loads((plan/'semantic-plan-bundle.v1.json').read_text())
    assert bundle['acceptances'][0]['assertion_ids'] == next(iter(value['obligation_contracts'].values()))['acceptance']['assertion_ids']
    assert any(f['failure_id'] == 'EXPLICIT_REPAIR_RED' for f in bundle['failure_intents'])
    projections = list((plan/'.compiler-work/candidate-repairs').glob('*.json'))
    assert len(projections) == 1
    receipt = json.loads(projections[0].read_text())
    assert receipt['repair'] == value and receipt['authorizes'] == []
    assert receipt['applied_obligation_ids'] == sorted(value['obligation_contracts'])
    assert all(digest(p) == sha for p,sha in caches.items())
    assert all(digest(p) == sha for p,sha in hashes.items())
    after = record.read_bytes()
    assert after.startswith(before)
    producer = lambda raw: [line for line in raw.splitlines() if line.startswith(adapter._RECORD_PREFIX.encode())]
    assert producer(after) == producer(before)
    assert result['planning_observation_reuse']['original_outcome'] == 'degraded'
    assert result['planning_observation_reuse']['episode_closed'] is True
    assert result['planning_observation_reuse']['already_delivered'] is True
    assert seen
    for prompt,payload in seen:
        ref = payload['planning_source_observations']
        assert ref['status'] == 'reference-only'
        assert all(k not in ref for k in ['query_result','read_set','candidates','excerpt'])
        assert json.dumps(prepared, ensure_ascii=False, sort_keys=True) not in prompt


@pytest.mark.parametrize('defect', ['requirements-hash', 'source-change', 'unknown-target', 'source-refs',
                                   'not-returned', 'cross-task', 'permission-revoked'])
def test_plain_combination_keeps_native_identity_and_permission_rejections(delivered, defect):
    root, _, origin, prepared = delivered
    path, value, options = correction(delivered)
    expected = None
    if defect == 'requirements-hash':
        value['requirements_sha256'] = 'sha256:'+'0'*64
        expected = 'requirements identity is stale'
    elif defect == 'source-change':
        source = next(root/r['path'] for r in prepared['query_result']['read_set']
                      if r['path'] != 'requirements.md')
        source.write_bytes(source.read_bytes()+b'\n# Changed source.\n')
        expected = 'PLANNING_OBSERVATION_REUSE_BLOCKED:'
    elif defect == 'unknown-target':
        value['obligation_contracts'] = {'O-UNKNOWN': next(iter(value['obligation_contracts'].values()))}
        expected = 'targets absent from final active domain'
    elif defect == 'source-refs':
        next(iter(value['obligation_contracts'].values()))['acceptance']['source_refs'] = ['requirements.md#FR-UNKNOWN']
        expected = 'source binding mismatch'
    elif defect == 'not-returned':
        p = origin.parent/'result.json'
        result = json.loads(p.read_text())
        result['status'] = 'submitted'
        p.write_text(json.dumps(result))
        expected = 'native_return_binding'
    elif defect == 'cross-task':
        target = root/'execution-plans/other'
        target.mkdir()
        expected = 'different_target'
    else:
        paths = [root/p for p in adapter._CANONICAL]
        _switch_fixture_generation(root, paths, restrict_vdd=True)
        expected = 'current_permission_denied'
    path.write_text(json.dumps(value))
    record = root/'execution-plans/plan/execution-record.md'
    before = record.read_bytes()
    code, result, seen, stderr, stdout = run_public(
        delivered, options=options, out_dir=target if defect == 'cross-task' else None)
    if defect == 'cross-task':
        argv = json.loads((root/'logs/resume/argv.json').read_text())
        assert argv.count('--out-dir') == 1
        assert argv[argv.index('--out-dir') + 1] == str(target)
    assert code in {1,2} and (result is None or result['status'] == 'repair-vdd')
    assert expected in stderr+' '+stdout+' '+json.dumps(result), (result, stderr, stdout)
    assert 'unrecognized arguments' not in stderr
    assert record.read_bytes() == before
    if defect not in {'unknown-target','source-refs'}:
        assert not seen


@pytest.mark.parametrize('delivered', ['phase'], indirect=True)
@pytest.mark.parametrize('defect', ['withdrawn', 'changed'])
def test_plain_combination_requires_same_current_scope(delivered, defect):
    root, _, _, _ = delivered
    _, _, options = correction(delivered)
    if defect == 'withdrawn':
        options = options[:2]
    else:
        p = root/'scope.json'
        value = json.loads(p.read_text())
        value['support_paths'].append('tests/another.py')
        p.write_text(json.dumps(value))
    code, result, seen, stderr, _ = run_public(delivered, options=options)
    assert code == 1 and result['status'] == 'repair-vdd', (result, stderr)
    assert 'current_source_scope_changed' in result['reason'] and not seen


def test_reference_combination_rejects_extended_schema_after_real_native_load(delivered):
    root, _, _, _ = delivered
    path, value, options = correction(delivered)
    cases = []
    for extra in [{'dependency_revision': True},
                  {'source_index_sha256': 'sha256:'+'0'*64,
                   'test_path_replacements': {'tests/old.py':'tests/new.py'}}]:
        path.write_text(json.dumps({**value, **extra}))
        code, result, seen, stderr, _ = run_public(delivered, options=options,
                                                session_name='schema-'+str(len(cases)))
        cases.append({'extra_fields':sorted(extra),'exit':code,'stderr':stderr})
        assert code == 2 and result is None and not seen
        assert 'requires the four-field plain V3 candidate repair' in stderr
    (root/'logs/extended-schema-results.json').write_text(json.dumps(cases, indent=2))


def test_reference_plain_combination_rejects_other_routes_before_consumption(delivered):
    root, _, _, _ = delivered
    path, value, options = correction(delivered)
    (root/'extra.md').write_text('Unselected companion.\n')
    cases = []
    modes = [('--repair-published-v3-from',str(root/'execution-plans/plan')),
             ('--repair-quick-dev-handoff-from',str(root/'execution-plans/plan')),
             ('--companion',str(root/'extra.md')), ('--v3-contract-repair-addendum',str(path)),
             ('--v1-reuse-from-plan',str(root/'execution-plans/plan')),
             ('--worker-cache',str(path)), ('--recommendation-only',), ('--admission-only',)]
    for mode in modes:
        code, result, seen, stderr, _ = run_public(delivered, options=[*options,*mode],
                                                session_name='mode-'+str(len(cases)))
        cases.append({'options':mode,'exit':code,'stderr':stderr})
        assert code == 2 and result is None and not seen
        assert ('requires ordinary native resume without alternate inputs' in stderr
                or 'requires plain V3 candidate repair without alternate inputs' in stderr)
    (root/'logs/alternate-mode-results.json').write_text(json.dumps(cases, indent=2))


def test_plain_repair_without_reference_keeps_default_closed_gate(delivered):
    _, _, options = correction(delivered)
    code, result, seen, _, _ = run_public(delivered, reuse=False, options=options)
    assert code == 1 and result['reason'] == 'PLANNING_QUERY_BLOCKED:budget_exhausted'
    assert not seen


def test_plain_reference_combination_rejects_published_target(delivered):
    root, _, _, _ = delivered
    _, _, options = correction(delivered)
    (root/'execution-plans/plan/compiler-state.v1.json').write_text('{"state":"plan-ready"}')
    code, result, seen, stderr, _ = run_public(delivered, options=options)
    assert code == 2 and result is None and not seen
    assert 'requires a failed or unpublished output directory' in stderr
