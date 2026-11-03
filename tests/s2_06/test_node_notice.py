"""ADR-0061 AD14/17/25: inspect genuine protected notice operations, not presence."""
from pathlib import Path
import subprocess
import pytest
from trx_support import read_observations

pytest_plugins = ['trx_support']


@pytest.mark.cer_assertion('A-O-EDDBA9629B7A-1', 'A-O-EDDBA9629B7A-2',
                           'A-O-EDDBA9629B7A-3', 'A-O-EDDBA9629B7A-4', 'A-O-EDDBA9629B7A-5')
def test_o_eddba9629b7a(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-scope-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_EDDBA9629B7A',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    observed = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_EDDBA9629B7A', 'S206_NOTICE_SCOPE:')
    rows = observed['rows']
    expected = {'valid-pair', 'no-context', 'forged-context', 'forged-admin', 'revoked',
                'foreign-home', 'missing-home', 'foreign-local', 'stale-projection'}
    if {r['mode'] for r in rows} != expected:
        raise RuntimeError('Actual protected notice scope matrix incomplete')
    errors = []
    for row in rows:
        if not row['available']:
            errors.append((row['mode'], 'Actual protected local notification operations unavailable'))
            continue
        if row['ordinaryEscapes'] or row['publicConstruction'] or not row['publishDenied']:
            errors.append((row['mode'], 'Ordinary caller acquired privileged notice capability'))
        if row['postAttack'] != row['final'] or not row['privateContentUnchanged']:
            errors.append((row['mode'], 'Notice operation changed protected or private unrelated data'))
        if row['mode'] != 'valid-pair':
            if set(row['denials']) != {'ListAsync', 'DetailAsync', 'UnreadCountAsync', 'MarkReadAsync'}:
                errors.append((row['mode'], 'Current identity/home predicate did not deny every operation'))
            if row['after'] != row['before'] or row['final'] != row['before']:
                errors.append((row['mode'], 'Rejected operation mutated notice state'))
            continue
        ops = row['operations']
        if row['denials'] or set(ops) != {'ListAsync', 'DetailAsync', 'UnreadCountAsync', 'MarkReadAsync'}:
            errors.append('Valid current account cannot perform actual notice operations')
            continue
        if {r['NoticeId'] for r in ops['ListAsync']} != {'account-notice', 'all-notice'}:
            errors.append('Valid account audience list incorrect')
        if ops['DetailAsync']['NoticeId'] != 'account-notice' or ops['DetailAsync']['Revision'] != 1:
            errors.append('Detail not bound to actual current notice/revision')
        if ops['UnreadCountAsync'] != 2 or ops['MarkReadAsync'] is not True:
            errors.append('Valid actual count/read operation failed')
        if {r['NoticeId'] for r in row['otherList']} != {'all-notice'} or row['otherRead'] or row['otherDetail']:
            errors.append('Cross-account audience or read state disclosed/mutated')
        before, after = row['before'], row['after']
        if before['notice_read_state'] or after['notice_read_state'] != [[row['expectedAccount'], 'account-notice', 1, 1]]:
            errors.append('Mark-read did not create exactly the authenticated account/current revision key')
        if any(before[k] != after[k] for k in ('notice_facts', 'node_notice_projections')) or row['final'] != after:
            errors.append('Read operation changed central/projection/other-account state')
    if errors:
        print('FAILURE_ID:FAILURE-O-EDDBA9629B7A')
    assert not errors, errors


