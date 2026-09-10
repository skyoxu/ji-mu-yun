"""W3 real Git/catalog/freeze successor regression (ADR-0059/ADR-0060).

All publication-shaped artifacts are isolated fixtures, never live publication.
No freshness, catalog validation or successor function is mocked.
"""
import copy
import json
from pathlib import Path
import subprocess

import pytest
from scripts.python import knowledge_context_validation as k
from scripts.python.knowledge_gate_projection import observe_knowledge, project_knowledge_gates
from scripts.python.skill_input_protocol import digest, identity, read_json
from scripts.python.tests.test_toolchain_workflow_repair_e2e import fixture, complete
from scripts.python import skill_input_v2 as v2
from scripts.python.skill_input_generation import read_generation


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8', newline='\n')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode('utf-8').strip()


def commit(root, *paths):
    git(root, 'add', '--', *paths)
    git(root, '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
    return git(root, 'rev-parse', 'HEAD')


def seal_publication(root, snapshot_commit):
    paths = {'snapshot': 'knowledge/snapshots/repository-source-snapshot.v1.json',
        'catalog_v2': k.CATALOG_RELATIVE.as_posix(), 'projections': k.PROJECTION_RELATIVE.as_posix(),
        'catalog_v1': 'knowledge/catalogs/repository-knowledge-catalog.v1.json',
        'policy': k.POLICY_RELATIVE.as_posix(), 'exclusions': 'knowledge/policies/source-exclusions.v1.json',
        'query_suite': 'knowledge/evaluation/repository-knowledge-query-suite.v1.json'}
    generation_id = 'a' * 64
    directory = root / 'knowledge/indexes/generations' / generation_id
    write(directory / 'query-report.json', {'status':'fixture'})
    artifacts = {name: {'sha256':digest((root/path).read_bytes())} for name,path in paths.items()}
    artifacts['query_report'] = {'bundle_path':'query-report.json','sha256':digest((directory/'query-report.json').read_bytes())}
    manifest = {'schema_version':'jimuyun.knowledge-publication-generation.v1', 'generation_id':generation_id,
        'source_snapshot_id':'snapshot-1', 'main_commit':snapshot_commit, 'artifacts':artifacts}
    write(directory / 'manifest.json', manifest)
    pointer = {'schema_version':'jimuyun.knowledge-index-pointer.v2','generation_id':generation_id,
        'generation_sha256':digest((directory/'manifest.json').read_bytes()),'source_snapshot_id':'snapshot-1','main_commit':snapshot_commit}
    write(root / 'knowledge/indexes/current.json', pointer)
    write(root / 'knowledge/indexes/last-known-good.json', pointer)


def locator_fixture(root):
    request = fixture(root, 'vdd-execution-plan')
    git(root, 'branch', '-M', 'main')
    git(root, 'config', 'core.autocrlf', 'false')
    (root/'other.md').write_text('Unselected catalog source\n', encoding='utf-8', newline='\n')
    baseline = commit(root, 'requirements.md', 'other.md')
    source_hash = digest((root/'requirements.md').read_bytes())[7:]
    snapshot = {'ref':'refs/heads/main','commit':baseline,'snapshot_id':'snapshot-1',
        'sources':[{'path':p,'sha256':digest((root/p).read_bytes())[7:]} for p in ['requirements.md','other.md']]}
    catalog = {'schema_version':'jimuyun.repository-knowledge-catalog.v2','authority_ref':'refs/heads/main','source_snapshot':snapshot,
        'modules':[{'module_id':'core','source_path':'requirements.md','source_sha256':source_hash,'resources':[]}]}
    policy = {'policy_revision':'policy-1'}
    projection = {'policy_revision':'policy-1','policy_sha256':identity(policy),'catalog_sha256':identity(catalog),
        'source_snapshot_id':'snapshot-1','projections':[{'consumer':'vdd','eligible_module_ids':['core']}]}
    write(root/k.CATALOG_RELATIVE,catalog);write(root/k.POLICY_RELATIVE,policy);write(root/k.PROJECTION_RELATIVE,projection)
    write(root/'knowledge/snapshots/repository-source-snapshot.v1.json',snapshot)
    for path in ['knowledge/catalogs/repository-knowledge-catalog.v1.json','knowledge/policies/source-exclusions.v1.json','knowledge/evaluation/repository-knowledge-query-suite.v1.json']:
        write(root/path, {'fixture':True})
    seal_publication(root, baseline)
    candidate = {'module_id':'core','path':'requirements.md','source_sha256':source_hash,
        'read_set':[{'path':'requirements.md','source_sha256':source_hash}]}
    locator_request = {'schema_version':k.REQUEST_SCHEMA,'request_id':'fixture','consumer':'vdd','policy_revision':'policy-1',
        'snapshot':{'ref':'refs/heads/main','commit':baseline},'allow_stale_catalog':True}
    result = {'schema_version':k.RESULT_SCHEMA,'request_id':'fixture','snapshot':locator_request['snapshot'],
        'status':'matched','source_snapshot_id':'snapshot-1','policy_revision':'policy-1','candidates':[candidate]}
    context = {'schema_version':'jimuyun.vdd-knowledge-context.v1','locator_request':locator_request,'locator_result':result,
        'request_sha256':identity(locator_request),'result_sha256':identity(result),'required_modules':['core'],
        'decisions':[{'owner':'adapter','candidate':{'path':'requirements.md','source_sha256':source_hash},'decision':'accepted','satisfies':['core']}]}
    context['preflight']={'status':'ready','failure_code':None,'context_sha256':identity(context),
        'knowledge_freshness':'current','catalog_failure_code':None}
    write(root/'context.json',context)
    reseal_freeze(root)
    candidate_baseline=commit(root,'.')
    authority=read_json(root/'authority.json');authority['skill_input_baseline']=candidate_baseline
    write(root/'authority.json',authority)
    request['bindings']['authority']['sha256']=digest((root/'authority.json').read_bytes())
    request['bindings']['knowledge_freeze']['sha256']=digest((root/'freeze.json').read_bytes())
    assert k.validate_catalog_freshness(root) is None
    assert k.validate_context(context,repository_root=root,verify_catalog=True,verify_sources=True,require_selection=True) is None
    return request


def reseal_freeze(root):
    write(root/'freeze.json',{'schema_version':'jimuyun.vdd-knowledge-freeze.v1','context_path':'context.json',
        'context_sha256':digest((root/'context.json').read_bytes()),'authorizes':[]})


def make_stale(root, selected=False):
    path='requirements.md' if selected else 'other.md'
    (root/path).write_text('Changed source bytes\n',encoding='utf-8',newline='\n')
    commit(root,path)
    assert k.validate_catalog_freshness(root)=='catalog_stale'


@pytest.mark.parametrize('state', ['current','stale-unselected','stale-selected'])
def test_real_locator_successor_preserves_frozen_evidence(tmp_path,state):
    locator_fixture(tmp_path)
    if state!='current':make_stale(tmp_path,selected=state=='stale-selected')
    if state!='current':
        assert k.validate_context(read_json(tmp_path/'context.json'),repository_root=tmp_path,verify_catalog=True,require_selection=True)=='preflight_catalog_freshness_invalid'
    frozen={p:p.read_bytes() for p in [tmp_path/'freeze.json',tmp_path/'context.json',*(tmp_path/'knowledge').rglob('*.json')]}
    result=observe_knowledge(tmp_path,tmp_path/'freeze.json',selection_hash='not-used-by-locator')
    assert result['catalog_stale']==(state!='current')
    assert result['source_refreshed']==(state=='stale-selected')
    successor=result['successor_context']
    assert result['context_hash']==identity(successor)
    assert successor['preflight']['knowledge_freshness']==('current' if state=='current' else 'degraded')
    assert k.validate_context(successor,repository_root=tmp_path,verify_catalog=True,verify_sources=True,require_selection=True,require_catalog_membership=True) is None
    assert all(p.read_bytes()==data for p,data in frozen.items())
    assert observe_knowledge(tmp_path,tmp_path/'freeze.json',selection_hash='not-used-by-locator')==result


def test_stale_locator_completes_v2_pipeline(tmp_path):
    request=locator_fixture(tmp_path)
    make_stale(tmp_path)
    _,result,_=complete(tmp_path,request)
    receipt=read_generation(tmp_path/request['storage'],result['pointer']['generation_id'])['receipt']
    assert receipt['gates']['route']=='degraded-continuation'
    assert receipt['gates']['execution_allowed'] is True
    assert receipt['gates']['publication_allowed'] is False
    assert receipt['knowledge']['successor_context']['preflight']['knowledge_freshness']=='degraded'
    assert receipt['authorizes']==[]


@pytest.mark.parametrize('case', ['failed-preflight','context-hash','publication','missing-source','selection','policy','stale-disallowed','malformed-freshness','forged-source-refresh'])
def test_successor_keeps_failure_boundaries(tmp_path,case):
    locator_fixture(tmp_path);make_stale(tmp_path)
    context=read_json(tmp_path/'context.json')
    if case=='malformed-freshness':context['preflight']['knowledge_freshness']='unknown'
    elif case=='forged-source-refresh':
        context['locator_result']['candidates'][0]['module_id']='outside-projection'
        context['result_sha256']=identity(context['locator_result'])
        context['source_refresh']={'schema_version':'jimuyun.knowledge-source-refresh.v1','mode':'current_worktree_read_set','base_locator_result_sha256':'sha256:'+'0'*64}
        context['preflight']['context_sha256']=identity({k:v for k,v in context.items() if k!='preflight'})
    elif case=='failed-preflight':context['preflight']['status']='blocked'
    elif case=='context-hash':context['preflight']['context_sha256']='sha256:'+'0'*64
    elif case=='publication':(tmp_path/'knowledge/indexes/current.json').write_text('{}',encoding='utf-8')
    elif case=='missing-source':(tmp_path/'requirements.md').unlink()
    elif case=='policy':
        # Re-seal fixture publication: the failure must come from policy binding.
        policy=read_json(tmp_path/k.POLICY_RELATIVE);policy['policy_revision']='policy-2';write(tmp_path/k.POLICY_RELATIVE,policy)
        seal_publication(tmp_path,context['locator_request']['snapshot']['commit'])
    elif case=='selection':
        context['locator_result']['candidates'][0]['module_id']='outside-projection'
        context['result_sha256']=identity(context['locator_result'])
        context['preflight']['context_sha256']=identity({k:v for k,v in context.items() if k!='preflight'})
    elif case=='stale-disallowed':
        context['locator_request']['allow_stale_catalog']=False
        context['request_sha256']=identity(context['locator_request'])
        context['preflight']['context_sha256']=identity({k:v for k,v in context.items() if k!='preflight'})
    write(tmp_path/'context.json',context);reseal_freeze(tmp_path)
    before=(tmp_path/'freeze.json').read_bytes(),(tmp_path/'context.json').read_bytes()
    with pytest.raises((OSError,ValueError)):
        observe_knowledge(tmp_path,tmp_path/'freeze.json',selection_hash='not-used-by-locator')
    assert before==((tmp_path/'freeze.json').read_bytes(),(tmp_path/'context.json').read_bytes())


def test_verified_successor_freeze_is_reusable(tmp_path):
    locator_fixture(tmp_path);make_stale(tmp_path,selected=True)
    result=observe_knowledge(tmp_path,tmp_path/'freeze.json',selection_hash='unused')
    frozen=(tmp_path/'freeze.json').read_bytes(),(tmp_path/'context.json').read_bytes()
    write(tmp_path/'successor-context.json',result['successor_context'])
    write(tmp_path/'successor-freeze.json',{'schema_version':'jimuyun.vdd-knowledge-freeze.v1',
        'context_path':'successor-context.json','context_sha256':digest((tmp_path/'successor-context.json').read_bytes()),'authorizes':[]})
    reused=observe_knowledge(tmp_path,tmp_path/'successor-freeze.json',selection_hash='unused')
    assert reused['catalog_stale'] and not reused['source_refreshed']
    assert reused['context_hash']==result['context_hash']
    assert frozen==((tmp_path/'freeze.json').read_bytes(),(tmp_path/'context.json').read_bytes())
