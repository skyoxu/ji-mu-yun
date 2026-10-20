"""ADR-0041: real-entry A09 diagnostics, with frozen independent oracles."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.sc.tests.skill_quality_support import dependency_package, write_contract
from scripts.sc.validate_skill_quality import validate_package


def _require(condition, message):
    if not condition:
        print('FAILURE_ID:DEPENDENCY_DIAGNOSTIC_OUTCOME_MISSING')
    assert condition, message


@pytest.mark.parametrize('defect,code,pointer', [
    pytest.param('missing-record', 'DEPENDENCY_MISSING_RECORD',
                 'skill-quality.v1.json#/entrypoints/0/dependencies/0',
                 marks=pytest.mark.cer_assertion('A-668FC5F50610-MISSING-RECORD'),
                 id='missing-record'),
    pytest.param('unresolved-authority', 'DEPENDENCY_UNRESOLVED_AUTHORITY',
                 'skill-quality.v1.json#/dependencies/0/authority',
                 marks=pytest.mark.cer_assertion('A-668FC5F50610-UNRESOLVED-AUTHORITY'),
                 id='unresolved-authority'),
    pytest.param('no-execution', None, None,
                 marks=pytest.mark.cer_assertion('A-668FC5F50610-NO-DEPENDENCY-EXECUTION'),
                 id='no-execution'),
    pytest.param('version-conflict', 'DEPENDENCY_VERSION_CONFLICT',
                 'skill-quality.v1.json#/dependencies/0/version',
                 marks=pytest.mark.cer_assertion('A-668FC5F50610-VERSION-CONFLICT'),
                 id='version-conflict'),
])
def test_a09(tmp_path, monkeypatch, defect, code, pointer):
    if defect == 'no-execution':
        _observe_no_execution(tmp_path, monkeypatch)
        return
    root, package, original = dependency_package(tmp_path)
    value = json.loads(json.dumps(original))
    if defect == 'missing-record':
        value['dependencies'] = []
    elif defect == 'unresolved-authority':
        value['dependencies'][0]['authority'] = 'references/missing.json'
    else:
        value['dependencies'][0]['version'] = '9.9.9'
    write_contract(package, value)
    # Use the real extant callable; public keyword/CLI parity is owned by A24.
    result = validate_package(root, package, mode='strict')
    diagnostics = result.get('diagnostics', []) if isinstance(result, dict) else []
    _require(isinstance(result, dict) and result.get('status') == 'fail'
             and result.get('exit_code') == 1 and result.get('authorizes') == [],
             'The defective package must produce a non-authorizing package failure')
    expected = {'rule': 'A09', 'code': code, 'path': pointer, 'dependency_id': 'local-parser'}
    _require(any(all(d.get(k) == v for k, v in expected.items()) for d in diagnostics),
             'The real validator must identify this dependency and defect, not an unrelated failure')
    rendered = json.dumps(result)
    _require(str(root) not in rendered and '9.9.9' not in rendered,
             'Diagnostic output must not echo absolute paths or arbitrary inspected versions')
    write_contract(package, original)
    repaired = validate_package(root, package, mode='strict')
    _require(isinstance(repaired, dict) and repaired.get('authorizes') == []
             and not any(d.get('rule') == 'A09' for d in repaired.get('diagnostics', [])),
             'Repairing only this dependency defect must remove its dependency diagnostic')


def _observe_no_execution(tmp_path, monkeypatch):
    root, package, _ = dependency_package(tmp_path)
    calls = []

    def denied(*args, **kwargs):
        calls.append('external-operation')
        raise RuntimeError('Static declaration inspection must not execute or fetch')

    for target, name in ((subprocess, 'Popen'), (subprocess, 'run'),
                         (socket, 'socket'), (socket, 'create_connection'),
                         (urllib.request, 'urlopen')):
        monkeypatch.setattr(target, name, denied)
    before = {p.relative_to(root).as_posix(): p.read_bytes()
              for p in root.rglob('*') if p.is_file()}
    result = validate_package(root, package, mode='strict')
    _require(not calls and isinstance(result, dict) and result.get('authorizes') == [],
             'Dependency inspection must not execute, install, fetch or grant authority')
    after = {p.relative_to(root).as_posix(): p.read_bytes()
             for p in root.rglob('*') if p.is_file()}
    _require(after == before, 'Static inspection must preserve all fixture bytes')
