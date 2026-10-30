"""ADR-0041: regression admission integrity and fixture-only candidate execution."""
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import skill_baseline as baseline


@pytest.mark.parametrize('required_case_passes', [True, False])
def test_actual_ci_admission_sequence_runs_complete_candidate_and_stops_on_failure(tmp_path, required_case_passes):
    """ADR-0041: replay the checked-in CI commands through the real small runner."""
    workflow = (ROOT / '.github/workflows/ch456-capability.yml').read_text(encoding='utf-8')
    lines = workflow.splitlines()
    commands = []
    for index, line in enumerate(lines):
        if line.strip().startswith('py -3 -B scripts/skill_baseline.py '):
            assert lines[index + 1].strip() == 'if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }'
            commands.append(shlex.split(line.strip())[4:])
    assert [command[0] for command in commands] == ['candidate', 'test', 'admit', 'check']
    assert '--bootstrap' in commands[1] and '--defer-admission' in commands[1]
    assert not any('--diagnostic-target' in command for command in commands)
    assert all('--skill' not in command or command[command.index('--skill') + 1] == 'all'
               for command in commands)
    root = small_root(tmp_path / 'ci-repository')
    if not required_case_passes:
        target = root / 'tests/test_feature.py'
        target.write_text(target.read_text().replace('assert 2 + 2 == 4', 'assert 2 + 2 == 5'), encoding='utf-8')
    executed = []
    for command in commands:
        result = invoke(root, *command)
        executed.append((command[0], result.returncode))
        if result.returncode:
            break
    pointer = root / baseline.STORE / 'current.json'
    if required_case_passes:
        assert executed == [('candidate', 0), ('test', 0), ('admit', 0), ('check', 0)]
        assert pointer.is_file()
        for entry in ['scripts/vdd/compile_plan.py', 'scripts/quick_dev/run.py']:
            allowed = subprocess.run([sys.executable, '-B', str(root / entry), '--help'],
                                     cwd=root, capture_output=True, text=True, timeout=30)
            assert allowed.returncode == 0, allowed.stdout + allowed.stderr
            assert 'fixture-entry-admitted' in allowed.stdout
    else:
        assert executed == [('candidate', 0), ('test', 1)]
        assert not pointer.exists()
        assert not (root / 'execution-plans/formal-task').exists()


