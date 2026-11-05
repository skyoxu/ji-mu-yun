"""ADR-0041: regression admission integrity and fixture-only candidate execution."""
from copy import deepcopy
import ast
import gzip
import json
import os
from pathlib import Path
import shutil
import shlex
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import skill_baseline as baseline



@pytest.mark.parametrize('system,image_kind,entry_kind,base_kind,expected', [
    ('Windows', 'base', 'runner', 'valid', True),
    ('Windows', 'launcher', 'runner', 'valid', False),
    ('Windows', 'foreign', 'runner', 'valid', False),
    ('Windows', 'other_venv', 'runner', 'valid', False),
    ('Windows', 'base', 'other', 'valid', False),
    ('Windows', 'base', 'runner', 'missing', False),
    ('Windows', 'base', 'runner', 'foreign', False),
    ('Windows', 'base', 'runner', 'relative', False),
    ('Linux', 'launcher', 'runner', 'missing', True),
    ('Linux', 'base', 'runner', 'valid', False),
])
def test_runner_ancestor_binds_exact_runtime_image(tmp_path, monkeypatch, system, image_kind, entry_kind, base_kind, expected):
    # ADR-0041: neither an arbitrary interpreter nor a claimed ticket grants trust.
    runtime = tmp_path / 'runtime'
    base = runtime / 'python.exe'
    launcher = tmp_path / 'venv/Scripts/python.exe'
    foreign = tmp_path / 'foreign/python.exe'
    claimed_base = {'valid':str(base), 'missing':None, 'foreign':str(foreign), 'relative':'python.exe'}[base_kind]
    monkeypatch.setattr(baseline, 'sys', SimpleNamespace(executable=str(launcher), _base_executable=claimed_base, base_prefix=str(runtime)))
    monkeypatch.setattr(baseline, 'platform', SimpleNamespace(system=lambda:system))
    image = {'base':base,'launcher':launcher,'foreign':foreign,'other_venv':base}[image_kind].resolve()
    entry = 'scripts/skill_baseline.py' if entry_kind == 'runner' else 'scripts/other.py'
    argv = [str(launcher), '-u', '-B', str(tmp_path / entry), 'test']
    parent_pid = os.getpid() + 2000000
    def process(pid):
        if pid == parent_pid:
            return 0, argv, tmp_path, (foreign if image_kind == 'other_venv' else launcher).resolve()
        return parent_pid, argv, tmp_path, image
    monkeypatch.setattr(baseline, '_process', process)
    assert baseline._runner_ancestor(tmp_path, os.getpid()) is expected
    assert not baseline._runner_ancestor(tmp_path, os.getpid() + 1000000)


def _successful_scratch_fixture(tmp_path):
    root = tmp_path / 'repository'
    out = root / 'logs' / 'measurement'
    scratch = out / 'quick-dev' / '0' / 'scratch'
    scratch.mkdir(parents=True)
    payload = scratch / 'payload.bin'
    payload.write_bytes(b'fixture payload')
    report = scratch.parent / 'stdout.log'
    report.write_bytes(b'raw report retained')
    return root, out, scratch, payload, report


def _make_cleanup_alias(alias, target, *, junction=False):
    if junction and os.name == 'nt':
        import _winapi
        _winapi.CreateJunction(str(target), str(alias))
    else:
        alias.symlink_to(target, target_is_directory=True)


