"""ADR-0061 AD14: real Program object graph and actual protected effect probes."""
from pathlib import Path
import subprocess
import pytest
from trx_support import read_observations

pytest_plugins = ['trx_support']


@pytest.mark.cer_assertion(
    'A-O-840CB12CA43E-CURRENT-EXISTING-CENTRAL-VERIFIER',
    'A-O-840CB12CA43E-HASH-TRANSPORT-CONTEXT-SEMANTICS-RETAINED',
    'A-O-840CB12CA43E-INVALID-REVOKED-FORGED-LOCAL-DENIED',
    'A-O-840CB12CA43E-NO-COPIED-LOCAL-CREDENTIAL-AUTHORITY',
    'A-O-840CB12CA43E-VALID-CURRENT-CREDENTIAL-POSITIVE',
    'A-O-840CB12CA43E-VERIFIED-EXISTING-CONTEXT-DELIVERED')
def test_o_840cb12ca43e(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results = tmp_path / 'existing-verifier-trx'
    results.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_840CB12CA43E',
         '--logger', 'trx', '--results-directory', str(results)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    value = read_observations(completed, results,
        'PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_840CB12CA43E', 'S206_EXISTING_VERIFIER:')
    errors = []
    if value['sessionStatus'] != 200 or value['projectStatus'] != 200:
        raise RuntimeError('Actual authenticated Program positive controls unavailable')
    if value['session']['accountId'] != value['expectedAccount'] or value['session']['role'] != 'user':
        errors.append('Caller fields changed actual authenticated context')
    if value['expectedProject'] not in value['projectIds'] or value['otherProject'] in value['projectIds']:
        errors.append('Actual HTTP context was not delivered to the local project consumer')
    if value['freshStatus'] != 200 or value['currentCentralAccount'] != value['expectedAccount'] or not value['currentDirect']:
        errors.append('Real current central rotation/credential transport lost valid access')
    if value['restoredStatus'] != 200:
        errors.append('Real central projection refresh failed to restore valid access')
    for key in ('forgedDenied', 'roleForgeryDenied', 'unknownDenied', 'oldDirectDenied', 'oldCentralRejected',
                'staleDirectDenied', 'revokedDirectDenied', 'revokedCentralRejected', 'contentUnchanged'):
        if not value[key]:
            errors.append(('current central identity/local consumer boundary', key))
    for key in ('oldStatus', 'staleStatus', 'revokedStatus'):
        if value[key] not in {401, 403, 404, 409, 503}:
            errors.append(('invalid/stale credential retained HTTP access', key, value[key]))
    if set(value['columns']) != {'account_id', 'home_node_id', 'is_enabled', 'authority_revision'}:
        errors.append('Local projection contains copied credential or broad central authority')
    if errors:
        print('FAILURE_ID:FAILURE_O_840CB12CA43E')
    assert not errors, errors


@pytest.mark.cer_assertion(
    'S206_RESTRICTED_ALLOWED_DATA_AND_DENIED_CENTRAL_EFFECTS',
    'S206_RESTRICTED_GRAPH_REAL_OBJECT_REPLACEMENT',
    'S206_RESTRICTED_NONSECRET_EXECUTION_OPTIONS',
    'S206_RESTRICTED_NO_CONCRETE_STORE_OPTIONS_ESCAPE',
    'S206_RESTRICTED_NO_PROVIDER_SCOPE_FACTORY_ESCAPE')
def test_restricted_objects_replace_privileged_escapes(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'authority-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.RestrictedObjectsReplacePrivilegedEscapes',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    value = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.RestrictedObjectsReplacePrivilegedEscapes',
        'S206_CAPABILITY:')
    if value['source'] != 'actual_Program_HostBuilt_and_service_provider' or value['liveSessionStatus'] != 200:
        raise RuntimeError('Actual composition root/current authenticated control unavailable')
    if value['resolutionErrors']:
        raise RuntimeError('Incomplete actual production resolution: ' + repr(value['resolutionErrors']))
    if not value['resolvedConsumers'] or value['expectedProjectId'] not in value['allowedProjectIds'] or value['otherProjectIds'] or not value['accountsRetained']:
        raise RuntimeError('Real two-account permitted project-data controls failed')
    errors = []
    if value['forbidden']:
        errors.append('Actual production instances retain privileged store/options/SQL/provider objects: ' + repr(value['forbidden']))
    if value['exposedSecrets']:
        errors.append('Actual injected options expose synthetic protected credential/configuration')
    if any(row['centralWriteSucceeded'] for row in value['centralMutationAttempts']):
        errors.append('Actual consumer-held object mutated central account state')
    if errors:
        print('FAILURE_ID:S206_PRODUCTION_CONSUMER_RETAINS_PRIVILEGED_ESCAPE')
    assert not errors, errors


@pytest.mark.cer_assertion('A-O-71CCE9337ECA-1', 'A-O-71CCE9337ECA-2',
    'A-O-71CCE9337ECA-3', 'A-O-71CCE9337ECA-4')
def test_o_71cce9337eca(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'current-access-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_71CCE9337ECA',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    value = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_71CCE9337ECA', 'S206_CURRENT_ACCESS:')
    expected = {'forged-context', 'missing-home', 'foreign-home', 'missing-projection',
        'foreign-project', 'foreign-local', 'stale-projection', 'revoked',
        'admin-missing-home', 'admin-foreign-home'}
    if {row['attack'] for row in value['cases']} != expected:
        raise RuntimeError('Actual authority attack observations incomplete')
    errors = []
    for row in value['cases']:
        if not all(row['positive'].values()):
            raise RuntimeError('Actual permitted resource control failed: ' + row['attack'])
        if any(row['attempted'].values()):
            errors.append((row['attack'], 'invalid authority exposed resources/ticket', row['attempted']))
        if not row['unchanged']:
            errors.append((row['attack'], 'denied read changed protected ownership or sentinel'))
        if row['attack'] != 'forged-context':
            for key in ('httpStatus', 'issueStatus', 'redeemStatus'):
                if row[key] not in {401, 403, 404, 409, 503}:
                    errors.append((row['attack'], key, row[key]))
    if errors:
        print('FAILURE_ID:FAILURE-O-71CCE9337ECA')
    assert not errors, errors


@pytest.mark.cer_assertion('A-O-AEDD71ADAEA1-1', 'A-O-AEDD71ADAEA1-2',
    'A-O-AEDD71ADAEA1-3', 'A-O-AEDD71ADAEA1-4')
def test_o_aedd71adaea1(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'one-home-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_AEDD71ADAEA1',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    value = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_AEDD71ADAEA1', 'S206_ONE_HOME:')
    import json
    ownership = json.loads(value['ownership'])
    if not all(value['positive'].values()) or not value['execution']:
        raise RuntimeError('Actual four-family positive controls failed')
    errors = []
    if not value['projectId'] or not value['workspaceId'] or not value['runId'] or not value['snapshotId']:
        raise RuntimeError('Real resource identity observations missing')
    if ownership[:4] != ['test-physical-node'] * 4 or ownership[4] != ownership[5]:
        errors.append(('protected home/project/local/projection binding', ownership))
    if value['runProject'] != value['projectId']:
        errors.append('Actual run detached from protected project')
    if any(value['foreign'].values()) or value['foreignExecution']:
        errors.append('A second authenticated account selected the first account resources/execution')
    if not value['unchanged']:
        errors.append('Cross-account attempt changed binding or private bytes')
    if errors:
        print('FAILURE_ID:FAILURE-O-AEDD71ADAEA1')
    assert not errors, errors


@pytest.mark.cer_assertion('A-O-EFCE3FE74915-1', 'A-O-EFCE3FE74915-2',
    'A-O-EFCE3FE74915-3', 'A-O-EFCE3FE74915-4')
def test_o_efce3fe74915(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'dispatch-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_EFCE3FE74915',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    value = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_EFCE3FE74915', 'S206_CURRENT_DISPATCH:')
    if {row['attack'] for row in value['cases']} != {
        'forged-context', 'missing-home', 'foreign-home', 'foreign-project', 'foreign-local', 'revoked'}:
        raise RuntimeError('Actual dispatch attack observations incomplete')
    errors = []
    for row in value['cases']:
        if not row['positive']:
            raise RuntimeError('Actual permitted queue control failed: ' + row['attack'])
        if not row['denied'] or row['started'] or not row['unchanged']:
            errors.append(row)
    if errors:
        print('FAILURE_ID:FAILURE-O-EFCE3FE74915')
    assert not errors, errors
@pytest.mark.cer_assertion('S206_BROWSER_GAME_CONTENT_CANNOT_STAMP_PROJECT_NODE',
    'S206_CONFLICTING_HOME_LOCAL_DENIES_CREATION',
    'S206_NEW_PROJECT_NODE_STAMP_PROTECTED_HOME_LOCAL',
    'S206_PROJECT_NODE_ADDITIVE_NULLABLE_INSTALL_ONLY')
def test_o_5a39371ce268(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'project-stamp-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_5A39371CE268',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=repository_root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    value = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_5A39371CE268', 'S206_PROJECT_STAMP:')
    errors = []
    if not value['nullableAtInstall']:
        errors.append('Additive installation changed the legacy nullable project node contract')
    if any(value['nodes'].get(key) != 'test-physical-node' for key in (value['projectId'], value['directId'])):
        errors.append('Actual service/direct project creation did not stamp the protected node')
    if not value['gameClaimPresent'] or value['importStatus'] != 'succeeded':
        raise RuntimeError('The real game-content/forged request/import control was not exercised')
    if not value['denied'] or value['rejectedId'] in value['nodes']:
        errors.append('Mismatched protected local node created a project instead of denying atomically')
    if errors:
        print('FAILURE_ID:S206_PROJECT_NODE_STAMP_CALLER_CONTROLLED')
    assert not errors, errors



@pytest.mark.cer_assertion(
    'A-O-BC733E999001-1',
    'A-O-BC733E999001-2',
    'A-O-BC733E999001-3',
    'A-O-BC733E999001-4',
    'A-O-BC733E999001-5')
def test_o_bc733e999001(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results = tmp_path / 's236-counterexample-trx'
    results.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_BC733E999001',
         '--logger', 'trx', '--results-directory', str(results)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    value = read_observations(completed, results,
        'PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_BC733E999001', 'S206_WRITE_COUNTEREXAMPLES:')
    errors = []
    if {row['attack'] for row in value['rows']} != {'valid', 'revoked', 'foreign-project', 'foreign-local', 'stale-projection'}:
        raise RuntimeError('Actual post-permit counterexample inventory incomplete')
    for row in value['rows']:
        if not row['positiveObserved'] or not row['admissionObserved'] or not row['wasBlocked'] or not row['projectBytesUnchanged']:
            raise RuntimeError(('Real positive/admission/lock precondition unavailable', row))
        if row['attack'] == 'valid':
            if not row['published'] or row['denied'] or not row['manifestExists'] or not row['payloadExists'] or row['stored'] != 1:
                raise RuntimeError(('Unchanged current valid write did not publish', row))
        elif row['published'] or not row['denied'] or row['manifestExists'] or row['payloadExists'] or row['stored']:
            errors.append(('Stale pre-lock authority published a protected snapshot', row))
    if {row['attack'] for row in value['bindings']} != {'valid', 'foreign-root', 'wrong-workspace', 'generation-after-admission'}:
        raise RuntimeError('Actual registered-path/generation counterexample inventory incomplete')
    for row in value['bindings']:
        if not row['positiveObserved']:
            raise RuntimeError(('Actual valid path control unavailable', row))
        if row['attack'] == 'generation-after-admission' and not row['generationChanged']:
            raise RuntimeError('Real registered generation did not change under its existing run lock')
        if row['attack'] == 'valid':
            if row['denied'] or not row['published'] or not row['manifestExists'] or not row['payloadExists']:
                raise RuntimeError(('Valid registered snapshot binding unavailable', row))
        elif not row['denied'] or row['published'] or row['manifestExists'] or row['payloadExists'] or row['leakedOtherAccount']:
            errors.append(('Protected snapshot ignored its current registered path/workspace/generation', row))
    restore_controls = value['restoreControls']
    if {(row['overload'], row['mode']) for row in restore_controls} != {
            (overload, mode) for overload in ('default-key', 'explicit-key')
            for mode in ('valid', 'detached-explicit', 'foreign-account', 'forged-admin', 'foreign-home',
                         'foreign-project', 'foreign-local', 'stale-projection', 'revoked')}:
        raise RuntimeError('Actual restore entry/lease matrix incomplete')
    for row in restore_controls:
        if not row['positiveLeaseObserved'] or not row['privateBytesUnchanged'] or row['published']:
            raise RuntimeError(('Actual lease control or inherited route refusal unavailable', row))
        if row['mode'] in ('valid', 'detached-explicit'):
            if row['restoreDenied'] or row['stored'] != 1 or not row['routeRefusalRetained']:
                errors.append(('Valid restore entry did not preserve existing route-authority refusal', row))
        elif not row['restoreDenied'] or row['stored']:
            errors.append(('Invalid current node authority created a protected restore intent', row))
        if row['mode'] == 'valid':
            if row['leaseDenied'] or not row['leaseVisible']:
                errors.append(('Current owner cannot read its actual authoritative lease', row))
        elif not row['leaseDenied'] or row['leaseVisible']:
            errors.append(('Authoritative lease lookup bypassed current caller/owner validation', row))
    deletion_controls = value['deletionControls']
    if {row['mode'] for row in deletion_controls} != {
            'valid', 'valid-historical', 'role-closed', 'revoked', 'foreign-project', 'foreign-local', 'stale-projection'}:
        raise RuntimeError('Actual protected snapshot deletion matrix incomplete')
    for row in deletion_controls:
        if not row['insideMutationLock'] or not row['admissionObserved'] or not row['privateBytesUnchanged']:
            raise RuntimeError(('Real current-verifier/mutating-lock observation unavailable', row))
        before, after = row['before'], row['after']
        if before[0] != 0 or before[2] != 0 or before[3] <= 0 or before[1] < before[3]:
            raise RuntimeError(('Actual persisted snapshot/quota precondition unavailable', row))
        if row['mode'] in ('valid', 'valid-historical'):
            if row['mode'] == 'valid-historical' and not row['generationChanged']:
                raise RuntimeError('Actual historical snapshot generation control unavailable')
            if row['denied'] or after != [1, before[1] - before[3], 3, before[3]]:
                errors.append(('Current owner cannot delete its valid historical snapshot normally', row))
        elif not row['denied'] or after != before:
            errors.append(('Stale admission changed snapshot retention/quota inside the write lock', row))
    contract_wait = value['contractWaitControls']
    if {row['mode'] for row in contract_wait} != {
            'valid', 'revoked', 'foreign-home', 'stale-projection', 'foreign-project'}:
        raise RuntimeError('Actual contract-writer lease/current-authority matrix incomplete')
    for row in contract_wait:
        if not row['waited'] or not row['earlierProjectObserved'] or not row['triggersPreserved']:
            raise RuntimeError(('Actual prior authority/project mutation wait not observed', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['fresh'] or not row['contractHashRetained'] or set(row['changed']) != {
                    'routes/prototype-contract/latest.json', 'meta/routes/prototype-contract/latest.json'}:
                errors.append(('Current contract writer failed its actual two-file refresh', row))
        elif not row['denied'] or row['fresh'] or row['changed']:
            errors.append(('Earlier project authority survived a denied mutation-lease wait', row))
    goal_publish = value['goalPublishControls']
    if {row['mode'] for row in goal_publish} != {'valid', 'revoked', 'stale-projection'}:
        raise RuntimeError('Actual goal-publication/current-authority matrix incomplete')
    for row in goal_publish:
        if not row['reachedExecutor'] or row['calls'] < 1:
            raise RuntimeError(('Actual iteration service did not reach its external executor', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['resultReturned'] or not row['resultLogPublished'] or row['sessionUnchanged']:
                errors.append(('Current owner cannot publish its actual goal result', row))
        elif not row['denied'] or row['resultReturned'] or row['changed'] or not row['sessionUnchanged'] or row['calls'] != 1:
            errors.append(('Executor completion published under stale project authority', row))
    postprocess = value['postprocessControls']
    if {(row['family'], row['mode']) for row in postprocess} != {
            (family, mode) for family in ('feedback', 'ui') for mode in ('valid', 'revoked', 'stale-projection')}:
        raise RuntimeError('Actual feedback/UI post-executor matrix incomplete')
    for row in postprocess:
        if not row['reachedExecutor'] or row['calls'] != 1:
            raise RuntimeError(('Actual consumer executor boundary not observed', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['resultReturned'] or not row['payloadMatches'] or row['runUnchanged']:
                errors.append(('Current consumer did not perform its actual permitted result/BOM operation', row))
        elif not row['denied'] or row['resultReturned'] or row['changed'] or not row['runUnchanged']:
            errors.append(('Consumer performed protected postprocessing after current authority was denied', row))
    maps = value['requirementMapControls']
    if {row['mode'] for row in maps} != {'valid', 'revoked', 'stale-projection'}:
        raise RuntimeError('Actual structured requirement-map publication matrix incomplete')
    for row in maps:
        if not row['reachedModel'] or row['calls'] != 1 or row['cacheCount']:
            raise RuntimeError(('Actual structured requirement-map model boundary unavailable', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['resultReturned'] or not row['payloadMatches'] or not {
                    'meta/routes/gdd-requirements/latest.json', 'meta/routes/gdd-requirements/prompt-evidence.json'
                    }.issubset(row['changed']):
                errors.append(('Current owner lost its actual structured requirement map/source binding', row))
        elif not row['denied'] or row['resultReturned'] or row['changed']:
            errors.append(('Model reply published requirement files after current authority was denied', row))
    if errors:
        print('FAILURE_ID:FAILURE-O-BC733E999001')
    assert not errors, errors


@pytest.mark.cer_assertion('S206_REFINEMENT_EXCLUDES_UNRELATED_FEATURES', 'S206_REFINEMENT_PRESERVES_FROZEN_TRANSACTIONS', 'S206_REFINEMENT_PRESERVES_RESTRICTED_SEAMS')
def test_o_2f129b75af64(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-contract-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_2F129B75AF64',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeAuthorityTests.O_2F129B75AF64', 'S206_NOTICE_REFINEMENT:')
    try:
        from test_node_notice import _assert_notice_atomic
        assert v['realChanges'], 'Actual changed production inventory was not observed'
        assert not v['outside'], v['outside']
        assert not v['escapes'], v['escapes']
        _assert_notice_atomic(v['atomic'])
    except AssertionError:
        print('FAILURE_ID:S206_LAYOUT_REFINEMENT_WIDENS_SCOPE')
        raise