def test_complete_history_registry_has_no_missing_commit_or_unbound_current_witness():
    registry = json.loads((ROOT / '.agents/skill-baselines/capability-coverage.v1.json').read_text())
    ref = registry['historical_ledger']
    ledger_bytes = (ROOT / ref['path']).read_bytes()
    assert baseline.digest(ledger_bytes) == ref['sha256']
    ledger = json.loads(ledger_bytes)
    actual = subprocess.check_output(['git', 'rev-list', registry['scope']['range']], cwd=ROOT, text=True)
    rows = ledger['commits']
    assert len({row['commit'] for row in rows}) == len(rows)
    assert {row['commit'] for row in rows} == set(actual.splitlines())
    assert not any('pending' in row['classification'] for row in rows)
    families = registry['capabilities']
    ids = {family['id'] for family in families}
    assert len(ids) == len(families)
    shared = ['policy.v1.json', 'bootstrap-history.v1.json',
              'package-b-current-coverage.v1.json', 'capability-coverage.v1.json']
    for name in shared:
        result = subprocess.run(['git', 'check-ignore', '--no-index', '.agents/skill-baselines/' + name],
                                cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 1, name
    for private in ['admissions/current.json', 'device.user.toml', 'scratch/private.json']:
        result = subprocess.run(['git', 'check-ignore', '--no-index', '.agents/skill-baselines/' + private],
                                cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, private
    policies = json.loads((ROOT / baseline.POLICY).read_text())['skills']
    inventories = {}
    for row in rows:
        assert set(row.get('capabilities', [])).issubset(ids)
        if row['classification'] == 'capability-owner-and-contract-mapped':
            assert row['file_dispositions'] and row['capabilities']
    for family in families:
        assert family['intent'] and family['replacement_basis'] and family['tests']
        skills = ['vdd', 'quick-dev'] if family['skill'] == 'both' else [family['skill']]
        for item in family['implementation']:
            path = item['path'] if isinstance(item, dict) else item.split(':', 1)[0]
            assert (ROOT / path).is_file(), path
            if isinstance(item, dict) and item.get('sha256'):
                assert baseline.digest((ROOT / path).read_bytes()) == item['sha256'], path
        for node in family['tests']:
            source = node.split('::', 1)[0]
            if source not in inventories:
                inventories[source] = baseline.test_inventory(ROOT, [source])
            assert node in inventories[source], node
            assert any(any(node == target or node.startswith(target + '::')
                           for target in policies[skill]['suites']) for skill in skills), node


def put(root, name, content):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding='utf-8')
    return p


def small_root(root):
    for name, folder in baseline.SKILLS.items():
        put(root, folder + '/SKILL.md', '# ' + name + '\n')
    runner = root / 'scripts/skill_baseline.py'
    runner.parent.mkdir(parents=True)
    runner.write_bytes((ROOT / 'scripts/skill_baseline.py').read_bytes())
    (root / 'scripts/workflow_unit_budget.py').write_bytes((ROOT / 'scripts/workflow_unit_budget.py').read_bytes())
    collector = root / baseline.SKILLS['quick-dev'] / 'tools/pytest_case_collector.py'
    collector.parent.mkdir(parents=True)
    collector.write_bytes((ROOT / baseline.SKILLS['quick-dev'] / 'tools/pytest_case_collector.py').read_bytes())
    for name, entry in [('vdd', 'scripts/vdd/compile_plan.py'), ('quick-dev', 'scripts/quick_dev/run.py')]:
        put(root, entry, "from pathlib import Path\nimport sys\n"
            "root=Path(__file__).resolve().parents[2]\nsys.path.insert(0,str(root/'scripts'))\n"
            "from skill_baseline import require_admission\n"
            f"require_admission(root,{name!r},sys.argv[1:])\nprint('fixture-entry-admitted')\n")
    put(root, 'shared.py', 'VALUE = 1\n')
    put(root, 'tests/test_feature.py', r'''import os
from pathlib import Path
import subprocess
import sys

def test_required_case():
    assert 2 + 2 == 4

def test_guarded_candidate_fixture_and_formal_task_denial():
    root = Path.cwd()
    scratch = Path(os.environ['TMPDIR'])
    source = scratch / 'input.md'
    source.write_text('# FR-1\nFixture behavior\n', encoding='utf-8')
    entry = root / 'scripts/vdd/compile_plan.py'
    okay = subprocess.run([sys.executable, '-B', str(entry), '--requirements', str(source),
        '--out-dir', str(scratch / 'native-out')], capture_output=True, text=True, shell=False)
    assert okay.returncode == 0, okay.stdout + okay.stderr
    assert 'fixture-entry-admitted' in okay.stdout
    copied = scratch / 'isolated-repo/scripts/vdd/compile_plan.py'
    copied.parent.mkdir(parents=True)
    copied.write_bytes(entry.read_bytes())
    result = subprocess.run([sys.executable, '-B', str(copied), '--requirements', str(source),
        '--out-dir', str(scratch / 'isolated-repo/plan')], capture_output=True, text=True, shell=False)
    assert result.returncode == 0, result.stdout + result.stderr
    copied.write_text(copied.read_text() + '\n# tampered entry bytes\n')
    changed = subprocess.run([sys.executable, '-B', str(copied), '--requirements', str(source),
        '--out-dir', str(scratch / 'isolated-repo/plan')], capture_output=True, text=True, shell=False)
    assert changed.returncode != 0
    denied = subprocess.run([sys.executable, '-B', str(entry), '--requirements', str(source),
        '--out-dir', 'execution-plans/formal-task'], capture_output=True, text=True, shell=False)
    assert denied.returncode != 0
    assert not (root / 'execution-plans/formal-task').exists()

def test_live_broker_rejects_changed_shared_dependency():
    root = Path.cwd()
    scratch = Path(os.environ['TMPDIR'])
    source = scratch / 'dependency-input.md'
    source.write_text('# FR-1\nFixture behavior\n')
    dependency = root / 'shared.py'
    before = dependency.read_bytes()
    try:
        dependency.write_bytes(before + b'\nVALUE = 99\n')
        result = subprocess.run([sys.executable, '-B', str(root / 'scripts/vdd/compile_plan.py'),
            '--requirements', str(source), '--out-dir', str(scratch / 'must-not-run')],
            capture_output=True, text=True, shell=False)
        assert result.returncode != 0
        assert 'fixture-entry-admitted' not in result.stdout
        assert not (scratch / 'must-not-run').exists()
    finally:
        dependency.write_bytes(before)
''')
    policy = {'schema': 'toolchain.skill-baseline-policy.v1', 'shared_roots': ['shared.py'],
              'bootstrap_history': '.agents/skill-baselines/bootstrap-history.v1.json',
              'skills': {name: {'roots': [folder], 'suites': ['tests/test_feature.py']}
                         for name, folder in baseline.SKILLS.items()}}
    analysis = put(root, 'logs/history-fixture.json', '{"fixture_only":true}')
    family = {'id': 'fixture-behavior', 'intent': 'Tiny runner fixture, not repository history.',
              'commits': ['fixture-only'], 'implementation': ['shared.py'],
              'replacement_basis': 'Fixture has no historical predecessor.',
              'tests': ['tests/test_feature.py::test_required_case']}
    put(root, policy['bootstrap_history'], json.dumps({
        'schema': 'toolchain.skill-bootstrap-history.v1', 'fixed_main': 'fixture-only',
        'scope_start_exclusive': 'fixture-only', 'merge_boundaries': {'8-24': 'fixture', '8-05': 'fixture'},
        'skills': {name: {'source_analysis': {'path': 'logs/history-fixture.json',
                    'sha256': baseline.digest(analysis.read_bytes())}, 'families': [family]}
                   for name in baseline.SKILLS}}))
    put(root, baseline.POLICY, json.dumps(policy))
    return root


def candidate_file(root, name='candidate.json'):
    value = baseline.candidate(root, list(baseline.SKILLS))
    p = root / 'logs' / name
    baseline.atomic(p, value)
    return p, value


def invoke(root, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.pop(baseline.CHANNEL, None)
    return subprocess.run([sys.executable, '-B', str(root / 'scripts/skill_baseline.py'), *args],
                          cwd=root, env=env, capture_output=True, text=True, timeout=180, shell=False)


def disk_stopped_fixture(tmp_path, monkeypatch):
    """Real child launches interrupted by simulated fixture-only disk pressure."""
    root = small_root(tmp_path)
    target = 'scripts/tests/test_skill_baseline.py'
    put(root, target, 'def test_required_case():\n    assert 2 + 2 == 4\n')
    p = json.loads((root / baseline.POLICY).read_text())
    h = json.loads((root / p['bootstrap_history']).read_text())
    for name in baseline.SKILLS:
        p['skills'][name]['suites'] = [target]
        h['skills'][name]['families'][0]['tests'] = [target + '::test_required_case']
    put(root, baseline.POLICY, json.dumps(p))
    put(root, p['bootstrap_history'], json.dumps(h))
    initial, _ = candidate_file(root, 'initial.json')
    boot = invoke(root, 'test', '--candidate', str(initial.relative_to(root)),
                  '--out', 'logs/bootstrap', '--bootstrap')
    assert boot.returncode == 0, boot.stdout + boot.stderr
    with (root / target).open('a') as f:
        f.write('\ndef test_first_increment():\n    assert {1, 2} != {1}\n')
    origin_file, origin = candidate_file(root, 'origin.json')
    key = baseline.digest(baseline.wire({'candidate': origin, 'target': target,
                                         'platform': baseline.platform_key()}))
    proofs = []
    for n in (1, 2):
        batch = root / f'logs/disk-failure-{n}'
        baseline.atomic(batch / 'candidate.json', origin)
        unit = batch / 'quick-dev/0'
        with monkeypatch.context() as m:
            m.setattr(baseline.shutil, 'disk_usage', lambda _: SimpleNamespace(free=0))
            with pytest.raises(ValueError, match='regression-failed'):
                baseline.run_unit(root, target, unit, '', key)
        assert baseline.read_json(unit / 'exit.json')['timeout'] == 'insufficient-disk-during-unit'
        proofs.append({'directory': unit.relative_to(root).as_posix(), 'files': {
            name: baseline.digest((unit / name).read_bytes())
            for name in ('argv.json', 'request.json', 'exit.json', 'stdout.log')}})
    ledger = root / 'logs/workflow-unit-budgets/skill-baseline' / (key + '.json')
    prior = ledger.read_bytes()
    assert baseline.read_json(ledger)['failures'] == 2
    with (root / 'scripts/skill_baseline.py').open('a') as f:
        f.write('\n# Fixture successor: repaired resource runner identity.\n')
    with (root / target).open('a') as f:
        f.write('\ndef test_second_increment():\n    assert len({1, 2, 3}) == 3\n')
    successor_file, successor = candidate_file(root, 'successor.json')
    request = {'schema': 'toolchain.skill-resource-recovery.v1',
        'owner_confirmation': {'operation': 'one-disk-recovery-batch', 'message_id': 'fixture-only-explicit-owner'},
        'origin_candidate': {'path': origin_file.relative_to(root).as_posix(),
                             'sha256': baseline.digest(origin_file.read_bytes())},
        'candidate_sha256': baseline.digest(baseline.wire(successor)),
        'output': 'logs/recovered', 'platform': baseline.platform_key(), 'target': target,
        'unit_key': key, 'ledger_sha256': baseline.digest(prior), 'failures': proofs}
    request_file = put(root, 'logs/recovery-request.json', json.dumps(request))
    return root, successor_file, successor, request_file, request, ledger, prior


def test_resource_recovery_real_cli_preserves_two_failures_costs_and_all_skill_uses(tmp_path, monkeypatch):
    root, candidate, successor, request, value, ledger, prior = disk_stopped_fixture(tmp_path, monkeypatch)
    before_pointer = (root / baseline.STORE / 'current.json').read_bytes()
    result = invoke(root, 'test', '--candidate', str(candidate.relative_to(root)), '--out', value['output'],
                    '--resource-recovery', str(request.relative_to(root)), '--defer-admission')
    assert result.returncode == 0, result.stdout + result.stderr
    state = baseline.read_json(ledger)
    assert state['failures'] == 2
    assert state['spent'] > json.loads(prior)['spent']
    measured = baseline.read_json(root / value['output'] / 'measurement.json')
    receipt = baseline.read_json(root / measured['resource_recovery']['receipt'])
    assert receipt['status'] == 'complete' and receipt['expected_uses'] == 2
    assert [row['status'] for row in receipt['uses']] == ['passed', 'passed']
    assert receipt['unit_key'] == value['unit_key'] and receipt['prior'] == json.loads(prior)
    assert (root / value['output'] / 'resource-recovery-ledger-preimage.json').read_bytes() == prior
    assert (root / baseline.STORE / 'current.json').read_bytes() == before_pointer
    # Both real skill units execute every mandatory case; old failures do not
    # become successful proof records and a repeated claim cannot run again.
    for rows in measured['units'].values():
        report = baseline.read_json(root / rows[0]['source'])
        assert len(report['selected']) == 3 and report['exit_code'] == 0
    measurement_path = root / value['output'] / 'measurement.json'
    original_measurement = measurement_path.read_bytes()
    stripped = deepcopy(measured); stripped.pop('resource_recovery')
    measurement_path.write_bytes(baseline.wire(stripped))
    denied = invoke(root, 'admit', '--measurement', value['output'] + '/measurement.json')
    assert denied.returncode != 0 and 'measurement-resource-recovery-binding-missing' in denied.stdout
    measurement_path.write_bytes(original_measurement)
    receipt_path = root / measured['resource_recovery']['receipt']; receipt_bytes = receipt_path.read_bytes()
    receipt_path.write_bytes(receipt_bytes + b' ')
    assert invoke(root, 'admit', '--measurement', value['output'] + '/measurement.json').returncode != 0
    receipt_path.write_bytes(receipt_bytes)
    repeated = invoke(root, 'test', '--candidate', str(candidate.relative_to(root)), '--out', value['output'],
                      '--resource-recovery', str(request.relative_to(root)), '--defer-admission')
    assert repeated.returncode != 0
    renewed = deepcopy(value)
    renewed.update(output='logs/reuse-forbidden', ledger_sha256=baseline.digest(ledger.read_bytes()))
    renewed_file = put(root, 'logs/renewed-request.json', json.dumps(renewed))
    second_claim = baseline.ResourceRecovery(root, successor, renewed['output'], renewed_file.relative_to(root).as_posix())
    second_out = root / renewed['output']; second_out.mkdir()
    with pytest.raises(FileExistsError): second_claim.claim(second_out)
    admitted = invoke(root, 'admit', '--measurement', value['output'] + '/measurement.json')
    assert admitted.returncode == 0, admitted.stdout + admitted.stderr
    assert invoke(root, 'check').returncode == 0
    # Mutation after measurement still fails normal source validation.
    put(root, 'shared.py', 'VALUE = 999\n')
    assert invoke(root, 'check').returncode != 0


@pytest.fixture
def stopped_recovery(tmp_path, monkeypatch):
    return disk_stopped_fixture(tmp_path, monkeypatch)


@pytest.mark.parametrize('defect', ['assertion', 'ordinary-timeout', 'wrong-key', 'wrong-platform',
    'wrong-candidate', 'missing-owner', 'ledger-tamper', 'raw-tamper', 'duplicate-failure',
    'scope-growth', 'space', 'no-case-growth', 'completed-assertion', 'duplicate-nonce'])
def test_resource_recovery_rejects_nonresource_forgery_scope_and_unrestored_space(stopped_recovery, monkeypatch, defect):
    root, candidate, successor, request, value, ledger, prior = stopped_recovery
    if defect in {'assertion', 'ordinary-timeout'}:
        raw = root / value['failures'][0]['directory'] / 'exit.json'
        state = baseline.read_json(raw)
        state.update(exit_code=1, timeout=None if defect == 'assertion' else 'idle-timeout')
        raw.write_bytes(baseline.wire(state))
        value['failures'][0]['files']['exit.json'] = baseline.digest(raw.read_bytes())
    elif defect == 'wrong-key': value['unit_key'] = '0' * 64
    elif defect == 'wrong-platform': value['platform'] = 'not-this-platform'
    elif defect == 'wrong-candidate': value['candidate_sha256'] = '0' * 64
    elif defect == 'missing-owner': value.pop('owner_confirmation')
    elif defect == 'ledger-tamper': ledger.write_text('{"failures":0,"spent":0}')
    elif defect == 'raw-tamper': (root / value['failures'][0]['directory'] / 'stdout.log').write_text('changed')
    elif defect == 'duplicate-failure': value['failures'][1] = value['failures'][0]
    elif defect == 'completed-assertion':
        put(root, value['failures'][0]['directory'] + '/case-report.json', '{"exit_code":1}')
    elif defect == 'duplicate-nonce':
        first = baseline.read_json(root / value['failures'][0]['directory'] / 'request.json')
        second = root / value['failures'][1]['directory'] / 'request.json'
        second.write_bytes(baseline.wire(first))
        value['failures'][1]['files']['request.json'] = baseline.digest(second.read_bytes())
    elif defect == 'scope-growth':
        successor = deepcopy(successor)
        successor['skills']['vdd']['fingerprint']['files']['shared.py'] = 'unapproved-change'
        value['candidate_sha256'] = baseline.digest(baseline.wire(successor))
    elif defect == 'no-case-growth':
        successor = deepcopy(successor)
        origin = baseline.read_json(root / value['origin_candidate']['path'])
        for name in baseline.SKILLS:
            successor['skills'][name]['suite']['cases'] = origin['skills'][name]['suite']['cases']
        value['candidate_sha256'] = baseline.digest(baseline.wire(successor))
    else: monkeypatch.setattr(baseline.shutil, 'disk_usage', lambda _: SimpleNamespace(free=511 * 1024 * 1024))
    request.write_bytes(baseline.wire(value))
    with pytest.raises((ValueError, KeyError)):
        baseline.ResourceRecovery(root, successor, value['output'], request.relative_to(root).as_posix())
    assert not (root / value['output']).exists()


def test_resource_recovery_claim_is_once_only_and_failure_cannot_authorize(stopped_recovery):
    root, candidate, successor, request, value, ledger, prior = stopped_recovery
    recovery = baseline.ResourceRecovery(root, successor, value['output'], request.relative_to(root).as_posix())
    out = root / value['output']; out.mkdir()
    recovery.claim(out)
    with pytest.raises(FileExistsError): recovery.claim(out)
    recovery.authorize(value['target'], value['unit_key'], out / 'vdd/0')
    assert ledger.read_bytes() == prior
    state = json.loads(prior); state['failures'] += 1; state['spent'] += 1
    ledger.write_bytes(baseline.wire(state))
    recovery.end_unit(value['target'], False)
    with pytest.raises(ValueError, match='resource-recovery-use-or-ledger-mismatch'):
        recovery.authorize(value['target'], value['unit_key'], out / 'quick-dev/0')
    with pytest.raises(ValueError, match='resource-recovery-incomplete-batch'): recovery.complete(out)
    assert baseline.read_json(ledger)['failures'] == 3
    assert not (root / baseline.STORE / 'bootstrap.json').read_bytes() == b''


def test_resource_recovery_real_failed_assertion_keeps_third_failure_and_stops_second_use(stopped_recovery):
    root, candidate, successor, request, value, ledger, prior = stopped_recovery
    target = root / value['target']
    target.write_text(target.read_text().replace('assert len({1, 2, 3}) == 3', 'assert len({1, 2, 3}) == 4'))
    successor = baseline.candidate(root, list(baseline.SKILLS))
    candidate.write_bytes(baseline.wire(successor))
    value['candidate_sha256'] = baseline.digest(baseline.wire(successor))
    request.write_bytes(baseline.wire(value))
    result = invoke(root, 'test', '--candidate', str(candidate.relative_to(root)), '--out', value['output'],
                    '--resource-recovery', str(request.relative_to(root)), '--defer-admission')
    assert result.returncode != 0
    state = baseline.read_json(ledger)
    assert state['failures'] == 3 and state['spent'] > json.loads(prior)['spent']
    receipt = baseline.read_json(root / 'logs/workflow-unit-budgets/skill-baseline/resource-recoveries' / (value['unit_key'] + '.json'))
    assert receipt['status'] == 'failed' and len(receipt['uses']) == 1
    assert not (root / value['output'] / 'measurement.json').exists()


def test_resource_recovery_rechecks_live_space_after_claim(stopped_recovery, monkeypatch):
    root, candidate, successor, request, value, ledger, prior = stopped_recovery
    recovery = baseline.ResourceRecovery(root, successor, value['output'], request.relative_to(root).as_posix())
    out = root / value['output']; out.mkdir(); recovery.claim(out)
    monkeypatch.setattr(baseline.shutil, 'disk_usage', lambda _: SimpleNamespace(free=511 * 1024 * 1024))
    with pytest.raises(ValueError, match='resource-recovery-space-not-restored'):
        recovery.authorize(value['target'], value['unit_key'], out / 'vdd/0')
    assert ledger.read_bytes() == prior and recovery.state['uses'] == []


def test_ordinary_batch_keeps_five_arguments_and_never_passes_resource_keywords(tmp_path, monkeypatch):
    root = small_root(tmp_path)
    _, enrolled = candidate_file(root)
    observed = []
    def ordinary(*args, **kwargs):
        assert len(args) == 5 and kwargs == {}
        observed.append(args[1])
        raise ValueError('ordinary-unit-boundary-reached')
    monkeypatch.setattr(baseline, 'run_unit', ordinary)
    with pytest.raises(ValueError, match='mandatory-regression-units-failed:2'):
        baseline.run_tests(root, enrolled, 'logs/ordinary', bootstrap=True)
    assert observed == ['tests/test_feature.py', 'tests/test_feature.py']
    failures = baseline.read_json(root / 'logs/ordinary/failed-units.json')
    assert all(row['reason'] == 'ordinary-unit-boundary-reached' for row in failures)


def test_resource_recovery_any_batch_unit_failure_blocks_unused_stopped_unit(stopped_recovery):
    root, candidate, successor, request, value, ledger, prior = stopped_recovery
    recovery = baseline.ResourceRecovery(root, successor, value['output'], request.relative_to(root).as_posix())
    out = root / value['output']; out.mkdir(); recovery.claim(out)
    recovery.end_unit('another-declared-unit.py', False)
    with pytest.raises(ValueError, match='resource-recovery-use-or-ledger-mismatch'):
        recovery.authorize(value['target'], value['unit_key'], out / 'vdd/0')
    assert recovery.state['status'] == 'failed' and recovery.state['uses'] == []
    assert ledger.read_bytes() == prior


def test_fingerprint_is_relative_and_tracks_shared_imported_code(tmp_path):
    a = small_root(tmp_path / 'a')
    b = tmp_path / 'b'
    shutil.copytree(a, b)
    before = {n: baseline.fingerprint(a, n) for n in baseline.SKILLS}
    assert before == {n: baseline.fingerprint(b, n) for n in baseline.SKILLS}
    put(a, 'logs/ignored.txt', 'time and arbitrary run bytes')
    put(a, baseline.STORE + '/ignored.json', '{}')
    put(a, baseline.SKILLS['vdd'] + '/device.user.toml', 'private="not fingerprinted"')
    assert before == {n: baseline.fingerprint(a, n) for n in baseline.SKILLS}
    put(a, 'scripts/sc/unrelated_dashboard.py', 'VALUE = 1\n')
    assert before == {n: baseline.fingerprint(a, n) for n in baseline.SKILLS}
    put(a, 'shared.py', 'VALUE = 2\n')
    assert all(before[n] != baseline.fingerprint(a, n) for n in baseline.SKILLS)
    put(a, 'shared.py', 'from imported import VALUE\n')
    put(a, 'imported.py', 'VALUE = 1\n')
    first = baseline.fingerprint(a, 'vdd')
    assert 'imported.py' in first['files']
    put(a, 'imported.py', 'VALUE = 2\n')
    assert first != baseline.fingerprint(a, 'vdd')


@pytest.mark.parametrize('kind', ['rename', 'copy', 'comment', 'delete', 'weaken'])
def test_no_semantic_test_growth_or_old_case_loss_is_rejected(tmp_path, kind):
    root = small_root(tmp_path)
    p = root / 'tests/test_feature.py'
    old = baseline.test_inventory(root, ['tests/test_feature.py'])
    text = p.read_text()
    if kind == 'rename':
        text = text.replace('test_required_case', 'test_renamed_case')
    elif kind == 'copy':
        text += '\ndef test_copied_case():\n    assert 2 + 2 == 4\n'
    elif kind == 'comment':
        text += '\n# New test coverage is only a comment.\n'
    elif kind == 'delete':
        text = text.replace('def test_required_case():\n    assert 2 + 2 == 4\n', '')
        text += '\ndef test_distinct_case():\n    assert sum([1, 2]) == 3\n'
    else:
        text = text.replace('assert 2 + 2 == 4', 'assert True')
        text += '\ndef test_distinct_case():\n    assert sum([1, 2]) == 3\n'
    p.write_text(text, encoding='utf-8')
    with pytest.raises(ValueError, match='increment|nonadditive|removed'):
        baseline.check_increment(old, baseline.test_inventory(root, ['tests/test_feature.py']))


def test_real_added_case_and_appended_assertion_are_supported(tmp_path):
    root = small_root(tmp_path)
    p = root / 'tests/test_feature.py'
    old = baseline.test_inventory(root, ['tests/test_feature.py'])
    with p.open('a', encoding='utf-8') as stream:
        stream.write('\ndef test_distinct_case():\n    from shared import VALUE\n    assert VALUE == 1\n')
    assert baseline.check_increment(old, baseline.test_inventory(root, ['tests/test_feature.py']))
    p.write_text(p.read_text().replace('assert 2 + 2 == 4', 'assert 2 + 2 == 4\n    from shared import VALUE\n    assert VALUE == 1'), encoding='utf-8')
    assert baseline.check_increment(old, baseline.test_inventory(root, ['tests/test_feature.py']))


@pytest.mark.parametrize('mutation', ['skip', 'failed', 'missing', 'nonce', 'xfail', 'deselected'])
def test_case_report_cannot_admit_non_success(mutation):
    row = {'schema': 'toolchain.skill-baseline-case-report.v1', 'stage': 'baseline-regression',
           'nonce': 'n', 'complete': True, 'exit_code': 0, 'errors': [],
           'selected': ['test.py::test_one'], 'collected': {'test.py::test_one': []},
           'events': [{'node_id': 'test.py::test_one', 'phase': p, 'outcome': 'passed', 'xfail': False}
                      for p in ['setup', 'call', 'teardown']]}
    assert baseline.validate_report(row, 'n') == 1
    if mutation == 'skip': row['events'][1]['outcome'] = 'skipped'
    elif mutation == 'failed': row['exit_code'] = 1
    elif mutation == 'missing': row['events'].pop()
    elif mutation == 'nonce': row['nonce'] = 'wrong'
    elif mutation == 'xfail': row['events'][1]['xfail'] = True
    else: row['collected']['test.py::test_omitted'] = []
    with pytest.raises(ValueError):
        baseline.validate_report(row, 'n')


def test_arbitrary_environment_channel_cannot_bypass_entry(tmp_path, monkeypatch):
    root = small_root(tmp_path)
    candidate_path, enrolled = candidate_file(root)
    out = candidate_path.parent
    with baseline.TestChannel(root, out, enrolled) as ticket:
        monkeypatch.setenv(baseline.CHANNEL, ticket)
        # This process is pytest, not the actual regression runner ancestor.
        with pytest.raises(ValueError, match='SKILL_ADMISSION'):
            baseline.require_admission(root, 'vdd', ['--help'])


def test_actual_public_entries_reject_before_native_import_or_launch(tmp_path):
    root = small_root(tmp_path)
    env = dict(os.environ)
    env.pop(baseline.CHANNEL, None)
    env['JIMUYUN_SKIP_SKILL_HASH'] = '1'
    for relative in ['scripts/vdd/compile_plan.py', 'scripts/quick_dev/run.py']:
        (root / relative).write_bytes((ROOT / relative).read_bytes())
        done = subprocess.run([sys.executable, '-B', str(root / relative), '--help'],
                              cwd=root, env=env, capture_output=True, text=True, timeout=20, shell=False)
        assert done.returncode == 1
        assert json.loads(done.stdout)['status'] == 'blocked'
        assert 'SKILL_ADMISSION' in done.stdout


def test_real_runner_bootstrap_integrity_and_increment_rejection(tmp_path, monkeypatch):
    root = small_root(tmp_path)
    candidate_file(root)
    done = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/run', '--bootstrap')
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout.splitlines()[-1])['status'] == 'admitted'
    for name in baseline.SKILLS:
        assert baseline.approved(root, name)['bootstrap'] is True
    actual_versions = baseline.tool_versions()
    monkeypatch.setattr(baseline, 'tool_versions', lambda: actual_versions | {'pytest': 'changed-version'})
    with pytest.raises(ValueError, match='mismatch'):
        baseline.approved(root, 'vdd')
    monkeypatch.undo()
    denied = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/reset', '--bootstrap')
    assert denied.returncode != 0 and 'bootstrap-already' in denied.stdout
    put(root, 'shared.py', 'VALUE = 2\n')
    for name in baseline.SKILLS:
        with pytest.raises(ValueError, match='mismatch'):
            baseline.approved(root, name)
    new = baseline.candidate(root, list(baseline.SKILLS))
    with pytest.raises(ValueError, match='no-substantive-test-increment'):
        baseline.run_tests(root, new, 'logs/no-increment')
    assert not (root / 'logs/no-increment').exists()
    put(root, 'shared.py', 'VALUE = 1\n')
    pointer = baseline.current(root)
    ref = pointer['platforms'][baseline.platform_key()]['vdd']
    admission = root / ref['path']
    original = admission.read_bytes()
    admission.write_bytes(original + b' ')
    with pytest.raises(ValueError, match='corrupt'):
        baseline.approved(root, 'vdd')
    admission.write_bytes(original)
    proof = root / baseline.record(root, ref)['results'][0]['proof']
    proof.write_bytes(proof.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='proof-corrupt'):
        baseline.approved(root, 'vdd')


def test_measured_candidate_drift_prevents_admission(tmp_path, monkeypatch):
    root = small_root(tmp_path)
    _, enrolled = candidate_file(root)
    calls = []
    def measured(r, target, out, channel, key):
        calls.append(target)
        (out / 'scratch').mkdir(parents=True)
        put(r, 'shared.py', 'VALUE = 999\n')
        return {'target': target, 'nonce': 'n', 'source': root / 'unused.json'}
    monkeypatch.setattr(baseline, 'run_unit', measured)
    with pytest.raises(ValueError, match='changed-during-tests'):
        baseline.run_tests(root, enrolled, 'logs/drift', bootstrap=True)
    assert calls and baseline.current(root) is None


@pytest.mark.parametrize('mutation', ['source', 'coverage', 'missing'])
def test_bootstrap_requires_intact_history_and_actual_mandatory_cases(tmp_path, mutation):
    root = small_root(tmp_path)
    history_path = root / baseline.policy(root)['bootstrap_history']
    history = baseline.read_json(history_path)
    if mutation == 'source':
        put(root, 'logs/history-fixture.json', '{"changed":true}')
    elif mutation == 'coverage':
        history['skills']['vdd']['families'][0]['tests'] = ['tests/test_feature.py::test_not_required']
    else:
        history['skills']['vdd']['families'] = []
    history_path.write_text(json.dumps(history))
    enrolled = baseline.candidate(root, list(baseline.SKILLS))
    with pytest.raises(ValueError, match='bootstrap-history'):
        baseline.run_tests(root, enrolled, 'logs/uncovered', bootstrap=True)
    assert baseline.current(root) is None and not (root / 'logs/uncovered').exists()


def test_real_timed_out_unit_keeps_failure_and_cannot_admit(tmp_path, monkeypatch):
    import workflow_unit_budget
    root = small_root(tmp_path)
    put(root, 'tests/test_hanging.py',
        'import time\ndef test_hang():\n    time.sleep(30)\n    assert False\n')
    original = workflow_unit_budget.Budget
    monkeypatch.setattr(workflow_unit_budget, 'Budget',
        lambda **kw: original(**(kw | {'total': .5, 'idle': .3})))
    out = root / 'logs/timeout'
    with pytest.raises(ValueError, match='regression-failed'):
        baseline.run_unit(root, 'tests/test_hanging.py', out, '{}', 'timeout-fixture')
    result = baseline.read_json(out / 'exit.json')
    assert result['timeout'] and result['exit_code'] != 0
    assert result['elapsed_seconds'] < 10
    assert baseline.current(root) is None
    assert baseline.read_json(root / 'logs/workflow-unit-budgets/skill-baseline/timeout-fixture.json')['failures'] == 1


def test_failed_required_unit_never_admits_even_if_other_units_pass(tmp_path, monkeypatch):
    root = small_root(tmp_path)
    _, enrolled = candidate_file(root)
    calls = []
    def measured(r, target, out, channel, key):
        calls.append(target)
        (out / 'scratch').mkdir(parents=True)
        if len(calls) == 1:
            raise ValueError('fixture-required-unit-failed')
        return {'target': target, 'nonce': 'n', 'source': root / 'unused.json'}
    monkeypatch.setattr(baseline, 'run_unit', measured)
    with pytest.raises(ValueError, match='mandatory-regression-units-failed:1'):
        baseline.run_tests(root, enrolled, 'logs/partial', bootstrap=True)
    assert len(calls) == 2 and baseline.current(root) is None
    assert baseline.read_json(root / 'logs/partial/failed-units.json')[0]['reason'] == 'fixture-required-unit-failed'


def test_low_space_stops_owned_unit_without_success_or_admission(tmp_path, monkeypatch):
    from types import SimpleNamespace
    root = small_root(tmp_path)
    monkeypatch.setattr(baseline.shutil, 'disk_usage', lambda p: SimpleNamespace(free=80 * 1024 * 1024))
    out = root / 'logs/resource-stop'
    with pytest.raises(ValueError, match='regression-failed'):
        baseline.run_unit(root, 'tests/test_feature.py', out, '{}', 'resource-fixture')
    result = baseline.read_json(out / 'exit.json')
    assert result['timeout'] == 'insufficient-disk-during-unit'
    assert result['exit_code'] != 0 and baseline.current(root) is None


def test_real_diagnostic_channel_cannot_issue_an_admission(tmp_path):
    root = small_root(tmp_path)
    candidate_file(root)
    done = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/diagnostic',
        '--diagnostic-target', 'tests/test_feature.py', '--skill', 'vdd')
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout.splitlines()[-1])['status'] == 'diagnostic-only'
    assert baseline.current(root) is None and not (root / baseline.STORE).exists()
    assert set(baseline.read_json(root / 'logs/diagnostic/candidate.json')['skills']) == {'vdd'}
    rejected = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/undeclared',
        '--diagnostic-target', 'tests/not_in_policy.py')
    assert rejected.returncode != 0 and baseline.current(root) is None