def _remove_cleanup_alias(alias):
    try:
        metadata = alias.lstat()
    except FileNotFoundError:
        return
    if os.name == 'nt' and getattr(metadata, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_DIRECTORY:
        alias.rmdir()
    else:
        alias.unlink()


def test_successful_scratch_accepts_real_pytest_current_aliases(tmp_path, monkeypatch):
    """ADR-0041: pytest's retained numbered-directory aliases are private fixtures."""
    from _pytest.pathlib import make_numbered_dir
    root, out, scratch, payload, report = _successful_scratch_fixture(tmp_path)
    targets = [make_numbered_dir(scratch, prefix='test_first_'),
               make_numbered_dir(scratch, prefix='test_second_')]
    aliases = [scratch / 'test_first_current', scratch / 'test_second_current']
    for target in targets:
        put(target, 'proof.txt', 'ordinary owned target')
    assert all(stat.S_ISLNK(alias.lstat().st_mode) for alias in aliases)
    real_tree = baseline.shutil.rmtree
    observed = []

    def checked_tree(target, **kwargs):
        for alias in aliases:
            with pytest.raises(FileNotFoundError):
                alias.lstat()
        assert all((entry / 'proof.txt').read_text() == 'ordinary owned target' for entry in targets)
        observed.append(target)
        real_tree(target, **kwargs)

    monkeypatch.setattr(baseline.shutil, 'rmtree', checked_tree)
    baseline._remove_successful_scratch(root, out, 'quick-dev', 0)
    assert observed == [scratch]
    assert not scratch.exists()
    assert report.read_bytes() == b'raw report retained'


@pytest.mark.parametrize('form', ['absolute', 'relative', 'junction', 'verbatim'])
def test_successful_scratch_accepts_only_proven_internal_alias_forms(tmp_path, monkeypatch, form):
    """ADR-0041: namespace spelling does not turn an internal link into a target traversal."""
    root, out, scratch, payload, report = _successful_scratch_fixture(tmp_path)
    target = scratch / 'ordinary-target'
    put(target, 'proof.txt', 'ordinary owned target')
    alias = scratch / 'targetcurrent'
    raw_target = target.name if form == 'relative' else str(target)
    if form == 'verbatim' and os.name == 'nt':
        raw_target = '\\\\?\\' + str(target)
    _make_cleanup_alias(alias, raw_target, junction=form == 'junction')
    real_tree = baseline.shutil.rmtree

    def checked_tree(path, **kwargs):
        with pytest.raises(FileNotFoundError):
            alias.lstat()
        assert (target / 'proof.txt').read_text() == 'ordinary owned target'
        real_tree(path, **kwargs)

    monkeypatch.setattr(baseline.shutil, 'rmtree', checked_tree)
    baseline._remove_successful_scratch(root, out, 'quick-dev', 0)
    assert not scratch.exists()
    assert report.read_bytes() == b'raw report retained'


@pytest.mark.parametrize('invalid', ['external', 'chain', 'ancestor', 'missing', 'network'])
def test_successful_scratch_preserves_all_aliases_when_any_target_is_unproven(tmp_path, monkeypatch, invalid):
    """ADR-0041: a safe-looking alias name cannot permit external or chained cleanup."""
    root, out, scratch, payload, report = _successful_scratch_fixture(tmp_path)
    target = scratch / 'ordinary-target'
    put(target, 'proof.txt', 'ordinary owned target')
    outside = tmp_path / 'outside'
    put(outside, 'proof.txt', 'outside data')
    good, bad = scratch / 'goodcurrent', scratch / 'badcurrent'
    _make_cleanup_alias(good, target)
    destinations = {'external': os.path.relpath(outside, scratch), 'chain': good,
                    'ancestor': scratch, 'missing': scratch / 'missing-target', 'network': target}
    _make_cleanup_alias(bad, destinations[invalid])
    real_readlink, real_metadata = os.readlink, baseline._cleanup_metadata

    def read_alias(path):
        if invalid == 'network' and Path(path) == bad:
            return r'\\unreachable.invalid\share\target'
        return real_readlink(path)

    def private_metadata(path):
        assert path == root or path.is_relative_to(root), 'External target metadata must never be read.'
        return real_metadata(path)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(baseline.os, 'readlink', read_alias)
            patch.setattr(baseline, '_cleanup_metadata', private_metadata)
            with pytest.raises(ValueError, match='scratch-cleanup-reparse-point'):
                baseline._remove_successful_scratch(root, out, 'quick-dev', 0)
        assert stat.S_ISLNK(good.lstat().st_mode)
        assert stat.S_ISLNK(bad.lstat().st_mode)
        assert payload.read_bytes() == b'fixture payload'
        assert (target / 'proof.txt').read_text() == 'ordinary owned target'
        assert (outside / 'proof.txt').read_text() == 'outside data'
        assert report.read_bytes() == b'raw report retained'
    finally:
        _remove_cleanup_alias(bad)
        _remove_cleanup_alias(good)


def test_successful_scratch_rejects_alias_target_string_drift_before_deletion(tmp_path, monkeypatch):
    """ADR-0041: cleanup rereads the original link string before removing an alias."""
    root, out, scratch, payload, report = _successful_scratch_fixture(tmp_path)
    first, second = scratch / 'first-target', scratch / 'second-target'
    put(first, 'proof.txt', 'first target')
    put(second, 'proof.txt', 'second target')
    alias = scratch / 'targetcurrent'
    _make_cleanup_alias(alias, first)
    real_readlink = os.readlink
    reads = []

    def changed_readlink(path):
        value = real_readlink(path)
        if Path(path) == alias:
            reads.append(value)
            return value if len(reads) == 1 else str(second)
        return value

    try:
        with monkeypatch.context() as patch:
            patch.setattr(baseline.os, 'readlink', changed_readlink)
            with pytest.raises(ValueError, match='scratch-cleanup-reparse-point:alias-changed'):
                baseline._remove_successful_scratch(root, out, 'quick-dev', 0)
        assert len(reads) >= 2
        assert stat.S_ISLNK(alias.lstat().st_mode)
        assert (first / 'proof.txt').read_text() == 'first target'
        assert (second / 'proof.txt').read_text() == 'second target'
        assert report.read_bytes() == b'raw report retained'
    finally:
        _remove_cleanup_alias(alias)


def test_successful_scratch_rejects_unknown_reparse_tags(tmp_path, monkeypatch):
    """ADR-0041: arbitrary reparse behavior is never inferred from an internal target."""
    root, out, scratch, payload, report = _successful_scratch_fixture(tmp_path)
    target = scratch / 'ordinary-target'
    put(target, 'proof.txt', 'ordinary owned target')
    alias = scratch / 'targetcurrent'
    _make_cleanup_alias(alias, target)
    real_lstat = Path.lstat

    def unknown_metadata(path):
        value = real_lstat(path)
        if path == alias:
            return SimpleNamespace(st_mode=value.st_mode, st_dev=value.st_dev, st_ino=value.st_ino,
                                   st_nlink=value.st_nlink, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
                                   st_reparse_tag=0x8000000A)
        return value

    try:
        with monkeypatch.context() as patch:
            patch.setattr(Path, 'lstat', unknown_metadata)
            with pytest.raises(ValueError, match='scratch-cleanup-reparse-point'):
                baseline._remove_successful_scratch(root, out, 'quick-dev', 0)
        assert stat.S_ISLNK(alias.lstat().st_mode)
        assert payload.read_bytes() == b'fixture payload'
        assert (target / 'proof.txt').read_text() == 'ordinary owned target'
        assert report.read_bytes() == b'raw report retained'
    finally:
        _remove_cleanup_alias(alias)


def test_successful_scratch_removes_readonly_files_and_preserves_reports(tmp_path, monkeypatch):
    """ADR-0041: Windows Git-style read-only payloads cannot abort a successful unit."""
    root = small_root(tmp_path / 'repository')
    _, enrolled = candidate_file(root)
    retained = []

    def passed_unit(repository, target, unit, channel, key):
        scratch = unit / 'scratch'
        payload = put(scratch, 'repo/.git/objects/ab/fixture-object', 'owned fixture')
        os.chmod(payload, stat.S_IREAD)
        report = put(unit, 'stdout.log', 'raw successful unit report')
        retained.append((scratch, report))
        return {'target': target, 'nonce': 'fixture-only', 'source': report}

    monkeypatch.setattr(baseline, 'run_unit', passed_unit)
    result = baseline.run_tests(root, enrolled, 'logs/measurement',
                                diagnostic_target='tests/test_feature.py')
    assert result['status'] == 'diagnostic-only'
    assert result['authorizes'] == []
    assert len(retained) == 2
    assert all(not scratch.exists() for scratch, _ in retained)
    assert all(report.read_text() == 'raw successful unit report' for _, report in retained)
    assert not (root / baseline.STORE / 'current.json').exists()


@pytest.mark.parametrize('invalid', ['outside-logs', 'parent-traversal', 'skill', 'index'])
def test_successful_scratch_rejects_other_cleanup_boundaries(tmp_path, invalid):
    """ADR-0041: a unit cleanup cannot become a general directory deleter."""
    root, out, scratch, payload, report = _successful_scratch_fixture(tmp_path)
    skill, index = 'quick-dev', 0
    if invalid == 'outside-logs':
        out = root / 'outside'
    elif invalid == 'parent-traversal':
        out = out / '..' / 'elsewhere'
    elif invalid == 'skill':
        skill = 'unregistered-skill'
    else:
        index = True
    with pytest.raises(ValueError, match='scratch-cleanup-boundary'):
        baseline._remove_successful_scratch(root, out, skill, index)
    assert payload.read_bytes() == b'fixture payload'
    assert report.read_bytes() == b'raw report retained'


@pytest.mark.parametrize('placement', ['ancestor', 'root', 'descendant'])
def test_successful_scratch_rejects_reparse_objects_before_removing_payload(tmp_path, placement):
    """ADR-0041: real Windows junctions and POSIX links never widen cleanup."""
    root = tmp_path / 'repository'
    out = root / 'logs' / 'measurement'
    out.mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    sentinel = put(outside, 'sentinel.txt', 'outside data')
    scratch = out / 'quick-dev' / '0' / 'scratch'
    if placement == 'ancestor':
        put(outside, '0/scratch/owned.txt', 'retained private payload')
        link = out / 'quick-dev'
    elif placement == 'root':
        scratch.parent.mkdir(parents=True)
        link = scratch
    else:
        scratch.mkdir(parents=True)
        put(scratch, 'owned.txt', 'retained private payload')
        link = scratch / 'linked'
    if os.name == 'nt':
        import _winapi
        _winapi.CreateJunction(str(outside), str(link))
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(ValueError, match='scratch-cleanup-reparse-point'):
            baseline._remove_successful_scratch(root, out, 'quick-dev', 0)
        assert sentinel.read_text() == 'outside data'
        if placement != 'root':
            assert (scratch / 'owned.txt').read_text() == 'retained private payload'
    finally:
        if os.name == 'nt':
            link.rmdir()
        else:
            link.unlink()
    assert sentinel.read_text() == 'outside data'


@pytest.mark.parametrize('failure_kind', ['acl', 'other-error', 'directory'])
def test_successful_scratch_preserves_unrelated_permission_errors(tmp_path, monkeypatch, failure_kind):
    """ADR-0041: only a regular file's actual read-only attribute permits a retry."""
    root, out, scratch, payload, report = _successful_scratch_fixture(tmp_path)
    error = PermissionError('fixture access denied') if failure_kind != 'other-error' else OSError('fixture I/O error')

    def failed_tree(target, *, onerror):
        function = os.rmdir if failure_kind == 'directory' else os.unlink
        onerror(function, str(payload), (type(error), error, None))

    def forbidden_attribute_change(*args, **kwargs):
        raise AssertionError('An unrelated denial must not change file attributes.')

    monkeypatch.setattr(baseline.shutil, 'rmtree', failed_tree)
    monkeypatch.setattr(baseline.os, 'chmod', forbidden_attribute_change)
    with pytest.raises(type(error)) as caught:
        baseline._remove_successful_scratch(root, out, 'quick-dev', 0)
    assert caught.value is error
    assert payload.read_bytes() == b'fixture payload'
    assert report.read_bytes() == b'raw report retained'


def test_successful_scratch_restores_readonly_when_delete_retry_is_denied(tmp_path, monkeypatch):
    """ADR-0041: clearing a read-only bit cannot swallow a real ACL denial."""
    root, out, scratch, payload, report = _successful_scratch_fixture(tmp_path)
    real_metadata, real_chmod = baseline._cleanup_metadata, os.chmod
    original_mode = payload.stat().st_mode
    real_chmod(payload, original_mode & ~stat.S_IWRITE)
    before = payload.stat()
    changes = []
    denied = PermissionError('fixture ACL still denies deletion')

    def readonly_metadata(target):
        value = real_metadata(target)
        if target == payload:
            return SimpleNamespace(st_mode=value.st_mode, st_nlink=value.st_nlink,
                                   st_dev=value.st_dev, st_ino=value.st_ino,
                                   st_file_attributes=stat.FILE_ATTRIBUTE_READONLY)
        return value

    def denied_unlink(filename):
        raise denied

    def failed_tree(target, *, onerror):
        onerror(os.unlink, str(payload), (PermissionError, denied, None))

    def record_attribute_change(target, mode):
        changes.append(mode)
        real_chmod(target, mode)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(baseline, '_cleanup_metadata', readonly_metadata)
            patch.setattr(baseline.os, 'unlink', denied_unlink)
            patch.setattr(baseline.os, 'chmod', record_attribute_change)
            patch.setattr(baseline.shutil, 'rmtree', failed_tree)
            with pytest.raises(PermissionError) as caught:
                baseline._remove_successful_scratch(root, out, 'quick-dev', 0)
        assert caught.value is denied
        assert changes == [before.st_mode | stat.S_IWRITE, before.st_mode]
        assert payload.stat().st_mode == before.st_mode
        assert payload.read_bytes() == b'fixture payload'
        assert report.read_bytes() == b'raw report retained'
    finally:
        real_chmod(payload, original_mode)


def test_successful_scratch_refuses_readonly_hardlink_attribute_changes(tmp_path, monkeypatch):
    """ADR-0041: a scratch link must not change an object's outside alias attributes."""
    root, out, scratch, payload, report = _successful_scratch_fixture(tmp_path)
    outside = tmp_path / 'outside-alias.bin'
    os.link(payload, outside)
    real_metadata = baseline._cleanup_metadata
    denied = PermissionError('fixture read-only hardlink')

    def readonly_metadata(target):
        value = real_metadata(target)
        if target == payload:
            return SimpleNamespace(st_mode=value.st_mode, st_nlink=value.st_nlink,
                                   st_dev=value.st_dev, st_ino=value.st_ino,
                                   st_file_attributes=stat.FILE_ATTRIBUTE_READONLY)
        return value

    def failed_tree(target, *, onerror):
        onerror(os.unlink, str(payload), (PermissionError, denied, None))

    def forbidden_attribute_change(*args, **kwargs):
        raise AssertionError('Hardlinked object attributes must remain unchanged.')

    monkeypatch.setattr(baseline, '_cleanup_metadata', readonly_metadata)
    monkeypatch.setattr(baseline.shutil, 'rmtree', failed_tree)
    monkeypatch.setattr(baseline.os, 'chmod', forbidden_attribute_change)
    with pytest.raises(PermissionError) as caught:
        baseline._remove_successful_scratch(root, out, 'quick-dev', 0)
    assert caught.value is denied
    assert payload.stat().st_ino == outside.stat().st_ino
    assert payload.read_bytes() == outside.read_bytes() == b'fixture payload'
    assert report.read_bytes() == b'raw report retained'


def test_successful_scratch_cleanup_never_runs_for_failed_units(tmp_path, monkeypatch):
    """ADR-0041: failed scratch and raw reports retain their original locations."""
    root = small_root(tmp_path / 'repository')
    _, enrolled = candidate_file(root)
    retained = []

    def failed_unit(repository, target, unit, channel, key):
        payload = put(unit, 'scratch/failure.txt', 'original failed fixture')
        report = put(unit, 'stdout.log', 'original failed report')
        retained.append((payload, report))
        raise ValueError('fixture unit failed')

    def forbidden_cleanup(*args, **kwargs):
        raise AssertionError('Failed units must retain their fixture.')

    monkeypatch.setattr(baseline, 'run_unit', failed_unit)
    monkeypatch.setattr(baseline, '_remove_successful_scratch', forbidden_cleanup)
    with pytest.raises(ValueError, match='mandatory-regression-units-failed:2'):
        baseline.run_tests(root, enrolled, 'logs/measurement', diagnostic_target='tests/test_feature.py')
    assert len(retained) == 2
    assert all(payload.read_text() == 'original failed fixture' for payload, _ in retained)
    assert all(report.read_text() == 'original failed report' for _, report in retained)
    failures = json.loads((root / 'logs/measurement/failed-units.json').read_text())
    assert len(failures) == 2
    assert all(row['reason'] == 'fixture unit failed' for row in failures)
    assert not (root / baseline.STORE / 'current.json').exists()


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
    # The parsed CI contract is unchanged. Short fixture-only root/output names
    # leave room for atomic record suffixes on Windows without system changes.
    fixture_prefix = 'logs/ch456-skill-baseline'
    commands = [[('logs/b' + value[len(fixture_prefix):])
                 if value.startswith(fixture_prefix + '/') else value for value in command]
                for command in commands]
    root = small_root(tmp_path / 'r')
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
                    '--resource-recovery', request.relative_to(root).as_posix(), '--defer-admission')
    assert result.returncode == 0, result.stdout + result.stderr
    state = baseline.read_json(ledger)
    assert state['failures'] == 2
    assert state['spent'] > json.loads(prior)['spent']
    measured = baseline.read_json(root / value['output'] / 'measurement.json')
    receipt = baseline.read_json(root / measured['resource_recovery']['receipt'])
    assert receipt['status'] == 'complete' and receipt['expected_uses'] == 2
    assert [row['status'] for row in receipt['uses']] == ['passed', 'passed']
    assert [row['out'] for row in receipt['uses']] == [
        value['output'] + '/' + name + '/0' for name in measured['candidate']['skills']]
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
                      '--resource-recovery', request.relative_to(root).as_posix(), '--defer-admission')
    assert repeated.returncode != 0
    assert 'resource-recovery-ledger-identity' in repeated.stdout and 'unsafe-path' not in repeated.stdout
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


