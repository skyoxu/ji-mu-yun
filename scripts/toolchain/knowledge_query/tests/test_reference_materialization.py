"""ADR-0048: preserve provenance without eager expansion of prose citations."""
import hashlib
import json
from pathlib import Path
import subprocess
import pytest
from scripts.toolchain.knowledge_query import adapter


def put(root, name, data):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data, encoding='utf-8')
    return p


@pytest.fixture
def prepared_root(tmp_path, monkeypatch):
    for name, value in zip(adapter._CANONICAL, ({'source_snapshot': {'ref': 'refs/heads/main', 'commit': 'a' * 40, 'sources': []}},
                                              {'policy_revision': 'fixture'}, {})):
        put(tmp_path, name, json.dumps(value))
    seen = []
    def transport(request, root, *paths):
        seen.append(request)
        return {'outcome': 'degraded', 'budget_usage': {'calls': 0}, 'read_set': []}
    monkeypatch.setattr(adapter, 'diagnose', transport)
    return tmp_path, seen


def prepare(root, **changes):
    return adapter.prepare_consumption({'stage': 'vdd-create', 'operation': 'create',
        'task_id': 'reference-materialization-fixture', 'inputs': ['docs/input.md'],
        **changes}, root)


def test_ordinary_references_are_metadata_not_mandatory_excerpts(prepared_root):
    root, seen = prepared_root
    names = [f'scripts/module_{i}.py' for i in range(40)]
    for n in names:
        put(root, n, '# Reference implementation.\n' * 100)
    put(root, 'docs/input.md', '\n'.join('Reference `' + n + '`.' for n in names))
    prepare(root)
    assert seen[0]['scope'] == ['docs/input.md']
    refs = seen[0]['relevant_inputs']['source_references']
    assert {r['path'] for r in refs} == set(names)
    assert all(r['role'] == 'reference-only' and 'excerpt' not in r for r in refs)
    assert all(r['sha256'] == hashlib.sha256((root/r['path']).read_bytes()).hexdigest() for r in refs)


def test_explicit_required_sources_do_not_drop_normative_input(prepared_root):
    root, seen = prepared_root
    put(root, 'docs/input.md', 'Background `scripts/reference.py`.')
    put(root, 'scripts/reference.py', '# Reference only\n')
    put(root, 'docs/mandatory.md', '# Mandatory companion\n')
    prepare(root, scope=['docs/mandatory.md'])
    assert set(seen[0]['scope']) == {'docs/input.md', 'docs/mandatory.md'}
    assert seen[0]['relevant_inputs']['source_references'][0]['path'] == 'scripts/reference.py'


@pytest.mark.parametrize('reference', ['.git/config', 'secrets/.env', '../outside.py', 'C:/private.txt'])
def test_unsafe_reference_still_rejects(prepared_root, reference):
    root, seen = prepared_root
    put(root, 'docs/input.md', f'Reference `{reference}`.')
    with pytest.raises(ValueError, match='consumption_reference_denied'):
        prepare(root)
    assert not seen


def test_absent_proposed_reference_remains_non_source(prepared_root):
    root, seen = prepared_root
    put(root, 'docs/input.md', 'Proposed `scripts/missing.py`.')
    prepare(root)
    assert seen[0]['scope'] == ['docs/input.md']
    assert seen[0].get('relevant_inputs', {}).get('source_references', []) == []


def test_directory_reference_still_rejects(prepared_root):
    root, seen = prepared_root
    (root/'scripts').mkdir()
    put(root, 'docs/input.md', 'Reference `scripts/`.')
    with pytest.raises(ValueError, match='consumption_reference_denied'):
        prepare(root)


def test_reference_limit_is_not_removed(prepared_root):
    root, seen = prepared_root
    names = [f'scripts/module_{i}.py' for i in range(64)]
    for n in names: put(root, n, '# Reference\n')
    put(root, 'docs/input.md', '\n'.join('`'+n+'`' for n in names))
    with pytest.raises(ValueError, match='consumption_scope_exhausted'):
        prepare(root)