def test_deferred_real_measurement_requires_intact_current_proofs_before_admission(tmp_path):
    root = small_root(tmp_path)
    candidate_file(root)
    done = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/measured',
        '--bootstrap', '--defer-admission')
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout.splitlines()[-1])['status'] == 'measured-only'
    assert baseline.current(root) is None
    measurement = 'logs/measured/measurement.json'
    value = baseline.read_json(root / measurement)
    proof = root / value['units']['vdd'][0]['source']
    original = proof.read_bytes()
    proof.write_bytes(original + b' ')
    rejected = invoke(root, 'admit', '--measurement', measurement)
    assert rejected.returncode != 0 and 'proof-changed' in rejected.stdout
    assert baseline.current(root) is None
    proof.write_bytes(original)
    put(root, 'shared.py', 'VALUE = 2\n')
    rejected = invoke(root, 'admit', '--measurement', measurement)
    assert rejected.returncode != 0 and 'candidate' in rejected.stdout
    assert baseline.current(root) is None
    put(root, 'shared.py', 'VALUE = 1\n')
    accepted = invoke(root, 'admit', '--measurement', measurement)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert baseline.approved(root, 'vdd')['bootstrap'] is True


@pytest.mark.parametrize('kind', ['constant-only', 'after-return'])
def test_obviously_nonbehavioral_test_growth_is_rejected(tmp_path, kind):
    root = small_root(tmp_path)
    p = root / 'tests/test_feature.py'
    if kind == 'after-return':
        p.write_text(p.read_text().replace('assert 2 + 2 == 4', 'assert 2 + 2 == 4\n    return'))
    old = baseline.test_inventory(root, ['tests/test_feature.py'])
    if kind == 'constant-only':
        with p.open('a') as stream:
            stream.write('\ndef test_constant_arithmetic():\n    assert 6 * 7 == 42\n')
    else:
        p.write_text(p.read_text().replace('    return\n', '    return\n    from shared import VALUE\n    assert VALUE == 1\n'))
    with pytest.raises(ValueError, match='increment|nonadditive'):
        baseline.check_increment(old, baseline.test_inventory(root, ['tests/test_feature.py']))


