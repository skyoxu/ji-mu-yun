"""ADR-0061 AD24: real composed approved-source effects and raw .NET evidence."""
from pathlib import Path
import subprocess
import hashlib
import pytest
from trx_support import read_observations

pytest_plugins = ['trx_support']


def _check_real_fixture(v):
    if len(v['identities']) != 2 or len(set(v['identities'])) != 2 or v['owned'] != [True, True]:
        print('FAILURE_ID:S206_AC08_TWO_ACCOUNT_FIXTURE_INCOMPLETE')
        raise RuntimeError('Required two real authenticated accounts/projects are not available')
    assert len(v['approvedHash']) == 64 and len(v['approvalHash']) == 64


def _check_reads(v):
    assert v['available'], 'Actual approved local source capability unavailable'
    assert v['reference']['SourceId'] == 'rpg'
    assert v['reference']['Version']
    assert v['reference']['ContentHash'] == v['approvedHash']
    assert v['reference']['ApprovalRef'] == v['approvalHash']
    assert {r['account'] for r in v['cases']} == set(v['identities']) and len(v['cases']) == 2
    for row in v['cases']:
        assert row['privateAsSourceDenied'], 'Private project was accepted as approved source'
        assert row['read']['Reference'] == v['reference']
        assert row['read']['ContentHash'] == v['approvedHash']
        assert hashlib.sha256(row['read']['Content'].encode('utf-8')).hexdigest() == v['approvedHash']
    assert v['approvalUnchanged'], 'Project operation changed protected catalog approval'


@pytest.mark.cer_assertion('S206_GLOBAL_QUERY_NEW_VERSION_COPY_INDEPENDENT', 'S206_GLOBAL_UPDATE_EDITED_COPY_BYTES_INTACT', 'S206_GLOBAL_UPDATE_NO_AUTOMATIC_USER_EDIT_REPLACEMENT')
def test_global_update_preserves_edited_copy(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'approved-source-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.ApprovedSourceTests.GlobalVersionChangesNeverOverwriteUserEditedCopies',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.ApprovedSourceTests.GlobalVersionChangesNeverOverwriteUserEditedCopies', 'S206_APPROVED_SOURCE:')
    _check_real_fixture(v)
    try:
        _check_reads(v)
        assert len(v['copies']) == 2
        assert all(r['initialHash'] == v['approvedHash'] for r in v['copies'])
        assert all(r['copied']['SourceRef'] == v['reference'] and r['copied']['RunId'] for r in v['copies'])
        assert v['before'] == v['after'] == [r['editedHash'] for r in v['copies']]
        assert len(set(v['before'])) == 2 and v['approvedHash'] not in v['before']
        assert v['originalUnchanged']
        assert v['newReference']['Version'] != v['reference']['Version']
        assert v['newReference']['ContentHash'] == v['updatedHash'] != v['approvedHash']
        assert v['newRead']['Content'] == v['expectedUpdated']
        assert v['newRead']['ContentHash'] == v['updatedHash']
    except AssertionError:
        print('FAILURE_ID:S206_GLOBAL_VERSION_UPDATE_OVERWROTE_PRIVATE_USER_EDITS')
        raise


@pytest.mark.cer_assertion('S206_AC08_FIXTURE_BOTH_PRIVATE_AS_SOURCE_DENIALS', 'S206_AC08_FIXTURE_BOTH_SUCCESSFUL_VERIFIED_READS', 'S206_AC08_FIXTURE_ONE_APPROVED_VERSION_TWO_ACCOUNTS', 'S206_AC08_FIXTURE_REAL_COMPLETE_CASE_RESULTS')
def test_required_two_account_fixture(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'approved-source-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.ApprovedSourceTests.Ac08FixtureHasOneApprovedVersionAndTwoRealAccounts',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.ApprovedSourceTests.Ac08FixtureHasOneApprovedVersionAndTwoRealAccounts', 'S206_APPROVED_SOURCE:')
    _check_real_fixture(v)
    try:
        _check_reads(v)
    except AssertionError:
        print('FAILURE_ID:S206_AC08_REQUIRED_FIXTURE_BUSINESS_RESULTS_INCORRECT')
        raise


@pytest.mark.cer_assertion('S206_SHARED_CACHE_ALL_SOURCE_QUERY_PARAMETER_SCOPE_KEYS', 'S206_SHARED_CACHE_BOUNDED_HOST_MEMORY', 'S206_SHARED_CACHE_PROJECT_WRITES_NOT_AUTHORITY', 'S206_SHARED_CACHE_REAL_HIT_MISS_DATA_NO_COLLISION')
def test_bounded_host_owned_shared_query_cache(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'approved-source-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.ApprovedSourceTests.SharedQueryCacheUsesAllKeysAndBoundedHostOwnership',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.ApprovedSourceTests.SharedQueryCacheUsesAllKeysAndBoundedHostOwnership', 'S206_APPROVED_SOURCE:')
    _check_real_fixture(v)
    try:
        _check_reads(v)
        rows = {r['label']: r for r in v['observations']}
        assert len(rows) == len(v['observations']) and len(rows) >= 50
        values = {key: row['result'] for key, row in rows.items()}
        expected = {'parameter-first': (True, False), 'parameter-hit': (True, True),
                    'parameter-change': (False, False), 'case-sensitive': (False, False),
                    'implementation-change': (True, False), 'implementation-hit': (True, True),
                    'visibility-change': (True, False), 'visibility-hit': (True, True),
                    'project-imitation': (True, True), 'version-change': (True, False),
                    'version-hit': (True, True), 'evicted-original': (True, False),
                    'recomputed-hit': (True, True)}
        for name, (matched, hit) in expected.items():
            assert values[name]['Matched'] is matched, (name, values[name])
            assert values[name]['CacheHit'] is hit, (name, values[name])
        for row in values.values():
            assert 0 < row['EffectiveEntryBound'] < 2**31
            assert 0 <= row['ResidentEntries'] <= row['EffectiveEntryBound']
        for i in range(40):
            assert values[f'pressure-{i}']['Matched'] is False
            assert values[f'pressure-{i}']['CacheHit'] is False
        assert rows['implementation-hit']['account'] != rows['visibility-change']['account']
        assert v['currentReference']['Version'] != v['reference']['Version']
        assert v['currentReference']['ContentHash'] == v['reference']['ContentHash']
        assert v['oldDenied'] and v['badHashDenied'] and v['corruptSourceDenied']
        assert v['revokedDenied'] and v['foreignProjectDenied'] and v['protectedSourceUnchanged']
    except AssertionError:
        print('FAILURE_ID:S206_SHARED_QUERY_CACHE_KEY_BOUND_OR_HOST_AUTHORITY_BROKEN')
        raise