@pytest.mark.parametrize('defect', ['backslash', 'wrong-unit', 'reordered'])
def test_resource_recovery_admission_rejects_rebound_noncanonical_unit_paths(stopped_recovery, defect):
    """ADR-0041: real recovery admission compares canonical ordered unit paths."""
    root, candidate, successor, request, value, ledger, prior = stopped_recovery
    before_pointer = (root / baseline.STORE / 'current.json').read_bytes()
    measured = invoke(root, 'test', '--candidate', candidate.relative_to(root).as_posix(),
                      '--out', value['output'], '--resource-recovery', request.relative_to(root).as_posix(),
                      '--defer-admission')
    assert measured.returncode == 0, measured.stdout + measured.stderr
    measurement_path = root / value['output'] / 'measurement.json'
    measurement_bytes = measurement_path.read_bytes()
    measurement = json.loads(measurement_bytes)
    receipt_path = root / measurement['resource_recovery']['receipt']
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    expected = [value['output'] + '/' + name + '/0' for name in measurement['candidate']['skills']]
    assert [row['out'] for row in receipt['uses']] == expected
    if defect == 'backslash':
        receipt['uses'][0]['out'] = receipt['uses'][0]['out'].replace('/', '\\')
    elif defect == 'wrong-unit':
        receipt['uses'][0]['out'] += '-different'
    else:
        receipt['uses'].reverse()
    receipt_path.write_bytes(baseline.wire(receipt))
    # Rebind the raw hash so rejection must reach the ordered unit-path guard.
    measurement['resource_recovery']['sha256'] = baseline.digest(receipt_path.read_bytes())
    measurement_path.write_bytes(baseline.wire(measurement))
    refused = invoke(root, 'admit', '--measurement', value['output'] + '/measurement.json')
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert 'measurement-resource-recovery-units' in refused.stdout and 'unsafe-path' not in refused.stdout
    assert (root / baseline.STORE / 'current.json').read_bytes() == before_pointer
    assert baseline.read_json(ledger)['failures'] == json.loads(prior)['failures'] == 2
    receipt_path.write_bytes(receipt_bytes)
    measurement_path.write_bytes(measurement_bytes)
    admitted = invoke(root, 'admit', '--measurement', value['output'] + '/measurement.json')
    assert admitted.returncode == 0, admitted.stdout + admitted.stderr
    assert invoke(root, 'check').returncode == 0


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
                    '--resource-recovery', request.relative_to(root).as_posix(), '--defer-admission')
    assert result.returncode != 0
    assert 'resource-recovery-batch-failed:' + value['target'] in result.stdout
    assert 'unsafe-path' not in result.stdout
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