def test_approved_startup_rechecks_bytes_without_reparsing_sealed_ast(tmp_path, monkeypatch):
    root = small_root(tmp_path)
    candidate_file(root)
    done = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/full', '--bootstrap')
    assert done.returncode == 0, done.stdout + done.stderr
    def unexpected_reparse(*args):
        raise AssertionError('Unchanged sealed test AST must not be rebuilt at startup')
    monkeypatch.setattr(baseline, 'test_inventory', unexpected_reparse)
    assert baseline.approved(root, 'vdd')['bootstrap'] is True
    put(root, 'shared.py', 'VALUE = 2\n')
    with pytest.raises(ValueError, match='fingerprint-or-suite-mismatch'):
        baseline.approved(root, 'vdd')


def test_controlled_entry_does_not_duplicate_the_brokers_live_check(tmp_path):
    root = small_root(tmp_path)
    entry = root / 'scripts/vdd/compile_plan.py'
    source = entry.read_text()
    source = source.replace('require_admission(root,',
        'import skill_baseline\n'
        'def forbidden_candidate_rebuild(*args):\n'
        '    raise AssertionError("Child must delegate live content check to actual broker")\n'
        'skill_baseline.candidate=forbidden_candidate_rebuild\nrequire_admission(root,')
    entry.write_text(source)
    candidate_file(root)
    measured = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/full',
                      '--bootstrap', '--defer-admission')
    assert measured.returncode == 0, measured.stdout + measured.stderr
    assert baseline.current(root) is None
    admitted = invoke(root, 'admit', '--measurement', 'logs/full/measurement.json')
    assert admitted.returncode == 0, admitted.stdout + admitted.stderr
    entry_result = subprocess.run([sys.executable, '-B', str(entry)], cwd=root,
                                 capture_output=True, text=True, timeout=10)
    assert entry_result.returncode == 0 and 'fixture-entry-admitted' in entry_result.stdout