def test_reference_hash_and_mentioning_inputs_track_real_change(prepared_root):
    root, seen = prepared_root
    put(root, 'docs/input.md', 'Reference `scripts/dep.py`.')
    put(root, 'docs/second.md', 'Reference `scripts/dep.py`.')
    p=put(root, 'scripts/dep.py', '# First\n')
    prepare(root, inputs=['docs/input.md', 'docs/second.md'])
    first=seen[-1]['relevant_inputs']['source_references'][0]
    assert first['mentioned_in'] == ['docs/input.md', 'docs/second.md']
    p.write_text('# Changed\n', encoding='utf-8')
    prepare(root, inputs=['docs/input.md', 'docs/second.md'])
    assert first['sha256'] != seen[-1]['relevant_inputs']['source_references'][0]['sha256']

# Actual native diagnosis on a real published, isolated repository fixture.
# No production task episode or model request is used by these checks.
from scripts.toolchain.knowledge_query.tests.test_planning_query import (
    published_vdd_base, published_planning, _planning_operation, _s7_write_config,
)


def native_refs(fixture, *, unicode=False):
    root, paths, request = fixture
    name = 'docs/' + ('\u53c2\u8003' if unicode else 'reference') + '.py'
    p=put(root, name, '# Reference evidence\n' * 100)
    return [{'path': name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
             'mentioned_in': ['AGENTS.md'], 'role': 'reference-only'}]


def test_native_metadata_is_charged_without_materializing_reference(published_planning):
    _s7_write_config(published_planning)
    plain=_planning_operation(published_planning)
    refs=native_refs(published_planning, unicode=True)
    out=_planning_operation(published_planning, relevant_inputs={'source_references': refs})
    assert out['outcome'] not in {'blocked', 'budget_exhausted', 'cancelled'}
    assert out['source_references'] == refs
    assert refs[0]['path'] not in {r['path'] for r in out['read_set']}
    assert out['budget_usage']['output_bytes'] == len(adapter._wire(out))
    assert out['budget_usage']['output_bytes'] > plain['budget_usage']['output_bytes']
    assert out['read_set'] and all('excerpt' in r for r in out['read_set'])


def test_native_terminal_reserve_withholds_reference_metadata(published_planning):
    _s7_write_config(published_planning)
    refs=native_refs(published_planning)
    out=_planning_operation(published_planning, relevant_inputs={'source_references': refs},
        narrow_overrides={'max_candidates': 1, 'max_output_bytes': 4096})
    assert out['outcome'] == 'budget_exhausted'
    assert out['diagnostic']['closed'] is True
    assert 'source_references' not in out and not out['read_set']
    assert len(adapter._wire(out)) <= 4096


def test_native_stale_reference_binding_fails_closed(published_planning):
    _s7_write_config(published_planning)
    refs=native_refs(published_planning)
    refs[0]['sha256']='0' * 64
    out=_planning_operation(published_planning, relevant_inputs={'source_references': refs})
    assert out['outcome'] == 'blocked' and out['reason_code'] == 'integrity_failed'
    assert 'source_references' not in out


def test_native_reference_change_changes_content_identity(published_planning):
    _s7_write_config(published_planning)
    refs=native_refs(published_planning)
    first=_planning_operation(published_planning, relevant_inputs={'source_references': refs})
    p=published_planning[0]/refs[0]['path'];p.write_text('# Actually changed\n',encoding='utf-8')
    refs[0]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    second=_planning_operation(published_planning, relevant_inputs={'source_references': refs})
    assert first['outcome'] not in {'blocked','budget_exhausted'}
    assert second['outcome'] not in {'blocked','budget_exhausted'}
    assert first['episode_id'] != second['episode_id']


