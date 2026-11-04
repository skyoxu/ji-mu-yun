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


def _saved_export_provenance(manifest, exports, roles, candidates):
    """ADR-0061: assess delivered text exports and current bounded source claims, never originals."""
    import hashlib
    import json
    from pathlib import PurePosixPath
    expected = {
        'S2-06-requirements.md': (7998, '5a013274f838433ef14b6a0dc612e9757692e2b8ddceac5efe91d2649cda16c7'),
        '00-shared-scope-and-contracts.md': (22503, 'd327150ab20892084d00a8f6d2e8c632b1eb372b30f929e329e14463d982e3e5'),
        '01-dependencies-and-delivery.md': (14450, '160028ba7b29c0fe5fe778806902f3bd0774fec66a183a3facabaff60b6c9cdd'),
    }
    assessed_candidates = {
        'PhaseA.Platform/README.md': '6978e2bae3f0fac6f22c9c44cc99808e4e841d31b4d2363feb55889013846cc4',
        'docs/workflows/phase-service-node-identity-and-roles.md': '56de3c8f138910b5a9b933536fe7beee9e9a920b1ebad129f0e5949638e20728',
    }
    errors, observations, claim_assessments = [], [], []
    if not isinstance(manifest, list) or len(manifest) != 3 or not isinstance(exports, dict) or len(exports.get('results', [])) != 3:
        raise RuntimeError('Complete delivered manifest and three full export results are required')
    by_name = {row['name']: row for row in exports['results']}
    if len(by_name) != 3 or set(by_name) != set(expected):
        errors.append('Saved exported-source result identities do not exactly cover the three delivered sources')
    for row in manifest:
        name = PurePosixPath(row['path']).name
        if name not in expected or name not in by_name:
            errors.append('Manifest contains an unknown or missing exported source')
            continue
        result = by_name[name]
        content = result.get('content')
        if (not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], str)
                or result.get('mode') != 'full' or result.get('has_more') is not False
                or result.get('start_line') != 1 or result.get('end_line') != result.get('total_lines')):
            raise RuntimeError('A complete unmodified saved text result is required; no trimming or reconstruction is allowed')
        raw = content[0].encode('utf-8')  # Preserve the entire text, including its actual final byte.
        size, digest = len(raw), hashlib.sha256(raw).hexdigest()
        if (size, digest) != expected[name] or row['export_size_bytes'] != size or row['export_sha256'] != digest:
            errors.append('Actual exported UTF-8 bytes differ from the frozen identity: ' + name)
        if (row['library_size_bytes'] != result['size_bytes'] or result['size_bytes'] != size + 1
                or row['library_file_id'] != result['library_file_id']
                or result['requested_file_id'] != result['library_file_id']):
            errors.append('Original metadata/export distinction or exact saved result binding was lost: ' + name)
        if row.get('route') != 'complete Library read text exported; not raw original bytes; signed materialization failed':
            errors.append('Saved producer route no longer preserves the explicit text-export/original-byte distinction: ' + name)
        observations.append({'name': name, 'export_bytes': size, 'export_sha256': digest,
            'original_metadata_bytes': result['size_bytes'], 'original_download_byte_identity': 'not established'})
    expected_roles = {row['path']: 'provenance' for row in manifest}
    expected_roles.update({
        '_bmad-output/planning-artifacts/prds/prd-s2-06-20261028/prd.md': 'provenance',
        '_bmad-output/planning-artifacts/prds/prd-s2-06-20261028/addendum.md': 'provenance'})
    if (not isinstance(roles, list) or len(roles) != 5
            or {row['path']: row['role'] for row in roles} != expected_roles):
        errors.append('The three exported-source, PRD and addendum provenance roles were not preserved exactly')
    for path, expected_hash in assessed_candidates.items():
        raw = candidates[path]
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected_hash:
            errors.append('Current candidate claim content requires a new bounded semantic assessment: ' + path)
        claim_assessments.append({'path': path, 'sha256': digest,
            'assessment': ('Application/component and scoped local-notice claims; no downloaded-original identity claim is made.'
                if path.endswith('README.md') else
                'Normative authority is the Accepted ADR/adopted spine. Export provenance does not grant authority or establish runtime completion.'),
            'assessment_applies_to_exact_bytes': digest == expected_hash})
    workflow = candidates['docs/workflows/phase-service-node-identity-and-roles.md'].decode('utf-8')
    graph = json.loads(workflow.split('```json\n', 1)[1].split('\n```', 1)[0])
    if (graph['source_authority']['adr'] != 'docs/adr/ADR-0061-phase-b-c-identity-isolation-workspace-recovery-spine.md'
            or graph['source_authority']['adopted_spine_sha256'] != 'df6549c9f72595bfd883ea8f3d557935ae0f2daf835b500803618be2ef6ef7f2'
            or graph['authorizes'] != []
            or graph['implementation_claim'] != 'Design handoff only; pending storage/capability/consumer and Windows proof remains explicit.'):
        errors.append('Actual handoff promotes provenance or design identity into extra authority/completion')
    return {'schema': 's206.export-provenance-assessment.v1', 'authorizes': [],
        'export_observations': observations, 'actual_roles': roles, 'candidate_claim_assessments': claim_assessments,
        'original_source_paths_opened': False, 'original_files_reconstructed': False, 'violations': errors}


