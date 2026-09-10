"""Contract-owned input mapping, independent of caller source labels (ADR-0060)."""
try:
    from .skill_input_protocol import contained, relative, identity
    from .skill_input_selection import READ_ROLES
except ImportError:
    from skill_input_protocol import contained, relative, identity
    from skill_input_selection import READ_ROLES


def verify_inputs(root, contract, operation, inputs, sources):
    operations = contract.get('operations', {})
    if operation not in operations or not isinstance(inputs, dict):
        raise ValueError('operation and explicit input mapping are required')
    required = operations[operation].get('required_inputs')
    roles = contract.get('source_roles')
    if not isinstance(required, list) or not required or not isinstance(roles, dict):
        raise ValueError('consumer contract must declare required inputs and source roles')
    if set(inputs) - set(roles) or not set(required) <= set(inputs):
        raise ValueError('required input missing or unknown selector')
    rows = {row['path']: row for row in sources}
    used = set()
    normalized = {}
    for selector, roots in sorted(inputs.items()):
        spec = roles[selector]
        if not isinstance(roots, list) or not roots or len(set(roots)) != len(roots):
            raise ValueError('input roots must be nonempty and unambiguous')
        for value in roots:
            path = contained(root, relative(value))
            kind = 'directory' if path.is_dir() else 'file' if path.is_file() else 'missing'
            if kind not in spec.get('allowed_kinds', []):
                raise ValueError('input root kind is missing or outside contract')
            members = {value} if kind == 'file' else {p for p in rows if p.startswith(value + '/')}
            selected = {p for p in members if p in rows and rows[p]['role'] in READ_ROLES}
            if not selected:
                raise ValueError('required input has no selected readable source')
            # A directory is a typed universe: every payload member needs a role.
            # Non-payload plan roots only identify explicitly selected plan inputs.
            if kind == 'directory' and spec.get('payload', True):
                actual = set()
                for member in path.rglob('*'):
                    rel = member.relative_to(root).as_posix()
                    contained(root, rel)
                    if member.is_file():
                        actual.add(rel)
                if not actual <= members:
                    raise ValueError('directory input contains untyped omitted sources')
            used.update(selected)
        normalized[selector] = sorted(roots)
    if not {p for p, row in rows.items() if row['role'] in READ_ROLES} <= used:
        raise ValueError('selected source is not mapped to a consumer input')
    return {'inputs': normalized, 'input_hash': identity(normalized)}
