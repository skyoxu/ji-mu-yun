"""Explicit typed source universe and verified read set (ADR-0060)."""
from __future__ import annotations
try:
    from .skill_input_protocol import contained, digest, identity, relative, check_hash
except ImportError:
    from skill_input_protocol import contained, digest, identity, relative, check_hash

ROLES = frozenset({'normative_source', 'authority_source', 'implementation_input', 'lifecycle_projection', 'derived_context', 'execution_evidence', 'report', 'ephemeral_attempt'})
READ_ROLES = frozenset({'normative_source', 'authority_source', 'implementation_input'})
FIELDS = {'role', 'path', 'module', 'resource_set', 'authority', 'sha256'}


def normalize(sources):
    rows, seen = [], set()
    for raw in sources:
        if not isinstance(raw, dict) or set(raw) != FIELDS:
            raise ValueError('typed selection fields are incomplete or unknown')
        if any(not isinstance(v, str) or not v.strip() for v in raw.values()):
            raise ValueError('typed selection fields must be nonempty strings')
        if raw['role'] not in ROLES:
            raise ValueError('unknown source role')
        relative(raw['path'])
        check_hash(raw['sha256'])
        key = raw['path'].casefold()
        if key in seen:
            raise ValueError('duplicate or ambiguous source path')
        seen.add(key)
        rows.append(dict(raw))
    if not rows or not any(row['role'] in READ_ROLES for row in rows):
        raise ValueError('required read set is empty')
    return sorted(rows, key=lambda row: row['path'])


def selection_identity(sources, *, consumer, policy_revision):
    if not isinstance(consumer, str) or not consumer or not isinstance(policy_revision, str) or not policy_revision:
        raise ValueError('consumer and policy revision are required')
    rows = normalize(sources)
    selection = {'consumer': consumer, 'policy_revision': policy_revision,
                 'sources': [{k: v for k, v in row.items() if k != 'sha256'} for row in rows]}
    return {'sourceSelectionHash': identity(selection),
            'sourceContentHash': identity({'selection': selection, 'sources': rows})}


def verify_selection(root, sources, *, consumer, policy_revision, allow_refresh=False):
    rows = normalize(sources)
    current, refreshed = [], []
    for row in rows:
        item = dict(row)
        if row['role'] in READ_ROLES:
            if row['path'].startswith(('logs/', '.skill-input-work/')):
                raise ValueError('runtime evidence cannot be a source authority')
            path = contained(root, row['path'])
            if not path.is_file():
                raise ValueError('required source is missing: ' + row['path'])
            actual = digest(path.read_bytes())
            if actual != row['sha256']:
                if not allow_refresh or row['role'] == 'authority_source':
                    raise ValueError('source or authority drift: ' + row['path'])
                refreshed.append(row['path'])
                item['sha256'] = actual
        current.append(item)
    return {'sources': current, 'read_set': [r['path'] for r in current if r['role'] in READ_ROLES],
            'refreshed': refreshed, **selection_identity(current, consumer=consumer, policy_revision=policy_revision)}
