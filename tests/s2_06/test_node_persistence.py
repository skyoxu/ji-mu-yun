"""ADR-0061 scoped S2-06: real temporary SQLite, HTTP and transaction boundaries."""
from pathlib import Path
import subprocess
import pytest
from trx_support import read_observations, authority_violations

pytest_plugins = ['trx_support']


def _accounts(state):
    return {row['id']: row for row in state['accounts']}


def _home_violations(value):
    errors = []
    columns = {row['name']: row for row in value['installedBeforeStartup']}
    if 'home_node_id' not in columns or columns['home_node_id']['notNull']:
        errors.append('Existing initializer lacks nullable-at-install home column')
    rows = _accounts(value['initialState'])
    for identity in (value['firstId'], value['secondId']):
        if identity not in rows or rows[identity]['home_node_id'] != 'test-physical-node':
            errors.append('Existing account did not retain one protected test home')
    for session in value['sessions']:
        body = session['body']
        if session['status'] != 200 or body.get('accountId') != session['accountId'] or (body.get('ownership') or {}).get('homeNodeId') != 'test-physical-node':
            errors.append('Current authenticated self/forged-selector readback did not retain the protected home')
    if value['adminListStatus'] != 200 or value['userAdminStatus'] not in (403, 404) or value['forgedCreateStatus'] not in (403, 404):
        errors.append('Explicit actual admin/ordinary central-reader and writer controls are not enforced')
    admin_rows = {r['accountId']: r for r in value['adminUsers'].get('users', [])}
    for identity in (value['firstId'], value['secondId']):
        if admin_rows.get(identity, {}).get('homeNodeId') != 'test-physical-node':
            errors.append('Actual authorized admin home read does not reflect protected state')
    for row in value['conflicts']:
        if row['Started'] or row['state'] != value['beforeConflict']:
            errors.append('Changed ordinal/opaque node binding was accepted or mutated current facts')
    if value['unsafeConsumers']:
        errors.append('Actual production constructors still receive unrestricted central storage/options: ' + ','.join(value['unsafeConsumers']))
    return errors


def _new_home_violations(value):
    errors = []
    rows = _accounts(value['initialState'])
    for identity in (value['newAccountId'], value['directAccountId']):
        if not identity or rows.get(identity, {}).get('home_node_id') != 'test-physical-node':
            errors.append('Actual HTTP/direct central creation did not bind the server-selected unique home')
    if value['newStatus'] != 200:
        errors.append('Valid current central create did not work with a populated synthetic key-pool fixture')
    if value['forgedCreateStatus'] not in (403, 404):
        errors.append('Ordinary account forged central writer authority')
    if value['falsePolicyControlStatus'] != 200:
        raise RuntimeError('Policy-false host lost valid authenticated central read control')
    if value['falsePolicyStatus'] not in (403, 409, 503) or value['falsePolicyAccountId'] is not None:
        errors.append('Protected false policy admitted a new account')
    final = _accounts(value['finalState'])
    for identity in (value['firstId'], value['secondId']):
        if final.get(identity, {}).get('home_node_id') != 'test-physical-node':
            errors.append('False policy or caller hints changed an existing home')
    return errors


def _atomic_violations(value):
    errors = []
    before, changed = _accounts(value['initialState']), _accounts(value['changedState'])
    projection = {row['account_id']: row for row in value['changedState']['projections']}
    identity = value['firstId']
    first = changed.get(identity, {})
    visible = projection.get(identity, {})
    old_revision, new_revision = before.get(identity, {}).get('authority_revision'), first.get('authority_revision')
    if value['disableStatus'] != 200 or first.get('is_disabled') != 1:
        errors.append('Valid actual central account-state update did not occur')
    if not isinstance(old_revision, int) or not isinstance(new_revision, int) or old_revision < 1 or new_revision <= old_revision:
        errors.append('Actual central authority revision is absent/nonpositive/not monotonic')
    if visible.get('authority_revision') != new_revision or visible.get('home_node_id') != first.get('home_node_id') or visible.get('is_enabled') != 0:
        errors.append('Committed actual account/home/revision and projection are inconsistent')
    other = value['secondId']
    if before.get(other) != changed.get(other):
        errors.append('Updating one actual account changed another account')
    if not value['projectionFaultReached'] or not value['creationFaultReached'] or value['faultStatus'] != 19:
        errors.append('Real SQLite projection fault did not reach both mutation and initial-creation transactions')
    if value['faultBefore'] != value['faultAfter']:
        errors.append('Actual reached projection fault left a committed partial account/home/projection change')
    return errors


