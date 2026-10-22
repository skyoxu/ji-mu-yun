"""ADR-0041/ADR-0062: real bridge and VDD consumer, deterministic render fixtures."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

import pytest

ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT))
sys.dont_write_bytecode=True
from scripts.toolchain.bmad_native import contained, verify
from scripts.toolchain.bmad_native.testing import fixture, load, command, REPO
bridge=load('spec_bridge','.agents/skills/jimuyun-spec/scripts/bridge.py')
canonical=load('spec_canonical','.agents/skills/jimuyun-spec/scripts/canonical_package.py')
freeze=load('spec_freeze','.agents/skills/vdd-execution-plan/scripts/source_freeze.py')
SPEC='_bmad-output/specs/spec-example/SPEC.md'


def initial(root, crlf=False):
    package=root/Path(SPEC).parent;package.mkdir(parents=True)
    entries=[{'path':str(PurePosixPath(SPEC).parent/'rules.md'),'role':'normative_companion'},
             {'path':str(PurePosixPath(SPEC).parent/'adopted.md'),'role':'adopted_companion'},
             {'path':'docs/source.md','role':'provenance'}]
    lines=['---','id: SPEC-example','package_schema: canonical-spec-package.v1','companions:']
    for e in entries[:2]:lines+=['  - path: '+e['path'],'    role: '+e['role']]
    lines+=['sources:','  - path: docs/source.md','    role: provenance','---','# Example','CAP-1: Keep the accepted behavior.','']
    text='\n'.join(lines)
    (root/SPEC).write_bytes(text.replace('\n','\r\n').encode() if crlf else text.encode())
    init=command(['uv','run',str(root/'_bmad/scripts/memlog.py'),'init','--workspace',str(package),'--field','topic=example'],root)
    assert init.returncode==0,init.stderr
    append=command(['uv','run',str(root/'_bmad/scripts/memlog.py'),'append','--workspace',str(package),'--type','capability','--text','CAP-1: Accepted behavior'],root)
    assert append.returncode==0,append.stderr
    for e in entries:
        p=root/e['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_text('Original '+e['role']+'\n',encoding='utf-8')
    descriptor,selection,sha=canonical.build_contract(root,root/SPEC)
    registry=root/'_bmad-output/specs/canonical-spec-package-selections'
    canonical.write_json(registry/(sha.replace(':','-')+'.json'),selection)
    canonical.write_json(registry/'current/SPEC-example.json',{'package_id':'SPEC-example','schema':canonical.CURRENT_SCHEMA,'selection_hash':sha})
    return descriptor,selection,sha


def render_refresh(root,run,crlf=False):
    """Deterministic fixture output, explicitly not an LLM/native workflow run."""
    path=root/run/'native'/SPEC
    text=path.read_text(encoding='utf-8').replace('Keep the accepted behavior.','Keep the accepted behavior and expose a diagnostic.')
    path.write_bytes(text.replace('\n','\r\n').encode() if crlf else text.encode())
    memory=path.parent/'.memlog.md'
    result=command(['uv','run',str(root/run/'native/_bmad/scripts/memlog.py'),'append','--workspace',str(path.parent),'--type','event','--text','Deterministic transport fixture refresh.'],root/run/'native')
    assert result.returncode==0,result.stderr


@pytest.mark.parametrize('crlf',[False,True])
def test_round_trip_and_real_vdd_consumer(tmp_path,crlf):
    root=fixture(tmp_path/'space \u4e2d\u6587')
    descriptor,selection,sha=initial(root,crlf)
    before={e['path']:(root/e['path']).read_bytes() for e in descriptor['companions']+descriptor['sources']}
    for number in range(2):
        run=f'logs/bmad-wrappers/round-{number}'
        result=bridge.prepare(root,SPEC,run)
        native,_=bridge.native_descriptor((root/result['native_spec']).read_text(encoding='utf-8'))
        assert all(isinstance(x,str) for x in native['companions'])
        render_refresh(root,run,crlf)
        result=bridge.publish(root,run)
        assert result['selection_hash']==sha
        actual=canonical.build_contract(root,root/SPEC)
        assert actual==(descriptor,selection,sha)
        manifest=freeze.build_manifest(root,root/SPEC,'execution-plans/example','fixture')
        freeze.validate_manifest(root,manifest)
        assert manifest['selection_hash']==sha and manifest['authorizes']==[]
        assert [(s['path'],s['role']) for s in manifest['sources'][:4]]==[(e['path'],e['role']) for e in selection['role_graph']]
        verify(root);verify(root/run/'native')
    assert all((root/path).read_bytes()==content for path,content in before.items())
    assert canonical.REPOSITORY_ROOT==ROOT
    from scripts.toolchain.canonical_evidence import canonical_bytes
    assert canonical.canonical_bytes is canonical_bytes
    projection={'domain':'jimuyun.canonical-spec-package.selection.v1','payload':selection}
    expected='sha256:'+hashlib.sha256(json.dumps(projection,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    assert sha==expected


@pytest.mark.parametrize('defect',['missing-pointer','stale-pointer','missing-record','stale-record'])
def test_bad_selection_blocks_prepare_and_consumer(tmp_path,defect):
    root=fixture(tmp_path/'root');_,_,sha=initial(root)
    registry=root/'_bmad-output/specs/canonical-spec-package-selections'
    p=registry/'current/SPEC-example.json' if 'pointer' in defect else registry/(sha.replace(':','-')+'.json')
    if defect.startswith('missing'):p.unlink()
    else:p.write_text('{}')
    original=(root/SPEC).read_bytes()
    with pytest.raises((ValueError,OSError)):bridge.prepare(root,SPEC,'logs/bmad-wrappers/reject')
    with pytest.raises((ValueError,OSError)):freeze.build_manifest(root,root/SPEC,'execution-plans/example','fixture')
    assert (root/SPEC).read_bytes()==original
    assert not (root/'logs/bmad-wrappers/reject').exists()


@pytest.mark.parametrize('path',['../outside','/tmp/outside','a/../../outside','C:/outside','a\\b','a//b','a/./b','a:stream','NUL','a/CON.txt','a/trailing.','a\nrole: provenance','a?b','a\x00b'])
def test_unsafe_paths_rejected(tmp_path,path):
    with pytest.raises(ValueError):contained(tmp_path,path)


def test_symlink_rejected_without_following(tmp_path):
    outside=tmp_path/'outside';outside.write_text('sentinel')
    root=tmp_path/'root';root.mkdir();(root/'link').symlink_to(outside)
    with pytest.raises(ValueError):contained(root,'link')
    assert outside.read_text()=='sentinel'


def test_native_order_does_not_change_selection_or_immutable_record(tmp_path):
    root=fixture(tmp_path/'root');descriptor,selection,sha=initial(root)
    record=root/'_bmad-output/specs/canonical-spec-package-selections'/(sha.replace(':','-')+'.json')
    before=record.stat().st_mtime_ns
    run='logs/bmad-wrappers/reorder';bridge.prepare(root,SPEC,run)
    path=root/run/'native'/SPEC
    native,body=bridge.native_descriptor(path.read_text())
    native['companions'].reverse()
    path.write_text('---\n'+'\n'.join(k+': '+json.dumps(v) for k,v in native.items())+'\n---\n'+body,encoding='utf-8')
    assert bridge.publish(root,run)['selection_hash']==sha
    assert canonical.build_contract(root,root/SPEC)==(descriptor,selection,sha)
    assert record.stat().st_mtime_ns==before


def test_selection_symlink_and_root_symlink_rejected(tmp_path):
    root=fixture(tmp_path/'root');_,_,sha=initial(root)
    record=root/'_bmad-output/specs/canonical-spec-package-selections'/(sha.replace(':','-')+'.json')
    outside=tmp_path/'record.json';outside.write_bytes(record.read_bytes());record.unlink();record.symlink_to(outside)
    with pytest.raises(ValueError,match='UNSAFE_PATH'):
        bridge.prepare(root,SPEC,'logs/bmad-wrappers/selection-symlink')
    alias=tmp_path/'alias';alias.symlink_to(root,target_is_directory=True)
    with pytest.raises(ValueError,match='UNSAFE_PATH'):
        bridge.prepare(alias,SPEC,'logs/bmad-wrappers/root-symlink')


@pytest.mark.parametrize('defect',['drop-role','change-category','input-drift','memory-rewrite','adopted-write','native-drift','native-extra','traversal'])
def test_publish_rejects_before_canonical_write(tmp_path,defect):
    root=fixture(tmp_path/'root');initial(root);run='logs/bmad-wrappers/reject'
    bridge.prepare(root,SPEC,run);path=root/run/'native'/SPEC
    if defect=='drop-role':path.write_text(path.read_text().replace('"rules.md", ',''))
    elif defect=='change-category':path.write_text(path.read_text().replace('"rules.md", ', '').replace('sources: [','sources: ["rules.md", '))
    elif defect=='input-drift':(root/'docs/source.md').write_text('changed')
    elif defect=='memory-rewrite':(path.parent/'.memlog.md').write_text('rewritten')
    elif defect=='adopted-write':(path.parent/'adopted.md').write_text('changed')
    elif defect=='native-drift':(root/run/'native/.agents/skills/bmad-spec/SKILL.md').write_text('changed')
    elif defect=='native-extra':(root/run/'native/.agents/skills/bmad-spec/shim.py').write_text('pass')
    else:path.write_text(path.read_text().replace('"rules.md"','"../../../../escape"'))
    before=(root/SPEC).read_bytes()
    with pytest.raises((ValueError,OSError)):bridge.publish(root,run)
    assert (root/SPEC).read_bytes()==before


def test_create_and_explicit_new_role(tmp_path):
    root=fixture(tmp_path/'root');run='logs/bmad-wrappers/create'
    bridge.prepare(root,SPEC,run,'SPEC-example')
    package=root/run/'native'/Path(SPEC).parent
    (package/'SPEC.md').write_text('---\nid: SPEC-example\ncompanions: ["rules.md"]\nsources: []\n---\n# Example\nCAP-1: Created\n')
    (package/'rules.md').write_text('Contract')
    p=command(['uv','run',str(root/run/'native/_bmad/scripts/memlog.py'),'init','--workspace',str(package),'--field','topic=example'],root)
    assert p.returncode==0,p.stderr
    with pytest.raises(ValueError,match='EXPLICIT_ROLE_REQUIRED'):bridge.publish(root,run)
    bridge.publish(root,run,[{'path':str(PurePosixPath(SPEC).parent/'rules.md'),'role':'normative_companion'}])
    assert canonical.build_contract(root,root/SPEC)[0]['companions'][0]['role']=='normative_companion'


def test_missing_runtime_is_not_native_success(tmp_path):
    root=fixture(tmp_path/'root');initial(root)
    (root/'_bmad/scripts/memlog.py').unlink()
    p=command([sys.executable,'-B',str(REPO/'.agents/skills/jimuyun-spec/scripts/bridge.py'),'prepare','--repo-root',str(root),'--spec',SPEC,'--run','logs/bmad-wrappers/missing'],root)
    assert p.returncode==2 and json.loads(p.stdout)['error']=='NATIVE_RUNTIME_MISSING'
    assert not (root/'logs/bmad-wrappers/missing').exists()
