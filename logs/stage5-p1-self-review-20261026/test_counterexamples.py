"""ADR-0048: diagnostic counterexamples only, not native RED/Q4 authority."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts/python')]
spec = importlib.util.spec_from_file_location(
    'existing_planning_fixtures',
    ROOT / 'scripts/toolchain/knowledge_query/tests/test_planning_query.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
published_vdd_base = fixtures.published_vdd_base
published_planning = fixtures.published_planning
core = fixtures.core
adapter = fixtures.adapter


@pytest.mark.parametrize('missing', ['catalog', 'policy', 'projection', 'uninstalled'])
def test_public_vdd_missing_component(published_vdd_base, tmp_path, monkeypatch, capsys, missing):
    root = tmp_path / 'caller'
    shutil.copytree(published_vdd_base, root)
    requirement = fixtures._put(root, 'requirements.md', b'# FR-1\nRetain existing source.\n')
    paths = [root / p for p in adapter._CANONICAL]
    if missing == 'uninstalled':
        for path in paths:
            path.unlink()
        shutil.rmtree(root / 'knowledge/indexes')
    else:
        paths[['catalog', 'policy', 'projection'].index(missing)].unlink()
        assert (root / 'knowledge/indexes/current.json').is_file()
    entry_spec = importlib.util.spec_from_file_location('diagnostic_public_vdd', ROOT / 'scripts/vdd/compile_plan.py')
    entry = importlib.util.module_from_spec(entry_spec)
    entry_spec.loader.exec_module(entry)
    monkeypatch.setattr(entry, 'ROOT', root)
    reached = []
    # Keep the real public CLI preparation/admission path. Stop at the semantic
    # delegate; neither a model nor a compiler lifecycle is launched here.
    def stop_at_semantic_delegate(**kwargs):
        reached.append(True)
        return {'status': 'recommendation-only', 'fixture_control': True}
    monkeypatch.setattr(entry, 'compile_plan', stop_at_semantic_delegate)
    monkeypatch.setattr(sys, 'argv', [str(ROOT / 'scripts/vdd/compile_plan.py'),
        '--requirements', str(requirement), '--out-dir', str(root / 'execution-plans/diagnostic')])
    code = entry.main()
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    print('PUBLIC_CALLER_OBSERVATION:' + json.dumps({'missing': missing,
        'exit_code': code, 'semantic_delegate_reached': bool(reached), 'result': result}))
    if missing == 'uninstalled':
        assert code == 0 and reached == [True]
    else:
        assert code != 0 and reached == [], 'Existing publication corruption reached semantic compilation'
        assert 'PLANNING_QUERY_BLOCKED:' in result.get('reason', '')


def _switch_fixture_generation(root, paths, *, restrict_vdd):
    """Construct isolated content-bound input, never a production receipt.

    The native projection owner rebuilds membership and the real consumer
    verifies manifest/artifact bindings. No publication approval is invented or
    borrowed and no real repository generation or pointer is modified.
    """
    import _knowledge_catalog_builder as builder
    pointer_path = root / 'knowledge/indexes/current.json'
    old = json.loads(pointer_path.read_text())
    old_root = root / 'knowledge/indexes/generations' / old['generation_id']
    body = json.loads((old_root / 'manifest.json').read_text())
    body.pop('generation_id')
    body.pop('publication_request', None)
    policy = json.loads(paths[1].read_text())
    selected = next(p for p in policy['policies'] if p['consumer'] == ('vdd' if restrict_vdd else 'bootstrap'))
    if restrict_vdd:
        selected['path_prefixes'] = ['docs/']
        selected['exact_paths'] = ['README.md']
    else:
        selected['max_candidates'] = max(1, selected['max_candidates'] - 1)
    catalog = json.loads(paths[0].read_text())
    projection = builder.build_consumer_projections(catalog, policy)
    updates = {'policy': json.dumps(policy, sort_keys=True).encode(),
               'projections': json.dumps(projection, sort_keys=True).encode()}
    payloads = {}
    for name, item in body['artifacts'].items():
        payload = updates.get(name, (old_root / item['bundle_path']).read_bytes())
        payloads[item['bundle_path']] = payload
        item['sha256'] = 'sha256:' + hashlib.sha256(payload).hexdigest()
    generation = hashlib.sha256(builder.canonical_bytes(body)).hexdigest()
    manifest = {**body, 'generation_id': generation}
    generation_root = root / 'knowledge/indexes/generations' / generation
    for relative, payload in payloads.items():
        fixtures._put(generation_root, relative, payload)
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
    fixtures._put(generation_root, 'manifest.json', manifest_bytes)
    paths[1].write_bytes(updates['policy'])
    paths[2].write_bytes(updates['projections'])
    pointer = {**old, 'generation_id': generation,
               'generation_sha256': 'sha256:' + hashlib.sha256(manifest_bytes).hexdigest()}
    pointer_path.write_text(json.dumps(pointer), encoding='utf-8')
    assert core.verify_current_publication(root, catalog_path=paths[0],
        policy_path=paths[1], projections_path=paths[2])
    return policy, projection, pointer


@pytest.mark.parametrize('change', ['same', 'unrelated-generation', 'permission-revoked'])
def test_current_permissions_before_reuse(published_planning, monkeypatch, change):
    root, paths, request = published_planning
    fixtures._s7_write_config(published_planning)
    record = root / 'execution-plans/example/memlog.md'
    record.write_text('# Isolated diagnostic record\n', encoding='utf-8')
    options = {'record_path': record.relative_to(root).as_posix()}
    real_query = core.query_with_diagnostics
    calls = []
    def traced(*args, **kwargs):
        calls.append(True)
        return real_query(*args, **kwargs)
    monkeypatch.setattr(core, 'query_with_diagnostics', traced)
    first = fixtures._planning_operation(published_planning, **options)
    assert first['outcome'] == 'hit' and first['candidates']
    frozen = copy.deepcopy(first)
    hashes = {r['path']: hashlib.sha256((root / r['path']).read_bytes()).hexdigest()
              for r in first['read_set']}
    if change != 'same':
        policy, projections, pointer = _switch_fixture_generation(root, paths,
            restrict_vdd=change == 'permission-revoked')
        assert pointer['generation_id'] != first['index_identity']['generation_id']
        assert all(hashlib.sha256((root / p).read_bytes()).hexdigest() == h
                   for p, h in hashes.items())
    else:
        policy, projections = (json.loads(p.read_text()) for p in paths[1:])
    second = fixtures._planning_operation(published_planning, **options)
    assert first == frozen
    current_policy = core._policy_for(request, policy)
    catalog = json.loads(paths[0].read_text())
    eligible = core._projection_for(request, catalog, policy, projections)
    modules = {m['source_path']: m for m in catalog['modules']}
    allowed = all(core._policy_allows(modules[c['path']], request['query'], current_policy)
                  and c['module_id'] in eligible for c in second['candidates'])
    print('PERMISSION_REUSE_OBSERVATION:' + json.dumps({'change': change,
        'outcome': second['outcome'], 'reused': second['diagnostic'].get('reused'),
        'permission_checked': second['diagnostic'].get('permission_checked'),
        'current_eligibility_satisfied': allowed, 'query_calls': len(calls)}))
    assert allowed, 'A revoked candidate survived current policy/projection checks'
    if change != 'permission-revoked':
        assert second['diagnostic'].get('reused') is True and len(calls) == 1
        assert second['index_identity'] == first['index_identity']
    else:
        assert not second['diagnostic'].get('reused')
