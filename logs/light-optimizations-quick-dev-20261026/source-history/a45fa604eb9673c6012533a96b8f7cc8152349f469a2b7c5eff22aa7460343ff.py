"""ADR-0041: public bounded admission, with real owning readers and no execution."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[5]
for directory in (ROOT, ROOT / 'scripts', ROOT / '.agents/skills/vdd-execution-plan/scripts'):
    sys.path.insert(0, str(directory))
from scripts.vdd import compile_plan as cli
import execution_preflight
from scripts.toolchain.knowledge_query import adapter

PLAN = ROOT / 'execution-plans/2026-10-26-toolchain-light-optimizations-q2-boundary'
REQUIREMENTS = ROOT / 'docs/2026-10-26-toolchain-light-optimizations-requirements-v3.md'


def expect(condition, failure_id):
    if not condition:
        print('FAILURE_ID:' + failure_id)
    assert condition, failure_id


def invoke(out, *, source=REQUIREMENTS, profile='standard', extra=()):
    args = ['compile_plan.py', '--requirements', str(source), '--out-dir', str(out),
            '--profile', profile, *extra]
    stdout, stderr = io.StringIO(), io.StringIO()
    advisory = {'status': 'disabled', 'queried': False, 'authorizes': [], 'query_result': {'read_set': []}}
    with mock.patch.object(sys, 'argv', args), mock.patch.object(adapter, 'prepare_consumption', return_value=advisory) as query, mock.patch.object(cli.semantic_compiler, 'invoke_worker') as worker, redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            rc = cli.main()
        except SystemExit as exc:
            rc = exc.code
    lines = stdout.getvalue().splitlines()
    result = json.loads(lines[-1]) if lines else {'status': 'cli-rejected'}
    return rc, result, worker.call_count, query.call_count


def admission(out, **kwargs):
    return invoke(out, extra=['--admission-only', *kwargs.pop('extra', ())], **kwargs)


@pytest.fixture
def local():
    with tempfile.TemporaryDirectory(dir=ROOT / 'logs', prefix='light-admission-') as name:
        yield Path(name)


@pytest.mark.cer_assertion('ASSERT-LIGHT-03FC732FF336')
def test_light_3151dcccab85(local):
    # Existing recommendation is a real public read-only route, not a test stub.
    rc, result, workers, _ = invoke(local / 'out', extra=['--recommendation-only'])
    value = result.get('admission', {})
    expect(rc == 0 and set(value.get('checks', {})) == {'inputs', 'recovery', 'dependencies', 'quick_dev'}
           and value.get('authorizes') == [] and workers == 0, 'LIGHT-03FC732FF336')


@pytest.mark.cer_assertion('ASSERT-LIGHT-D10FAB14076E')
@pytest.mark.parametrize('defect', ['missing', 'corrupt', 'recovery-source', 'recovery-bundle', 'recovery-missing-bundle', 'consumer'])
def test_light_1622025eedfb(local, defect):
    source = REQUIREMENTS
    extra = []
    out = local / 'out'
    if defect in {'missing', 'corrupt'}:
        source = local / 'requirements.md'
        if defect == 'corrupt':
            source.write_bytes(b'\xff')
    if defect.startswith('recovery'):
        shutil.copytree(PLAN, out)
        extra = ['--resume-from', 'first-failed-stage']
        path = out / ('source-index.v1.json' if defect == 'recovery-source' else 'semantic-plan-bundle.v1.json')
        if defect == 'recovery-missing-bundle':
            path.unlink()
        else:
            value = json.loads(path.read_text())
            value['sha256' if defect == 'recovery-source' else 'plan_id'] = 'wrong-current-identity'
            path.write_text(json.dumps(value))
    original_is_file = Path.is_file
    def visible(path):
        if defect == 'consumer' and path == ROOT / 'scripts/quick_dev/run.py':
            return False
        return original_is_file(path)
    with mock.patch.object(Path, 'is_file', visible):
        rc, result, workers, queries = admission(out, source=source, profile='self-hosted' if defect.startswith('recovery') else 'standard', extra=extra)
    expect(rc != 0 and result.get('admission', {}).get('status') == 'blocked' and workers == queries == 0,
           'LIGHT-D10FAB14076E')


@pytest.mark.cer_assertion('ASSERT-LIGHT-D33AF6125B46')
@pytest.mark.parametrize('plan_profile,execution,allowed', [('resumable', 'standard', True), ('standard', 'fast-ship', True), ('self-hosted', 'standard', True), ('standard', 'resumable', False)])
def test_light_51007ee5cc9c(local, plan_profile, execution, allowed):
    rc, result, _, _ = admission(local / 'out', profile=plan_profile, extra=['--execution-profile', execution])
    value = result.get('admission', {})
    expect((rc == 0) == allowed and value.get('plan_profile') == plan_profile
           and value.get('execution_profile') == execution and value.get('status') == ('pending' if allowed else 'blocked'),
           'LIGHT-D33AF6125B46')


@pytest.mark.cer_assertion('ASSERT-LIGHT-EE30987A8DDE')
@pytest.mark.parametrize('kind', ['valid', 'invalid', 'recovery'])
def test_light_964924bbdac1(local, kind):
    source, out, extra = REQUIREMENTS, local / 'out', []
    if kind == 'invalid':
        source = local / 'missing.md'
    if kind == 'recovery':
        shutil.copytree(PLAN, out)
        extra = ['--resume-from', 'first-failed-stage']
    before = {str(p.relative_to(local)): p.read_bytes() for p in local.rglob('*') if p.is_file()}
    with mock.patch.object(cli, 'compile_plan') as compiler:
        rc, result, workers, queries = admission(out, source=source, profile='self-hosted' if kind == 'recovery' else 'standard', extra=extra)
    after = {str(p.relative_to(local)): p.read_bytes() for p in local.rglob('*') if p.is_file()}
    expect('admission' in result and workers == queries == compiler.call_count == 0 and before == after
           and not (local / 'out/compiler-state.v1.json').exists() if kind != 'recovery' else
           'admission' in result and workers == queries == compiler.call_count == 0 and before == after,
           'LIGHT-EE30987A8DDE')


@pytest.mark.cer_assertion('ASSERT-LIGHT-6BE79070B34A')
def test_light_6c636a19f2df(local):
    # Admission composes the existing source owner and leaves later compiler gates owned.
    sc = cli.semantic_compiler
    original = sc.source_preflight
    with mock.patch.object(sc, 'source_preflight', wraps=original) as source_check, mock.patch.object(cli, 'compile_plan', return_value={'status': 'repair-vdd', 'stage': 'V3-execution-preflight'}) as compiler:
        rc, result, workers, _ = invoke(local / 'out')
    expect(source_check.call_count >= 1 and compiler.call_count == 1 and result.get('stage') == 'V3-execution-preflight'
           and rc != 0 and result.get('admission', {}).get('status') == 'pending' and workers == 0,
           'LIGHT-6BE79070B34A')


@pytest.mark.cer_assertion('ASSERT-LIGHT-EB921B27E2BA')
def test_light_c660ed94c51c(local):
    config = ROOT / 'scripts/sc/model_config.py'
    before = config.read_bytes()
    rc, result, workers, queries = admission(local / 'out')
    expect(rc == 0 and result.get('admission', {}).get('authorizes') == [] and workers == queries == 0
           and config.read_bytes() == before, 'LIGHT-EB921B27E2BA')


@pytest.mark.cer_assertion('ASSERT-LIGHT-B96B2954D606')
def test_light_112e17a2606e(local):
    rc, result, _, _ = admission(local / 'out')
    value = result.get('admission', {})
    expect(rc == 0 and value.get('status') == 'pending' and value.get('checks', {}).get('dependencies', {}).get('status') == 'pending'
           and value.get('checks', {}).get('recovery', {}).get('status') == 'not-selected'
           and result.get('status') != 'plan-ready' and not (local / 'out').exists(), 'LIGHT-B96B2954D606')