def test_authenticated_fixture_startup_delegates_both_old_approval_and_live_scan_to_broker(tmp_path):
    """The actual authenticated broker remains the one current-content reader."""
    root = small_root(tmp_path)
    entry = root / 'scripts/vdd/compile_plan.py'
    source = entry.read_text().replace('require_admission(root,',
        'import os, skill_baseline\n'
        'if os.environ.get(skill_baseline.CHANNEL):\n'
        '    def forbidden_duplicate_scan(*args, **kwargs):\n'
        '        raise AssertionError("Authenticated fixture must use broker live hash, not duplicate child scans")\n'
        '    skill_baseline.approved=forbidden_duplicate_scan\n'
        '    skill_baseline.fingerprint=forbidden_duplicate_scan\n'
        'require_admission(root,')
    entry.write_text(source)
    candidate_file(root)
    result = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/broker-only',
                    '--bootstrap', '--defer-admission')
    # The unchanged tiny suite also makes a real shared-dependency mutation
    # and a formal-task request: both must still be refused by the broker.
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (root / 'execution-plans/formal-task').exists()
    assert baseline.current(root) is None
    admitted = invoke(root, 'admit', '--measurement', 'logs/broker-only/measurement.json')
    assert admitted.returncode == 0, admitted.stdout + admitted.stderr
    env = dict(os.environ); env.pop(baseline.CHANNEL, None)
    ordinary = subprocess.run([sys.executable, '-B', str(entry), '--help'], cwd=root,
                              env=env, capture_output=True, text=True, timeout=10)
    assert ordinary.returncode == 0, ordinary.stdout + ordinary.stderr
    put(root, 'shared.py', 'VALUE = 999\n')
    drift = subprocess.run([sys.executable, '-B', str(entry), '--help'], cwd=root,
                           env=env, capture_output=True, text=True, timeout=10)
    assert drift.returncode != 0 and 'fixture-entry-admitted' not in drift.stdout


