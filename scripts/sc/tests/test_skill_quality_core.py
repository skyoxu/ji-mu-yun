"""ADR-0041: independent real-entry structured-result and containment oracles."""
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from scripts.sc.validate_skill_quality import validate_package
from scripts.sc.tests.skill_quality_support import dependency_package, invocation_args, write_contract, REPOSITORY, POLICY


def require(condition, *failure_ids):
    if not condition:
        for failure_id in failure_ids:
            print('FAILURE_ID:' + failure_id)
    assert condition, 'The actual production outcome violates the frozen contract'


@pytest.mark.parametrize('defect', [
    pytest.param('missing-file', marks=pytest.mark.cer_assertion('A05-MISSING-FILE-REJECTED')),
    pytest.param('missing-anchor', marks=pytest.mark.cer_assertion('A05-MISSING-ANCHOR-REJECTED')),
    pytest.param('traversal', marks=pytest.mark.cer_assertion('A05-PATH-TRAVERSAL-REJECTED')),
    pytest.param('absolute', marks=pytest.mark.cer_assertion('A05-ABSOLUTE-PATH-REJECTED')),
    pytest.param('symlink', marks=pytest.mark.cer_assertion('A05-SYMLINK-ESCAPE-REJECTED')),
])
@pytest.mark.cer_assertion('A05-NO-OUTSIDE-READ-BEFORE-REJECTION')
def test_a05(tmp_path, monkeypatch, defect):
    root, package, value = dependency_package(tmp_path)
    outside = root / 'outside.md'
    outside.write_text('# Private\n\nOUTSIDE_SENTINEL_MUST_NOT_BE_READ',encoding='utf-8')
    (package/'references/content.md').write_text('# Existing\n\nSubstantive required content.',encoding='utf-8')
    if defect == 'missing-file': ref = 'references/missing.md#existing'
    elif defect == 'missing-anchor': ref = 'references/content.md#absent'
    elif defect == 'traversal': ref = '../../outside.md#private'
    elif defect == 'absolute': ref = outside.as_posix() + '#private'
    else:
        (package/'references/escape.md').symlink_to(outside)
        assert (package/'references/escape.md').is_symlink()
        ref = 'references/escape.md#private'
    value['responsibility'] = {'ref': ref}
    write_contract(package,value)
    before = outside.read_bytes()
    reads=[]
    original_open=Path.open
    def observed_open(self,*args,**kwargs):
        if self.resolve()==outside.resolve(): reads.append(str(self))
        return original_open(self,*args,**kwargs)
    monkeypatch.setattr(Path,'open',observed_open)
    args,kwargs=invocation_args(validate_package,root,package)
    result=validate_package(*args,**kwargs)
    diagnostics=result.get('diagnostics',[]) if isinstance(result,dict) else []
    require(isinstance(result,dict) and result.get('status')=='fail' and result.get('exit_code')==1
            and any(d.get('rule')=='A05' and d.get('path')=='skill-quality.v1.json#/responsibility' for d in diagnostics)
            and not reads, 'A05_REFERENCE_BOUNDARY')
    monkeypatch.setattr(Path,'open',original_open)
    assert outside.read_bytes()==before
    assert 'OUTSIDE_SENTINEL' not in json.dumps(result) and str(root) not in json.dumps(result)


@pytest.mark.cer_assertion('A-84E55FAF94D5-1')
def test_a06(tmp_path):
    root,package,_=dependency_package(tmp_path)
    args,kwargs=invocation_args(validate_package,root,package)
    result=validate_package(*args,**kwargs)
    process=subprocess.run([sys.executable,'-B','scripts/sc/validate_skill_quality.py',
        '--repository-root',str(root),'--policy',POLICY,'--skill-root',str(package),'--mode','strict'],
        cwd=REPOSITORY,shell=False,capture_output=True,text=True,timeout=300)
    try: cli=json.loads(process.stdout)
    except json.JSONDecodeError: cli=None
    fields={'schema','package','mode','status','exit_code','diagnostics','authorizes'}
    require(isinstance(result,dict) and fields <= result.keys() and isinstance(cli,dict)
            and fields <= cli.keys() and cli==result and process.returncode==result['exit_code']
            and process.stderr=='' and result['authorizes']==[]
            and all({'rule','path','code','message'} <= d.keys() for d in result['diagnostics']),
            'A06_STRUCTURED_RESULT','PUBLIC_STRUCTURED_RESULT_MISSING')

from scripts.sc.tests.skill_quality_support import prepare_scenario
import socket, urllib.request, os

