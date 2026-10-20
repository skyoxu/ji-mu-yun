"""ADR-0041: initial S10 read-only missing-sidecar mode handling.

This entry implements the observed S10 result contract only. Sidecar validation,
policy/schema enforcement and the remaining Package A checks are not complete.
"""
from pathlib import Path


def _result(mode, status, exit_code, code):
    return {'schema': 'skill-quality-result.v1', 'mode': mode, 'status': status,
            'exit_code': exit_code, 'diagnostics': [{'code': code}], 'authorizes': []}


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
    # A present sidecar is not automatically valid. Later slices own its checks.
    return _result(mode, 'fail', 1, 'SIDECAR_VALIDATION_NOT_IMPLEMENTED')