def test_repeated_import_resolution_has_no_cross_call_filesystem_cache(tmp_path):
    root = small_root(tmp_path)
    put(root, 'shared.py', 'import optional_fixture_dependency\n' * 40 + 'VALUE = 1\n')
    first = baseline.fingerprint(root, 'vdd')
    extra = put(root, 'optional_fixture_dependency.py', 'VALUE = 2\n')
    changed = baseline.fingerprint(root, 'vdd')
    assert 'optional_fixture_dependency.py' not in first['files']
    assert changed['files']['optional_fixture_dependency.py'] == baseline.digest(extra.read_bytes())
    assert changed['sha256'] != first['sha256']
    extra.unlink()
    assert baseline.fingerprint(root, 'vdd') == first


@pytest.mark.parametrize('kind', ['parametrize-ids', 'param-id', 'cer-param-mark'])
def test_param_display_labels_cannot_turn_a_copy_into_substantive_growth(tmp_path, kind):
    test = tmp_path / 'test_values.py'
    forms = {
        'parametrize-ids': "@pytest.mark.parametrize('value', [1], ids=['LABEL'])",
        'param-id': "@pytest.mark.parametrize('value', [pytest.param(1, id='LABEL')])",
        'cer-param-mark': "@pytest.mark.parametrize('value', [pytest.param(1, marks=pytest.mark.cer_assertion('LABEL'))])",
    }
    decorator = forms[kind]
    original = 'import pytest\n' + decorator.replace('LABEL', 'original-label') + '\ndef test_original(value):\n    assert value > 0\n'
    test.write_text(original)
    old = baseline.test_inventory(tmp_path, ['test_values.py'])
    original_bytes = test.read_bytes()
    copy = decorator.replace('LABEL', 'renamed-label') + '\ndef test_copy(value):\n    assert value > 0\n'
    test.write_text(original + '\n' + copy)
    assert baseline.digest(test.read_bytes()) != baseline.digest(original_bytes)
    with pytest.raises(ValueError, match='increment|nonadditive'):
        baseline.check_increment(old, baseline.test_inventory(tmp_path, ['test_values.py']))
    with test.open('a') as out:
        out.write("\n@pytest.mark.parametrize('value', [-1])\ndef test_actual_negative_value(value):\n    assert value < 0\n")
    assert baseline.check_increment(old, baseline.test_inventory(tmp_path, ['test_values.py'])) == ['test_values.py::test_actual_negative_value']


