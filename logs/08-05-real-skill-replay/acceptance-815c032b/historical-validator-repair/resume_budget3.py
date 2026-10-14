"""ADR-0058: explicit threefold-budget successors; preserve all prior proofs."""
import json
import hashlib
import subprocess
import sys
import time
from pathlib import Path

import resume_minimal as prior
from stable_runner import _descriptor_inputs, candidate_identity
from current_router import materialize_descriptor
from read_only_reuse_audit import check
from behavior_routing import read_route
from runtime_evidence import load_json

HERE = Path(__file__).resolve().parent
ROOT = prior.ROOT
OUT = HERE / 'owner-recovery-r9-budget3'
prior.OUT = OUT
STAGE_BUDGET = 1800
SCOPE = ['S26', 'S28', 'S30', 'S35', 'S41', 'S44']
COMPLETED_R8 = ['S33', 'S34', 'S36']


def action(label, args):
    argv = [sys.executable, '-B', 'scripts/quick_dev/run.py', '--plan', prior.rel(prior.SEMANTIC.parent), *args]
    evidence = OUT / 'commands' / label
    process = evidence / 'process.json'
    if process.exists():
        facts = load_json(process)
        if facts['argv'] != argv or facts['head'] != prior.HEAD:
            raise RuntimeError('Action input drift: ' + label)
        result = load_json(evidence / 'stdout.bin')
        print('REUSE ACTION ' + label, flush=True)
    else:
        if evidence.exists():
            raise RuntimeError('Partial wrapper evidence: ' + label)
        evidence.mkdir(parents=True)
        print('START ' + label + '; stage budget=1800s, wrapper budget=3600s', flush=True)
        started = time.monotonic()
        completed = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=3600)
        prior.create_immutable(evidence / 'stdout.bin', completed.stdout)
        prior.create_immutable(evidence / 'stderr.bin', completed.stderr)
        facts = {'argv': argv, 'exit_code': completed.returncode, 'head': prior.HEAD,
                 'elapsed_seconds': time.monotonic() - started,
                 'stdout_sha256': 'sha256:' + hashlib.sha256(completed.stdout).hexdigest(),
                 'stderr_sha256': 'sha256:' + hashlib.sha256(completed.stderr).hexdigest(),
                 'authorizes': []}
        prior.create_json(process, facts)
        result = json.loads(completed.stdout)
    if (facts['exit_code'] != 0 or result.get('predicate_result') is False
            or result.get('status') in {'blocked', 'failed', 'stage-reentry-blocked'}):
        print(json.dumps(result)[:6000], flush=True)
        raise RuntimeError('Preserved action failure: ' + label)
    print('PASS ' + label + ' (' + str(round(facts['elapsed_seconds'], 2)) + 's)', flush=True)
    return result


prior.action = action


def selected_prior(sid):
    if sid in COMPLETED_R8:
        return prior.predecessor(sid, HERE / 'owner-recovery-r8' / (sid + '-historical-judge-r8'))
    return next(row['predecessor'] for row in prior.AUDIT['rows'] if row['slice_id'] == sid)


def audit():
    rows = [check(selected_prior(row['slice_id']), prior.BUNDLE) for row in prior.AUDIT['rows']]
    result = {'authorizes': [], 'tests_launched': 0, 'evidence_rebound': False,
              'rows': rows, 'blocked_slices': [r['slice_id'] for r in rows if not r['reusable']]}
    prior.immutable_json(OUT / 'reuse-audit-before-r9.json', result)
    print(json.dumps({'reusable': sum(r['reusable'] for r in rows),
                      'blocked_slices': result['blocked_slices']}), flush=True)
    unexpected = set(result['blocked_slices']) - set(SCOPE)
    if unexpected:
        raise RuntimeError('Additional binding impact requires diagnosis, not automatic rerun: ' + str(unexpected))