@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('artifact:policy-fields', 'POLICY_DEPENDENCY_VERSION_AUTHORITIES_DECLARED', ['POLICY_DECLARATION_CATEGORY_MISSING'], id='O-7B08727401CD-POLICY_DEPENDENCY_VERSION_AUTHORITIES_DECLARED', marks=pytest.mark.cer_assertion('POLICY_DEPENDENCY_VERSION_AUTHORITIES_DECLARED')),
    pytest.param('artifact:policy-fields', 'POLICY_FRONTMATTER_KEYS_DECLARED', ['POLICY_DECLARATION_CATEGORY_MISSING'], id='O-7B08727401CD-POLICY_FRONTMATTER_KEYS_DECLARED', marks=pytest.mark.cer_assertion('POLICY_FRONTMATTER_KEYS_DECLARED')),
    pytest.param('artifact:policy-fields', 'POLICY_LIMITS_DECLARED', ['POLICY_DECLARATION_CATEGORY_MISSING'], id='O-7B08727401CD-POLICY_LIMITS_DECLARED', marks=pytest.mark.cer_assertion('POLICY_LIMITS_DECLARED')),
    pytest.param('artifact:policy-fields', 'POLICY_SCHEMA_PATHS_DECLARED', ['POLICY_DECLARATION_CATEGORY_MISSING'], id='O-7B08727401CD-POLICY_SCHEMA_PATHS_DECLARED', marks=pytest.mark.cer_assertion('POLICY_SCHEMA_PATHS_DECLARED')),
    pytest.param('artifact:policy-fields', 'POLICY_STABLE_RULE_IDS_DECLARED', ['POLICY_DECLARATION_CATEGORY_MISSING'], id='O-7B08727401CD-POLICY_STABLE_RULE_IDS_DECLARED', marks=pytest.mark.cer_assertion('POLICY_STABLE_RULE_IDS_DECLARED')),
    pytest.param('frontmatter:identity', 'assert_quality_sidecar_filename', ['SIDECAR_IDENTITY_GUARD'], id='O-59A8F2B6C9DA-assert_quality_sidecar_filename', marks=pytest.mark.cer_assertion('assert_quality_sidecar_filename')),
    pytest.param('frontmatter:identity', 'assert_sidecar_name_matches_canonical_package_directory', ['SIDECAR_IDENTITY_GUARD'], id='O-59A8F2B6C9DA-assert_sidecar_name_matches_canonical_package_directory', marks=pytest.mark.cer_assertion('assert_sidecar_name_matches_canonical_package_directory')),
    pytest.param('frontmatter:identity', 'assert_sidecar_name_matches_frontmatter', ['SIDECAR_IDENTITY_GUARD'], id='O-59A8F2B6C9DA-assert_sidecar_name_matches_frontmatter', marks=pytest.mark.cer_assertion('assert_sidecar_name_matches_frontmatter')),
    pytest.param('paths:roots', 'A-F666C89808F0-ROOT-BOUNDARY', ['FI_F666C89808F0_ROOT_ESCAPE'], id='O-F666C89808F0-A-F666C89808F0-ROOT-BOUNDARY', marks=pytest.mark.cer_assertion('A-F666C89808F0-ROOT-BOUNDARY')),
    pytest.param('artifact:standard-root', 'assert_policy_standard_link_uses_declared_repository_root', ['POLICY_LINK_ROOT_GUARD'], id='O-560B8436110C-assert_policy_standard_link_uses_declared_repository_root', marks=pytest.mark.cer_assertion('assert_policy_standard_link_uses_declared_repository_root')),
    pytest.param('artifact:policy', 'policy-deliverable-path-exists', ['POLICY_DELIVERABLE_MISSING'], id='O-22BF3BB5AC14-policy-deliverable-path-exists', marks=pytest.mark.cer_assertion('policy-deliverable-path-exists')),
    pytest.param('artifact:argv', 'A-D7BDC80EF7E3-ARGV-NO-SHELL', ['FI_D7BDC80EF7E3_ARGV_CONTRACT'], id='O-D7BDC80EF7E3-A-D7BDC80EF7E3-ARGV-NO-SHELL', marks=pytest.mark.cer_assertion('A-D7BDC80EF7E3-ARGV-NO-SHELL')),
    pytest.param('artifact:argv', 'A-D7BDC80EF7E3-INTERPRETER', ['FI_D7BDC80EF7E3_ARGV_CONTRACT'], id='O-D7BDC80EF7E3-A-D7BDC80EF7E3-INTERPRETER', marks=pytest.mark.cer_assertion('A-D7BDC80EF7E3-INTERPRETER')),
    pytest.param('artifact:static-claims', 'A-0E5FB41159EF-1', ['FI_0E5FB41159EF_CAPABILITY_CLAIMS'], id='O-1B272191A541-A-0E5FB41159EF-1', marks=pytest.mark.cer_assertion('A-0E5FB41159EF-1')),
    pytest.param('frontmatter:constructor', 'A-O2E-UNTRUSTED-SAFE-PARSE', ['O2E_UNTRUSTED_CONTENT_CONTROL'], id='O-EEA3B1063B7B-A-O2E-UNTRUSTED-SAFE-PARSE', marks=pytest.mark.cer_assertion('A-O2E-UNTRUSTED-SAFE-PARSE')),
    pytest.param('schema:remote-ref', 'A-DCDAB9D1B54E-LOCAL-REF', ['FAIL_EXTERNAL_SCHEMA_REF_ACCEPTED'], id='O-DCDAB9D1B54E-A-DCDAB9D1B54E-LOCAL-REF', marks=pytest.mark.cer_assertion('A-DCDAB9D1B54E-LOCAL-REF')),
    pytest.param('paths:relative', 'A-E396A50025A5-CONTAINED-PATH', ['FAIL_OUT_OF_ROOT_PATH_ACCEPTED'], id='O-E396A50025A5-A-E396A50025A5-CONTAINED-PATH', marks=pytest.mark.cer_assertion('A-E396A50025A5-CONTAINED-PATH')),
    pytest.param('required:responsibility', 'A-SM-A01-MISSING-DECLARATION-AND-SECTION-RULE', ['A01_MISSING_SECTION_RULE'], id='O-A01FF5AF65D5-A-SM-A01-MISSING-DECLARATION-AND-SECTION-RULE', marks=pytest.mark.cer_assertion('A-SM-A01-MISSING-DECLARATION-AND-SECTION-RULE')),
    pytest.param('artifact:contract-schema', 'A-7F94290AD117-SCHEMA-EXISTS', ['QUALITY_CONTRACT_SCHEMA_MISSING'], id='O-6FDB1DC67474-A-7F94290AD117-SCHEMA-EXISTS', marks=pytest.mark.cer_assertion('A-7F94290AD117-SCHEMA-EXISTS')),
    pytest.param('required:outputs', 'assert_package_declarations_and_structure_are_checked', ['PACKAGE_DECLARATION_STRUCTURE_MISSING'], id='O-33F20A2DD763-assert_package_declarations_and_structure_are_checked', marks=pytest.mark.cer_assertion('assert_package_declarations_and_structure_are_checked')),
    pytest.param('positive:local', 'A-UNDECLARED-CAPABILITY-INFRASTRUCTURE', ['UNDECLARED_CAPABILITY_INFRASTRUCTURE_REJECTED'], id='O-A341EE963B39-A-UNDECLARED-CAPABILITY-INFRASTRUCTURE', marks=pytest.mark.cer_assertion('A-UNDECLARED-CAPABILITY-INFRASTRUCTURE')),
    pytest.param('diagnostics:secrets', 'ASSERT-DIAGNOSTIC-CONTENT-BOUNDARY', ['DIAGNOSTIC_CONTENT_BOUNDARY_GAP'], id='O-34AD6F7F0CF6-ASSERT-DIAGNOSTIC-CONTENT-BOUNDARY', marks=pytest.mark.cer_assertion('ASSERT-DIAGNOSTIC-CONTENT-BOUNDARY')),
    pytest.param('artifact:entrypoints', 'A-O-68F9F5DB3666-VALIDATOR-ENTRYPOINTS', ['MISSING_VALIDATOR_ENTRYPOINTS'], id='O-1169812142B3-A-O-68F9F5DB3666-VALIDATOR-ENTRYPOINTS', marks=pytest.mark.cer_assertion('A-O-68F9F5DB3666-VALIDATOR-ENTRYPOINTS')),
    pytest.param('schema:consumption', 'assert_normative_policy_affects_validation', ['NORMATIVE_INPUTS_GUARD'], id='O-61FC3F0C11C5-assert_normative_policy_affects_validation', marks=pytest.mark.cer_assertion('assert_normative_policy_affects_validation')),
    pytest.param('schema:consumption', 'assert_normative_schema_affects_validation', ['NORMATIVE_INPUTS_GUARD'], id='O-61FC3F0C11C5-assert_normative_schema_affects_validation', marks=pytest.mark.cer_assertion('assert_normative_schema_affects_validation')),
    pytest.param('schema:invalid-inputs', 'A-DC9328497131-FAIL-STATUS', ['FAIL_INSPECTABLE_DEFECT_PASS'], id='O-DC9328497131-A-DC9328497131-FAIL-STATUS', marks=pytest.mark.cer_assertion('A-DC9328497131-FAIL-STATUS')),
    pytest.param('artifact:result-schema', 'A-O-BA69B0E713DE-001', ['QUALITY_RESULT_SCHEMA_MISSING'], id='O-73D31383D597-A-O-BA69B0E713DE-001', marks=pytest.mark.cer_assertion('A-O-BA69B0E713DE-001')),
    pytest.param('api:signature', 'ASSERT_VALIDATE_PACKAGE_SIGNATURE', ['API_SIGNATURE_MISMATCH'], id='O-C54BDA14E670-ASSERT_VALIDATE_PACKAGE_SIGNATURE', marks=pytest.mark.cer_assertion('ASSERT_VALIDATE_PACKAGE_SIGNATURE')),
    pytest.param('schema:invalid-inventory', 'ASSERT_PRESENT_INVALID_SIDECAR_NOT_LEGACY_OR_PASS', ['INVALID_SIDECAR_CLASSIFICATION_NOT_REJECTED'], id='O-0D98D0E908B4-ASSERT_PRESENT_INVALID_SIDECAR_NOT_LEGACY_OR_PASS', marks=pytest.mark.cer_assertion('ASSERT_PRESENT_INVALID_SIDECAR_NOT_LEGACY_OR_PASS')),
    pytest.param('required:responsibility', 'A-SM-A01-REMOVAL-DIAGNOSTIC-RELATIVE-LOCATION', ['A01_RELATIVE_LOCATION_MISSING'], id='O-C87DEB8F7B15-A-SM-A01-REMOVAL-DIAGNOSTIC-RELATIVE-LOCATION', marks=pytest.mark.cer_assertion('A-SM-A01-REMOVAL-DIAGNOSTIC-RELATIVE-LOCATION')),
    pytest.param('frontmatter:extension', 'A-SEMANTIC-FIELD-STORAGE', ['SEMANTIC_FIELD_STORAGE_BOUNDARY_VIOLATION'], id='O-C05B0E75BE86-A-SEMANTIC-FIELD-STORAGE', marks=pytest.mark.cer_assertion('A-SEMANTIC-FIELD-STORAGE')),
])
def test_a01_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
    root,package,mode,oracle=prepare_scenario(tmp_path,scenario,assertion)
    effects=[];outside=root/'outside.md';original=Path.open
    def observed(self,*args,**kwargs):
        if self.resolve()==outside.resolve(): effects.append('forbidden-read')
        return original(self,*args,**kwargs)
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Inspected declarations must remain static data')
    with monkeypatch.context() as patch:
        patch.setattr(Path,'open',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen'),(os,'system')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
    valid=not effects and oracle(result)
    if not valid:
        for failure_id in failure_ids: print('FAILURE_ID:'+failure_id)
    assert valid, 'Required independent declaration outcome is missing: '+scenario+' / '+assertion


@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('schema:typo', 'SM-A02-CAPABILITY-TYPO-REJECTED', ['CAPABILITY_TYPO_REJECTED'], id='O-54346907B86F-SM-A02-CAPABILITY-TYPO-REJECTED', marks=pytest.mark.cer_assertion('SM-A02-CAPABILITY-TYPO-REJECTED')),
    pytest.param('schema:capabilities', 'SM-A02-EXPLICIT-CAPABILITY-RECORD', ['CAPABILITY_RECORDS_NOT_EXPLICIT'], id='O-EB7603F8A6E8-SM-A02-EXPLICIT-CAPABILITY-RECORD', marks=pytest.mark.cer_assertion('SM-A02-EXPLICIT-CAPABILITY-RECORD')),
    pytest.param('positive:valid', 'A-O-3AB6EA99CBC2-1', ['VALID_CONTRACT_REJECTED'], id='O-75662112AE20-A-O-3AB6EA99CBC2-1', marks=pytest.mark.cer_assertion('A-O-3AB6EA99CBC2-1')),
])
def test_a02_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
    root,package,mode,oracle=prepare_scenario(tmp_path,scenario,assertion)
    effects=[];outside=root/'outside.md';original=Path.open
    def observed(self,*args,**kwargs):
        if self.resolve()==outside.resolve(): effects.append('forbidden-read')
        return original(self,*args,**kwargs)
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Inspected declarations must remain static data')
    with monkeypatch.context() as patch:
        patch.setattr(Path,'open',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen'),(os,'system')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
    valid=not effects and oracle(result)
    if not valid:
        for failure_id in failure_ids: print('FAILURE_ID:'+failure_id)
    assert valid, 'Required independent declaration outcome is missing: '+scenario+' / '+assertion


@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('frontmatter:constructor', 'SM-A03-SAFE-PARSE', ['SAFE_PARSE_CONSTRUCTOR_EXEC'], id='O-2661E1825A17-SM-A03-SAFE-PARSE', marks=pytest.mark.cer_assertion('SM-A03-SAFE-PARSE')),
    pytest.param('frontmatter:conflict', 'A-O-991C281B5663-IDENTITY-CONSISTENCY', ['IDENTITY_CONFLICT_ACCEPTED'], id='O-991C281B5663-A-O-991C281B5663-IDENTITY-CONSISTENCY', marks=pytest.mark.cer_assertion('A-O-991C281B5663-IDENTITY-CONSISTENCY')),
    pytest.param('frontmatter:canonical', 'A-O-77D10B1504E5-CANONICAL-NAME-RESULT', ['FAIL_CANONICAL_PACKAGE_NAME_ACCEPTED'], id='O-77D10B1504E5-A-O-77D10B1504E5-CANONICAL-NAME-RESULT', marks=pytest.mark.cer_assertion('A-O-77D10B1504E5-CANONICAL-NAME-RESULT')),
    pytest.param('frontmatter:variants', 'A-C05161C42E01-CONFLICTING-NAME', ['FRONTMATTER_BOUNDARY_MISMATCH'], id='O-C05161C42E01-A-C05161C42E01-CONFLICTING-NAME', marks=pytest.mark.cer_assertion('A-C05161C42E01-CONFLICTING-NAME')),
    pytest.param('frontmatter:variants', 'A-C05161C42E01-DUPLICATE-KEYS', ['FRONTMATTER_BOUNDARY_MISMATCH'], id='O-C05161C42E01-A-C05161C42E01-DUPLICATE-KEYS', marks=pytest.mark.cer_assertion('A-C05161C42E01-DUPLICATE-KEYS')),
    pytest.param('frontmatter:variants', 'A-C05161C42E01-MALFORMED-FRONTMATTER', ['FRONTMATTER_BOUNDARY_MISMATCH'], id='O-C05161C42E01-A-C05161C42E01-MALFORMED-FRONTMATTER', marks=pytest.mark.cer_assertion('A-C05161C42E01-MALFORMED-FRONTMATTER')),
    pytest.param('frontmatter:variants', 'A-C05161C42E01-MISSING-FRONTMATTER', ['FRONTMATTER_BOUNDARY_MISMATCH'], id='O-C05161C42E01-A-C05161C42E01-MISSING-FRONTMATTER', marks=pytest.mark.cer_assertion('A-C05161C42E01-MISSING-FRONTMATTER')),
    pytest.param('frontmatter:variants', 'A-C05161C42E01-UNSUPPORTED-EXTENSION', ['FRONTMATTER_BOUNDARY_MISMATCH'], id='O-C05161C42E01-A-C05161C42E01-UNSUPPORTED-EXTENSION', marks=pytest.mark.cer_assertion('A-C05161C42E01-UNSUPPORTED-EXTENSION')),
    pytest.param('frontmatter:empty', 'A-SM-A03-DESCRIPTION-NONEMPTY', ['EMPTY_SKILL_METADATA_ACCEPTED'], id='O-A54DEED7E747-A-SM-A03-DESCRIPTION-NONEMPTY', marks=pytest.mark.cer_assertion('A-SM-A03-DESCRIPTION-NONEMPTY')),
    pytest.param('frontmatter:empty', 'A-SM-A03-NAME-NONEMPTY', ['EMPTY_SKILL_METADATA_ACCEPTED'], id='O-A54DEED7E747-A-SM-A03-NAME-NONEMPTY', marks=pytest.mark.cer_assertion('A-SM-A03-NAME-NONEMPTY')),
])
def test_a03_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
    root,package,mode,oracle=prepare_scenario(tmp_path,scenario,assertion)
    effects=[];outside=root/'outside.md';original=Path.open
    def observed(self,*args,**kwargs):
        if self.resolve()==outside.resolve(): effects.append('forbidden-read')
        return original(self,*args,**kwargs)
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Inspected declarations must remain static data')
    with monkeypatch.context() as patch:
        patch.setattr(Path,'open',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen'),(os,'system')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
    valid=not effects and oracle(result)
    if not valid:
        for failure_id in failure_ids: print('FAILURE_ID:'+failure_id)
    assert valid, 'Required independent declaration outcome is missing: '+scenario+' / '+assertion


@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('lines:invariance', 'ASSERT-SM-A04-LINE-ENDING-INVARIANCE', ['FAIL_SM_A04_LINE_ENDINGS'], id='O-DAC3487BE1C1-ASSERT-SM-A04-LINE-ENDING-INVARIANCE', marks=pytest.mark.cer_assertion('ASSERT-SM-A04-LINE-ENDING-INVARIANCE')),
    pytest.param('lines:boundary', 'A-ACF8FD2D2E95-499-PASS', ['SKILL_LINE_GATE_MISMATCH'], id='O-ACF8FD2D2E95-A-ACF8FD2D2E95-499-PASS', marks=pytest.mark.cer_assertion('A-ACF8FD2D2E95-499-PASS')),
    pytest.param('lines:boundary', 'A-ACF8FD2D2E95-500-REJECT', ['SKILL_LINE_GATE_MISMATCH'], id='O-ACF8FD2D2E95-A-ACF8FD2D2E95-500-REJECT', marks=pytest.mark.cer_assertion('A-ACF8FD2D2E95-500-REJECT')),
    pytest.param('lines:boundary', 'A-ACF8FD2D2E95-501-REJECT', ['SKILL_LINE_GATE_MISMATCH'], id='O-ACF8FD2D2E95-A-ACF8FD2D2E95-501-REJECT', marks=pytest.mark.cer_assertion('A-ACF8FD2D2E95-501-REJECT')),
    pytest.param('lines:final', 'ASSERT-SM-A04-FINAL-NEWLINE-INVARIANCE', ['FAIL_SM_A04_FINAL_NEWLINE'], id='O-D5C4644942C0-ASSERT-SM-A04-FINAL-NEWLINE-INVARIANCE', marks=pytest.mark.cer_assertion('ASSERT-SM-A04-FINAL-NEWLINE-INVARIANCE')),
])
def test_a04_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
    root,package,mode,oracle=prepare_scenario(tmp_path,scenario,assertion)
    effects=[];outside=root/'outside.md';original=Path.open
    def observed(self,*args,**kwargs):
        if self.resolve()==outside.resolve(): effects.append('forbidden-read')
        return original(self,*args,**kwargs)
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Inspected declarations must remain static data')
    with monkeypatch.context() as patch:
        patch.setattr(Path,'open',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen'),(os,'system')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
    valid=not effects and oracle(result)
    if not valid:
        for failure_id in failure_ids: print('FAILURE_ID:'+failure_id)
    assert valid, 'Required independent declaration outcome is missing: '+scenario+' / '+assertion


@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('static:remote', 'ASSERT-O-C18F4E850EDF-NO-REMOTE-DOC-FETCH', ['FAIL_O_C18F4E850EDF_REMOTE_FETCH'], id='O-C18F4E850EDF-ASSERT-O-C18F4E850EDF-NO-REMOTE-DOC-FETCH', marks=pytest.mark.cer_assertion('ASSERT-O-C18F4E850EDF-NO-REMOTE-DOC-FETCH')),
    pytest.param('reference:remote-required', 'A-O87087A4FB14C-LOCAL-SOURCE-ONLY', ['FAIL_O87087A4FB14C_REMOTE_SOURCE_SUBSTITUTION'], id='O-87087A4FB14C-A-O87087A4FB14C-LOCAL-SOURCE-ONLY', marks=pytest.mark.cer_assertion('A-O87087A4FB14C-LOCAL-SOURCE-ONLY')),
    pytest.param('reference:reachable', 'ASSERT-SM-A05-LOCAL-REFERENCE-REACHABILITY', ['FAIL_SM_A05_LOCAL_REFERENCE'], id='O-0250CBD01B72-ASSERT-SM-A05-LOCAL-REFERENCE-REACHABILITY', marks=pytest.mark.cer_assertion('ASSERT-SM-A05-LOCAL-REFERENCE-REACHABILITY')),
])
def test_a05_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
    root,package,mode,oracle=prepare_scenario(tmp_path,scenario,assertion)
    effects=[];outside=root/'outside.md';original=Path.open
    def observed(self,*args,**kwargs):
        if self.resolve()==outside.resolve(): effects.append('forbidden-read')
        return original(self,*args,**kwargs)
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Inspected declarations must remain static data')
    with monkeypatch.context() as patch:
        patch.setattr(Path,'open',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen'),(os,'system')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
    valid=not effects and oracle(result)
    if not valid:
        for failure_id in failure_ids: print('FAILURE_ID:'+failure_id)
    assert valid, 'Required independent declaration outcome is missing: '+scenario+' / '+assertion


@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('diagnostics:secrets', 'A-9F6EBBDA8D40-1', ['A06_OUTPUT_METADATA'], id='O-9F6EBBDA8D40-A-9F6EBBDA8D40-1', marks=pytest.mark.cer_assertion('A-9F6EBBDA8D40-1')),
])
def test_a06_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
    root,package,mode,oracle=prepare_scenario(tmp_path,scenario,assertion)
    effects=[];outside=root/'outside.md';original=Path.open
    def observed(self,*args,**kwargs):
        if self.resolve()==outside.resolve(): effects.append('forbidden-read')
        return original(self,*args,**kwargs)
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Inspected declarations must remain static data')
    with monkeypatch.context() as patch:
        patch.setattr(Path,'open',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen'),(os,'system')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
    valid=not effects and oracle(result)
    if not valid:
        for failure_id in failure_ids: print('FAILURE_ID:'+failure_id)
    assert valid, 'Required independent declaration outcome is missing: '+scenario+' / '+assertion


@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('routing:false-leaf', 'A08-FALSE-LEAF-CLASSIFICATION', ['FALSE_LEAF_CLASSIFICATION_NOT_REJECTED'], id='O-480F9731ED2D-A08-FALSE-LEAF-CLASSIFICATION', marks=pytest.mark.cer_assertion('A08-FALSE-LEAF-CLASSIFICATION')),
    pytest.param('routing:unresolved', 'A08-UNRESOLVED-BRANCH-FAILURE', ['UNRESOLVED_BRANCH_NOT_REJECTED'], id='O-0976854BA162-A08-UNRESOLVED-BRANCH-FAILURE', marks=pytest.mark.cer_assertion('A08-UNRESOLVED-BRANCH-FAILURE')),
])
def test_a08_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
    root,package,mode,oracle=prepare_scenario(tmp_path,scenario,assertion)
    effects=[];outside=root/'outside.md';original=Path.open
    def observed(self,*args,**kwargs):
        if self.resolve()==outside.resolve(): effects.append('forbidden-read')
        return original(self,*args,**kwargs)
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Inspected declarations must remain static data')
    with monkeypatch.context() as patch:
        patch.setattr(Path,'open',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen'),(os,'system')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
    valid=not effects and oracle(result)
    if not valid:
        for failure_id in failure_ids: print('FAILURE_ID:'+failure_id)
    assert valid, 'Required independent declaration outcome is missing: '+scenario+' / '+assertion


@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('invocation:tests:missing', 'A-O-15F898F7D82D-1', ['A11_TEST_COVERAGE'], id='O-15F898F7D82D-A-O-15F898F7D82D-1', marks=pytest.mark.cer_assertion('A-O-15F898F7D82D-1')),
    pytest.param('invocation:script:missing', 'A-O-C0EBEEDDC609-1', ['FI_COMPLEX_CHECK_SCRIPT_ENTRY_REJECTED'], id='O-C0EBEEDDC609-A-O-C0EBEEDDC609-1', marks=pytest.mark.cer_assertion('A-O-C0EBEEDDC609-1')),
    pytest.param('invocation:timeout:0', 'A-O-97484DA36E34-1', ['TIMEOUT_BOUND_VALIDATION_FAILURE'], id='O-1BEFAF8FAD91-A-O-97484DA36E34-1', marks=pytest.mark.cer_assertion('A-O-97484DA36E34-1')),
    pytest.param('invocation:shell:true', 'A-O-77F47DD1592B-1', ['FI_O77F47DD1592B_SHELL_FALSE'], id='O-77F47DD1592B-A-O-77F47DD1592B-1', marks=pytest.mark.cer_assertion('A-O-77F47DD1592B-1')),
])
def test_a11_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
    root,package,mode,oracle=prepare_scenario(tmp_path,scenario,assertion)
    effects=[];outside=root/'outside.md';original=Path.open
    def observed(self,*args,**kwargs):
        if self.resolve()==outside.resolve(): effects.append('forbidden-read')
        return original(self,*args,**kwargs)
    def denied(*args,**kwargs):
        effects.append('execution-or-network')
        raise RuntimeError('Inspected declarations must remain static data')
    with monkeypatch.context() as patch:
        patch.setattr(Path,'open',observed)
        for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'create_connection'),(urllib.request,'urlopen'),(os,'system')):
            patch.setattr(module,name,denied)
        args,kwargs=invocation_args(validate_package,root,package,mode)
        result=validate_package(*args,**kwargs)
    valid=not effects and oracle(result)
    if not valid:
        for failure_id in failure_ids: print('FAILURE_ID:'+failure_id)
    assert valid, 'Required independent declaration outcome is missing: '+scenario+' / '+assertion