def test_dependency_import_nodes_preserve_all_statement_containers(monkeypatch):
    # ADR-0041: expression pruning must retain every statically bound import.
    source = '''
import top
from package import member
def ordinary():
    import function_body
    if condition:
        from conditional import member
    else:
        import alternate
    for item in values:
        import loop_body
    else:
        import loop_else
    while condition:
        import while_body
    else:
        import while_else
    with resource():
        import context_body
    try:
        import try_body
    except Exception:
        import handler_body
    else:
        import try_else
    finally:
        import final_body
    try:
        import group_try
    except* Exception:
        import group_handler
    match value:
        case {'key': item} if item:
            import match_body
    return [str(item + 1) for item in values if item]
class Container:
    import class_body
    async def asynchronous(self):
        async for item in stream:
            import async_loop
        else:
            import async_else
        async with manager():
            import async_context
        return await operation()
'''
    tree = ast.parse(source)
    expected = [ast.dump(node) for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    original = ast.iter_child_nodes
    def children(node):
        assert not isinstance(node, ast.expr), 'dependency traversal must not descend expression trees'
        return original(node)
    with monkeypatch.context() as context:
        context.setattr(ast, 'iter_child_nodes', children)
        actual = [ast.dump(node) for node in baseline._dependency_import_nodes(tree)]
    assert len(expected) == 21
    assert actual == expected


def test_dependency_import_nodes_match_full_walk_for_current_sources():
    # ADR-0041: compare against the original full AST walk on actual source bytes.
    inventory = baseline.fingerprint(ROOT, 'vdd')['files']
    compared = 0
    for relative in inventory:
        if relative.endswith('.py'):
            tree = ast.parse((ROOT / relative).read_text(encoding='utf-8-sig'))
            expected = [ast.dump(node) for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
            assert [ast.dump(node) for node in baseline._dependency_import_nodes(tree)] == expected, relative
            compared += 1
    assert compared > 100


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


# ADR-0041, owner-approved 2026-10-31: native publication-only readmission.
@pytest.fixture(scope='module')
def native_refresh_pair(tmp_path_factory):
    from scripts.toolchain.knowledge_query.tests.test_planning_query import _prepare_published_main_fixture
    import publish_knowledge_catalog as publication
    root = _prepare_published_main_fixture(tmp_path_factory.mktemp('baseline-publication-base'), current_controls=True)
    tooling = small_root(tmp_path_factory.mktemp('tiny-baseline-tooling'))
    for source in tooling.rglob('*'):
        if source.is_file():
            target = root / source.relative_to(tooling)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    policy = baseline.read_json(root / baseline.POLICY)
    policy['shared_roots'].append('knowledge/projections')
    (root / baseline.POLICY).write_text(json.dumps(policy), encoding='utf-8')
    # Native validation code is actual source, not a replacement verifier.
    for relative in publication.CONTROL_PATHS:
        assert (root / relative).read_bytes() == (ROOT / relative).read_bytes()
    seed_main = subprocess.check_output(['git', 'rev-parse', 'refs/heads/main'], cwd=root, text=True).strip()
    seed_publication = baseline.read_json(root / 'knowledge/indexes/current.json')
    assert seed_publication['main_commit'] == seed_main
    _, seed_candidate = candidate_file(root, 'seed.json')
    seed = invoke(root, 'test', '--candidate', 'logs/seed.json', '--out', 'logs/seed',
                  '--bootstrap', '--defer-admission')
    assert seed.returncode == 0, seed.stdout + seed.stderr
    admitted = invoke(root, 'admit', '--measurement', 'logs/seed/measurement.json')
    assert admitted.returncode == 0, admitted.stdout + admitted.stderr
    before = baseline.current(root)
    for name in baseline.SKILLS:
        record = baseline.record(root, before['platforms'][baseline.platform_key()][name])
        assert record['bootstrap'] is True and record['predecessor'] is None
        assert record['derived_publication']['pointer'] == seed_publication
        baseline._verify_admission_proofs(root, record)
    agents = root / 'AGENTS.md'
    agents.write_bytes(agents.read_bytes() + b'\nRead-only fixture source refresh.\n')
    _refresh_fixture_commit(root, ['AGENTS.md'])
    refresh_main = subprocess.check_output(['git', 'rev-parse', 'refs/heads/main'], cwd=root, text=True).strip()
    assert subprocess.check_output(['git', 'rev-parse', refresh_main + '^'], cwd=root, text=True).strip() == seed_main
    changed = subprocess.check_output(['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', refresh_main],
                                     cwd=root, text=True).splitlines()
    assert changed == ['AGENTS.md']
    # Seed and successor differ only in derived publication, never execution inputs.
    assert baseline.candidate(root, list(baseline.SKILLS)) == seed_candidate
    for relative in publication.CONTROL_PATHS:
        assert (root / relative).read_bytes() == (ROOT / relative).read_bytes()
    refreshed = _native_fixture_publish(root, 'refresh')
    current_publication = baseline.read_json(root / 'knowledge/indexes/current.json')
    assert refreshed['main_commit'] == current_publication['main_commit'] == refresh_main
    assert refreshed['generation_id'] == current_publication['generation_id'] != seed_publication['generation_id']
    assert baseline.current(root) == before
    successor = baseline.candidate(root, list(baseline.SKILLS))
    assert {key: successor[key] for key in ('policy_sha256', 'runner_sha256', 'tool_versions')} == {
        key: seed_candidate[key] for key in ('policy_sha256', 'runner_sha256', 'tool_versions')}
    for name in baseline.SKILLS:
        assert successor['skills'][name]['suite'] == seed_candidate['skills'][name]['suite']
        previous = baseline.record(root, before['platforms'][baseline.platform_key()][name])
        assert previous['derived_publication']['pointer'] == seed_publication
        baseline._verify_admission_proofs(root, previous)
    return root


def _refresh_fixture_commit(root, paths):
    subprocess.run(['git', 'add', '--', *paths], cwd=root, check=True, capture_output=True)
    subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                    'commit', '-qm', 'Fixture publication source update'], cwd=root, check=True, capture_output=True)


