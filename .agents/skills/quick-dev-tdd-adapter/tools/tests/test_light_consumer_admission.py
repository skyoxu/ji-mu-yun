"""ADR-0041: the real readonly consumers must inspect their actual inputs."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[5]
TOOLS = ROOT / '.agents/skills/quick-dev-tdd-adapter/tools'
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT))
import stable_runner as runner
import q1_planned_preflight as planned
import current_router
from behavior_routing import production_hashes, validate_plan
from case_selection import literal_nodes

PLAN = ROOT / 'execution-plans/2026-10-26-toolchain-light-optimizations-ready'


def expect(condition, failure_id):
    if not condition:
        print('FAILURE_ID:' + failure_id)
    assert condition, failure_id


def fixture(tmp_path):
    bundle = json.loads((PLAN / 'semantic-plan-bundle.v1.json').read_text())
    for item in bundle['slices']:
        for ref in item['production_owners']:
            path = tmp_path / ref
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# candidate identity fixture\n', encoding='utf-8')
        ref = item['execution_snapshot_paths'][0]
        path = tmp_path / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        assertions = [v for a in bundle['acceptances'] if a['acceptance_id'] in item['acceptance_ids'] for v in a['assertion_ids']]
        text = "raise RuntimeError('admission must never import this test')\nimport pytest\n"
        for n, assertion in enumerate(assertions):
            text += f"@pytest.mark.cer_assertion({assertion!r})\ndef test_case_{n}(): pass\n"
        path.write_text(text, encoding='utf-8')
    plan = tmp_path / 'plan'
    save(plan, bundle)
    return plan, bundle


def save(plan, bundle):
    plan.mkdir(parents=True, exist_ok=True)
    (plan / 'semantic-plan-bundle.v1.json').write_text(json.dumps(bundle), encoding='utf-8')
    for context in bundle['agent_contexts']:
        path = plan / 'agent-context' / context['slice_id'] / 'agent-context.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(context), encoding='utf-8')


def admit(workspace, plan):
    with mock.patch.object(runner, 'ROOT', workspace), mock.patch.object(current_router, 'environment_probe', return_value={'available': True}):
        try:
            return runner.q1_preflight(semantic=plan / 'semantic-plan-bundle.v1.json', slice_id='S4', profile='standard')
        except (ValueError, OSError) as exc:
            return {'status': 'blocked', 'reason': str(exc)}


@pytest.mark.cer_assertion('ASSERT-LIGHT-77EEE6DD9C66')
@pytest.mark.parametrize('kind', ['matching', 'missing', 'command', 'selector', 'acceptance', 'ambiguous'])
def test_light_2186eab31aa1(tmp_path, kind):
    plan, bundle = fixture(tmp_path)
    path = plan / 'agent-context/S4/agent-context.json'
    disk = json.loads(path.read_text())
    if kind == 'missing':
        path.unlink()
    elif kind in {'command', 'selector', 'acceptance'}:
        key = {'command': 'validation_commands', 'selector': 'selector_intents', 'acceptance': 'acceptance_ids'}[kind]
        disk[key] = [['python', '-c', 'pass']] if kind == 'command' else ['DRIFT']
        path.write_text(json.dumps(disk), encoding='utf-8')
    elif kind == 'ambiguous':
        bundle['agent_contexts'].append(deepcopy(disk))
        (plan / 'semantic-plan-bundle.v1.json').write_text(json.dumps(bundle), encoding='utf-8')
    result = admit(tmp_path, plan)
    expect((result['status'] == 'preflight-passed') == (kind == 'matching'), 'LIGHT-77EEE6DD9C66')


@pytest.mark.cer_assertion('ASSERT-LIGHT-BB99F694D6BB')
@pytest.mark.parametrize('kind', ['valid', 'shell-command', 'unbound-target', 'nul-selector'])
def test_light_b01c33d730ee(tmp_path, kind):
    plan, bundle = fixture(tmp_path)
    context = next(c for c in bundle['agent_contexts'] if c['slice_id'] == 'S4')
    target = next(s for s in bundle['slices'] if s['slice_id'] == 'S4')['execution_snapshot_paths'][0]
    argv = ['python', '-B', '-m', 'pytest', target, '-q']
    if kind == 'shell-command': argv = ['python -m pytest ' + target]
    if kind == 'unbound-target': argv[4] = 'tests/unbound.py'
    if kind == 'nul-selector': argv[4] += '::test_\x00invalid'
    context['validation_commands'][0] = argv
    save(plan, bundle)
    result = admit(tmp_path, plan)
    expect((result['status'] == 'preflight-passed') == (kind == 'valid'), 'LIGHT-BB99F694D6BB')


@pytest.mark.cer_assertion('ASSERT-LIGHT-D9E930D6957F')
def test_light_8888741bb36f(tmp_path):
    plan, bundle = fixture(tmp_path)
    selected = next(s for s in bundle['slices'] if s['slice_id'] == 'S4')
    target = tmp_path / selected['execution_snapshot_paths'][0]
    target.unlink()
    result = admit(tmp_path, plan)
    expect(result['status'] == 'preflight-passed' and not target.exists(), 'LIGHT-D9E930D6957F')
    expect(not list(plan.glob('**/stage-result*.json')), 'LIGHT-D9E930D6957F')


@pytest.mark.cer_assertion('ASSERT-LIGHT-D7B4E29286C5')
def test_light_e16830860490(tmp_path):
    plan, bundle = fixture(tmp_path)
    selected = next(s for s in bundle['slices'] if s['slice_id'] == 'S4')
    target = selected['execution_snapshot_paths'][0]
    (tmp_path / target).write_text("raise RuntimeError('no import')\nimport pytest\n@pytest.mark.cer_assertion(dynamic)\ndef test_dynamic(): pass\n", encoding='utf-8')
    with mock.patch.object(runner, 'ROOT', tmp_path):
        selected_argv, _, _ = runner._descriptor_inputs(bundle, plan, 'S4')
    nodes, reason = literal_nodes(tmp_path, [target], {'ANY'})
    expect(nodes is None and reason == 'dynamic-marker' and target in selected_argv, 'LIGHT-D7B4E29286C5')


@pytest.mark.cer_assertion('ASSERT-LIGHT-CCCC9778C3EC')
def test_light_33f5fd4e59ad(tmp_path):
    plan, bundle = fixture(tmp_path)
    valid = admit(tmp_path, plan)
    acceptance = next(a for a in bundle['acceptances'] if a['obligation_ids'] == ['O-0F5BEB365D58'])
    acceptance['red_intent_ids'] = []
    save(plan, bundle)
    rejected = admit(tmp_path, plan)
    expect(valid['status'] == 'preflight-passed' and rejected['status'] != 'preflight-passed', 'LIGHT-CCCC9778C3EC')


@pytest.mark.cer_assertion('ASSERT-LIGHT-104D8E0F76C4')
def test_light_d07a4a77480c(tmp_path):
    plan, bundle = fixture(tmp_path)
    validate_plan(bundle)
    before = production_hashes(tmp_path, bundle, 'S3')
    dependency = tmp_path / '.agents/skills/quick-dev-tdd-adapter/tools/q1_planned_preflight.py'
    dependency.write_text('# changed transitive production dependency\n', encoding='utf-8')
    after = production_hashes(tmp_path, bundle, 'S3')
    changed = deepcopy(bundle)
    next(s for s in changed['slices'] if s['slice_id'] == 'S3')['depends_on'] = []
    frozen = deepcopy(changed)
    save(plan, changed)
    rejected = admit(tmp_path, plan)['status'] != 'preflight-passed'
    expect(before != after and rejected and changed == frozen, 'LIGHT-104D8E0F76C4')


@pytest.mark.cer_assertion('ASSERT-LIGHT-C35D920B20D8')
def test_light_3a295774a883():
    from scripts.vdd import compile_plan as cli
    import semantic_v3_contract_repair as repair
    from execution_preflight import inspect_candidate
    bundle = json.loads((PLAN / 'semantic-plan-bundle.v1.json').read_text())
    raw = repair.project_published_v3(bundle)
    with mock.patch.object(planned, 'validate_planned_preflight', wraps=planned.validate_planned_preflight) as owning:
        vdd = inspect_candidate(cli.semantic_compiler, ROOT, bundle['obligations'], bundle['acceptances'], bundle['failure_intents'], raw['slice_hints'], profile='self-hosted')
        vdd_calls = owning.call_count
        quick = runner.q1_preflight(semantic=PLAN / 'semantic-plan-bundle.v1.json', slice_id='S4', profile='standard')
        quick_calls = owning.call_count - vdd_calls
    expect(vdd['valid'] and quick['status'] == 'preflight-passed' and vdd_calls > 0 and quick_calls > 0, 'LIGHT-C35D920B20D8')
