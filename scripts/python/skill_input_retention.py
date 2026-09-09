"""Leased attempts, explicit reference protection and approved GC (ADR-0060)."""
from __future__ import annotations
import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path
try:
    from .skill_input_protocol import contained, name, read_json, atomic_json, immutable_json, identity, digest
    from .skill_input_current import resolve_current
    from .skill_input_generation import read_generation
except ImportError:
    from skill_input_protocol import contained, name, read_json, atomic_json, immutable_json, identity, digest
    from skill_input_current import resolve_current
    from skill_input_generation import read_generation

KINDS = {'lifecycle', 'authorization', 'terminal', 'acceptance'}
STATES = {'active', 'failed', 'succeeded', 'expired'}


def clock(value=None):
    value = time.time() if value is None else value
    if type(value) not in (int, float) or not 0 <= value < 1e12:
        raise ValueError('invalid clock')
    return value


def attempt_path(repository_root, plan_id, attempt_id):
    return contained(repository_root, '.skill-input-work/' + name(plan_id) + '/' + name(attempt_id))


def start_attempt(repository_root, plan_id, attempt_id, *, lease_seconds=300, now=None):
    now = clock(now)
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 86400:
        raise ValueError('invalid lease duration')
    path = attempt_path(repository_root, plan_id, attempt_id)
    path.mkdir(parents=True, exist_ok=False)
    state = {'schema_version': 'skill-input-attempt.v2', 'plan_id': plan_id, 'attempt_id': attempt_id,
             'status': 'active', 'heartbeat': now, 'lease_until': now + lease_seconds,
             'generation_ids': [], 'authorizes': []}
    atomic_json(path / 'attempt.json', state)
    return state


def update_attempt(repository_root, plan_id, attempt_id, *, status='active', generation_ids=(), lease_seconds=300, now=None):
    now = clock(now)
    path = attempt_path(repository_root, plan_id, attempt_id)
    state = read_json(contained(path, 'attempt.json'))
    if state.get('status') != 'active' or state.get('plan_id') != plan_id or state.get('attempt_id') != attempt_id:
        raise ValueError('attempt transition requires active matching predecessor')
    if now < state['heartbeat'] or now >= state['lease_until']:
        raise ValueError('attempt lease expired or clock regressed')
    if status not in STATES or type(lease_seconds) is not int or not 1 <= lease_seconds <= 86400:
        raise ValueError('invalid attempt transition')
    state.update(status=status, heartbeat=now, lease_until=now + lease_seconds if status == 'active' else now,
                 generation_ids=sorted({name(g) for g in generation_ids} | set(state['generation_ids'])))
    atomic_json(path / 'attempt.json', state)
    return state


def register_reference(root, repository_root, *, reference_id, kind, artifact_path, generation_ids):
    if kind not in KINDS or not generation_ids:
        raise ValueError('invalid retention reference')
    artifact = contained(repository_root, artifact_path)
    body = read_json(artifact)
    ids = _generation_ids(body)
    if not set(generation_ids) <= ids:
        raise ValueError('artifact does not reference declared generations')
    for value in generation_ids:
        read_generation(root, value)
    row = {'kind': kind, 'artifact_path': artifact_path, 'sha256': digest(artifact.read_bytes()),
           'generation_ids': sorted(set(generation_ids)), 'authorizes': []}
    immutable_json(contained(root, 'references/' + name(reference_id) + '.json'), row)
    return row


def _generation_ids(value):
    result = set()
    if isinstance(value, dict):
        if isinstance(value.get('generation_id'), str):
            result.add(value['generation_id'])
        if isinstance(value.get('generation_ids'), list):
            result.update(value['generation_ids'])
        for item in value.values():
            result.update(_generation_ids(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_generation_ids(item))
    return result


def _tree(path):
    rows = []
    for item in sorted(path.rglob('*')):
        contained(path, item.relative_to(path).as_posix())
        if item.is_file():
            raw = item.read_bytes()
            rows.append({'path': item.relative_to(path).as_posix(), 'sha256': digest(raw), 'bytes': len(raw)})
        elif not item.is_dir():
            raise ValueError('unsupported retention object')
    return {'tree_hash': identity(rows), 'bytes': sum(r['bytes'] for r in rows)}


def _head(repository_root):
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repository_root, capture_output=True, text=True, shell=False)
    return result.stdout.strip() if result.returncode == 0 else None


