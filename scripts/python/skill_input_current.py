"""Single validated current pointer; no history scan (ADR-0060)."""
from __future__ import annotations
try:
    from .skill_input_protocol import atomic_json, contained, identity, read_json
    from .skill_input_generation import read_generation
except ImportError:
    from skill_input_protocol import atomic_json, contained, identity, read_json
    from skill_input_generation import read_generation


def resolve_current(root):
    pointer = contained(root, 'current.v1.json')
    if not pointer.exists():
        return None
    value = read_json(pointer)
    if not isinstance(value, dict) or set(value) != {'schema_version', 'generation_id', 'receipt_hash', 'authorizes'} or value['schema_version'] != 'skill-input-current.v2' or value['authorizes'] != []:
        raise ValueError('current pointer schema is invalid')
    payload = read_generation(root, value['generation_id'])
    if value['receipt_hash'] != identity(payload['receipt']):
        raise ValueError('current receipt binding mismatch')
    return value


def advance_current(root, generation_id, *, expected_current, repository_root, consumer, operation, contract_path):
    try:
        from .skill_input_v2 import validate_generation
    except ImportError:
        from skill_input_v2 import validate_generation
    validate_generation(repository_root, root, generation_id, consumer=consumer,
                        operation=operation, contract_path=contract_path)
    payload = read_generation(root, generation_id)
    current = resolve_current(root)
    if current != expected_current:
        raise ValueError('current pointer changed during publication')
    value = {'schema_version': 'skill-input-current.v2', 'generation_id': generation_id,
             'receipt_hash': identity(payload['receipt']), 'authorizes': []}
    atomic_json(contained(root, 'current.v1.json'), value)
    return value
