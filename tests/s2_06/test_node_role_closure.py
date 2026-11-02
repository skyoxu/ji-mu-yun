"""ADR-0061 AD19/20: actual direct, startup and timed recovery effects."""
from pathlib import Path
import subprocess
import os
import sys
import pytest
from trx_support import read_observations

pytest_plugins = ['trx_support']


@pytest.mark.cer_assertion('A-O-7486EC7571D0-1')
def test_program_detached_preview_current_authority(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results = tmp_path / 'program-boundary-trx'
    results.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeRoleClosureTests.ProgramDetachedPreviewAndRestoreAdmissionObservations',
         '--logger', 'trx', '--results-directory', str(results)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    rows = read_observations(completed, results,
        'PhaseA.Platform.Tests.NodeIdentity.NodeRoleClosureTests.ProgramDetachedPreviewAndRestoreAdmissionObservations',
        'S206_PROGRAM_BOUNDARIES:')
    if {row['mode'] for row in rows} != {'valid', 'revoked', 'stale-projection', 'foreign-home', 'foreign-project'}:
        raise RuntimeError('Actual Program callback matrix incomplete')
    errors = []
    for row in rows:
        if not row['httpAccepted'] or not row['queueWaitObserved'] or not row['callbackObserved']:
            raise RuntimeError(('Actual Program detached queue boundary unavailable', row))
        if row['restoreInitialStatus'] != 409 or row['restoreInitialCode'] != 'package_snapshot_unavailable':
            raise RuntimeError(('Actual non-versioned restore positive gate unavailable', row))
        if row['mode'] == 'valid':
            if not row['started'] or not row['finished']:
                errors.append(('Current authorized Program callback failed to start/finish its actual service run', row))
        elif row['started'] or row['changed'] or row['restoreAfterStatus'] < 400:
            errors.append(('Program detached callback or restore admission bypassed current ownership', row))
    if errors:
        print('FAILURE_ID:FAILURE-O-7486EC7571D0')
    assert not errors, errors


@pytest.mark.cer_assertion(
    'S206_AUTHORIZED_EXISTING_RECOVERY_BEHAVIOR_RETAINED',
    'S206_ENTRY_ONLY_NO_SEED_RECOVERY_SUCCESS_PROMOTION',
    'S206_GUARD_DENIAL_NO_DESTRUCTIVE_FAILURE_COMPENSATION',
    'S206_INITIALIZATION_ALL_PUBLIC_ENTRYPOINTS_ROLE_NODE_GUARDED',
    'S206_PROGRAM_STARTUP_AND_PREHEAT_ROLE_NODE_GUARDED',
    'S206_RECOVERY_HOSTED_LOOP_ROLE_NODE_GUARDED',
    'S206_WORKSPACE_MAINTENANCE_ROLE_NODE_GUARDED')
def test_o_f3517d4eef1b(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results = tmp_path / 'recovery-trx'
    results.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeRoleClosureTests.O_F3517D4EEF1B',
         '--logger', 'trx', '--results-directory', str(results)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    value = read_observations(completed, results,
        'PhaseA.Platform.Tests.NodeIdentity.NodeRoleClosureTests.O_F3517D4EEF1B', 'S206_RECOVERY:')
    direct = {row['mode']: row for row in value['direct']}
    hosted = {row['mode']: row for row in value['hosted']}
    if set(direct) != {'valid', 'entry-only', 'no-context', 'forged-context', 'missing-home',
                       'foreign-project', 'foreign-local', 'revoked'} or set(hosted) != {
                           'valid', 'entry-only', 'foreign-project', 'missing-home'}:
        raise RuntimeError('Actual recovery matrix incomplete')
    if not direct['valid']['seeded'] or not direct['valid']['observed'] or not direct['valid']['bootstrapSucceeded']:
        raise RuntimeError('Actual direct seeding/completed-bootstrap positive control unavailable')
    errors = []
    for mode, row in direct.items():
        if not row['observed']:
            raise RuntimeError('Detached public initialization path was not observed: ' + mode)
        if not row['projectRetained'] or not row['unchanged']:
            errors.append((mode, 'guard denial destroyed or altered protected project'))
        if mode != 'valid' and (row['seeded'] or row['bootstrapSucceeded']):
            errors.append((mode, 'direct entry produced an unauthorized seed/bootstrap effect'))
        if not all(row['reconcilesDenied']) or not row['maintenanceDenied']:
            errors.append((mode, 'ordinary caller acquired global recovery scan'))
    for mode, row in hosted.items():
        if not row['unchanged'] or not row['firstProjectRetained']:
            errors.append((mode, 'startup changed protected ownership or deleted project'))
        if mode == 'valid':
            if not row['started'] or not row['startupSeed'] or not row['timerObserved'] or not row['timerSeed'] or not row['preheatObserved']:
                errors.append((mode, 'actual Program startup/hosted timer failed to preserve authorized recovery'))
        elif row['startupSeed'] or row['timerSeed'] or (mode == 'entry-only' and row['preheatObserved']):
            errors.append((mode, 'entry-only or invalid-home startup wrote protected workspace'))
    if errors:
        print('FAILURE_ID:S206_INITIALIZATION_RECOVERY_ROLE_NODE_BYPASS')
    assert not errors, errors


@pytest.mark.cer_assertion(
    'A-O-7486EC7571D0-1',
    'A-O-7486EC7571D0-2',
    'A-O-7486EC7571D0-3',
    'A-O-7486EC7571D0-4',
    'A-O-7486EC7571D0-5',
    'A-O-7486EC7571D0-6')
def test_o_7486ec7571d0(tmp_path):
    root = Path(__file__).resolve().parents[2]
    results = tmp_path / 's236-counterexample-trx'
    results.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeRoleClosureTests.O_7486EC7571D0',
         '--logger', 'trx', '--results-directory', str(results)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    value = read_observations(completed, results,
        'PhaseA.Platform.Tests.NodeIdentity.NodeRoleClosureTests.O_7486EC7571D0', 'S206_CONSUMER_COUNTEREXAMPLES:')
    errors = []
    expected = {'ProjectCreationService.legacy', 'ProjectDraftImportService.legacy',
                'ProjectAssetInventoryService.legacy', 'PrototypeCommandService.legacy',
                'PrototypeQuickFixService.legacy', 'PrototypeUiOptimizationService.legacy',
                'PrototypeIterationGoalService.legacy', 'PrototypeFeedbackIterationService.legacy',
                'PrototypeWorkflowService.legacy', 'ChatService.legacy', 'Chapter2BootstrapService.legacy',
                'GameDesignDocumentService.omitted-queue', 'ArtifactReadbackService.omitted-queues',
                'ProjectPackageService.omitted-consumers', 'ProjectWebPreviewService.omitted-consumers',
                'ProjectAssetLibraryService.omitted-consumers'}
    if {row['family'] for row in value['legacy']} != expected:
        raise RuntimeError('Declared concrete constructor counterexample inventory incomplete')
    if not value['seedControl'] or len(value['controls']) != 3 or value['networkCalls']:
        raise RuntimeError('Real explicit-consumer positive controls unavailable')
    for row in value['controls']:
        if not row['registeredQueue'] or row['result'] != 1 or row['count'] != 1:
            raise RuntimeError(('Actual explicit queue did not reach its control boundary', row))
    for row in value['legacy']:
        if not row['denied'] or row['constructedQueues'] or row['constructedSeeders']:
            errors.append(('Implicit legacy consumer construction', row))
    if not value['pureImportSupported']:
        errors.append('Existing pure draft parsing was incorrectly turned into a production-only operation')
    queue_controls = value['queueControls']
    if {(row['position'], row['mode']) for row in queue_controls} != {
            (position, mode) for position in ('running', 'waiting')
            for mode in ('own', 'foreign-account', 'no-context', 'revoked', 'entry-only', 'admin')}:
        raise RuntimeError('Actual running/waiting control matrix incomplete')
    for row in queue_controls:
        permitted = row['mode'] in ('own', 'entry-only')
        if row['mode'] == 'admin':
            if not row['allVisible'] or row['allDenied']:
                errors.append(('Verified admin queue diagnostics unavailable', row))
        elif row['allVisible'] or not row['allDenied']:
            errors.append(('Unprivileged caller obtained global queue diagnostics', row))
        if row['visible'] != permitted or row['readDenied'] == permitted:
            errors.append(('Queue readback bypassed current account or blocked authorized diagnostics', row))
        if row['cancelled'] != permitted or row['targetCancelled'] != permitted or row['cancelDenied'] == permitted:
            errors.append(('Queue cancellation did not retain current same-account control boundary', row))
        if row['position'] == 'waiting' and permitted and row['waitingStarted']:
            errors.append(('Cancelled waiting task reached production callback', row))
        if row['mode'] == 'entry-only' and (row['dispatched'] or not row['dispatchDenied']):
            errors.append(('Control authority enabled entry-only production', row))
    cancellation_controls = value['cancellationControls']
    if {row['mode'] for row in cancellation_controls} != {
            'own', 'foreign-account', 'forged-admin', 'no-context', 'revoked', 'entry-only'}:
        raise RuntimeError('Actual linked cancellation-source control matrix incomplete')
    for row in cancellation_controls:
        allowed = row['mode'] in ('own', 'entry-only')
        if row['cancelled'] != allowed or row['requested'] != allowed or row['denied'] == allowed:
            errors.append(('Linked cancellation source bypassed current owner control', row))
        if not row['ownershipUnchanged']:
            errors.append(('Cancellation control changed protected ownership', row))
        if not all(row[k] for k in ('trustedRegistrationNotPublic', 'trustedCleanupNotPublic', 'privateTokenStateNotPublic')):
            errors.append(('Ordinary cancellation facade exposes trusted registration/cleanup/token state', row))
    overloads = value['queueOverloads']
    entries = ('execute', 'execute-start', 'authorized', 'enter', 'try-enter', 'creation-wrapper')
    modes = ('valid', 'entry-only', 'no-context', 'forged-context', 'revoked', 'foreign-home',
             'foreign-project', 'foreign-local', 'stale-projection')
    if {(row['entry'], row['mode']) for row in overloads} != {
            (entry, mode) for entry in entries for mode in modes} | {('authorized', 'detached-explicit')}:
        raise RuntimeError('Actual queue overload/current-authority matrix incomplete')
    for row in overloads:
        allowed = row['mode'] in ('valid', 'detached-explicit')
        if row['remainingRunning'] or row['remainingWaiting'] or not row['creationWrapperSameQueue']:
            errors.append(('Queue overload stranded or duplicated an owned queue commitment', row))
        if row['rejected'] == allowed or row['started'] != int(allowed) or row['result'] != int(allowed):
            errors.append(('Queue overload bypassed current authority or broke a valid control', row))
        if allowed and row['entry'] in ('enter', 'try-enter') and not row['leaseObserved']:
            errors.append(('Actual owned queue lease was not observed', row))
    shutdown = value['shutdownControls']
    kinds = {'creation', 'ordinary', 'prototype', 'asset', 'preview'}
    if not shutdown['stopObserved'] or {r['kind'] for r in shutdown['rows']} != kinds:
        raise RuntimeError('Actual composed host shutdown/owned queue inventory unavailable')
    if not all(r['projectMatched'] for r in shutdown['rows']) or not shutdown['positiveRun']:
        raise RuntimeError('Actual pre-stop protected run/queue positive control unavailable')
    for row in shutdown['rows']:
        if not row['cancelledAtStop'] or row['running'] != 'cancelled':
            errors.append(('Host shutdown did not cancel its actual owned in-flight task', row))
        if row['waiting'] not in ('cancelled', 'denied') or row['waitingStarted']:
            errors.append(('Owned waiting task produced work after host shutdown', row))
    if not shutdown['writeDenied'] or shutdown['afterRuns'] != shutdown['beforeRuns']:
        errors.append(('Direct metadata production remained callable after actual host stop', shutdown))
    if not shutdown['noticeReadDenied'] or shutdown['noticeChanged'] or shutdown['beforeNoticeReads'] != shutdown['afterNoticeReads']:
        errors.append(('Recipient read-state writer remained callable after actual host stop', shutdown))
    if not shutdown['seedDenied'] or shutdown['initialMarker'] != shutdown['finalMarker']:
        errors.append(('Direct workspace seeder wrote after actual host stop', shutdown))
    if shutdown['newDispatches'] or set(shutdown['newDispatchDenials']) != kinds:
        errors.append(('Stopped host retained an active queue dispatch entry', shutdown))
    if shutdown['controlDenied'] or not shutdown['ownershipUnchanged']:
        errors.append(('Shutdown lost authorized diagnostics/cancel control or changed ownership', shutdown))
    tickets = value['ticketControls']
    if {(row['kind'], row['mode']) for row in tickets} != {
            (kind, mode) for kind in ('asset', 'gdd', 'package')
            for mode in ('valid', 'revoked', 'foreign-home', 'stale-projection', 'foreign-project')}:
        raise RuntimeError('Actual ticket private-byte matrix incomplete')
    for row in tickets:
        if not row['corruptSignatureChanged']:
            raise RuntimeError('Tamper fixture did not mutate the decoded signature bytes')
        if row['mode'] == 'valid':
            if row['status'] != 200 or not row['bytesMatch']:
                errors.append(('Real authenticated issue did not preserve anonymous signed private read', row))
        elif row['status'] == 200 or row['bytesMatch']:
            errors.append(('Signed transport bypassed current account/home/project authority', row))
        if row['corruptStatus'] == 200 or not row['privateFilesUnchanged']:
            errors.append(('Tampered transport disclosed private bytes or changed project files', row))
        if not all(row[key] for key in ('assetNoContext', 'packageNoContext', 'assetForeign',
                                       'packageForeign', 'assetForged', 'packageForged', 'legacyAssetRejected')):
            errors.append(('Direct/legacy ticket issuer or host validator bypassed current authority', row))
    reads = value['routeReadControls']
    if {(row['entry'], row['mode']) for row in reads} != {
            (entry, mode) for entry in ('default', 'bindings', 'full', 'contract-guard')
            for mode in ('valid', 'no-context', 'foreign-account', 'forged-context', 'revoked', 'foreign-home',
                         'stale-projection', 'foreign-project', 'swapped-path', 'legacy', 'stopped')}:
        raise RuntimeError('Actual direct route-source overload/current-authority matrix incomplete')
    for row in reads:
        permitted = row['mode'] == 'valid' or (row['entry'] == 'contract-guard' and row['mode'] == 'legacy')
        if row['denied'] == permitted or row['read'] != permitted or row['foreignRead'] or not row['privateFilesUnchanged']:
            errors.append(('Direct route-source overload read private sources without current authority', row))
    artifacts = value['artifactReadControls']
    if {(row['entry'], row['mode']) for row in artifacts} != {
            (entry, mode) for entry in ('project-runs', 'account-project-runs', 'run', 'account-run',
                                      'artifacts', 'artifact', 'account-artifact', 'health-summary')
            for mode in ('valid', 'no-context', 'foreign-account', 'forged-context', 'revoked',
                         'foreign-home', 'stale-projection', 'foreign-project', 'foreign-local')}:
        raise RuntimeError('Actual private artifact/run/health read matrix incomplete')
    for row in artifacts:
        permitted = row['mode'] == 'valid'
        if row['denied'] == permitted or row['exposed'] != permitted or not row['privateFilesUnchanged'] or not row['publicHealthCompatible']:
            errors.append(('Direct artifact/run/health read bypassed current ownership', row))
    forms = value['questionFormControls']
    if {row['mode'] for row in forms} != {'valid', 'revoked', 'stale-projection'}:
        raise RuntimeError('Actual pending question-form read/cache matrix incomplete')
    for row in forms:
        if not row['reachedModel'] or row['calls'] != 1 or row['changed']:
            raise RuntimeError(('Actual read-only question-form model boundary unavailable', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['resultReturned'] or not row['payloadMatches'] or row['cacheCount'] != 1:
                errors.append(('Current owner lost its actual agent-generated schema/cache', row))
        elif not row['denied'] or row['resultReturned'] or row['payloadMatches'] or row['cacheCount']:
            errors.append(('Pending private schema/cache returned after current authority was denied', row))
    warm = value['warmQuestionFormControls']
    if {(row['decision'], row['mode']) for row in warm} != {
            (decision, mode) for decision in ('keep', 'rebuild') for mode in ('valid', 'revoked', 'stale-projection')}:
        raise RuntimeError('Actual warm-cache decision/rebuild matrix incomplete')
    for row in warm:
        if not row['reachedDecision']:
            raise RuntimeError(('Actual cache-decision model boundary was not observed', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['resultReturned'] or not row['payloadMatches'] or row['cacheCount'] != 1:
                errors.append(('Current owner cannot retain/rebuild its actual private schema', row))
            if row['calls'] != (3 if row['decision'] == 'rebuild' else 2) or row['cacheUnchanged'] != (row['decision'] == 'keep'):
                errors.append(('Current cache decision did not use the actual expected model/cache path', row))
        elif not row['denied'] or row['resultReturned'] or row['payloadMatches'] or row['calls'] != 2 or not row['cacheUnchanged']:
            errors.append(('Denied cache decision dispatched a new model or changed/returned private cache', row))
    scenes = value['sceneReplyControls']
    if {(row['reply'], row['mode']) for row in scenes} != {
            (reply, mode) for reply in ('valid-json', 'invalid-json', 'invalid-shape')
            for mode in ('valid', 'revoked', 'stale-projection', 'entry-only')}:
        raise RuntimeError('Actual scene result/fallback matrix incomplete')
    for row in scenes:
        if not row['reachedModel'] or row['calls'] != 1 or row['changed']:
            raise RuntimeError(('Actual read-only scene model boundary unavailable', row))
        if row['mode'] == 'valid':
            expected_source = 'agent' if row['reply'] == 'valid-json' else 'fallback'
            if row['denied'] or not row['resultReturned'] or row['status'] != 'ready' or row['source'] != expected_source:
                errors.append(('Current owner lost real scene reply/fallback compatibility', row))
            if row['payloadMatches'] != (row['reply'] == 'valid-json'):
                errors.append(('Scene response was not derived from the selected actual reply', row))
            if row['reply'] != 'valid-json' and not row['failureCode']:
                errors.append(('Existing malformed-response fallback lost its reason', row))
        elif not row['denied'] or row['resultReturned'] or row['payloadMatches']:
            errors.append(('Private scene reply/fallback returned after current responsibility or identity denial', row))
    planning = value['iterationPlanReplies']
    if {(row['reply'], row['mode']) for row in planning} != {
            (reply, mode) for reply in ('empty-json', 'malformed-json')
            for mode in ('valid', 'revoked', 'stale-projection', 'entry-only', 'foreign-home', 'foreign-project', 'swapped-path')}:
        raise RuntimeError('Actual iteration-plan model reply matrix incomplete')
    for row in planning:
        if not row['reachedModel'] or row['calls'] != 1:
            raise RuntimeError(('Actual single iteration-plan model boundary unavailable', row))
        if row['changed'] or row['beforeSessions'] != row['afterSessions']:
            errors.append(('Planning failure or denied return changed private files/session rows', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['resultReturned'] or row['status'] != 'llm_failed':
                errors.append(('Valid planning parse-failure control lost existing behavior', row))
        elif not row['denied'] or row['resultReturned']:
            errors.append(('Iteration-plan model fallback retained expired current authority', row))
    backfill = value['backfillEntries']
    if {(row['entry'], row['mode']) for row in backfill} != {
            (entry, mode) for entry in ('existing', 'resolve', 'refresh')
            for mode in ('valid', 'entry-only', 'revoked', 'stale-projection', 'foreign-home',
                         'foreign-project', 'swapped-path', 'no-context', 'forged-context')}:
        raise RuntimeError('Actual direct backfill entry/current-authority matrix incomplete')
    for row in backfill:
        if not row['filesUnchanged']:
            errors.append(('Readback/backfill unexpectedly changed private project files', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['returned'] or row['calls'] != int(row['entry'] == 'resolve'):
                errors.append(('Current registered backfill control unavailable', row))
            if row['entry'] == 'resolve' and (row['status'] != 'matched' or row['metadataUnchanged']):
                errors.append(('Actual valid matcher result was not persisted', row))
        elif row['entry'] == 'refresh' and row['mode'] == 'swapped-path':
            # This entry receives only an ID, re-reads current server metadata and has no
            # contract to publish. There is no caller-carried stale path to consume.
            # It must retain this exact no-contract result without any private effect.
            if row['denied'] or not row['returned'] or row['status'] != 'failed' or row['calls'] or not row['metadataUnchanged']:
                errors.append(('Metadata-only no-contract refresh changed effects or lost its safe result', row))
        elif not row['denied'] or row['returned'] or row['calls'] or not row['metadataUnchanged']:
            errors.append(('Direct backfill dispatched/returned before current project authorization', row))
    if not value['invalidDenied'] or value['invalidStarted'] or not value['entryDenied'] or value['entryStarted']:
        errors.append(('Actual current/role dispatch boundary', value['invalidDenied'], value['entryDenied']))
    inventory = value['assetInventoryReplies']
    if {row['mode'] for row in inventory} != {'valid', 'revoked', 'stale-projection', 'entry-only', 'foreign-home', 'foreign-project', 'swapped-path'}:
        raise RuntimeError('Actual inventory publication matrix incomplete')
    for row in inventory:
        if not row['reachedModel'] or row['calls'] != 1:
            raise RuntimeError(('Actual inventory model boundary unavailable', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['resultReturned'] or not row['canReadInventory'] or row['candidateCount'] != 1 or not row['cacheExists'] or not row['cachedReturn']:
                errors.append(('Current inventory owner lost actual publication or cached readback', row))
            if row['changed'] != ['_phasea/asset-inventory-cache.json']:
                errors.append(('Inventory positive changed files outside its exact cache', row))
        elif not row['denied'] or row['resultReturned'] or row['cacheExists'] or row['changed']:
            errors.append(('Inventory model continuation published under stale current workspace authority', row))
    plans = value['repairAndMilestoneReplies']
    if {(row['family'], row['mode']) for row in plans} != {
            (family, mode) for family in ('repair-plan', 'gdd-next-step-review')
            for mode in ('valid', 'revoked', 'stale-projection', 'entry-only', 'foreign-home', 'foreign-project', 'swapped-path')}:
        raise RuntimeError('Actual repair/milestone pending-model matrix incomplete')
    for row in plans:
        if not row['reachedModel'] or row['calls'] != 1:
            raise RuntimeError(('Actual repair/milestone model boundary unavailable', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['returned'] or not row['count'] or not row['changed']:
                errors.append(('Current repair/milestone owner lost its actual protected publication', row))
            if row['status'] != ('ready' if row['family'] == 'repair-plan' else 'confirmed'):
                errors.append(('Current repair/milestone control lost its expected state', row))
            if row['afterSessions'] != row['beforeSessions'] + int(row['family'] == 'repair-plan'):
                errors.append(('Current repair/milestone published unexpected session rows', row))
        elif not row['denied'] or row['returned'] or row['changed'] or row['beforeSessions'] != row['afterSessions']:
            errors.append(('Pending repair/milestone result published under expired current authority', row))
    media = value['assetAndPreviewPublications']
    if {(row['family'], row['mode']) for row in media} != {
            (family, mode) for family in ('asset-decision', 'preview-direct', 'preview-queued')
            for mode in ('valid', 'revoked', 'stale-projection', 'entry-only', 'foreign-home', 'foreign-project', 'swapped-path')}:
        raise RuntimeError('Actual asset/preview caller boundary matrix incomplete')
    for row in media:
        if not row['boundaryReached'] or row['nativeWindowsOrProviderEvidence']:
            raise RuntimeError(('Actual portable caller boundary unavailable or misrepresented', row))
        if row['family'] == 'asset-decision':
            if row['modelCalls'] != 1 or row['exportCalls']:
                raise RuntimeError(('Actual asset decision/provider trace invalid', row))
        elif row['exportCalls'] != 1 or row['modelCalls'] or row['imageCalls']:
            raise RuntimeError(('Actual direct/queued export continuation unavailable', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['returned'] or not row['published'] or not row['addedOrChanged'] or not row['originalsUnchanged']:
                errors.append(('Current owner lost actual caller publication', row))
            if row['family'] == 'asset-decision' and row['imageCalls'] != 1:
                errors.append(('Current asset control never reached provider', row))
        elif row['published'] or row['addedOrChanged'] or not row['originalsUnchanged']:
            errors.append(('Caller published private effects after current authority changed', row))
        elif row['family'] == 'asset-decision' and (not row['denied'] or row['imageCalls'] or row['newDirectories']):
            errors.append(('Denied asset decision still dispatched or created output paths', row))
    transfers = value['assetImportsAndSelections']
    if {(row['family'], row['mode']) for row in transfers} != {
            (family, mode) for family in ('asset-import', 'asset-import-stream', 'asset-import-read', 'asset-selection')
            for mode in ('valid', 'revoked', 'stale-projection', 'entry-only', 'foreign-home', 'foreign-project', 'swapped-path')}:
        raise RuntimeError('Actual import/selection continuation matrix incomplete')
    for row in transfers:
        if not row['boundaryReached'] or row['externalProviderOrWindowsEvidence']:
            raise RuntimeError(('Owned import/selection boundary unavailable or misrepresented', row))
        if row['httpCalls'] != int(row['family'].startswith('asset-import')) or row['smokeCalls'] != int(row['family'] == 'asset-selection'):
            raise RuntimeError(('Actual import/smoke callback not reached exactly once', row))
        if len(row['pausedEmptyFiles']) != int(row['family'] == 'asset-import-read'):
            raise RuntimeError(('Owned pending read did not prove exact empty writer target', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['returned'] or not row['published'] or not row['changed']:
                errors.append(('Current asset import/selection lost its real publication', row))
        elif not row['denied'] or row['returned'] or row['published'] or row['changed'] or row['removed']:
            errors.append(('Asset import/selection wrote after current authority expired', row))
    producers = value['childProducerPublications']
    if {(row['family'], row['mode']) for row in producers} != {
            (family, mode) for family in ('image-sidecar', 'semantic-fallback', 'dedicated-adapter')
            for mode in ('valid', 'revoked', 'stale-projection', 'entry-only', 'foreign-home', 'foreign-project', 'swapped-path')}:
        raise RuntimeError('Actual child-producer continuation matrix incomplete')
    for row in producers:
        if not row['boundaryReached'] or row['calls'] != 1 or row['realProviderOrWindowsEvidence']:
            raise RuntimeError(('Actual portable child-producer boundary unavailable or misrepresented', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['returned'] or not row['published'] or not row['changed']:
                errors.append(('Current child producer lost its actual publication/fallback', row))
        elif not row['denied'] or row['returned'] or row['published'] or row['changed'] or row['removed']:
            errors.append(('Child producer published after current protected authority changed', row))
    chat = value['chatHistoryControls']
    if {(row['entry'], row['mode']) for row in chat} != {
            (entry, mode) for entry in ('list', 'append')
            for mode in ('valid', 'no-context', 'foreign-account', 'forged-context', 'revoked',
                         'foreign-home', 'stale-projection', 'foreign-project', 'foreign-local', 'entry-only')}:
        raise RuntimeError('Actual direct chat history read/write matrix incomplete')
    for row in chat:
        if row['exposed'] or not row['privateFilesUnchanged'] or not row['initialRowsPreserved']:
            errors.append(('Direct chat history disclosed foreign bytes or changed unrelated state', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['returned'] or row['rowsChanged'] != (row['entry'] == 'append'):
                errors.append(('Actual current chat history control unavailable', row))
        elif not row['denied'] or row['returned'] or row['rowsChanged']:
            errors.append(('Direct chat history bypassed current role/account/home/project authority', row))
    saved = value['savedReadbackControls']
    if {(row['entry'], row['mode']) for row in saved} != {
            (entry, mode) for entry in ('question-answers', 'scene-route', 'requirement-map', 'repair-plan')
            for mode in ('valid', 'no-context', 'foreign-account', 'forged-context', 'revoked',
                         'foreign-home', 'stale-projection', 'foreign-project', 'foreign-local', 'entry-only')}:
        raise RuntimeError('Actual persisted private readback matrix incomplete')
    for row in saved:
        if row['foreignPayload'] or not row['privateFilesUnchanged']:
            errors.append(('Saved readback disclosed other-account content or changed project files', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['returned'] or not row['ownPayload']:
                errors.append(('Actual saved private readback positive unavailable', row))
        elif not row['denied'] or row['returned'] or row['ownPayload']:
            errors.append(('Saved readback bypassed current role/account/home/project authority', row))
    chat = value['chatReplyControls']
    if {(row['backend'], row['mode']) for row in chat} != {
            (backend, mode) for backend in ('codex-route', 'new-api')
            for mode in ('valid', 'revoked', 'stale-projection', 'entry-only', 'foreign-home', 'foreign-project', 'swapped-path')}:
        raise RuntimeError('Actual pending chat reply boundary matrix incomplete')
    for row in chat:
        if not row['reachedModel'] or row['calls'] != 1:
            raise RuntimeError(('Chat case did not reach its actual provider wait', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['returned'] or row['status'] != 'succeeded' or row['reply'] != 'Owned current chat reply' or not row['publishedRowsChanged']:
                errors.append(('Actual chat completion positive unavailable', row))
        elif not row['denied'] or row['returned'] or row['reply'] is not None or row['publishedRowsChanged']:
            errors.append(('Pending chat reply bypassed current authority or published protected rows', row))
    direct = value['directExecutionContinuations']
    if {(row['family'], row['mode']) for row in direct} != {
            (family, mode) for family in ('skill-action', 'chapter2-bootstrap', 'prototype-tdd', 'prototype-scene')
            for mode in ('valid', 'revoked', 'stale-projection', 'entry-only', 'foreign-home', 'foreign-project', 'swapped-path')}:
        raise RuntimeError('Actual direct execution continuation matrix incomplete')
    for row in direct:
        if not row['reachedProvider'] or row['calls'] != 1:
            raise RuntimeError(('Actual direct execution positive did not reach external boundary', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['returned'] or row['status'] != 'succeeded' or not row['publishedRowsChanged']:
                errors.append(('Actual direct execution positive completion unavailable', row))
            if row['family'] == 'skill-action' and not row['changed']:
                errors.append(('Actual skill positive failed to publish its owned reply file', row))
        elif not row['denied'] or row['returned'] or row['changed'] or row['publishedRowsChanged']:
            errors.append(('Direct continuation published after current protected authority changed', row))
    repair = value['repairExecutionAndNewRound']
    if {(row['family'], row['mode']) for row in repair} != {
            (family, mode) for family in ('repair-execute', 'new-round')
            for mode in ('valid', 'revoked', 'stale-projection', 'entry-only', 'foreign-home', 'foreign-project', 'swapped-path')
            if family != 'new-round' or mode != 'swapped-path'}:
        raise RuntimeError('Actual repair execution and new-round matrix incomplete')
    for row in repair:
        if row['family'] == 'repair-execute' and (not row['reachedRunner'] or row['calls'] != 1):
            raise RuntimeError(('Actual repair did not reach its executor', row))
        if row['family'] == 'new-round' and row['calls']:
            raise RuntimeError(('New-round local state operation unexpectedly invoked executor', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['returned'] or not row['changed']:
                errors.append(('Actual repair/new-round positive publication unavailable', row))
            if row['family'] == 'new-round' and (row['status'] != 'created' or not row['appendedModule']):
                errors.append(('Actual new module was not appended', row))
        elif not row['denied'] or row['returned'] or row['changed'] or row['publishedRowsChanged']:
            errors.append(('Repair/new-round wrote after protected authority changed', row))
    milestones = value['milestoneMutationWaits']
    if {(row['entry'], row['mode']) for row in milestones} != {
            (entry, mode) for entry in ('feedback', 'feedback-strict', 'iteration-plan', 'execute', 'execute-strict')
            for mode in ('valid', 'revoked', 'stale-projection', 'entry-only', 'foreign-home', 'foreign-project', 'swapped-path')}:
        raise RuntimeError('Actual milestone caller/mutation-wait matrix incomplete')
    for row in milestones:
        if not row['waitObserved']:
            raise RuntimeError(('Actual milestone did not reach the shared mutation wait', row))
        if row['mode'] == 'valid':
            if row['denied'] or not row['returned'] or not row['changed']:
                errors.append(('Actual milestone continuation positive publication unavailable', row))
        elif not row['denied'] or row['returned'] or row['changed'] or row['runnerCalls']:
            errors.append(('Milestone continuation bypassed current authority after mutation wait', row))
    if errors:
        print('FAILURE_ID:FAILURE-O-7486EC7571D0')
    assert not errors, errors


@pytest.mark.parametrize('outcome', ['pass', 'assertion', 'exception', 'skip', 'setup', 'teardown', 'interrupt', 'symlink'])
def test_fixture_retention_uses_final_python_outcome(tmp_path, outcome):
    """Adapter contract only: synthetic native observation cannot authorize cleanup."""
    import os
    import sys
    case = tmp_path / ('retention-' + outcome)
    case.mkdir()
    other = case / 'other-fixture'
    other.mkdir()
    (other / 'keep.txt').write_text('unrelated fixture', encoding='utf-8')
    sample = case / 'test_observation.py'
    sample.write_text(
        "import os\nfrom pathlib import Path\nimport pytest\n"
        "@pytest.fixture\ndef prerequisite(tmp_path):\n"
        "    root = Path(os.environ.get('S206_OWNED_FIXTURE_ROOT', str(tmp_path / 'legacy-owned')))\n"
        "    root.mkdir(exist_ok=True)\n"
        "    (root / 'synthetic.sqlite3').write_bytes(b'synthetic disposable database')\n"
        "    Path(" + repr(str(case / 'created-root.txt')) + ").write_text(str(root))\n"
        "    if " + repr(outcome) + " == 'setup': raise RuntimeError('setup failed')\n"
        "    yield root\n"
        "    if " + repr(outcome) + " == 'teardown': raise RuntimeError('teardown failed')\n"
        "def test_actual_python_decision(prerequisite):\n"
        "    print('Synthetic CSharp observation passed; not a business verdict')\n"
        "    if " + repr(outcome) + " == 'assertion': assert False, 'business assertion failed'\n"
        "    if " + repr(outcome) + " == 'exception': raise RuntimeError('business observation incomplete')\n"
        "    if " + repr(outcome) + " == 'skip': pytest.skip('no complete business verdict')\n"
        "    if " + repr(outcome) + " == 'interrupt': raise KeyboardInterrupt()\n"
        "    if " + repr(outcome) + " == 'symlink':\n"
        "        (prerequisite / 'escape').symlink_to(" + repr(str(other)) + ", target_is_directory=True)\n",
        encoding='utf-8')
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(Path(__file__).parent) + os.pathsep + environment.get('PYTHONPATH', '')
    result = subprocess.run(
        [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'trx_support', '-p', 'no:cacheprovider',
         str(sample), '--basetemp', str(case / 'pytest-output')],
        cwd=Path(__file__).resolve().parents[2], env=environment, shell=False,
        capture_output=True, text=True, timeout=30)
    recorded = case / 'created-root.txt'
    assert recorded.is_file(), result.stdout + result.stderr
    owned = Path(recorded.read_text())
    if outcome == 'pass':
        assert result.returncode == 0, result.stdout + result.stderr
        assert not owned.exists(), 'Final Python success retained disposable owned data'
        report = owned.parent / (owned.name + '.cleanup.json')
        import json
        value = json.loads(report.read_text())
        assert value['deleted'] is True and value['files']
        assert any(row['path'] == 'synthetic.sqlite3' and row['sha256'] for row in value['files'])
    else:
        assert owned.is_dir(), 'Failed, skipped, interrupted or unsafe case lost its debugging state'
        assert (owned / 'synthetic.sqlite3').is_file()
        if outcome == 'skip':
            assert result.returncode == 0
        else:
            assert result.returncode != 0, result.stdout + result.stderr
    assert (other / 'keep.txt').read_text(encoding='utf-8') == 'unrelated fixture'


def test_legacy_route_reader_compatibility(tmp_path):
    """Run unchanged legacy assertions with real current fixture prerequisites."""
    import hashlib
    import xml.etree.ElementTree as ET
    root = Path(__file__).resolve().parents[2]
    results = tmp_path / 'legacy-route-reader-trx'
    results.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeRoleClosureTests.AuthorityFixturesDoNotChangeProcessSnapshotKeyRoot|FullyQualifiedName~ProjectRouteStateArtifactServiceTests|FullyQualifiedName~GddToModuleBackendContractServiceTests|FullyQualifiedName~RouteActionDescriptorsTests|FullyQualifiedName~ProjectAssetPreviewTicketService|FullyQualifiedName~ProjectPackageDownloadTicketService|FullyQualifiedName~S52BoundaryTests',
         '--logger', 'trx', '--results-directory', str(results)],
        cwd=root, shell=False, check=False, capture_output=True, text=True, timeout=300)
    files = list(results.glob('*.trx'))
    archive = root / 'logs' / 's2-06-native-child-artifacts'
    archive.mkdir(exist_ok=True)
    for path in files:
        raw = path.read_bytes()
        retained = archive / (hashlib.sha256(raw).hexdigest() + '.trx')
        if retained.exists():
            if retained.read_bytes() != raw:
                raise RuntimeError('Raw legacy regression report corruption')
        else:
            with retained.open('xb') as stream:
                stream.write(raw)
    if len(files) != 1:
        raise RuntimeError('Expected one fresh legacy regression TRX')
    ns = {'t': 'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}
    rows = ET.parse(files[0]).getroot().findall('.//t:Results/t:UnitTestResult', ns)
    if not rows:
        raise RuntimeError('No actual legacy regression cases executed')
    assert completed.returncode == 0 and all(row.get('outcome') == 'Passed' for row in rows), (
        'Legacy regression did not pass every original assertion',
        [(row.get('testName'), row.get('outcome')) for row in rows if row.get('outcome') != 'Passed'],
        completed.stdout[-1800:], completed.stderr[-500:])


@pytest.mark.parametrize('mode', ['omitted', 'weak-count', 'failed-policy', 'existing-basetemp', 'linked-basetemp', 'sparse-index', 'garbage-root', 'native-repeat', 'fresh-basetemp', 'late-omitted', 'late-native'])
def test_s206_retention_entry_preserves_prior_roots(tmp_path, mode):
    """ADR-0061: only synthetic sentinels, never rotate actual S2 history."""
    import os
    import sys
    sample = tmp_path / 'entry-sandbox'
    sample.mkdir()
    pool = sample / 'pool'
    pool.mkdir()
    import getpass
    prior = pool / ('pytest-of-' + getpass.getuser())
    prior.mkdir(mode=0o700)
    sentinels = []
    for number in range(6):
        old = prior / ('pytest-' + str(number))
        old.mkdir()
        marker = old / 'historical-original.txt'
        marker.write_bytes(('immutable-' + str(number)).encode())
        sentinels.append((marker, marker.read_bytes()))
    if mode == 'sparse-index':
        (prior / 'pytest-1000').mkdir()
    if mode == 'garbage-root':
        garbage = prior / 'garbage-synthetic'
        garbage.mkdir()
        marker = garbage / 'historical-original.txt'
        marker.write_bytes(b'immutable-garbage-original')
        sentinels.append((marker, marker.read_bytes()))
    test = sample / 'test_synthetic.py'
    test.write_text(
        "import os\nfrom pathlib import Path\nimport pytest\n"
        "pytest_plugins = ['trx_support']\n"
        "def test_owned(tmp_path):\n"
        "    root = Path(os.environ['S206_OWNED_FIXTURE_ROOT'])\n"
        "    (root / 'synthetic.sqlite3').write_bytes(b'only a synthetic sentinel')\n"
        "    Path(os.environ['S206_SYNTHETIC_RECORD']).write_text(str(root))\n"
        "    verdict = os.environ['S206_SYNTHETIC_OUTCOME']\n"
        "    if verdict == 'assertion': assert False, 'synthetic business failure'\n"
        "    if verdict == 'exception': raise RuntimeError('synthetic incomplete observation')\n",
        encoding='utf-8')
    env = dict(os.environ)
    env.pop('PYTEST_ADDOPTS', None)
    env.update(TMPDIR=str(pool), TMP=str(pool), TEMP=str(pool),
               PYTHONPATH=str(Path(__file__).parent) + os.pathsep + env.get('PYTHONPATH', ''))
    permitted = mode in {'native-repeat', 'fresh-basetemp', 'late-native'}
    iterations = ('pass', 'assertion', 'exception') if permitted else ('pass',)
    for index, outcome in enumerate(iterations):
        record = sample / ('owned-' + str(index) + '.txt')
        env.update(S206_SYNTHETIC_RECORD=str(record), S206_SYNTHETIC_OUTCOME=outcome)
        args = [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'trx_support',
                '-p', 'no:cacheprovider', str(test)]
        if mode == 'weak-count':
            args += ['-o', 'tmp_path_retention_count=3', '-o', 'tmp_path_retention_policy=all']
        elif mode == 'failed-policy':
            args += ['-o', 'tmp_path_retention_count=1000', '-o', 'tmp_path_retention_policy=failed']
        elif mode in {'native-repeat', 'sparse-index', 'garbage-root', 'late-native'}:
            args += ['-o', 'tmp_path_retention_count=1000', '-o', 'tmp_path_retention_policy=all']
        elif mode == 'fresh-basetemp':
            args += ['--basetemp', str(sample / ('fresh-' + str(index)))]
        elif mode in {'existing-basetemp', 'linked-basetemp'}:
            chosen = sample / 'unsafe-base'
            if mode == 'linked-basetemp': chosen.symlink_to(prior / 'pytest-0', target_is_directory=True)
            else:
                chosen.mkdir()
                (chosen / 'keep.txt').write_bytes(b'preexisting original')
            args += ['--basetemp', str(chosen)]
        if mode.startswith('late-'):
            args.remove('trx_support')
            args.remove('-p')
        result = subprocess.run(args, env=env, cwd=Path(__file__).resolve().parents[2],
                                capture_output=True, text=True, timeout=30, shell=False)
        if not permitted:
            # A plugin loaded by collection reports a collection error (2), while early configuration reports usage error (4).
            expected_exit = 2 if mode == 'late-omitted' else 4
            assert result.returncode == expected_exit and 's206-scratch-retention' in result.stdout + result.stderr, result.stdout + result.stderr
            assert not record.exists(), 'Unsafe entry executed a fixture before rejection'
        else:
            assert record.is_file(), result.stdout + result.stderr
            owned = Path(record.read_text())
            assert (result.returncode == 0) == (outcome == 'pass'), result.stdout + result.stderr
            assert owned.exists() == (outcome != 'pass'), 'Final Python verdict did not control retention'
        for marker, raw in sentinels:
            assert marker.is_file() and marker.read_bytes() == raw, 'Entry rotated prior synthetic history'


def test_native_registered_project_launch_current_authority(tmp_path):
    # ADR-0061 AD20: separate actual process prerequisites from portable caller cells.
    # The unchanged full-module terminal selector includes this test. No skip or xfail.
    root = Path(__file__).resolve().parents[2]
    results = tmp_path / 'native-owned-launch-trx'
    results.mkdir()
    completed = subprocess.run(
        ['dotnet', 'test', 'PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj', '--no-restore',
         '--filter', 'FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodeRoleClosureTests.HostedRegisteredProjectLaunchObservations',
         '--logger', 'trx', '--results-directory', str(results)],
        cwd=root, shell=False, check=False, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
        env={**os.environ, 'S206_TEST_PYTHON': sys.executable})
    launches = read_observations(completed, results,
        'PhaseA.Platform.Tests.NodeIdentity.NodeRoleClosureTests.HostedRegisteredProjectLaunchObservations',
        'S206_NATIVE_LAUNCH_COUNTEREXAMPLES:')
    errors = []
    if {row['mode'] for row in launches} != {
            'valid', 'detached-current', 'no-context', 'foreign-account', 'forged-context',
            'revoked', 'foreign-home', 'stale-projection', 'foreign-project', 'foreign-local',
            'entry-only', 'no-authority'}:
        raise RuntimeError('Actual registered-project child launch matrix incomplete')
    for row in launches:
        if row['actualWindowsEvidence']:
            raise RuntimeError('Portable owned child must not be relabeled as Windows isolation')
        if row['mode'] in ('valid', 'detached-current'):
            if row['exitCode'] != 0 or not all(row[k] for k in ('childOutput', 'markerExists', 'markerMatches')) or row['filesUnchanged']:
                errors.append(('Actual current owned child launch failed', row))
        elif row['exitCode'] != 403 or row['childOutput'] or row['markerExists'] or not row['filesUnchanged']:
            errors.append(('Actual child launched without current registered project authority', row))
    assert not errors, errors