def plan_retention(root, *, repository_root=None, plan_id='default', dry_run=True, now=None, retention_seconds=86400):
    root = Path(root).absolute()
    repository_root = Path(repository_root or root).absolute()
    root.relative_to(repository_root)
    now = clock(now)
    if type(retention_seconds) is not int or retention_seconds < 0:
        raise ValueError('invalid retention duration')
    protected, candidates = [], []
    protected_ids = set()
    current = resolve_current(root)
    if current:
        protected_ids.add(current['generation_id'])
        protected.append({'object': current['generation_id'], 'reason': 'current-generation'})
    refs = contained(root, 'references')
    if refs.exists():
        for item in sorted(refs.iterdir()):
            contained(refs, item.name)
            row = read_json(item)
            artifact = contained(repository_root, row['artifact_path'])
            if row.get('kind') not in KINDS or digest(artifact.read_bytes()) != row['sha256'] or not set(row['generation_ids']) <= _generation_ids(read_json(artifact)):
                raise ValueError('stale retention reference; repair before GC')
            protected_ids.update(row['generation_ids'])
            protected.append({'object': item.name, 'reason': row['kind'] + '-reference'})
    attempts = contained(repository_root, '.skill-input-work/' + name(plan_id))
    if attempts.exists():
        for path in sorted(attempts.iterdir()):
            contained(attempts, path.name)
            state = read_json(contained(path, 'attempt.json'))
            if state.get('schema_version') != 'skill-input-attempt.v2' or state.get('status') not in STATES or state.get('plan_id') != plan_id or state.get('attempt_id') != path.name or state.get('authorizes') != []:
                raise ValueError('invalid attempt metadata; repair before GC')
            heartbeat, lease_until = clock(state['heartbeat']), clock(state['lease_until'])
            if state['status'] == 'active' and lease_until > now:
                protected_ids.update(state['generation_ids'])
                protected.append({'object': path.relative_to(repository_root).as_posix(), 'reason': 'active-lease'})
            elif now - max(heartbeat, lease_until) < retention_seconds:
                protected_ids.update(state['generation_ids'])
                protected.append({'object': path.relative_to(repository_root).as_posix(), 'reason': 'retention-window'})
            else:
                candidates.append({'path': path.relative_to(repository_root).as_posix(), 'reason': 'expired-unreferenced-attempt', **_tree(path)})
    generations = contained(root, 'skill-input-generations')
    if generations.exists():
        for path in sorted(generations.iterdir()):
            contained(generations, path.name)
            # Incomplete staging remains diagnostic evidence; never delete implicitly.
            if path.name.startswith('.staging-'):
                protected.append({'object': path.name, 'reason': 'incomplete-staging'})
                continue
            read_generation(root, path.name)
            if path.name in protected_ids:
                continue
            if now - path.stat().st_mtime < retention_seconds:
                protected.append({'object': path.name, 'reason': 'retention-window'})
                continue
            candidates.append({'path': path.relative_to(repository_root).as_posix(), 'reason': 'unreferenced-generation', **_tree(path)})
    value = {'schema_version': 'skill-input-retention-plan.v2', 'mode': 'dry-run' if dry_run else 'apply',
             'root': root.relative_to(repository_root).as_posix(), 'plan_id': plan_id,
             'retention_seconds': retention_seconds, 'predecessor_commit': _head(repository_root),
             'candidates': sorted(candidates, key=lambda x: x['path']), 'protected': protected, 'authorizes': []}
    value['plan_hash'] = identity(value)
    return value


def apply_retention(root, *, approval, repository_root=None, plan_id='default', retention_seconds=86400, now=None):
    if approval is None:
        return {'status': 'approval-required'}
    repository_root = Path(repository_root or root).absolute()
    plan = plan_retention(root, repository_root=repository_root, plan_id=plan_id, retention_seconds=retention_seconds, now=now)
    if not isinstance(approval, dict) or set(approval) != {'schema_version', 'approved_by', 'plan_hash', 'predecessor_commit'} or approval['schema_version'] != 'skill-input-gc-approval.v1' or approval['approved_by'] != 'maintainer' or approval['plan_hash'] != plan['plan_hash'] or not plan['predecessor_commit'] or approval['predecessor_commit'] != plan['predecessor_commit']:
        raise ValueError('explicit maintainer approval does not bind current GC plan and commit')
    receipt_dir = contained(root, 'cleanup-receipts')
    run = uuid.uuid4().hex
    result = {'schema_version': 'skill-input-cleanup.v2', 'status': 'started', 'plan': plan,
              'approval_hash': identity(approval), 'removed': [], 'authorizes': []}
    immutable_json(receipt_dir / (run + '.started.json'), result)
    try:
        for row in plan['candidates']:
            path = contained(repository_root, row['path'])
            if _tree(path) != {k: row[k] for k in ('tree_hash', 'bytes')}:
                raise ValueError('cleanup candidate changed')
            shutil.rmtree(path)
            result['removed'].append(row)
        result['status'] = 'complete'
    except Exception:
        result['status'] = 'failed'
        raise
    finally:
        immutable_json(receipt_dir / (run + '.result.json'), result)
    return result