# Independent boundary fixtures; no producer policy is used as an oracle.
@pytest.mark.parametrize('declaration', [
    pytest.param(('schema','skill-quality.v99'),id='unsupported-version'),
    pytest.param(('capabilities',[]),id='malformed-top-level-type'),
    pytest.param(('unknown-owned-field',True),id='unknown-owned-field'),
    pytest.param(('responsibility',{'ref':'references/absent.md#required'}),id='unresolved-local-reference'),
])
def test_a02_rejects_independent_contract_defects(tmp_path,declaration):
    root,package,value=dependency_package(tmp_path)
    value[declaration[0]]=declaration[1];write_contract(package,value)
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    require(result['status']=='fail' and result['exit_code']==1 and result['authorizes']==[] and result['diagnostics'], 'FAIL_O_06F56FA829B4')


@pytest.mark.parametrize('capability,field,malformed', [
    ('untrusted_content','prohibit_expansion',True),
    ('untrusted_content','prohibit_expansion',[{}]),
    ('destructive','authorization_source',{}),
    ('network','targets',[{}]),
    ('network','owner',['not-a-string']),
    ('network','internal_exceptions',[{'kind':'controlled-internal-mcp','owner':{},'authority':[]}]),
    ('secrets','unknown-owned-field',True),
])
def test_a02_nested_control_types_are_structured_rejections(tmp_path,capability,field,malformed):
    from copy import deepcopy
    from scripts.sc.tests.skill_quality_support import CONTROL_FIXTURES
    root,package,value=dependency_package(tmp_path)
    value['capabilities'][capability]=True
    value['controls'][capability]=deepcopy(CONTROL_FIXTURES[capability]);write_contract(package,value)
    positive=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert positive['status']=='pass',positive
    value['controls'][capability][field]=malformed;write_contract(package,value)
    try: result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    except (TypeError,AttributeError,RecursionError):result=None
    require(isinstance(result,dict) and result['status']=='fail' and result['exit_code']==1
            and result['authorizes']==[] and any(d['rule']=='A02' for d in result['diagnostics']), 'FAIL_O_06F56FA829B4')