@pytest.mark.cer_assertion('A-O-53E6DDB4537B-1',
    'A-O-53E6DDB4537B-2',
    'A-O-53E6DDB4537B-3',
    'A-O-53E6DDB4537B-4')
def test_o_53e6ddb4537b(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'persistence-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodePersistenceTests.O_53E6DDB4537B',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    value = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodePersistenceTests.O_53E6DDB4537B', 'S206_AUTHORITY:')
    errors = authority_violations(value)
    if errors:
        print('FAILURE_ID:FAILURE-O-53E6DDB4537B')
    assert not errors, errors


@pytest.mark.cer_assertion('A-O-B093CBB29DA6-1',
    'A-O-B093CBB29DA6-2',
    'A-O-B093CBB29DA6-3',
    'A-O-B093CBB29DA6-4')
def test_o_b093cbb29da6(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'persistence-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodePersistenceTests.O_B093CBB29DA6',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    value = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodePersistenceTests.O_B093CBB29DA6', 'S206_PERSISTENCE:')
    errors = _home_violations(value)
    reentry = value['bindingReentry']
    if {row['mode'] for row in reentry['cases']} != {
        'unchanged', 'missing-home', 'missing-project', 'missing-projection', 'stale-projection'
    }:
        raise RuntimeError('Real completed-binding install matrix incomplete')
    for row in reentry['cases']:
        if row['mode'] == 'unchanged':
            if row['rejected'] or not row['unchanged']:
                raise RuntimeError('Legitimate direct repeated-install control unavailable')
        elif row['mode'] in {'missing-projection', 'stale-projection'}:
            # AD17 permits current-central refresh OR safe denial. Derived
            # projection repair must not alter authoritative home/revision/data.
            if row['rejected']:
                if not row['unchanged']:
                    errors.append((row['mode'], 'rejected projection refresh changed data'))
            elif not row['authorityUnchanged'] or not row['projectionCurrent']:
                errors.append((row['mode'], 'refresh lost current central source identity'))
        elif not row['rejected'] or not row['unchanged']:
            errors.append((row['mode'], 'completed binding was silently repaired/reassigned'))
    disabled = reentry['disabledOwner']
    if not disabled['started'] or not disabled['secondSeeded']:
        errors.append('One explicitly disabled owner blocked healthy local startup/recovery')
    if disabled['firstSeeded'] or not disabled['retained'] or not disabled['unchanged']:
        errors.append('Disabled owner received recovery writes or destructive compensation')
    if errors:
        print('FAILURE_ID:FAILURE-O-B093CBB29DA6')
    assert not errors, errors


@pytest.mark.cer_assertion('A-O-B30BD7CEB94E-1',
    'A-O-B30BD7CEB94E-2',
    'A-O-B30BD7CEB94E-3',
    'A-O-B30BD7CEB94E-4')
def test_o_b30bd7ceb94e(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'persistence-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodePersistenceTests.O_B30BD7CEB94E',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    value = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodePersistenceTests.O_B30BD7CEB94E', 'S206_PERSISTENCE:')
    errors = _new_home_violations(value)
    if errors:
        print('FAILURE_ID:FAILURE-O-B30BD7CEB94E')
    assert not errors, errors


@pytest.mark.cer_assertion('A-O-B77520560CA4-1',
    'A-O-B77520560CA4-2',
    'A-O-B77520560CA4-3',
    'A-O-B77520560CA4-4')
def test_o_b77520560ca4(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'persistence-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodePersistenceTests.O_B77520560CA4',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    value = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodePersistenceTests.O_B77520560CA4', 'S206_PERSISTENCE:')
    errors = _atomic_violations(value)
    if errors:
        print('FAILURE_ID:FAILURE-O-B77520560CA4')
    assert not errors, errors