@pytest.mark.cer_assertion('S206_AC09_INDEPENDENT_REOPEN_QUERY', 'S206_AC09_INTERRUPTED_COMPLETE_OLD_OR_NEW', 'S206_AC09_INTERRUPT_ACTUAL_UPDATE', 'S206_AC09_NO_MIXED_FIELDS', 'S206_AC09_VALID_RETRY_COMPLETE_NEW')
def test_o_38765c481069(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-integration-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_38765C481069',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_38765C481069', 'S206_NOTICE_INTEGRATION:')
    try:
        assert v['interrupted'], 'Actual late projection failure was not reached after fact write'
        assert v['after'] == v['before'], 'Interrupted publication exposed mixed or partial state'
        assert v['reopened']['Revision'] == 1 and v['reopened']['Body'] == 'old body'
        assert v['reopened']['ChangeRef'] == 'change-1'
        assert v['retry']['Revision'] == 2 and v['retry']['Body'] == 'new body'
        assert v['retry']['ChangeRef'] == 'change-2' and v['retry']['ChangeRevision'] == 2
        assert v['final']['notice_facts'][0][1] == 2
        assert v['final']['node_notice_projections'][0][2:5] == [2, 2, 'change-2']
    except AssertionError:
        print('FAILURE_ID:S206_38765C481069')
        raise


@pytest.mark.cer_assertion('S206_AUDIENCE_INELIGIBLE_STILL_EXCLUDED', 'S206_AUDIENCE_NEW_ALL_MEMBER', 'S206_AUDIENCE_NEW_NODE_MEMBER', 'S206_AUDIENCE_NO_REPUBLISH', 'S206_AUDIENCE_PUBLICATION_PRECEDES_ACTIVATION')
def test_o_af6f5c359b10(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-integration-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_AF6F5C359B10',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_AF6F5C359B10', 'S206_NOTICE_INTEGRATION:')
    try:
        assert v['disabledDenied'] and v['wrongHomeDenied']
        assert {r['NoticeId'] for r in v['first']} == {'all-existing', 'node-existing', 'private-a'}
        assert {r['NoticeId'] for r in v['activated']} == {'all-existing', 'node-existing'}
        assert all(r['Revision'] == 1 for r in v['activated'])
        assert v['before'] == v['after'], 'Activation/listing republished or mutated notice state'
    except AssertionError:
        print('FAILURE_ID:S206_AF6F5C359B10')
        raise


@pytest.mark.cer_assertion('S206_EXPIRY_NOT_EXTENDED', 'S206_EXPIRY_PENDING_COUNT_EXCLUDED', 'S206_EXPIRY_PENDING_LIST_DETAIL_EXCLUDED', 'S206_EXPIRY_PENDING_READ_NO_MUTATION', 'S206_EXPIRY_PRE_TRANSITION_CONTROL', 'S206_EXPIRY_VALID_NOTICE_REMAINS')
def test_o_f1a2e019e2fe(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-integration-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_F1A2E019E2FE',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_F1A2E019E2FE', 'S206_NOTICE_INTEGRATION:')
    try:
        assert {r['NoticeId'] for r in v['initial']} == {'expiring', 'still-valid'}
        assert v['initialDetail']['NoticeId'] == 'expiring' and v['initialCount'] == 2
        assert {r['NoticeId'] for r in v['listed']} == {'still-valid'}
        assert v['expiredDetail'] is None and v['count'] == 1 and not v['expiredRead']
        assert v['afterExpired'] == v['before'], 'Expiry extended validity or mutated read-state/projection'
        assert v['validDetail']['NoticeId'] == 'still-valid' and v['validRead']
    except AssertionError:
        print('FAILURE_ID:S206_F1A2E019E2FE')
        raise


def _assert_current_notice_refusals(v):
    expected = {'no-context', 'forged-context', 'forged-admin', 'revoked', 'foreign-home',
                'missing-home', 'foreign-local', 'stale-projection'}
    assert {r['mode'] for r in v['authority']} == expected
    for r in v['authority']:
        assert r['available']
        assert set(r['denials']) == {'ListAsync', 'DetailAsync', 'UnreadCountAsync', 'MarkReadAsync'}
        assert r['after'] == r['before'] and r['final'] == r['before']
        assert r['postAttack'] == r['final'] and r['publishDenied']
        assert not r['ordinaryEscapes'] and not r['publicConstruction']
        assert r['privateContentUnchanged']
    assert v['privateContentUnchanged']


