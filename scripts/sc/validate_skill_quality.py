"""ADR-0041: deterministic, read-only Package A declaration inspection.

This local static validator never executes inspected content or grants authority.
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
    value = json.loads(_bounded_text(path), object_pairs_hook=_unique_object, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite JSON')))
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object')
    stack=[(value,0)];nodes=0
    while stack:
        child,depth=stack.pop();nodes+=1
        if depth>40 or nodes>20000:raise ValueError('JSON structure budget exceeded')
        if isinstance(child,dict):stack.extend((v,depth+1) for v in child.values())
        elif isinstance(child,list):stack.extend((v,depth+1) for v in child)
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
        if current.is_symlink() or getattr(current,'is_junction',lambda:False)():
            raise ValueError('Symbolic authority path')
    target = current.resolve(strict=True)
    target.relative_to(package)
    if not target.is_file():
        raise ValueError('Unavailable local authority')
    return target


def _dependency_diagnostics(package, contract, repository_root=None, policy_records=()):
    """Resolve only supplied local records; optional fallback remains data."""
    diagnostics=[]
    def emit(code,pointer,identity=None):
        diagnostic=_diagnostic('A09',code,'skill-quality.v1.json#'+pointer)
        if isinstance(identity,str) and re.fullmatch(r'[a-z][a-z0-9-]{0,63}',identity):diagnostic['dependency_id']=identity
        diagnostics.append(diagnostic)
    records=contract.get('dependencies',[]);entries=contract.get('entrypoints',[])
    if not isinstance(records,list) or not isinstance(entries,list):emit('DEPENDENCY_INVALID_RECORD','/dependencies');return diagnostics
    by_id={};policy_versions={}
    combined=[(record,True,index) for index,record in enumerate(policy_records)]+[(record,False,index) for index,record in enumerate(records)]
    for record,policy_owned,index in combined:
        pointer='/dependencies/'+str(index)
        if not isinstance(record,dict):emit('DEPENDENCY_INVALID_RECORD',pointer);continue
        identity=record.get('id')
        if not isinstance(identity,str) or re.fullmatch(r'[a-z][a-z0-9-]{0,63}',identity) is None:
            emit('DEPENDENCY_INVALID_RECORD',pointer);continue
        if identity in by_id and not (identity in policy_versions and not policy_owned):
            emit('DEPENDENCY_INVALID_RECORD',pointer,identity);continue
        by_id[identity]=record
        if type(record.get('required')) is not bool or record.get('when_missing') not in {'block','fallback'} or record.get('when_mismatch')!='block':
            emit('DEPENDENCY_INVALID_RECORD',pointer,identity)
        if record.get('required') is True and record.get('when_missing')!='block':emit('DEPENDENCY_INVALID_RECORD',pointer+'/when_missing',identity)
        fallback_ok=False
        if record.get('required') is False:
            fallback=record.get('fallback')
            try:
                if (not isinstance(fallback,dict) or set(fallback)!={'ref','authorizes'} or fallback['authorizes']!=[] or record.get('when_missing')!='fallback'):
                    raise ValueError('Invalid fallback')
                _content_reference(package,fallback['ref']);fallback_ok=True
            except (OSError,ValueError,RuntimeError,UnicodeError):emit('DEPENDENCY_INVALID_FALLBACK',pointer+'/fallback',identity)
        try:
            authority_path=(_authority_file(repository_root,record.get('authority')) if policy_owned else _authority_file(package,record.get('authority')))
            authority=_read_object(authority_path)
            if authority.get('id')!=identity or not isinstance(authority.get('version'),str) or not authority['version']:
                raise ValueError('Unresolved authority')
        except FileNotFoundError:
            if not (record.get('required') is False and fallback_ok):emit('DEPENDENCY_UNRESOLVED_AUTHORITY',pointer+'/authority',identity)
            continue
        except (OSError,ValueError,TypeError,RuntimeError,UnicodeError):
            emit('DEPENDENCY_UNRESOLVED_AUTHORITY',pointer+'/authority',identity)
            continue
        requested=record.get('version',authority['version'])
        if not isinstance(requested,str) or requested!=authority['version'] or (identity in policy_versions and requested!=policy_versions[identity]):
            emit('DEPENDENCY_VERSION_CONFLICT',pointer+'/version',identity)
        if policy_owned:policy_versions[identity]=authority['version']
    for entry_index,entry in enumerate(entries):
        if not isinstance(entry,dict) or not isinstance(entry.get('dependencies'),list):
            emit('DEPENDENCY_INVALID_RECORD','/entrypoints/'+str(entry_index));continue
        for dep_index,identity in enumerate(entry.get('dependencies',[])):
            if not isinstance(identity,str) or identity not in by_id:
                emit('DEPENDENCY_MISSING_RECORD','/entrypoints/'+str(entry_index)+'/dependencies/'+str(dep_index),identity)
    return sorted(diagnostics,key=lambda row:(row['rule'],row['path'],row['code']))


def _faq_diagnostics(package,contract):
    diagnostics=[];entries=contract.get('faq',[])
    if not isinstance(entries,list):return [_diagnostic('A12','INVALID_FAQ','skill-quality.v1.json#/faq')]
    errors=contract.get('error_ids',[]);branches=contract.get('routing',{}).get('branches',[])
    known={x for x in [*(errors if isinstance(errors,list) else []),*(branches if isinstance(branches,list) else [])] if isinstance(x,str)}
    for index,entry in enumerate(entries):
        path='skill-quality.v1.json#/faq/'+str(index)
        if not isinstance(entry,dict) or set(entry)!={'from','target'} or not isinstance(entry.get('from'),str) or entry['from'] not in known:
            diagnostics.append(_diagnostic('A12','ORPHAN_FAQ_ENTRY',path));continue
        try:
            target=entry['target'];reference=target['ref'] if isinstance(target,dict) and set(target)=={'ref'} else target
            _content_reference(package,reference)
        except (OSError,ValueError,TypeError,KeyError,RuntimeError,UnicodeError):
            diagnostics.append(_diagnostic('A12','UNRESOLVED_FAQ_TARGET',path+'/target'))
    return diagnostics


def _diagnostic(rule, code, pointer):
    return {'rule': rule, 'code': code, 'path': pointer,
            'message': 'The declaration does not satisfy the local contract.'}


def _public_result(mode, status, code, diagnostics, package=None):
    return {'schema': 'skill-quality-result.v1', 'package': package,
            'mode': mode if isinstance(mode,str) and mode in {'strict', 'inventory'} else None,
            'status': status, 'exit_code': code,
            'diagnostics': sorted(diagnostics, key=lambda d: (d['rule'], d['path'], d['code']))[:100],
            'authorizes': []}


def _caller_path(root, supplied):
    raw = Path(supplied)
    if '..' in raw.parts:
        raise ValueError('Invalid caller path')
    path = raw if raw.is_absolute() else root / raw
    path.resolve().relative_to(root)
    current = path
    while current != root:
        if current.is_symlink() or getattr(current,'is_junction',lambda:False)():
            raise ValueError('Symbolic caller path')
        current = current.parent
    return path


def _content_reference(package, reference):
    if not isinstance(reference, str):
        raise ValueError('Invalid reference')
    filename, separator, anchor = reference.partition('#')
    path = _authority_file(package, filename)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('Oversized reference')
    content = path.read_text(encoding='utf-8')
    if separator:
        headings=list(re.finditer(r'^(#{1,6}) +(.+?) *#*$',content,re.MULTILINE))
        counts={};selected=None
        for index,heading in enumerate(headings):
            base=re.sub(r'[^\w -]','',heading[2].lower()).replace(' ','-')
            occurrence=counts.get(base,0);counts[base]=occurrence+1
            slug=base+('-'+str(occurrence) if occurrence else '')
            if anchor and slug==anchor:
                end=next((h.start() for h in headings[index+1:] if len(h[1])<=len(heading[1])),len(content))
                selected=content[heading.end():end];break
        if selected is None:raise ValueError('Unresolved anchor')
        content=selected
    if not content.strip():
        raise ValueError('Empty reference')
    return content


def _reference_diagnostics(package, contract):
    diagnostics=[]
    def inspect(value, pointer):
        if isinstance(value, dict):
            if 'ref' in value:
                try:
                    _content_reference(package, value['ref'])
                except (OSError, ValueError, RuntimeError, UnicodeError):
                    diagnostics.append(_diagnostic('A05', 'INVALID_LOCAL_REFERENCE',
                                                   'skill-quality.v1.json#'+pointer))
            else:
                for key, child in value.items():
                    inspect(child, pointer+'/'+(key if key in {'responsibility','triggers','non_goals','inputs','outputs','references','tests','evidence','lifecycle','controls','routing','diagram','faq','target'} else 'item'))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                inspect(child, pointer+'/'+str(index))
    inspect(contract, '')
    return diagnostics


def _declaration_diagnostics(package, contract, frontmatter):
    diagnostics=[]
    def bad(rule,code,field):diagnostics.append(_diagnostic(rule,code,'skill-quality.v1.json#/'+field))
    for field in ('responsibility','triggers','non_goals','inputs','outputs','dependencies','references','tests','evidence','lifecycle'):
        value=contract.get(field)
        if field in {'dependencies','references'}:
            if not isinstance(value,list):bad('A01','MISSING_DECLARATION',field)
            continue
        if field=='lifecycle':
            if not isinstance(value,dict) or not all(_substantive(value.get(k)) for k in ('owner','completion_owner')):bad('A01','MISSING_LIFECYCLE',field)
            continue
        values=value if isinstance(value,list) else [value]
        if not values:bad('A01','MISSING_DECLARATION',field)
        for child in values:
            try:content=_content_reference(package,child['ref']) if isinstance(child,dict) and set(child)=={'ref'} else child
            except (OSError,ValueError,RuntimeError,UnicodeError):content=None
            if not _substantive(content):bad('A01','MISSING_SUBSTANTIVE_CONTENT',field)
    name=contract.get('name')
    if (not isinstance(name,str) or re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*',package.name) is None
            or name!=package.name or frontmatter.get('name')!=package.name):bad('A03','IDENTITY_MISMATCH','name')
    for index,reference in enumerate(contract.get('references',[]) if isinstance(contract.get('references'),list) else []):
        try:
            if isinstance(reference,dict) and set(reference)=={'uri','required'} and reference['required'] is False and isinstance(reference['uri'],str) and reference['uri'].startswith('https://'):
                continue
            target=reference if isinstance(reference,str) else reference['ref']
            _content_reference(package,target)
        except (OSError,ValueError,KeyError,TypeError,RuntimeError,UnicodeError):bad('A05','INVALID_LOCAL_REFERENCE','references/'+str(index))
    return diagnostics


def validate_package(*, repository_root, package_root, policy_path, mode='strict'):
    """Inspect one contained package; no execution or authority is granted."""
    identity=None
    try:
        if not isinstance(mode,str) or mode not in {'strict','inventory'}:raise ValueError('Invalid mode')
        inspection=Path(repository_root);root=inspection.resolve(strict=True)
        if inspection.is_symlink() or not root.is_dir():raise ValueError('Invalid repository root')
        package=_caller_path(root,package_root);policy_file=_caller_path(root,policy_path)
        if not package.is_dir():raise ValueError('Unavailable inspection')
        identity=package.relative_to(root).as_posix()
        policy,contract_schema,result_schema=_load_policy(root,policy_file)
        skill=_authority_file(package,'SKILL.md');text=_bounded_text(skill)
        sidecar=package/'skill-quality.v1.json'
        if sidecar.is_symlink():raise ValueError('Symbolic sidecar')
    except (OSError,ValueError,TypeError,KeyError,RuntimeError,UnicodeError,RecursionError):
        return _public_result(mode,'error',2,[_diagnostic('A06','INVALID_INSPECTION','invocation')])
    def finish(status,code,diagnostics):
        result=_public_result(mode,status,code,diagnostics,identity)
        result['diagnostics']=result['diagnostics'][:policy['limits']['diagnostics']]
        if _schema_errors(result,result_schema):
            return _public_result(mode,'error',2,[_diagnostic('A06','RESULT_SCHEMA_MISMATCH','result')],identity)
        return result
    diagnostics=[]
    try:frontmatter=_frontmatter(text,policy['frontmatter_keys'])
    except (ValueError,TypeError,UnicodeError):
        frontmatter={};diagnostics.append(_diagnostic('A03','INVALID_FRONTMATTER','SKILL.md'))
    if len(text.splitlines())>=policy['limits']['skill_logical_lines_exclusive']:
        diagnostics.append(_diagnostic('A04','SKILL_LINE_LIMIT','SKILL.md'))
    if not sidecar.exists():
        if diagnostics:return finish('fail',1,diagnostics)
        status,code=('legacy',3) if mode=='inventory' else ('fail',1)
        return finish(status,code,[_diagnostic('A22','MISSING_QUALITY_SIDECAR','skill-quality.v1.json')])
    try:contract=_read_object(sidecar)
    except (OSError,ValueError,RuntimeError,UnicodeError,RecursionError):
        return finish('fail',1,diagnostics+[_diagnostic('A02','INVALID_QUALITY_SIDECAR','skill-quality.v1.json')])
    shape_diagnostics,safe_shape=_owned_shapes(contract)
    diagnostics.extend(shape_diagnostics)
    diagnostics.extend(_declaration_diagnostics(package,contract,frontmatter))
    schema_errors=_schema_errors(contract,contract_schema)
    diagnostics.extend(_diagnostic('A02','QUALITY_SCHEMA_VIOLATION','skill-quality.v1.json#'+pointer) for pointer in schema_errors)
    # Type-invalid declarations never reach capability logic. Shape checks use
    # the actual published schema; semantic diagnostics retain their own rules.
    valid_shape=(isinstance(contract.get('capabilities'),dict) and all(type(v) is bool for v in contract['capabilities'].values())
                 and all(isinstance(contract.get(k),dict) for k in ('controls','lookup','routing'))
                 and all(isinstance(contract.get(k),list) for k in ('dependencies','entrypoints','examples','outcomes')))
    if valid_shape and safe_shape:
        diagnostics.extend(_reference_diagnostics(package,contract))
        diagnostics.extend(_dependency_diagnostics(package,contract,root,policy['dependencies']))
        diagnostics.extend(_capability_diagnostics(package,contract,policy))
        diagnostics.extend(_routing_diagnostics(package,contract))
        if __package__:
            from . import skill_quality_examples
        else:
            import skill_quality_examples
        diagnostics.extend(skill_quality_examples.validate_examples(contract))
        diagnostics.extend(_faq_diagnostics(package,contract))
    if 'invocation' in contract:diagnostics.extend(_invocation_diagnostics(package,contract['invocation']))
    return finish('fail',1,diagnostics) if diagnostics else finish('pass',0,[])


def main(argv=None):
    import argparse
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError('Invalid invocation')
        def exit(self, status=0, message=None):
            raise ValueError('Unsupported invocation')
    parser=Parser(add_help=False)
    for flag in ('repository-root','policy','skill-root'):
        parser.add_argument('--'+flag,required=True)
    parser.add_argument('--mode',default='strict')
    try:
        args=parser.parse_args(argv)
        result=validate_package(repository_root=args.repository_root,package_root=args.skill_root,
                                policy_path=args.policy,mode=args.mode)
    except (ValueError,TypeError):
        result=_public_result(None,'error',2,[_diagnostic('A06','INVALID_ARGUMENTS','invocation')])
    print(json.dumps(result,sort_keys=True,ensure_ascii=True,allow_nan=False))
    return result['exit_code']




# ADR-0041: supported local schema subset, consumed independently of optional
# installed packages. No remote resolution, constructors or declared execution.
SCHEMA_KEYWORDS = {'$schema','$id','$defs','$ref','title','description','standard_version','rules',
                   'type','required','properties','additionalProperties','items','enum','const','anyOf',
                   'minItems','maxItems','minLength','maxLength','minimum','maximum','pattern'}
CAPABILITIES = ('routing','version_lookup','secrets','destructive','database_write',
                'untrusted_content','filesystem','subprocess','network')
RULES = ['A%02d' % number for number in range(1,26)]


def _schema_preflight(schema, root=None, depth=0, visiting=()):
    if depth>40 or not isinstance(schema,dict) or set(schema)-SCHEMA_KEYWORDS:
        raise ValueError('Unsupported schema')
    root=schema if root is None else root
    if '$ref' in schema:
        ref=schema['$ref']
        if not isinstance(ref,str) or not ref.startswith('#/$defs/') or ref in visiting:
            raise ValueError('Unsupported schema reference')
        target=root
        for segment in ref[2:].split('/'):
            target=target[segment.replace('~1','/').replace('~0','~')]
        _schema_preflight(target,root,depth+1,(*visiting,ref))
    if 'type' in schema:
        types=schema['type'] if isinstance(schema['type'],list) else [schema['type']]
        if not types or any(t not in {'object','array','string','boolean','integer','number','null'} for t in types):
            raise ValueError('Unsupported schema type')
    if 'required' in schema and (not isinstance(schema['required'],list) or any(not isinstance(k,str) for k in schema['required'])):
        raise ValueError('Invalid required fields')
    for key in ('minItems','maxItems','minLength','maxLength','minimum','maximum'):
        if key in schema and (type(schema[key]) is not int or schema[key]<0):
            raise ValueError('Invalid schema bound')
    if 'pattern' in schema:
        if not isinstance(schema['pattern'],str) or len(schema['pattern'])>256:
            raise ValueError('Invalid schema pattern')
        try:
            re.compile(schema['pattern'])
        except re.error as exc:
            raise ValueError('Invalid schema pattern') from exc
    for key in ('properties','$defs'):
        if key in schema:
            if not isinstance(schema[key],dict):raise ValueError('Invalid schema map')
            for child in schema[key].values():_schema_preflight(child,root,depth+1,visiting)
    if 'items' in schema:_schema_preflight(schema['items'],root,depth+1,visiting)
    if 'additionalProperties' in schema:
        child=schema['additionalProperties']
        if type(child) is not bool:_schema_preflight(child,root,depth+1,visiting)
    if 'anyOf' in schema:
        if not isinstance(schema['anyOf'],list) or not schema['anyOf']:raise ValueError('Invalid schema union')
        for child in schema['anyOf']:_schema_preflight(child,root,depth+1,visiting)
    for key in ('const','enum'):
        if key=='enum' and key in schema and not isinstance(schema[key],list):raise ValueError('Invalid enum')


def _schema_errors(value, schema, root=None, pointer='', depth=0):
    if depth>40:raise ValueError('Schema evaluation depth exceeded')
    root=schema if root is None else root
    if '$ref' in schema:
        target=root
        for segment in schema['$ref'][2:].split('/'):target=target[segment.replace('~1','/').replace('~0','~')]
        return _schema_errors(value,target,root,pointer,depth+1)
    checks={'object':lambda:type(value) is dict,'array':lambda:type(value) is list,
            'string':lambda:type(value) is str,'boolean':lambda:type(value) is bool,
            'integer':lambda:type(value) is int,'number':lambda:type(value) in (int,float),
            'null':lambda:value is None}
    expected=schema.get('type')
    if expected and not any(checks[t]() for t in (expected if isinstance(expected,list) else [expected])):
        return [pointer]
    same=lambda a,b: type(a) is type(b) and a==b
    if 'const' in schema and not same(value,schema['const']):return [pointer]
    if 'enum' in schema and not any(same(value,x) for x in schema['enum']):return [pointer]
    if 'anyOf' in schema and not any(not _schema_errors(value,s,root,pointer,depth+1) for s in schema['anyOf']):return [pointer]
    errors=[]
    if isinstance(value,dict):
        props=schema.get('properties',{})
        errors.extend(pointer+'/'+key for key in schema.get('required',[]) if key not in value)
        for key,child in value.items():
            if key in props:errors.extend(_schema_errors(child,props[key],root,pointer+'/'+key,depth+1))
            elif schema.get('additionalProperties') is False:errors.append(pointer+'/unknown')
            elif isinstance(schema.get('additionalProperties'),dict):
                errors.extend(_schema_errors(child,schema['additionalProperties'],root,pointer+'/item',depth+1))
    if isinstance(value,list):
        if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',100000):errors.append(pointer)
        if 'items' in schema:
            for index,child in enumerate(value):errors.extend(_schema_errors(child,schema['items'],root,pointer+'/'+str(index),depth+1))
    if isinstance(value,str):
        if len(value)<schema.get('minLength',0) or len(value)>schema.get('maxLength',1000000):errors.append(pointer)
        if 'pattern' in schema and re.search(schema['pattern'],value) is None:errors.append(pointer)
    if type(value) in (int,float):
        if value<schema.get('minimum',-float('inf')) or value>schema.get('maximum',float('inf')):errors.append(pointer)
    return sorted(set(errors))[:100]


def _load_policy(root, path):
    from urllib.parse import urlsplit
    policy=_read_object(path)
    required={'schema','standard_version','standard','contract_schema','result_schema','frontmatter_keys',
              'rules','limits','dependencies','official_origins'}
    if set(policy)!=required or policy['schema']!='skill-authoring-standard.v1' or policy['standard_version']!='1.0':
        raise ValueError('Invalid policy identity')
    if policy['rules']!=RULES or policy['frontmatter_keys']!=['name','description']:
        raise ValueError('Invalid policy vocabulary')
    limits=policy['limits']
    if (not isinstance(limits,dict) or limits.get('skill_logical_lines_exclusive')!=500
            or type(limits.get('diagnostics')) is not int or not 1<=limits['diagnostics']<=100):
        raise ValueError('Invalid policy limits')
    if not isinstance(policy['dependencies'],list) or not isinstance(policy['official_origins'],list):
        raise ValueError('Invalid policy authorities')
    dependency_shape,_=_owned_shapes({'dependencies':policy['dependencies']})
    if dependency_shape:raise ValueError('Invalid policy dependency records')
    for origin in policy['official_origins']:
        if not isinstance(origin,str):raise ValueError('Invalid official origin')
        parts=urlsplit(origin)
        if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.path not in ('','/') or parts.query or parts.fragment:
            raise ValueError('Invalid official origin')
    standard=_caller_path(root,policy['standard'])
    standard_text=_bounded_text(standard)
    if 'Standard version: 1.0' not in standard_text or any('| '+rule+' |' not in standard_text for rule in RULES):
        raise ValueError('Standard identity mismatch')
    schemas=[]
    for key in ('contract_schema','result_schema'):
        schema=_read_object(_caller_path(root,policy[key]))
        if schema.get('standard_version')!='1.0' or schema.get('rules')!=RULES or schema.get('type')!='object' or not schema.get('required'):
            raise ValueError('Schema identity mismatch')
        _schema_preflight(schema);schemas.append(schema)
    return policy,*schemas


def _bounded_text(path):
    if not path.is_file() or path.stat().st_size>1024*1024:raise ValueError('Unavailable bounded input')
    return path.read_text(encoding='utf-8')


def _substantive(value):
    if not isinstance(value,str):return False
    words=[line.strip() for line in value.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    return bool(words) and ' '.join(words).lower() not in {'todo','tbd','placeholder'}


def _frontmatter(text, allowed):
    lines=text.splitlines()
    if not lines or lines[0]!='---':raise ValueError('Missing frontmatter')
    closing=next((i for i,line in enumerate(lines[1:],1) if line=='---'),None)
    if closing is None:raise ValueError('Unclosed frontmatter')
    result={};index=1
    while index<closing:
        line=lines[index];index+=1
        if not line.strip() or line.lstrip().startswith('#'):continue
        match=re.fullmatch(r'([a-z][a-z0-9-]*):(?:[ \t]+(.*))?',line)
        if not match:raise ValueError('Unsupported frontmatter syntax')
        key,value=match.groups();value='' if value is None else value
        if key not in allowed or key in result:raise ValueError('Unsupported or duplicate key')
        if value in {'>','|','>-','|-','>+','|+'}:
            block=[]
            while index<closing and (lines[index].startswith((' ','\t')) or not lines[index].strip()):
                block.append(lines[index].strip());index+=1
            value=(' ' if value.startswith('>') else '\n').join(block)
        elif value.startswith('"'):
            value=json.loads(value)
        elif value.startswith("'"):
            if re.fullmatch(r"'(?:[^']|'')*'",value) is None:raise ValueError('Malformed quoted value')
            value=value[1:-1].replace("''", "'")
        elif (value.startswith(('[','{','!','&','*')) or ': ' in value
              or value.lower() in {'true','false','yes','no','on','off','null','~'}
              or re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',value)):
            raise ValueError('Unsupported YAML construct')
        if not _substantive(value):raise ValueError('Empty field')
        result[key]=value
    if set(result)!=set(allowed):raise ValueError('Missing frontmatter fields')
    return result


def _scope_path(package, reference):
    if not isinstance(reference,str) or not reference or '\\' in reference or PureWindowsPath(reference).drive or '://' in reference:
        raise ValueError('Invalid contained scope')
    raw=Path(reference)
    if raw.is_absolute() or '..' in raw.parts:raise ValueError('Escaping contained scope')
    target=package/raw
    target.resolve().relative_to(package)
    current=target
    while current!=package:
        if current.is_symlink() or getattr(current,'is_junction',lambda:False)():raise ValueError('Symbolic scope')
        current=current.parent
    return target


def _invocation_diagnostics(package, invocation, rule='A11'):
    diagnostics=[]
    prefix='invocation' if rule=='A11' else 'controls/subprocess'
    def bad(field):diagnostics.append(_diagnostic(rule,'INVALID_INVOCATION','skill-quality.v1.json#/'+prefix+'/'+field))
    if not isinstance(invocation,dict):bad('declaration');return diagnostics
    for field in ('script','tests'):
        if rule=='A11':
            try:_authority_file(package,invocation.get(field))
            except (OSError,ValueError,RuntimeError):bad(field)
    argv=invocation.get('argv')
    if not isinstance(argv,list) or not argv or any(not isinstance(arg,str) or not arg or '\x00' in arg for arg in argv):bad('argv')
    if invocation.get('shell') is not False:bad('shell')
    try:
        cwd=_scope_path(package,invocation.get('cwd'))
        if not cwd.is_dir():raise ValueError('Unavailable cwd')
    except (OSError,ValueError,RuntimeError):bad('cwd')
    timeout=invocation.get('timeout')
    import math
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=300:bad('timeout')
    if rule=='A11' and not _substantive(invocation.get('result_type')):bad('result_type')
    return diagnostics


def _capability_diagnostics(package, contract, policy):
    from urllib.parse import urlsplit
    from datetime import date
    diagnostics=[];caps=contract.get('capabilities',{});controls=contract.get('controls',{})
    def bad(rule,field):diagnostics.append(_diagnostic(rule,'INVALID_CAPABILITY_CONTROL','skill-quality.v1.json#/'+field))
    lookup=contract.get('lookup',{})
    if not caps.get('version_lookup'):
        if lookup.get('kind')!='not-applicable' or any(d.get('kind') in {'api','network'} for d in contract.get('dependencies',[]) if isinstance(d,dict)):
            bad('A13','lookup')
    else:
        if lookup.get('kind')!='version-sensitive' or lookup.get('preferred')!='context7-first':bad('A14','lookup/preferred')
        for field in ('version','source','retrieval_date','missing_policy','stale_policy'):
            if not _substantive(lookup.get(field)):bad('A14','lookup/'+field)
        try:date.fromisoformat(lookup.get('retrieval_date',''))
        except (ValueError,TypeError):bad('A14','lookup/retrieval_date')
        for field in ('source','fallback'):
            try:
                parts=urlsplit(lookup.get(field,''));origin=parts.scheme+'://'+parts.netloc
                if parts.scheme!='https' or parts.username or parts.password or not parts.hostname or origin not in policy['official_origins']:
                    raise ValueError('Unapproved origin')
            except (ValueError,TypeError):bad('A14','lookup/'+field)
    required={
        'secrets':('A15',('owner','reference','redaction','denied_outputs','output_policy')),
        'destructive':('A16',('owner','scope','authorization_source')),
        'database_write':('A17',('owner','system','backup','recovery','transaction','failure','record_authority')),
        'untrusted_content':('A18',('owner','role','prohibit_expansion')),
        'filesystem':('A19',('owner','roots','read','write','delete','traversal','symlinks')),
        'subprocess':('A20',('owner','argv','shell','cwd','timeout','output_limit','cancellation_owner')),
        'network':('A21',('owner','schemes','targets','redirect_owner','dns_owner','private_addresses','loopback','metadata','internal_exceptions','timeout')),
    }
    for name,(rule,fields) in required.items():
        if not caps.get(name):continue
        control=controls.get(name)
        if not isinstance(control,dict):bad(rule,'controls/'+name);continue
        for field in fields:
            value=control.get(field)
            if field in {'shell','internal_exceptions'}:
                if field not in control:bad(rule,'controls/'+name+'/'+field)
            elif field=='owner':
                if not _substantive(value):bad(rule,'controls/'+name+'/'+field)
            elif not value:bad(rule,'controls/'+name+'/'+field)
        if name=='secrets':
            if control.get('output_policy')!='redacted' or any(k in control for k in ('literal','password','token','secret','api_key')) or 'SYNTHETIC_SECRET' in json.dumps(control):bad(rule,'controls/secrets/output_policy')
            if not isinstance(control.get('denied_outputs'),list) or not control['denied_outputs']:bad(rule,'controls/secrets/denied_outputs')
        elif name=='destructive':
            if control.get('authorization_source') not in {'existing-session','explicit-user','trusted-controller'} or control.get('bypass',False) is not False:bad(rule,'controls/destructive/authorization_source')
            if not _substantive(control.get('recovery')) and not _substantive(control.get('irreversibility')):bad(rule,'controls/destructive/recovery')
        elif name=='database_write':
            try:_content_reference(package,control.get('record_authority'))
            except (OSError,ValueError,RuntimeError,UnicodeError):bad(rule,'controls/database_write/record_authority')
        elif name=='untrusted_content':
            if control.get('role')!='data-only' or set(control.get('prohibit_expansion',[]))!={'targets','commands','tools','authority'} or 'override' in control:bad(rule,'controls/untrusted_content/role')
        elif name=='filesystem':
            if control.get('traversal')!='reject' or control.get('symlinks')!='reject':bad(rule,'controls/filesystem/traversal')
            for field in ('roots','read','write','delete'):
                scopes=control.get(field)
                if not isinstance(scopes,list) or not scopes:bad(rule,'controls/filesystem/'+field);continue
                for scope in scopes:
                    try:_scope_path(package,scope)
                    except (OSError,ValueError,RuntimeError):bad(rule,'controls/filesystem/'+field)
        elif name=='subprocess':
            diagnostics.extend(_invocation_diagnostics(package,control,rule))
            if type(control.get('output_limit')) is not int or not 0<control['output_limit']<=1048576:bad(rule,'controls/subprocess/output_limit')
        elif name=='network':
            if control.get('schemes')!=['https']:bad(rule,'controls/network/schemes')
            targets=control.get('targets')
            if not isinstance(targets,list) or not targets:bad(rule,'controls/network/targets')
            else:
                for target in targets:
                    try:
                        parts=urlsplit(target)
                        if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or '*' in target:raise ValueError('Unbounded target')
                    except (ValueError,TypeError):bad(rule,'controls/network/targets')
            if any(control.get(field)!='block' for field in ('private_addresses','loopback','metadata')):bad(rule,'controls/network/private_addresses')
            exceptions=control.get('internal_exceptions')
            if not isinstance(exceptions,list) or any(not isinstance(row,dict) or row.get('kind')!='controlled-internal-mcp' or not row.get('owner') or not row.get('authority') for row in exceptions):bad(rule,'controls/network/internal_exceptions')
            import math
            timeout=control.get('timeout')
            if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=300:bad(rule,'controls/network/timeout')
    return diagnostics



def _owned_shapes(contract):
    """Close owned namespaces and reject wrong scalar/container types safely."""
    diagnostics=[];safe=True
    def error(pointer,hard=False):
        nonlocal safe
        diagnostics.append(_diagnostic('A02','QUALITY_SCHEMA_VIOLATION','skill-quality.v1.json#'+pointer))
        if hard:safe=False
    def record(value,fields,pointer):
        if not isinstance(value,dict):error(pointer,True);return
        for key,child in value.items():
            if key not in fields:error(pointer+'/unknown');continue
            typ=fields[key]
            if typ=='strings':valid=isinstance(child,list) and all(isinstance(x,str) for x in child)
            elif typ=='number':valid=type(child) in (int,float)
            elif typ=='content':valid=isinstance(child,str) or (isinstance(child,dict) and set(child)=={'ref'} and isinstance(child['ref'],str))
            else:valid=type(child) is typ
            if not valid:error(pointer+'/'+key,True)
    text=str;strings='strings'
    controls={
      'secrets':dict.fromkeys(('owner','reference','redaction','output_policy'),text)|{'denied_outputs':strings},
      'destructive':dict.fromkeys(('owner','authorization_source','recovery','irreversibility'),text)|{'scope':strings,'bypass':bool},
      'database_write':dict.fromkeys(('owner','system','backup','recovery','transaction','failure','record_authority'),text)|{'already_verified':bool},
      'untrusted_content':{'owner':text,'role':text,'prohibit_expansion':strings},
      'filesystem':{'owner':text,'roots':strings,'read':strings,'write':strings,'delete':strings,'traversal':text,'symlinks':text},
      'subprocess':{'owner':text,'argv':strings,'shell':bool,'cwd':text,'timeout':'number','output_limit':int,'cancellation_owner':text},
      'network':dict.fromkeys(('owner','redirect_owner','dns_owner','private_addresses','loopback','metadata'),text)|{'schemes':strings,'targets':strings,'internal_exceptions':list,'timeout':'number'},
    }
    value=contract.get('controls',{})
    if not isinstance(value,dict):error('/controls',True)
    else:
        for cap,control in value.items():
            if cap not in controls:error('/controls/unknown');continue
            record(control,controls[cap],'/controls/'+cap)
            if cap=='network' and isinstance(control,dict) and isinstance(control.get('internal_exceptions'),list):
                for index,exception in enumerate(control['internal_exceptions']):record(exception,{'kind':str,'owner':str,'authority':str},'/controls/network/internal_exceptions/'+str(index))
    record(contract.get('lookup',{}),dict.fromkeys(('kind','preferred','fallback','version','source','retrieval_date','missing_policy','stale_policy'),text),'/lookup')
    record(contract.get('routing',{}),{'kind':text,'entry':text,'branches':strings,'diagram':dict},'/routing')
    routing=contract.get('routing',{})
    if isinstance(routing,dict) and 'diagram' in routing:record(routing['diagram'],{'ref':str},'/routing/diagram')
    record(contract.get('lifecycle',{}),{'owner':str,'completion_owner':str},'/lifecycle')
    dependencies=contract.get('dependencies',[])
    if isinstance(dependencies,list):
        for index,dependency in enumerate(dependencies):
            pointer='/dependencies/'+str(index)
            record(dependency,dict.fromkeys(('id','version','authority','when_missing','when_mismatch','kind'),text)|{'required':bool,'fallback':dict},pointer)
            if isinstance(dependency,dict) and 'fallback' in dependency:record(dependency['fallback'],{'ref':str,'authorizes':list},pointer+'/fallback')
    if 'invocation' in contract:record(contract['invocation'],{'script':str,'tests':str,'argv':strings,'shell':bool,'cwd':str,'timeout':'number','result_type':str},'/invocation')
    return diagnostics,safe


def _routing_diagnostics(package, contract):
    routing=contract.get('routing',{});enabled=contract.get('capabilities',{}).get('routing')
    if not enabled:
        return [] if routing.get('kind')=='leaf' and set(routing)=={'kind'} else [_diagnostic('A08','FALSE_LEAF','skill-quality.v1.json#/routing')]
    try:
        if routing.get('kind')!='conditional':raise ValueError('False leaf')
        branches=routing['branches'];entry=routing['entry'];diagram=routing['diagram']
        if not isinstance(branches,list) or len(set(branches))!=len(branches) or not all(isinstance(b,str) and b for b in branches) or not isinstance(entry,str):raise ValueError('Invalid branches')
        content=_content_reference(package,diagram['ref'])
        _bounded_text(_authority_file(package,diagram['ref'].partition('#')[0])).encode('ascii')
        edges=re.findall(r'\[([a-zA-Z0-9_-]+)\]\s*->\s*\[([a-zA-Z0-9_-]+)\]',content)
        allowed=set(branches)|{entry}
        if not edges or any(a not in allowed or b not in allowed for a,b in edges):raise ValueError('Unknown diagram branch')
        reached={entry}
        for _ in range(len(allowed)):
            reached.update(b for a,b in edges if a in reached)
        if not set(branches)<=reached or any(e.get('branch') not in branches for e in contract.get('examples',[]) if isinstance(e,dict)):raise ValueError('Unreachable branch')
    except (KeyError,OSError,ValueError,TypeError,RuntimeError,UnicodeError):
        return [_diagnostic('A08','INVALID_ROUTING_DIAGRAM','skill-quality.v1.json#/routing')]
    return []


if __name__=='__main__':
    raise SystemExit(main())