@pytest.mark.parametrize('state', ['main', 'branch', 'detached'])
@pytest.mark.parametrize('dirty', [False, True])
def test_source_identity_batches_real_git_without_changing_read_set(tmp_path, monkeypatch, state, dirty):
    """ADR-0048: retain actual per-path provenance while using one identity process."""
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args],
                                       stderr=subprocess.PIPE).decode('utf-8').strip()
    git('init', '-b', 'main')
    names = ['docs/source.md', 'docs/space name.md']
    for name in names:
        put(tmp_path, name, '# Source evidence\n' * 200)
    git('add', '--', *names)
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '-qm', 'Fixture source')
    if state == 'branch':
        git('checkout', '-qb', 'topic')
    elif state == 'detached':
        git('checkout', '--detach', '-q')
    if dirty:
        put(tmp_path, names[0], '# Changed source\n')
    # Independently retain the previous two-command identity and path status.
    commit, branch = git('rev-parse', 'HEAD'), git('rev-parse', '--abbrev-ref', 'HEAD')
    statuses = {name: git('status', '--porcelain', '--', name) for name in names}
    expected = []
    for name in sorted(names):
        content = (tmp_path / name).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        excerpt = content[:2048].decode('utf-8', errors='ignore')
        changed = bool(statuses[name])
        identity = {'kind': 'worktree' if changed else ('main' if branch == 'main' else 'branch'),
                    'commit': commit}
        if changed:
            identity.update(base_commit=commit, sha256=digest)
        expected.append({'path': name, 'origin': 'direct-source' if changed else 'locator',
            'sha256': digest, 'read_identity': identity,
            'excerpt_range': {'start_byte': 0, 'end_byte': len(excerpt.encode('utf-8'))},
            'excerpt': excerpt})
    launched = []
    original = subprocess.Popen
    def launch(args, *a, **kw):
        launched.append(args)
        return original(args, *a, **kw)
    monkeypatch.setattr(subprocess, 'Popen', launch)
    actual = adapter._read_sources(tmp_path, [*names, names[0]], 'locator', {'commit': commit})
    assert actual == expected
    assert [args[3:] for args in launched] == [
        ['rev-parse', 'HEAD', '--abbrev-ref', 'HEAD'],
        ['status', '--porcelain=v1', '-z', '--untracked-files=all', '--', *sorted(names)]]
    # A stale index still changes origin without altering source identity.
    stale = adapter._read_sources(tmp_path, names, 'locator', {'commit': '0' * 40})
    assert stale == [{**row, 'origin': 'direct-source'} for row in expected]


@pytest.mark.parametrize('stdout', [
    '', 'a' * 40 + '\n', 'a' * 40 + '\nmain\nextra\n',
    '\n' + 'a' * 40 + '\nmain\n', 'a' * 40 + '\nmain\n\n',
    'HEAD\nmain\n', 'g' * 40 + '\nmain\n', 'a' * 39 + '\nmain\n',
    'a' * 40 + '\n\n', 'a' * 40 + '\n main\n',
])
def test_source_identity_malformed_git_output_fails_closed(tmp_path, monkeypatch, stdout):
    """ADR-0048: never read source evidence after an ambiguous Git identity."""
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout, '')
    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(adapter._Stop) as caught:
        adapter._read_sources(tmp_path, ['missing.md'], 'locator', None)
    assert caught.value.reason == 'unknown_failure'
    assert len(calls) == 1 and calls[0][3:] == ['rev-parse', 'HEAD', '--abbrev-ref', 'HEAD']


@pytest.mark.parametrize('failed_command', ['rev-parse', 'status'])
def test_source_identity_git_failure_remains_closed(tmp_path, monkeypatch, failed_command):
    """ADR-0048: both identity and original per-path status errors remain terminal."""
    put(tmp_path, 'source.md', '# Source\n')
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 1 if args[3] == failed_command else 0,
                                           'a' * 40 + '\nmain\n', 'Git failure')
    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(adapter._Stop) as caught:
        adapter._read_sources(tmp_path, ['source.md'], 'locator', None)
    assert caught.value.reason == 'unknown_failure'
    assert len(calls) == (1 if failed_command == 'rev-parse' else 2)


def test_source_identity_real_unborn_git_head_fails_closed(tmp_path):
    """ADR-0048: a real Git failure must not materialize a read set."""
    subprocess.run(['git', '-C', str(tmp_path), 'init', '-b', 'main'],
                   capture_output=True, check=True)
    put(tmp_path, 'source.md', '# Uncommitted source\n')
    with pytest.raises(adapter._Stop) as caught:
        adapter._read_sources(tmp_path, ['source.md'], 'locator', None)
    assert caught.value.reason == 'unknown_failure'