def _native_fixture_publish(root, name):
    import publish_knowledge_catalog as publication
    relative = 'logs/knowledge-context/publication-requests/' + name + '.json'
    command = [sys.executable, '-B', str(ROOT / '.agents/skills/maintain-knowledge-base/scripts/prepare_publication_request.py'),
        '--repository-root', str(root), '--request-id', 'fixture-' + name, '--trigger', 'operator-requested',
        '--target-plan', 'execution-plans/2026-07-26-knowledge-locator-workflow-integration',
        '--output', relative, '--ack-maintainer']
    subprocess.run(command, check=True, capture_output=True, timeout=20)
    result = publication.run(root, publish=True, repeat=1, publication_request=Path(relative))
    assert result['status'] == 'published', result
    main = subprocess.check_output(['git', 'rev-parse', 'refs/heads/main'], cwd=root, text=True).strip()
    request = baseline.read_json(root / relative)
    pointer = baseline.read_json(root / 'knowledge/indexes/current.json')
    manifest_path = root / 'knowledge/indexes/generations' / pointer['generation_id'] / 'manifest.json'
    manifest = baseline.read_json(manifest_path)
    assert result['main_commit'] == request['main_commit'] == pointer['main_commit'] == manifest['main_commit'] == main
    assert result['generation_id'] == pointer['generation_id'] == manifest['generation_id']
    assert result['generation_sha256'] == pointer['generation_sha256'] == 'sha256:' + baseline.digest(manifest_path.read_bytes())
    assert manifest['publication_request'] == publication._load_publication_request(
        root, Path(relative), expected_main=main).summary
    assert result['evaluation']['failed'] == result['evaluation']['protocol_failed'] == 0
    return result


