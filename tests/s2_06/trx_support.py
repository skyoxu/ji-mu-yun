"""ADR-0061: validate fresh invocation-specific genuine TRX before business assertions."""
import json
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET


def read_observations(completed, results_directory, fully_qualified_name, prefix):
    # Preserve genuine child artifacts before pytest rotates temporary fixture roots.
    # This is a byte archive only; it never creates a verdict or native stage receipt.
    archive = Path(__file__).resolve().parents[2] / 'logs' / 's2-06-native-child-artifacts'
    archive.mkdir(parents=True, exist_ok=True)
    for source in Path(results_directory).glob('*.trx'):
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        destination = archive / (digest + '.trx')
        if destination.exists():
            if destination.read_bytes() != raw:
                raise RuntimeError('Child raw-artifact hash collision or corruption')
        else:
            with destination.open('xb') as stream:
                stream.write(raw)
    if completed.returncode != 0:
        raise RuntimeError("Native .NET build/test harness failed: " + completed.stdout[-2500:] + completed.stderr[-1000:])
    files = list(Path(results_directory).glob('*.trx'))
    if len(files) != 1:
        raise RuntimeError('Expected exactly one fresh TRX')
    root = ET.parse(files[0]).getroot()
    ns = {'t': 'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}
    definitions = {}
    for test in root.findall('.//t:TestDefinitions/t:UnitTest', ns):
        method = test.find('t:TestMethod', ns)
        if method is not None:
            definitions[test.attrib['id']] = method.attrib['className'].split(',')[0] + '.' + method.attrib['name']
    results = root.findall('.//t:Results/t:UnitTestResult', ns)
    if len(results) != 1 or definitions.get(results[0].attrib.get('testId')) != fully_qualified_name:
        raise RuntimeError('Wrong or ambiguous executed .NET method')
    result = results[0]
    if result.attrib.get('outcome') != 'Passed':
        raise RuntimeError('Native observation case did not pass its harness checks')
    lines = [line.strip() for node in result.findall('.//t:StdOut', ns) for line in (node.text or '').splitlines()]
    payloads = [line[len(prefix):] for line in lines if line.startswith(prefix)]
    if len(payloads) != 1:
        raise RuntimeError('Missing or ambiguous actual product observations')
    return json.loads(payloads[0])


def authority_violations(observed):
    """Compare the current real source/owner handoff, never runtime completion."""
    import json
    document = observed['document']
    graph = json.loads(document.split('```json\n', 1)[1].split('\n```', 1)[0])
    source = graph['source_authority']
    errors = []
    if source['adopted_spine_sha256'] != observed['spineSha256'] or observed['spineSha256'] != 'df6549c9f72595bfd883ea8f3d557935ae0f2daf835b500803618be2ef6ef7f2':
        errors.append('Accepted owner decision is not bound to the actual immutable adopted spine')
    addendum = observed['adr'].split('## Addendum (2026-10-28 S2-06', 1)[1]
    if 'accepted for the approved implementation scope' not in addendum or observed['spineSha256'] not in addendum:
        errors.append('Current ADR does not actually adopt the exact scoped spine')
    if source['decisions'] != list(range(14, 27)) or 'AD-1 through AD-13' not in addendum:
        errors.append('Scoped and parent decision namespaces are not preserved')
    if not all(row['present'] for row in observed['ownerPaths']):
        errors.append('A concrete current authority owner path is absent')
    if graph['ordering'] != ['accepted_irreversible_authority', 'restricted_interfaces_and_storage', 'dispatch_implementation', 'runtime_validation']:
        errors.append('Implementation is allowed before irreversible authority and interface decisions')
    if graph['persistence']['owner'] != 'PhaseA.Platform/Data/SqliteMetadataSchema.cs' or graph['persistence']['database'] != 'existing_protected_local_sqlite':
        errors.append('Storage authority is replaced or left wholly unspecified')
    if set(graph['persistence']['tables']) != {'node_binding', 'accounts', 'projects', 'account_node_projections'} or graph['persistence']['conflict'] != 'rollback_entire_binding_increment_without_reassignment_or_adoption':
        errors.append('Minimal additive storage/rollback contract was not fixed')
    if set(graph['node_owner']['denied']) != {'central_account_writer', 'credential_store', 'sql_connection_or_factory', 'unrestricted_options', 'service_locator', 'home_reassignment'}:
        errors.append('Restricted node interfaces silently broaden protected authority')
    if graph['unresolved_authority_contradictions'] or graph['authorizes']:
        errors.append('Unresolved owner contradiction or self-authorizing handoff')
    if graph['readback']['unmeasured'] != [False, None, None] or 'no-store' not in document:
        errors.append('Compatible readback/measurement/privacy boundary lost')
    if 'pending' not in graph['implementation_claim'] or 'not a' not in document:
        errors.append('Design handoff is misrepresented as runtime proof')
    return errors


# Test-only ownership: native observations do not authorize fixture disposal.
# The final pytest teardown report is the sole success decision here.
import os
import re
import stat
import subprocess
import sys
import uuid
import pytest


def _require_safe_scratch(config):
    """ADR-0061: reject destructive pytest defaults before requesting tmp_path."""
    if getattr(config, '_s206_safe_scratch_checked', False):
        return
    import tempfile
    logs = Path(__file__).resolve().parents[2] / 'logs'

    def contained(path):
        absolute = Path(os.path.abspath(path))
        if not absolute.is_relative_to(logs) or absolute.resolve() != absolute:
            raise pytest.UsageError('s206-scratch-retention: use a real repository logs path without symlink parents')
        return absolute

    base = config.option.basetemp
    if base is not None:
        # Pytest removes an existing explicit basetemp recursively. Even an empty
        # directory or dangling link must not be accepted as a reusable scratch.
        base = contained(base)
        if os.path.lexists(base):
            raise pytest.UsageError('s206-scratch-retention: explicit basetemp must be a new, absent path')
    else:
        try:
            count = int(config.getini('tmp_path_retention_count'))
        except (ValueError, TypeError) as exc:
            raise pytest.UsageError('s206-scratch-retention: invalid retention count') from exc
        if (count < 1000
                or config.getini('tmp_path_retention_policy') != 'all'):
            raise pytest.UsageError('s206-scratch-retention: require native retention1000/all or a new dedicated basetemp')
        pool = contained(tempfile.gettempdir())
        # Finite retention is safe only while this invocation cannot rotate any
        # existing numbered root. Preserve all users' existing numbered roots.
        for parent in pool.glob('pytest-of-*'):
            contained(parent)
            if parent.is_symlink() or not parent.is_dir():
                raise pytest.UsageError('s206-scratch-retention: unsafe shared pytest root')
            if any(parent.glob('garbage-*')) or any(p.is_symlink() and not p.exists() for p in parent.iterdir()):
                raise pytest.UsageError('s206-scratch-retention: shared pool contains automatic-cleanup candidates')
            numbers = [int(p.name[7:]) for p in parent.iterdir()
                       if p.name.startswith('pytest-') and p.name[7:].isdigit()]
            # Pytest keeps by index range, not the number of surviving roots.
            if numbers and max(numbers) + 1 - count >= min(numbers):
                raise pytest.UsageError('s206-scratch-retention: native count would rotate existing history; use new dedicated scratch')
    config._s206_safe_scratch_checked = True


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    _require_safe_scratch(config)


@pytest.fixture(autouse=True)
def s206_case_owned_fixtures(request, monkeypatch):
    _require_safe_scratch(request.config)
    tmp_path = request.getfixturevalue('tmp_path')
    root = tmp_path / ('s206-owned-fixtures-' + uuid.uuid4().hex)
    root.mkdir()
    token = uuid.uuid4().hex
    (root / '.s206-owner.json').write_text(json.dumps({'token': token}), encoding='utf-8')
    identity = root.stat()
    request.node._s206_owned_fixture = (root, identity.st_dev, identity.st_ino, token)
    monkeypatch.setenv('S206_OWNED_FIXTURE_ROOT', str(root))
    # One stable child-process key namespace, shared by parallel native test
    # collections for this Python case. Never mutate it per C# fixture.
    monkeypatch.setenv('PHASEA_SNAPSHOT_KEY_ROOT', str(root / 'synthetic-snapshot-keys'))
    yield
    # Never dispose here: later teardown may still fail or be interrupted.


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    reports = getattr(item, '_s206_phase_reports', {})
    reports[report.when] = report
    item._s206_phase_reports = reports
    owned = getattr(item, '_s206_owned_fixture', None)
    if report.when != 'teardown' or owned is None:
        return
    if not all(phase in reports and reports[phase].passed and not hasattr(reports[phase], 'wasxfail')
               for phase in ('setup', 'call', 'teardown')):
        return
    root, device, inode, token = owned
    try:
        # Files created by the native child are disposable outputs, not source inputs.
        # Hash and remove them in a separate test-support process. The current owned
        # dependency observer stays enabled and the retained TRX remains untouched.
        result = subprocess.run(
            [sys.executable, '-B', str(Path(__file__).resolve()), '--cleanup-owned-fixture',
             str(root), str(device), str(inode), token],
            cwd=Path(__file__).resolve().parents[2], shell=False, check=False,
            capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr[-1600:] or result.stdout[-1600:])
    except Exception as error:
        # This runs before the native case collector consumes the final report.
        report.outcome = 'failed'
        report.longrepr = 'Owned fixture cleanup refused; data retained: ' + str(error)


def cleanup_owned_fixture(root, device, inode, token):
    """One exact per-case output tree, never a prefix scan or general log cleaner."""
    import shutil
    root = Path(root).absolute()
    logs = Path(__file__).resolve().parents[2] / 'logs'
    if not re.fullmatch(r's206-owned-fixtures-[0-9a-f]{32}', root.name):
        raise ValueError('Unexpected owned fixture name')
    if not root.is_relative_to(logs) or root.resolve() != root or root.is_symlink():
        raise ValueError('Owned fixture must be a real repository log directory')
    identity = root.lstat()
    if not stat.S_ISDIR(identity.st_mode) or (identity.st_dev, identity.st_ino) != (int(device), int(inode)):
        raise ValueError('Owned fixture identity changed')
    marker = root / '.s206-owner.json'
    if marker.is_symlink() or json.loads(marker.read_text(encoding='utf-8')) != {'token': token}:
        raise ValueError('Owned fixture marker changed')
    rows = []
    for base, directories, files in os.walk(root, followlinks=False):
        for name in directories:
            path = Path(base) / name
            if path.is_symlink() or path.resolve() != path:
                raise ValueError('Owned fixture contains a directory link')
        for name in files:
            path = Path(base) / name
            entry = path.lstat()
            if not stat.S_ISREG(entry.st_mode) or entry.st_nlink != 1 or path.is_symlink():
                raise ValueError('Owned fixture contains a linked or nonregular file')
            rows.append({'path': path.relative_to(root).as_posix(), 'bytes': entry.st_size,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    # Preserve content identity and the fact of disposal outside the removed tree.
    report_path = root.parent / (root.name + '.cleanup.json')
    if report_path.exists():
        raise ValueError('Owned fixture cleanup already recorded')
    record = {'schema': 's2-06.successful-fixture-disposal.v1', 'root': str(root),
              'files': rows, 'deleted': False,
              'warning': 'Hashes only; SQLite working data is not backed up.', 'authorizes': []}
    with report_path.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, sort_keys=True)
    current = root.lstat()
    if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino) or root.is_symlink():
        raise ValueError('Owned fixture identity changed before disposal')
    shutil.rmtree(root)
    record['deleted'] = True
    report_path.write_text(json.dumps(record, sort_keys=True), encoding='utf-8')


if __name__ == '__main__':
    if len(sys.argv) != 6 or sys.argv[1] != '--cleanup-owned-fixture':
        raise SystemExit('Only exact test-owned fixture disposal is supported')
    cleanup_owned_fixture(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