def _assert_notice_lists(v):
    wanted = {v['expectedAccount']: {'all', 'node', 'only-a'},
              v['otherAccount']: {'all', 'node', 'only-b'}}
    assert {r['account'] for r in v['accountObservations']} == set(wanted)
    for row in v['accountObservations']:
        assert {n['NoticeId'] for n in row['list']} == wanted[row['account']]
        assert len(row['list']) == 3 and row['count'] == 3
        assert all(n['Revision'] == 1 and not n['Read'] for n in row['list'])
    assert v['afterQuery'] == v['baseline']


def _assert_notice_details(v):
    wanted = {v['expectedAccount']: {'all', 'node', 'only-a'},
              v['otherAccount']: {'all', 'node', 'only-b'}}
    bodies = {'all': 'all body', 'node': 'node body', 'only-a': 'private A', 'only-b': 'private B'}
    for row in v['accountObservations']:
        assert set(row['details']) == {'all', 'node', 'only-a', 'only-b', 'other-node', 'future', 'expired', 'unknown'}
        for key, detail in row['details'].items():
            if key in wanted[row['account']]:
                assert detail['NoticeId'] == key and detail['Revision'] == 1
                assert detail['Body'] == bodies[key] and not detail['Read']
            else:
                assert detail is None
    assert v['afterQuery'] == v['baseline']


def _assert_notice_read_keys(v):
    assert v['ownRead'] and v['repeatRead'] and not v['foreignRead'] and not v['staleRead'] and not v['unknownRead']
    assert not v['baseline']['notice_read_state']
    assert v['afterRead']['notice_read_state'] == [[v['expectedAccount'], 'only-a', 1, 1]]
    for table in ('notice_facts', 'node_notice_projections'):
        assert v['afterRead'][table] == v['baseline'][table]
    assert v['newRevision']['Revision'] == 2 and v['newRevision']['Body'] == 'private A revised'
    assert not v['newRevision']['Read'] and v['newRead']
    assert v['afterNewRead']['notice_read_state'] == [
        [v['expectedAccount'], 'only-a', 1, 1], [v['expectedAccount'], 'only-a', 2, 1]]
    for row in v['withdrawal']:
        assert row['detail'] is None and not row['read']
        assert 'all' not in {n['NoticeId'] for n in row['list']}
        assert row['count'] == (1 if row['account'] == v['expectedAccount'] else 2)
    assert v['final']['notice_read_state'] == v['afterNewRead']['notice_read_state']


def _assert_notice_projection(v):
    for state in (v['baseline'], v['final']):
        facts = {row[0]: row for row in state['notice_facts']}
        assert len(state['node_notice_projections']) == len(facts) == 7
        for row in state['node_notice_projections']:
            fact = facts[row[1]]
            assert row[0] == v['nodeId']
            assert row[2:5] == [fact[1], fact[8], fact[9]]
            assert row[5] == int(bool(fact[7]) and fact[0] != 'other-node')
    final = {r[0]: r for r in v['final']['notice_facts']}
    assert final['only-a'][1] == 2 and final['only-a'][8:10] == [2, 'a-ref-2']
    assert final['all'][7] == 0 and final['all'][8:10] == [2, 'all-withdrawn']


@pytest.mark.cer_assertion('S206_DETAIL_ALL_NODE_ACCOUNT_AUDIENCE', 'S206_DETAIL_CURRENT_ENABLED', 'S206_DETAIL_ELIGIBLE_CONTROL', 'S206_DETAIL_HOME_LOCAL_NODE', 'S206_DETAIL_PENDING_EXPIRY_NO_BODY', 'S206_DETAIL_VALIDITY_WINDOW')
def test_o_04de2124065a(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-integration-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_04DE2124065A',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_04DE2124065A', 'S206_NOTICE_INTEGRATION:')
    try:
        _assert_current_notice_refusals(v)
        _assert_notice_details(v)
    except AssertionError:
        print('FAILURE_ID:S206_04DE2124065A')
        raise