def _refresh_copy(base, path):
    from scripts.toolchain.knowledge_query.tests.test_planning_query import _copy_published_fixture
    return _copy_published_fixture(base, path)


def test_native_publication_refresh_requires_full_remeasurement_and_activates_both_skills(native_refresh_pair, tmp_path_factory):
    root = _refresh_copy(native_refresh_pair, tmp_path_factory.mktemp('r') / 'refresh')
    before = baseline.current(root)
    _, enrolled = candidate_file(root)
    for name, skill in enrolled['skills'].items():
        old = baseline.record(root, before['platforms'][baseline.platform_key()][name])['candidate_skill']
        assert old['suite'] == skill['suite']
        assert {p for p in old['fingerprint']['files'] | skill['fingerprint']['files']
                if old['fingerprint']['files'].get(p) != skill['fingerprint']['files'].get(p)} == {
                    'knowledge/projections/consumer-projections.v1.json'}
    denied = invoke(root, 'check')
    assert denied.returncode != 0 and 'mismatch' in denied.stdout
    measured = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/refreshed', '--defer-admission')
    assert measured.returncode == 0, measured.stdout + measured.stderr
    assert baseline.current(root) == before
    value = baseline.read_json(root / 'logs/refreshed/measurement.json')
    assert set(value['units']) == set(baseline.SKILLS)
    assert all(len(value['units'][name]) == len(enrolled['skills'][name]['suite']['targets']) for name in baseline.SKILLS)
    assert all(value['increments'][name] == [] for name in baseline.SKILLS)
    accepted = invoke(root, 'admit', '--measurement', 'logs/refreshed/measurement.json')
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    for name in baseline.SKILLS:
        approved = baseline.approved(root, name)
        assert approved['predecessor'] == before['platforms'][baseline.platform_key()][name]
        assert approved['derived_publication']['pointer']['generation_id'] == baseline.read_json(root / 'knowledge/indexes/current.json')['generation_id']
    assert invoke(root, 'check').returncode == 0
    previous = baseline.record(root, before['platforms'][baseline.platform_key()]['vdd'])
    proof = root / previous['results'][0]['proof']
    proof.write_bytes(proof.read_bytes() + b'changed')
    refused = invoke(root, 'check')
    assert refused.returncode != 0 and 'proof-corrupt' in refused.stdout