def test_a02_deep_json_is_bounded_rejection(tmp_path):
    root,package,value=dependency_package(tmp_path)
    nested='leaf'
    for _ in range(110):nested={'child':nested}
    value['unknown-owned-field']=nested;write_contract(package,value)
    try:result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    except RecursionError:result=None
    require(isinstance(result,dict) and result['status']=='fail' and result['exit_code']==1 and result['diagnostics'], 'FAIL_O_06F56FA829B4')


@pytest.mark.parametrize('frontmatter', [
    '', 'name: reference-skill\ndescription: Inspect local sample.\n',
    '---\nname:reference-skill\ndescription: Valid prose\n---\n',
    '---\nname: reference-skill\ndescription: true\n---\n',
    '---\nname: reference-skill\ndescription: 123\n---\n',
])
def test_a03_safe_string_frontmatter(tmp_path,frontmatter):
    root,package,_=dependency_package(tmp_path)
    (package/'SKILL.md').write_text(frontmatter+'# Actual body\nInspect the local package.\n')
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    require(result['status']=='fail' and any(d['rule']=='A03' and d['path']=='SKILL.md' for d in result['diagnostics']), 'MISSING_FRONTMATTER_ACCEPTED')


@pytest.mark.parametrize('field',['responsibility','triggers','non_goals','inputs','outputs','tests','evidence'])
def test_a01_empty_referenced_section_cannot_borrow_other_content(tmp_path,field):
    root,package,value=dependency_package(tmp_path)
    reference=package/'references/required.md'
    reference.write_text('# Required\n\nSubstantive required declaration.\n\n# Other\nUnrelated substantive text.\n')
    entry={'ref':'references/required.md#required'}
    value[field]=[entry] if field in {'triggers','non_goals','inputs','outputs','tests'} else entry
    write_contract(package,value)
    assert validate_package(repository_root=root,package_root=package,policy_path=POLICY)['status']=='pass'
    reference.write_text('# Required\n\n# Other\nUnrelated substantive text.\n')
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    require(result['status']=='fail' and any(d['rule']=='A01' and d['path'].startswith('skill-quality.v1.json#/'+field) for d in result['diagnostics']), 'FAIL_O_945D42143461')