@pytest.mark.cer_assertion('S206_LIST_AUDIENCE_FILTER', 'S206_LIST_CURRENT_ENABLED', 'S206_LIST_CURRENT_HOME_NODE', 'S206_LIST_ELIGIBLE_SET_CONTROL', 'S206_LIST_NO_EXCLUDED_METADATA', 'S206_LIST_PENDING_EXPIRY_EXCLUDED', 'S206_LIST_VALIDITY_FILTER')
def test_o_a59c66ea9d03(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-integration-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_A59C66EA9D03',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_A59C66EA9D03', 'S206_NOTICE_INTEGRATION:')
    try:
        _assert_current_notice_refusals(v)
        _assert_notice_lists(v)
    except AssertionError:
        print('FAILURE_ID:S206_A59C66EA9D03')
        raise


@pytest.mark.cer_assertion('S206_AC09_ACCOUNT_NOTICE_REVISION_KEY', 'S206_AC09_CENTRAL_ONLY_POSITIVE_NEGATIVE', 'S206_AC09_COUNT_FULL_PREDICATES', 'S206_AC09_DETAIL_FULL_PREDICATES', 'S206_AC09_LIST_FULL_PREDICATES', 'S206_AC09_NEW_REVISION_UNREAD', 'S206_AC09_READ_FULL_PREDICATES')
def test_o_4820f52ca2ad(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-integration-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_4820F52CA2AD',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_4820F52CA2AD', 'S206_NOTICE_INTEGRATION:')
    try:
        _assert_current_notice_refusals(v)
        _assert_notice_lists(v)
        _assert_notice_details(v)
        _assert_notice_read_keys(v)
    except AssertionError:
        print('FAILURE_ID:S206_4820F52CA2AD')
        raise


@pytest.mark.cer_assertion('S206_AC09_CENTRAL_PUBLISH_OBSERVED', 'S206_AC09_CURRENT_REVISION_READ_TRANSITION', 'S206_AC09_DERIVED_PROJECTION_OBSERVED', 'S206_AC09_ELIGIBLE_QUERY', 'S206_AC09_INELIGIBLE_QUERY', 'S206_AC09_STAGES_NOT_SEEDED')
def test_o_980f4ff195ac(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-integration-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_980F4FF195AC',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_980F4FF195AC', 'S206_NOTICE_INTEGRATION:')
    try:
        _assert_current_notice_refusals(v)
        _assert_notice_projection(v)
        _assert_notice_lists(v)
        _assert_notice_read_keys(v)
    except AssertionError:
        print('FAILURE_ID:S206_980F4FF195AC')
        raise


@pytest.mark.cer_assertion('S206_PROJECTION_ALL_SOURCE_REFS_STATUS', 'S206_PROJECTION_CURRENT_REVISION_BINDING', 'S206_PROJECTION_MATCHING_NODE_FACT', 'S206_PROJECTION_NO_PUBLISH_PERMISSION_ESCAPE', 'S206_PROJECTION_TRUSTED_CONTROL', 'S206_PROJECTION_UNAUTHORIZED_SOURCE_DENIED')
def test_o_f3b019b69748(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-integration-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_F3B019B69748',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_F3B019B69748', 'S206_NOTICE_INTEGRATION:')
    try:
        _assert_current_notice_refusals(v)
        _assert_notice_projection(v)
        _assert_notice_read_keys(v)
    except AssertionError:
        print('FAILURE_ID:S206_F3B019B69748')
        raise