@pytest.mark.parametrize('defect', ['code', 'test-bytes', 'unknown-derived', 'projection-permission',
    'corrupt-layer', 'corrupt-manifest', 'missing-request', 'corrupt-predecessor', 'missing-predecessor',
    'missing-predecessor-proof', 'corrupt-predecessor-proof'])
def test_native_publication_refresh_exception_refuses_unproved_or_mixed_change(native_refresh_pair, tmp_path_factory, defect):
    root = _refresh_copy(native_refresh_pair, tmp_path_factory.mktemp('r') / 'negative')
    if defect == 'code': put(root, 'shared.py', 'VALUE = 2\n')
    elif defect == 'test-bytes':
        target = root / 'tests/test_feature.py'; target.write_bytes(target.read_bytes() + b'\n# no semantic growth\n')
    elif defect == 'unknown-derived': put(root, 'knowledge/projections/unrecognized.json', '{}')
    elif defect == 'projection-permission':
        target = root / 'knowledge/projections/consumer-projections.v1.json'; value = baseline.read_json(target)
        value['projections'][0]['eligible_module_ids'] = []; target.write_text(json.dumps(value), encoding='utf-8')
    elif defect == 'corrupt-layer':
        pointer = baseline.read_json(root / 'knowledge/indexes/current.json')
        target = root / 'knowledge/indexes/generations' / pointer['generation_id'] / 'layers/repository-knowledge-catalog.v2.json'
        target.write_bytes(target.read_bytes() + b' ')
    elif defect == 'corrupt-manifest':
        pointer = baseline.read_json(root / 'knowledge/indexes/current.json')
        target = root / 'knowledge/indexes/generations' / pointer['generation_id'] / 'manifest.json';target.write_bytes(target.read_bytes() + b' ')
    elif defect == 'missing-request':
        (root / 'logs/knowledge-context/publication-requests/refresh.json').unlink()
    elif defect == 'corrupt-predecessor':
        ref = baseline.current(root)['platforms'][baseline.platform_key()]['vdd']; target = root / ref['path'];target.write_bytes(target.read_bytes() + b' ')
    elif defect == 'missing-predecessor': (root / baseline.STORE / 'current.json').unlink()
    elif defect in {'missing-predecessor-proof', 'corrupt-predecessor-proof'}:
        ref = baseline.current(root)['platforms'][baseline.platform_key()]['vdd']
        proof = root / baseline.record(root, ref)['results'][0]['proof']
        if defect == 'missing-predecessor-proof': proof.unlink()
        else: proof.write_bytes(proof.read_bytes() + b'changed')
    before = (root / baseline.STORE / 'current.json').read_bytes() if (root / baseline.STORE / 'current.json').exists() else None
    candidate_file(root)
    denied = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/must-not-run', '--defer-admission')
    assert denied.returncode != 0 and 'SKILL_ADMISSION' in denied.stdout
    assert not (root / 'logs/must-not-run').exists()
    assert ((root / baseline.STORE / 'current.json').read_bytes() if before is not None else None) == before