@pytest.mark.parametrize('category',['blank','frontmatter','code'])
@pytest.mark.cer_assertion('REPAIR_O_7E8E1F30B868')
def test_a04_counts_all_logical_line_categories(tmp_path,category):
    root,package,_=dependency_package(tmp_path)
    if category=='frontmatter':prefix=['---','name: reference-skill','description: |','  Inspect local sample.','  Return a structured report.','---']
    else:prefix=['---','name: reference-skill','description: Inspect local sample.','---']
    filler='' if category=='blank' else 'A substantive body line.'
    body=[filler]*(499-len(prefix))
    if category=='code':body[:3]=['```python','print("declaration only")','```']
    lines=prefix+body;assert len(lines)==499
    (package/'SKILL.md').write_text('\n'.join(lines)+'\n')
    assert validate_package(repository_root=root,package_root=package,policy_path=POLICY)['status']=='pass'
    (package/'SKILL.md').write_text('\n'.join(lines+[''])+'\n')
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    require(result['status']=='fail' and any(d['rule']=='A04' for d in result['diagnostics']), 'FAIL_O_7E8E1F30B868')


@pytest.mark.parametrize('case,status,exit_code', [('pass','pass',0),('fail','fail',1),('error','error',2),('legacy','legacy',3)])
@pytest.mark.cer_assertion('REPAIR_O_19FB7DD356B0')
def test_a24_actual_cli_api_four_outcomes(tmp_path,case,status,exit_code):
    root,package,value=dependency_package(tmp_path);mode='inventory' if case=='legacy' else 'strict';policy=POLICY
    if case=='fail':value['inputs']=[];write_contract(package,value)
    if case=='error':policy='scripts/sc/config/absent-policy.json'
    if case=='legacy':(package/'skill-quality.v1.json').unlink()
    result=validate_package(repository_root=root,package_root=package,policy_path=policy,mode=mode)
    process=subprocess.run([sys.executable,'-B','scripts/sc/validate_skill_quality.py','--repository-root',str(root),'--policy',policy,'--skill-root',str(package),'--mode',mode],cwd=REPOSITORY,shell=False,capture_output=True,text=True,timeout=300)
    actual=json.loads(process.stdout)
    require(actual==result and process.returncode==exit_code and actual['status']==status
            and actual['exit_code']==exit_code and actual['authorizes']==[] and not process.stderr,
            'FAIL_O_19FB7DD356B0')


@pytest.mark.parametrize('defect',['policy-version','schema-version','unused-policy','result-schema','standard-link','invalid-reference'])
@pytest.mark.cer_assertion('A-4E7-TERMINAL-GATE')
def test_a24_terminal_inputs_reject_each_defect(tmp_path,defect):
    root,package,value=dependency_package(tmp_path)
    if defect in {'policy-version','unused-policy','standard-link'}:
        path=root/POLICY;policy=json.loads(path.read_text())
        if defect=='policy-version':policy['standard_version']='99.0'
        elif defect=='unused-policy':policy['rules']=[]
        else:policy['standard']='docs/standards/absent.md'
        path.write_text(json.dumps(policy))
    elif defect in {'schema-version','result-schema'}:
        path=root/('scripts/sc/schemas/skill-quality-contract.v1.schema.json' if defect=='schema-version' else 'scripts/sc/schemas/skill-quality-result.v1.schema.json')
        schema=json.loads(path.read_text())
        if defect=='schema-version':schema['standard_version']='99.0'
        else:schema['properties']['status']={'const':'impossible'}
        path.write_text(json.dumps(schema))
    else:value['responsibility']={'ref':'references/absent.md'};write_contract(package,value)
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    require(result['status'] in {'error','fail'} and result['exit_code'] in {1,2} and result['diagnostics'] and result['authorizes']==[], 'FAIL_O_00C011A2BAE8')


@pytest.mark.cer_assertion('REPAIR_O_33FC9FCE9C75')
def test_a24_declared_terminal_selection_has_all_four_modules():
    # Admission guard only. Actual execution is proved separately by native Q8.
    context=json.loads((REPOSITORY/'execution-plans/2026-08-06-skill-authoring-standard/package-a-completion-plan/agent-context/S21-R2/agent-context.json').read_text())
    required={'scripts/sc/tests/test_skill_quality_'+name+'.py' for name in ('core','capabilities','examples','migration')}
    declared={arg for command in context['validation_commands'] for arg in command if arg.endswith('.py')}
    assert required<=declared, 'The terminal selection must retain all four declared modules'


@pytest.mark.cer_assertion('REPAIR_O_06F56FA829B4')
def test_a02_complete_malformed_contract_matrix(tmp_path):
    from copy import deepcopy
    from scripts.sc.tests.skill_quality_support import CONTROL_FIXTURES
    mutations=[('top','schema','skill-quality.v99'),('top','capabilities',[]),('top','unknown-owned-field',True),
               ('top','responsibility',{'ref':'references/absent.md#required'}),
               ('untrusted_content','prohibit_expansion',True),('untrusted_content','prohibit_expansion',[{}]),
               ('destructive','authorization_source',{}),('network','targets',[{}]),('network','owner',['not-a-string']),
               ('network','internal_exceptions',[{'kind':'controlled-internal-mcp','owner':{},'authority':[]}]),
               ('secrets','unknown-owned-field',True)]
    violations=[]
    for index,(cap,field,bad) in enumerate(mutations):
        root,package,value=dependency_package(tmp_path/str(index))
        if cap!='top':value['capabilities'][cap]=True;value['controls'][cap]=deepcopy(CONTROL_FIXTURES[cap])
        write_contract(package,value)
        assert validate_package(repository_root=root,package_root=package,policy_path=POLICY)['status']=='pass'
        target=value if cap=='top' else value['controls'][cap];target[field]=bad;write_contract(package,value)
        try:result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
        except (TypeError,AttributeError,RecursionError):result=None
        if not (isinstance(result,dict) and result['status']=='fail' and result['exit_code']==1 and result['authorizes']==[] and result['diagnostics']):violations.append((cap,field))
    require(not violations,'FAIL_O_06F56FA829B4')


@pytest.mark.cer_assertion('A-O-93C7DC1F898B-1')
def test_a03_complete_frontmatter_rejection_matrix(tmp_path):
    invalid=['','name: reference-skill\ndescription: Inspect local sample.\n',
             '---\nname:reference-skill\ndescription: Valid prose\n---\n',
             '---\nname: reference-skill\ndescription: true\n---\n',
             '---\nname: reference-skill\ndescription: 123\n---\n']
    outcomes=[]
    for index,text in enumerate(invalid):
        root,package,_=dependency_package(tmp_path/str(index));(package/'SKILL.md').write_text(text+'# Body\nSubstantive input.\n')
        result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
        outcomes.append(result['status']=='fail' and any(d['rule']=='A03' and d['path']=='SKILL.md' for d in result['diagnostics']))
    require(all(outcomes),'MISSING_FRONTMATTER_ACCEPTED')