def _assert_notice_forgery(v):
    assert {(r['actor'], r['operation']) for r in v['attempted']} == {
        (a, o) for a in ('project', 'port', 'forged-admin') for o in ('insert', 'replace')}
    assert all(r['denied'] and r['stateUnchanged'] for r in v['attempted'])
    assert {r['name'] for r in v['constructors']} == {'NodeNoticeReader', 'CentralNoticePublisher'}
    assert all(r['refused'] and not r['publicConstructors'] for r in v['constructors'])
    assert not v['projectEscape'] and v['after'] == v['before']
    assert v['selectedReaderUnchanged'] and v['selectedPublisherUnchanged']
    assert v['positive']['NoticeId'] == 'protected' and v['positive']['Body'] == 'protected body'
    assert v['missingIngestStatus'] == 404 and v['endpointContacts'] == 0
    assert v['routes'], 'Actual composed endpoint graph was not observed'
    assert not any('/notices/ingest' in r or '/notifications/ingest' in r for r in v['routes'])


@pytest.mark.cer_assertion('S206_FORGED_NODE_CENTRAL_WRITE_DENIED', 'S206_FORGED_NODE_NO_CAPABILITY_ESCAPE', 'S206_FORGED_NODE_PROJECTION_REPLACE_DENIED', 'S206_FORGED_NODE_PROTECTED_ROWS_IDENTICAL', 'S206_FORGED_NODE_TRUSTED_CONTROL')
def test_o_39aacbd7edd7(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-forgery-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_39AACBD7EDD7',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_39AACBD7EDD7', 'S206_NOTICE_FORGERY:')
    try:
        _assert_notice_forgery(v)
    except AssertionError:
        print('FAILURE_ID:S206_39AACBD7EDD7')
        raise


@pytest.mark.cer_assertion('S206_ADAPTER_LOCAL_CONTROL', 'S206_ADAPTER_NO_ENDPOINT_PROXY', 'S206_ADAPTER_NO_PUBLIC_INGEST', 'S206_ADAPTER_NO_REMOTE_CREDENTIAL', 'S206_ADAPTER_PROJECT_SELECTOR_NO_EFFECT', 'S206_ADAPTER_PROTECTED_SELECTION')
def test_o_444fae230351(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-forgery-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_444FAE230351',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_444FAE230351', 'S206_NOTICE_FORGERY:')
    try:
        _assert_notice_forgery(v)
    except AssertionError:
        print('FAILURE_ID:S206_444FAE230351')
        raise


@pytest.mark.cer_assertion('S206_AC09_BODY_INERT_DATA', 'S206_AC09_INELIGIBLE_BODY_DENIED', 'S206_AC09_NO_AUTHORITY_PROJECT_EFFECT', 'S206_AC09_NO_COMMAND_AGENT_INSTALL', 'S206_AC09_ONLY_AUTHORIZED_READ_TRANSITION', 'S206_AC09_RECORD_OUTPUT_LOG_NO_SECRET')
def test_o_863894e117b8(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-body-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_863894E117B8',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_863894E117B8', 'S206_NOTICE_BODY:')
    try:
        assert v['bodyReturnedUnchanged'] and v['listBodyReturnedUnchanged'] and v['count'] == 1
        assert v['markerAbsent'] and v['observerWorks'] and v['before'] == v['after']
        assert v['privateContentUnchanged'] and not v['foreignBodyReturned'] and not v['foreignRead']
        assert v['stateBeforeReads'] == v['afterQueries'] and v['read']
        assert v['final']['notice_read_state'] == [[v['expectedAccount'], 'inert', 1, 1]]
        for key in ('notice_facts', 'node_notice_projections'):
            assert v['final'][key] == v['stateBeforeReads'][key]
        assert v['logChannelObserved'] and v['recordMatches'] == 0 and v['logMatches'] == 0
    except AssertionError:
        print('FAILURE_ID:S206_863894E117B8')
        raise


def _assert_notice_atomic(v):
    assert v['interrupted'] and v['before'] == v['after']
    assert v['reopened']['Revision'] == 1 and v['reopened']['Body'] == 'old body'
    assert v['retry']['Revision'] == 2 and v['retry']['Body'] == 'new body'
    assert v['retry']['ChangeRef'] == 'change-2' and v['retry']['ChangeRevision'] == 2
    assert v['final']['notice_facts'][0][1] == 2
    assert v['final']['node_notice_projections'][0][2:5] == [2, 2, 'change-2']


