"""ADR-0041: disposable Package A fixtures with independent expected values."""
from copy import deepcopy
import json
import inspect
from pathlib import Path
import shutil

REPOSITORY = Path(__file__).resolve().parents[3]
POLICY = 'scripts/sc/config/skill-authoring-standard.v1.json'
SCHEMAS = (
    'scripts/sc/schemas/skill-quality-contract.v1.schema.json',
    'scripts/sc/schemas/skill-quality-result.v1.schema.json',
)


def dependency_package(tmp_path):
    """Copy actual candidate inputs; never synthesize a passing policy/schema."""
    root = tmp_path / 'inspection'
    package = root / 'packages' / 'reference-skill'
    package.mkdir(parents=True)
    for relative in (POLICY, *SCHEMAS, 'docs/standards/skill-authoring-standard.md'):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / relative, target)
    (package / 'SKILL.md').write_text(
        '---\nname: reference-skill\ndescription: Inspect a local example.\n---\n'
        '# Reference Skill\n\nInspect contained input and return a local report.\n',
        encoding='utf-8')
    contract = {
        'schema': 'skill-quality.v1', 'standard_version': '1.0', 'name': 'reference-skill', 'authorizes': [],
        'responsibility': 'Inspect a contained local example and return its report.',
        'triggers': ['A caller requests a local example inspection.'],
        'non_goals': ['Executing dependencies or granting permissions.'],
        'inputs': ['A contained example path.'], 'outputs': ['A structured report.'],
        'references': [], 'tests': ['Local package declaration checks.'],
        'evidence': 'The caller owns real execution evidence.',
        'lifecycle': {'owner': 'repository-maintainer', 'completion_owner': 'caller'},
        'capabilities': {key: False for key in ('routing','version_lookup','secrets','destructive','database_write','untrusted_content','filesystem','subprocess','network')},
        'lookup': {'kind': 'not-applicable'}, 'controls': {},
        'routing': {'kind': 'leaf'},
        'outcomes': ['typical','boundary','error'], 'error_ids': ['INPUT_INVALID'],
        'examples': [
            {'outcome': 'typical', 'branch': 'typical', 'input': 'Inspect local sample', 'output': 'Sample report', 'expected_result': 'pass'},
            {'outcome': 'boundary', 'branch': 'boundary', 'input': 'Inspect empty sample', 'output': 'Empty report', 'expected_result': 'pass'},
            {'outcome': 'error', 'branch': 'error', 'input': 'Inspect malformed sample', 'output': 'INPUT_INVALID', 'expected_result': 'fail'},
        ],
        'entrypoints': [{'id': 'inspect', 'dependencies': ['local-parser'],
                         'preflight': 'Check the declared local parser record.', 'inputs': ['A local sample'], 'outputs': ['A structured report'], 'standalone': True, 'caller_setup': 'none'}],
        'dependencies': [{'id': 'local-parser', 'required': True, 'version': '1.2.3',
                          'authority': 'references/parser.json',
                          'when_missing': 'block', 'when_mismatch': 'block'}],
    }
    authority = package / 'references' / 'parser.json'
    authority.parent.mkdir()
    authority.write_text(json.dumps({'id': 'local-parser', 'version': '1.2.3'}), encoding='utf-8')
    write_contract(package, contract)
    return root, package, deepcopy(contract)


def write_contract(package, value):
    (package / 'skill-quality.v1.json').write_text(json.dumps(value, sort_keys=True), encoding='utf-8')


def invocation_args(function, root, package, mode='strict'):
    """Transport compatibility only; tests retain independent outcome oracles."""
    if 'repository_root' in inspect.signature(function).parameters:
        return (), dict(repository_root=root, package_root=package, policy_path=POLICY, mode=mode)
    return (root, package), dict(mode=mode)

