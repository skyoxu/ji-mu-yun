"""Explicit minimal successor orchestration; current owners write proofs.

Accepted ADR-0058. No implementation, old evidence mutation, or history scan.
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = HERE / 'owner-recovery-r8'
sys.path.insert(0, str(ROOT / '.agents/skills/quick-dev-tdd-adapter/tools'))
from runtime_evidence import load_json, sha256_value, create_json, create_immutable, canonical_bytes
from current_router import materialize_descriptor
from behavior_routing import read_route
from read_only_reuse_audit import check

REQUEST = load_json(ROOT / 'compact-vdd-projection-request.815c032b.v1.json')
BINDING = REQUEST['currentQuickDev']
SEMANTIC = ROOT / BINDING['semanticPlan']['path']
BUNDLE = load_json(SEMANTIC)
OLD = load_json(ROOT / BINDING['receipt']['path'])
AUDIT = load_json(HERE / 'read-only-reuse-audit-r1.json')
HEAD = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
ALLOWED = ['S26', 'S28', 'S30', 'S33', 'S34', 'S35', 'S36', 'S41', 'S44']


def rel(path):
    return path.relative_to(ROOT).as_posix()


def immutable_json(path, value):
    if path.exists():
        if load_json(path) != value:
            raise RuntimeError('Existing input differs: ' + str(path))
    else:
        create_immutable(path, canonical_bytes(value))


def action(label, args):
    argv = [sys.executable, '-B', 'scripts/quick_dev/run.py', '--plan', rel(SEMANTIC.parent), *args]
    evidence = OUT / 'commands' / label
    process = evidence / 'process.json'
    if process.exists():
        facts = load_json(process)
        if facts['argv'] != argv or facts['head'] != HEAD:
            raise RuntimeError('Action input drift: ' + label)
        result = load_json(evidence / 'stdout.bin')
        print('REUSE ACTION ' + label, flush=True)
    else:
        if evidence.exists():
            raise RuntimeError('Partial wrapper evidence: ' + label)
        evidence.mkdir(parents=True)
        print('START ' + label, flush=True)
        started = time.monotonic()
        completed = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=1200)
        create_immutable(evidence / 'stdout.bin', completed.stdout)
        create_immutable(evidence / 'stderr.bin', completed.stderr)
        facts = {'argv': argv, 'exit_code': completed.returncode, 'head': HEAD,
                 'elapsed_seconds': time.monotonic() - started,
                 'stdout_sha256': 'sha256:' + hashlib.sha256(completed.stdout).hexdigest(),
                 'stderr_sha256': 'sha256:' + hashlib.sha256(completed.stderr).hexdigest(),
                 'authorizes': []}
        create_json(process, facts)
        try:
            result = json.loads(completed.stdout)
        except Exception:
            print(completed.stderr.decode('utf-8', errors='replace')[-4000:], flush=True)
            raise RuntimeError('No typed action result: ' + label)
    if (facts['exit_code'] != 0 or result.get('predicate_result') is False
            or result.get('status') in {'blocked', 'failed', 'stage-reentry-blocked'}):
        print(json.dumps(result), flush=True)
        raise RuntimeError('Preserved action failure: ' + label)
    print('PASS ' + label + ' (' + str(round(facts['elapsed_seconds'], 2)) + 's)', flush=True)
    return result


def predecessor(sid, run):
    result = run / 'slice-ready-result.v2.json'
    return {'slice_id': sid, 'run_root': rel(run), 'result_ref': rel(result),
            'result_sha256': sha256_value(load_json(result))}


def recover(sid):
    if sid not in ALLOWED or sid not in AUDIT['blocked_slices']:
        raise RuntimeError('Not in explicit affected scope: ' + sid)
    run = OUT / (sid + '-historical-judge-r8')
    prior = next(p for p in OLD['predecessors'] if p['slice_id'] == sid)
    original = load_json(ROOT / prior['result_ref'])
    if (run / 'slice-ready-result.v2.json').exists() and (run / 'canonical-evidence/terminal/stage-result.v2.json').exists():
        row = check(predecessor(sid, run), BUNDLE)
        if not row['reusable']:
            raise RuntimeError('Completed successor is stale: ' + json.dumps(row['failures']))
        print('REUSE COMPLETE ' + sid, flush=True)
        return
    args = ['--slice', sid, '--profile', OLD['profile'], '--run-dir', rel(run)]
    action(sid + '-preflight', args + ['--action', 'preflight'])
    author = action(sid + '-materialize', args + ['--action', 'author-red'])
    if author.get('worker', {}).get('status') != 'worker-not-required':
        raise RuntimeError('Unexpected author requirement: ' + sid)
    immutable_json(run / 'recovery-intent.json', {
        'prior': prior, 'candidate_commit': HEAD,
        'reason': 'Historical trusted-validator separation changes actual replay behavior',
        'diagnostic': next(r for r in AUDIT['rows'] if r['slice_id'] == sid),
        'additional_failure_run': rel(HERE / 'owner-recovery-r7/S26-historical-judge-r7') if sid == 'S26' else None,
        'stage_budget_seconds': 600, 'authorizes': []})
    action(sid + '-probe', args + ['--action', 'run-probe'])
    route = read_route(ROOT, BUNDLE, run, sid)
    if any(row['disposition'] != 'present' for row in route['behavior_dispositions']):
        raise RuntimeError('Requires bounded implementation/repair: ' + sid)
    probe = load_json(run / 'descriptors/probe.json')
    for stage in ['regression', 'terminal']:
        path = run / 'descriptors' / (stage + '.json')
        descriptor = materialize_descriptor(bundle=BUNDLE, slice_id=sid, stage=stage,
            run_id=run.name, candidate_hash=probe['candidate_hash'], argv=probe['argv'],
            cwd=probe['cwd'], timeout_seconds=600, target_refs=probe['target_refs'],
            fixture_refs=probe['fixture_refs'], routing_result=route)
        immutable_json(path, descriptor)
    action(sid + '-regression', args + ['--action', 'execute-stage', '--descriptor', rel(run / 'descriptors/regression.json')])
    roots = [dict(row) for row in original['snapshot_roots']]
    for row in roots:
        row.pop('content_sha256', None)
        row['source_commit'] = HEAD
        if row['root_kind'] in {'descriptor', 'plan_state_transition'}:
            row.pop('repository_relative_posix_paths', None)
            row['repository_relative_posix_path'] = rel(run / 'descriptors') if row['root_kind'] == 'descriptor' else rel(run)
    immutable_json(run / 'snapshot-roots.json', roots)
    action(sid + '-q7', args + ['--action', 'validate-slice', '--snapshot-roots', rel(run / 'snapshot-roots.json'),
        '--source-commit', HEAD, '--base-commit', BINDING['baseCommit'], '--out', rel(run / 'slice-ready-result.v2.json')])
    action(sid + '-terminal', args + ['--action', 'execute-stage', '--descriptor', rel(run / 'descriptors/terminal.json')])
    successor = predecessor(sid, run)
    row = check(successor, BUNDLE)
    if not row['reusable']:
        raise RuntimeError('Owner proof replay failed: ' + json.dumps(row['failures']))
    immutable_json(run / 'predecessor-lineage.json', {'prior': prior, 'successor': successor,
        'reason': 'Current executing replay implementation changed', 'authorizes': []})
    print('COMPLETE ' + sid, flush=True)


def q8():
    predecessors = []
    for row in AUDIT['rows']:
        sid = row['slice_id']
        selected = row['predecessor'] if row['reusable'] else predecessor(sid, OUT / (sid + '-historical-judge-r8'))
        replay = check(selected, BUNDLE)
        if not replay['reusable']:
            raise RuntimeError('Q8 input is not reusable: ' + sid + ': ' + json.dumps(replay['failures']))
        predecessors.append(selected)
    run = OUT / 'Q8-historical-judge-r8'
    roots = [dict(row) for row in BINDING['snapshotRoots']]
    for row in roots:
        row.pop('content_sha256', None)
        row['source_commit'] = HEAD
        if row['root_kind'] == 'descriptor':
            row['repository_relative_posix_path'] = rel(OUT / 'S44-historical-judge-r8/descriptors')
        elif row['root_kind'] == 'plan_state_transition':
            row['repository_relative_posix_path'] = rel(run)
    immutable_json(run / 'predecessors.json', predecessors)
    immutable_json(run / 'snapshot-roots.json', roots)
    action('Q8', ['--slice', 'S44', '--profile', OLD['profile'], '--action', 'implementation-complete',
        '--snapshot-roots', rel(run / 'snapshot-roots.json'), '--predecessors', rel(run / 'predecessors.json'),
        '--source-commit', HEAD, '--base-commit', BINDING['baseCommit'],
        '--out', rel(run / 'implementation-complete-result.v2.json')])
    print('Q8 COMPLETE; reused 36 exact predecessors, recovered 9 affected slices', flush=True)


if __name__ == '__main__':
    for selected in sys.argv[1:]:
        q8() if selected == 'Q8' else recover(selected)