@pytest.mark.parametrize('state', ['modified', 'renamed', 'untracked', 'space', 'unicode', 'ignored', 'alias'])
def test_batched_status_preserves_real_individual_git_verdicts(tmp_path, state):
    # ADR-0048: retain dirty provenance for unusual actual repository states.
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args], stderr=subprocess.PIPE).decode('utf-8')
    git('init', '-b', 'main')
    names=['clean.md', 'source.md']
    for name in names:
        put(tmp_path,name,'# Committed source\n')
    git('add','--',*names)
    git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Source')
    if state=='modified':
        put(tmp_path,'source.md','# Changed\n')
    elif state=='renamed':
        git('mv','source.md','renamed source.md');names[1]='renamed source.md'
    elif state in ('untracked','space','unicode'):
        name={'untracked':'new/a.md','space':'new/space name.md','unicode':'new/\u6d4b\u8bd5.md'}[state]
        put(tmp_path,name,'# New source\n');names.extend([name,'new/second.md']);put(tmp_path,'new/second.md','# Second new source\n')
    elif state=='ignored':
        put(tmp_path,'.gitignore','ignored.md\n');put(tmp_path,'ignored.md','# Ignored source\n');names.append('ignored.md')
    else:
        names.append('./source.md')
    expected={name for name in names if git('status','--porcelain','--',name).strip()}
    assert adapter._dirty_source_paths(git,names)==expected


@pytest.mark.parametrize('wire', [' M file.md', 'bad\0', 'ZZ file.md\0', 'R  new.md\0', 'R  new.md\0\0'])
def test_batched_status_malformed_protocol_fails_closed(wire):
    with pytest.raises(adapter._Stop) as caught:
        adapter._dirty_source_paths(lambda *args:wire,['file.md'])
    assert caught.value.reason=='unknown_failure'


@pytest.mark.parametrize('state', ['same', 'descendant', 'unrelated', 'tree', 'blob', 'close-error'])
def test_streamed_source_ancestry_retains_real_commit_and_every_hash(tmp_path, monkeypatch, state):
    # ADR-0048: equal hashes prove ancestry only after Git validates object type.
    def git(*args):
        return subprocess.check_output(['git','-C',str(tmp_path),*args],stderr=subprocess.PIPE).decode('utf-8').strip()
    git('init','-b','main');put(tmp_path,'source.md','# Original committed source\n');git('add','source.md')
    git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','First')
    first=git('rev-parse','HEAD');first_hash=hashlib.sha256(subprocess.check_output(['git','-C',str(tmp_path),'cat-file','blob',first+':source.md'])).hexdigest()
    put(tmp_path,'source.md','# Changed committed source\n');git('add','source.md')
    git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Second')
    second=git('rev-parse','HEAD');second_hash=hashlib.sha256(subprocess.check_output(['git','-C',str(tmp_path),'cat-file','blob',second+':source.md'])).hexdigest()
    current=first if state in ('same','close-error') else second
    snapshot=first
    if state=='unrelated':
        git('checkout','--orphan','alternate');git('rm','-rf','--cached','.');put(tmp_path,'other.md','# Other\n');git('add','other.md')
        git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Unrelated');current=git('rev-parse','HEAD')
    elif state in ('tree','blob'):
        current=git('rev-parse','HEAD^{tree}' if state=='tree' else 'HEAD:source.md');snapshot=current
    catalog={'source_snapshot':{'ref':'refs/heads/main','commit':snapshot,'sources':[{'path':'source.md','sha256':first_hash}]}}
    launched=[];original=subprocess.Popen
    def launch(argv,*args,**kwargs):
        launched.append(argv)
        child=original(argv,*args,**kwargs)
        if state=='close-error' and 'cat-file' in argv:
            pipe=child.stdin
            class ClosingFault:
                def write(self,data): return pipe.write(data)
                def flush(self): return pipe.flush()
                def close(self):
                    pipe.close()
                    raise OSError(22,'Fixture closed-pipe fault')
            child.stdin=ClosingFault()
        return child
    monkeypatch.setattr(subprocess,'Popen',launch)
    if state in ('tree','blob','close-error'):
        with pytest.raises(adapter._Stop) as caught:
            adapter._stream_source_hashes(tmp_path,catalog,current,5,None)
        assert caught.value.reason==('unknown_failure' if state=='close-error' else 'integrity_failed')
    else:
        result=adapter._stream_source_hashes(tmp_path,catalog,current,5,None)
        assert result==({} if state=='unrelated' else {'source.md':first_hash if state=='same' else second_hash})
    assert sum('merge-base' in command for command in launched)==(state in ('descendant','unrelated'))
    assert sum('cat-file' in command for command in launched)==(state!='unrelated')