@pytest.mark.parametrize('kind', ['policy', 'scope'])
def test_native_valid_publication_cannot_hide_policy_or_scope_change(native_refresh_pair, tmp_path_factory, kind):
    root = _refresh_copy(native_refresh_pair, tmp_path_factory.mktemp('r') / 'semantic-change')
    if kind == 'policy':
        target = root / 'knowledge/policies/consumer-policies.v2.json'; value = baseline.read_json(target)
        next(p for p in value['policies'] if p['consumer'] == 'vdd')['max_candidates'] = 19
        target.write_text(json.dumps(value, sort_keys=True), encoding='utf-8'); paths = ['knowledge/policies/consumer-policies.v2.json']
    else:
        relative = 'docs/adr/ADR-9998-fixture-scope.md'
        put(root, relative, '# ADR-9998 Fixture-only additional scope\n\nStatus: Accepted\n\nRead-only fixture scope.\n'); paths = [relative]
    _refresh_fixture_commit(root, paths)
    _native_fixture_publish(root, 'semantic-' + kind)
    candidate_file(root)
    result = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/semantic-denied', '--defer-admission')
    assert result.returncode != 0 and 'SKILL_ADMISSION' in result.stdout
    assert not (root / 'logs/semantic-denied').exists()


@pytest.mark.parametrize('defect', ['incomplete', 'other-publication', 'post-measure-code'])
def test_native_refresh_measurement_cannot_approve_other_or_partial_content(native_refresh_pair, tmp_path_factory, defect):
    root = _refresh_copy(native_refresh_pair, tmp_path_factory.mktemp('r') / 'measurement')
    candidate_file(root)
    measured = invoke(root, 'test', '--candidate', 'logs/candidate.json', '--out', 'logs/measured', '--defer-admission')
    assert measured.returncode == 0, measured.stdout + measured.stderr
    pointer_before = baseline.current(root)
    target = root / 'logs/measured/measurement.json'; value = baseline.read_json(target)
    if defect == 'incomplete': value['units']['vdd'] = []
    elif defect == 'other-publication': value['derived_publications']['vdd']['pointer']['generation_id'] = '0' * 64
    else: put(root, 'shared.py', 'VALUE = 100\n')
    target.write_bytes(baseline.wire(value))
    refused = invoke(root, 'admit', '--measurement', 'logs/measured/measurement.json')
    assert refused.returncode != 0 and 'SKILL_ADMISSION' in refused.stdout
    assert baseline.current(root) == pointer_before
