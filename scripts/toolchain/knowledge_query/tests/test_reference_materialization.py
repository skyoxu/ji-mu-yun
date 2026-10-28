"""ADR-0048: preserve provenance without eager expansion of prose citations."""
import hashlib
import json
from pathlib import Path
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