@pytest.mark.cer_assertion('REPAIR_O_945D42143461')
def test_a01_complete_empty_section_matrix(tmp_path):
    outcomes=[]
    for field in ('responsibility','triggers','non_goals','inputs','outputs','tests','evidence'):
        root,package,value=dependency_package(tmp_path/field);reference=package/'references/required.md'
        reference.write_text('# Required\n\nSubstantive required declaration.\n\n# Other\nUnrelated substantive text.\n')
        entry={'ref':'references/required.md#required'};value[field]=[entry] if field in {'triggers','non_goals','inputs','outputs','tests'} else entry;write_contract(package,value)
        assert validate_package(repository_root=root,package_root=package,policy_path=POLICY)['status']=='pass'
        reference.write_text('# Required\n\n# Other\nUnrelated substantive text.\n')
        result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
        outcomes.append(result['status']=='fail' and any(d['rule']=='A01' and d['path'].startswith('skill-quality.v1.json#/'+field) for d in result['diagnostics']))
    require(all(outcomes),'FAIL_O_945D42143461')


@pytest.mark.parametrize('obligation,phrases',[
    pytest.param('O-7E51316B0CE4',['substantive triggers', 'invocation and applicability triggers'],id='O-7E51316B0CE4',marks=[pytest.mark.cer_assertion('A-SM-A01-TRIGGER-DEFINITION')]),
    pytest.param('O-7698135E1B46',['declarations only', 'phase/runner', 'runtime security'],id='O-7698135E1B46',marks=[pytest.mark.cer_assertion('ASSERT_RUNTIME_ENFORCEMENT_CLAIM_BOUNDARY')]),
    pytest.param('O-E77AA1A9EA4B',['read-only static', 'no lookup executes', 'knowledge-query workflow'],id='O-E77AA1A9EA4B',marks=[pytest.mark.cer_assertion('ASSERT_REPOSITORY_BOUNDARY_NO_WORKFLOW')]),
    pytest.param('O-498AA134E62A',['tests', 'evidence', 'lifecycle boundaries'],id='O-498AA134E62A',marks=[pytest.mark.cer_assertion('A-SM-A01-TEST-DEFINITION')]),
    pytest.param('O-5DE3F2879F77',['dependency records declare id', 'required boolean', 'authority', 'when_missing'],id='O-5DE3F2879F77',marks=[pytest.mark.cer_assertion('A-SM-A01-DEPENDENCY-DECLARATION')]),
    pytest.param('O-DA0C70E43A5B',['existing runner/job infrastructure remains unchanged', 'cancellation/process-tree owner'],id='O-DA0C70E43A5B',marks=[pytest.mark.cer_assertion('A20-NO-DUPLICATE-SUBPROCESS-INFRA')]),
    pytest.param('O-E271EAED67AA',['versioned quality namespace', 'frontmatter', 'first-level', 'lf/crlf'],id='O-E271EAED67AA',marks=[pytest.mark.cer_assertion('A-E271EAED67AA-DOCUMENTED-TOPICS')]),
    pytest.param('O-89E320D5565C',['external review', 'do not add a new governance skill'],id='O-89E320D5565C',marks=[pytest.mark.cer_assertion('A-STANDARD-EXTERNAL-REVIEW-BOUNDARY')]),
    pytest.param('O-733593552894',['local validator exit semantics only', '0/pass', '1/fail', '2/error', '3/legacy'],id='O-733593552894',marks=[pytest.mark.cer_assertion('assert-exit-code-local-map'),pytest.mark.cer_assertion('assert-no-toolchain-error-taxonomy')]),
    pytest.param('O-CF9F35D73798',['orchestrator', 'linked ascii diagram', 'real leaf', 'needs no diagram'],id='O-CF9F35D73798',marks=[pytest.mark.cer_assertion('A-CF9F35D73798-DIAGRAM-CONDITION'),pytest.mark.cer_assertion('A-CF9F35D73798-LEAF-EXEMPTION')]),
    pytest.param('O-B0742877CF69',['no phase, godot, windows isolation', 'no lookup executes', 'no global total-entry skill'],id='O-B0742877CF69',marks=[pytest.mark.cer_assertion('assert_package_a_scope_excludes_prohibited_additions')]),
    pytest.param('O-A7F16659E19F',['not universal secret detection', 'synthetic'],id='O-A7F16659E19F',marks=[pytest.mark.cer_assertion('ASSERT_SM_A15_NO_UNIVERSAL_SECRET_DETECTION_CLAIM')]),
    pytest.param('O-3FD46F386819',['no dns, url request, network-tool installation or command'],id='O-3FD46F386819',marks=[pytest.mark.cer_assertion('A21-NO-NETWORK-TOOL-INSTALL')]),
    pytest.param('O-52DE3A3C47ED',['evidence', 'lifecycle boundaries', 'caller owns real execution evidence'],id='O-52DE3A3C47ED',marks=[pytest.mark.cer_assertion('A-SM-A01-EVIDENCE-DEFINITION')]),
    pytest.param('O-1C9455666CAA',['private/loopback/metadata', 'owner'],id='O-1C9455666CAA',marks=[pytest.mark.cer_assertion('A21-ADDR-OWNER')]),
    pytest.param('O-FD717A6F40DD',['skill-quality.v1.json', 'beside skill.md'],id='O-FD717A6F40DD',marks=[pytest.mark.cer_assertion('A-FD717A6F40DD-1')]),
    pytest.param('O-D88E8B8E0988',['https', 'schemes/targets', 'network controls declare'],id='O-D88E8B8E0988',marks=[pytest.mark.cer_assertion('A21_NETWORK_SCHEME_ALLOWLIST'),pytest.mark.cer_assertion('A21_NETWORK_TARGET_ALLOWLIST')]),
    pytest.param('O-6E6EED17C1E3',['vdd owns plan-ready', 'quick dev owns implementation-complete', 'acceptance', 'bootstrap review is optional'],id='O-6E6EED17C1E3',marks=[pytest.mark.cer_assertion('A25_HANDOFF_EXISTING_AUTHORITY_PRESERVED')]),
    pytest.param('O-BF960FA05C37',['exactly one primary responsibility'],id='O-BF960FA05C37',marks=[pytest.mark.cer_assertion('A-SM-A01-REQUIRED-AREAS')]),
    pytest.param('O-FAF28A995120',['references resolve inside the selected package', 'direct first-level existing local file and anchor'],id='O-FAF28A995120',marks=[pytest.mark.cer_assertion('SM_A01_REFERENCES_EXPLICIT_DEFINITION'),pytest.mark.cer_assertion('SM_A01_REFERENCES_SUBSTANTIVE_CONTENT')]),
    pytest.param('O-C09E6A7DB23F',['package a completion never', 'requires all five real skills to pass'],id='O-C09E6A7DB23F',marks=[pytest.mark.cer_assertion('A25_NO_FIVE_SKILL_COMPLIANCE_GATE')]),
    pytest.param('O-45EC43D9BAB4',['# repository skill authoring standard', 'standard version: 1.0'],id='O-45EC43D9BAB4',marks=[pytest.mark.cer_assertion('STANDARD_DELIVERABLE_PRESENT')]),
    pytest.param('O-CA4ACB6E93E2',['existing phase/runner entrypoints retain', 'enforcement'],id='O-CA4ACB6E93E2',marks=[pytest.mark.cer_assertion('A-O-92F56D01C02C-CAPABILITY-OWNERS')]),
    pytest.param('O-FECC4A9F7100',['fewer than 500', 'prefer a smaller', 'not a second hard gate'],id='O-FECC4A9F7100',marks=[pytest.mark.cer_assertion('ASSERT-SM-A04-SINGLE-HARD-GATE-GUIDANCE')]),
])
def test_a01_normative_standard_obligations(tmp_path,obligation,phrases):
    root,package,_=dependency_package(tmp_path)
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert result['status']=='pass' and result['authorizes']==[]
    standard=(REPOSITORY/'docs/standards/skill-authoring-standard.md').read_text().lower()
    normalized=' '.join(standard.split())
    assert all(phrase in normalized for phrase in phrases),(obligation,phrases)


@pytest.mark.cer_assertion('A-FCBEC7979A9D-1')
def test_a03_unknown_frontmatter_key_rejected(tmp_path):
    root,package,_=dependency_package(tmp_path);skill=package/'SKILL.md';skill.write_text(skill.read_text().replace('description:', 'unknown-owned-key: true\ndescription:'))
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert result['status']=='fail' and any(d['rule']=='A03' for d in result['diagnostics'])