def _assert_complete_notice_fixture(v):
    matrix = v['matrix']
    _assert_current_notice_refusals(matrix)
    _assert_notice_lists(matrix)
    _assert_notice_details(matrix)
    _assert_notice_read_keys(matrix)
    _assert_notice_projection(matrix)
    member = v['membership']
    assert member['disabledDenied'] and member['wrongHomeDenied']
    assert {r['NoticeId'] for r in member['activated']} == {'all-existing', 'node-existing'}
    assert {r['NoticeId'] for r in member['first']} == {'all-existing', 'node-existing', 'private-a'}
    assert member['before'] == member['after']
    assert all(r['Revision'] == 1 for r in member['activated'])
    expiry = v['expiry']
    assert {r['NoticeId'] for r in expiry['initial']} == {'expiring', 'still-valid'}
    assert expiry['initialDetail']['NoticeId'] == 'expiring' and expiry['initialCount'] == 2
    assert {r['NoticeId'] for r in expiry['listed']} == {'still-valid'}
    assert expiry['expiredDetail'] is None and expiry['count'] == 1 and not expiry['expiredRead']
    assert expiry['before'] == expiry['afterExpired']
    assert expiry['validDetail']['NoticeId'] == 'still-valid' and expiry['validRead']
    _assert_notice_forgery(v['forgery'])


@pytest.mark.cer_assertion('S206_AC09_FIXTURE_ELIGIBLE', 'S206_AC09_FIXTURE_EXPIRY_TRANSITION', 'S206_AC09_FIXTURE_INELIGIBLE', 'S206_AC09_FIXTURE_NEWLY_ACTIVATED', 'S206_AC09_FIXTURE_PORT_FORGERY', 'S206_AC09_FIXTURE_PROJECT_FORGERY', 'S206_AC09_FIXTURE_REVISION_TRANSITION')
def test_o_bc2947090115(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-contract-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_BC2947090115',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_BC2947090115', 'S206_NOTICE_FIXTURE:')
    try:
        _assert_complete_notice_fixture(v)
    except AssertionError:
        print('FAILURE_ID:S206_BC2947090115')
        raise


@pytest.mark.cer_assertion('S206_AC09_LIMIT_CROSS_HOST_UNPROVED', 'S206_AC09_LIMIT_CURRENT_EVIDENCE_BOUND', 'S206_AC09_LIMIT_FULL_PRODUCT_UNPROVED', 'S206_AC09_LIMIT_LOCAL_CONTRACT_ONLY', 'S206_AC09_LIMIT_OFFLINE_UNPROVED')
def test_o_c11143a9f8a7(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results_directory = tmp_path / 'notice-contract-trx'
    results_directory.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_C11143A9F8A7',
         '--logger', 'trx', '--results-directory', str(results_directory)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    v = read_observations(completed, results_directory,
        'PhaseA.Platform.Tests.NodeIdentity.NodeNoticeTests.O_C11143A9F8A7', 'S206_NOTICE_LIMITS:')
    try:
        import hashlib
        assert v['actual']['NoticeId'] == 'local-scope' and v['read']
        assert v['databases'] == ['main'] and v['expectedFile'] and v['sameProcessHost']
        assert v['scope'] == 'single_node_test' and v['processId'] > 0 and v['runtimeOs']
        assert v['productionAssemblySha256'] == hashlib.sha256((root / 'PhaseA.Platform.Tests/bin/Debug/net8.0/PhaseA.Platform.dll').read_bytes()).hexdigest()
        assert set(v['unproved']) == {'cross-host-transport', 'offline-recovery', 'full-notification-product', 'native-Windows-isolation'}
        assert not v['nativeWindowsEvidence']
    except AssertionError:
        print('FAILURE_ID:S206_C11143A9F8A7')
        raise
