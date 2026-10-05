"""ADR-0041: real 08-05 handoff regression and canonical publication checks."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[5]
SCRIPTS = ROOT / '.agents/skills/vdd-execution-plan/scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / '.agents/skills/quick-dev-tdd-adapter/tools'))
import semantic_feasibility_patch  # noqa: F401
import semantic_compiler as sc
from quick_dev_handoff import _regression, handoff_findings, repair_bundle, repair_runtime_red_bindings, semantic_projection
from semantic_chain_audit import audit_bundle
from semantic_plan_contract import validate_semantic_bundle
from current_router import materialize_descriptor, validate_red_author_delta, validate_write_delta
from q1_planned_preflight import validate_planned_preflight
import stable_runner
from stable_runner import _descriptor_inputs

SCOPE = Path('execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/recompilation-4')
PRIOR = SCOPE / 'cer-repair-1/current-plan'
TEST_ROOT = 'scripts/sc/tests/tc_d1_cer'


def original():
    return json.loads((ROOT / PRIOR / 'semantic-plan-bundle.v1.json').read_text(encoding='utf-8'))


def repaired():
    return repair_bundle(original(), TEST_ROOT)[0]


def test_handoff_retains_windows_python_launcher_for_pytest_regression():
    command = ['py', '-3', '-m', 'pytest', 'scripts/sc/tests/tc_d1_cer/test_s4_cer.py', '-q']
    assert _regression(command) == (command, 'retained-regression')
    assert _regression(['python', '-m', 'pytest', 'scripts/sc/tests/tc_d1_cer/test_s4_cer.py', '-q'], windows_launcher=True) == (command, 'retained-regression')
    repaired_bundle = repair_bundle(original(), TEST_ROOT, windows_launcher_slices=['S4'])[0]
    context = next(item for item in repaired_bundle['agent_contexts'] if item['slice_id'] == 'S4')
    assert all(item[:4] == ['py', '-3', '-m', 'pytest'] for item in context['validation_commands'])
    unaffected = next(item for item in repaired_bundle['agent_contexts'] if item['slice_id'] == 'S5')
    original_context = next(item for item in original()['agent_contexts'] if item['slice_id'] == 'S5')
    expected_unaffected = repair_bundle(original(), TEST_ROOT)[0]
    expected_context = next(item for item in expected_unaffected['agent_contexts'] if item['slice_id'] == 'S5')
    assert unaffected['validation_commands'] == expected_context['validation_commands']
    assert original_context['slice_id'] == 'S5'


def test_real_predecessor_exposes_all_three_handoff_defects():
    findings = handoff_findings(original())
    assert any('production-frozen' in x for x in findings)
    assert any('missing-authorable' in x for x in findings)
    assert any(x.startswith('S6:missing-behavior-red-route:') for x in findings)


def test_repair_preserves_requirements_oracles_scope_and_historical_guards():
    old = original()
    new = repaired()
    assert semantic_projection(old) == semantic_projection(new)
    assert len(new['obligations']) == len(new['acceptances']) == 114
    assert len(new['slices']) == 45
    assert all(f in new['failure_intents'] for f in old['failure_intents'])
    assert validate_semantic_bundle(new) == (True, [])
    assert audit_bundle(new)['valid']
    assert handoff_findings(new) == []


def test_only_executable_behavior_gets_a_new_red_role():
    old = original()
    new = repaired()
    prior = {f['failure_intent_id'] for f in old['failure_intents']}
    amap = {a['acceptance_id']: a for a in new['acceptances']}
    omap = {o['obligation_id']: o for o in new['obligations']}
    added = [f for f in new['failure_intents'] if f['failure_intent_id'] not in prior]
    assert len(added) == 16
    for failure in added:
        assert failure['failure_family'] == 'expected-red'
        for aid in failure['acceptance_ids']:
            for oid in amap[aid]['obligation_ids']:
                assert omap[oid]['obligation_kind'] in {'behavior', 'quality'}
                assert omap[oid]['requirement_type'] != 'Governance'
    s1 = new['slices'][0]
    assert not [f for f in added if set(f['acceptance_ids']) & set(s1['acceptance_ids'])]


def test_runtime_red_repair_reports_conflicting_existing_test_binding(tmp_path):
    bundle = original()
    runtime_intent = next(item['failure_intent_id'] for item in bundle['failure_intents']
                          if item['failure_family'] != 'expected-red'
                          and len(item['acceptance_ids']) == 1)
    test = ROOT / 'scripts/sc/tests/tc_d1_cer/test_s4.py'
    previous = test.read_text(encoding='utf-8') if test.exists() else None
    try:
        test.parent.mkdir(parents=True, exist_ok=True)
        test.write_text('@pytest.mark.cer_assertion("other-slice")\ndef test_marker(): pass\n', encoding='utf-8')
        repaired, delta = repair_runtime_red_bindings(bundle, TEST_ROOT, ROOT, [runtime_intent])
        s4 = next(item for item in repaired['slices'] if item['slice_id'] == 'S4')
        assert any(path.startswith(f'{TEST_ROOT}/test_s4_cer')
                   for path in s4['execution_snapshot_paths'])
        assert not any('existing-test-assertion-mismatch' in item
                       for item in handoff_findings(repaired, workspace=ROOT))
        assert len(delta['runtime_red_role_bindings']) == 1
        original_ids = {item['failure_intent_id'] for item in bundle['failure_intents']}
        assert len([item for item in repaired['failure_intents'] if item['failure_intent_id'] not in original_ids]) == 1
    finally:
        if previous is None:
            test.unlink(missing_ok=True)
        else:
            test.write_text(previous, encoding='utf-8')


@pytest.mark.parametrize('sid', [f'S{i}' for i in range(1, 46)])
def test_each_real_slice_has_authorable_test_and_unfrozen_production(tmp_path, sid, monkeypatch):
    monkeypatch.setattr(stable_runner, "ROOT", tmp_path)
    bundle = repaired()
    item = next(s for s in bundle['slices'] if s['slice_id'] == sid)
    context = next(c for c in bundle['agent_contexts'] if c['slice_id'] == sid)
    path = tmp_path / 'agent-context' / sid / 'agent-context.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(context), encoding='utf-8')
    command, targets, fixtures = _descriptor_inputs(bundle, tmp_path, sid)
    assert f'{TEST_ROOT}/test_{sid.lower()}.py' in targets
    assert all(target in item['execution_snapshot_paths'] for target in targets)
    validate_red_author_delta(targets, item['execution_snapshot_paths'] + item['planned_new_files'], item['production_owners'])
    validate_write_delta(item['production_owners'], item['allowed_write_paths'], item['execution_snapshot_paths'])
    validate_planned_preflight(workspace=ROOT, bundle=bundle, slice_id=sid, timeout_seconds=600)
    descriptor = materialize_descriptor(bundle=bundle, slice_id=sid, stage='probe', run_id='handoff-fixture',
        candidate_hash='sha256:' + '1' * 64, argv=command, cwd='.', timeout_seconds=60,
        target_refs=targets, fixture_refs=fixtures)
    assert {a['assertion_id'] for a in descriptor['acceptance_assertions']} == set(item['proof']['assertion_ids'])
    assert all(a['target_ref'] in targets for a in descriptor['acceptance_assertions'])


@pytest.mark.parametrize('mutation,expected', [
    ('freeze', 'production-frozen'), ('selector', 'missing-authorable'), ('forbidden', 'test-entry-forbidden')])
def test_gate_rejects_reintroduced_defects(mutation, expected):
    bundle = repaired()
    item, context = bundle['slices'][0], bundle['agent_contexts'][0]
    if mutation == 'freeze':
        item['execution_snapshot_paths'].append(item['production_owners'][0])
    elif mutation == 'selector':
        context['validation_commands'][0] = ['python', item['production_owners'][0], '--help']
    else:
        context['forbidden_paths'].append(TEST_ROOT)
    assert any(expected in x for x in handoff_findings(bundle))


@pytest.fixture
def cli_root(tmp_path):
    root = tmp_path / 'repo'
    for directory in ['.agents/skills/vdd-execution-plan/scripts', 'scripts/vdd']:
        shutil.copytree(ROOT / directory, root / directory, ignore=shutil.ignore_patterns('__pycache__', 'tests'))
    files = ['AGENTS.md', str(SCOPE / 'assembled-requirements.md')]
    files += [str(PRIOR / name) for name in ['source-index.v1.json', 'compiler-state.v1.json',
        'semantic-plan-bundle.v1.json', 'semantic-alignment.v1.json', 'atomic-recall-alignment.v1.json']]
    for item in original()['slices']:
        files += item['production_owners'] + item['execution_snapshot_paths']
    for name in set(files):
        src, dst = ROOT / name, root / name
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    return root


def invoke(root):
    out = PRIOR.parent / 'test-successor/current-plan'
    result = subprocess.run([sys.executable, 'scripts/vdd/compile_plan.py', '--requirements',
        str(SCOPE / 'assembled-requirements.md'), '--out-dir', str(out),
        '--profile', 'self-hosted', '--repair-quick-dev-handoff-from', str(PRIOR)],
        cwd=root, capture_output=True, encoding='utf-8', timeout=30)
    return result, root / out


def test_public_cli_publishes_checked_successor_without_worker(cli_root):
    result, out = invoke(cli_root)
    assert result.returncode == 0, result.stdout + result.stderr
    state = json.loads((out / 'compiler-state.v1.json').read_text())
    bundle = json.loads((out / 'semantic-plan-bundle.v1.json').read_text(encoding='utf-8'))
    assert state['state'] == 'plan-ready'
    assert state['semantic_plan_sha256'] == sc.sha256_value(bundle)
    report = json.loads((out / 'handoff-repair.v1.json').read_text())
    assert report['authorizes'] == [] and report['model_called'] is False
    # Source rebinding is conditional: a byte-identical predecessor has no
    # rebindings, while a text-equivalent source relocation records them.
    assert isinstance(report['source_byte_rebindings'], list)
    assert semantic_projection(original()) == semantic_projection(bundle)
    assert not (cli_root / TEST_ROOT).exists()  # Plan authoring is not test execution.


@pytest.mark.parametrize('fault', ['source-drift', 'state-hash', 'review'])
def test_cli_refuses_drift_or_missing_review_without_publishing(cli_root, fault):
    if fault == 'source-drift':
        path = cli_root / SCOPE / 'assembled-requirements.md'
        path.write_text(path.read_text(encoding='utf-8') + '\nUnreviewed requirement change.\n', encoding='utf-8')
    else:
        name = 'compiler-state.v1.json' if fault == 'state-hash' else 'semantic-alignment.v1.json'
        path = cli_root / PRIOR / name
        value = json.loads(path.read_text(encoding='utf-8'))
        if fault == 'state-hash':
            value['semantic_plan_sha256'] = 'sha256:' + '0' * 64
        else:
            value['valid'] = False
        path.write_text(json.dumps(value), encoding='utf-8')
    result, out = invoke(cli_root)
    assert result.returncode == 1
    assert json.loads(result.stdout)['status'] == 'repair-vdd'
    assert not (out / 'compiler-state.v1.json').exists()