@pytest.mark.cer_assertion('A-O-A45D4EDED200-1', 'A-O-A45D4EDED200-2',
    'A-O-A45D4EDED200-3', 'A-O-A45D4EDED200-4')
def test_o_a45d4eded200(tmp_path):
    import json
    root = Path(__file__).resolve().parents[2]
    fresh_trx_directory = tmp_path / 'provenance-trx'
    fresh_trx_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--filter',
         'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_A45D4EDED200',
         '--logger', 'trx', '--results-directory', str(fresh_trx_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True, encoding='utf-8', timeout=180)
    native = read_observations(completed, fresh_trx_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_A45D4EDED200', 'S206_SOURCE_PROVENANCE:')
    if native.get('entry') != 'PhaseAPlatformOptionsLoader.FromDictionary' or native.get('phaseServiceState') != 'test':
        raise RuntimeError('The declared existing local configuration entry was not observed')
    logs = root / 'logs/s2-06-bmad-20261028'
    assessment = _saved_export_provenance(
        json.loads((logs / 'source-manifest.json').read_bytes()),
        json.loads((logs / 'library-read-export.json').read_bytes()),
        json.loads((logs / 'spec-initial-roles.json').read_bytes()),
        {p: (root / p).read_bytes() for p in ('PhaseA.Platform/README.md', 'docs/workflows/phase-service-node-identity-and-roles.md')})
    print('S206_DERIVED_PROVENANCE:' + json.dumps(assessment, sort_keys=True))
    if assessment['violations']:
        print('FAILURE_ID:FAILURE-O-A45D4EDED200')
    assert not assessment['violations'], assessment['violations']


def _s162_scope_assessment(root, obligation, native):
    """Bounded claim assessment on actual admitted-baseline deltas and reviewed current artifacts.

    Hashes bind the stated semantic assessment to the actual text. They do not
    supply runtime proof. Unknown candidate text or production deltas require a
    fresh assessment rather than inheriting these current test-only conclusions.
    """
    import hashlib
    import json
    expected = {
        'PhaseA.Platform/README.md': '6978e2bae3f0fac6f22c9c44cc99808e4e841d31b4d2363feb55889013846cc4',
        'docs/workflows/phase-service-node-identity-and-roles.md': '56de3c8f138910b5a9b933536fe7beee9e9a920b1ebad129f0e5949638e20728',
        'docs/requirements/s2-06/vdd-input.md': 'f6e4bacdd952da675a0aeb70c94da6cb7478b0b2f7d6543b0a8b48072db90654',
        'docs/adr/ADR-0061-phase-b-c-identity-isolation-workspace-recovery-spine.md': '2792b5ae5d890120a630787e82b97299434e88252bfc3fb9b9603ce336fc986c',
    }
    artifacts = {p: (root / p).read_bytes() for p in expected}
    errors = ['Current source/claim bytes require a new semantic assessment: ' + p
              for p, digest in expected.items() if hashlib.sha256(artifacts[p]).hexdigest() != digest]
    document = artifacts['docs/workflows/phase-service-node-identity-and-roles.md'].decode('utf-8')
    graph = json.loads(document.split('```json\n', 1)[1].split('\n```', 1)[0])
    if (graph['authorizes'] or graph['unresolved_authority_contradictions']
            or graph['ordering'] != ['accepted_irreversible_authority', 'restricted_interfaces_and_storage', 'dispatch_implementation', 'runtime_validation']
            or graph['implementation_claim'] != 'Design handoff only; pending storage/capability/consumer and Windows proof remains explicit.'):
        errors.append('The actual handoff grants authority, contradicts owners or promotes planning into completion')
    if set(graph['node_owner']['denied']) != {'central_account_writer', 'credential_store', 'sql_connection_or_factory', 'unrestricted_options', 'service_locator', 'home_reassignment'}:
        errors.append('Actual restricted-node handoff broadens central authority')
    def git(*args):
        return subprocess.run(['git', '-c', 'safe.directory=' + str(root), *args], cwd=root,
            shell=False, check=True, capture_output=True, text=True, encoding='utf-8', timeout=15).stdout.splitlines()
    # 338ec4d is the explicit admitted delivery-toolchain baseline, not a new
    # product authorization. Native VDD/CI maintenance was separately authorized.
    baseline = '338ec4dafb03e619109228efe1759f430106bd2c'
    changed = sorted(set(git('diff', '--name-only', baseline, '--') +
        git('ls-files', '--others', '--exclude-standard', '--', 'PhaseA.Platform', 'PhaseA.Platform.Tests', 'tests/s2_06', 'docs/workflows')))
    test_only = lambda p: ((p.startswith('PhaseA.Platform.Tests/NodeIdentity/') and p.endswith('.cs'))
                          or (p.startswith('tests/s2_06/') and p.endswith('.py')))
    unassessed = [p for p in changed if not test_only(p)]
    if unassessed:
        errors.append('Actual non-test implementation/claim delta needs a new exclusion/authority assessment: ' + repr(unassessed))
    if (native.get('case') != obligation or native.get('phaseServiceState') != 'test'
            or type(native.get('httpsAccepted')) is not bool or type(native.get('insecurePublicUrlRejected')) is not bool):
        raise RuntimeError('Declared real configuration observations are missing or malformed')
    if not native['httpsAccepted'] or not native['insecurePublicUrlRejected']:
        errors.append('Existing public HTTPS configuration validation was not retained')
    source = 'docs/requirements/s2-06/vdd-input.md'
    families = {
        'O-3541A1914CAF': [
            ('completed 8-24 capabilities', 'Reuse/relevant regression only; this candidate adds tests, not a rebuild.'),
            ('user Git/GitHub', 'No user Git/GitHub product or gateway is added; local delivery Git operations are a separate authorized execution scope.'),
            ('patch gateways', 'No patch gateway implementation is added.'),
            ('second ledgers/validators', 'No second product ledger, approval system or validator platform is added; native evidence owners remain unchanged.'),
            ('full frontend work', 'No browser/frontend implementation delta is present.'),
            ('full telemetry work', 'No telemetry implementation delta is present.')],
        'O-57C432D34201': [(name, 'Not granted by adoption or these design/test artifacts.') for name in
            ('extra project access', 'network permission', 'cross-host execution', 'dynamic placement', 'deployment', 'live database mutation', 'release authority')],
        'O-5FB690F6AA79': [(name, 'Separate before-opening owner condition; owning implementation/opening proof is not supplied by this scope.') for name in
            ('formal password product', 'password recovery', 'minimal soft-delete', 'HTTPS before opening', 'Identity/Direct Mail implementation', 'deployment')],
        'O-B6F8A8621F40': [
            ('execution-boundary reauthorization', 'S2-05/S2-04A own this consumer release condition; actual owning runtime proof is not supplied here.'),
            ('ordinary run redaction/SLS/Sentry', 'S2-03B retains limits and owning release proof; local configuration success is insufficient.'),
            ('active-content browser/session/network isolation', 'S2-05/S2-04B retain actual isolation evidence; no opening or active-content authority is granted.')],
        'O-E0AF971772C4': [
            ('formal Identity/password recovery', 'Separate before-opening product condition. Existing token/test configuration is not formal account-product completion.')],
    }
    anchors = {'O-3541A1914CAF': 'SM-SPEC-CONTEXT', 'O-57C432D34201': 'SM-S2-AUTHORITY',
        'O-5FB690F6AA79': 'SM-VERIFICATION-CONTRACT', 'O-B6F8A8621F40': 'SM-SHARED-NOTIFICATION-CONTRACT',
        'O-E0AF971772C4': 'SM-IDENTITY-CONTRACT'}
    # This is a per-family claim/action assessment, not a runtime passed flag.
    rows = [{'family': name, 'assessment': disposition, 'source_ref': source + '#' + anchors[obligation],
             'current_action_basis': 'Actual current delta is the listed test-only changes; candidate text is bound to the reviewed bytes.',
             'owning_runtime_results_supplied': False} for name, disposition in families[obligation]]
    return {'schema': 's206.scoped-claim-assessment.v1', 'authorizes': [], 'obligation_id': obligation,
        'baseline': baseline, 'actual_changed_paths': changed, 'unassessed_non_test_paths': unassessed,
        'candidate_source_identities': {p: hashlib.sha256(raw).hexdigest() for p, raw in artifacts.items()},
        'candidate_claim_basis': {'readme': 'Existing application/component and scoped local-notice contract; no S2-06 completion or formal opening grant.',
            'workflow': graph['implementation_claim'], 'authority': graph['source_authority'], 'node_denied': graph['node_owner']['denied']},
        'family_assessments': rows, 'https_observation_is_opening_proof': False, 'violations': errors}


@pytest.mark.cer_assertion('A-O-3541A1914CAF-1', 'A-O-3541A1914CAF-2', 'A-O-3541A1914CAF-3', 'A-O-3541A1914CAF-4')
def test_o_3541a1914caf(tmp_path):
    root = Path(__file__).resolve().parents[2]
    fresh_trx_directory = tmp_path / 'scope-trx'
    fresh_trx_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--filter',
         'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_3541A1914CAF',
         '--logger', 'trx', '--results-directory', str(fresh_trx_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True, encoding='utf-8', timeout=180)
    native = read_observations(completed, fresh_trx_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_3541A1914CAF', 'S206_SCOPE_BOUNDARY:')
    assessment = _s162_scope_assessment(root, 'O-3541A1914CAF', native)
    import json
    print('S206_DERIVED_SCOPE:' + json.dumps(assessment, sort_keys=True))
    if assessment['violations']:
        print('FAILURE_ID:FAILURE-O-3541A1914CAF')
    assert not assessment['violations'], assessment['violations']


@pytest.mark.cer_assertion('A-O-57C432D34201-1', 'A-O-57C432D34201-2', 'A-O-57C432D34201-3')
def test_o_57c432d34201(tmp_path):
    root = Path(__file__).resolve().parents[2]
    fresh_trx_directory = tmp_path / 'scope-trx'
    fresh_trx_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--filter',
         'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_57C432D34201',
         '--logger', 'trx', '--results-directory', str(fresh_trx_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True, encoding='utf-8', timeout=180)
    native = read_observations(completed, fresh_trx_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_57C432D34201', 'S206_SCOPE_BOUNDARY:')
    assessment = _s162_scope_assessment(root, 'O-57C432D34201', native)
    import json
    print('S206_DERIVED_SCOPE:' + json.dumps(assessment, sort_keys=True))
    if assessment['violations']:
        print('FAILURE_ID:FAILURE-O-57C432D34201')
    assert not assessment['violations'], assessment['violations']


@pytest.mark.cer_assertion('A-O-5FB690F6AA79-1', 'A-O-5FB690F6AA79-2', 'A-O-5FB690F6AA79-3')
def test_o_5fb690f6aa79(tmp_path):
    root = Path(__file__).resolve().parents[2]
    fresh_trx_directory = tmp_path / 'scope-trx'
    fresh_trx_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--filter',
         'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_5FB690F6AA79',
         '--logger', 'trx', '--results-directory', str(fresh_trx_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True, encoding='utf-8', timeout=180)
    native = read_observations(completed, fresh_trx_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_5FB690F6AA79', 'S206_SCOPE_BOUNDARY:')
    assessment = _s162_scope_assessment(root, 'O-5FB690F6AA79', native)
    import json
    print('S206_DERIVED_SCOPE:' + json.dumps(assessment, sort_keys=True))
    if assessment['violations']:
        print('FAILURE_ID:FAILURE-O-5FB690F6AA79')
    assert not assessment['violations'], assessment['violations']


@pytest.mark.cer_assertion('A-O-B6F8A8621F40-1', 'A-O-B6F8A8621F40-2', 'A-O-B6F8A8621F40-3', 'A-O-B6F8A8621F40-4')
def test_o_b6f8a8621f40(tmp_path):
    root = Path(__file__).resolve().parents[2]
    fresh_trx_directory = tmp_path / 'scope-trx'
    fresh_trx_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--filter',
         'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_B6F8A8621F40',
         '--logger', 'trx', '--results-directory', str(fresh_trx_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True, encoding='utf-8', timeout=180)
    native = read_observations(completed, fresh_trx_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_B6F8A8621F40', 'S206_SCOPE_BOUNDARY:')
    assessment = _s162_scope_assessment(root, 'O-B6F8A8621F40', native)
    import json
    print('S206_DERIVED_SCOPE:' + json.dumps(assessment, sort_keys=True))
    if assessment['violations']:
        print('FAILURE_ID:FAILURE-O-B6F8A8621F40')
    assert not assessment['violations'], assessment['violations']


@pytest.mark.cer_assertion('A-O-E0AF971772C4-1', 'A-O-E0AF971772C4-2', 'A-O-E0AF971772C4-3')
def test_o_e0af971772c4(tmp_path):
    root = Path(__file__).resolve().parents[2]
    fresh_trx_directory = tmp_path / 'scope-trx'
    fresh_trx_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--filter',
         'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_E0AF971772C4',
         '--logger', 'trx', '--results-directory', str(fresh_trx_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True, encoding='utf-8', timeout=180)
    native = read_observations(completed, fresh_trx_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeConfigurationTests.O_E0AF971772C4', 'S206_SCOPE_BOUNDARY:')
    assessment = _s162_scope_assessment(root, 'O-E0AF971772C4', native)
    import json
    print('S206_DERIVED_SCOPE:' + json.dumps(assessment, sort_keys=True))
    if assessment['violations']:
        print('FAILURE_ID:FAILURE-O-E0AF971772C4')
    assert not assessment['violations'], assessment['violations']
