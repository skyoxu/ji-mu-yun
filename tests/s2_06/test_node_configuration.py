"""ADR-0061 S2-06: actual protected host role responsibilities across phase states."""
from pathlib import Path
import json
import subprocess
import pytest
from trx_support import read_observations, authority_violations

pytest_plugins = ['trx_support']


@pytest.mark.cer_assertion(
    'A-O-C8FCBDB2A9F7-ACTUAL-ROLE-RESPONSIBILITIES-CONTROLS',
    'A-O-C8FCBDB2A9F7-ALL-PHASE-STATES-NO-ROLE-GRANT',
    'A-O-C8FCBDB2A9F7-BOTH-ROLE-COLOCATION-TEST-ONLY',
    'A-O-C8FCBDB2A9F7-EXPLICIT-ENTRY-ROLE-RECOGNIZED',
    'A-O-C8FCBDB2A9F7-EXPLICIT-PRODUCTION-ROLE-RECOGNIZED',
    'A-O-C8FCBDB2A9F7-MISSING-UNKNOWN-ROLE-NO-PRODUCTION',
)
def test_o_c8fcbdb2a9f7(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    fresh_trx_directory = tmp_path / 'role-trx'
    fresh_trx_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_C8FCBDB2A9F7',
         '--logger', 'trx', '--results-directory', str(fresh_trx_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True,
        text=True, encoding='utf-8', errors='replace', timeout=180,
    )
    observations = read_observations(
        completed, fresh_trx_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_C8FCBDB2A9F7',
        'S206_ROLE_OBSERVATIONS:',
    )
    if len(observations) != 18 or {(v['phase'], v['roles']) for v in observations} != {
        (p, roles) for p in ('development', 'test', 'production')
        for roles in (None, '', 'unknown', 'entry', 'production', 'entry,production')
    }:
        raise RuntimeError('Incomplete actual role/phase observation matrix')
    violations = []
    for value in observations:
        roles = value['roles']
        if roles in (None, '', 'unknown'):
            if value['started'] or not value['startupRejected'] or not value['roleDiagnostic']:
                violations.append((value['phase'], roles, 'missing/unknown roles did not safely reject startup'))
            continue
        ownership = value['ownership'] or {}
        expected_roles = roles.split(',')
        if not value['started'] or value['sessionStatus'] != 200:
            violations.append((value['phase'], roles, 'valid explicit role lost central entry control'))
        if sorted(ownership.get('enabledRoles', [])) != sorted(expected_roles):
            violations.append((value['phase'], roles, 'actual role readback differs from explicit roles'))
        if ownership.get('scope') != 'single_node_test':
            violations.append((value['phase'], roles, 'same-host scope is not explicitly test-only'))
        if ownership.get('nodeId') != 'test-physical-node':
            violations.append((value['phase'], roles, 'protected configured physical identity was not retained'))
        if roles == 'entry':
            if value['projectsStatus'] not in (403, 404, 503):
                violations.append((value['phase'], roles, 'entry-only performed ordinary project readback'))
        elif value['projectsStatus'] != 200:
            violations.append((value['phase'], roles, 'valid local production control is unavailable'))
    if violations:
        print('FAILURE_ID:FAILURE_O_C8FCBDB2A9F7')
    assert not violations, violations


@pytest.mark.cer_assertion('A-O-C145D65BFB3C-1', 'A-O-C145D65BFB3C-2',
                          'A-O-C145D65BFB3C-3', 'A-O-C145D65BFB3C-4')
def test_o_c145d65bfb3c(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'capacity-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_C145D65BFB3C',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    values = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_C145D65BFB3C',
        'S206_CAPACITY_OBSERVATIONS:')
    if len(values) != 2 or {v['acceptNewAccounts'] for v in values} != {True, False}:
        raise RuntimeError('Incomplete actual policy/restart observations')
    problems = []
    homes = []
    for row in values:
        session = row['session'] or {}
        ownership = row['ownership'] or {}
        capacity = ownership.get('capacity', {})
        if not row['started'] or row['sessionStatus'] != 200 or not session.get('authenticated'):
            problems.append('Current authorized session lost compatibility')
        if not all(field in session for field in ('accountId', 'username', 'role')):
            problems.append('Existing session fields were removed')
        if not {'nodeId', 'online', 'acceptNewAccounts', 'measurementValid', 'capacityRef', 'readinessRef'} <= set(capacity):
            problems.append('Actual capacity schema does not separate required facts')
        if capacity.get('online') is not True or capacity.get('acceptNewAccounts') is not row['acceptNewAccounts']:
            problems.append('Actual availability and configured policy are not independently represented')
        if capacity.get('measurementValid') is not False or capacity.get('capacityRef') is not None or capacity.get('readinessRef') is not None:
            problems.append('Unmeasured online/policy state was turned into readiness')
        if any(k in capacity for k in ('numericCapacity', 'headroom', 'placementAllowed')):
            problems.append('Unexpected fabricated measurement or placement grant')
        if not ownership.get('homeNodeId'):
            problems.append('Current protected persisted self home is missing')
        homes.append((session.get('accountId'), ownership.get('homeNodeId')))
    if homes[0] != homes[1]:
        problems.append('Changing operator policy changed existing self identity/home')
    if problems:
        print('FAILURE_ID:FAILURE-O-C145D65BFB3C')
    assert not problems, problems


def _capacity_violations(matrix):
    values = matrix.get('observations', [])
    if len(values) != 8 or {(v['acceptNewAccounts'], v['requestedReference']) for v in values} != {
        (policy, reference) for policy in (False, True)
        for reference in (None, 'unknown-reference', 'stale-reference', 'unavailable-reference')
    }:
        raise RuntimeError('The real host did not return the complete capacity input matrix')
    errors = []
    keys = set()
    account_ids = set()
    for row in values:
        if not row['started'] or row['sessionStatus'] != 200 or not row['session'].get('authenticated'):
            raise RuntimeError('The current authenticated host control was not available')
        account_ids.add(row['session']['accountId'])
        ownership = row['ownership'] or {}
        capacity = ownership.get('capacity') or {}
        if not {'nodeId', 'online', 'acceptNewAccounts', 'measurementValid', 'capacityRef', 'readinessRef'} <= set(capacity):
            errors.append('Required six-field capacity contract absent or extended with fabricated capacity')
        if capacity.get('nodeId') != 'test-physical-node':
            errors.append('Physical capacity identity is not the protected configured node')
        else:
            keys.add(capacity['nodeId'])
        if capacity.get('online') is not True or capacity.get('acceptNewAccounts') is not row['acceptNewAccounts']:
            errors.append('Actual local availability and operator policy were conflated')
        if capacity.get('measurementValid') is not False:
            errors.append('No real current S2-03A evidence was promoted to a valid measurement')
        if capacity.get('capacityRef') is not None or capacity.get('readinessRef') is not None:
            errors.append('Missing/unknown/stale/unavailable evidence produced a fabricated reference')
        if row['requestedReference'] == 'unavailable-reference' and row['unavailableTransportObserved'] is not True:
            raise RuntimeError('The owned stopped-host unavailability control was not observed')
    if len(keys) != 1 or len(account_ids) != 1:
        errors.append('Sequential diagnostic-instance/policy changes changed physical/self identity')
    availability = matrix.get('availability', [])
    if len(availability) != 4 or {(r['online'], r['policy']) for r in availability} != {
        (online, policy) for online in (False, True) for policy in (False, True)
    }:
        raise RuntimeError('The real host lifetime did not reach all availability/policy states')
    for row in availability:
        view = row['readback'] or {}
        if view.get('online') is not row['online'] or view.get('acceptNewAccounts') is not row['policy']:
            errors.append('Actual protected readback did not preserve independent host availability and policy')
        if view.get('measurementValid') is not False or view.get('capacityRef') is not None or view.get('readinessRef') is not None:
            errors.append('Stopped/unmeasured local service was promoted to measured readiness')
    control = values[-1]
    ids = control['existingProjectIds']
    if len(ids) != 2 or len(set(ids)) != 2 or set(control['registeredRunnerIds']) != set(ids):
        raise RuntimeError('The two real logical Runner registrations were not populated/read back')
    projects = json.loads(control['projectsBody'])
    returned_ids = {v.get('projectId') for v in projects} if isinstance(projects, list) else set()
    if control['projectsStatus'] != 200 or not set(ids) <= returned_ids:
        errors.append('Existing actual own-project readback was lost under honest unknown capacity')
    if (matrix['defaultOtherRuns'], matrix['defaultCreations'], matrix['defaultPerAccount'],
        matrix['overrideOtherRuns'], matrix['overrideCreations']) != (3, 3, 1, 2, 2):
        errors.append('Existing service budget defaults or explicit override semantics changed')
    return errors


@pytest.mark.cer_assertion('A-O-44305F724FA7-1',
    'A-O-44305F724FA7-2',
    'A-O-44305F724FA7-3')
def test_o_44305f724fa7(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'capacity-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_44305F724FA7',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    matrix = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_44305F724FA7', 'S206_CAPACITY_MATRIX:')
    errors = _capacity_violations(matrix)
    if errors:
        print('FAILURE_ID:FAILURE-O-44305F724FA7')
    assert not errors, errors


@pytest.mark.cer_assertion('A-O-9BF16D4EDE9E-1',
    'A-O-9BF16D4EDE9E-2',
    'A-O-9BF16D4EDE9E-3')
def test_o_9bf16d4ede9e(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'capacity-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_9BF16D4EDE9E',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    matrix = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_9BF16D4EDE9E', 'S206_CAPACITY_MATRIX:')
    errors = _capacity_violations(matrix)
    if errors:
        print('FAILURE_ID:FAILURE-O-9BF16D4EDE9E')
    assert not errors, errors


@pytest.mark.cer_assertion('S206_CAPACITY_ABSENT_MEASUREMENT_FALSE_NULL_REFS',
    'S206_CAPACITY_ALL_SIX_FIELDS_PRESENT',
    'S206_CAPACITY_ONLINE_POLICY_INDEPENDENT_OF_READINESS',
    'S206_CAPACITY_PHYSICAL_NODE_COUNT_ONCE')
def test_o_a960be607452(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'capacity-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_A960BE607452',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    matrix = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_A960BE607452', 'S206_CAPACITY_MATRIX:')
    errors = _capacity_violations(matrix)
    if errors:
        print('FAILURE_ID:S206_CAPACITY_CONTRACT_INCOMPLETE_OR_MULTIPLIED')
    assert not errors, errors


@pytest.mark.cer_assertion('A-O-C740CE8BB7BA-BOTH-REFERENCES-NULL',
    'A-O-C740CE8BB7BA-EXISTING-VALID-USE-CONTROL',
    'A-O-C740CE8BB7BA-INVALID-STALE-MEASUREMENT-INVALID',
    'A-O-C740CE8BB7BA-MISSING-MEASUREMENT-INVALID',
    'A-O-C740CE8BB7BA-NO-INVENTED-NUMERIC-CAPACITY',
    'A-O-C740CE8BB7BA-NO-SYNTHETIC-REFERENCE-SUCCESS',
    'A-O-C740CE8BB7BA-UNAVAILABLE-MEASUREMENT-INVALID')
def test_o_c740ce8bb7ba(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'capacity-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_C740CE8BB7BA',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    matrix = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_C740CE8BB7BA', 'S206_CAPACITY_MATRIX:')
    errors = _capacity_violations(matrix)
    if errors:
        print('FAILURE_ID:FAILURE_O_C740CE8BB7BA')
    assert not errors, errors


@pytest.mark.cer_assertion('A-O-D15470FAB535-1',
    'A-O-D15470FAB535-2',
    'A-O-D15470FAB535-3')
def test_o_d15470fab535(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'capacity-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_D15470FAB535',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    matrix = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_D15470FAB535', 'S206_CAPACITY_MATRIX:')
    errors = _capacity_violations(matrix)
    if errors:
        print('FAILURE_ID:FAILURE-O-D15470FAB535')
    assert not errors, errors


@pytest.mark.cer_assertion('A-O-D8D207360833-BOTH-REFS-NULL',
    'A-O-D8D207360833-BUDGETS-UNCHANGED',
    'A-O-D8D207360833-EXISTING-VALID-PROJECT-USE-RETAINED',
    'A-O-D8D207360833-INVALID-MEASUREMENT-FALSE',
    'A-O-D8D207360833-NO-FABRICATED-NUMERIC-OR-PLACEMENT-CLAIM',
    'A-O-D8D207360833-UNPROVED-NEW-PLACEMENT-DENIED')
def test_o_d8d207360833(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'capacity-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_D8D207360833',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    matrix = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_D8D207360833', 'S206_CAPACITY_MATRIX:')
    errors = _capacity_violations(matrix)
    if errors:
        print('FAILURE_ID:FAILURE_O_D8D207360833')
    assert not errors, errors


@pytest.mark.cer_assertion('A-O-5044D91BC32C-1',
    'A-O-5044D91BC32C-2',
    'A-O-5044D91BC32C-3')
def test_o_5044d91bc32c(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'persistence-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_5044D91BC32C',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    value = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_5044D91BC32C', 'S206_AUTHORITY:')
    errors = authority_violations(value)
    if errors:
        print('FAILURE_ID:FAILURE-O-5044D91BC32C')
    assert not errors, errors


@pytest.mark.cer_assertion('A-O-A18D7D0A4419-1',
    'A-O-A18D7D0A4419-2',
    'A-O-A18D7D0A4419-3')
def test_o_a18d7d0a4419(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'persistence-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_A18D7D0A4419',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    value = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_A18D7D0A4419', 'S206_AUTHORITY:')
    errors = authority_violations(value)
    if errors:
        print('FAILURE_ID:FAILURE-O-A18D7D0A4419')
    assert not errors, errors
