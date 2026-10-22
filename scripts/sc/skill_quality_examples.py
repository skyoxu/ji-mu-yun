"""ADR-0041: bounded static example and public-entry declarations only."""
import re


def _diagnostic(rule,code,pointer):
    return {'rule':rule,'code':code,'path':'skill-quality.v1.json#/'+pointer,
            'message':'The declaration does not satisfy the local contract.'}


def _content(value):
    if isinstance(value,str):
        return bool(value.strip()) and any(line.strip() and not line.lstrip().startswith('#') for line in value.splitlines())
    return isinstance(value,dict) and set(value)=={'ref'} and isinstance(value['ref'],str) and bool(value['ref'])


def validate_examples(contract):
    """Return declaration diagnostics without imports, I/O or execution."""
    diagnostics=[];examples=contract.get('examples');outcomes=contract.get('outcomes')
    def bad(rule,code,path):diagnostics.append(_diagnostic(rule,code,path))
    if not isinstance(outcomes,list) or not all(isinstance(v,str) and v for v in outcomes) or len(set(outcomes))!=len(outcomes):
        bad('A07','INVALID_OUTCOMES','outcomes');outcomes=[]
    routing=contract.get('routing',{});branches=routing.get('branches',[]) if contract.get('capabilities',{}).get('routing') else outcomes
    if not isinstance(branches,list) or not all(isinstance(v,str) and v for v in branches):branches=[]
    if not isinstance(examples,list) or len(examples)!=3:
        bad('A07','PRIMARY_EXAMPLE_COUNT','examples')
    else:
        seen_branches=set();seen_pairs=set()
        for index,(value,outcome) in enumerate(zip(examples,('typical','boundary','error'))):
            path='examples/'+str(index)
            if not isinstance(value,dict) or set(value)!={'outcome','branch','input','output','expected_result'}:
                bad('A07','INVALID_PRIMARY_EXAMPLE',path);continue
            if value['outcome']!=outcome or outcome not in outcomes:bad('A07','PRIMARY_EXAMPLE_ORDER',path+'/outcome')
            branch=value['branch']
            if not isinstance(branch,str) or branch not in branches or branch in seen_branches:
                bad('A07','INVALID_EXAMPLE_BRANCH',path+'/branch')
            else:seen_branches.add(branch)
            if not all(_content(value[key]) and isinstance(value[key],str) for key in ('input','output','expected_result')):
                bad('A07','EMPTY_EXAMPLE_PAIR',path);continue
            pair=tuple(' '.join(value[key].split()).casefold() for key in ('input','output'))
            if pair in seen_pairs:bad('A07','DUPLICATE_EXAMPLE_PAIR',path)
            seen_pairs.add(pair)
    entries=contract.get('entrypoints',[]);seen=set()
    if not isinstance(entries,list) or not entries:bad('A10','MISSING_PUBLIC_ENTRY','entrypoints');return diagnostics
    allowed={'id','inputs','outputs','preflight','standalone','dependencies','caller_setup','install_missing','skip_missing'}
    for index,entry in enumerate(entries):
        path='entrypoints/'+str(index)
        if not isinstance(entry,dict):bad('A10','INVALID_PUBLIC_ENTRY',path);continue
        identity=entry.get('id')
        if not isinstance(identity,str) or re.fullmatch('[a-z][a-z0-9-]{0,63}',identity) is None or identity in seen:bad('A10','INVALID_ENTRY_ID',path+'/id')
        else:seen.add(identity)
        if set(entry)-allowed:bad('A10','UNKNOWN_ENTRY_FIELD',path)
        for key in ('inputs','outputs'):
            value=entry.get(key)
            if not isinstance(value,list) or not value or not all(_content(v) for v in value):bad('A10','MISSING_ENTRY_DECLARATION',path+'/'+key)
        if not _content(entry.get('preflight')):bad('A10','MISSING_PREFLIGHT',path+'/preflight')
        if type(entry.get('standalone')) is not bool:bad('A10','MISSING_STANDALONE_BEHAVIOR',path+'/standalone')
        if not _content(entry.get('caller_setup')) or entry.get('caller_setup')=='implicit':bad('A10','UNDECLARED_CALLER_SETUP',path+'/caller_setup')
        for key in ('install_missing','skip_missing'):
            if key in entry and entry[key] is not False:bad('A10','UNSAFE_DEPENDENCY_BEHAVIOR',path+'/'+key)
    return diagnostics
