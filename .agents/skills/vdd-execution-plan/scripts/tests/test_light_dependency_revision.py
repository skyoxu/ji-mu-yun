"""ADR-0041: bounded source-stable dependency revision, never execution authority."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[5]
for path in (ROOT, ROOT / 'scripts', ROOT / '.agents/skills/vdd-execution-plan/scripts'):
    sys.path.insert(0, str(path))
from scripts.vdd import compile_plan as cli
import execution_contract as graph
import semantic_compiler as sc
import semantic_v3_contract_repair as repair
from quick_dev_handoff import repair_runtime_red_roles, semantic_projection
from scripts.toolchain.knowledge_query import adapter

PLAN = ROOT / 'execution-plans/2026-10-26-toolchain-light-optimizations-q2-boundary'
REQ = ROOT / 'docs/2026-10-26-toolchain-light-optimizations-requirements-v3.md'


def expect(value, fid):
    if not value:
        print('FAILURE_ID:' + fid)
    assert value, fid


def manifest(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}


@pytest.fixture
def setup_revision():
    with tempfile.TemporaryDirectory(dir=ROOT / 'logs', prefix='light-revision-') as name:
        root = Path(name)
        prior = root / 'predecessor'
        shutil.copytree(PLAN, prior)
        bundle = json.loads((prior / 'semantic-plan-bundle.v1.json').read_text())
        # Within FR-3, validating fresh gates depends on the exact input binding.
        # This is a controlled compiler fixture, not a revision of our running plan.
        oid = next(o['obligation_id'] for o in bundle['obligations'] if o['subject'] == 'Fresh semantic dependency gates')
        dep = next(o['obligation_id'] for o in bundle['obligations'] if o['subject'] == 'Explicit dependency revision input binding')
        source = json.loads((prior / 'source-index.v1.json').read_text())
        raw = repair.project_published_v3(bundle)
        contracts = {}
        for field, key in [('acceptances', 'acceptance'), ('failure_intents', 'failure_intents'), ('slice_hints', 'slice_hint')]:
            entries = [x for x in raw[field] if x['obligation_ids'] == [oid]]
            if key == 'failure_intents':
                contracts[key] = [{k: v for k, v in x.items() if k != 'obligation_ids'} for x in entries]
            else:
                contracts[key] = {k: v for k, v in entries[0].items() if k != 'obligation_ids'}
        value = {'schema': 'vdd.v3-candidate-repair.v1',
                 'requirements_sha256': 'sha256:' + hashlib.sha256(REQ.read_bytes()).hexdigest(),
                 'authorizes': [], 'obligation_contracts': {oid: contracts},
                 'dependency_revision': {'predecessor_sha256': sc.sha256_value(bundle),
                     'source_index_sha256': source['sha256'],
                     'changes': [{'obligation_id': oid, 'old_depends_on': [], 'new_depends_on': [dep]}]}}
        yield root, prior, bundle, value


def public(fixture, *, value=None, successor=None, valid_v4=True):
    root, prior, bundle, original = fixture
    value = deepcopy(original if value is None else value)
    correction = root / 'correction.json'
    correction.write_text(json.dumps(value))
    successor = root / 'successor' if successor is None else successor
    argv = ['compile_plan.py', '--requirements', str(REQ), '--out-dir', str(successor),
            '--profile', 'self-hosted', '--repair-published-v3-from', str(prior),
            '--v3-contract-repair', str(correction)]
    calls = []
    def model(**kwargs):
        stage, data = kwargs['stage'], kwargs['payload']
        calls.append(stage)
        while isinstance(data.get('input'), dict):
            data = data['input']
        if 'source-gap' in stage:
            return {'source_gap_claims': []}
        ids = [o['obligation_id'] for o in data.get('obligations', []) if o.get('status') == 'active']
        if 'atomic-recall' in stage:
            return {'supported_obligation_ids': ids, 'invented_obligation_ids': [], 'source_gap_claims': []}
        if stage.startswith('v4'):
            return {'covered_obligation_ids': ids if valid_v4 else [],
                    'missing_obligation_ids': [] if valid_v4 else ids,
                    'invented_obligation_ids': [], 'misaligned_acceptance_ids': [],
                    'oracle_alignment': {a['acceptance_id']: 'aligned' for a in data.get('acceptances', [])}, 'repairs': []}
        raise AssertionError('Unchanged generation unexpectedly invoked: ' + stage)
    out, err = io.StringIO(), io.StringIO()
    advisory = {'status': 'disabled', 'queried': False, 'authorizes': [], 'query_result': {'read_set': []}}
    with ExitStack() as stack:
        for obj, attr in ((sc, 'compile_obligations'), (sc, 'partition_slices'), (sc, 'semantic_align'),
                          (sc, '_v1_reuse_predecessor_plan'), (repair.group.gate, '_resolved_atomic_recall_worker')):
            stack.enter_context(mock.patch.object(obj, attr, getattr(obj, attr)))
        stack.enter_context(mock.patch.object(sc, 'invoke_worker', side_effect=model))
        stack.enter_context(mock.patch.object(adapter, 'prepare_consumption', return_value=advisory))
        stack.enter_context(mock.patch.object(sys, 'argv', argv))
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = cli.main()
            except SystemExit as exc:
                rc = exc.code
    lines = out.getvalue().splitlines()
    result = json.loads(lines[-1]) if lines else {'reason': err.getvalue(), 'status': 'cli-rejected'}
    return rc, result, calls, successor


@pytest.mark.cer_assertion('ASSERT-LIGHT-6F1AEDA1DBC8')
@pytest.mark.parametrize('drift', ['none', 'predecessor', 'source', 'old-edges'])
def test_light_e8c955695910(setup_revision, drift):
    root, prior, bundle, value = setup_revision
    path = root / 'input.json'
    if drift == 'predecessor':
        value['dependency_revision']['predecessor_sha256'] = 'sha256:' + '0' * 64
    if drift == 'source':
        value['dependency_revision']['source_index_sha256'] = 'sha256:' + '0' * 64
    if drift == 'old-edges':
        value['dependency_revision']['changes'][0]['old_depends_on'] = ['O-NOT-OLD']
    path.write_text(json.dumps(value))
    accepted = False
    try:
        loaded = repair.load_repair(path, REQ)
        prepare = getattr(repair, 'prepare_dependency_revision', None)
        if prepare:
            prepare(loaded, {'bundle': bundle, 'source_index': json.loads((prior / 'source-index.v1.json').read_text())})
            accepted = True
    except ValueError:
        pass
    expect(accepted == (drift == 'none'), 'LIGHT-6F1AEDA1DBC8')


def graphs():
    old = [{'obligation_id': 'O-A', 'depends_on': []}, {'obligation_id': 'O-B', 'depends_on': ['O-A']},
           {'obligation_id': 'O-C', 'depends_on': ['O-B']}, {'obligation_id': 'O-D', 'depends_on': []}]
    slices = [{'slice_id': name, 'obligation_ids': ['O-' + name]} for name in 'ABCD']
    new = deepcopy(old)
    new[1]['depends_on'] = []
    return old, new, slices


@pytest.mark.cer_assertion('ASSERT-LIGHT-8B877C540FC4')
@pytest.mark.parametrize('side', ['old', 'new'])
@pytest.mark.parametrize('defect', ['unknown', 'duplicate', 'dangling', 'cycle'])
def test_light_c88bf08ef42b(side, defect):
    old, new, slices = graphs()
    target = old if side == 'old' else new
    if defect == 'unknown':
        target[0]['depends_on'] = ['FR-UNKNOWN']
    if defect == 'duplicate':
        target[2]['depends_on'] = ['O-B', 'O-B']
    if defect == 'dangling':
        target[0]['depends_on'] = ['O-ABSENT']
    if defect == 'cycle':
        target[0]['depends_on'] = ['O-C']; target[1]['depends_on'] = ['O-A']
    function = getattr(graph, 'dependency_revision_impact', None)
    rejected = False
    if function:
        try:
            function(old, new, slices)
        except ValueError:
            rejected = True
    expect(rejected, 'LIGHT-8B877C540FC4')


@pytest.mark.cer_assertion('ASSERT-LIGHT-2768B5FD436D')
@pytest.mark.parametrize('operation', ['remove', 'add'])
def test_light_b0f66ffcfc79(operation):
    old, new, slices = graphs()
    if operation == 'add':
        old, new = new, old
    function = getattr(graph, 'dependency_revision_impact', None)
    result = function(old, new, slices) if function else {}
    expect(result.get('affected_slices') == ['B', 'C'] and result.get('changed_obligation_ids') == ['O-B'], 'LIGHT-2768B5FD436D')


@pytest.mark.cer_assertion('ASSERT-LIGHT-0CC55D3C196E')
@pytest.mark.parametrize('field', ['requirements', 'oracle', 'owners', 'writes', 'selector', 'terminal', 'failure'])
def test_light_7f086cf4da00(setup_revision, field):
    root, prior, bundle, value = setup_revision
    before = manifest(prior)
    contract = next(iter(value['obligation_contracts'].values()))
    if field == 'requirements':
        value['requirements_sha256'] = 'sha256:' + '0' * 64
    elif field == 'oracle':
        contract['acceptance']['then'] = 'unapproved'
    elif field in {'owners', 'writes'}:
        contract['slice_hint']['production_owners' if field == 'owners' else 'allowed_write_paths'] = ['scripts/sc/_llm_backend.py']
    elif field == 'selector':
        contract['slice_hint']['validation_commands'] = [['python', '-m', 'pytest', 'unapproved.py']]
    elif field == 'terminal':
        contract['slice_hint']['terminal_predicate'] = 'unapproved'
    else:
        contract['failure_intents'][0]['failure_id'] = 'UNAPPROVED'
    rc, result, _, out = public(setup_revision)
    expect(rc != 0 and result.get('status') != 'plan-ready' and not (out / 'compiler-state.v1.json').exists()
           and before == manifest(prior), 'LIGHT-0CC55D3C196E')


@pytest.mark.cer_assertion('ASSERT-LIGHT-1268DA5EAF2C')
@pytest.mark.parametrize('valid', [True, False])
def test_light_008838d2f51b(setup_revision, valid):
    rc, result, calls, _ = public(setup_revision, valid_v4=valid)
    expect(any(s.startswith('v4') for s in calls) and ((rc == 0 and result.get('status') == 'plan-ready') == valid),
           'LIGHT-1268DA5EAF2C')


@pytest.mark.cer_assertion('ASSERT-LIGHT-18D1FC191242')
@pytest.mark.parametrize('output', ['valid', 'same', 'nonempty', 'outside'])
def test_light_cbed8d28dd7b(setup_revision, output):
    root, prior, bundle, value = setup_revision
    before = manifest(prior)
    out = root / 'successor'
    if output == 'same': out = prior
    if output == 'nonempty':
        out.mkdir(); (out / 'preserve').write_text('preserve')
    if output == 'outside': out = root / 'nested/successor'
    rc, result, _, _ = public(setup_revision, successor=out)
    expect(before == manifest(prior) and ((rc == 0 and result.get('status') == 'plan-ready') == (output == 'valid')),
           'LIGHT-18D1FC191242')


@pytest.mark.cer_assertion('ASSERT-LIGHT-F6C303667A95')
def test_light_eb373fbd3f25(setup_revision):
    _, _, bundle, _ = setup_revision
    prior = deepcopy(bundle)
    intent = next(f for f in prior['failure_intents'] if f['failure_family'] == 'expected-red')
    intent['failure_family'] = 'artifact-integrity'
    changed, report = repair_runtime_red_roles(prior, [intent['failure_intent_id']])
    expect(semantic_projection(changed) == semantic_projection(prior)
           and all(f in changed['failure_intents'] for f in prior['failure_intents'])
           and len(changed['failure_intents']) == len(prior['failure_intents']) + 1,
           'LIGHT-F6C303667A95')


@pytest.mark.cer_assertion('ASSERT-LIGHT-52B78C7AFF3E')
def test_light_c20a9174d21a(setup_revision):
    root, prior, _, _ = setup_revision
    historical = prior / 'historical-execution.json'
    historical.write_text('{"historical":true}')
    before = manifest(prior)
    rc, result, calls, out = public(setup_revision)
    expect(rc == 0 and result.get('status') == 'plan-ready' and calls and all(s.startswith('v4') for s in calls)
           and before == manifest(prior) and not (out / historical.name).exists(), 'LIGHT-52B78C7AFF3E')


@pytest.mark.cer_assertion('ASSERT-LIGHT-CA6D769917C2')
def test_light_9b9f1488f81b(setup_revision):
    root, prior, _, value = setup_revision
    value['unapproved_semantic_authority'] = True
    before = manifest(prior)
    rc, result, calls, out = public(setup_revision)
    expect(rc != 0 and 'fields are invalid' in result.get('reason', '') and before == manifest(prior)
           and not (out / 'compiler-state.v1.json').exists(), 'LIGHT-CA6D769917C2')
