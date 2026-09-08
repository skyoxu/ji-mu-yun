"""ADR-0041: revalidate completed stages and stop before duplicate execution."""
from pathlib import Path
from runtime_evidence import load_json, sha256_value, sha256_bytes, hash_refs, resolve_file
from repeat_guard import repeat_guard


def input_binding(workspace, bundle, descriptor, profile):
    selected = next(s for s in bundle['slices'] if s['slice_id'] == descriptor['slice_id'])
    paths = set(selected.get('production_owners', [])) | set(selected.get('allowed_write_paths', []))
    paths.update(selected.get('execution_snapshot_paths', []))
    hashes = {p: sha256_bytes((workspace / p).read_bytes()) if (workspace / p).is_file() else None for p in sorted(paths)}
    if 'behavior_routing' in bundle:
        from behavior_routing import production_hashes
        hashes.update(production_hashes(workspace, bundle, descriptor['slice_id']))
    engine = {name: sha256_bytes(Path(__file__).with_name(name).read_bytes()) for name in ('stage_reentry.py', 'stage_pipeline.py', 'independent_judge_v2.py', 'case_evidence.py', 'pytest_case_collector.py', 'regression_gate.py')}
    return {'engine_sha256': engine, 'plan_sha256': sha256_value(bundle), 'descriptor_sha256': sha256_value(descriptor),
            'profile': profile, 'candidate_paths': hashes,
            'targets': hash_refs(workspace, descriptor['target_refs']),
            'fixtures': hash_refs(workspace, descriptor['fixture_refs'])}


def existing_result(workspace, bundle, run_dir, descriptor, profile):
    """No inference from other runs. Incomplete or stale bytes never execute again."""
    evidence = run_dir / 'canonical-evidence' / descriptor['stage']
    if not evidence.exists():
        return None
    try:
        result = load_json(evidence / 'stage-result.v2.json')
        binding = load_json(evidence / 'execution-input.v1.json')
        if binding != input_binding(workspace, bundle, descriptor, profile):
            raise ValueError('execution input changed')
        receipt = load_json(evidence / 'process-receipt.v2.json')
        observation = load_json(evidence / 'observation.v2.json')
        for key, value in [('descriptor_sha256', sha256_value(descriptor)), ('receipt_sha256', sha256_value(receipt)), ('observation_sha256', sha256_value(observation))]:
            if result.get(key) != value:
                raise ValueError('stage evidence binding changed')
        if receipt.get('descriptor_sha256') != sha256_value(descriptor) or observation.get('receipt_sha256') != sha256_value(receipt):
            raise ValueError('receipt lineage changed')
        for key in ('plan_id', 'slice_id', 'run_id', 'stage', 'candidate_hash'):
            if result.get(key) != descriptor[key]:
                raise ValueError('stage identity changed')
        for key in ('predicate_result', 'verification_outcome', 'failure_family', 'failure_id', 'failure_fingerprint'):
            if result.get(key) != observation.get(key):
                raise ValueError('observation result changed')
        for name in ('stdout', 'stderr'):
            if sha256_bytes((evidence / (name + '.bin')).read_bytes()) != receipt.get(name + '_sha256'):
                raise ValueError('process output changed')
        if receipt.get('case_report') is not None and receipt.get('case_report_sha256') != sha256_value(receipt['case_report']):
            raise ValueError('case report changed')
        for ref in result['runtime_edges']:
            if sha256_value(load_json(resolve_file(run_dir, ref['path']))) != ref['sha256']:
                raise ValueError('runtime edge changed')
        gate = result.get('regression_gate')
        if gate and sha256_value(load_json(resolve_file(run_dir, gate['ref']))) != gate['sha256']:
            raise ValueError('regression gate changed')
        seal = load_json(evidence / 'execution-complete.v1.json')
        if seal != {'result_sha256': sha256_value(result), 'input_sha256': sha256_value(binding)}:
            raise ValueError('completion binding changed')
        return result
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError('stage-reentry-blocked: incomplete or stale evidence; preserve this run and recover or start an explicit new run: ' + str(exc)) from exc


def check_history(run_dir, descriptor, history=None):
    # Explicit argument or one fixed run-local file; never glob or choose latest.
    path = run_dir / 'failure-history.json'
    if history is None:
        if path.is_file():
            import json
            history = json.loads(path.read_text(encoding='utf-8'))
        else:
            history = []
    if not isinstance(history, list):
        raise ValueError('failure history must be an explicit ordered list')
    return repeat_guard(descriptor=descriptor, history=history)
