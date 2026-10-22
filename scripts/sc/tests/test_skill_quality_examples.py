"""ADR-0041: real-entry A09 diagnostics, with frozen independent oracles."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.sc.tests.skill_quality_support import dependency_package, write_contract, invocation_args, prepare_example_scenario, POLICY
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
    args,kwargs=invocation_args(validate_package,root,package)
    result = validate_package(*args, **kwargs)
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
    args,kwargs=invocation_args(validate_package,root,package)
    repaired = validate_package(*args, **kwargs)
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
    args,kwargs=invocation_args(validate_package,root,package)
    result = validate_package(*args, **kwargs)
    _require(not calls and isinstance(result, dict) and result.get('authorizes') == [],
             'Dependency inspection must not execute, install, fetch or grant authority')
    after = {p.relative_to(root).as_posix(): p.read_bytes()
             for p in root.rglob('*') if p.is_file()}
    _require(after == before, 'Static inspection must preserve all fixture bytes')

@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('examples:typical', 'CER-SM-A07-TYPICAL-ROUTE', ['FAIL_SM_A07_TYPICAL_ROUTE'], id='O-21665ADEBC0E-examples-typical-CER-SM-A07-TYPICAL-ROUTE', marks=pytest.mark.cer_assertion('CER-SM-A07-TYPICAL-ROUTE')),
    pytest.param('examples:order', 'A-778F29E8E1FF', ['PRIMARY_ORDER_CONSTRAINT_FAIL'], id='O-462F64A686EA-examples-order-A-778F29E8E1FF', marks=pytest.mark.cer_assertion('A-778F29E8E1FF')),
    pytest.param('examples:expected_result', 'A07_EXPECTED_RESULT_LINKAGE', ['A07_EXPECTED_RESULT_LINKAGE_FAIL'], id='O-4C4BC3184CDC-examples-expected_result-A07_EXPECTED_RESULT_LINKAGE', marks=pytest.mark.cer_assertion('A07_EXPECTED_RESULT_LINKAGE')),
    pytest.param('examples:error', 'A-1E6B1E1F3C5F-1', ['PRIMARY_ROUTE_COVERAGE'], id='O-7657CD1586FC-examples-error-A-1E6B1E1F3C5F-1', marks=pytest.mark.cer_assertion('A-1E6B1E1F3C5F-1')),
    pytest.param('examples:output', 'A07-PRIMARY-EXAMPLE-OUTPUT-NONEMPTY', ['A07_OUTPUT_REQUIRED'], id='O-7902256EFC28-examples-output-A07-PRIMARY-EXAMPLE-OUTPUT-NONEMPTY', marks=pytest.mark.cer_assertion('A07-PRIMARY-EXAMPLE-OUTPUT-NONEMPTY')),
    pytest.param('examples:count', 'REPAIR_O_8CC763357B93', [], id='O-8CC763357B93-examples-count-REPAIR_O_8CC763357B93', marks=pytest.mark.cer_assertion('REPAIR_O_8CC763357B93')),
    pytest.param('examples:order', 'REPAIR_O_8CC763357B93', [], id='O-8CC763357B93-examples-order-REPAIR_O_8CC763357B93', marks=pytest.mark.cer_assertion('REPAIR_O_8CC763357B93')),
    pytest.param('examples:input', 'REPAIR_O_8CC763357B93', [], id='O-8CC763357B93-examples-input-REPAIR_O_8CC763357B93', marks=pytest.mark.cer_assertion('REPAIR_O_8CC763357B93')),
    pytest.param('examples:output', 'REPAIR_O_8CC763357B93', [], id='O-8CC763357B93-examples-output-REPAIR_O_8CC763357B93', marks=pytest.mark.cer_assertion('REPAIR_O_8CC763357B93')),
    pytest.param('examples:duplicate-branch', 'REPAIR_O_8CC763357B93', [], id='O-8CC763357B93-examples-duplicate-branch-REPAIR_O_8CC763357B93', marks=pytest.mark.cer_assertion('REPAIR_O_8CC763357B93')),
    pytest.param('examples:unknown-branch', 'REPAIR_O_8CC763357B93', [], id='O-8CC763357B93-examples-unknown-branch-REPAIR_O_8CC763357B93', marks=pytest.mark.cer_assertion('REPAIR_O_8CC763357B93')),
    pytest.param('examples:duplicate-pair', 'REPAIR_O_8CC763357B93', [], id='O-8CC763357B93-examples-duplicate-pair-REPAIR_O_8CC763357B93', marks=pytest.mark.cer_assertion('REPAIR_O_8CC763357B93')),
    pytest.param('examples:supplemental', 'A07-SUPPLEMENTAL-PRIMARY-SET-INVARIANCE', [], id='O-9CC283E0F2C9-examples-supplemental-A07-SUPPLEMENTAL-PRIMARY-SET-INVARIANCE', marks=pytest.mark.cer_assertion('A07-SUPPLEMENTAL-PRIMARY-SET-INVARIANCE')),
    pytest.param('examples:duplicate-branch', 'A07_DISTINCT_DECLARED_OUTCOME_BINDING', ['A07_DISTINCT_OUTCOME_BINDING'], id='O-A0C93CDA60F8-examples-duplicate-branch-A07_DISTINCT_DECLARED_OUTCOME_BINDING', marks=pytest.mark.cer_assertion('A07_DISTINCT_DECLARED_OUTCOME_BINDING')),
    pytest.param('examples:input', 'A07_INPUT_NONEMPTY', ['A07_INPUT_EMPTY_REJECTED'], id='O-BA46FB443203-examples-input-A07_INPUT_NONEMPTY', marks=pytest.mark.cer_assertion('A07_INPUT_NONEMPTY')),
    pytest.param('examples:boundary', 'A07_BOUNDARY_ROUTE_PRIMARY_EXAMPLE', ['A07_BOUNDARY_ROUTE_MISSING'], id='O-C853521D6F42-examples-boundary-A07_BOUNDARY_ROUTE_PRIMARY_EXAMPLE', marks=pytest.mark.cer_assertion('A07_BOUNDARY_ROUTE_PRIMARY_EXAMPLE')),
    pytest.param('examples:count', 'assert-primary-example-count-three', ['PRIMARY_EXAMPLE_COUNT_INVALID'], id='O-ED23C6AA5BA7-examples-count-assert-primary-example-count-three', marks=pytest.mark.cer_assertion('assert-primary-example-count-three')),
])
def test_a07(tmp_path,monkeypatch,scenario,assertion,failure_ids):
    root,package,mode,oracle=prepare_example_scenario(tmp_path,scenario)
    control=None
    kind,detail=scenario.split(':',1)
    baseline={'examples':'examples:positive','routing':'routing:positive','dependency':'dependency:optional' if detail.startswith('optional') else 'dependency:positive','entry':'entry:positive','invocation':'invocation:positive','faq':'faq:positive'}
    if detail not in {'positive','leaf','supplemental','none','no-execution'}:
        control=prepare_example_scenario(tmp_path/'control',baseline[kind])
    effects=[];helper_calls=[]
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Static package validation may not execute or fetch')
    from scripts.sc import skill_quality_examples
    original=skill_quality_examples.validate_examples
    def observed(contract):
        helper_calls.append(True)
        return original(contract)
    with monkeypatch.context() as patch:
        patch.setattr(skill_quality_examples,'validate_examples',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
        control_valid=True
        if control:
            control_root,control_package,control_mode,control_oracle=control
            control_args,control_kwargs=invocation_args(validate_package,control_root,control_package,control_mode)
            control_result=validate_package(*control_args,**control_kwargs)
            control_valid=control_oracle(control_result)
    valid=not effects and oracle(result) and control_valid
    if assertion=='A-CEE0E00D83B6-MAIN-CONSUMES':valid=valid and len(helper_calls)==1
    if not valid:
        for failure_id in failure_ids:print('FAILURE_ID:'+failure_id)
    assert valid, 'The actual declaration check does not satisfy: '+scenario+' / '+assertion

@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('routing:missing', 'A-O-1E3688B1827F-1', ['MISSING_DIAGRAM_ACCEPTANCE_FAILURE'], id='O-1D2669330EF3-routing-positive-A-O-1E3688B1827F-1', marks=pytest.mark.cer_assertion('A-O-1E3688B1827F-1')),
    pytest.param('routing:missing', 'A08-MISSING-DIAGRAM-FAIL', ['FAIL_MISSING_DIAGRAM_NOT_REJECTED'], id='O-90DFBCA3F781-routing-missing-A08-MISSING-DIAGRAM-FAIL', marks=pytest.mark.cer_assertion('A08-MISSING-DIAGRAM-FAIL')),
    pytest.param('routing:non-ascii', 'A08-ASCII-DIAGRAM-FORMAT', ['FAIL_DIAGRAM_NON_ASCII_ACCEPTED'], id='O-A33009E56C6D-routing-non-ascii-A08-ASCII-DIAGRAM-FORMAT', marks=pytest.mark.cer_assertion('A08-ASCII-DIAGRAM-FORMAT')),
    pytest.param('routing:leaf', 'A08-LEAF-NA-EXPLICIT', ['FAIL_LEAF_NA_IMPLICIT'], id='O-A4545FEAA107-routing-leaf-A08-LEAF-NA-EXPLICIT', marks=pytest.mark.cer_assertion('A08-LEAF-NA-EXPLICIT')),
    pytest.param('routing:unreachable', 'A08-PRIMARY-ROUTES-REACHABLE', ['FAIL_PRIMARY_ROUTE_BRANCH_MISSING'], id='O-A7D59E45EA2B-routing-unreachable-A08-PRIMARY-ROUTES-REACHABLE', marks=pytest.mark.cer_assertion('A08-PRIMARY-ROUTES-REACHABLE')),
    pytest.param('routing:missing', 'A08_DECISION_DIAGRAM_LINKAGE', [], id='O-E140B558211D-routing-positive-A08_DECISION_DIAGRAM_LINKAGE', marks=pytest.mark.cer_assertion('A08_DECISION_DIAGRAM_LINKAGE')),
])
def test_a08(tmp_path,monkeypatch,scenario,assertion,failure_ids):
    root,package,mode,oracle=prepare_example_scenario(tmp_path,scenario)
    control=None
    kind,detail=scenario.split(':',1)
    baseline={'examples':'examples:positive','routing':'routing:positive','dependency':'dependency:optional' if detail.startswith('optional') else 'dependency:positive','entry':'entry:positive','invocation':'invocation:positive','faq':'faq:positive'}
    if detail not in {'positive','leaf','supplemental','none','no-execution'}:
        control=prepare_example_scenario(tmp_path/'control',baseline[kind])
    effects=[];helper_calls=[]
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Static package validation may not execute or fetch')
    from scripts.sc import skill_quality_examples
    original=skill_quality_examples.validate_examples
    def observed(contract):
        helper_calls.append(True)
        return original(contract)
    with monkeypatch.context() as patch:
        patch.setattr(skill_quality_examples,'validate_examples',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
        control_valid=True
        if control:
            control_root,control_package,control_mode,control_oracle=control
            control_args,control_kwargs=invocation_args(validate_package,control_root,control_package,control_mode)
            control_result=validate_package(*control_args,**control_kwargs)
            control_valid=control_oracle(control_result)
    valid=not effects and oracle(result) and control_valid
    if assertion=='A-CEE0E00D83B6-MAIN-CONSUMES':valid=valid and len(helper_calls)==1
    if not valid:
        for failure_id in failure_ids:print('FAILURE_ID:'+failure_id)
    assert valid, 'The actual declaration check does not satisfy: '+scenario+' / '+assertion

@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('dependency:missing-record', 'A09_REQUIRED_RECORD_BLOCKING', ['REQUIRED_DEPENDENCY_RECORD_NOT_BLOCKED'], id='O-110D5665F3A7-dependency-missing-record-A09_REQUIRED_RECORD_BLOCKING', marks=pytest.mark.cer_assertion('A09_REQUIRED_RECORD_BLOCKING')),
    pytest.param('dependency:optional-authority', 'REPAIR_O_1487B4C87B47', [], id='O-1487B4C87B47-dependency-optional-authority-REPAIR_O_1487B4C87B47', marks=pytest.mark.cer_assertion('REPAIR_O_1487B4C87B47')),
    pytest.param('dependency:when_missing', 'A09_DETERMINISTIC_MISSING_MISMATCH_DECLARATION', [], id='O-24804DA8035F-dependency-when_missing-A09_DETERMINISTIC_MISSING_MISMATCH_DECLARATION', marks=pytest.mark.cer_assertion('A09_DETERMINISTIC_MISSING_MISMATCH_DECLARATION')),
    pytest.param('dependency:when_mismatch', 'A09_DETERMINISTIC_MISSING_MISMATCH_DECLARATION', [], id='O-24804DA8035F-dependency-when_mismatch-A09_DETERMINISTIC_MISSING_MISMATCH_DECLARATION', marks=pytest.mark.cer_assertion('A09_DETERMINISTIC_MISSING_MISMATCH_DECLARATION')),
    pytest.param('dependency:required', 'A09_REQUIRED_OPTIONAL_KIND', ['A09_KIND_CONTRACT_FAIL'], id='O-27FDCDA47FF1-dependency-required-A09_REQUIRED_OPTIONAL_KIND', marks=pytest.mark.cer_assertion('A09_REQUIRED_OPTIONAL_KIND')),
    pytest.param('dependency:version', 'A09_COMPATIBILITY_OR_AUTHORITY_REFERENCE', ['A09_VERSION_OR_AUTHORITY_FAIL'], id='O-32AAEAE3F552-dependency-version-A09_COMPATIBILITY_OR_AUTHORITY_REFERENCE', marks=pytest.mark.cer_assertion('A09_COMPATIBILITY_OR_AUTHORITY_REFERENCE')),
    pytest.param('dependency:unresolved', 'A09_UNRESOLVED_LOCAL_AUTHORITY_BLOCKING_DIAGNOSTIC', ['A09_UNRESOLVED_LOCAL_AUTHORITY_RED'], id='O-60B983D15976-dependency-unresolved-A09_UNRESOLVED_LOCAL_AUTHORITY_BLOCKING_DIAGNOSTIC', marks=pytest.mark.cer_assertion('A09_UNRESOLVED_LOCAL_AUTHORITY_BLOCKING_DIAGNOSTIC')),
    pytest.param('dependency:id', 'A09_DEPENDENCY_IDENTITY_PRESENT', ['A09_IDENTITY_FIELD_FAIL'], id='O-936576258C0A-dependency-id-A09_DEPENDENCY_IDENTITY_PRESENT', marks=pytest.mark.cer_assertion('A09_DEPENDENCY_IDENTITY_PRESENT')),
    pytest.param('dependency:no-execution', 'A09_DEPENDENCY_EXECUTION_BLOCKED', ['DEPENDENCY_EXECUTION_NOT_BLOCKED'], id='O-9AD4A4D5B26B-dependency-no-execution-A09_DEPENDENCY_EXECUTION_BLOCKED', marks=pytest.mark.cer_assertion('A09_DEPENDENCY_EXECUTION_BLOCKED')),
    pytest.param('dependency:version', 'A09_INCOMPATIBLE_VERSION_TYPED_DIAGNOSTIC', ['INCOMPATIBLE_VERSION_DIAGNOSTIC_MISSING'], id='O-AB91E6D05D78-dependency-version-A09_INCOMPATIBLE_VERSION_TYPED_DIAGNOSTIC', marks=pytest.mark.cer_assertion('A09_INCOMPATIBLE_VERSION_TYPED_DIAGNOSTIC')),
    pytest.param('dependency:optional-dead', 'A09_OPTIONAL_FALLBACK_RESOLVABLE', ['OPTIONAL_FALLBACK_UNRESOLVABLE'], id='O-C4D0B83860C4-dependency-optional-dead-A09_OPTIONAL_FALLBACK_RESOLVABLE', marks=pytest.mark.cer_assertion('A09_OPTIONAL_FALLBACK_RESOLVABLE')),
    pytest.param('dependency:optional', 'REPAIR_O_EAC80B824A22', ['FAIL_O_EAC80B824A22'], id='O-EAC80B824A22-dependency-optional-REPAIR_O_EAC80B824A22', marks=pytest.mark.cer_assertion('REPAIR_O_EAC80B824A22')),
    pytest.param('dependency:optional-no-fallback', 'A-OPTIONAL-FALLBACK-DECLARED', ['OPTIONAL_FALLBACK_REQUIRED'], id='O-7B99FE5859B6-dependency-optional-no-fallback-A-OPTIONAL-FALLBACK-DECLARED', marks=pytest.mark.cer_assertion('A-OPTIONAL-FALLBACK-DECLARED')),
    pytest.param('routing:unreachable', 'A-ROUTING-BRANCH-LINKAGE', ['ROUTING_BRANCH_LINKAGE_REQUIRED'], id='O-7BC5F5B4AFAE-routing-unreachable-A-ROUTING-BRANCH-LINKAGE', marks=pytest.mark.cer_assertion('A-ROUTING-BRANCH-LINKAGE')),
    pytest.param('examples:duplicate-pair', 'AEBBED2A459B-DUPLICATE-EXAMPLE', ['AEBBED2A459B_EXAMPLE_DEFECTS'], id='O-AEBBED2A459B-examples-duplicate-pair-AEBBED2A459B-DUPLICATE-EXAMPLE', marks=pytest.mark.cer_assertion('AEBBED2A459B-DUPLICATE-EXAMPLE')),
    pytest.param('examples:unknown-branch', 'AEBBED2A459B-INCONSISTENT-BRANCH-DECLARATION', ['AEBBED2A459B_EXAMPLE_DEFECTS'], id='O-AEBBED2A459B-examples-unknown-branch-AEBBED2A459B-INCONSISTENT-BRANCH-DECLARATION', marks=pytest.mark.cer_assertion('AEBBED2A459B-INCONSISTENT-BRANCH-DECLARATION')),
    pytest.param('examples:count', 'AEBBED2A459B-MISSING-EXAMPLE-STRUCTURE', ['AEBBED2A459B_EXAMPLE_DEFECTS'], id='O-AEBBED2A459B-examples-count-AEBBED2A459B-MISSING-EXAMPLE-STRUCTURE', marks=pytest.mark.cer_assertion('AEBBED2A459B-MISSING-EXAMPLE-STRUCTURE')),
    pytest.param('dependency:no-execution', 'A-REQUIRED-TOOL-HOST-INDEPENDENCE', ['REQUIRED_TOOL_HOST_INSTALL_REQUIRED'], id='O-B4FF0AD42FB2-dependency-no-execution-A-REQUIRED-TOOL-HOST-INDEPENDENCE', marks=pytest.mark.cer_assertion('A-REQUIRED-TOOL-HOST-INDEPENDENCE')),
    pytest.param('examples:count', 'A-CEE0E00D83B6-BOUNDED-PARSE', ['FI_CEE0E00D83B6_EXAMPLES_UNCONSUMED'], id='O-CEE0E00D83B6-examples-count-A-CEE0E00D83B6-BOUNDED-PARSE', marks=pytest.mark.cer_assertion('A-CEE0E00D83B6-BOUNDED-PARSE')),
    pytest.param('examples:positive', 'A-CEE0E00D83B6-MAIN-CONSUMES', ['FI_CEE0E00D83B6_EXAMPLES_UNCONSUMED'], id='O-CEE0E00D83B6-examples-positive-A-CEE0E00D83B6-MAIN-CONSUMES', marks=pytest.mark.cer_assertion('A-CEE0E00D83B6-MAIN-CONSUMES')),
])
def test_a09_declarations(tmp_path,monkeypatch,scenario,assertion,failure_ids):
    root,package,mode,oracle=prepare_example_scenario(tmp_path,scenario)
    control=None
    kind,detail=scenario.split(':',1)
    baseline={'examples':'examples:positive','routing':'routing:positive','dependency':'dependency:optional' if detail.startswith('optional') else 'dependency:positive','entry':'entry:positive','invocation':'invocation:positive','faq':'faq:positive'}
    if detail not in {'positive','leaf','supplemental','none','no-execution'}:
        control=prepare_example_scenario(tmp_path/'control',baseline[kind])
    effects=[];helper_calls=[]
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Static package validation may not execute or fetch')
    from scripts.sc import skill_quality_examples
    original=skill_quality_examples.validate_examples
    def observed(contract):
        helper_calls.append(True)
        return original(contract)
    with monkeypatch.context() as patch:
        patch.setattr(skill_quality_examples,'validate_examples',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
        control_valid=True
        if control:
            control_root,control_package,control_mode,control_oracle=control
            control_args,control_kwargs=invocation_args(validate_package,control_root,control_package,control_mode)
            control_result=validate_package(*control_args,**control_kwargs)
            control_valid=control_oracle(control_result)
    valid=not effects and oracle(result) and control_valid
    if assertion=='A-CEE0E00D83B6-MAIN-CONSUMES':valid=valid and len(helper_calls)==1
    if not valid:
        for failure_id in failure_ids:print('FAILURE_ID:'+failure_id)
    assert valid, 'The actual declaration check does not satisfy: '+scenario+' / '+assertion

@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('entry:positive', 'REPAIR_O_3D6A27ADCD71', [], id='O-3D6A27ADCD71-entry-positive-REPAIR_O_3D6A27ADCD71', marks=pytest.mark.cer_assertion('REPAIR_O_3D6A27ADCD71')),
    pytest.param('entry:skip', 'A-O445E201A7962-REQUIRED-DEPENDENCY', [], id='O-445E201A7962-entry-skip-A-O445E201A7962-REQUIRED-DEPENDENCY', marks=pytest.mark.cer_assertion('A-O445E201A7962-REQUIRED-DEPENDENCY')),
    pytest.param('dependency:positive', 'A-O44B07BEA78A5-CHILD-DEPENDENCY', [], id='O-44B07BEA78A5-dependency-positive-A-O44B07BEA78A5-CHILD-DEPENDENCY', marks=pytest.mark.cer_assertion('A-O44B07BEA78A5-CHILD-DEPENDENCY')),
    pytest.param('entry:preflight', 'A-O6109432D914E-PREFLIGHT', [], id='O-6109432D914E-entry-preflight-A-O6109432D914E-PREFLIGHT', marks=pytest.mark.cer_assertion('A-O6109432D914E-PREFLIGHT')),
    pytest.param('entry:install', 'A10-SILENT-CHILD-DEPENDENCY-REJECTED', ['SILENT_CHILD_DEPENDENCY_ACCEPTED'], id='O-7B02E186864D-entry-install-A10-SILENT-CHILD-DEPENDENCY-REJECTED', marks=pytest.mark.cer_assertion('A10-SILENT-CHILD-DEPENDENCY-REJECTED')),
    pytest.param('entry:standalone', 'A10-STANDALONE-BEHAVIOR-DECLARED', ['MISSING_STANDALONE_BEHAVIOR_DECLARATION'], id='O-BAA8FB90C544-entry-standalone-A10-STANDALONE-BEHAVIOR-DECLARED', marks=pytest.mark.cer_assertion('A10-STANDALONE-BEHAVIOR-DECLARED')),
    pytest.param('entry:inputs', 'A10-ACCEPTED-INPUT-DECLARED', ['MISSING_ACCEPTED_INPUT_DECLARATION'], id='O-BC8EC3064EBA-entry-inputs-A10-ACCEPTED-INPUT-DECLARED', marks=pytest.mark.cer_assertion('A10-ACCEPTED-INPUT-DECLARED')),
    pytest.param('entry:setup', 'A10-UNDECLARED-CALLER-PREPARATION-REJECTED', ['UNDECLARED_CALLER_PREPARATION_ACCEPTED'], id='O-E22FC88563F6-entry-setup-A10-UNDECLARED-CALLER-PREPARATION-REJECTED', marks=pytest.mark.cer_assertion('A10-UNDECLARED-CALLER-PREPARATION-REJECTED')),
    pytest.param('entry:outputs', 'A10_PUBLIC_ENTRY_OUTPUT_DECLARATION', [], id='O-EB249051B4A8-entry-outputs-A10_PUBLIC_ENTRY_OUTPUT_DECLARATION', marks=pytest.mark.cer_assertion('A10_PUBLIC_ENTRY_OUTPUT_DECLARATION')),
])
def test_a10(tmp_path,monkeypatch,scenario,assertion,failure_ids):
    root,package,mode,oracle=prepare_example_scenario(tmp_path,scenario)
    control=None
    kind,detail=scenario.split(':',1)
    baseline={'examples':'examples:positive','routing':'routing:positive','dependency':'dependency:optional' if detail.startswith('optional') else 'dependency:positive','entry':'entry:positive','invocation':'invocation:positive','faq':'faq:positive'}
    if detail not in {'positive','leaf','supplemental','none','no-execution'}:
        control=prepare_example_scenario(tmp_path/'control',baseline[kind])
    effects=[];helper_calls=[]
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Static package validation may not execute or fetch')
    from scripts.sc import skill_quality_examples
    original=skill_quality_examples.validate_examples
    def observed(contract):
        helper_calls.append(True)
        return original(contract)
    with monkeypatch.context() as patch:
        patch.setattr(skill_quality_examples,'validate_examples',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
        control_valid=True
        if control:
            control_root,control_package,control_mode,control_oracle=control
            control_args,control_kwargs=invocation_args(validate_package,control_root,control_package,control_mode)
            control_result=validate_package(*control_args,**control_kwargs)
            control_valid=control_oracle(control_result)
    valid=not effects and oracle(result) and control_valid
    if assertion=='A-CEE0E00D83B6-MAIN-CONSUMES':valid=valid and len(helper_calls)==1
    if not valid:
        for failure_id in failure_ids:print('FAILURE_ID:'+failure_id)
    assert valid, 'The actual declaration check does not satisfy: '+scenario+' / '+assertion

@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('invocation:argv', 'A11_STRUCTURED_ARGV_ARRAY_ACCEPTED', ['A11_STRUCTURED_ARGV_REQUIRED'], id='O-29B7B5F4CEBC-invocation-argv-A11_STRUCTURED_ARGV_ARRAY_ACCEPTED', marks=pytest.mark.cer_assertion('A11_STRUCTURED_ARGV_ARRAY_ACCEPTED')),
    pytest.param('invocation:positive', 'A11_TYPED_RESULT_DECLARATION_ACCEPTED', ['A11_UNTYPED_RESULT_ACCEPTED'], id='O-33DE9D239B2F-invocation-positive-A11_TYPED_RESULT_DECLARATION_ACCEPTED', marks=pytest.mark.cer_assertion('A11_TYPED_RESULT_DECLARATION_ACCEPTED')),
    pytest.param('invocation:result', 'A11_UNTYPED_RESULT_DECLARATION_REJECTED', ['A11_UNTYPED_RESULT_ACCEPTED'], id='O-33DE9D239B2F-invocation-result-A11_UNTYPED_RESULT_DECLARATION_REJECTED', marks=pytest.mark.cer_assertion('A11_UNTYPED_RESULT_DECLARATION_REJECTED')),
    pytest.param('invocation:timeout', 'A11_INVOCATION_TIMEOUT_POSITIVE_FINITE', ['A11_UNBOUNDED_INVOCATION_ACCEPTED'], id='O-97484DA36E34-invocation-timeout-A11_INVOCATION_TIMEOUT_POSITIVE_FINITE', marks=pytest.mark.cer_assertion('A11_INVOCATION_TIMEOUT_POSITIVE_FINITE')),
    pytest.param('invocation:positive', 'A-O-C836674828F3-CWD-EXPLICIT', [], id='O-C836674828F3-invocation-positive-A-O-C836674828F3-CWD-EXPLICIT', marks=pytest.mark.cer_assertion('A-O-C836674828F3-CWD-EXPLICIT')),
    pytest.param('invocation:positive', 'A-O-C836674828F3-CWD-STATIC', [], id='O-C836674828F3-invocation-positive-A-O-C836674828F3-CWD-STATIC', marks=pytest.mark.cer_assertion('A-O-C836674828F3-CWD-STATIC')),
    pytest.param('invocation:missing-cwd', 'A-O-C836674828F3-CWD-UNSAFE', [], id='O-C836674828F3-missing-cwd', marks=pytest.mark.cer_assertion('A-O-C836674828F3-CWD-UNSAFE')),
    pytest.param('invocation:cwd', 'A-O-C836674828F3-CWD-UNSAFE', [], id='O-C836674828F3-invocation-cwd-A-O-C836674828F3-CWD-UNSAFE', marks=pytest.mark.cer_assertion('A-O-C836674828F3-CWD-UNSAFE')),
    pytest.param('invocation:cwd', 'A-O-C836674828F3-1', ['FI_O_C836674828F3_UNSAFE_CWD_ACCEPTED'], id='O-CD8451473EB6-invocation-cwd-A-O-C836674828F3-1', marks=pytest.mark.cer_assertion('A-O-C836674828F3-1')),
    pytest.param('invocation:string', 'A-D6413BE44865-1', ['A11_STRING_INVOCATION_ACCEPTED'], id='O-D6413BE44865-invocation-positive-A-D6413BE44865-1', marks=pytest.mark.cer_assertion('A-D6413BE44865-1')),
    pytest.param('invocation:positive', 'A11_STATIC_VALIDATOR_NEVER_EXECUTES_DECLARATION', ['A11_STATIC_VALIDATION_EXECUTED_COMMAND'], id='O-F496CAF10DD2-invocation-positive-A11_STATIC_VALIDATOR_NEVER_EXECUTES_DECLARATION', marks=pytest.mark.cer_assertion('A11_STATIC_VALIDATOR_NEVER_EXECUTES_DECLARATION')),
])
def test_a11(tmp_path,monkeypatch,scenario,assertion,failure_ids):
    root,package,mode,oracle=prepare_example_scenario(tmp_path,scenario)
    control=None
    kind,detail=scenario.split(':',1)
    baseline={'examples':'examples:positive','routing':'routing:positive','dependency':'dependency:optional' if detail.startswith('optional') else 'dependency:positive','entry':'entry:positive','invocation':'invocation:positive','faq':'faq:positive'}
    if detail not in {'positive','leaf','supplemental','none','no-execution'}:
        control=prepare_example_scenario(tmp_path/'control',baseline[kind])
    effects=[];helper_calls=[]
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Static package validation may not execute or fetch')
    from scripts.sc import skill_quality_examples
    original=skill_quality_examples.validate_examples
    def observed(contract):
        helper_calls.append(True)
        return original(contract)
    with monkeypatch.context() as patch:
        patch.setattr(skill_quality_examples,'validate_examples',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
        control_valid=True
        if control:
            control_root,control_package,control_mode,control_oracle=control
            control_args,control_kwargs=invocation_args(validate_package,control_root,control_package,control_mode)
            control_result=validate_package(*control_args,**control_kwargs)
            control_valid=control_oracle(control_result)
    valid=not effects and oracle(result) and control_valid
    if assertion=='A-CEE0E00D83B6-MAIN-CONSUMES':valid=valid and len(helper_calls)==1
    if not valid:
        for failure_id in failure_ids:print('FAILURE_ID:'+failure_id)
    assert valid, 'The actual declaration check does not satisfy: '+scenario+' / '+assertion

@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('faq:orphan', 'A-FAQ-REACHABILITY-ORPHAN-REJECT', ['FAQ_REACHABILITY_ORPHAN_EXPECTED_RED'], id='O-2ED942C6B68F-faq-orphan-A-FAQ-REACHABILITY-ORPHAN-REJECT', marks=pytest.mark.cer_assertion('A-FAQ-REACHABILITY-ORPHAN-REJECT')),
    pytest.param('faq:positive', 'A-FAQ-LOCAL-TARGETS-RESOLVE', ['FAQ_LOCAL_TARGET_RESOLUTION_CONTRACT_GAP'], id='O-415FCFC08A7E-faq-positive-A-FAQ-LOCAL-TARGETS-RESOLVE', marks=pytest.mark.cer_assertion('A-FAQ-LOCAL-TARGETS-RESOLVE')),
    pytest.param('faq:positive', 'A-OB631FAQ-reachability', ['FAQ_ORPHAN_ENTRY_REACHABILITY_GAP'], id='O-698B21668564-faq-positive-A-OB631FAQ-reachability', marks=pytest.mark.cer_assertion('A-OB631FAQ-reachability')),
    pytest.param('faq:none', 'ASSERT_FAQ_EMPTY_ACCEPTED', ['FAQ_OPTIONALITY_REJECTION'], id='O-E87124F93774-faq-none-ASSERT_FAQ_EMPTY_ACCEPTED', marks=pytest.mark.cer_assertion('ASSERT_FAQ_EMPTY_ACCEPTED')),
    pytest.param('faq:dead', 'A-FAQ-TARGET-DEAD-REJECT', ['FAQ_TARGET_DEAD_EXPECTED_RED'], id='O-F20B8DD9C457-faq-dead-A-FAQ-TARGET-DEAD-REJECT', marks=pytest.mark.cer_assertion('A-FAQ-TARGET-DEAD-REJECT')),
    pytest.param('faq:unknown', 'ASSERT-O-FDAC07BBA2D4-UNKNOWN-FAQ-REF', ['RED_UNKNOWN_FAQ_REFERENCE'], id='O-FDAC07BBA2D4-faq-unknown-ASSERT-O-FDAC07BBA2D4-UNKNOWN-FAQ-REF', marks=pytest.mark.cer_assertion('ASSERT-O-FDAC07BBA2D4-UNKNOWN-FAQ-REF')),
])
def test_a12(tmp_path,monkeypatch,scenario,assertion,failure_ids):
    root,package,mode,oracle=prepare_example_scenario(tmp_path,scenario)
    control=None
    kind,detail=scenario.split(':',1)
    baseline={'examples':'examples:positive','routing':'routing:positive','dependency':'dependency:optional' if detail.startswith('optional') else 'dependency:positive','entry':'entry:positive','invocation':'invocation:positive','faq':'faq:positive'}
    if detail not in {'positive','leaf','supplemental','none','no-execution'}:
        control=prepare_example_scenario(tmp_path/'control',baseline[kind])
    effects=[];helper_calls=[]
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Static package validation may not execute or fetch')
    from scripts.sc import skill_quality_examples
    original=skill_quality_examples.validate_examples
    def observed(contract):
        helper_calls.append(True)
        return original(contract)
    with monkeypatch.context() as patch:
        patch.setattr(skill_quality_examples,'validate_examples',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
        control_valid=True
        if control:
            control_root,control_package,control_mode,control_oracle=control
            control_args,control_kwargs=invocation_args(validate_package,control_root,control_package,control_mode)
            control_result=validate_package(*control_args,**control_kwargs)
            control_valid=control_oracle(control_result)
    valid=not effects and oracle(result) and control_valid
    if assertion=='A-CEE0E00D83B6-MAIN-CONSUMES':valid=valid and len(helper_calls)==1
    if not valid:
        for failure_id in failure_ids:print('FAILURE_ID:'+failure_id)
    assert valid, 'The actual declaration check does not satisfy: '+scenario+' / '+assertion

@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('dependency:id','DEPENDENCY_RECORD_IDENTITY',['DEPENDENCY_RECORD_STATIC_CHECK_FAILURE'],id='O-D67B6024B775-DEPENDENCY_RECORD_IDENTITY',marks=pytest.mark.cer_assertion('DEPENDENCY_RECORD_IDENTITY')),
    pytest.param('dependency:version','DEPENDENCY_RECORD_VERSION_AUTHORITY',['DEPENDENCY_RECORD_STATIC_CHECK_FAILURE'],id='O-D67B6024B775-DEPENDENCY_RECORD_VERSION_AUTHORITY',marks=pytest.mark.cer_assertion('DEPENDENCY_RECORD_VERSION_AUTHORITY')),
    pytest.param('dependency:when_mismatch','DEPENDENCY_RECORD_MISSING_MISMATCH',['DEPENDENCY_RECORD_STATIC_CHECK_FAILURE'],id='O-D67B6024B775-DEPENDENCY_RECORD_MISSING_MISMATCH',marks=pytest.mark.cer_assertion('DEPENDENCY_RECORD_MISSING_MISMATCH')),
    pytest.param('dependency:no-execution','DEPENDENCY_RECORD_NO_INVOCATION',['DEPENDENCY_RECORD_STATIC_CHECK_FAILURE'],id='O-D67B6024B775-DEPENDENCY_RECORD_NO_INVOCATION',marks=pytest.mark.cer_assertion('DEPENDENCY_RECORD_NO_INVOCATION')),
])
def test_a09_record_declarations(tmp_path,monkeypatch,scenario,assertion,failure_ids):
    root,package,mode,oracle=prepare_example_scenario(tmp_path,scenario)
    control=None
    kind,detail=scenario.split(':',1)
    baseline={'examples':'examples:positive','routing':'routing:positive','dependency':'dependency:optional' if detail.startswith('optional') else 'dependency:positive','entry':'entry:positive','invocation':'invocation:positive','faq':'faq:positive'}
    if detail not in {'positive','leaf','supplemental','none','no-execution'}:
        control=prepare_example_scenario(tmp_path/'control',baseline[kind])
    effects=[];helper_calls=[]
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Static package validation may not execute or fetch')
    from scripts.sc import skill_quality_examples
    original=skill_quality_examples.validate_examples
    def observed(contract):
        helper_calls.append(True)
        return original(contract)
    with monkeypatch.context() as patch:
        patch.setattr(skill_quality_examples,'validate_examples',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
        control_valid=True
        if control:
            control_root,control_package,control_mode,control_oracle=control
            control_args,control_kwargs=invocation_args(validate_package,control_root,control_package,control_mode)
            control_result=validate_package(*control_args,**control_kwargs)
            control_valid=control_oracle(control_result)
    valid=not effects and oracle(result) and control_valid
    if assertion=='A-CEE0E00D83B6-MAIN-CONSUMES':valid=valid and len(helper_calls)==1
    if not valid:
        for failure_id in failure_ids:print('FAILURE_ID:'+failure_id)
    assert valid, 'The actual declaration check does not satisfy: '+scenario+' / '+assertion

@pytest.mark.cer_assertion('DEPENDENCY_EXPLICIT_LOCAL_RECORD_SOURCES')
@pytest.mark.cer_assertion('DEPENDENCY_IMPLICIT_REMOTE_SOURCES_UNUSED')
def test_policy_authority_rejects_uri_before_read(tmp_path,monkeypatch):
    root,package,value=dependency_package(tmp_path)
    value['dependencies']=[];write_contract(package,value)
    policy_path=root/'scripts/sc/config/skill-authoring-standard.v1.json'
    policy=json.loads(policy_path.read_text())
    record={'id':'local-parser','required':True,'version':'1.2.3',
            'authority':'authorities/parser.json','when_missing':'block','when_mismatch':'block'}
    real=root/'authorities/parser.json';real.parent.mkdir()
    real.write_text(json.dumps({'id':'local-parser','version':'1.2.3'}))
    policy['dependencies']=[record];policy_path.write_text(json.dumps(policy))
    args,kwargs=invocation_args(validate_package,root,package)
    control=validate_package(*args,**kwargs)
    record['authority']='https://unapproved.invalid/authority.json'
    disguised=root/record['authority']
    # POSIX permits a URI-shaped local filename; Windows blocks its colon.
    # Both hosts execute the URI rejection case; no unsupported path is created.
    if os.name!='nt':
        disguised.parent.mkdir(parents=True)
        disguised.write_text(json.dumps({'id':'local-parser','version':'1.2.3'}))
    policy_path.write_text(json.dumps(policy))
    reads=[];original=Path.open
    def observed(self,*args,**kwargs):
        if self==disguised:reads.append(True)
        return original(self,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path,'open',observed)
        result=validate_package(*args,**kwargs)
    valid=(control.get('status')=='pass' and result.get('status')=='fail'
           and result.get('exit_code')==1 and result.get('authorizes')==[] and not reads
           and any(d.get('rule')=='A09' and d.get('code')=='DEPENDENCY_UNRESOLVED_AUTHORITY' for d in result.get('diagnostics',[])))
    if not valid:print('FAILURE_ID:DEPENDENCY_RECORD_SOURCE_BOUNDARY_VIOLATION')
    assert valid, 'Only explicit local authority paths may be read; URI-shaped records cannot substitute'


@pytest.mark.parametrize('defect',['input','output','order','duplicate','unknown','same-pair'])
@pytest.mark.cer_assertion('REPAIR_O_8CC763357B93')
def test_a07_all_independent_invalid_examples(tmp_path,defect):
    root,package,value=dependency_package(tmp_path)
    if defect in {'input','output'}:value['examples'][0][defect]=''
    elif defect=='order':value['examples'][0],value['examples'][1]=value['examples'][1],value['examples'][0]
    elif defect=='duplicate':value['examples'][1]['branch']=value['examples'][0]['branch']
    elif defect=='unknown':value['examples'][1]['branch']='unlisted-outcome'
    else:
        value['examples'][1]['input']=value['examples'][0]['input'].upper()+'  '
        value['examples'][1]['output']=value['examples'][0]['output'].lower()
    write_contract(package,value)
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert result['status']=='fail' and any(d['rule']=='A07' for d in result['diagnostics']) and result['authorizes']==[],result


@pytest.mark.cer_assertion('A-O-0AC244DC8D60-CLASSIFICATION')
@pytest.mark.cer_assertion('A-O-0AC244DC8D60-OUTCOME-IDS')
def test_a07_leaf_examples_do_not_change_routing_classification(tmp_path):
    root,package,value=dependency_package(tmp_path)
    assert [entry['outcome'] for entry in value['examples']]==['typical','boundary','error'] and value['routing']=={'kind':'leaf'}
    assert not value['capabilities']['routing']
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert result['status']=='pass' and result['authorizes']==[] and not any(d['rule']=='A08' for d in result['diagnostics'])


@pytest.mark.cer_assertion('ASSERT_EXTERNAL_EXAMPLE_REVIEW_REQUIREMENT')
@pytest.mark.cer_assertion('ASSERT_STATIC_SEMANTIC_CLAIM_BOUNDARY')
def test_a07_examples_require_external_semantic_review(tmp_path):
    root,package,_=dependency_package(tmp_path)
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert result['status']=='pass' and result['authorizes']==[]
    from scripts.sc.tests.skill_quality_support import REPOSITORY
    standard=' '.join((REPOSITORY/'docs/standards/skill-authoring-standard.md').read_text().lower().split())
    assert 'checked mechanically' in standard and 'external review judges their semantic usefulness' in standard