@pytest.mark.parametrize('skill', ['vdd', 'quick-dev'])
@pytest.mark.parametrize('style', ['equals', 'abbreviation', 'mixed', 'duplicate'])
def test_candidate_path_options_refuse_noncanonical_or_ambiguous_forms(tmp_path, skill, style):
    root = tmp_path
    scratch = root / 'scratch'
    scratch.mkdir()
    put(root, 'scratch/input.md', '# Fixture input')
    put(root, 'scratch/plan.json', '{}')
    if skill == 'vdd':
        args = ['--requirements', str(scratch / 'input.md'), '--out-dir', str(scratch / 'plan')]
        flag, short = '--result-json', '--result-j'
    else:
        args = ['--plan', str(scratch / 'plan.json')]
        flag, short = '--run-dir', '--run-d'
    outside = str(root / 'formal-output')
    inside = str(scratch / 'result')
    assert baseline.fixture_command(root, scratch, skill, [*args, flag, inside])
    variants = {'equals': [flag + '=' + outside], 'abbreviation': [short, outside],
                'mixed': [flag, inside, flag + '=' + outside],
                'duplicate': [flag, outside, flag, inside]}
    assert not baseline.fixture_command(root, scratch, skill, [*args, *variants[style]])


def test_parent_package_initializers_and_their_imports_are_fingerprinted(tmp_path):
    root = small_root(tmp_path)
    put(root, 'shared.py', 'from support.deep.worker import VALUE\n')
    put(root, 'support/__init__.py', 'from . import state\nVALUE = 1\n')
    put(root, 'support/state.py', 'STATE = 1\n')
    put(root, 'support/deep/__init__.py', 'VALUE = 1\n')
    put(root, 'support/deep/worker.py', 'VALUE = 1\n')
    before = baseline.fingerprint(root, 'vdd')
    for relative in ['support/__init__.py', 'support/state.py', 'support/deep/__init__.py']:
        assert relative in before['files']
        original = (root / relative).read_bytes()
        (root / relative).write_bytes(original + b'\nCHANGED = True\n')
        assert baseline.fingerprint(root, 'vdd') != before
        (root / relative).write_bytes(original)