# ADR-0041: fixed synthetic declarations; these values are test oracles, not
# discovered from production policy or capability code.
CONTROL_FIXTURES = {
 'secrets': {'owner':'Phase credential provider','reference':'credential-id','redaction':'remove values', 'denied_outputs':['stdout','logs','model'], 'output_policy':'redacted'},
 'destructive': {'owner':'Phase project service','scope':['workspace'], 'authorization_source':'existing-session','recovery':'User snapshot restore','bypass':False},
 'database_write': {'owner':'Phase data owner','system':'SQLite','backup':'Owning workflow backup','recovery':'Owning workflow restore','transaction':'atomic','failure':'rollback','record_authority':'references/backup.md#results'},
 'untrusted_content': {'owner':'Phase controller','role':'data-only','prohibit_expansion':['targets','commands','tools','authority']},
 'filesystem': {'owner':'Runner workspace owner','roots':['.'],'read':['.'],'write':['src'],'delete':['src'],'traversal':'reject','symlinks':'reject'},
 'subprocess': {'owner':'Runner','argv':['python','scripts/check.py'],'shell':False,'cwd':'.','timeout':30,'output_limit':4096,'cancellation_owner':'Runner process tree'},
 'network': {'owner':'Phase egress owner','schemes':['https'],'targets':['https://docs.python.org'],'redirect_owner':'Phase egress','dns_owner':'Phase resolver','private_addresses':'block','loopback':'block','metadata':'block','internal_exceptions':[],'timeout':30},
}
LOOKUP_FIXTURE={'kind':'version-sensitive','preferred':'context7-first','fallback':'https://docs.python.org', 'version':'3.12', 'source':'https://docs.python.org/3.12/', 'retrieval_date':'2026-10-01', 'missing_policy':'block','stale_policy':'recheck-before-use'}


