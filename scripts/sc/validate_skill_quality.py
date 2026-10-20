"""ADR-0041: incremental read-only S10 mode and S3 dependency diagnostics.

Only missing-sidecar outcomes and local dependency diagnostics are implemented.
Full sidecar/policy/schema validation and the remaining Package A checks are not
complete; other sidecar inputs continue to fail closed.
"""
import json
from pathlib import Path, PureWindowsPath
import re


def _result(mode, status, exit_code, code):
    return {'schema': 'skill-quality-result.v1', 'mode': mode, 'status': status,
            'exit_code': exit_code, 'diagnostics': [{'code': code}], 'authorizes': []}



def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _read_object(path):
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object')
    return value


def _authority_file(package, reference):
    # Validate lexical and filesystem containment before any authority read.
    if (not isinstance(reference, str) or not reference or '\\' in reference
            or PureWindowsPath(reference).drive or '://' in reference):
        raise ValueError('Invalid local authority')
    relative = Path(reference)
    if relative.is_absolute() or any(part in {'.', '..'} for part in reference.split('/')):
        raise ValueError('Invalid local authority')
    current = package
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symbolic authority path')
    target = current.resolve(strict=True)
    target.relative_to(package)
    if not target.is_file():
        raise ValueError('Unavailable local authority')
    return target


def _dependency_diagnostics(package, contract):
    diagnostics = []

    def emit(code, pointer, identity=None):
        diagnostic = {'rule': 'A09', 'code': code,
                      'path': 'skill-quality.v1.json#' + pointer,
                      'message': 'The local dependency declaration does not satisfy its contract.'}
        # Only a canonical machine identity may be returned, never raw content.
        if isinstance(identity, str) and re.fullmatch(r'[a-z][a-z0-9-]{0,63}', identity):
            diagnostic['dependency_id'] = identity
        diagnostics.append(diagnostic)

    records = contract.get('dependencies', [])
    entries = contract.get('entrypoints', [])
    if not isinstance(records, list) or not isinstance(entries, list):
        emit('DEPENDENCY_INVALID_RECORD', '/dependencies')
        return diagnostics
    by_id = {}
    for index, record in enumerate(records):
        pointer = '/dependencies/' + str(index)
        if not isinstance(record, dict):
            emit('DEPENDENCY_INVALID_RECORD', pointer)
            continue
        identity = record.get('id')
        if (not isinstance(identity, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', identity)
                or identity in by_id):
            emit('DEPENDENCY_INVALID_RECORD', pointer, identity)
            continue
        by_id[identity] = record
        try:
            authority = _read_object(_authority_file(package, record.get('authority')))
            if authority.get('id') != identity or not isinstance(authority.get('version'), str):
                raise ValueError('Unresolved dependency identity')
        except (OSError, ValueError, RuntimeError, UnicodeError):
            emit('DEPENDENCY_UNRESOLVED_AUTHORITY', pointer + '/authority', identity)
            continue
        if not isinstance(record.get('version'), str) or record['version'] != authority['version']:
            emit('DEPENDENCY_VERSION_CONFLICT', pointer + '/version', identity)
    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(entry.get('dependencies', []), list):
            emit('DEPENDENCY_INVALID_RECORD', '/entrypoints/' + str(entry_index))
            continue
        for dep_index, identity in enumerate(entry.get('dependencies', [])):
            if not isinstance(identity, str) or identity not in by_id:
                emit('DEPENDENCY_MISSING_RECORD',
                     '/entrypoints/' + str(entry_index) + '/dependencies/' + str(dep_index), identity)
    return sorted(diagnostics, key=lambda row: (row['rule'], row['path'], row['code']))


def validate_package(inspection_root, package_root, *, mode=None):
    mode = 'strict' if mode is None else mode
    if mode not in {'strict', 'inventory'}:
        return _result(mode, 'fail', 2, 'INVALID_MODE')
    inspection = Path(inspection_root)
    package = Path(package_root)
    try:
        root = inspection.resolve(strict=True)
        target = package.resolve(strict=True)
        target.relative_to(root)
        # An inspectable package remains contained and is never modified.
        if inspection.is_symlink() or package.is_symlink() or not target.is_dir():
            return _result(mode, 'fail', 2, 'INVALID_PACKAGE_ROOT')
        current = package.absolute()
        while current != root and root in current.parents:
            if current.is_symlink():
                return _result(mode, 'fail', 2, 'INVALID_PACKAGE_ROOT')
            current = current.parent
        skill = target/'SKILL.md'
        sidecar = target/'skill-quality.v1.json'
        if skill.is_symlink() or not skill.is_file() or sidecar.is_symlink():
            return _result(mode, 'fail', 2, 'UNINSPECTABLE_PACKAGE')
        if not sidecar.exists():
            status, code = ('legacy', 3) if mode == 'inventory' else ('fail', 1)
            return _result(mode, status, code, 'MISSING_QUALITY_SIDECAR')
    except (OSError, ValueError, RuntimeError):
        return _result(mode, 'fail', 2, 'INVALID_PACKAGE_ROOT')
    try:
        contract = _read_object(sidecar)
    except (OSError, ValueError, RuntimeError, UnicodeError):
        return _result(mode, 'fail', 1, 'INVALID_QUALITY_SIDECAR')
    diagnostics = _dependency_diagnostics(target, contract)
    if diagnostics:
        result = _result(mode, 'fail', 1, 'DEPENDENCY_CONTRACT_FAILURE')
        result['diagnostics'] = diagnostics
        return result
    # Dependency conformance alone must never imply full package conformance.
    return _result(mode, 'fail', 1, 'SIDECAR_VALIDATION_NOT_IMPLEMENTED')