@pytest.mark.cer_assertion('A-O-34DAA82F5AC5-1')
def test_a06_local_schema_implementation_has_no_assumed_dependency(tmp_path):
    root,package,_=dependency_package(tmp_path)
    assert validate_package(repository_root=root,package_root=package,policy_path=POLICY)['status']=='pass'
    standard=(REPOSITORY/'docs/standards/skill-authoring-standard.md').read_text()
    assert 'No new dependency is required.' in standard and 'Existing optional' in standard
    source=(REPOSITORY/'scripts/sc/validate_skill_quality.py').read_text()
    assert 'def _schema_preflight' in source and 'Unsupported schema' in source
    assert 'import jsonschema' not in source and 'pip install' not in source


@pytest.mark.cer_assertion('A-ADR-PATH-COLLISION-001')
@pytest.mark.cer_assertion('ADR0060_ROLE_PRESERVED')
def test_a01_adr_allocation_and_preserved_existing_role(tmp_path):
    root,package,_=dependency_package(tmp_path)
    assert validate_package(repository_root=root,package_root=package,policy_path=POLICY)['status']=='pass'
    reference='a05d343ea697139d989bcdbd5138204fd4f570b4'
    allocated=subprocess.run(['git','ls-tree',reference,'--','docs/adr/ADR-0062-repository-skill-authoring-contract.md'],cwd=REPOSITORY,shell=False,capture_output=True,text=True,timeout=300)
    assert allocated.returncode==0 and allocated.stdout==''
    existing='docs/adr/ADR-0060-skill-input-selection-and-progressive-delivery.md'
    # Exact historical role is selected by the tracked ADR index, not a latest-file scan.
    listing=subprocess.run(['git','ls-tree','-r','--name-only',reference,'--','docs/adr'],cwd=REPOSITORY,shell=False,capture_output=True,text=True,timeout=300)
    names=[name for name in listing.stdout.splitlines() if Path(name).name.startswith('ADR-0060-')]
    assert listing.returncode==0 and len(names)==1
    original=subprocess.run(['git','show',reference+':'+names[0]],cwd=REPOSITORY,shell=False,capture_output=True,timeout=300)
    assert original.returncode == 0
    # ADR-0060 retained its role and all original bytes. Its later accepted
    # mutex clarification is an append, not a reassignment to skill authoring.
    accepted = subprocess.check_output(['git', 'show',
        '25580d700da91d2702fd234a024a616d55419f90:' + names[0]], cwd=REPOSITORY)
    assert accepted.startswith(original.stdout)
    assert (REPOSITORY / names[0]).read_bytes() == accepted
    assert b'## Implementation clarification (2026-10-28)' in accepted[len(original.stdout):]
    adr=REPOSITORY/'docs/adr/ADR-0062-repository-skill-authoring-contract.md'
    assert adr.is_file() and 'ADR-0062' in adr.read_text()
    assert 'ADR-0062' in (REPOSITORY/'docs/architecture/ADR_INDEX_PHASE.md').read_text()


@pytest.mark.cer_assertion('A-C0F95921DA31-DECLARATION-REMOVAL-EXERCISED')
@pytest.mark.cer_assertion('A-C0F95921DA31-INDEPENDENT-REJECTION-CHECKS')
@pytest.mark.cer_assertion('A-C0F95921DA31-REFERENCED-SECTION-REMOVAL-EXERCISED')
@pytest.mark.cer_assertion('A-3F697BEC8FFF-MISSING-DECLARATION')
@pytest.mark.cer_assertion('A-3F697BEC8FFF-MISSING-REFERENCED-CONTENT')
@pytest.mark.parametrize('variant',['declaration','referenced-section'])
def test_a01_required_content_removals_have_located_diagnostics(tmp_path,variant):
    root,package,value=dependency_package(tmp_path)
    if variant=='declaration':value.pop('inputs')
    else:
        value['inputs']=[{'ref':'references/input.md#required'}]
        (package/'references/input.md').write_text('# Required\n\n# Unrelated\nThis unrelated paragraph cannot satisfy the required section.\n')
    write_contract(package,value)
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert result['status']=='fail' and result['authorizes']==[] and any(d['rule']=='A01' and d['path'].startswith('skill-quality.v1.json#/inputs') for d in result['diagnostics']),result


@pytest.mark.cer_assertion('A04_LIMIT_THRESHOLD_DRIFT')
@pytest.mark.cer_assertion('A04_POLICY_SCHEMA_CONSUMPTION_DRIFT')
@pytest.mark.cer_assertion('A04_BOUNDARY_499_PASS')
@pytest.mark.cer_assertion('A04_BOUNDARY_500_FAIL')
@pytest.mark.cer_assertion('A04_BOUNDARY_501_FAIL')
@pytest.mark.cer_assertion('A04_BOUNDARY_COMPLETE_EXECUTION')
def test_a04_boundary_and_owned_policy_threshold_are_consumed(tmp_path):
    root,package,_=dependency_package(tmp_path)
    prefix=['---','name: reference-skill','description: Inspect local sample.','---']
    for count,status in ((499,'pass'),(500,'fail'),(501,'fail')):
        (package/'SKILL.md').write_text('\n'.join(prefix+['A body line.']*(count-len(prefix)))+'\n')
        result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
        assert result['status']==status and result['authorizes']==[],(count,result)
    path=root/POLICY;policy=json.loads(path.read_text());policy['limits']['skill_logical_lines_exclusive']=501;path.write_text(json.dumps(policy))
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert result['status']=='error' and result['exit_code']==2


@pytest.mark.cer_assertion('A-O-49DAD46B110F-ASSERT-1')
def test_a01_final_plan_has_distinct_atomic_assertion_identity():
    plan=REPOSITORY/'execution-plans/2026-08-06-skill-authoring-standard/package-a-completion-plan/semantic-plan-bundle.v1.json'
    bundle=json.loads(plan.read_text());seen={};obligations=set()
    for acceptance in bundle['acceptances']:
        assert len(acceptance['obligation_ids'])==1
        oid=acceptance['obligation_ids'][0];obligations.add(oid)
        for marker in acceptance['assertion_ids']:
            assert marker not in seen or seen[marker]==oid,(marker,seen.get(marker),oid)
            seen[marker]=oid
    assert obligations=={o['obligation_id'] for o in bundle['obligations'] if o['status']=='active'}


@pytest.mark.cer_assertion('A-AC55E09567C3-1')
def test_a02_actual_version_and_rule_vocabulary_alignment(tmp_path):
    root,package,value=dependency_package(tmp_path)
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert result['status']=='pass' and result['authorizes']==[]
    expected=['A%02d'%number for number in range(1,26)]
    paths=[POLICY,'scripts/sc/schemas/skill-quality-contract.v1.schema.json','scripts/sc/schemas/skill-quality-result.v1.schema.json']
    for path in paths:
        artifact=json.loads((REPOSITORY/path).read_text());assert artifact['standard_version']=='1.0' and artifact['rules']==expected
    assert value['standard_version']=='1.0'
    standard=(REPOSITORY/'docs/standards/skill-authoring-standard.md').read_text()
    assert 'Standard version: 1.0' in standard and all('| '+rule+' |' in standard for rule in expected)


