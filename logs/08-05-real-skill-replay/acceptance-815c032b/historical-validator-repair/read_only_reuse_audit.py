"""Inspect explicitly bound proofs without launching tests (ADR-0058).

This diagnostic is non-authorizing. Only the public Q8/Acceptance owners
may publish lifecycle completion. Existing proof bytes are never changed.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.agents/skills/quick-dev-tdd-adapter/tools'))
from runtime_evidence import load_json, sha256_value, hash_path, create_json
from coverage_predicates import _replay_snapshot, _reread_edge, _semantic_index
from behavior_routing import read_route, stage_map, verify_stage, current_result, verify_case_continuity


SUCCESSORS = {
    'S2': 'owner-recovery/S2-historical-judge-r1',
    'S3': 'owner-recovery/S3-historical-judge-r1',
    'S7': 'owner-recovery-r4/S7-historical-judge-r4',
    'S9': 'owner-recovery-r2/S9-historical-judge-r2',
    'S10': 'owner-recovery-r2/S10-historical-judge-r2',
    'S12': 'owner-recovery-r2/S12-historical-judge-r2',
    'S13': 'owner-recovery-r6/S13-historical-judge-r6',
    'S17': 'owner-recovery-r7/S17-historical-judge-r7',
    'S19': 'owner-recovery-r7/S19-historical-judge-r7',
    'S25': 'owner-recovery-r7/S25-historical-judge-r7',
}


def check(prior, bundle):
    sid = prior['slice_id']
    run = ROOT / prior['run_root']
    ready = load_json(ROOT / prior['result_ref'])
    failures = []

    def verify(label, operation):
        try:
            return operation()
        except Exception as exc:
            failures.append({'check': label, 'error': str(exc)})
            return None

    if (sha256_value(ready) != prior['result_sha256'] or ready.get('status') != 'pass'
            or ready.get('slice_id') != sid or ready.get('authorizes') != []):
        failures.append({'check': 'ready', 'error': 'Invalid immutable predecessor'})
    verify('snapshot', lambda: _replay_snapshot(ROOT, ready['snapshot_roots'],
        ready['source_commit'], ready.get('base_commit'),
        {'snapshot_manifest': ready['snapshot_manifest']}))
    changed = []
    for row in ready['snapshot_manifest']['roots']:
        paths = row.get('repository_relative_posix_paths') or [row['repository_relative_posix_path']]
        value = hash_path(ROOT / paths[0]) if len(paths) == 1 else sha256_value([(p, hash_path(ROOT / p)) for p in paths])
        if row['root_kind'] != 'plan_state_transition' and value != row['content_sha256']:
            changed.append({'root_kind': row['root_kind'], 'paths': paths})
    route = verify('probe', lambda: read_route(ROOT, bundle, run, sid))
    if route is not None and ready.get('behavior_route_sha256') != sha256_value(route):
        failures.append({'check': 'route', 'error': 'Ready/probe binding mismatch'})
    requirements = stage_map(bundle, sid, route) if route is not None else {}
    _, assertions = _semantic_index(bundle, sid)
    stages = set(s for values in requirements.values() for s in values) | {'terminal'}
    for stage in sorted(stages):
        try:
            descriptor = load_json(run / 'descriptors' / (stage + '.json'))
            result = load_json(run / 'canonical-evidence' / stage / 'stage-result.v2.json')
            receipt = load_json(run / 'canonical-evidence' / stage / 'process-receipt.v2.json')
        except Exception as exc:
            failures.append({'check': stage, 'error': str(exc)})
            continue
        verify(stage + ':binding', lambda: verify_stage(ROOT, bundle, run, descriptor, require_probe_current=False))
        verify(stage + ':cases', lambda: verify_case_continuity(descriptor, receipt, route))
        if stage in {'refactor', 'regression', 'terminal'}:
            verify(stage + ':production', lambda: current_result(ROOT, bundle, sid, result))
        if (result.get('predicate_result') is not True
                or result.get('verification_outcome') != ('fail' if stage == 'red' else 'pass')):
            failures.append({'check': stage, 'error': 'Stage is not an admissible observed pass/RED'})
        if stage == 'terminal' and result.get('candidate_hash') != ready.get('candidate_hash'):
            failures.append({'check': stage, 'error': 'Terminal/Q7 candidate mismatch'})
        observed = {}
        for ref in result.get('runtime_edges', []):
            edge = verify(stage + ':edge', lambda: _reread_edge(ROOT, run, ref,
                slice_id=sid, stage=stage, selector_identity=result['selector_identity']))
            if edge is not None:
                observed.setdefault(edge['acceptance_id'], []).append(edge['assertion_id'])
        expected = {aid: ids for aid, ids in assertions.items()
                    if stage == 'terminal' or stage in requirements.get(aid, ())}
        if ({aid: set(ids) for aid, ids in observed.items()} != expected
                or any(len(ids) != len(set(ids)) for ids in observed.values())):
            failures.append({'check': stage + ':exact-cover', 'error': 'Incomplete or duplicate assertion edges'})
    return {'slice_id': sid, 'predecessor': prior, 'reusable': not failures,
            'changed_runtime_roots': changed, 'failures': failures}


def main():
    request = load_json(ROOT / 'compact-vdd-projection-request.815c032b.v1.json')
    binding = request['currentQuickDev']
    old = load_json(ROOT / binding['receipt']['path'])
    bundle = load_json(ROOT / binding['semanticPlan']['path'])
    rows = []
    for original in old['predecessors']:
        sid = original['slice_id']
        selected = dict(original)
        if sid in SUCCESSORS:
            run = HERE / SUCCESSORS[sid]
            result_path = run / 'slice-ready-result.v2.json'
            selected = {'slice_id': sid, 'run_root': run.relative_to(ROOT).as_posix(),
                'result_ref': result_path.relative_to(ROOT).as_posix(),
                'result_sha256': sha256_value(load_json(result_path))}
        row = check(selected, bundle)
        row['selection'] = 'explicit-successor' if sid in SUCCESSORS else 'original-Q8-predecessor'
        rows.append(row)
        print(sid + ': ' + ('REUSABLE' if row['reusable'] else 'BLOCKED')
              + ' ' + ', '.join(x['check'] for x in row['failures']), flush=True)
    report = {'schema': 'quick-dev.read-only-reuse-diagnostic.v1',
        'authorizes': [], 'tests_launched': 0, 'evidence_rebound': False,
        'rows': rows, 'reusable_slices': [r['slice_id'] for r in rows if r['reusable']],
        'blocked_slices': [r['slice_id'] for r in rows if not r['reusable']]}
    create_json(Path(sys.argv[1]), report)
    print(json.dumps({k: report[k] for k in ('tests_launched', 'reusable_slices', 'blocked_slices')}), flush=True)


if __name__ == '__main__':
    main()