def prepare_scenario(tmp_path, scenario, assertion):
    """Independent fixture mutation and outcome specification for one assertion."""
    import inspect
    from hashlib import sha256
    from scripts.sc.validate_skill_quality import validate_package
    root,package,value=dependency_package(tmp_path)
    mode='strict';expected=('pass',0);rule=None;extra=lambda result: True
    bits=scenario.split(':');kind=bits[0];detail=bits[1] if len(bits)>1 else ''
    (package/'references/backup.md').write_text('# Results\n\nThe owning workflow records real backup/restore results here.\n')
    (package/'scripts').mkdir();(package/'scripts/check.py').write_text('raise RuntimeError("MUST_NOT_EXECUTE_DECLARED_COMMAND")\n')
    (package/'tests').mkdir();(package/'tests/test_check.py').write_text('def test_declaration():\n    assert True\n')
    def reject(target_rule):
        nonlocal expected,rule
        expected=('fail',1);rule=target_rule
    if kind=='required':
        value.pop(detail);reject('A01')
    elif kind=='positive':pass
    elif kind=='capability-type':value['capabilities']['network']='false';reject('A02')
    elif kind=='cap':
        capability=detail
        if capability=='composition':
            for cap in ('secrets','filesystem'):value['capabilities'][cap]=True;value['controls'][cap]=deepcopy(CONTROL_FIXTURES[cap])
            del value['controls']['filesystem'];reject('A19')
        else:
            value['capabilities'][capability]=True;control=deepcopy(CONTROL_FIXTURES[capability]);value['controls'][capability]=control
            field=bits[2];raw=':'.join(bits[3:]);control[field]=True if raw=='true' else [raw] if field in {'scope','targets','schemes'} else raw
            if not raw:control.pop(field,None)
            reject({'secrets':'A15','destructive':'A16','database_write':'A17','untrusted_content':'A18','filesystem':'A19','subprocess':'A20','network':'A21'}[capability])
            if capability=='secrets' and raw.startswith('SYNTHETIC_'):
                extra=lambda result: raw not in json.dumps(result) and str(root) not in json.dumps(result)
    elif kind=='lookup':
        if detail in {'false-local','applicability'}:
            if detail=='false-local':value['dependencies'][0]['kind']='api'
            else:value['lookup']={}
            reject('A13')
        else:
            value['capabilities']['version_lookup']=True;value['lookup']=deepcopy(LOOKUP_FIXTURE)
            if detail in {'official','policy-origin'}:
                pass
            if detail in {'official','policy-origin'}:
                if detail=='policy-origin':value['lookup']['fallback']='https://not-official.invalid';value['lookup']['official']=True;reject('A14')
            elif detail=='failure-policy':value['lookup'].pop('missing_policy');value['lookup'].pop('stale_policy');reject('A14')
            else:
                raw=':'.join(bits[2:]);value['lookup'][detail]=raw
                if not raw:value['lookup'].pop(detail,None)
                reject('A14')
    elif kind=='frontmatter':
        skill=package/'SKILL.md';text=skill.read_text()
        if detail in {'constructor'}:text='---\nname: !!python/object/apply:os.system ["MUST_NOT_EXECUTE"]\ndescription: unsafe constructor\n---\n'
        elif detail=='conflict' or detail=='identity':text=text.replace('name: reference-skill','name: other-skill')
        elif detail=='canonical':value['name']='Not_Canonical'
        elif detail=='empty':
            field='description' if 'DESCRIPTION' in assertion else 'name';text=text.replace('description: Inspect a local example.','description: ""') if field=='description' else text.replace('name: reference-skill','name: ""')
        elif detail=='variants':
            if 'MISSING-' in assertion:text='# Missing frontmatter\n'
            elif 'DUPLICATE' in assertion:text=text.replace('name: reference-skill','name: reference-skill\nname: reference-skill')
            elif 'CONFLICTING' in assertion:text=text.replace('name: reference-skill','name: other-skill')
            elif 'MALFORMED' in assertion:text=text.replace('description: Inspect a local example.','description: [unterminated')
            else:text=text.replace('---\n#','unsupported: yes\n---\n#')
        else:text=text.replace('---\n#','unsupported: yes\n---\n#')
        skill.write_text(text);reject('A03')
    elif kind=='lines':
        count=499 if '499' in assertion or detail in {'final','invariance'} else 501 if '501' in assertion else 500
        lines=['---','name: reference-skill','description: A counted example.','---','# Heading','```text','code','```']
        lines += ['']*(count-len(lines));text='\n'.join(lines)+'\n';(package/'SKILL.md').write_bytes(text.encode())
        if count>=500:reject('A04')
        extra=lambda result: len((package/'SKILL.md').read_text().splitlines())==count
    elif kind=='reference':
        (package/'references/content.md').write_text('# Responsibility\n\nInspect a contained local sample and return its report.\n')
        value['responsibility']={'ref':'references/content.md#responsibility'}
        if detail=='remote-required':value['responsibility']={'ref':'https://example.invalid/required'};reject('A05')
    elif kind=='routing':
        value['capabilities']['routing']=True;value['routing']={'kind':'leaf'}
        # A08 is implemented with its own declaration group after foundation.
        if detail=='unresolved':value['routing']={'kind':'conditional','entry':'start','branches':['typical','boundary','error'],'diagram':{'ref':'references/routing.md#flow'}};(package/'references/routing.md').write_text('# Flow\n[start] -> [unresolved]\n')
        reject('A08')
    elif kind=='invocation':
        value['invocation']={'script':'scripts/check.py','tests':'tests/test_check.py','argv':['python','scripts/check.py'],'shell':False,'cwd':'.','timeout':30,'result_type':'check-result.v1'}
        field=detail;raw=bits[2]
        if raw=='missing':value['invocation'][field]='absent.py'
        elif field=='timeout':value['invocation'][field]=0
        elif field=='shell':value['invocation'][field]=True
        reject('A11')
    elif kind=='fs':
        value['capabilities']['filesystem']=True;value['controls']['filesystem']=deepcopy(CONTROL_FIXTURES['filesystem'])
        if detail=='write':value['controls']['filesystem']['write']=['../escape'];reject('A19')
        else:
            sentinel=root/'outside.md';sentinel.write_text('SYNTHETIC_FORBIDDEN_CONTENT')
            (package/'references/escape.md').symlink_to(sentinel)
            value['responsibility']={'ref':'references/escape.md'};reject('A05')
    elif kind=='schema':
        if detail=='typo':value['capabilities']['netwrok']=False;reject('A02')
        elif detail=='capabilities':value.pop('capabilities');reject('A02')
        elif detail in {'invalid-inventory','invalid-inputs'}:value['schema']='skill-quality.v999';mode='inventory' if detail=='invalid-inventory' else 'strict';reject('A02')
        elif detail=='remote-ref':
            p=root/SCHEMAS[0];schema=json.loads(p.read_text());schema['$ref']='https://example.invalid/schema';p.write_text(json.dumps(schema));expected=('error',2)
        else:
            p=root/SCHEMAS[0];schema=json.loads(p.read_text());schema['required']=['never_declared'];p.write_text(json.dumps(schema));reject('A02')
    elif kind=='paths':
        if detail=='roots':package=tmp_path/'outside-package';package.mkdir();(package/'SKILL.md').write_text('---\nname: outside-package\ndescription: Outside.\n---\n');expected=('error',2)
        else:package=package.relative_to(root)
    elif kind=='modes':
        if detail=='inventory':(package/'skill-quality.v1.json').unlink();mode='inventory';expected=('legacy',3)
        elif detail=='strict-nonsuccess':mode='unknown';expected=('error',2)
        elif detail=='known':mode='unknown';expected=('error',2)
        # parity is checked separately by the CLI/API suite.
    elif kind=='api':
        expected=None
        extra=lambda result: all(p.kind==inspect.Parameter.KEYWORD_ONLY for p in inspect.signature(validate_package).parameters.values()) and inspect.signature(validate_package).parameters['mode'].default=='strict'
    elif kind=='diagnostics':
        value['name']='SYNTHETIC_SECRET_TEST_ONLY';expected=('fail',1)
        extra=lambda result: 'SYNTHETIC_SECRET_TEST_ONLY' not in json.dumps(result) and str(root) not in json.dumps(result) and 'timestamp' not in result
    elif kind=='static':
        if detail=='remote':value['references']=[{'uri':'https://example.invalid/docs','required':False}]
        else:value['capabilities']['version_lookup']=True;value['lookup']=deepcopy(LOOKUP_FIXTURE)
    elif kind=='migration':
        value['lifecycle']={'owner':'original-owner','completion_owner':'external-acceptance'}
        (package/'scripts/skill-contract.json').write_text('{"authorizes":[],"owner":"original-owner"}')
        (package/'references/skill-input-contract.v1.json').write_text('{"owner":"original-input-owner"}')
        original=json.loads(json.dumps(value['lifecycle']))
        def unchanged(before,after):
            return before['lifecycle']==after['lifecycle'] and before['authorizes']==after['authorizes']
        before=deepcopy(value);changed=deepcopy(value);changed['lifecycle']['owner']='drifted-owner'
        changed_authority=deepcopy(value);changed_authority['authorizes']=['unexpected-authority']
        extra=lambda result: unchanged(before,json.loads((package/'skill-quality.v1.json').read_text())) and not unchanged(before,changed) and not unchanged(before,changed_authority) and result['authorizes']==[]
    elif kind=='artifact':
        policy=json.loads((root/POLICY).read_text());standard=(root/'docs/standards/skill-authoring-standard.md').read_text()
        if detail=='policy-fields':extra=lambda r: {'contract_schema','result_schema','frontmatter_keys','rules','limits','dependencies','official_origins'}<=policy.keys() and policy['frontmatter_keys']==['name','description'] and policy['rules']==['A%02d'%n for n in range(1,26)] and policy['limits']['skill_logical_lines_exclusive']==500
        elif detail=='policy':extra=lambda r: policy.get('schema')=='skill-authoring-standard.v1' and policy.get('standard_version')=='1.0'
        elif detail in {'contract-schema','result-schema'}:
            schema=json.loads((root/SCHEMAS[0 if detail=='contract-schema' else 1]).read_text());extra=lambda r: schema.get('type')=='object' and bool(schema.get('required')) and schema.get('standard_version')=='1.0'
        elif detail=='standard-root':extra=lambda r: policy.get('standard')=='docs/standards/skill-authoring-standard.md' and 'Standard version: 1.0' in standard
        elif detail=='entrypoints':extra=lambda r: callable(validate_package) and callable(__import__('scripts.sc.validate_skill_quality',fromlist=['main']).main)
        elif detail=='argv':extra=lambda r: 'shell=false' in standard and '300 seconds' in standard
        elif detail=='static-claims':extra=lambda r: 'Static checks prove' in standard or 'performs read-only static' in standard
        else:extra=lambda r: 'no real credential fixture' in standard
        # The artifact is the oracle, not an assertion that other product rules pass.
        expected=None
    write_target=package if package.is_absolute() else root/package
    if write_target.is_relative_to(root) and scenario!='modes:inventory':write_contract(write_target,value)
    original_files={p.relative_to(root).as_posix():sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
    def oracle(result):
        if not isinstance(result,dict) or result.get('authorizes')!=[]:return False
        if expected and (result.get('status'),result.get('exit_code'))!=expected:return False
        if rule and not any(d.get('rule')==rule for d in result.get('diagnostics',[])):return False
        if not extra(result):return False
        current={p.relative_to(root).as_posix():sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
        return current==original_files
    return root,package,mode,oracle


def prepare_example_scenario(tmp_path, scenario):
    import hashlib
    root,package,value=dependency_package(tmp_path)
    mode='strict';status='pass';rule=None
    bits=scenario.split(':');kind=bits[0];detail=bits[1] if len(bits)>1 else ''
    (package/'references/help.md').write_text('# Help\n\nThe input must be a contained local sample.\n\n# Fallback\n\nReturn a report without protected work.\n')
    (package/'scripts').mkdir(exist_ok=True);(package/'scripts/check.py').write_text('raise RuntimeError("DO_NOT_EXECUTE")\n')
    (package/'tests').mkdir(exist_ok=True);(package/'tests/test_check.py').write_text('def test_check(): assert True\n')
    def reject(number):
        nonlocal status,rule
        status='fail';rule=number
    if kind=='examples':
        if detail=='positive' or detail=='supplemental':
            value['references']=[{'ref':'references/help.md#help'}]
        else:
            if detail=='count':value['examples'].pop()
            elif detail=='order':value['examples'].reverse()
            elif detail in {'typical','boundary','error'}:value['examples']=[e for e in value['examples'] if e['outcome']!=detail]
            elif detail in {'input','output','expected_result'}:value['examples'][0][detail]=''
            elif detail=='duplicate-branch':value['examples'][1]['branch']=value['examples'][0]['branch']
            elif detail=='unknown-branch':value['examples'][0]['branch']='unknown'
            elif detail=='duplicate-pair':value['examples'][1]['input']=value['examples'][0]['input'];value['examples'][1]['output']=value['examples'][0]['output']
            else:raise ValueError('Unknown fixed example scenario')
            reject('A07')
    elif kind=='routing':
        if detail=='leaf':pass
        else:
            value['capabilities']['routing']=True
            value['routing']={'kind':'conditional','entry':'start','branches':['typical','boundary','error'], 'diagram':{'ref':'references/diagram.md#flow'}}
            content='# Flow\n[start] -> [typical]\n[start] -> [boundary]\n[start] -> [error]\n'
            if detail=='missing':value['routing'].pop('diagram');reject('A08')
            elif detail=='non-ascii':content+='# \u4e2d\u6587\n';reject('A08')
            elif detail=='unreachable':content='# Flow\n[start] -> [typical]\n';reject('A08')
            elif detail=='false-leaf':value['routing']['kind']='leaf';reject('A08')
            elif detail=='unknown':content+='%s\n' % '[start] -> [unknown]';reject('A08')
            (package/'references/diagram.md').write_text(content,encoding='utf-8')
    elif kind=='dependency':
        dependency=value['dependencies'][0]
        if detail=='missing-record':value['dependencies']=[];reject('A09')
        elif detail=='unresolved':dependency['authority']='references/missing.json';reject('A09')
        elif detail=='version':dependency['version']='9.9.9';reject('A09')
        elif detail in {'id','required','version-field','when_missing','when_mismatch'}:
            dependency.pop('version' if detail=='version-field' else detail);reject('A09')
        elif detail.startswith('optional'):
            dependency.update(required=False,authority='references/not-installed.json',when_missing='fallback',fallback={'ref':'references/help.md#fallback','authorizes':[]})
            if detail=='optional-no-fallback':dependency['authority']='references/parser.json';dependency.pop('fallback');reject('A09')
            elif detail=='optional-dead':dependency['fallback']['ref']='references/dead.md#fallback';reject('A09')
            elif detail=='optional-authority':dependency['authority']='references/parser.json';dependency['fallback']['authorizes']=['protected-write'];reject('A09')
        elif detail not in {'positive','no-execution'}:raise ValueError('Unknown dependency scenario')
    elif kind=='entry':
        entry=value['entrypoints'][0]
        if detail=='install':entry['install_missing']=True
        elif detail=='skip':entry['skip_missing']=True
        elif detail=='setup':entry['caller_setup']='implicit'
        elif detail=='positive':pass
        else:entry.pop(detail)
        if detail!='positive':reject('A10')
    elif kind=='invocation':
        value['invocation']={'script':'scripts/check.py','tests':'tests/test_check.py','argv':['python','scripts/check.py'],'cwd':'.','shell':False,'timeout':30,'result_type':'check-result.v1'}
        if detail=='argv':value['invocation']['argv']='python check.py';reject('A11')
        elif detail=='result':value['invocation'].pop('result_type');reject('A11')
        elif detail=='timeout':value['invocation']['timeout']=0;reject('A11')
        elif detail=='cwd':value['invocation']['cwd']='../outside';reject('A11')
        elif detail=='shell':value['invocation']['shell']=True;reject('A11')
        elif detail=='string':value['invocation']='python scripts/check.py';reject('A11')
        elif detail=='missing-cwd':value['invocation'].pop('cwd');reject('A11')
    elif kind=='faq':
        if detail!='none':
            value['faq']=[{'from':'INPUT_INVALID','target':{'ref':'references/help.md#help'}}]
            if detail=='orphan':value['faq'][0].pop('from');reject('A12')
            elif detail=='unknown':value['faq'][0]['from']='UNKNOWN_ERROR';reject('A12')
            elif detail=='dead':value['faq'][0]['target']={'ref':'references/not-here.md#help'};reject('A12')
    else:raise ValueError('Unknown declaration scenario')
    write_contract(package,value)
    before={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    def oracle(result):
        if not isinstance(result,dict) or result.get('status')!=status or result.get('exit_code')!=(0 if status=='pass' else 1) or result.get('authorizes')!=[]:return False
        if rule and not any(d.get('rule')==rule for d in result.get('diagnostics',[])):return False
        after={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        return before==after
    return root,package,mode,oracle
