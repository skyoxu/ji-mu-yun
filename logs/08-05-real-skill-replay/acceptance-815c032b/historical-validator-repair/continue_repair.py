"""Append-only targeted recovery diagnostics (Accepted ADR-0058)."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
RECOVERY_ROOT = HERE / 'owner-recovery-r2'
sys.path.insert(0, str(ROOT / '.agents/skills/quick-dev-tdd-adapter/tools'))
from runtime_evidence import hash_path, sha256_value


def capture(label, argv):
    out = HERE / label
    if out.exists():
        if any(out.iterdir()):
            raise RuntimeError('Existing non-empty action evidence requires explicit recovery: ' + label)
    else:
        out.mkdir(parents=True, exist_ok=False)
    print('START ' + label, flush=True)
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=900)
    (out / 'stdout.bin').write_bytes(result.stdout)
    (out / 'stderr.bin').write_bytes(result.stderr)
    facts = dict(argv=argv, exit_code=result.returncode,
                 head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                 stdout_sha256='sha256:' + hashlib.sha256(result.stdout).hexdigest(),
                 stderr_sha256='sha256:' + hashlib.sha256(result.stderr).hexdigest(), authorizes=[])
    (out / 'process.json').write_text(json.dumps(facts, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(result.stdout.decode('utf-8', errors='replace')[-3500:], flush=True)
    print(result.stderr.decode('utf-8', errors='replace')[-2000:], flush=True)
    return result.returncode


def audit():
    request = json.loads((ROOT / 'compact-vdd-projection-request.815c032b.v1.json').read_text(encoding='utf-8'))
    q8 = json.loads((ROOT / request['currentQuickDev']['receipt']['path']).read_text(encoding='utf-8'))
    rows = []
    for prior in q8['predecessors']:
        ready = json.loads((ROOT / prior['result_ref']).read_text(encoding='utf-8'))
        stale = []
        for row in ready['snapshot_manifest']['roots']:
            paths = row.get('repository_relative_posix_paths') or [row['repository_relative_posix_path']]
            value = hash_path(ROOT / paths[0]) if len(paths) == 1 else sha256_value([(p, hash_path(ROOT / p)) for p in paths])
            if row['root_kind'] != 'plan_state_transition' and value != row['content_sha256']:
                stale.append(dict(kind=row['root_kind'], paths=paths, frozen=row['content_sha256'], current=value))
        if stale:
            rows.append(dict(slice=prior['slice_id'], stale=stale))
    print(json.dumps(rows, indent=2))
    return rows


def recover():
    # Only actual changed runtime roots select successors. Unchanged rows
    # retain their original receipts, bytes and source identities.
    request = json.loads((ROOT / 'compact-vdd-projection-request.815c032b.v1.json').read_text(encoding='utf-8'))
    binding = request['currentQuickDev']
    old = json.loads((ROOT / binding['receipt']['path']).read_text(encoding='utf-8'))
    plan = (ROOT / binding['semanticPlan']['path']).parent
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    successors = [dict(p) for p in old['predecessors']]
    def rel(path):
        return path.relative_to(ROOT).as_posix()

    affected = {row['slice'] for row in audit()}
    reusable = {}
    deferred = []
    for sid in ('S2', 'S3'):
        existing = HERE / 'owner-recovery' / (sid + '-historical-judge-r1')
        existing_result = existing / 'slice-ready-result.v2.json'
        if existing_result.is_file():
            value = json.loads(existing_result.read_text(encoding='utf-8'))
            if value.get('status') == 'pass' and value.get('predicate') == 'slice-ready':
                reusable[sid] = dict(slice_id=sid, run_root=rel(existing), result_ref=rel(existing_result), result_sha256=sha256_value(value))
                affected.discard(sid)
    from runtime_evidence import canonical_bytes, create_immutable, create_json

    def command(args, label):
        evidence = RECOVERY_ROOT / 'commands' / label
        process_path = evidence / 'process.json'
        if process_path.is_file():
            facts = json.loads(process_path.read_text(encoding='utf-8'))
            if facts['exit_code']:
                raise RuntimeError('Preserved unsuccessful action requires an explicit successor: ' + label)
            value = json.loads((evidence / 'stdout.bin').read_bytes().decode('utf-8'))
            if value.get('status') in {'blocked', 'failed', 'stage-reentry-blocked'} or value.get('predicate_result') is False:
                raise RuntimeError('Preserved unsuccessful action cannot be reused: ' + label)
            print('REUSE ' + label, flush=True)
            return value
        argv = [sys.executable, '-B', 'scripts/quick_dev/run.py', '--plan', rel(plan), *args]
        if capture('owner-recovery-r2/commands/' + label, argv):
            raise RuntimeError('Owner action failed: ' + label)
        value = json.loads((evidence / 'stdout.bin').read_bytes())
        if value.get('status') in {'blocked', 'failed', 'stage-reentry-blocked'} or value.get('predicate_result') is False:
            raise RuntimeError('Owner action refused: ' + label + ': ' + str(value))
        return value

    for prior in old['predecessors']:
        sid = prior['slice_id']
        if sid not in affected:
            if sid in reusable:
                successors = [reusable[sid] if p['slice_id'] == sid else p for p in successors]
                print('REUSE ' + sid + ' completed recovery', flush=True)
            continue
        if sid == 'S7':
            deferred.append(dict(slice_id=sid, reason='timeout-no-observation', failure_id='QD-TIMEOUT-NO-OBSERVATION-9855E0D72E8C0DE6'))
            print('DEFER S7: current Windows stage budget cannot collect a complete case report', flush=True)
            continue
        # S3 already has a successful owner recovery bound to this exact
        # historical-judge change; reuse it after validating its terminal
        # result instead of reopening the slice.
        ready = json.loads((ROOT / prior['result_ref']).read_text(encoding='utf-8'))
        run = RECOVERY_ROOT / (sid + '-historical-judge-r2')
        args = ['--slice', sid, '--profile', old['profile'], '--run-dir', rel(run)]
        command(args + ['--action', 'preflight'], sid + '-preflight')
        materialized = command(args + ['--action', 'author-red'], sid + '-materialize')
        if materialized.get('worker', {}).get('status') != 'worker-not-required':
            raise RuntimeError('Unexpected author invocation: ' + sid)
        command(args + ['--action', 'run-probe'], sid + '-probe')
        route = command(args + ['--action', 'route-behaviors'], sid + '-route')
        if route.get('required_next_action') != 'run-regression':
            raise RuntimeError('Behavior requires bounded repair: ' + sid + ': ' + str(route))
        command(args + ['--action', 'run-regression'], sid + '-regression')
        roots = [dict(row) for row in ready['snapshot_roots']]
        for row in roots:
            row.pop('content_sha256', None)
            row['source_commit'] = commit
            if row['root_kind'] in {'descriptor', 'plan_state_transition'}:
                row.pop('repository_relative_posix_paths', None)
                row['repository_relative_posix_path'] = rel(run / 'descriptors') if row['root_kind'] == 'descriptor' else rel(run)
        roots_path = run / 'snapshot-roots.json'
        if not roots_path.exists():
            create_immutable(roots_path, canonical_bytes(roots))
        result_path = run / 'slice-ready-result.v2.json'
        command(args + ['--action', 'validate-slice', '--snapshot-roots', rel(roots_path),
            '--source-commit', commit, '--base-commit', binding['baseCommit'], '--out', rel(result_path)], sid + '-q7')
        command(args + ['--action', 'run-terminal'], sid + '-terminal')
        fresh = json.loads(result_path.read_text(encoding='utf-8'))
        successor = dict(slice_id=sid, run_root=rel(run), result_ref=rel(result_path), result_sha256=sha256_value(fresh))
        successors = [successor if p['slice_id'] == sid else p for p in successors]
        lineage = run / 'predecessor-lineage.json'
        if not lineage.exists():
            create_json(lineage, dict(prior=prior, successor=successor,
                reason='Shared executing judge separation changes result-determining production paths', authorizes=[]))
        print('COMPLETE ' + sid, flush=True)
    if deferred:
        from runtime_evidence import create_json
        blocker = RECOVERY_ROOT / 'recovery-status.v1.json'
        if not blocker.exists():
            create_json(blocker, dict(schema='quick-dev.acceptance-successor-recovery.v1',
                candidate_commit=commit, completed_slices=sorted(sid for sid in affected if sid != 'S7'),
                deferred=deferred, q8_published=False, authorizes=[]))
        print('Q8 BLOCKED: unresolved slices ' + ','.join(row['slice_id'] for row in deferred), flush=True)
        return
    q8 = RECOVERY_ROOT / 'Q8-historical-judge-r2'
    s44 = next(p for p in successors if p['slice_id'] == 'S44')
    s44_result = json.loads((ROOT / s44['result_ref']).read_text(encoding='utf-8'))
    roots = s44_result['snapshot_roots']
    for name, value in [('snapshot-roots.json', roots), ('predecessors.json', successors)]:
        if not (q8 / name).exists():
            create_immutable(q8 / name, canonical_bytes(value))
    command(['--slice', 'S44', '--profile', old['profile'], '--action', 'implementation-complete',
        '--snapshot-roots', rel(q8 / 'snapshot-roots.json'), '--predecessors', rel(q8 / 'predecessors.json'),
        '--source-commit', commit, '--base-commit', binding['baseCommit'],
        '--out', rel(q8 / 'implementation-complete-result.v2.json')], 'Q8')


if __name__ == '__main__':
    if sys.argv[1] == 'audit':
        audit()
    elif sys.argv[1] == 'recover':
        recover()
    else:
        raise SystemExit(capture(sys.argv[1], sys.argv[2:]))
