"""ADR-0041: fixed independent declaration oracles for Package A."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request
import os
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from scripts.sc.validate_skill_quality import validate_package
from scripts.sc.tests.skill_quality_support import prepare_scenario, invocation_args


@pytest.mark.parametrize("scenario,assertion,failure_ids", [
    pytest.param('capability-type', 'A8A11046_CAPABILITY_FLAGS_TYPED', ['CAPABILITY_AUTHORITY_INFERRED'], id='O-A8A11046F7AE-A8A11046_CAPABILITY_FLAGS_TYPED', marks=pytest.mark.cer_assertion('A8A11046_CAPABILITY_FLAGS_TYPED')),
    pytest.param('capability-type', 'A8A11046_NO_INFERRED_AUTHORITY', ['CAPABILITY_AUTHORITY_INFERRED'], id='O-A8A11046F7AE-A8A11046_NO_INFERRED_AUTHORITY', marks=pytest.mark.cer_assertion('A8A11046_NO_INFERRED_AUTHORITY')),
    pytest.param('lookup:policy-origin', 'ASSERT-O244-POLICY-OWNED-HTTPS-ORIGINS', ['O244_POLICY_ORIGIN_AUTHORITY'], id='O-244C3CDAF8D6-ASSERT-O244-POLICY-OWNED-HTTPS-ORIGINS', marks=pytest.mark.cer_assertion('ASSERT-O244-POLICY-OWNED-HTTPS-ORIGINS')),
    pytest.param('cap:composition', 'capabilities_composition_rejects_missing_control', ['COMPOSED_CONTROL_REJECTION'], id='O-A03278BA66AB-capabilities_composition_rejects_missing_control', marks=pytest.mark.cer_assertion('capabilities_composition_rejects_missing_control')),
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
    pytest.param('positive:local', 'A13_LOCAL_FIXTURE_VALIDATION_PASSES', ['A13_LOCAL_FIXTURE_PASS_EXPECTED_RED'], id='O-28B9EF60E1BA-A13_LOCAL_FIXTURE_VALIDATION_PASSES', marks=pytest.mark.cer_assertion('A13_LOCAL_FIXTURE_VALIDATION_PASSES')),
    pytest.param('lookup:false-local', 'A13', ['LOCAL_ONLY_NETWORK_DEPENDENCY_ACCEPTED'], id='O-56ED3B79CFC3-A13', marks=pytest.mark.cer_assertion('A13')),
    pytest.param('lookup:applicability', 'A13-LOCAL-ONLY-DECLARATION', ['LOCAL_ONLY_DECLARATION_MISSING'], id='O-51D1910126F5-A13-LOCAL-ONLY-DECLARATION', marks=pytest.mark.cer_assertion('A13-LOCAL-ONLY-DECLARATION')),
])
def test_a13_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
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
    pytest.param('lookup:missing_policy:', 'A14-missing-information-policy', ['C2EB_MISSING_INFORMATION_POLICY_ACCEPTED'], id='O-C2EB749C891A-A14-missing-information-policy', marks=pytest.mark.cer_assertion('A14-missing-information-policy')),
    pytest.param('lookup:fallback:http://docs.python.org', 'A14_HTTP_FALLBACK_REJECTED', ['HTTP_FALLBACK_STATIC_REJECTION'], id='O-70CAC778D714-A14_HTTP_FALLBACK_REJECTED', marks=pytest.mark.cer_assertion('A14_HTTP_FALLBACK_REJECTED')),
    pytest.param('lookup:fallback:https://arbitrary.invalid', 'A14-REJECT-NONOFFICIAL-FALLBACK', ['A14_NONOFFICIAL_FALLBACK_NOT_REJECTED'], id='O-E214B31B8E50-A14-REJECT-NONOFFICIAL-FALLBACK', marks=pytest.mark.cer_assertion('A14-REJECT-NONOFFICIAL-FALLBACK')),
    pytest.param('lookup:version:', 'A14_VERSION_RECORD_PRESENT', ['A14_VERSION_RECORD_MISSING'], id='O-228C627D16C8-A14_VERSION_RECORD_PRESENT', marks=pytest.mark.cer_assertion('A14_VERSION_RECORD_PRESENT')),
    pytest.param('lookup:preferred:arbitrary', 'A14_CONTEXT7_FIRST_WHEN_AVAILABLE', ['CONTEXT7_FIRST_DECLARATION_MISSING'], id='O-3D687D89E0FE-A14_CONTEXT7_FIRST_WHEN_AVAILABLE', marks=pytest.mark.cer_assertion('A14_CONTEXT7_FIRST_WHEN_AVAILABLE')),
    pytest.param('lookup:source:', 'A14_SOURCE_RECORD_REQUIRED', ['A14_SOURCE_RECORD_VALIDATION_GAP'], id='O-0F3555501763-A14_SOURCE_RECORD_REQUIRED', marks=pytest.mark.cer_assertion('A14_SOURCE_RECORD_REQUIRED')),
    pytest.param('lookup:retrieval_date:', 'A14-retrieval-date-record', ['CDFE_RETRIEVAL_DATE_MISSING_ACCEPTED'], id='O-CDFE3575B803-A14-retrieval-date-record', marks=pytest.mark.cer_assertion('A14-retrieval-date-record')),
    pytest.param('static:lookup', 'A14_NO_LOOKUP_STATIC_VALIDATION', ['NO_LOOKUP_STATIC_VALIDATION_GUARD'], id='O-345CBA33C326-A14_NO_LOOKUP_STATIC_VALIDATION', marks=pytest.mark.cer_assertion('A14_NO_LOOKUP_STATIC_VALIDATION')),
    pytest.param('lookup:version:', 'A14-version-record-missing-rejected', ['A99_VERSION_RECORD_MISSING_ACCEPTED'], id='O-A99A4332AEB4-A14-version-record-missing-rejected', marks=pytest.mark.cer_assertion('A14-version-record-missing-rejected')),
    pytest.param('lookup:official', 'A14_OFFICIAL_HTTPS_FALLBACK', ['OFFICIAL_HTTPS_FALLBACK_MISSING'], id='O-78419D2E4529-A14_OFFICIAL_HTTPS_FALLBACK', marks=pytest.mark.cer_assertion('A14_OFFICIAL_HTTPS_FALLBACK')),
    pytest.param('lookup:failure-policy', 'A14-FAILURE-POLICY-DIAGNOSTIC', ['A14_MISSING_FAILURE_POLICY_NOT_REJECTED'], id='O-F704880C46BB-A14-FAILURE-POLICY-DIAGNOSTIC', marks=pytest.mark.cer_assertion('A14-FAILURE-POLICY-DIAGNOSTIC')),
    pytest.param('lookup:failure-policy', 'A14-FAILURE-POLICY-REJECTION', ['A14_MISSING_FAILURE_POLICY_NOT_REJECTED'], id='O-F704880C46BB-A14-FAILURE-POLICY-REJECTION', marks=pytest.mark.cer_assertion('A14-FAILURE-POLICY-REJECTION')),
    pytest.param('lookup:stale_policy:', 'A14_STALE_INFORMATION_POLICY', ['A14_STALE_POLICY_MISSING'], id='O-0EE266F22792-A14_STALE_INFORMATION_POLICY', marks=pytest.mark.cer_assertion('A14_STALE_INFORMATION_POLICY')),
    pytest.param('lookup:retrieval_date:', 'A14_RETRIEVAL_DATE_REQUIRED', ['A14_RETRIEVAL_DATE_VALIDATION_GAP'], id='O-0F9FB51BD665-A14_RETRIEVAL_DATE_REQUIRED', marks=pytest.mark.cer_assertion('A14_RETRIEVAL_DATE_REQUIRED')),
])
def test_a14_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
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
    pytest.param('cap:secrets:output_policy:raw', 'A-SM-A15-RAW-SECRET-OUTPUT-REJECTED', ['RAW_SECRET_OUTPUT_POLICY_REJECTED'], id='O-7EC6CD93C2B0-A-SM-A15-RAW-SECRET-OUTPUT-REJECTED', marks=pytest.mark.cer_assertion('A-SM-A15-RAW-SECRET-OUTPUT-REJECTED')),
    pytest.param('cap:secrets:reference:', 'A15_SAFE_CREDENTIAL_REFERENCE', ['A15_SAFE_CREDENTIAL_REFERENCE_MISSING'], id='O-3D838423D59D-A15_SAFE_CREDENTIAL_REFERENCE', marks=pytest.mark.cer_assertion('A15_SAFE_CREDENTIAL_REFERENCE')),
    pytest.param('cap:secrets:redaction:', 'A15-ASSERT-REDACTION-POLICY-NAMED', ['A15_REDACTION_POLICY_CONTRACT_GAP'], id='O-B595259141C6-A15-ASSERT-REDACTION-POLICY-NAMED', marks=pytest.mark.cer_assertion('A15-ASSERT-REDACTION-POLICY-NAMED')),
    pytest.param('cap:secrets:owner:', 'A15-missing-runtime-credential-owner-rejected', ['A15_MISSING_CREDENTIAL_OWNER_REJECTED'], id='O-18862EFBC292-A15-missing-runtime-credential-owner-rejected', marks=pytest.mark.cer_assertion('A15-missing-runtime-credential-owner-rejected')),
    pytest.param('artifact:synthetic-secrets', 'A15-ASSERT-CREDENTIAL-FIXTURE-NO-REAL-CREDENTIAL', ['CREDENTIAL_FIXTURE_REAL_SECRET'], id='O-CC550C76EADA-A15-ASSERT-CREDENTIAL-FIXTURE-NO-REAL-CREDENTIAL', marks=pytest.mark.cer_assertion('A15-ASSERT-CREDENTIAL-FIXTURE-NO-REAL-CREDENTIAL')),
    pytest.param('cap:secrets:literal:SYNTHETIC_LITERAL_VALUE', 'A15-SYNTHETIC-LITERAL-SECRET-REJECTED', ['A15_SYNTHETIC_SECRET_BOUNDARY_FAIL'], id='O-C77E3EA0560F-literal-A15-SYNTHETIC-LITERAL-SECRET-REJECTED', marks=pytest.mark.cer_assertion('A15-SYNTHETIC-LITERAL-SECRET-REJECTED')),
    pytest.param('cap:secrets:reference:SYNTHETIC_SECRET_TEST_ONLY', 'A15-SYNTHETIC-LITERAL-SECRET-REJECTED', ['A15_SYNTHETIC_SECRET_BOUNDARY_FAIL'], id='O-C77E3EA0560F-marker-A15-SYNTHETIC-LITERAL-SECRET-REJECTED', marks=pytest.mark.cer_assertion('A15-SYNTHETIC-LITERAL-SECRET-REJECTED')),
])
def test_a15_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
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
    pytest.param('cap:destructive:scope:', 'A-O-16586FD3D7EE-AFFECTED-SCOPE-REJECTED', ['FI_O16586FD3D7EE_MISSING_SCOPE_ACCEPTED'], id='O-16586FD3D7EE-A-O-16586FD3D7EE-AFFECTED-SCOPE-REJECTED', marks=pytest.mark.cer_assertion('A-O-16586FD3D7EE-AFFECTED-SCOPE-REJECTED')),
    pytest.param('cap:destructive:authorization_source:untrusted', 'A16-UNTRUSTED-CONFIRMATION-REJECTED', ['A16_UNTRUSTED_CONFIRMATION_REJECTION'], id='O-D3DFFD9D9560-A16-UNTRUSTED-CONFIRMATION-REJECTED', marks=pytest.mark.cer_assertion('A16-UNTRUSTED-CONFIRMATION-REJECTED')),
    pytest.param('cap:destructive:bypass:true', 'A-O-02906D3E032E-BYPASS-REJECTED', ['A16_BYPASS_REJECTION'], id='O-02906D3E032E-A-O-02906D3E032E-BYPASS-REJECTED', marks=pytest.mark.cer_assertion('A-O-02906D3E032E-BYPASS-REJECTED')),
])
def test_a16_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
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
    pytest.param('cap:database_write:backup:', 'A17_BACKUP_RECOVERY_PREREQUISITES_DECLARED', ['A17_BACKUP_RECOVERY_EXPECTED_RED'], id='O-B7451BC5651B-A17_BACKUP_RECOVERY_PREREQUISITES_DECLARED', marks=pytest.mark.cer_assertion('A17_BACKUP_RECOVERY_PREREQUISITES_DECLARED')),
    pytest.param('cap:database_write:recovery:', 'A17_E7511D8893A7_MISSING_RECOVERY_CONTRACT_FAILS', ['A17_MISSING_RECOVERY_REJECTED'], id='O-E7511D8893A7-A17_E7511D8893A7_MISSING_RECOVERY_CONTRACT_FAILS', marks=pytest.mark.cer_assertion('A17_E7511D8893A7_MISSING_RECOVERY_CONTRACT_FAILS')),
    pytest.param('cap:database_write:recovery:', 'A17_E7511D8893A7_RECOVERY_DIAGNOSTIC_IDENTIFIES_CAPABILITY', ['A17_MISSING_RECOVERY_REJECTED'], id='O-E7511D8893A7-A17_E7511D8893A7_RECOVERY_DIAGNOSTIC_IDENTIFIES_CAPABILITY', marks=pytest.mark.cer_assertion('A17_E7511D8893A7_RECOVERY_DIAGNOSTIC_IDENTIFIES_CAPABILITY')),
])
def test_a17_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
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
    pytest.param('cap:untrusted_content:override:controller', 'A18-FIXTURE-AUTHORITY-INVALID', ['FIXTURE_AUTHORITY_OVERRIDE_ACCEPTED'], id='O-4EC31902CEBC-A18-FIXTURE-AUTHORITY-INVALID', marks=pytest.mark.cer_assertion('A18-FIXTURE-AUTHORITY-INVALID')),
])
def test_a18_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
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
    pytest.param('fs:write:../escape', 'A19-ESCAPING-PATHS-REJECTED', ['A19_ESCAPING_PATH_ACCEPTED'], id='O-39448AEE250F-A19-ESCAPING-PATHS-REJECTED', marks=pytest.mark.cer_assertion('A19-ESCAPING-PATHS-REJECTED')),
    pytest.param('fs:symlink', 'A19-symlink-containment', ['SYMLINK_OUTSIDE_ACCEPTED'], id='O-4108270BED5E-A19-symlink-containment', marks=pytest.mark.cer_assertion('A19-symlink-containment')),
    pytest.param('fs:sentinel', 'A19-forbidden-read-sentinel', ['FORBIDDEN_READ_SENTINEL_UNPROVEN'], id='O-72018A8944F3-A19-forbidden-read-sentinel', marks=pytest.mark.cer_assertion('A19-forbidden-read-sentinel')),
    pytest.param('fs:sentinel', 'A19-FORBIDDEN-READ-SENTINEL-BYTES', ['FORBIDDEN_READ_SENTINEL_MUTATED'], id='O-E1D37DF8393B-A19-FORBIDDEN-READ-SENTINEL-BYTES', marks=pytest.mark.cer_assertion('A19-FORBIDDEN-READ-SENTINEL-BYTES')),
    pytest.param('cap:filesystem:owner:', 'A19-TRAVERSAL-SYMLINK-POLICY-OWNER', ['TRAVERSAL_SYMLINK_POLICY_MISSING'], id='O-E855E9D4651C-A19-TRAVERSAL-SYMLINK-POLICY-OWNER', marks=pytest.mark.cer_assertion('A19-TRAVERSAL-SYMLINK-POLICY-OWNER')),
    pytest.param('fs:sentinel', 'A19-CONTAINMENT-DIAGNOSTIC-SANITIZATION', ['A19_DIAGNOSTIC_LEAK'], id='O-1477C6E10A8C-A19-CONTAINMENT-DIAGNOSTIC-SANITIZATION', marks=pytest.mark.cer_assertion('A19-CONTAINMENT-DIAGNOSTIC-SANITIZATION')),
])
def test_a19_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
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
    pytest.param('cap:subprocess:cancellation_owner:', 'A20-CANCELLATION-PROCESS-TREE-OWNER', ['A20_OWNER_DECLARATION_GAP'], id='O-E684BB93880B-A20-CANCELLATION-PROCESS-TREE-OWNER', marks=pytest.mark.cer_assertion('A20-CANCELLATION-PROCESS-TREE-OWNER')),
])
def test_a20_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
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
    pytest.param('cap:network:targets:*', 'A21-ARBITRARY-TARGET-REJECTED', ['ARBITRARY_TARGET_DECLARATION_ACCEPTED'], id='O-8B60865BCCD7-A21-ARBITRARY-TARGET-REJECTED', marks=pytest.mark.cer_assertion('A21-ARBITRARY-TARGET-REJECTED')),
    pytest.param('cap:network:redirect_owner:', 'A21_REDIRECT_ADDRESS_POLICY_REJECTED', ['A21_REDIRECT_ADDRESS_POLICY_REJECTED'], id='O-855023F9103C-A21_REDIRECT_ADDRESS_POLICY_REJECTED', marks=pytest.mark.cer_assertion('A21_REDIRECT_ADDRESS_POLICY_REJECTED')),
    pytest.param('cap:network:schemes:http', 'A21-http-downgrade-rejected', ['HTTP_DOWNGRADE_REJECTION_MISSING'], id='O-F7BCED0EC996-A21-http-downgrade-rejected', marks=pytest.mark.cer_assertion('A21-http-downgrade-rejected')),
])
def test_a21_contract(tmp_path, monkeypatch, scenario, assertion, failure_ids):
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



from copy import deepcopy
from scripts.sc.tests.skill_quality_support import dependency_package,write_contract,CONTROL_FIXTURES,POLICY


def check_real(result,status,rule=None,failure_id='CAPABILITY_CONTRACT_FAILURE'):
    valid=(isinstance(result,dict) and result.get('status')==status and result.get('exit_code')==(0 if status=='pass' else 1)
           and result.get('authorizes')==[] and (rule is None or any(d['rule']==rule and d['path'] and d['message'] for d in result['diagnostics'])))
    if not valid:print('FAILURE_ID:'+failure_id)
    assert valid,result


@pytest.mark.parametrize('disclosure',['recovery','irreversibility','neither'])
def test_a16_recovery_or_irreversibility_without_extra_confirmation(tmp_path,disclosure):
    root,package,value=dependency_package(tmp_path)
    control=deepcopy(CONTROL_FIXTURES['destructive']);control.pop('bypass');control.pop('recovery')
    if disclosure!='neither':control[disclosure]='The caller owns snapshot restoration.' if disclosure=='recovery' else 'Deletion cannot always be reversed.'
    value['capabilities']['destructive']=True;value['controls']['destructive']=control;write_contract(package,value)
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    check_real(result,'fail' if disclosure=='neither' else 'pass','A16' if disclosure=='neither' else None,'FAIL_O9DA22965FBFF_DISCLOSURE')


@pytest.mark.parametrize('field,marker',[
    pytest.param('redirect_owner','A-4D88A14E3AB8-OWNER',marks=pytest.mark.cer_assertion('A-4D88A14E3AB8-OWNER')),
    pytest.param('dns_owner','A-O-28D7831ED166-DNS-OWNER',marks=pytest.mark.cer_assertion('A-O-28D7831ED166-DNS-OWNER')),
    pytest.param('owner','A-O-20CDF785F117-TIMEOUT-OWNER',marks=pytest.mark.cer_assertion('A-O-20CDF785F117-TIMEOUT-OWNER')),
])
def test_a21_declared_network_owner_is_required(tmp_path,field,marker):
    root,package,value=dependency_package(tmp_path)
    control=deepcopy(CONTROL_FIXTURES['network']);value['capabilities']['network']=True;value['controls']['network']=control;write_contract(package,value)
    check_real(validate_package(repository_root=root,package_root=package,policy_path=POLICY),'pass')
    assert isinstance(control[field],str) and control[field]
    control.pop(field);write_contract(package,value)
    check_real(validate_package(repository_root=root,package_root=package,policy_path=POLICY),'fail','A21')


@pytest.mark.cer_assertion('A-9FA0D5A56DCC-OWNER')
def test_a21_controlled_internal_exception_owner(tmp_path):
    root,package,value=dependency_package(tmp_path)
    control=deepcopy(CONTROL_FIXTURES['network']);control['internal_exceptions']=[{'kind':'controlled-internal-mcp','owner':'Phase internal gateway','authority':'Approved workflow policy'}]
    value['capabilities']['network']=True;value['controls']['network']=control;write_contract(package,value)
    check_real(validate_package(repository_root=root,package_root=package,policy_path=POLICY),'pass')
    del control['internal_exceptions'][0]['owner'];write_contract(package,value)
    check_real(validate_package(repository_root=root,package_root=package,policy_path=POLICY),'fail','A21')


@pytest.mark.cer_assertion('A20-MISSING-CANCELLATION-OWNER-REJECTED')
def test_a20_requires_cancellation_owner(tmp_path):
    root,package,value=dependency_package(tmp_path)
    control=deepcopy(CONTROL_FIXTURES['subprocess']);value['capabilities']['subprocess']=True;value['controls']['subprocess']=control;write_contract(package,value)
    check_real(validate_package(repository_root=root,package_root=package,policy_path=POLICY),'pass')
    control.pop('cancellation_owner');write_contract(package,value)
    check_real(validate_package(repository_root=root,package_root=package,policy_path=POLICY),'fail','A20','A20_CANCELLATION_OWNER_MISSING_ACCEPTED')


@pytest.mark.cer_assertion('REPAIR_O_1E5582474ED5')
def test_a19_missing_containment_rejected_without_outside_read(tmp_path,monkeypatch):
    root,package,value=dependency_package(tmp_path)
    control=deepcopy(CONTROL_FIXTURES['filesystem']);value['capabilities']['filesystem']=True;value['controls']['filesystem']=control;write_contract(package,value)
    check_real(validate_package(repository_root=root,package_root=package,policy_path=POLICY),'pass')
    outside=root/'outside-private.txt';outside.write_text('SYNTHETIC_OUTSIDE_SENTINEL');reads=[];original=Path.open
    control.pop('traversal');write_contract(package,value)
    def observed(self,*a,**k):
        if self.resolve()==outside.resolve():reads.append(self)
        return original(self,*a,**k)
    monkeypatch.setattr(Path,'open',observed)
    check_real(validate_package(repository_root=root,package_root=package,policy_path=POLICY),'fail','A19')
    assert reads==[]


@pytest.mark.cer_assertion('REPAIR_O_199DDCBD4191')
def test_a15_diagnostics_do_not_echo_synthetic_secret(tmp_path):
    root,package,value=dependency_package(tmp_path)
    control=deepcopy(CONTROL_FIXTURES['secrets']);control['literal']='SYNTHETIC_SECRET_NEVER_REAL';value['capabilities']['secrets']=True;value['controls']['secrets']=control;write_contract(package,value)
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    check_real(result,'fail','A15')
    assert 'SYNTHETIC_SECRET' not in json.dumps(result) and str(root) not in json.dumps(result)
    assert all(d['message']=='The declaration does not satisfy the local contract.' for d in result['diagnostics'])


@pytest.mark.cer_assertion('A-O4186-local-only-validation')
@pytest.mark.cer_assertion('ASSERT_PACKAGE_A_NO_URL_REQUEST')
@pytest.mark.cer_assertion('A-O4E-NO-YAML-OBJECT-CONSTRUCTOR')
def test_a13_local_only_safe_parse_and_no_url(tmp_path,monkeypatch):
    root,package,value=dependency_package(tmp_path);effects=[]
    def denied(*a,**k):effects.append('external-or-execution');raise AssertionError('No external dependency allowed')
    for module,name in ((subprocess,'run'),(subprocess,'Popen'),(socket,'socket'),(socket,'getaddrinfo'),(urllib.request,'urlopen'),(os,'system')):monkeypatch.setattr(module,name,denied)
    # A forbidden constructor string must remain inert data and be rejected.
    check_real(validate_package(repository_root=root,package_root=package,policy_path=POLICY),'pass')
    (package/'SKILL.md').write_text('---\nname: reference-skill\ndescription: !!python/object/apply:os.system [echo forbidden]\n---\n# Body\n')
    check_real(validate_package(repository_root=root,package_root=package,policy_path=POLICY),'fail','A03')
    assert effects==[]


@pytest.mark.cer_assertion('A-O-9DA22965FBFF-1')
def test_a16_complete_disclosure_matrix(tmp_path):
    outcomes=[]
    for disclosure in ('recovery','irreversibility','neither'):
        root,package,value=dependency_package(tmp_path/disclosure)
        control=deepcopy(CONTROL_FIXTURES['destructive']);control.pop('bypass');control.pop('recovery')
        if disclosure!='neither':control[disclosure]='The user owns recovery or accepts irreversibility.'
        value['capabilities']['destructive']=True;value['controls']['destructive']=control;write_contract(package,value)
        result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
        outcomes.append(result['status']==('fail' if disclosure=='neither' else 'pass') and result['authorizes']==[])
    if not all(outcomes):print('FAILURE_ID:FAIL_O9DA22965FBFF_DISCLOSURE')
    assert all(outcomes)


@pytest.mark.parametrize('obligation,capability,fields',[
    pytest.param('O-266C5B9FFBAF','subprocess',['output_limit'],id='O-266C5B9FFBAF',marks=[pytest.mark.cer_assertion('A20_OUTPUT_BOUND_MUTATION_REJECTED')]),
    pytest.param('O-6324AB9F297C','destructive',['scope'],id='O-6324AB9F297C',marks=[pytest.mark.cer_assertion('A16-AFFECTED-SCOPE-DECLARATION-OBSERVED')]),
    pytest.param('O-43D6F582F1DB','subprocess',['argv'],id='O-43D6F582F1DB',marks=[pytest.mark.cer_assertion('A20_SUBPROCESS_ARGV_DECLARED')]),
    pytest.param('O-E3D98550014B','secrets',['denied_outputs'],id='O-E3D98550014B',marks=[pytest.mark.cer_assertion('A15-DENIED-OUTPUT-LOCATIONS-DECLARED'),pytest.mark.cer_assertion('A15-DENIED-OUTPUT-LOCATIONS-OMISSION-REJECTED')]),
    pytest.param('O-AB33912562D0','filesystem',['owner', 'roots'],id='O-AB33912562D0',marks=[pytest.mark.cer_assertion('A19-containment-metadata-owner')]),
    pytest.param('O-9033A08397FD','subprocess',['cwd'],id='O-9033A08397FD',marks=[pytest.mark.cer_assertion('A20_SUBPROCESS_WORKING_DIRECTORY_EXPLICIT'),pytest.mark.cer_assertion('A20_SUBPROCESS_WORKING_DIRECTORY_OMISSION_DETECTED')]),
    pytest.param('O-E36EEAA44ACD','untrusted_content',['prohibit_expansion'],id='O-E36EEAA44ACD',marks=[pytest.mark.cer_assertion('A18_DECLARATION_CHECK_GRANTS_NO_AUTHORITY'),pytest.mark.cer_assertion('A18_UNTRUSTED_AUTHORITY_EXPANSION_PROHIBITED'),pytest.mark.cer_assertion('A18_UNTRUSTED_COMMAND_EXPANSION_PROHIBITED'),pytest.mark.cer_assertion('A18_UNTRUSTED_TARGET_EXPANSION_PROHIBITED'),pytest.mark.cer_assertion('A18_UNTRUSTED_TOOL_PERMISSION_EXPANSION_PROHIBITED')]),
    pytest.param('O-016095AFE52A','database_write',['system'],id='O-016095AFE52A',marks=[pytest.mark.cer_assertion('A17_DATABASE_NO_SYSTEM_DECLARATION_REJECTED'),pytest.mark.cer_assertion('A17_DATABASE_SYSTEM_REQUIREMENT_EXPLICIT')]),
    pytest.param('O-B06EDCDBB058','database_write',['record_authority'],id='O-B06EDCDBB058',marks=[pytest.mark.cer_assertion('A17_B06_MISSING_REFERENCE_DIAGNOSTIC_IS_CAPABILITY_LOCAL'),pytest.mark.cer_assertion('A17_B06_STATIC_REJECTION_CONFERS_NO_AUTHORITY'),pytest.mark.cer_assertion('A17_B06_UNREFERENCED_FLAG_FAILS_OWNER_VALIDATION')]),
    pytest.param('O-6F40EB7D4B77','untrusted_content',['role'],id='O-6F40EB7D4B77',marks=[pytest.mark.cer_assertion('A18-DATA-ROLE-DECLARATION-CHECK'),pytest.mark.cer_assertion('A18-DATA-ROLE-STANDARD-REQUIREMENT')]),
    pytest.param('O-321D04164CD4','database_write',['record_authority'],id='O-321D04164CD4',marks=[pytest.mark.cer_assertion('A17_BACKUP_RESTORE_RECORD_LOCATION_DECLARED'),pytest.mark.cer_assertion('A17_RECORD_AUTHORITY_REFERENCE_REQUIRED')]),
    pytest.param('O-D0505EF6EC92','destructive',['authorization_source'],id='O-D0505EF6EC92',marks=[pytest.mark.cer_assertion('A16-CONFIRMATION-AUTHORIZATION-SOURCE-DECLARED')]),
    pytest.param('O-69E07DB584F7','database_write',['transaction', 'failure'],id='O-69E07DB584F7',marks=[pytest.mark.cer_assertion('A17_DB_WRITE_FAILURE_HANDLING_REQUIRED'),pytest.mark.cer_assertion('A17_DB_WRITE_HANDLING_COMPLETE_DECLARATION_ACCEPTED'),pytest.mark.cer_assertion('A17_DB_WRITE_TRANSACTION_HANDLING_REQUIRED')]),
    pytest.param('O-657E4509038D','secrets',['owner'],id='O-657E4509038D',marks=[pytest.mark.cer_assertion('SM-A15-CREDENTIAL-OWNER-LOCATION'),pytest.mark.cer_assertion('SM-A15-CREDENTIAL-OWNER-PRESENT')]),
    pytest.param('O-A19BF1AD20E4','subprocess',['timeout'],id='O-A19BF1AD20E4',marks=[pytest.mark.cer_assertion('A20-SUBPROCESS-TIMEOUT-FINITE'),pytest.mark.cer_assertion('A20-SUBPROCESS-TIMEOUT-MISSING-REJECTED'),pytest.mark.cer_assertion('A20-SUBPROCESS-TIMEOUT-NONFINITE-REJECTED')]),
    pytest.param('O-C93427474BF2','subprocess',['argv', 'shell'],id='O-C93427474BF2',marks=[pytest.mark.cer_assertion('A20-ARGV-ARRAY-DECLARATION'),pytest.mark.cer_assertion('A20-SHELL-DECLARATION-REJECTION'),pytest.mark.cer_assertion('A20-SHELL-EXPLICIT-FALSE')]),
])
def test_capability_complete_declaration_and_independent_omissions(tmp_path,obligation,capability,fields):
    root,package,value=dependency_package(tmp_path)
    (package/'references/backup.md').write_text('# Results\n\nThe owning workflow records backup and restoration results.\n')
    control=deepcopy(CONTROL_FIXTURES[capability]);value['capabilities'][capability]=True;value['controls'][capability]=control
    write_contract(package,value)
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert result['status']=='pass' and result['authorizes']==[],result
    baseline=deepcopy(control)
    variants=[(field,None) for field in fields]
    if capability=='subprocess' and 'timeout' in fields:variants += [('timeout',-1),('timeout','unbounded')]
    if capability=='subprocess' and 'argv' in fields:variants += [('argv','python unsafe.py')]
    if capability=='subprocess' and 'shell' in fields:variants += [('shell',True)]
    for field,invalid in variants:
        control.clear();control.update(deepcopy(baseline))
        if invalid is None:control.pop(field)
        else:control[field]=invalid
        write_contract(package,value)
        result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
        assert result['status']=='fail' and result['authorizes']==[],(obligation,field,result)
        located=any(d['path'].startswith('skill-quality.v1.json#/controls/'+capability) for d in result['diagnostics'])
        if not located:
            failure={'O-A19BF1AD20E4':'A20_SUBPROCESS_TIMEOUT_DECLARATION_DEFECT','O-C93427474BF2':'A20_SHELL_ARGV_DECLARATION_GAP'}.get(obligation)
            if failure:print('FAILURE_ID:'+failure)
        assert located,result
    control.clear();control.update(baseline);write_contract(package,value)
    assert validate_package(repository_root=root,package_root=package,policy_path=POLICY)['status']=='pass'


@pytest.mark.cer_assertion('A-A21-DNS-BOUNDARY-INSTRUMENTATION')
@pytest.mark.cer_assertion('A-A21-DNS-RESOLVER-CALLS-ZERO')
def test_a21_dns_boundaries_are_observed_before_resolution(tmp_path,monkeypatch):
    root,package,value=dependency_package(tmp_path);attempts=[]
    def forbidden(*a,**k):attempts.append('resolution');raise OSError('Resolution forbidden')
    for module,name in ((socket,'getaddrinfo'),(socket,'gethostbyname'),(socket,'gethostbyname_ex'),(urllib.request,'urlopen')):monkeypatch.setattr(module,name,forbidden)
    value['capabilities']['network']=True;value['controls']['network']=deepcopy(CONTROL_FIXTURES['network']);write_contract(package,value)
    assert validate_package(repository_root=root,package_root=package,policy_path=POLICY)['status']=='pass'
    value['controls']['network']['targets']=['*'];write_contract(package,value)
    assert validate_package(repository_root=root,package_root=package,policy_path=POLICY)['status']=='fail'
    assert attempts==[]


@pytest.mark.cer_assertion('SCHEMA_IMPLEMENTATION_AVAILABLE')
@pytest.mark.cer_assertion('UNSUPPORTED_SCHEMA_CONSTRUCT_REJECTED')
def test_a02_supported_local_schema_and_explicit_unsupported_rejection(tmp_path):
    root,package,_=dependency_package(tmp_path)
    assert validate_package(repository_root=root,package_root=package,policy_path=POLICY)['status']=='pass'
    schema_path=root/'scripts/sc/schemas/skill-quality-contract.v1.schema.json';schema=json.loads(schema_path.read_text());schema['unevaluatedProperties']=False;schema_path.write_text(json.dumps(schema))
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert result['status']=='error' and result['exit_code']==2 and result['authorizes']==[]


@pytest.mark.cer_assertion('VERSION_DATE_NO_LIVE_FRESHNESS_EFFECTS')
@pytest.mark.cer_assertion('VERSION_DATE_STATIC_RECORD_SCOPE')
@pytest.mark.cer_assertion('A14-historical-records-provenance-only')
@pytest.mark.cer_assertion('A14_SOURCE_RECORD_PRESENT')
def test_a14_provenance_records_do_not_claim_current_latest_version(tmp_path,monkeypatch):
    from scripts.sc.tests.skill_quality_support import LOOKUP_FIXTURE
    root,package,value=dependency_package(tmp_path);value['capabilities']['version_lookup']=True;value['lookup']=deepcopy(LOOKUP_FIXTURE);value['lookup']['retrieval_date']='2001-01-01';write_contract(package,value)
    attempts=[]
    def forbidden(*a,**k):attempts.append(True);raise OSError('No lookup allowed')
    monkeypatch.setattr(urllib.request,'urlopen',forbidden);monkeypatch.setattr(socket,'getaddrinfo',forbidden)
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert result['status']=='pass' and result['authorizes']==[]
    assert validate_package(repository_root=root,package_root=package,policy_path=POLICY)==result
    value['lookup']['retrieval_date']='not-a-date';write_contract(package,value)
    assert validate_package(repository_root=root,package_root=package,policy_path=POLICY)['status']=='fail'
    assert attempts==[]


@pytest.mark.cer_assertion('ASSERT-E6D48F5ADC23-NO-BACKUP-PREREQUISITE')
@pytest.mark.cer_assertion('ASSERT-E6D48F5ADC23-NO-DATABASE-PREREQUISITE')
@pytest.mark.cer_assertion('A08-LEAF-DIAGRAM-EXEMPTION')
def test_a13_leaf_without_optional_infrastructure(tmp_path):
    root,package,value=dependency_package(tmp_path)
    assert not any(value['capabilities'].values()) and value['routing']=={'kind':'leaf'} and value['controls']=={}
    result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
    assert result['status']=='pass' and result['diagnostics']==[] and result['authorizes']==[]


@pytest.mark.cer_assertion('A19-VALIDATOR-ESCAPE-REJECTED-BEFORE-READ')
@pytest.mark.cer_assertion('A19-VALIDATOR-INSPECTION-ROOT-ENFORCED')
def test_a19_caller_and_reference_escape_rejected_before_read(tmp_path,monkeypatch):
    root,package,value=dependency_package(tmp_path);outside=tmp_path/'external.md';outside.write_text('FORBIDDEN_OUTSIDE_SENTINEL');before=outside.read_bytes();reads=[];original=Path.open
    def observed(self,*a,**k):
        if self.resolve()==outside.resolve():reads.append(True)
        return original(self,*a,**k)
    with monkeypatch.context() as patch:
        patch.setattr(Path,'open',observed)
        result=validate_package(repository_root=root,package_root=outside,policy_path=POLICY)
        assert result['status']=='error' and result['exit_code']==2
        value['responsibility']={'ref':'../../../external.md'};write_contract(package,value)
        result=validate_package(repository_root=root,package_root=package,policy_path=POLICY)
        assert result['status']=='fail' and result['authorizes']==[]
    assert reads==[] and outside.read_bytes()==before
    assert 'FORBIDDEN_OUTSIDE_SENTINEL' not in json.dumps(result) and str(tmp_path) not in json.dumps(result)