@pytest.mark.parametrize('configuration', ['conftest.py', 'pytest.ini'])
def test_applicable_pytest_configuration_changes_both_candidate_and_suite(tmp_path, configuration):
    root = small_root(tmp_path)
    original = 'VALUE = 1\n' if configuration.endswith('.py') else '[pytest]\naddopts =\n'
    put(root, configuration, original)
    before = baseline.candidate(root, list(baseline.SKILLS))
    for row in before['skills'].values():
        assert configuration in row['fingerprint']['files']
        assert configuration in row['suite']['files']
    put(root, configuration, original + ('CHANGED = True\n' if configuration.endswith('.py') else 'testpaths = tests\n'))
    after = baseline.candidate(root, list(baseline.SKILLS))
    for name in baseline.SKILLS:
        assert after['skills'][name]['fingerprint'] != before['skills'][name]['fingerprint']
        assert after['skills'][name]['suite_sha256'] != before['skills'][name]['suite_sha256']


def test_parent_initializer_and_test_configuration_drift_refuse_real_approval(tmp_path):
    root = small_root(tmp_path)
    put(root, 'shared.py', 'from support.deep.worker import VALUE\n')
    for relative in ['support/__init__.py', 'support/deep/__init__.py', 'support/deep/worker.py', 'conftest.py']:
        put(root, relative, 'VALUE = 1\n')
    put(root, 'pytest.ini', '[pytest]\naddopts =\n')
    candidate_file(root)
    measured = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/run', '--bootstrap')
    assert measured.returncode == 0, measured.stdout + measured.stderr
    for relative in ['support/__init__.py', 'support/deep/__init__.py', 'conftest.py', 'pytest.ini']:
        original = (root / relative).read_bytes()
        (root / relative).write_bytes(original + (b'\nCHANGED = True\n' if relative.endswith('.py') else b'\ntestpaths = tests\n'))
        for name in baseline.SKILLS:
            with pytest.raises(ValueError, match='mismatch'):
                baseline.approved(root, name)
        denied = invoke(root, 'check')
        assert denied.returncode != 0 and 'mismatch' in denied.stdout
        (root / relative).write_bytes(original)


def test_live_candidate_broker_rejects_initializer_and_pytest_configuration_drift(tmp_path):
    root = small_root(tmp_path)
    put(root, 'shared.py', 'from support.worker import VALUE\n')
    put(root, 'support/__init__.py', 'VALUE = 1\n')
    put(root, 'support/worker.py', 'VALUE = 1\n')
    put(root, 'conftest.py', 'VALUE = 1\n')
    put(root, 'tests/test_package_drift.py', r'''import os
from pathlib import Path
import subprocess
import sys

def test_changed_package_or_collection_input_cannot_run():
    root = Path.cwd()
    scratch = Path(os.environ['TMPDIR'])
    source = scratch / 'input.md'
    source.write_text('# Fixture input')
    for relative in ['support/__init__.py', 'conftest.py']:
        path = root / relative
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'\nCHANGED = True\n')
            result = subprocess.run([sys.executable, '-B', str(root / 'scripts/vdd/compile_plan.py'),
                '--requirements', str(source), '--out-dir', str(scratch / 'blocked')],
                cwd=root, capture_output=True, text=True, timeout=20)
            assert result.returncode != 0
            assert 'fixture-entry-admitted' not in result.stdout
            assert not (scratch / 'blocked').exists()
        finally:
            path.write_bytes(original)
''')
    policy = baseline.policy(root)
    for row in policy['skills'].values():
        row['suites'].append('tests/test_package_drift.py')
    put(root, baseline.POLICY, json.dumps(policy))
    candidate_file(root)
    result = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/diagnostic',
                    '--diagnostic-target', 'tests/test_package_drift.py', '--skill', 'vdd')
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.splitlines()[-1])['status'] == 'diagnostic-only'
    assert baseline.current(root) is None


def test_published_guard_fixture_is_self_contained_and_preserves_all_failure_roles():
    """ADR-0041: generic published regressions contain no business-task source payload."""
    relative = '.agents/skills/vdd-execution-plan/scripts/tests/fixtures/expected_red_guard_returned.json'
    fixture = json.loads((ROOT / relative).read_text(encoding='utf-8'))
    provenance = fixture['provenance']
    assert provenance.get('kind') == 'self-contained-synthetic-contract-fixture'
    assert provenance['runtime_sources_required'] == [] and provenance['authorizes'] == []
    assert len(fixture['cases']) == 16
    assert len({c['obligation']['obligation_id'] for c in fixture['cases']}) == 16
    assert all(c['obligation']['source_refs'] == [
        f'fixtures/generic-requirements.md#FR-{index}']
        for index, c in enumerate(fixture['cases'], 1))
    assert all('returned_response' not in c for c in fixture['cases'])
    text = json.dumps(fixture, sort_keys=True)
    assert not any(value in text for value in (
        'logs/', 'execution-plans/', '/workspace/', 'PhaseA.Platform',
        'S2-06', 's2-06', 's2_06', 'home_node_id'))
    families = [[f['failure_family'] for f in c['raw_failure_intents']]
                for c in fixture['cases']]
    assert sum(set(row) <= {'artifact-integrity', 'semantic-contract-gap'}
               for row in families) == 14
    assert sum(row.count('task-implementation-failure') for row in families) == 1
    assert sum(row.count('expected-red') for row in families) == 1
    assert sum(row.count('test-harness-failure') for row in families) == 1
    preparer = '.agents/skills/maintain-knowledge-base/scripts/prepare_publication_request.py'
    assert all(preparer in baseline.fingerprint(ROOT, skill)['files']
               for skill in ('quick-dev', 'vdd'))
