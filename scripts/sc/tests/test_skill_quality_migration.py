"""ADR-0041: S10 real-entry checks for missing-sidecar inventory/strict behavior."""
from hashlib import sha256
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.sc.validate_skill_quality import validate_package


@pytest.fixture
def legacy_package(tmp_path):
    inspection = tmp_path/'inspection'
    package = inspection/'legacy-skill'
    package.mkdir(parents=True)
    (package/'SKILL.md').write_text('---\nname: legacy-skill\ndescription: A pre-standard example.\n---\n\n# Legacy Skill\n\nInspect existing files.\n', encoding='utf-8')
    return inspection, package


def _files(root):
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def _check(result, expected_status, expected_exit, failure_id):
    valid = (isinstance(result, dict) and result.get('status') == expected_status
             and result.get('exit_code') == expected_exit and result.get('authorizes') == [])
    if not valid:
        print('FAILURE_ID:' + failure_id)
    assert valid, 'Actual validator result does not satisfy the declared mode outcome'


@pytest.mark.cer_assertion('A22_STRICT_REJECTS_PRESTANDARD')
def test_strict_mode_rejects_prestandard_fixture(legacy_package):
    inspection, package = legacy_package
    before = _files(inspection)
    result = validate_package(inspection, package, mode='strict')
    _check(result, 'fail', 1, 'STRICT_PRESTANDARD_ACCEPTED')
    assert _files(inspection) == before


@pytest.mark.parametrize('mode,status,exit_code', [
    pytest.param('inventory', 'legacy', 3, id='inventory-legacy',
                 marks=pytest.mark.cer_assertion('ASSERT-O-CDE014A7614A-INVENTORY-LEGACY')),
    pytest.param('strict', 'fail', 1, id='strict-fail',
                 marks=pytest.mark.cer_assertion('ASSERT-O-CDE014A7614A-STRICT-FAIL')),
])
def test_a22(legacy_package, mode, status, exit_code):
    inspection, package = legacy_package
    before = _files(inspection)
    result = validate_package(inspection, package, mode=mode)
    _check(result, status, exit_code, 'MISSING_SIDECAR_MODE_OUTCOME_RED')
    assert _files(inspection) == before