def recover(sid):
    if sid not in SCOPE:
        raise ValueError('Outside explicit remaining scope')
    run = OUT / (sid + '-budget3-r9')
    original_prior = selected_prior(sid)
    original = load_json(ROOT / original_prior['result_ref'])
    if (run / 'slice-ready-result.v2.json').exists() and (run / 'canonical-evidence/terminal/stage-result.v2.json').exists():
        row = check(prior.predecessor(sid, run), prior.BUNDLE)
        if not row['reusable']:
            raise RuntimeError('Completed successor is not reusable: ' + json.dumps(row['failures']))
        print('REUSE COMPLETE ' + sid, flush=True)
        return
    args = ['--slice', sid, '--profile', prior.OLD['profile'], '--run-dir', prior.rel(run)]
    prior.action(sid + '-preflight', args + ['--action', 'preflight'])
    argv, targets, fixtures = _descriptor_inputs(prior.BUNDLE, prior.SEMANTIC.parent, sid)
    identity = candidate_identity(ROOT, prior.BUNDLE, sid)
    descriptor = materialize_descriptor(bundle=prior.BUNDLE, slice_id=sid, stage='probe',
        run_id=run.name, candidate_hash=identity['candidate_hash'], argv=argv, cwd='.',
        timeout_seconds=STAGE_BUDGET, target_refs=targets, fixture_refs=fixtures)
    prior.immutable_json(run / 'descriptors/probe.json', descriptor)
    prior.immutable_json(run / 'recovery-intent.json', {
        'prior': original_prior, 'candidate_commit': prior.HEAD,
        'explicit_failure_run': prior.rel(HERE / 'owner-recovery-r8' / (sid + '-historical-judge-r8')) if sid in {'S26', 'S28'} else None,
        'reason': 'Maintainer-approved threefold deadlines; no selector or verdict relaxation',
        'stage_budget_seconds': STAGE_BUDGET, 'authorizes': []})
    prior.action(sid + '-probe', args + ['--action', 'execute-stage', '--descriptor', prior.rel(run / 'descriptors/probe.json')])
    route = read_route(ROOT, prior.BUNDLE, run, sid)
    if any(r['disposition'] != 'present' for r in route['behavior_dispositions']):
        raise RuntimeError('Observed behavior requires bounded repair: ' + sid)
    for stage in ['regression', 'terminal']:
        descriptor = materialize_descriptor(bundle=prior.BUNDLE, slice_id=sid, stage=stage,
            run_id=run.name, candidate_hash=identity['candidate_hash'], argv=argv, cwd='.',
            timeout_seconds=STAGE_BUDGET, target_refs=targets, fixture_refs=fixtures, routing_result=route)
        prior.immutable_json(run / 'descriptors' / (stage + '.json'), descriptor)
    prior.action(sid + '-regression', args + ['--action', 'execute-stage', '--descriptor', prior.rel(run / 'descriptors/regression.json')])
    roots = [dict(row) for row in original['snapshot_roots']]
    for row in roots:
        row.pop('content_sha256', None)
        row['source_commit'] = prior.HEAD
        if row['root_kind'] in {'descriptor', 'plan_state_transition'}:
            row.pop('repository_relative_posix_paths', None)
            row['repository_relative_posix_path'] = prior.rel(run / 'descriptors') if row['root_kind'] == 'descriptor' else prior.rel(run)
    prior.immutable_json(run / 'snapshot-roots.json', roots)
    prior.action(sid + '-q7', args + ['--action', 'validate-slice', '--snapshot-roots', prior.rel(run / 'snapshot-roots.json'),
        '--source-commit', prior.HEAD, '--base-commit', prior.BINDING['baseCommit'], '--out', prior.rel(run / 'slice-ready-result.v2.json')])
    prior.action(sid + '-terminal', args + ['--action', 'execute-stage', '--descriptor', prior.rel(run / 'descriptors/terminal.json')])
    successor = prior.predecessor(sid, run)
    row = check(successor, prior.BUNDLE)
    if not row['reusable']:
        raise RuntimeError('Owner proof replay failed: ' + json.dumps(row['failures']))
    prior.immutable_json(run / 'predecessor-lineage.json', {'prior': original_prior, 'successor': successor,
        'reason': 'Explicit budget3 successor preserves prior failure records', 'authorizes': []})
    print('COMPLETE ' + sid, flush=True)


def q8():
    predecessors = []
    for row in prior.AUDIT['rows']:
        sid = row['slice_id']
        selected = (prior.predecessor(sid, OUT / (sid + '-budget3-r9'))
                    if sid in SCOPE else selected_prior(sid))
        predecessors.append(selected)
    run = OUT / 'Q8-budget3-r9'
    roots = [dict(row) for row in prior.BINDING['snapshotRoots']]
    for row in roots:
        row.pop('content_sha256', None)
        row['source_commit'] = prior.HEAD
        if row['root_kind'] == 'descriptor':
            row['repository_relative_posix_path'] = prior.rel(OUT / 'S44-budget3-r9/descriptors')
        elif row['root_kind'] == 'plan_state_transition':
            row['repository_relative_posix_path'] = prior.rel(run)
    prior.immutable_json(run / 'predecessors.json', predecessors)
    prior.immutable_json(run / 'snapshot-roots.json', roots)
    action('Q8', ['--slice', 'S44', '--profile', prior.OLD['profile'], '--action', 'implementation-complete',
        '--snapshot-roots', prior.rel(run / 'snapshot-roots.json'), '--predecessors', prior.rel(run / 'predecessors.json'),
        '--source-commit', prior.HEAD, '--base-commit', prior.BINDING['baseCommit'],
        '--out', prior.rel(run / 'implementation-complete-result.v2.json')])


if __name__ == '__main__':
    for sid in sys.argv[1:]:
        audit() if sid == 'audit' else q8() if sid == 'Q8' else recover(sid)
