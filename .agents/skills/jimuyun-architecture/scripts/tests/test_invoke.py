"""ADR-0041/ADR-0062: deterministic invocation checks, not simulated reviewers."""
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
from scripts.toolchain.bmad_native import verify
from scripts.toolchain.bmad_native.testing import fixture,load,command,REPO
invoke=load('architecture_invoke','.agents/skills/jimuyun-architecture/scripts/invoke.py')


def test_policy_is_initial_context_and_native_source_is_exact(tmp_path):
    root=fixture(tmp_path/'space \u4e2d\u6587');(root/'input.md').write_text('Use repository reality; no new technology decision.')
    result=invoke.prepare(root,'logs/bmad-wrappers/architecture',['input.md'])
    prompt=(root/result['invocation']).read_text()
    policy=(REPO/'.agents/skills/jimuyun-architecture/references/reviewer-lifecycle.md').read_text()
    original=(root/'.agents/skills/bmad-architecture/SKILL.md').read_text()
    assert prompt.index(policy)<prompt.index('# Native Skill')
    assert prompt.endswith(original)
    assert 'wait_agent' in policy and 'unknown-agent' in policy and 'timeout' in policy
    assert 'inspect agent state once' in policy and 'entire reviewer set is terminal' in policy
    native=root/'logs/bmad-wrappers/architecture/native'
    p=command(['uv','run',str(native/'_bmad/scripts/resolve_customization.py'),'--skill',str(native/'.agents/skills/bmad-architecture'),'--project-root',str(native),'--key','workflow'],native)
    assert p.returncode==0,p.stderr
    verify(root);verify(native)


def test_update_selects_existing_workspace_and_requires_memory(tmp_path):
    root=fixture(tmp_path/'root');folder=root/'docs/architecture';folder.mkdir(parents=True)
    (folder/'ARCHITECTURE-SPINE.md').write_text('# Existing')
    with pytest.raises(ValueError,match='EXISTING_MEMLOG_REQUIRED'):
        invoke.prepare(root,'logs/bmad-wrappers/reject',['docs/architecture/ARCHITECTURE-SPINE.md'],'update')
    (folder/'.memlog.md').write_text('# Existing memory')
    result=invoke.prepare(root,'logs/bmad-wrappers/update',['docs/architecture/ARCHITECTURE-SPINE.md','docs/architecture/.memlog.md'],'update')
    assert result['doc_workspace'].endswith('/native/docs/architecture')
    assert (root/result['doc_workspace']/'ARCHITECTURE-SPINE.md').read_text()=='# Existing'


def test_relative_root_verifies_and_resource_inputs_block(tmp_path,monkeypatch):
    root=fixture(tmp_path/'root');monkeypatch.chdir(tmp_path)
    verify(Path('root'))
    with pytest.raises(ValueError,match='INPUT_RESOURCE_COLLISION'):
        invoke.prepare(root,'logs/bmad-wrappers/reject',['.agents/skills/bmad-spec/SKILL.md'])
    assert not (root/'logs/bmad-wrappers/reject').exists()


def test_native_altitude_and_purpose_are_forwarded(tmp_path):
    root=fixture(tmp_path/'root');(root/'input.md').write_text('Approved initiative scope.')
    result=invoke.prepare(root,'logs/bmad-wrappers/options',['input.md'],altitude='initiative',purpose='discussion')
    prompt=(root/result['invocation']).read_text()
    assert 'altitude=initiative' in prompt and 'purpose=discussion' in prompt
    assert 'altitude=feature;' not in prompt


@pytest.mark.parametrize('defect',['missing','changed','extra'])
def test_native_integrity_rejects_drift(tmp_path,defect):
    root=fixture(tmp_path/'root');p=root/'.agents/skills/bmad-architecture/SKILL.md'
    if defect=='missing':p.unlink()
    elif defect=='changed':p.write_text('changed')
    else:(p.parent/'shim.py').write_text('pass')
    with pytest.raises(ValueError,match='NATIVE_INSTALLATION_MISSING' if defect=='missing' else 'NATIVE_TREE_DRIFT'):verify(root)