# ADR-0062: bounded counterexamples for the accepted Package A result contract.
# Existing A06 assertions own these API/CLI outcomes; domain rules are checked.
@pytest.mark.cer_assertion('A-DC9328497131-FAIL-STATUS')
@pytest.mark.parametrize('defect,mode', [
    ('entry-missing', 'strict'),
    ('entry-missing', 'inventory'),
    ('entry-null', 'strict'),
    ('entry-null', 'inventory'),
    ('entry-unknown', 'strict'),
    ('entry-unknown', 'inventory'),
    ('optional-traversal', 'strict'),
    ('optional-traversal', 'inventory'),
    ('optional-absolute', 'strict'),
    ('optional-absolute', 'inventory'),
    ('optional-symlink', 'strict'),
    ('optional-symlink', 'inventory'),
    ('optional-malformed', 'strict'),
    ('optional-malformed', 'inventory'),
    ('optional-wrong-identity', 'strict'),
    ('optional-wrong-identity', 'inventory'),
    ('optional-directory', 'strict'),
    ('optional-directory', 'inventory'),
    ('owner-secrets', 'strict'),
    ('owner-secrets', 'inventory'),
    ('owner-destructive', 'strict'),
    ('owner-destructive', 'inventory'),
    ('owner-database_write', 'strict'),
    ('owner-database_write', 'inventory'),
    ('owner-untrusted_content', 'strict'),
    ('owner-untrusted_content', 'inventory'),
    ('owner-filesystem', 'strict'),
    ('owner-filesystem', 'inventory'),
    ('owner-subprocess', 'strict'),
    ('owner-subprocess', 'inventory'),
    ('owner-network', 'strict'),
    ('owner-network', 'inventory'),
    ('quote-interior', 'strict'),
    ('quote-interior', 'inventory'),
    ('quote-trailing', 'strict'),
    ('quote-trailing', 'inventory'),
    ('quote-unclosed', 'strict'),
    ('quote-unclosed', 'inventory'),
], ids=['entry-missing-strict', 'entry-missing-inventory', 'entry-null-strict', 'entry-null-inventory', 'entry-unknown-strict', 'entry-unknown-inventory', 'optional-traversal-strict', 'optional-traversal-inventory', 'optional-absolute-strict', 'optional-absolute-inventory', 'optional-symlink-strict', 'optional-symlink-inventory', 'optional-malformed-strict', 'optional-malformed-inventory', 'optional-wrong-identity-strict', 'optional-wrong-identity-inventory', 'optional-directory-strict', 'optional-directory-inventory', 'owner-secrets-strict', 'owner-secrets-inventory', 'owner-destructive-strict', 'owner-destructive-inventory', 'owner-database_write-strict', 'owner-database_write-inventory', 'owner-untrusted_content-strict', 'owner-untrusted_content-inventory', 'owner-filesystem-strict', 'owner-filesystem-inventory', 'owner-subprocess-strict', 'owner-subprocess-inventory', 'owner-network-strict', 'owner-network-inventory', 'quote-interior-strict', 'quote-interior-inventory', 'quote-trailing-strict', 'quote-trailing-inventory', 'quote-unclosed-strict', 'quote-unclosed-inventory'])
def test_a06_p2_defective_declaration_result(tmp_path, monkeypatch, defect, mode):
    from copy import deepcopy
    from scripts.sc.tests.skill_quality_support import CONTROL_FIXTURES
    root, package, value = dependency_package(tmp_path)
    rule = 'A09'
    (package/'references/fallback.md').write_text('# Fallback\nReturn an unavailable report.\n', encoding='utf-8')
    outside = root/'outside.json'
    outside.write_text('{"id":"local-parser","version":"1.2.3","sentinel":"FORBIDDEN_P2_READ"}', encoding='utf-8')
    outside_before = outside.read_bytes()
    if defect.startswith('entry-'):
        value['entrypoints'][0]['dependencies'] = []
    elif defect.startswith('optional-'):
        value['dependencies'][0].update(required=False, authority='references/absent.json', when_missing='fallback',
            fallback={'ref':'references/fallback.md','authorizes':[]})
    elif defect.startswith('owner-'):
        kind = defect.removeprefix('owner-')
        value['capabilities'][kind] = True
        value['controls'][kind] = deepcopy(CONTROL_FIXTURES[kind])
        (package/'references/backup.md').write_text('# Results\nThe owning workflow records actual recovery.\n', encoding='utf-8')
        rule = {'secrets':'A15','destructive':'A16','database_write':'A17','untrusted_content':'A18',
                'filesystem':'A19','subprocess':'A20','network':'A21'}[kind]
    else:
        rule = 'A03'
        (package/'SKILL.md').write_text("---\nname: reference-skill\ndescription: 'inspect''quoted input'\n---\n# Skill\nInspect local input.\n", encoding='utf-8')
    write_contract(package, value)
    control = validate_package(repository_root=root, package_root=package, policy_path=POLICY, mode=mode)
    assert control['status'] == 'pass' and control['exit_code'] == 0, 'The independent valid control must pass'
    if defect == 'entry-missing': value['entrypoints'][0].pop('dependencies')
    elif defect == 'entry-null': value['entrypoints'][0]['dependencies'] = None
    elif defect == 'entry-unknown': value['entrypoints'][0]['dependencies'] = ['undeclared-child']
    elif defect == 'optional-traversal': value['dependencies'][0]['authority'] = '../../outside.json'
    elif defect == 'optional-absolute': value['dependencies'][0]['authority'] = str(outside)
    elif defect == 'optional-symlink':
        (package/'references/linked.json').symlink_to(outside)
        value['dependencies'][0]['authority'] = 'references/linked.json'
    elif defect in {'optional-malformed','optional-wrong-identity'}:
        path = package/'references/broken.json'
        path.write_text('{' if defect == 'optional-malformed' else '{"id":"another","version":"1.2.3"}', encoding='utf-8')
        value['dependencies'][0]['authority'] = 'references/broken.json'
    elif defect == 'optional-directory': value['dependencies'][0]['authority'] = 'references'
    elif defect.startswith('owner-'): value['controls'][kind]['owner'] = ' \t\n '
    else:
        raw = {'quote-interior':"'inspect'broken'",'quote-trailing':"'inspect' tail 'text'",'quote-unclosed':"'inspect"}[defect]
        (package/'SKILL.md').write_text('---\nname: reference-skill\ndescription: '+raw+'\n---\n# Skill\nInspect local input.\n', encoding='utf-8')
    write_contract(package, value)
    forbidden_reads = []
    original_read = Path.read_text
    def observed_read(path, *args, **kwargs):
        if path.resolve() == outside.resolve():
            forbidden_reads.append(True)
            raise AssertionError('Inspection attempted a forbidden authority read')
        return original_read(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'read_text', observed_read)
        result = validate_package(repository_root=root, package_root=package, policy_path=POLICY, mode=mode)
    process = subprocess.run([sys.executable, '-B', str(REPOSITORY/'scripts/sc/validate_skill_quality.py'),
        '--repository-root', str(root), '--policy', POLICY, '--skill-root', str(package), '--mode', mode],
        cwd=REPOSITORY, shell=False, capture_output=True, text=True, timeout=30)
    cli = json.loads(process.stdout)
    allowed_rules = {'A09','A10'} if defect.startswith('entry-') else {rule}
    valid = (result['status']=='fail' and result['exit_code']==1 and result['authorizes']==[]
             and any(d['rule'] in allowed_rules for d in result['diagnostics'])
             and cli==result and process.returncode==1 and not process.stderr
             and not forbidden_reads and outside.read_bytes()==outside_before
             and 'FORBIDDEN_P2_READ' not in process.stdout and str(root) not in process.stdout)
    require(valid, 'FAIL_INSPECTABLE_DEFECT_PASS')


@pytest.mark.cer_assertion('A-A9A489B8935D-1')
@pytest.mark.parametrize('schema_kind,mode', [
    ('contract_schema','strict'), ('contract_schema','inventory'),
    ('result_schema','strict'), ('result_schema','inventory'),
], ids=['contract-strict','contract-inventory','result-strict','result-inventory'])
def test_a06_p2_invalid_schema_regex_result(tmp_path, schema_kind, mode):
    import re
    root, package, _ = dependency_package(tmp_path)
    policy = json.loads((root/POLICY).read_text(encoding='utf-8'))
    path = root/policy[schema_kind]
    schema = json.loads(path.read_text(encoding='utf-8'))
    schema['properties']['schema']['pattern'] = '^[a-z][a-z0-9.-]+$'
    path.write_text(json.dumps(schema), encoding='utf-8')
    assert validate_package(repository_root=root, package_root=package, policy_path=POLICY, mode=mode)['status']=='pass'
    schema['properties']['schema']['pattern'] = '['
    path.write_text(json.dumps(schema), encoding='utf-8')
    try:
        result = validate_package(repository_root=root, package_root=package, policy_path=POLICY, mode=mode)
    except re.error:
        # An observed product parser exception violates its structured API;
        # imports, setup failures and unrelated exceptions are never relabeled.
        result = None
    process = subprocess.run([sys.executable, '-B', str(REPOSITORY/'scripts/sc/validate_skill_quality.py'),
        '--repository-root', str(root), '--policy', POLICY, '--skill-root', str(package), '--mode', mode],
        cwd=REPOSITORY, shell=False, capture_output=True, text=True, timeout=30)
    try: cli = json.loads(process.stdout)
    except json.JSONDecodeError: cli = None
    valid = (isinstance(result,dict) and result['status']=='error' and result['exit_code']==2
             and result['authorizes']==[] and result['diagnostics'] and cli==result
             and process.returncode==2 and not process.stderr and str(root) not in process.stdout)
    require(valid, 'F-A9A489B8935D')
