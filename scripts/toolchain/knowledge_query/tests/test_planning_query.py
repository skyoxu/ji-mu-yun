"""ADR-0048/0041: actual legacy CLI and VDD adapter share read-only preflight.

Fixtures are isolated local Git repositories. Legacy catalog arguments test
the existing CLI compatibility interface; canonical missing-publication denial
is tested separately. No debug bypass flag, publication or BMAD flow is used.
"""
import copy
import hashlib
import io
import importlib.util
import shutil
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts/python')]
import _knowledge_locator_core as core
import knowledge_locator as cli
from scripts.toolchain.knowledge_query import adapter


def _put(root, relative, payload):
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return target


def _git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args],
                                   stderr=subprocess.PIPE, timeout=10).decode().strip()


def _preflight_fixture(root, scenario):
    source = b'# Planning contract\nRead-only repository source.\n'
    _put(root, 'docs/contract.md', source)
    _git(root, 'init', '-b', 'main')
    _git(root, 'add', 'docs/contract.md')
    _git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
         'commit', '-qm', 'Fixture source')
    commit = _git(root, 'rev-parse', 'refs/heads/main')
    source_hash = hashlib.sha256(source).hexdigest()
    catalog = {'authority_ref': 'refs/heads/main',
        'source_snapshot': {'ref': 'refs/heads/main', 'commit': commit,
                            'sources': [{'path': 'docs/contract.md', 'sha256': source_hash}]},
        'entries': [{'path': 'docs/contract.md', 'content': source.decode(),
                     'source_sha256': source_hash, 'status': 'active'}]}
    policies = {'policy_revision': 'fixture-policy', 'policies': [
        {'consumer': 'vdd', 'path_prefixes': ['docs/'], 'statuses': ['active'],
         'max_candidates': 12}]}
    request = {'schema_version': 'jimuyun.knowledge-locator-request.v1',
        'request_id': 'shared-preflight', 'consumer': 'vdd', 'query': 'planning contract',
        'snapshot': {'ref': 'refs/heads/main', 'commit': commit},
        'policy_revision': policies['policy_revision']}
    if scenario == 'no-match':
        request['query'] = 'unmatcheduniquevaluezz7'
    elif scenario == 'snapshot-missing':
        catalog.pop('source_snapshot')
    elif scenario == 'snapshot-mismatch':
        request['snapshot']['commit'] = '0' * 40
    elif scenario == 'policy-missing':
        request['consumer'] = 'not-registered'
    elif scenario == 'stale-main':
        _put(root, 'docs/contract.md', source + b'Changed real main source.\n')
        _git(root, 'add', 'docs/contract.md')
        _git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
             'commit', '-qm', 'Changed fixture main source')
    names = ('catalog.json', 'policies.json', 'projections.json')
    if scenario == 'publication-missing':
        names = ('knowledge/catalogs/repository-knowledge-catalog.v2.json',
                 'knowledge/policies/consumer-policies.v2.json',
                 'knowledge/projections/consumer-projections.v1.json')
    paths = []
    for relative, data in zip(names, (catalog, policies, {})):
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        if scenario == 'malformed-catalog' and relative == names[0]:
            payload = b'{invalid-json'
        paths.append(_put(root, relative, payload))
    return request, paths


def _content_snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}


@pytest.mark.cer_assertion('ASSERT_CA335D988AF5')
@pytest.mark.parametrize('scenario,status,diagnostic', [
    ('matched', 'matched', None),
    ('no-match', 'insufficient_match', None),
    ('snapshot-missing', 'blocked', 'snapshot_missing'),
    ('snapshot-mismatch', 'blocked', 'snapshot_mismatch'),
    ('policy-missing', 'blocked', 'policy_missing'),
    ('stale-main', 'blocked', 'stale'),
    ('publication-missing', 'blocked', 'publication_invalid'),
    ('malformed-catalog', None, None),
], ids=['matched', 'no-match', 'snapshot-missing', 'snapshot-mismatch',
        'policy-missing', 'stale-main', 'publication-missing', 'malformed-catalog'])
def test_contract_ca335d988af5(tmp_path, monkeypatch, capsys, scenario, status, diagnostic):
    request, paths = _preflight_fixture(tmp_path, scenario)
    before = _content_snapshot(tmp_path)
    # Wrap the actual implementation; never replace preflight results with
    # expected data. Both in-process callers must delegate exactly once.
    assert cli.core is core and adapter.core is core
    original = core.query_with_diagnostics
    calls, outputs = [], []
    def traced(*args, **kwargs):
        calls.append((copy.deepcopy(args[0]), kwargs))
        result = original(*args, **kwargs)
        outputs.append(copy.deepcopy(result))
        return result
    monkeypatch.setattr(core, 'query_with_diagnostics', traced)
    arguments = ['--repository-root', str(tmp_path), '--catalog', str(paths[0]),
                 '--policies', str(paths[1]), '--projections', str(paths[2])]
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(request)))
    monkeypatch.setattr(sys, 'argv', ['knowledge_locator.py', *arguments])
    if scenario == 'malformed-catalog':
        with pytest.raises(json.JSONDecodeError):
            cli.main()
        assert capsys.readouterr().out == ''
        with pytest.raises(json.JSONDecodeError):
            adapter.diagnose(request, tmp_path, *paths)
    else:
        code = cli.main()
        legacy = json.loads(capsys.readouterr().out)
        actual = adapter.diagnose(request, tmp_path, *paths)
        assert code == 0 and legacy == actual['result'] == outputs[0]['result']
        assert actual == outputs[1] == outputs[0]
        assert legacy['schema_version'] == 'jimuyun.knowledge-locator-result.v1'
        assert legacy['request_id'] == request['request_id']
        assert legacy['snapshot'] == request['snapshot'] and legacy['status'] == status
        assert bool(legacy['candidates']) == (status == 'matched')
        codes = {item['code'] for item in actual['diagnostics']}
        assert diagnostic in codes if diagnostic else not codes
    assert len(calls) == 2
    assert all(call[0] == request for call in calls)
    assert all(not call[1].get('allow_unpublished_inputs', False)
               and not call[1].get('allow_stale_catalog', False) for call in calls)
    # Run the actual public CLI process too: its exit/wire boundary is not
    # inferred from the Python main() call or from a mocked subprocess result.
    process = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/python/knowledge_locator.py'),
                              *arguments], input=json.dumps(request), text=True, encoding='utf-8',
                             capture_output=True, shell=False, timeout=15)
    if scenario == 'malformed-catalog':
        assert process.returncode != 0 and 'JSONDecodeError' in process.stderr
        assert process.stdout == ''
    else:
        assert process.returncode == 0 and json.loads(process.stdout) == legacy
        assert process.stderr == ''
    assert _content_snapshot(tmp_path) == before


@pytest.fixture(scope='module')
def published_vdd_base(tmp_path_factory):
    """Copy an actual existing generation; never manufacture or republish one."""
    root = tmp_path_factory.mktemp('published-vdd-base')
    relative_paths = [
        'knowledge/snapshots/repository-source-snapshot.v1.json',
        'knowledge/catalogs/repository-knowledge-catalog.v2.json',
        'knowledge/catalogs/repository-knowledge-catalog.v1.json',
        'knowledge/projections/consumer-projections.v1.json',
        'knowledge/policies/consumer-policies.v2.json',
        'knowledge/policies/source-exclusions.v1.json',
        'knowledge/evaluation/repository-knowledge-query-suite.v1.json',
        'knowledge/indexes/current.json', 'knowledge/planning-query.toml',
    ]
    canonical = [ROOT / p for p in relative_paths[1:2] + relative_paths[4:5] + relative_paths[3:4]]
    assert core.verify_current_publication(ROOT, catalog_path=canonical[0],
        policy_path=canonical[1], projections_path=canonical[2])
    pointer = json.loads((ROOT / 'knowledge/indexes/current.json').read_text(encoding='utf-8'))
    generation = Path('knowledge/indexes/generations') / pointer['generation_id']
    manifest = json.loads((ROOT / generation / 'manifest.json').read_text(encoding='utf-8'))
    report = generation / manifest['artifacts']['query_report']['bundle_path']
    assert (ROOT / report).resolve().is_relative_to((ROOT / generation).resolve())
    for relative in [*relative_paths, generation / 'manifest.json', report]:
        _put(root, relative, (ROOT / relative).read_bytes())
    # Borrow real source objects read-only, without checking out the repository
    # or restoring any installed skill. Fixture refs are independent copies.
    subprocess.run(['git', 'clone', '--shared', '--bare', str(ROOT), str(root / '.git')],
                   capture_output=True, check=True, timeout=15)
    _git(root, 'config', '--local', 'core.bare', 'false')
    _git(root, 'symbolic-ref', 'HEAD', 'refs/heads/main')
    # A fresh-publication control must use the actual published source commit,
    # not pretend this older generation is fresh at today's repository main.
    # Only independent fixture refs change; the real repository is read-only.
    _git(root, 'update-ref', 'refs/heads/main', pointer['main_commit'])
    _git(root, 'read-tree', 'refs/heads/main')
    assert _git(root, 'rev-parse', 'refs/heads/main') == pointer['main_commit']
    agents = subprocess.check_output(['git', '-C', str(ROOT), 'show', pointer['main_commit'] + ':AGENTS.md'], timeout=10)
    _put(root, 'AGENTS.md', agents)
    return root


@pytest.mark.cer_assertion('ASSERT_2E09F07252E1')
@pytest.mark.cer_assertion('ASSERT_3F7D90E3D044')
@pytest.mark.parametrize('scenario', [
    'admitted', 'later-main-stale', 'configuration-absent', 'publication-absent', 'pointer-json',
    'manifest-absent', 'manifest-content', 'catalog-domain', 'catalog-visibility',
    'catalog-lifecycle', 'catalog-enforcement', 'catalog-path', 'policy-permission',
    'projection-membership', 'consumer-unknown', 'consumer-bootstrap',
])
def test_contract_2e09f07252e1(published_vdd_base, tmp_path, monkeypatch, scenario):
    import shutil
    import jsonschema
    import _knowledge_catalog_builder as builder

    root = tmp_path / 'published-copy'
    shutil.copytree(published_vdd_base, root)
    catalog_path = root / 'knowledge/catalogs/repository-knowledge-catalog.v2.json'
    policy_path = root / 'knowledge/policies/consumer-policies.v2.json'
    projection_path = root / 'knowledge/projections/consumer-projections.v1.json'
    pointer_path = root / 'knowledge/indexes/current.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    projections = json.loads(projection_path.read_text(encoding='utf-8'))
    pointer = json.loads(pointer_path.read_text(encoding='utf-8'))
    manifest_path = root / 'knowledge/indexes/generations' / pointer['generation_id'] / 'manifest.json'
    request = {'schema_version': 'jimuyun.knowledge-locator-request.v1', 'request_id': 'vdd-admission',
        'consumer': 'vdd', 'query': 'AGENTS.md', 'policy_revision': policy['policy_revision'],
        'snapshot': {key: catalog['source_snapshot'][key] for key in ('ref', 'commit')}}
    schema = json.loads((ROOT / 'knowledge/contracts/knowledge-locator-request.v1.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator(schema).validate(request)
    schema_projection = json.loads((ROOT / 'knowledge/contracts/knowledge-consumer-projections.v1.schema.json').read_text(encoding='utf-8'))
    # Admission consumes the existing published binding, not a new upstream
    # schema approval. The old generation contains repeated module IDs; the
    # native owner consumes membership as a set. Keep that
    # historical finding separate instead of adding a whole-package gate.
    declared_consumers = set(schema_projection['properties']['projections']['items']['properties']['consumer']['enum'])
    assert {p['consumer'] for p in projections['projections']} == {p['consumer'] for p in policy['policies']} == declared_consumers
    assert core.verify_current_publication(root, catalog_path=catalog_path,
        policy_path=policy_path, projections_path=projection_path)
    vdd_policy = next(p for p in policy['policies'] if p['consumer'] == 'vdd')
    vdd_projection = next(p for p in projections['projections'] if p['consumer'] == 'vdd')
    module = next(m for m in catalog['modules'] if m['source_path'] == 'AGENTS.md')
    if scenario == 'admitted':
        # Use the actual unchanged registry, not a copied foreign consumer ACL.
        assert policy == json.loads((ROOT / 'knowledge/policies/consumer-policies.v2.json').read_text(encoding='utf-8'))
        recomputed = builder.build_consumer_projections(catalog, policy)
        assert next(p for p in recomputed['projections'] if p['consumer'] == 'vdd') == vdd_projection
        assert core._projection_for(request, catalog, policy, projections) == set(vdd_projection['eligible_module_ids'])
        assert module['module_id'] in vdd_projection['eligible_module_ids']
        assert module['primary_domain'] == 'toolchain' and module['visibility']['toolchain'] == 'active'
        assert module['lifecycle'] == 'repository-source' and module['enforcement_level'] == 'E1'
        assert builder._module_allowed(module, vdd_policy)
        for change in ({'consumer_ids': ['bootstrap']}, {'lifecycle': 'other-instance'},
                       {'source_path': 'outside-contract.md'},
                       {'visibility': {'workspace': 'active', 'marketplace': 'active'}}):
            restricted = {**module, **change}
            assert not builder._module_allowed(restricted, vdd_policy)
            assert not core._policy_allows(restricted, request['query'], vdd_policy)
    if scenario == 'later-main-stale':
        later_main = _git(ROOT, 'rev-parse', 'refs/heads/main')
        _git(root, 'update-ref', 'refs/heads/main', later_main)
        _git(root, 'read-tree', 'refs/heads/main')
        _put(root, 'AGENTS.md', subprocess.check_output(
            ['git', '-C', str(ROOT), 'show', later_main + ':AGENTS.md'], timeout=10))
    elif scenario == 'configuration-absent':
        (root / 'knowledge/planning-query.toml').unlink()
    elif scenario == 'publication-absent':
        pointer_path.unlink()
    elif scenario == 'pointer-json':
        pointer_path.write_bytes(b'{broken-json')
    elif scenario == 'manifest-absent':
        manifest_path.unlink()
    elif scenario == 'manifest-content':
        manifest_path.write_bytes(manifest_path.read_bytes() + b' ')
    elif scenario.startswith('catalog-'):
        field, value = {
            'catalog-domain': ('primary_domain', 'marketplace'),
            'catalog-visibility': ('visibility', {'toolchain': 'excluded'}),
            'catalog-lifecycle': ('lifecycle', 'other-instance'),
            'catalog-enforcement': ('enforcement_level', 'E2'),
            'catalog-path': ('source_path', 'outside-contract.md'),
        }[scenario]
        module[field] = value
        catalog_path.write_text(json.dumps(catalog), encoding='utf-8')
    elif scenario == 'policy-permission':
        vdd_policy['domains'].append('marketplace')
        policy_path.write_text(json.dumps(policy), encoding='utf-8')
    elif scenario == 'projection-membership':
        vdd_projection['eligible_module_ids'].append('unapproved-module')
        projection_path.write_text(json.dumps(projections), encoding='utf-8')
    elif scenario == 'consumer-unknown':
        request['consumer'] = 'not-registered'
    elif scenario == 'consumer-bootstrap':
        request['consumer'] = 'bootstrap'
    before = _content_snapshot(root)
    observed = []
    original = core.query_with_diagnostics
    def tracked(*args, **kwargs):
        observed.append(copy.deepcopy(args[0]))
        return original(*args, **kwargs)
    monkeypatch.setattr(core, 'query_with_diagnostics', tracked)
    actual = adapter.diagnose({**request, 'stage': 'vdd-create', 'operation': 'create',
        'task_id': 'S1-admission', 'scope': ['AGENTS.md'],
        'narrow_overrides': {'max_candidates': 1}}, root, catalog_path, policy_path, projection_path)
    assert actual['consumer'] == request['consumer'] and not actual.get('authorizes')
    if scenario == 'admitted':
        assert actual['outcome'] == 'hit' and actual['reason_code'] == 'matched'
        assert actual['index_identity']['generation_id'] == pointer['generation_id']
        assert actual['index_identity']['policy_revision'] == policy['policy_revision']
        assert len(actual['candidates']) == 1 and actual['candidates'][0]['path'] == 'AGENTS.md'
        assert any(r['path'] == 'AGENTS.md' and r['sha256'] == hashlib.sha256((root / 'AGENTS.md').read_bytes()).hexdigest()
                   for r in actual['read_set'])
        assert observed == [request]
    elif scenario == 'later-main-stale':
        assert actual['outcome'] == 'degraded' and actual['reason_code'] == 'stale_verified'
        assert observed == [request]
        assert actual['candidates'] == []
        assert actual['read_set'] and all(r['origin'] == 'direct-source' for r in actual['read_set'])
    elif scenario == 'configuration-absent':
        assert actual['outcome'] == 'unavailable' and actual['reason_code'] == 'config_missing'
        assert observed == []
        assert core.verify_current_publication(root, catalog_path=catalog_path,
            policy_path=policy_path, projections_path=projection_path)
    elif scenario in {'consumer-unknown', 'consumer-bootstrap'}:
        assert actual['outcome'] == 'blocked' and actual['reason_code'] == 'invalid_request'
        assert observed == []  # No identity rewrite, fallback or borrowed retry.
    else:
        expected = 'publication_missing' if scenario == 'publication-absent' else 'integrity_failed'
        assert actual['outcome'] == 'blocked' and actual['reason_code'] == expected
        assert observed == [request]  # Reuses real shared preflight exactly once.
        assert not core.verify_current_publication(root, catalog_path=catalog_path,
            policy_path=policy_path, projections_path=projection_path)
    if scenario not in {'admitted', 'later-main-stale'}:
        assert actual['candidates'] == [] and actual['read_set'] == []
    assert _content_snapshot(root) == before


@pytest.mark.cer_assertion('ASSERT_F96ECD3253A2')
@pytest.mark.cer_assertion('ASSERT_31BA1038EB57')
@pytest.mark.cer_assertion('ASSERT_65F3B954FB04')
@pytest.mark.cer_assertion('ASSERT_D64F7E6FDF45')
@pytest.mark.cer_assertion('ASSERT_DCF68B1ABA8F')
@pytest.mark.parametrize('stage,operation,scenario', [
    ('vdd-create', 'create', 'admitted'),
    ('vdd-create', 'create', 'unknown'),
    ('vdd-create', 'create', 'bootstrap'),
    ('vdd-create', 'create', 'quick-dev'),
    ('vdd-create', 'create', 'refactor-acceptance'),
    ('vdd-create', 'create', 'stage-as-consumer'),
    ('vdd-create', 'create', 'policy-absent'),
    ('vdd-create', 'create', 'publication-absent'),
    ('vdd-create', 'create', 'publication-corrupt'),
    ('vdd-repair', 'repair', 'admitted'),
    ('vdd-repair', 'repair', 'unknown'),
    ('vdd-repair', 'repair', 'bootstrap'),
    ('vdd-repair', 'repair', 'quick-dev'),
    ('vdd-repair', 'repair', 'refactor-acceptance'),
    ('vdd-repair', 'repair', 'stage-as-consumer'),
    ('vdd-repair', 'repair', 'policy-absent'),
    ('vdd-repair', 'repair', 'publication-absent'),
    ('vdd-repair', 'repair', 'publication-corrupt'),
    (None, None, 'vdd'),
    (None, None, 'bootstrap'),
    (None, None, 'refactor-acceptance'),
    (None, None, 'quick-dev'),
])
def test_contract_f96ecd3253a2(published_vdd_base, tmp_path, monkeypatch, stage, operation, scenario):
    """Stage is sidecar metadata; actual Locator identity/policy never changes."""
    import shutil
    import jsonschema

    root = tmp_path / 'identity-copy'
    shutil.copytree(published_vdd_base, root)
    paths = [root / relative for relative in (
        'knowledge/catalogs/repository-knowledge-catalog.v2.json',
        'knowledge/policies/consumer-policies.v2.json',
        'knowledge/projections/consumer-projections.v1.json')]
    catalog, policy = [json.loads(p.read_text(encoding='utf-8')) for p in paths[:2]]
    consumer = scenario if stage is None else {
        'unknown': 'not-registered', 'bootstrap': 'bootstrap', 'quick-dev': 'quick-dev',
        'refactor-acceptance': 'refactor-acceptance', 'stage-as-consumer': stage,
    }.get(scenario, 'vdd')
    request = {'schema_version': 'jimuyun.knowledge-locator-request.v1',
        'request_id': 'identity-boundary', 'consumer': consumer, 'query': 'AGENTS.md',
        'snapshot': {k: catalog['source_snapshot'][k] for k in ('ref', 'commit')},
        'policy_revision': policy['policy_revision']}
    schema = json.loads((ROOT / 'knowledge/contracts/knowledge-locator-request.v1.schema.json').read_text(encoding='utf-8'))
    validator = jsonschema.Draft202012Validator(schema)
    assert set(schema['properties']['consumer']['enum']) == {'vdd', 'quick-dev', 'bootstrap', 'refactor-acceptance'}
    if scenario in {'unknown', 'stage-as-consumer'}:
        assert list(validator.iter_errors(request))
    else:
        validator.validate(request)
    if stage is not None:
        assert list(validator.iter_errors({**request, 'stage': stage}))
    if scenario == 'policy-absent':
        policy['policies'] = [p for p in policy['policies'] if p['consumer'] != 'vdd']
        paths[1].write_text(json.dumps(policy), encoding='utf-8')
    elif scenario == 'publication-absent':
        (root / 'knowledge/indexes/current.json').unlink()
    elif scenario == 'publication-corrupt':
        pointer = root / 'knowledge/indexes/current.json'
        pointer.write_bytes(b'{broken-json')
    before = _content_snapshot(root)
    original = core.query_with_diagnostics
    calls, results = [], []
    def traced(*args, **kwargs):
        calls.append((copy.deepcopy(args[0]), copy.deepcopy(kwargs)))
        result = original(*args, **kwargs)
        results.append(copy.deepcopy(result))
        return result
    monkeypatch.setattr(core, 'query_with_diagnostics', traced)
    envelope = request if stage is None else {**request, 'stage': stage,
        'operation': operation, 'task_id': 'S3-identity', 'scope': ['AGENTS.md'],
        'narrow_overrides': {'max_candidates': 1}}
    actual = adapter.diagnose(envelope, root, *paths)
    try:
        if stage is None:
            # Compatibility only: no workflow or live QuickDev caller is enabled.
            assert len(calls) == 1 and calls[0][0] == request
            assert actual == results[0]
            assert 'stage' not in actual and 'consumer' not in actual
            assert actual['result']['request_id'] == request['request_id']
            assert actual['result']['snapshot'] == request['snapshot']
            if scenario == 'quick-dev':
                assert actual['result']['candidates'] == []
            else:
                assert actual['result']['status'] == 'matched'
                assert actual['result']['candidates']
        else:
            assert actual['stage'] == stage and actual['operation'] == operation
            assert actual['consumer'] == consumer and not actual.get('authorizes')
            if scenario in {'unknown', 'bootstrap', 'quick-dev', 'refactor-acceptance', 'stage-as-consumer'}:
                assert actual['outcome'] == 'blocked' and actual['reason_code'] == 'invalid_request'
                assert calls == []  # Rejection must never retry as vdd/bootstrap.
            else:
                assert len(calls) == 1 and calls[0][0] == request
                assert 'stage' not in calls[0][0] and 'operation' not in calls[0][0]
                if scenario == 'admitted':
                    assert actual['outcome'] == 'hit' and actual['reason_code'] == 'matched'
                    assert actual['candidates'] and actual['read_set']
                    assert actual['index_identity']['policy_revision'] == policy['policy_revision']
                else:
                    reason = 'publication_missing' if scenario == 'publication-absent' else 'integrity_failed'
                    assert actual['outcome'] == 'blocked' and actual['reason_code'] == reason
            if scenario != 'admitted':
                assert actual['candidates'] == [] and actual['read_set'] == []
        assert all(not kw.get('allow_unpublished_inputs', False)
                   and not kw.get('allow_stale_catalog', False) for _, kw in calls)
        assert _content_snapshot(root) == before
    except AssertionError:
        print('KQ_F96ECD3253A2')
        raise


def _s7_inputs(published_vdd_base, tmp_path):
    import shutil
    root = tmp_path / 'admission-copy'
    shutil.copytree(published_vdd_base, root)
    paths = [root / p for p in (
        'knowledge/catalogs/repository-knowledge-catalog.v2.json',
        'knowledge/policies/consumer-policies.v2.json',
        'knowledge/projections/consumer-projections.v1.json')]
    catalog, policy, projection = [json.loads(p.read_text(encoding='utf-8')) for p in paths]
    request = {'schema_version': 'jimuyun.knowledge-locator-request.v1',
        'request_id': 'S7-admission', 'consumer': 'vdd', 'query': 'AGENTS.md',
        'snapshot': {k: catalog['source_snapshot'][k] for k in ('ref', 'commit')},
        'policy_revision': policy['policy_revision'], 'stage': 'vdd-create',
        'operation': 'create', 'task_id': 'S7', 'scope': ['AGENTS.md'],
        'narrow_overrides': {'max_candidates': 1}}
    return root, paths, catalog, policy, projection, request


def _s7_query(root, paths, request, monkeypatch):
    before = _content_snapshot(root)
    original, calls = core.query_with_diagnostics, []
    def traced(*args, **kwargs):
        calls.append(copy.deepcopy(args[0]))
        assert not kwargs.get('allow_unpublished_inputs', False)
        assert not kwargs.get('allow_stale_catalog', False)
        return original(*args, **kwargs)
    monkeypatch.setattr(core, 'query_with_diagnostics', traced)
    actual = adapter.diagnose(request, root, *paths)
    assert _content_snapshot(root) == before
    assert actual['consumer'] == request.get('consumer')
    assert not actual.get('authorizes')
    assert len(calls) <= 1 and all(r['consumer'] == 'vdd' for r in calls)
    return actual, calls


@pytest.mark.cer_assertion('ASSERT_2B5B0BA2BE94')
@pytest.mark.cer_assertion('ASSERT_085B1807BD2E')
@pytest.mark.cer_assertion('ASSERT_DCF68B1ABA8F')
@pytest.mark.parametrize('scenario', ['admitted', 'identity-absent', 'identity-unknown',
    'policy-absent', 'publication-absent', 'publication-corrupt', 'configuration-absent'])
def test_contract_2b5b0ba2be94(published_vdd_base, tmp_path, monkeypatch, scenario):
    root, paths, catalog, policy, projection, request = _s7_inputs(published_vdd_base, tmp_path)
    if scenario == 'identity-absent':
        request.pop('consumer')
    elif scenario == 'identity-unknown':
        request['consumer'] = 'not-registered'
    elif scenario == 'policy-absent':
        policy['policies'] = [r for r in policy['policies'] if r['consumer'] != 'vdd']
        paths[1].write_text(json.dumps(policy), encoding='utf-8')
    elif scenario == 'publication-absent':
        (root / 'knowledge/indexes/current.json').unlink()
    elif scenario == 'publication-corrupt':
        (root / 'knowledge/indexes/current.json').write_bytes(b'{invalid')
    elif scenario == 'configuration-absent':
        (root / 'knowledge/planning-query.toml').unlink()
    actual, calls = _s7_query(root, paths, request, monkeypatch)
    if scenario == 'admitted':
        assert actual['outcome'] == 'hit' and actual['reason_code'] == 'matched'
        assert actual['candidates'] and actual['read_set'] and len(calls) == 1
    else:
        expected = {'identity-absent': ('blocked', 'invalid_request', 0),
            'identity-unknown': ('blocked', 'invalid_request', 0),
            'policy-absent': ('blocked', 'integrity_failed', 1),
            'publication-absent': ('blocked', 'publication_missing', 1),
            'publication-corrupt': ('blocked', 'integrity_failed', 1),
            'configuration-absent': ('unavailable', 'config_missing', 0)}[scenario]
        assert (actual['outcome'], actual['reason_code'], len(calls)) == expected
        assert actual['candidates'] == [] and actual['read_set'] == []
        if scenario == 'policy-absent':
            assert 'policy_missing' in {r['code'] for r in actual['diagnostics']}
        if scenario == 'configuration-absent':
            assert core.verify_current_publication(root, catalog_path=paths[0], policy_path=paths[1], projections_path=paths[2])


@pytest.mark.cer_assertion('ASSERT_BD7C42FF441E')
@pytest.mark.cer_assertion('ASSERT_9C72720F8F91')
@pytest.mark.cer_assertion('ASSERT_2D078C89F59A')
@pytest.mark.cer_assertion('ASSERT_DCF68B1ABA8F')
@pytest.mark.parametrize('scenario', ['admitted', 'domain', 'visibility', 'lifecycle',
    'path', 'consumer', 'enforcement-binding', 'hosted-override', 'hosted-config'])
def test_contract_bd7c42ff441e(published_vdd_base, tmp_path, monkeypatch, scenario):
    import _knowledge_catalog_builder as builder
    root, paths, catalog, policy, projection, request = _s7_inputs(published_vdd_base, tmp_path)
    module = next(m for m in catalog['modules'] if m['source_path'] == 'AGENTS.md')
    vdd = next(p for p in policy['policies'] if p['consumer'] == 'vdd')
    assert builder._module_allowed(module, vdd) and core._policy_allows(module, request['query'], vdd)
    changes = {
        'domain': {'primary_domain': 'marketplace', 'visibility': {'marketplace': 'active'}},
        'visibility': {'visibility': {d: 'excluded' for d in module['visibility']}},
        'lifecycle': {'lifecycle': 'hosted-instance'},
        'path': {'source_path': 'hosted/private.md'},
        'consumer': {'consumer_ids': ['bootstrap']},
        'enforcement-binding': {'enforcement_level': 'E2'},
    }
    if scenario in changes:
        module.update(changes[scenario])
        if scenario != 'enforcement-binding':
            assert not builder._module_allowed(module, vdd)
            assert not core._policy_allows(module, request['query'], vdd)
        # Enforcement metadata is protected by the published byte binding;
        # configuration is never a grant or a replacement isolation authority.
        paths[0].write_text(json.dumps(catalog), encoding='utf-8')
    elif scenario == 'hosted-override':
        request['narrow_overrides']['enforcement_level'] = 'E2'
    elif scenario == 'hosted-config':
        config = root / 'knowledge/planning-query.toml'
        config.write_bytes(config.read_bytes() + b'\nenforcement_level = "E2"\n')
    actual, calls = _s7_query(root, paths, request, monkeypatch)
    if scenario == 'admitted':
        assert actual['outcome'] == 'hit' and actual['candidates'] and actual['read_set']
    else:
        assert actual['outcome'] == 'blocked'
        if scenario.startswith('hosted-'):
            assert actual['reason_code'] == 'invalid_config' and calls == []
        else:
            assert actual['reason_code'] == 'integrity_failed' and len(calls) == 1
        assert actual['candidates'] == [] and actual['read_set'] == []


@pytest.mark.cer_assertion('ASSERT_94C2D2FA535D')
@pytest.mark.cer_assertion('ASSERT_9C72720F8F91')
@pytest.mark.cer_assertion('ASSERT_2D078C89F59A')
@pytest.mark.cer_assertion('ASSERT_DCF68B1ABA8F')
@pytest.mark.parametrize('scenario', ['owner-consistent', 'policy-only', 'catalog-consumer',
    'projection-handedit', 'generation-mismatch'])
def test_contract_94c2d2fa535d(published_vdd_base, tmp_path, monkeypatch, scenario):
    import _knowledge_catalog_builder as builder
    root, paths, catalog, policy, projection, request = _s7_inputs(published_vdd_base, tmp_path)
    module = next(m for m in catalog['modules'] if m['source_path'] == 'AGENTS.md')
    # Recompute with the existing owner without writing/publishing a generation.
    assert builder.build_consumer_projections(catalog, policy) == projection
    assert module['consumer_ids'] == sorted(builder._consumer_ids(module['primary_domain']))
    expected_ids = {m['module_id'] for m in catalog['modules'] if
                    builder._module_allowed(m, next(p for p in policy['policies'] if p['consumer'] == 'vdd'))}
    assert core._projection_for(request, catalog, policy, projection) == expected_ids
    if scenario == 'policy-only':
        next(p for p in policy['policies'] if p['consumer'] == 'vdd')['domains'].append('workspace')
        paths[1].write_text(json.dumps(policy), encoding='utf-8')
    elif scenario == 'catalog-consumer':
        module['consumer_ids'] = ['bootstrap']
        paths[0].write_text(json.dumps(catalog), encoding='utf-8')
    elif scenario == 'projection-handedit':
        next(p for p in projection['projections'] if p['consumer'] == 'vdd')['eligible_module_ids'].append('unapproved-module')
        paths[2].write_text(json.dumps(projection), encoding='utf-8')
    elif scenario == 'generation-mismatch':
        pointer = root / 'knowledge/indexes/current.json'
        data = json.loads(pointer.read_text(encoding='utf-8'))
        data['generation_id'] = '0' * 64
        pointer.write_text(json.dumps(data), encoding='utf-8')
    actual, calls = _s7_query(root, paths, request, monkeypatch)
    assert len(calls) == 1
    if scenario == 'owner-consistent':
        assert actual['outcome'] == 'hit' and actual['candidates'] and actual['read_set']
        assert core.verify_current_publication(root, catalog_path=paths[0], policy_path=paths[1], projections_path=paths[2])
    else:
        assert actual['outcome'] == 'blocked' and actual['reason_code'] == 'integrity_failed'
        assert actual['candidates'] == [] and actual['read_set'] == []
        assert not core.verify_current_publication(root, catalog_path=paths[0], policy_path=paths[1], projections_path=paths[2])
        if scenario in {'policy-only', 'catalog-consumer'}:
            with pytest.raises(ValueError, match='consumer_projection_stale'):
                core._projection_for(request, catalog, policy, projection)


@pytest.mark.cer_assertion('ASSERT_F7401102FE99')
@pytest.mark.parametrize('scenario', ['unicode-argv', 'stdout', 'stderr', 'combined',
                                    'timeout', 'cancel', 'windows-evidence'])
def test_contract_f7401102fe99(published_vdd_base, tmp_path, monkeypatch, scenario):
    import threading
    import time
    if scenario == 'windows-evidence':
        _current_windows_runtime_evidence()
        return
    root, paths, _, _, _, request = _s7_inputs(published_vdd_base, tmp_path)
    renamed = root.with_name('repository space \u03c0')
    root.rename(renamed)
    paths = [renamed / p.relative_to(root) for p in paths]
    root = renamed
    before = _content_snapshot(root)
    if scenario == 'timeout':
        request['narrow_overrides']['timeout_seconds'] = 1
    cancelled = threading.Event()
    if scenario == 'cancel':
        request['cancel_event'] = cancelled
    spawn, run = subprocess.Popen, subprocess.run
    children, invocation = [], []
    consumed = {'stdout': 0, 'stderr': 0}
    class ObservedPipe:
        def __init__(self, pipe, label):
            self.pipe, self.label = pipe, label
        def __getattr__(self, name):
            return getattr(self.pipe, name)
        def read(self, *args, **kwargs):
            data = self.pipe.read(*args, **kwargs)
            consumed[self.label] += len(data.encode('utf-8') if isinstance(data, str) else data)
            return data
    def observed_run(argv, *args, **kwargs):
        if list(argv) == ['git', '-C', str(root), 'rev-parse', 'refs/heads/main']:
            invocation.append({'argv': list(argv), 'shell': kwargs.get('shell', False), 'encoding': kwargs.get('encoding')})
        return run(argv, *args, **kwargs)
    def launch(argv, *args, **kwargs):
        selected = list(argv) == ['git', '-C', str(root), 'rev-parse', 'refs/heads/main']
        if not selected or scenario == 'unicode-argv':
            return spawn(argv, *args, **kwargs)
        if scenario in {'timeout', 'cancel'}:
            script = 'import time; time.sleep(2.2)'
        else:
            script = 'import sys; '
            script += ('sys.stdout.write(chr(960)*35000); ' if scenario in {'stdout', 'combined'}
                       else 'sys.stdout.write(' + repr(request['snapshot']['commit']+'\n') + '); ')
            script += 'sys.stdout.flush(); '
            if scenario in {'stderr', 'combined'}:
                script += 'sys.stderr.write("y"*70000); sys.stderr.flush()'
        child = spawn([sys.executable, '-c', script], *args, **kwargs)
        children.append(child)
        for label in ('stdout', 'stderr'):
            pipe = getattr(child, label)
            if pipe is not None:
                setattr(child, label, ObservedPipe(pipe, label))
        if scenario == 'cancel':
            cancelled.set()
        return child
    monkeypatch.setattr(subprocess, 'run', observed_run)
    monkeypatch.setattr(subprocess, 'Popen', launch)
    start = time.monotonic()
    try:
        actual = adapter.diagnose(request, root, *paths)
        elapsed = time.monotonic() - start
        assert invocation and all(i['shell'] is False and i['encoding'] == 'utf-8' for i in invocation)
        if scenario == 'unicode-argv':
            assert actual['outcome'] == 'hit' and actual['reason_code'] == 'matched'
            assert actual['candidates'] and actual['read_set']
        else:
            assert len(children) == 1 and children[0].poll() is not None
            assert actual['candidates'] == [] and actual['read_set'] == []
            assert actual['diagnostic']['incomplete'] is True
            if scenario == 'cancel':
                assert elapsed < 1.75 and actual['outcome'] == actual['reason_code'] == 'cancelled'
            elif scenario == 'timeout':
                assert elapsed < 1.75 and (actual['outcome'], actual['reason_code']) == ('unavailable', 'timeout')
            else:
                assert sum(consumed.values()) > 0
                assert consumed['stdout'] <= 65537 and consumed['stderr'] <= 65537
                assert sum(consumed.values()) <= 131074
                assert actual['outcome'] in {'blocked', 'budget_exhausted'}
        assert not actual.get('authorizes') and _content_snapshot(root) == before
    except AssertionError:
        print('FAILURE_ID:KQ_F7401102FE99')
        raise
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)


@pytest.mark.cer_assertion('ASSERT_850A2D68C126')
@pytest.mark.cer_assertion('ASSERT_B4DDDFEB665F')
@pytest.mark.parametrize('scenario', ['hit', 'publication-missing', 'publication-corrupt'])
def test_contract_850a2d68c126(published_vdd_base, tmp_path, monkeypatch, scenario):
    root, paths, _, _, _, request = _s7_inputs(published_vdd_base, tmp_path)
    history = root / 'execution-plans/existing/memlog.md'
    history.parent.mkdir(parents=True)
    history.write_bytes(b'# Immutable prior caller history\nExisting decision.\n')
    if scenario == 'publication-missing':
        (root / 'knowledge/indexes/current.json').unlink()
    elif scenario == 'publication-corrupt':
        (root / 'knowledge/indexes/current.json').write_bytes(b'{invalid')
    before = _content_snapshot(root)
    refs = _git(root, 'show-ref')
    head = _git(root, 'rev-parse', 'HEAD')
    branch = _git(root, 'symbolic-ref', 'HEAD')
    spawn, commands = subprocess.Popen, []
    def trace(argv, *args, **kwargs):
        if isinstance(argv, (list, tuple)) and list(argv[:3]) == ['git', '-C', str(root)]:
            commands.append(list(argv))
        return spawn(argv, *args, **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', trace)
    actual = adapter.diagnose(request, root, *paths)
    assert commands
    assert all(c[3] in {'rev-parse', 'merge-base', 'cat-file', 'status'} for c in commands)
    assert _git(root, 'show-ref') == refs
    assert _git(root, 'rev-parse', 'HEAD') == head
    assert _git(root, 'symbolic-ref', 'HEAD') == branch
    assert _content_snapshot(root) == before
    assert history.read_bytes() == b'# Immutable prior caller history\nExisting decision.\n'
    assert not actual.get('authorizes')
    if scenario == 'hit':
        assert actual['outcome'] == 'hit' and actual['read_set']
    else:
        reason = 'publication_missing' if scenario == 'publication-missing' else 'integrity_failed'
        assert actual['outcome'] == 'blocked' and actual['reason_code'] == reason
        assert actual['candidates'] == [] and actual['read_set'] == []


# Scoped S12: retained adapter tests, rebound to authentic VDD inputs.
# Historical author source is never imported and no BMAD workflow is restored.
diagnose = adapter.diagnose


def _s12_raw_query(request, *args, **kwargs):
    # Give controlled raw producer samples the same explicit one-row bound as
    # the tested adapter call, without truncating or changing returned data.
    kwargs.setdefault('max_candidates', 1)
    return core.query_with_diagnostics(request, *args, **kwargs)


@pytest.fixture
def published_planning(published_vdd_base, tmp_path):
    root, paths, catalog, policy, _, envelope = _s7_inputs(published_vdd_base, tmp_path)
    pointer = json.loads((root/'knowledge/indexes/current.json').read_text(encoding='utf-8'))
    generation = Path('knowledge/indexes/generations') / pointer['generation_id']
    manifest = json.loads((ROOT/generation/'manifest.json').read_text(encoding='utf-8'))
    # Keep real frozen layer originals for the switch/data-attribution check.
    for metadata in manifest['artifacts'].values():
        relative = generation / metadata['bundle_path']
        _put(root, relative, (ROOT/relative).read_bytes())
    vdd = next(p for p in policy['policies'] if p['consumer']=='vdd')
    needed = {'AGENTS.md', 'README.md'}
    for query in ('AGENTS.md', 'repository knowledge authority'):
        rows = core.locate({'consumer':'vdd', 'query':query}, catalog, policy=vdd,
            max_candidates=20, eligible_module_ids=core._projection_for(envelope,catalog,policy,
                json.loads(paths[2].read_text(encoding='utf-8'))))['candidates']
        needed.update(r['path'] for r in rows)
    for path in sorted(needed):
        data = subprocess.check_output(['git','-C',str(ROOT),'show',pointer['main_commit']+':'+path],timeout=10)
        _put(root, path, data)
    (root/'execution-plans/example').mkdir(parents=True, exist_ok=True)
    (root/'knowledge/planning-query.toml').unlink()
    request = {k:v for k,v in envelope.items() if k in {
        'schema_version','request_id','consumer','query','snapshot','policy_revision','stage'}}
    assert request['consumer']=='vdd' and request['stage']=='vdd-create'
    return root, paths, request


def _s12_restore_existing_generation(root):
    # Exact historical pointer, not a newly manufactured publication request.
    pointer_bytes = (ROOT/'logs/quick-dev-s12-20261025/existing-generation-B-pointer.json').read_bytes()
    pointer = json.loads(pointer_bytes)
    generation = Path('knowledge/indexes/generations')/pointer['generation_id']
    manifest_bytes = (ROOT/generation/'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    _put(root,generation/'manifest.json',manifest_bytes)
    for metadata in manifest['artifacts'].values():
        relative = generation/metadata['bundle_path']
        data = (ROOT/relative).read_bytes()
        assert 'sha256:'+hashlib.sha256(data).hexdigest()==metadata['sha256']
        _put(root,relative,data)
        if metadata.get('repository_path'):
            _put(root,metadata['repository_path'],data)
    _put(root,'knowledge/indexes/current.json',pointer_bytes)
    assert core.verify_current_publication(root, catalog_path=root/'knowledge/catalogs/repository-knowledge-catalog.v2.json',
        policy_path=root/'knowledge/policies/consumer-policies.v2.json',
        projections_path=root/'knowledge/projections/consumer-projections.v1.json')
    return pointer


def _s7_generation_switch(fixture):
    from unittest.mock import patch
    root,paths,request=fixture
    _s7_write_config(fixture)
    before=json.loads((root/'knowledge/indexes/current.json').read_text())
    original=adapter._stream_source_hashes
    original_locate=core.locate
    switched,consumed=[],[]
    def locate(req,catalog,*args,**kwargs):
        consumed.append(copy.deepcopy(catalog))
        return original_locate(req,catalog,*args,**kwargs)
    def switch(*args,**kwargs):
        hashes=original(*args,**kwargs)
        switched.append(_s12_restore_existing_generation(root))
        return hashes
    with patch.object(adapter,'_stream_source_hashes',switch),patch.object(core,'locate',locate):
        output=_planning_operation(fixture)
    assert len(switched)==1 and switched[0]['generation_id']!=before['generation_id']
    if output.get('result',output).get('status',output.get('outcome'))=='blocked':
        assert not output.get('read_set') and not output.get('adopted')
    else:
        assert len(consumed)==1
        assert consumed[0]['source_snapshot']['commit']==before['main_commit']
        frozen_manifest=json.loads((root/'knowledge/indexes/generations'/before['generation_id']/'manifest.json').read_text())
        frozen=(root/'knowledge/indexes/generations'/before['generation_id']/frozen_manifest['artifacts']['catalog_v2']['bundle_path']).read_bytes()
        assert json.loads(frozen)==consumed[0]
        hashes={m['source_path']:m['source_sha256'] for m in consumed[0]['modules']}
        assert all(c['source_sha256']==hashes[c['path']] for c in output.get('result',output)['candidates'])
        assert before['generation_id'] in json.dumps(output['index_identity'])
        assert switched[0]['generation_id'] not in json.dumps(output['index_identity'])


def _planning_operation(fixture, **options):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    root, paths, base = fixture
    request = {**base, 'operation': 'create', 'task_id': 'bounded-planning',
               'scope': ['AGENTS.md'], 'relevant_inputs': {}, 'narrow_overrides': {'max_candidates':1}, **options}
    return diagnose(request, root, *paths)


def _s7_schema(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    output = _planning_operation(fixture)
    required = {'schema', 'episode_id', 'stage', 'operation', 'consumer', 'outcome',
                'reason_code', 'index_identity', 'candidates', 'read_set', 'budget_usage', 'diagnostic'}
    assert required <= output.keys()
    assert output['schema'] == 'planning-query.v1'
    assert json.loads(json.dumps(output, ensure_ascii=False)) == output


def _s7_missing_config(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    root, _, _ = fixture
    path = root / 'knowledge/planning-query.toml'
    if path.exists():
        raise RuntimeError('S7 fixture requires an absent query config')
    if scenario == 'malformed':
        path.write_text('[query\n', encoding='utf-8')
    elif scenario == 'empty':
        path.write_bytes(b'')
    output = _planning_operation(fixture)
    expected = ('unavailable', 'config_missing') if scenario == 'absent' else ('blocked', 'invalid_config')
    assert (output.get('outcome'), output.get('reason_code')) == expected
    assert output.get('candidates') == [] and output.get('read_set') == []


def _s7_write_config(fixture, suffix='', **settings):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    root, _, _ = fixture
    settings = {'enabled': True, 'stages': ['prd', 'spec', 'architecture', 'vdd-create', 'vdd-repair'],
                'max_candidates': 12, 'max_output_bytes': 65536, 'max_calls': 3,
                'timeout_seconds': 30, **settings}
    path = root / 'knowledge/planning-query.toml'
    path.write_text('[query]\n' + '\n'.join(f'{k} = {json.dumps(v)}' for k, v in settings.items()) + '\n' + suffix,
                    encoding='utf-8')
    return path


def _s7_invalid_config(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    # Each invalid value is a separate collected case, with otherwise valid config.
    field, value = scenario
    path = _s7_write_config(fixture)
    if field == 'malformed':
        path.write_text('[query\n', encoding='utf-8')
    elif field == 'unknown':
        _s7_write_config(fixture, unrecognized_field=True)
    else:
        _s7_write_config(fixture, **{field: value})
    output = _planning_operation(fixture)
    assert (output.get('outcome'), output.get('reason_code')) == ('blocked', 'invalid_config')
    assert output.get('candidates') == [] and output.get('read_set') == []
    assert output.get('diagnostic', {}).get('incomplete') is True


def _s7_config(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    _s7_write_config(fixture)
    if scenario == 'repository-disabled':
        _s7_write_config(fixture, enabled=False)
        output = _planning_operation(fixture)
        assert (output.get('outcome'), output.get('reason_code')) == ('unavailable', 'disabled')
        assert not output.get('candidates') and not output.get('adopted')
        return
    # AD-4's explicit narrowing input belongs to the planning request envelope,
    # not the underlying Locator request. Its production owner is this slice's
    # existing adapter; no new export or pre-RED implementation is necessary.
    overrides = {
        'personal-narrowing': {'max_candidates': 1, 'max_calls': 1},
        'personal-disable': {'enabled': False},
        'remove-required-stage': {'stages': ['prd']},
        'over-hard-cap': {'max_candidates': 21},
        'arbitrary-consumer': {'consumer': 'bootstrap'},
        'free-command': {'command': ['arbitrary-program']},
        'path-expansion': {'scope': ['../outside-private.txt']},
    }
    if scenario in overrides:
        output = _planning_operation(fixture, narrow_overrides=overrides[scenario])
        assert not output.get('adopted') and not output.get('authorizes')
        if scenario != 'personal-narrowing':
            assert (output.get('outcome'), output.get('reason_code')) == ('blocked', 'invalid_config')
            assert not output.get('candidates') and not output.get('read_set')
            return
        effective = output.get('diagnostic', {}).get('effective_config', {})
        assert effective.get('max_candidates') == 1
        assert effective.get('max_calls') == 1
        assert effective.get('enabled') is True
        assert set(effective.get('stages', [])) == {'prd', 'spec', 'architecture', 'vdd-create', 'vdd-repair'}
        assert 'narrow_overrides' in json.dumps(effective.get('origins', {}))
        return
    if scenario not in {'defaults', 'legal-boundary', 'narrow-team'}:
        raise ValueError('Unknown author scenario: ' + scenario)
    values = {'max_candidates':20,'max_calls':5,'timeout_seconds':60,'max_output_bytes':131072} if scenario=='legal-boundary' else ({'max_candidates':1,'max_calls':1,'timeout_seconds':1,'max_output_bytes':4096} if scenario=='narrow-team' else {})
    _s7_write_config(fixture, **values)
    output=_planning_operation(fixture,narrow_overrides={})
    effective=output.get('diagnostic',{}).get('effective_config',{})
    assert effective, 'Actual tracked query configuration is not consumed or reported'
    assert effective.get('max_candidates') <= values.get('max_candidates',12)
    for field, default in [('max_calls',3),('max_output_bytes',65536),('timeout_seconds',30)]:
        assert effective.get(field)==values.get(field,default)
    assert effective.get('origins') and effective.get('consumer')=='vdd'


def _s7_hit_read(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    import hashlib
    _s7_write_config(fixture)
    root, _, _ = fixture
    output = _planning_operation(fixture)
    assert (output.get('outcome'), output.get('reason_code')) == ('hit', 'matched')
    assert output.get('read_set') and output.get('candidates')
    for read in output['read_set']:
        assert {'origin', 'path', 'read_identity', 'sha256', 'excerpt_range'} <= read.keys()
        assert read['origin'] == 'locator'
        assert read['sha256'].removeprefix('sha256:') == hashlib.sha256((root/read['path']).read_bytes()).hexdigest()
    assert not output.get('adopted') and not output.get('authorizes')


def _s7_identity(fixture, scenario='snapshot'):
    __tracebackhide__ = True
    import subprocess, hashlib
    root, paths, request = fixture
    _s7_write_config(fixture)
    def git(*args):
        return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.PIPE,text=True).strip()
    def commit(message):
        git('add','AGENTS.md');git('-c','user.name=Isolated Test','-c','user.email=test@example.invalid','commit','-m',message)
        return git('rev-parse','HEAD')
    old=request['snapshot']['commit']
    pointer=json.loads((root/'knowledge/indexes/current.json').read_text())
    baseline=_planning_operation(fixture)
    original=baseline.get('result',baseline)['candidates']
    expected_commit=old; expected_kind='snapshot'
    if scenario in {'main','branch','worktree'}:
        (root/'AGENTS.md').write_text('# Repository knowledge authority\nMain version B.\n',encoding='utf-8')
        expected_commit=commit('Relevant allowed source change');expected_kind='main'
    if scenario in {'branch','worktree'}:
        git('checkout','-b','fixture-branch')
        (root/'AGENTS.md').write_text('# Repository knowledge authority\nBranch version C.\n',encoding='utf-8')
        expected_commit=commit('Relevant branch source change');expected_kind='branch'
    if scenario=='worktree':
        (root/'AGENTS.md').write_text('# Repository knowledge authority\nUncommitted version D.\n',encoding='utf-8')
        expected_kind='worktree'
    if scenario=='unauthorized-change':
        # A derived candidate hash tamper is not an attributable source commit
        # or formal publication. Distinguish it from actual allowed Git changes.
        catalog=json.loads(paths[0].read_text())
        target=next(x for x in catalog['modules'] if x.get('source_path')=='AGENTS.md')
        target['source_sha256']='sha256:'+'0'*64
        paths[0].write_text(json.dumps(catalog),encoding='utf-8')
        output=_planning_operation(fixture)
        result=output.get('result',output)
        assert result.get('status',output.get('outcome'))=='blocked'
        assert not result.get('candidates') and not output.get('read_set') and not output.get('adopted')
        assert 'integrity_failed' in json.dumps(output)
        return
    source=(root/'AGENTS.md').read_bytes();digest=hashlib.sha256(source).hexdigest()
    output=_planning_operation(fixture)
    identity=output.get('index_identity')
    assert isinstance(identity,dict)
    encoded=json.dumps(identity)
    assert old in encoded and pointer['generation_id'] in encoded and request['policy_revision'] in encoded
    if expected_commit!=old:assert expected_commit not in encoded, 'Current source cannot relabel published index'
    if scenario=='candidate-preservation':
        delivered=output.get('result',output)['candidates']
        assert [(x['path'],x['source_sha256']) for x in delivered]==[(x['path'],x['source_sha256']) for x in original]
        return
    # The actual repository checkout supplies the requested current source;
    # no new export or fabricated change_reason/authorization key is introduced.
    reads=[x for x in output.get('read_set',[]) if x.get('path')=='AGENTS.md']
    assert reads, 'The actual allowed source must be checked, not merely listed as an index candidate'
    for read in reads:
        assert read['sha256'].removeprefix('sha256:')==digest
        binding=json.dumps(read['read_identity'])
        assert expected_commit in binding
        if expected_kind=='worktree':
            assert 'worktree' in binding and digest in binding
        elif expected_kind=='branch':assert 'branch' in binding
        elif expected_kind=='main':assert 'main' in binding
        else:assert 'snapshot' in binding or 'main' in binding
        assert read.get('excerpt_range') and read.get('origin') in {'locator','direct-source'}
        if scenario in {'main','branch','worktree'}:assert read['origin']=='direct-source'
    assert not output.get('adopted') and not output.get('authorizes')


def _s7_zero(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    _s7_required_gate(fixture, False)
    _s7_write_config(fixture)
    output = _planning_operation(fixture, query='zzzz-unique-no-match-123456789')
    assert (output.get('outcome'), output.get('reason_code')) == ('no_match', 'empty')
    assert output.get('candidates') == []
    diagnostic = output.get('diagnostic', {})
    assert diagnostic.get('raw_status') == 'insufficient_match'
    assert diagnostic.get('requires_source_check') is True
    assert not diagnostic.get('capability_absent') and not diagnostic.get('required_gate_satisfied')
    reads=output.get('read_set',[])
    assert reads and all(r.get('origin')=='direct-source' for r in reads), 'Targeted source check must have actual verified sources, not only a flag'


def _s7_blocked(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    _s7_write_config(fixture)
    output = _planning_operation(fixture, consumer='unknown', stage=None)
    result = output.get('result', output)
    assert result.get('status', output.get('outcome')) == 'blocked'
    assert result.get('candidates') == []
    assert not output.get('read_set') and not output.get('adopted') and not output.get('authorizes')
    assert output.get('diagnostics') or output.get('diagnostic'), 'Denied identity must have a diagnostic'
    if 'outcome' in output:
        assert output.get('reason_code') in ['invalid_request', 'policy_denied']
        assert output.get('diagnostic', {}).get('incomplete') is True


def _s7_paths(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    _s7_write_config(fixture)
    root, _, _ = fixture
    outside = root.parent/'outside-private.txt'
    outside.write_text('DENIED_CONTENT_SENTINEL', encoding='utf-8')
    (root/'escape.md').symlink_to(outside)
    paths = {'traversal': '../outside-private.txt', 'absolute': str(outside),
             'symlink': 'escape.md', 'missing': 'missing.md'}
    output = _planning_operation(fixture, scope=[paths[scenario]])
    assert output.get('outcome') == 'blocked'
    assert output.get('reason_code') in ['invalid_request', 'path_denied']
    assert output.get('read_set') == [] and output.get('candidates') == []
    assert 'DENIED_CONTENT_SENTINEL' not in json.dumps(output)


def _s7_duplicate(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    _s7_recovery(fixture, 'same')


def _s7_recovery(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    import hashlib
    _s7_write_config(fixture)
    root, _, _ = fixture
    record = root/'execution-plans/example/memlog.md'
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text('# Existing caller record\nHistorical failure remains incomplete.\n', encoding='utf-8')
    original_record = record.read_bytes()
    options = {'record_path': record.relative_to(root).as_posix()}
    first = _planning_operation(fixture, **options)
    frozen = json.dumps(first, sort_keys=True)
    assert first.get('episode_id'), 'A real planning call must identify its bounded episode'
    first_record = record.read_bytes()
    assert first_record.startswith(original_record) and len(first_record) > len(original_record)
    if scenario == 'unrelated-file':
        (root/'unindexed-unrelated.txt').write_text('Unrelated bytes', encoding='utf-8')
    elif scenario == 'related-source':
        source=root/'AGENTS.md'; source.write_bytes(source.read_bytes()+b'\nRelevant change\n')
    elif scenario == 'task-change':
        options['task_id'] = 'different-bounded-planning-intent'
    elif scenario != 'same':
        raise ValueError('Unknown recovery scenario: ' + scenario)
    second = _planning_operation(fixture, **options)
    assert json.dumps(first, sort_keys=True) == frozen
    assert not second.get('authorizes') and not second.get('adopted')
    facts={'scenario':scenario, 'scope_equivalence':[['AGENTS.md','README.md'],['README.md','AGENTS.md']],
        'source_sha256':hashlib.sha256((root/'AGENTS.md').read_bytes()).hexdigest()}
    print('S7_RECOVERY_SETUP:' + json.dumps(facts))
    assert record.read_bytes().startswith(first_record), 'Recovery must append, never rewrite old failure or result bytes'
    if scenario in {'same', 'unrelated-file'}:
        assert second.get('episode_id') == first['episode_id']
        assert second.get('index_identity') == first.get('index_identity')
        assert second.get('budget_usage', {}).get('calls') == first.get('budget_usage', {}).get('calls')
        assert second.get('diagnostic', {}).get('reused') is True
        assert second.get('diagnostic', {}).get('permission_checked') is True
    else:
        assert second.get('episode_id') != first['episode_id']
        assert second.get('diagnostic', {}).get('predecessor_episode_id') == first['episode_id']
        assert second.get('diagnostic', {}).get('refresh_reason') in {'task_changed', 'source_changed'}
        if scenario == 'related-source':
            reads = [r for r in second.get('read_set', []) if r.get('path') == 'AGENTS.md']
            assert reads and all(r.get('sha256', '').removeprefix('sha256:') == facts['source_sha256'] for r in reads)
    assert 'Historical failure remains incomplete.' in record.read_text(encoding='utf-8')


def _s7_budget(fixture, scenario='candidate-cap'):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    from unittest.mock import patch
    _s7_write_config(fixture, max_candidates=1, max_calls=1)
    root, paths, request = fixture
    original = core.query_with_diagnostics
    baseline = original({k:v for k,v in request.items() if k != 'stage'}, root,
        catalog_path=paths[0], policies_path=paths[1], projections_path=paths[2], max_candidates=2)
    if len(baseline['result']['candidates']) < 2:
        raise RuntimeError('AUTHOR_FIXTURE: candidate cap needs at least two real published matches')
    record = root/'execution-plans/example/memlog.md'
    record.write_text('# Existing caller record\n', encoding='utf-8')
    if scenario == 'publication-failure':
        (root/'knowledge/indexes/current.json').write_bytes(b'{invalid-publication')
    calls=[]
    def traced(*args, **kwargs):
        result=original(*args, **kwargs); calls.append({'kwargs': {k:str(v) for k,v in kwargs.items()},
            'rows': len(result['result']['candidates'])}); return result
    with patch.object(core, 'query_with_diagnostics', traced):
        output = _planning_operation(fixture, record_path=record.relative_to(root).as_posix())
    if len(calls) != 1:
        raise RuntimeError('AUTHOR_BINDING: query boundary was not called exactly once')
    print('S7_ACTUAL_CANDIDATE_CALL:' + json.dumps(calls))
    if scenario == 'candidate-cap':
        result = output.get('result', output)
        assert len(result['candidates']) <= 1, 'Actual delivered rows exceed the tracked one-candidate setting'
        assert calls[0]['rows'] <= 1, 'Locator call must use the remaining allowance, not truncate after unbounded retrieval'
    else:
        assert not output.get('adopted') and not output.get('authorizes')
        assert output.get('budget_usage', {}).get('calls') == 1, 'The actual first attempt must be charged, including a failed one'
        if scenario == 'publication-failure':
            assert (output.get('outcome'), output.get('reason_code')) == ('blocked', 'integrity_failed')
        elif scenario not in {'valid', 'episode-counter', 'episode-counters'}:
            raise ValueError('Unknown budget scenario: ' + scenario)
        if scenario in {'episode-counter', 'episode-counters'}:
            previous = record.read_bytes()
            with patch.object(core, 'query_with_diagnostics', traced):
                second = _planning_operation(fixture, record_path=record.relative_to(root).as_posix(),
                                             supplement_reason='missing_basis')
            assert len(calls) == 1, 'The exhausted episode must not invoke another Locator attempt'
            assert second.get('episode_id') == output.get('episode_id')
            assert (second.get('outcome'), second.get('reason_code')) == ('budget_exhausted', 'budget_exhausted')
            assert second.get('budget_usage', {}).get('calls') == 1
            assert second.get('diagnostic', {}).get('closed') is True
            assert record.read_bytes().startswith(previous)


def _s7_output(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    _s7_write_config(fixture, max_output_bytes=4096)
    output = _planning_operation(fixture)
    assert (output.get('outcome'), output.get('reason_code')) == ('budget_exhausted', 'budget_exhausted')
    assert output.get('candidates') == [] and output.get('read_set') == []
    encoded = json.dumps(output, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    assert len(encoded) <= 4096
    assert len(output.get('diagnostic', {}).get('summary', '').encode('utf-8')) <= 512
    assert isinstance(output.get('budget_usage', {}).get('output_bytes'), int)
    assert output['budget_usage']['output_bytes'] <= 4096
    # Exact equality requires the actual delivery writer bytes, not guessed JSON separators.
    assert output.get('diagnostic', {}).get('incomplete') is True
    assert output.get('diagnostic', {}).get('closed') is True


def _s7_no_mutation(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    import subprocess
    from unittest.mock import patch
    _s7_write_config(fixture)
    root, _, _ = fixture
    if scenario == 'publication-failure':
        (root/'knowledge/indexes/current.json').write_bytes(b'{invalid-publication')
    # Audit/memlog appends are allowed. Only immutable publication/history/Git
    # authority is frozen here; this does not ban all repository file writes.
    def protected():
        prefixes = ['knowledge/indexes', '.git/refs', '.git/objects', 'execution-plans']
        files = [p for prefix in prefixes for p in (root/prefix).rglob('*') if p.is_file()]
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in files}
    before = protected()
    commands = []
    original = subprocess.Popen
    def traced(argv, *args, **kwargs):
        commands.append(argv)
        return original(argv, *args, **kwargs)
    with patch.object(subprocess, 'Popen', traced):
        output = _planning_operation(fixture)
    assert before == protected()
    for argv in commands:
        assert not isinstance(argv, str), 'Query subprocesses must use argv'
        names = [str(x) for x in argv]
        assert not any(x in names for x in ['fetch', 'checkout', 'reset', 'pip', 'install'])
        assert not any('publish_knowledge' in x or 'workflow_host.py' in x for x in names)
        assert '--allow-unpublished-inputs' not in names and '--allow-stale-catalog' not in names
    assert not output.get('authorizes') and not output.get('adopted')


def _s7_cancel(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    import subprocess
    import threading
    import time
    from unittest.mock import patch
    _s7_write_config(fixture)
    root, paths, request = fixture
    raw = _s12_raw_query({k: v for k, v in request.items() if k != 'stage'},
        root, catalog_path=paths[0], policies_path=paths[1], projections_path=paths[2])
    cancelled = threading.Event()
    record = root/'execution-plans/example/memlog.md'
    record.write_text('# Existing caller record\n', encoding='utf-8')
    spawn = subprocess.Popen
    children = []
    def controlled_launch(argv, *args, **kwargs):
        # Fault injection returns a real OS process, never a fabricated receipt
        # or completed-process object. Only the actual reached query process is
        # delayed; the adapter must own and terminate it after the signal.
        names = [str(x) for x in argv] if not isinstance(argv, str) else []
        if names[:3] == ['git', '-C', str(root)] and 'rev-parse' in names:
            payload = request['snapshot']['commit']
        elif any('knowledge_locator.py' in x or 'knowledge_query/adapter.py' in x for x in names):
            payload = json.dumps(raw['result'])
        else:
            return spawn(argv, *args, **kwargs)
        child = spawn([sys.executable, '-c', 'import time; time.sleep(2.2); print(' + repr(payload) + ')'],
                      *args, **kwargs)
        children.append(child)
        cancelled.set()
        return child
    start = time.monotonic()
    try:
        with patch.object(subprocess, 'Popen', controlled_launch):
            output = _planning_operation(fixture, cancel_event=cancelled,
                                         record_path=record.relative_to(root).as_posix())
        elapsed = time.monotonic() - start
        assert len(children) == 1, 'Cancellation must target the real owned query child without retry'
        assert elapsed < 1.75, 'Cancellation did not terminate the running query promptly'
        assert children[0].poll() is not None, 'Cancelled query left its owned child alive'
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
    assert not output.get('adopted') and not output.get('authorizes')
    assert (output.get('outcome'), output.get('reason_code')) == ('cancelled', 'cancelled')
    assert output.get('diagnostic', {}).get('incomplete') is True
    assert not output.get('candidates') and not output.get('read_set')
    assert output.get('budget_usage', {}).get('calls') == 1
    assert 'cancelled' in record.read_text(encoding='utf-8')


def _s7_audit(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    _s7_write_config(fixture)
    root, _, _ = fixture
    existing=root/'execution-plans/example/memlog.md'
    existing.write_text('# Existing record\nHistorical decision retained.\n', encoding='utf-8')
    old=existing.read_bytes()
    prior_files = {p.relative_to(existing.parent).as_posix(): p.read_bytes()
                   for p in existing.parent.rglob('*') if p.is_file() and p != existing}
    output = _planning_operation(fixture, record_path=existing.relative_to(root).as_posix())
    assert existing.read_bytes().startswith(old), 'Existing history must not be rewritten'
    assert not output.get('adopted') and not output.get('normative') and not output.get('authorizes')
    appended = existing.read_bytes()[len(old):].decode('utf-8')
    assert appended, 'Actual query status must reach the caller-selected existing record'
    assert fixture[2]['query'] in appended and fixture[2]['consumer'] in appended
    assert output.get('episode_id') and output['episode_id'] in appended
    assert output.get('outcome') and output['outcome'] in appended
    assert output.get('reason_code') and output['reason_code'] in appended
    assert output.get('read_set'), 'Successful record must bind actual verified source reads'
    for read in output['read_set']:
        assert read['path'] in appended and read['sha256'] in appended
    # S5 owns real native accept/reject decisions. This check only establishes
    # that its input is attributable and can be appended without a second log.
    after_files = {p.relative_to(existing.parent).as_posix(): p.read_bytes()
                   for p in existing.parent.rglob('*') if p.is_file() and p != existing}
    assert after_files == prior_files, 'Query must preserve other plan files without adding a mandatory separate record'


def _s7_transport(fixture, scenario):
    __tracebackhide__ = True
    import os
    import subprocess
    from unittest.mock import patch
    _s7_write_config(fixture)
    root, _, request = fixture
    if scenario == 'json-parser':
        # Core is an in-process structured-output boundary. An invalid value
        # must not be trusted; this is not a claim that Git emits query JSON.
        escaped = None
        with patch.object(core, 'query_with_diagnostics', return_value='{"status":') as boundary:
            try:
                output = _planning_operation(fixture)
            except (TypeError, ValueError, AttributeError) as error:
                escaped = type(error).__name__
        assert boundary.called
        assert escaped is None, 'Malformed producer output escaped the fail-closed adapter: ' + str(escaped)
        assert (output.get('outcome'), output.get('reason_code')) == ('blocked', 'unknown_failure')
        assert not output.get('read_set') and not output.get('candidates')
        return
    if scenario not in {'stdout', 'stderr', 'combined'}:
        raise ValueError('Unknown transport scenario: ' + scenario)
    spawn, os_read = subprocess.Popen, os.read
    children, fds, consumed = [], {}, {'stdout': 0, 'stderr': 0}
    class ObservedPipe:
        def __init__(self, pipe, label):
            self.pipe, self.label = pipe, label
        def __getattr__(self, name):
            return getattr(self.pipe, name)
        def read(self, *args, **kwargs):
            data = self.pipe.read(*args, **kwargs)
            consumed[self.label] += len(data.encode('utf-8') if isinstance(data, str) else data)
            return data
        def read1(self, *args, **kwargs):
            data = self.pipe.read1(*args, **kwargs)
            consumed[self.label] += len(data)
            return data
    def observed_read(fd, count):
        data = os_read(fd, count)
        if fd in fds:
            consumed[fds[fd]] += len(data)
        return data
    def controlled_launch(argv, *args, **kwargs):
        names = [str(x) for x in argv] if not isinstance(argv, str) else []
        selected = (names[:3] == ['git', '-C', str(root)] and 'rev-parse' in names)
        selected = selected or any('knowledge_locator.py' in x or 'knowledge_query/adapter.py' in x for x in names)
        if not selected:
            return spawn(argv, *args, **kwargs)
        script = ('import sys; '
            + ('sys.stdout.write(chr(960)*35000); ' if scenario in {'stdout', 'combined'}
               else 'sys.stdout.write(' + repr(request['snapshot']['commit']+'\n') + '); ')
            + ('sys.stderr.write("y"*70000); ' if scenario in {'stderr', 'combined'} else '')
            + 'sys.stdout.flush(); sys.stderr.flush()')
        child = spawn([sys.executable, '-c', script], *args, **kwargs)
        children.append(child)
        for label in ('stdout', 'stderr'):
            pipe = getattr(child, label)
            if pipe is not None:
                fds[pipe.fileno()] = label
                setattr(child, label, ObservedPipe(pipe, label))
        return child
    try:
        with patch.object(subprocess, 'Popen', controlled_launch), patch.object(os, 'read', observed_read):
            output = _planning_operation(fixture)
        assert len(children) == 1, 'One bounded attempt must stop the overflowing owned child without retry'
        assert consumed['stdout'] + consumed['stderr'] > 0, 'The real process read boundary was not observed'
        # One extra detection byte is admissible; it must never become a stored
        # or parsed payload. Count bytes pulled from actual pipes, not a fake
        # CompletedProcess constructed after unbounded buffering in the test.
        assert consumed['stdout'] <= 65537
        assert consumed['stderr'] <= 65537
        assert sum(consumed.values()) <= 131074
        assert children[0].poll() is not None
        assert output.get('outcome') in {'blocked', 'budget_exhausted'}
        assert not output.get('candidates') and not output.get('read_set')
        assert not output.get('adopted') and not output.get('authorizes')
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)


def _s7_timeout(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    import subprocess, sys, time
    from unittest.mock import patch
    _s7_write_config(fixture, timeout_seconds=1)
    root, _, request = fixture
    original = subprocess.run
    reached = []
    def delayed(argv, *args, **kwargs):
        if list(argv) == ['git', '-C', str(root), 'rev-parse', 'refs/heads/main']:
            reached.append({'argv': argv, 'timeout': kwargs.get('timeout')})
            return original([sys.executable, '-c',
                'import time; time.sleep(2.2); print(' + repr(request['snapshot']['commit']) + ')'], *args, **kwargs)
        return original(argv, *args, **kwargs)
    start = time.monotonic()
    with patch.object(subprocess, 'run', delayed):
        try:
            output = _planning_operation(fixture)
        except subprocess.TimeoutExpired:
            output = None
    elapsed = time.monotonic() - start
    if not reached:
        raise RuntimeError('AUTHOR_BINDING: actual core Git rev-parse deadline boundary not reached')
    print('S7_ACTUAL_DEADLINE:' + json.dumps({'calls': reached, 'elapsed': elapsed}))
    # Finite child, production timeout kwargs unchanged; tolerance is for CI
    # scheduling, not a replacement test timeout or a claim of Windows coverage.
    assert elapsed < 1.75, 'Configured one-second query deadline was not enforced on a real query dependency'
    assert output is not None, 'A dependency timeout must be classified, not escape as an exception'
    assert (output.get('outcome'), output.get('reason_code')) == ('unavailable', 'timeout')
    assert output.get('diagnostic', {}).get('incomplete') is True


def _s7_unknown(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    from copy import deepcopy
    from unittest.mock import patch
    _s7_write_config(fixture)
    root, paths, request = fixture
    response = _s12_raw_query({k: v for k, v in request.items() if k != 'stage'},
        root, catalog_path=paths[0], policies_path=paths[1], projections_path=paths[2])
    controlled = deepcopy(response)
    controlled['result']['candidates'] = []
    if scenario == 'unknown-empty':
        controlled['result']['status'] = 'unrecognized_status'
    elif scenario == 'blocked-empty':
        controlled['result']['status'] = 'blocked'
        controlled['diagnostics'] = []  # No reliable availability diagnosis.
    elif scenario == 'matched-empty':
        controlled['result']['status'] = 'matched'
    with patch.object(core, 'query_with_diagnostics', return_value=controlled) as boundary:
        output = _planning_operation(fixture)
    if not boundary.called:
        raise RuntimeError('S7 injection did not reach the shared production boundary')
    assert (output.get('outcome'), output.get('reason_code')) == ('blocked', 'unknown_failure')
    assert output.get('candidates') == [] and output.get('read_set') == []
    assert output.get('diagnostic', {}).get('incomplete') is True


def _s7_direct(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    import hashlib
    _s7_write_config(fixture, enabled=False)
    root, paths, request = fixture
    path=root/'scripts/toolchain/knowledge_query/local-evidence.py'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('# Current source outside publication\n', encoding='utf-8')
    raw=_s12_raw_query({k:v for k,v in request.items() if k!='stage'},root,
        catalog_path=paths[0],policies_path=paths[1],projections_path=paths[2])
    relative=path.relative_to(root).as_posix()
    if any(c['path']==relative for c in raw['result']['candidates']):
        raise RuntimeError('AUTHOR_FIXTURE: direct source unexpectedly appeared in Locator candidates')
    output=_planning_operation(fixture, scope=[relative])
    print('S7_DIRECT_SOURCE_SETUP:'+json.dumps({'path':relative,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'absent_from_candidates':True}))
    assert not output.get('adopted') and not output.get('authorizes')
    assert (output.get('outcome'), output.get('reason_code')) == ('unavailable', 'disabled')
    assert not output.get('candidates'), 'Direct inspection must not invent a Locator hit'
    reads = [r for r in output.get('read_set', []) if r.get('path') == relative]
    assert reads, 'Authorized in-root scope must be independently read on diagnosed unavailability'
    assert all(r.get('origin') == 'direct-source' and r.get('read_identity') for r in reads)
    assert all(r.get('sha256', '').removeprefix('sha256:') == hashlib.sha256(path.read_bytes()).hexdigest() for r in reads)
    _s7_required_gate(fixture, False)


def _s7_degraded(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    # Fault injection is at the existing shared Locator boundary, not an unused
    # copied CLI. It tests the real adapter classification, not a fake adapter.
    from copy import deepcopy
    from unittest.mock import patch
    _s7_write_config(fixture)
    root, paths, request = fixture
    raw_request = {k: v for k, v in request.items() if k != 'stage'}
    response = _s12_raw_query(raw_request, root, catalog_path=paths[0],
                                          policies_path=paths[1], projections_path=paths[2])
    if not response['result']['candidates']:
        raise RuntimeError('S7 fixture requires a trusted nonempty result')
    controlled = deepcopy(response)
    result = controlled['result']
    expected = {'insufficient': 'insufficient_match', 'low-confidence': 'low_confidence',
                'missing-confidence': 'low_confidence'}[scenario]
    if scenario == 'insufficient':
        result['status'] = 'insufficient_match'
    else:
        for candidate in result['candidates']:
            evidence = candidate.setdefault('rank_evidence', {})
            if scenario == 'missing-confidence':
                evidence.pop('confidence', None)
            else:
                evidence['confidence'] = 'low'
    # Hashes, publication bindings and candidate paths remain authentic.
    with patch.object(core, 'query_with_diagnostics', return_value=controlled) as boundary:
        output = _planning_operation(fixture)
    if not boundary.called:
        raise RuntimeError('S7 injection did not reach the shared production boundary')
    assert (output.get('outcome'), output.get('reason_code')) == ('degraded', expected)
    assert not output.get('adopted')
    reads=output.get('read_set', [])
    assert reads, 'Degraded fallback must record actual separately verified source bytes'
    for read in reads:
        assert read.get('origin')=='direct-source'
        assert read.get('sha256','').removeprefix('sha256:')==__import__('hashlib').sha256((root/read['path']).read_bytes()).hexdigest()
    assert output.get('diagnostic', {}).get('requires_source_check') is True


def _s7_integrity_guard(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    _s7_write_config(fixture)
    root, paths, _ = fixture
    if scenario == 'pointer':
        (root/'knowledge/indexes/current.json').write_bytes(b'{DENIED_CONTENT_SENTINEL')
    else:
        index = {'catalog': 0, 'policy': 1, 'projection': 2}[scenario]
        paths[index].write_bytes(paths[index].read_bytes() + b' ')
    output = _planning_operation(fixture, query='zzzz-no-match')
    # The legacy and typed adapter paths must both preserve rejection. This
    # guard must not manufacture a new RED merely for an absent envelope field.
    result = output.get('result', output)
    assert result.get('status', output.get('outcome')) == 'blocked'
    assert result.get('candidates') == []
    assert not output.get('read_set') and not output.get('adopted') and not output.get('authorizes')
    assert output.get('diagnostics') or output.get('diagnostic'), 'Rejection must report a cause'
    assert 'DENIED_CONTENT_SENTINEL' not in json.dumps(output)


def _s7_cancel_prior_error(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    _s7_write_config(fixture)
    root, _, _=fixture
    import threading
    record = root/'execution-plans/example/memlog.md'
    record.write_text('# Existing caller record\n', encoding='utf-8')
    options = {'record_path': record.relative_to(root).as_posix()}
    (root/'knowledge/indexes/current.json').write_bytes(b'{invalid-publication')
    first = _planning_operation(fixture, **options)
    assert first.get('result',first).get('status',first.get('outcome')) == 'blocked'
    assert 'integrity_failed' in json.dumps(first)
    frozen=json.dumps(first,sort_keys=True)
    # The caller records a real earlier producer failure. This is test input,
    # not an invented workflow receipt or a claimed native adoption decision.
    with record.open('a', encoding='utf-8') as stream:
        stream.write(frozen + '\n')
    first_record = record.read_bytes()
    cancelled = threading.Event()
    cancelled.set()
    second=_planning_operation(fixture, cancel_event=cancelled, **options)
    assert json.dumps(first,sort_keys=True)==frozen
    assert not second.get('adopted') and not second.get('authorizes')
    assert second.get('result', second).get('status', second.get('outcome')) == 'blocked'
    assert 'integrity_failed' in json.dumps(second)
    assert record.read_bytes().startswith(first_record)
    assert 'integrity_failed' in record.read_text(encoding='utf-8')


def _s7_history_preservation(fixture, scenario):
    """Observe the preservation guard without requiring a new episode schema."""
    root, _, _ = fixture
    _s7_write_config(fixture)
    record = root/'execution-plans/example/memlog.md'
    record.write_text('# Historical fixture\nCancelled work remains incomplete.\n', encoding='utf-8')
    (root/'knowledge/indexes/current.json').write_bytes(b'{invalid-publication')
    options = {'record_path': record.relative_to(root).as_posix()}
    first = _planning_operation(fixture, **options)
    assert first.get('result', first).get('status', first.get('outcome')) == 'blocked'
    with record.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(first, sort_keys=True) + '\n')
    prior = record.read_bytes()
    immutable = json.dumps(first, sort_keys=True)
    if scenario == 'unrelated-file':
        (root/'unrelated.txt').write_text('Unrelated fixture change', encoding='utf-8')
    elif scenario == 'related-source':
        source = root/'AGENTS.md'
        source.write_bytes(source.read_bytes() + b'\nRelevant fixture change\n')
    elif scenario == 'task-change':
        options['task_id'] = 'another-task'
    elif scenario != 'same':
        raise ValueError('Unknown history scenario: ' + scenario)
    second = _planning_operation(fixture, **options)
    assert record.read_bytes().startswith(prior)
    assert json.dumps(first, sort_keys=True) == immutable
    assert not second.get('adopted') and not second.get('authorizes')
    assert second.get('result', second).get('status', second.get('outcome')) == 'blocked'


def _s7_closed_pairs(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    from copy import deepcopy
    from unittest.mock import patch
    _s7_required_gate(fixture, scenario!='empty')
    _s7_write_config(fixture)
    root, paths, request = fixture
    raw = _s12_raw_query({k: v for k, v in request.items() if k != 'stage'},
        root, catalog_path=paths[0], policies_path=paths[1], projections_path=paths[2])
    if not raw['result']['candidates']:
        raise RuntimeError('Closed-pair fixture requires a trusted nonempty result')
    controlled = deepcopy(raw)
    expected = {'matched': ('hit','matched'), 'empty': ('no_match','empty'),
                'insufficient': ('degraded','insufficient_match'),
                'unknown': ('blocked','unknown_failure')}
    if scenario in {'empty','insufficient'}:
        controlled['result']['status'] = 'insufficient_match'
    if scenario in {'empty','unknown'}:
        controlled['result']['candidates'] = []
    if scenario == 'unknown':
        controlled['result']['status'] = 'unknown'
    with patch.object(core, 'query_with_diagnostics', return_value=controlled) as boundary:
        output = _planning_operation(fixture)
    if not boundary.called:
        raise RuntimeError('Closed-pair injection did not reach the production boundary')
    assert (output.get('outcome'), output.get('reason_code')) == expected[scenario]
    if scenario == 'unknown':
        assert output.get('candidates') == [] and output.get('read_set') == []
    elif scenario in {'empty', 'insufficient'}:
        assert output.get('diagnostic', {}).get('requires_source_check') is True
        assert not output.get('diagnostic', {}).get('required_gate_satisfied')


def _s7_snapshot_truth_guard(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    import subprocess
    _s7_write_config(fixture)
    root, _, request = fixture
    old = request['snapshot']['commit']
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Isolated Test', '-c',
                    'user.email=test@example.invalid', 'commit', '--allow-empty', '-m', 'Unrelated head'],
                   check=True, capture_output=True)
    head = subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    if old == head:
        raise RuntimeError('Snapshot-truth fixture requires distinct old and current commits')
    if scenario == 'unconfirmed':
        (root/'knowledge/indexes/current.json').unlink()
    output = _planning_operation(fixture)
    if scenario == 'unconfirmed':
        assert output.get('index_identity') is None
        assert not output.get('adopted') and not output.get('authorizes')
        result = output.get('result', output)
        assert result.get('status', output.get('outcome')) == 'blocked'
    elif 'index_identity' in output:
        identity = output['index_identity']
        assert old in json.dumps(identity) and head not in json.dumps(identity)
    else:
        # Legacy snapshot fields describe the bound source, not a new publication.
        assert output['result']['snapshot']['commit'] == old
        assert output['result']['snapshot']['commit'] != head
    assert not output.get('adopted') and not output.get('authorizes')


def _s7_failure_priority(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    import subprocess
    _s7_write_config(fixture)
    root, paths, request = fixture
    options={'query':'zzzz-unique-no-match-123456789'}
    if scenario in {'integrity','stale-integrity'}:
        (root/'knowledge/indexes/current.json').write_bytes(b'{DENIED_CONTENT_SENTINEL')
    if scenario=='publication-missing':
        (root/'knowledge/indexes/current.json').unlink()
    if scenario in {'policy','stale-policy'}:
        options['policy_revision']='not-an-authorized-policy'
    if scenario=='snapshot':
        options['snapshot']={'ref':'refs/heads/main','commit':'0'*40}
    if scenario.startswith('stale'):
        (root/'AGENTS.md').write_text('# Changed actual main source\n', encoding='utf-8')
        subprocess.run(['git','-C',str(root),'add','AGENTS.md'],check=True,capture_output=True)
        subprocess.run(['git','-C',str(root),'-c','user.name=Isolated Test','-c','user.email=test@example.invalid','commit','-m','Actual stale source'],check=True,capture_output=True)
    output=_planning_operation(fixture,**options)
    result=output.get('result',output)
    assert result.get('status',output.get('outcome')) in ({'blocked','degraded'} if scenario=='stale' else {'blocked'}), 'Higher priority must not become no_match from empty candidates'
    assert not result.get('candidates') and not output.get('adopted') and not output.get('authorizes')
    assert 'DENIED_CONTENT_SENTINEL' not in json.dumps(output)
    # New adapter representation is an explicit oracle, separate from the
    # existing blocking guard above. Preserve diagnostics, not just a new label.
    assert output.get('outcome') in ({'blocked','degraded'} if scenario=='stale' else {'blocked'})
    assert output.get('diagnostic',{}).get('raw_status')=='blocked'
    assert output.get('diagnostic',{}).get('evidence_refs')
    if scenario=='stale':
        assert (output.get('outcome'),output.get('reason_code'))==('degraded','stale_verified')
    if scenario=='publication-missing':
        assert output.get('reason_code')=='publication_missing'


def _s7_process_cause(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    import subprocess,sys
    from unittest.mock import patch
    _s7_write_config(fixture)
    root, paths, request=fixture
    if scenario=='unicode-argv':
        renamed=root.with_name('repository space '+chr(0x03c0));root.rename(renamed)
        paths=[renamed/p.relative_to(root) for p in paths];root=renamed
        fixture=(root,paths,request)
    original=subprocess.run; calls=[]
    def observed(argv,*args,**kwargs):
        if list(argv)==['git','-C',str(root),'rev-parse','refs/heads/main']:
            calls.append({'argv':argv,'shell':kwargs.get('shell',False),'encoding':kwargs.get('encoding')})
            if scenario=='nonzero':
                return original([sys.executable,'-c','import sys; sys.stderr.write("unclassified dependency failure"); sys.exit(7)'],*args,**kwargs)
        return original(argv,*args,**kwargs)
    with patch.object(subprocess,'run',observed):
        output=_planning_operation(fixture)
    if not calls: raise RuntimeError('AUTHOR_BINDING: no actual Git process observed')
    print('S7_ACTUAL_PROCESS:'+json.dumps(calls,ensure_ascii=False))
    assert all(c['shell'] is False and c['encoding']=='utf-8' for c in calls)
    if scenario=='unicode-argv':
        assert output.get('result',output).get('status',output.get('outcome')) in {'matched','hit'}
    else:
        result=output.get('result',output)
        assert result.get('status',output.get('outcome'))=='blocked'
        assert not result.get('candidates') and not output.get('adopted')
        assert output.get('outcome')=='blocked' and output.get('reason_code')=='unknown_failure', 'Unknown child exit is not positive timeout/unavailability evidence'


def _s7_delivery_boundary(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    _s7_write_config(fixture)
    import io
    import hashlib
    from datetime import datetime
    root, _, _ = fixture
    source = root/'docs/utf8-evidence.md'
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(('Verified ' + chr(0x03c0) + ' source.\n') * 5000, encoding='utf-8')
    scope = [source.relative_to(root).as_posix()]
    record = root/'execution-plans/example/memlog.md'
    record.write_text('# Existing caller record\n', encoding='utf-8')
    delivered = io.BytesIO()
    output=_planning_operation(fixture, scope=scope, record_path=record.relative_to(root).as_posix(), delivery_stream=delivered)
    assert not output.get('adopted') and not output.get('authorizes')
    print('S7_UTF8_EXPECTATION:'+json.dumps({'characters':len(chr(0x03c0)*3),'encoded_bytes':len((chr(0x03c0)*3).encode('utf-8'))}))
    raw = delivered.getvalue()
    assert raw, 'The real delivery writer did not deliver any bytes'
    assert json.loads(raw.decode('utf-8')) == output
    assert output.get('budget_usage', {}).get('output_bytes') == len(raw)
    timestamp = output.get('diagnostic', {}).get('recorded_at')
    assert timestamp and datetime.fromisoformat(timestamp.replace('Z', '+00:00')).utcoffset().total_seconds() == 0
    assert output.get('read_set')
    reads = [r for r in output['read_set'] if r.get('path') == scope[0]]
    assert reads
    for read in reads:
        assert read.get('excerpt_range') and isinstance(read.get('excerpt'), str)
        assert read['sha256'].removeprefix('sha256:') == hashlib.sha256(source.read_bytes()).hexdigest()
        assert read['excerpt'] and read['excerpt'] in source.read_text(encoding='utf-8')
        assert len(read['excerpt'].encode('utf-8')) > len(read['excerpt'])
        assert len(read['excerpt'].encode('utf-8')) < len(source.read_bytes())
    next_delivery = io.BytesIO()
    second = _planning_operation(fixture, scope=scope, record_path=record.relative_to(root).as_posix(), delivery_stream=next_delivery)
    second_raw = next_delivery.getvalue()
    assert second_raw and json.loads(second_raw) == second
    assert second['episode_id'] == output['episode_id']
    assert second['budget_usage']['output_bytes'] == len(raw) + len(second_raw)
    assert second['budget_usage']['output_bytes'] <= 65536


def _s7_exit_zero_blocked(fixture):
    __tracebackhide__ = True
    import subprocess
    from unittest.mock import patch
    root,paths,request=fixture
    _s7_write_config(fixture)
    denied={**request,'policy_revision':'not-authorized'}
    raw=_s12_raw_query({k:v for k,v in denied.items() if k!='stage'},root,
        catalog_path=paths[0],policies_path=paths[1],projections_path=paths[2])
    assert raw['result']['status']=='blocked' and raw['result']['candidates']==[]
    # CLI exit is an observed process fact, never fabricated in an adapter result.
    proc=subprocess.run([sys.executable,str(ROOT/'scripts/python/knowledge_locator.py'),'--repository-root',str(root),'--catalog',str(paths[0]),'--policies',str(paths[1]),'--projections',str(paths[2])],input=json.dumps({k:v for k,v in denied.items() if k!='stage'}),capture_output=True,text=True,encoding='utf-8',check=False)
    assert proc.returncode==0
    observed={**raw,'result':json.loads(proc.stdout)}
    assert observed['result']['status']=='blocked'
    with patch.object(core,'query_with_diagnostics',return_value=observed) as called:
        output=_planning_operation(fixture)
    assert called.called
    result=output.get('result',output)
    assert result.get('status',output.get('outcome'))=='blocked'
    assert not result.get('candidates') and not output.get('read_set') and not output.get('adopted')


def _s7_raw_compatibility(fixture, scenario):
    __tracebackhide__ = True
    import subprocess
    root,paths,request=fixture
    _s7_write_config(fixture)
    overrides={'query':'zzzz-no-match'} if scenario=='empty' else ({'policy_revision':'unknown-policy'} if scenario=='blocked' else {})
    raw_request={k:v for k,v in {**request,**overrides}.items() if k!='stage'}
    proc=subprocess.run([sys.executable,str(ROOT/'scripts/python/knowledge_locator.py'),'--max-candidates','1','--repository-root',str(root),'--catalog',str(paths[0]),'--policies',str(paths[1]),'--projections',str(paths[2])],input=json.dumps(raw_request),capture_output=True,text=True,encoding='utf-8',check=False)
    assert proc.returncode==0
    legacy=json.loads(proc.stdout)
    output=_planning_operation(fixture,**overrides)
    assert output.get('result')==legacy, 'The original Locator result and caller compatibility must be retained'
    diagnostic=output.get('diagnostic',{})
    assert diagnostic.get('raw_status')==legacy['status']
    assert 'exit_code' in diagnostic
    assert diagnostic['exit_code'] is None or diagnostic['exit_code']==proc.returncode
    assert diagnostic.get('evidence_refs'), 'Classification may not erase its real diagnostic evidence'


def _s7_required_gate(fixture, nonempty=False):
    __tracebackhide__ = True
    import knowledge_context_validation as validator
    root,paths,base=fixture
    req={k:v for k,v in base.items() if k!='stage'}
    req.update(consumer='vdd',query='repository knowledge authority' if nonempty else 'zzzz-no-match')
    raw=_s12_raw_query(req,root,catalog_path=paths[0],policies_path=paths[1],projections_path=paths[2])['result']
    if nonempty:assert raw['candidates']
    else:assert raw['status']=='insufficient_match' and raw['candidates']==[]
    payload={'schema_version':'jimuyun.vdd-knowledge-context.v1','locator_request':req,'locator_result':raw,
        'required_modules':['repository-rules'],'decisions':[{'owner':'adapter','candidate':{'path':c['path'],'source_sha256':c['source_sha256']},'decision':'rejected','satisfies':[],'rejection_reason':'insufficient_specificity'} for c in raw['candidates']],
        'request_sha256':validator.canonical_hash(req),'result_sha256':validator.canonical_hash(raw)}
    reason=validator.validate_context(payload,repository_root=root,verify_catalog=True,expected_consumer='vdd',require_selection=True)
    assert reason==('required_modules_unsatisfied' if nonempty else 'locator_result_not_matched')
    return reason


def _s7_verified_read(fixture, scenario):
    __tracebackhide__ = True
    from copy import deepcopy
    from unittest.mock import patch
    import hashlib
    _s7_write_config(fixture)
    root,paths,request=fixture
    raw=_s12_raw_query({k:v for k,v in request.items() if k!='stage'},root,catalog_path=paths[0],policies_path=paths[1],projections_path=paths[2])
    assert raw['result']['candidates']
    if scenario=='hash-mismatch':
        raw=deepcopy(raw)
        for c in raw['result']['candidates']:
            c['source_sha256']='0'*64
            for ref in c.get('read_set',[]):ref['source_sha256']='0'*64
    with patch.object(core,'query_with_diagnostics',return_value=raw) as reached:
        output=_planning_operation(fixture)
    assert reached.called
    if scenario=='hash-mismatch':
        assert output.get('outcome')=='blocked' and output.get('reason_code')=='integrity_failed'
        assert not output.get('read_set') and not output.get('candidates')
    else:
        reads=output.get('read_set',[])
        assert reads, 'Matched source must produce actually verified read metadata'
        for read in reads:
            actual=(root/read['path']).read_bytes()
            assert read['sha256'].removeprefix('sha256:')==hashlib.sha256(actual).hexdigest()
            assert read.get('excerpt_range') and read.get('read_identity')
    assert not output.get('adopted') and not output.get('authorizes')


@pytest.mark.cer_assertion('ASSERT_C2B808E0497D')
@pytest.mark.parametrize("scenario", ['same', 'unrelated-file', 'related-source', 'task-change'], ids=['0-same', '1-unrelated-file', '2-related-source', '3-task-change'])
def test_contract_c2b808e0497d(published_planning, scenario):
    # Recover same task/scope/read-set with either unchanged, unrelated changed or related changed source
    try:
        _s7_recovery(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_C2B808E0497D')
        raise


@pytest.mark.cer_assertion('ASSERT_C1C6D547B2BD')
def test_contract_c1c6d547b2bd(published_planning):
    # Every adapter outcome including terminal
    try:
        _s7_schema(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_C1C6D547B2BD')
        raise


@pytest.mark.cer_assertion('ASSERT_C90E2D008D9F')
@pytest.mark.parametrize("scenario", ['snapshot', 'main', 'branch', 'worktree', 'candidate-preservation', 'unauthorized-change'])
def test_contract_c90e2d008d9f(published_planning, scenario):
    # Same source at snapshot/main/branch/worktree versions
    try:
        _s7_identity(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_C90E2D008D9F')
        raise


@pytest.mark.cer_assertion('ASSERT_E7FD5135E3CE')
def test_contract_e7fd5135e3ce(published_planning):
    # Cancel after an integrity/policy error observed
    try:
        _s7_cancel_prior_error(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_E7FD5135E3CE')
        raise


@pytest.mark.cer_assertion('ASSERT_7161798390FD')
def test_contract_7161798390fd(published_planning):
    # Recognized availability/insufficient/confidence/ambiguity/stale/change and unknown failure
    try:
        _s7_direct(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_7161798390FD')
        raise


@pytest.mark.cer_assertion('ASSERT_8118AC4A1D1B')
@pytest.mark.parametrize("scenario", ['snapshot', 'main', 'branch', 'worktree', 'candidate-preservation', 'unauthorized-change'])
def test_contract_8118ac4a1d1b(published_planning, scenario):
    # Retained VDD request and all source version kinds
    try:
        _s7_identity(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_8118AC4A1D1B')
        raise


@pytest.mark.cer_assertion('ASSERT_295A1ED8402C')
def test_contract_295a1ed8402c(published_planning):
    # Cancel active query then resume same task
    try:
        _s7_cancel(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_295A1ED8402C')
        raise


@pytest.mark.cer_assertion('ASSERT_1986A8A866A9')
@pytest.mark.parametrize("scenario", ['candidate-cap', 'episode-counter'])
def test_contract_1986a8a866a9(published_planning, scenario):
    # Episode with repeated calls, duplicate candidates and multibyte large excerpts
    try:
        _s7_budget(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_1986A8A866A9')
        raise


@pytest.mark.cer_assertion('ASSERT_7D56282FCA48')
@pytest.mark.parametrize("scenario", ["matched", "empty", "insufficient", "unknown"])
def test_contract_7d56282fca48(published_planning, scenario):
    # Legal zero/nonzero insufficient, low confidence and ambiguity after prerequisites
    try:
        _s7_closed_pairs(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_7D56282FCA48')
        raise


@pytest.mark.cer_assertion('ASSERT_6F28F6213395')
@pytest.mark.parametrize("scenario", ['absent', 'empty', 'malformed'], ids=['0-absent', '1-empty', '2-malformed'])
def test_contract_6f28f6213395(published_planning, scenario):
    # Absent installation/config versus existing malformed/unreadable/corrupt config
    try:
        _s7_missing_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_6F28F6213395')
        raise


@pytest.mark.cer_assertion('ASSERT_FBE33745AF99')
def test_contract_fbe33745af99(published_planning):
    # Active subprocess receives cancellation after prior failed attempt
    try:
        _s7_cancel(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_FBE33745AF99')
        raise


@pytest.mark.cer_assertion('ASSERT_CF914A509B70')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_cf914a509b70(published_planning, scenario):
    # Personal override or query intent widens path/domain/budget
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_CF914A509B70')
        raise


@pytest.mark.cer_assertion('ASSERT_53AB257DBFF5')
def test_contract_53ab257dbff5(published_planning):
    # Query, adoption, rejection and local refresh sequence
    try:
        _s7_audit(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_53AB257DBFF5')
        raise


@pytest.mark.cer_assertion('ASSERT_50ACBBD8D0AF')
def test_contract_50acbbd8d0af(published_planning):
    # Malformed request/output, invalid config, integrity mismatch, policy/path denial or unknown error
    try:
        _s7_blocked(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_50ACBBD8D0AF')
        raise


@pytest.mark.cer_assertion('ASSERT_0531C165C195')
def test_contract_0531c165c195(published_planning):
    # Cancellation before source verification completes
    try:
        _s7_cancel(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_0531C165C195')
        raise


@pytest.mark.cer_assertion('ASSERT_0E473B3331BF')
@pytest.mark.parametrize("scenario", ['unknown-empty', 'blocked-empty', 'matched-empty'], ids=['0-unknown-empty', '1-blocked-empty', '2-matched-empty'])
def test_contract_0e473b3331bf(published_planning, scenario):
    # Unknown/mismatched status with empty array
    try:
        _s7_unknown(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_0E473B3331BF')
        raise


@pytest.mark.cer_assertion('ASSERT_8610730096AD')
@pytest.mark.parametrize("scenario", ['terminal-reserve', 'utf8-cumulative-writer'])
def test_contract_8610730096ad(published_planning, scenario):
    try:
        _s7_output(published_planning) if scenario=='terminal-reserve' else _s7_delivery_boundary(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_8610730096AD')
        raise


@pytest.mark.cer_assertion('ASSERT_FC7DBACE2B9E')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_fc7dbace2b9e(published_planning, scenario):
    # Default required stages, repository disabled and personal disabled
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_FC7DBACE2B9E')
        raise


@pytest.mark.cer_assertion('ASSERT_5B57A2FF7E8E')
def test_contract_5b57a2ff7e8e(published_planning):
    # Relevant conflicting candidate plus many irrelevant search results
    try:
        _s7_audit(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_5B57A2FF7E8E')
        raise


@pytest.mark.cer_assertion('ASSERT_3BF54CFB6A2C')
@pytest.mark.parametrize("scenario", ['same', 'unrelated-file', 'related-source', 'task-change'], ids=['0-same', '1-unrelated-file', '2-related-source', '3-task-change'])
def test_contract_3bf54cfb6a2c(published_planning, scenario):
    # Same task read-set resume and unrelated generation change contrasted relevant input change
    try:
        _s7_recovery(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_3BF54CFB6A2C')
        raise


@pytest.mark.cer_assertion('ASSERT_9B9F2277BAF0')
def test_contract_9b9f2277baf0(published_planning):
    # Valid matched candidate with correct source hash and a tampered source variant
    try:
        _s7_hit_read(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_9B9F2277BAF0')
        raise


@pytest.mark.cer_assertion('ASSERT_BA146B52F4BF')
def test_contract_ba146b52f4bf(published_planning):
    # Untrusted result and attempted dependent judgment
    try:
        _s7_blocked(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_BA146B52F4BF')
        raise


@pytest.mark.cer_assertion('ASSERT_891CBF9A43F0')
def test_contract_891cbf9a43f0(published_planning):
    # Legal insufficient_match with [] or nonempty and required module unsatisfied
    try:
        _s7_zero(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_891CBF9A43F0')
        raise


@pytest.mark.cer_assertion('ASSERT_2A4453D64EC3')
@pytest.mark.parametrize("scenario", ['valid', 'publication-failure', 'episode-counters'])
def test_contract_2a4453d64ec3(published_planning, scenario):
    try:
        _s7_no_mutation(published_planning, scenario) if scenario!='episode-counters' else _s7_budget(published_planning, 'episode-counter')
    except AssertionError:
        print('FAILURE_ID:KQ_2A4453D64EC3')
        raise


@pytest.mark.cer_assertion('ASSERT_9A38E9C1D8D3')
@pytest.mark.parametrize("scenario", ['snapshot', 'main', 'branch', 'worktree', 'candidate-preservation', 'unauthorized-change'])
def test_contract_9a38e9c1d8d3(published_planning, scenario):
    # Published snapshot differs from current main/branch/worktree
    try:
        _s7_identity(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_9A38E9C1D8D3')
        raise


@pytest.mark.cer_assertion('ASSERT_C3FDEAA09926')
def test_contract_c3fdeaa09926(published_planning):
    # Governance off/on with recognized stale/availability and unknown failure
    try:
        _s7_direct(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_C3FDEAA09926')
        raise


@pytest.mark.cer_assertion('ASSERT_6D340C60E04C')
def test_contract_6d340c60e04c(published_planning):
    # Output allowance4096 or65536 near exhaustion
    try:
        _s7_output(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_6D340C60E04C')
        raise


@pytest.mark.cer_assertion('ASSERT_663AC61551EA')
@pytest.mark.parametrize('scenario', ['valid-read', 'hash-mismatch'])
def test_contract_663ac61551ea(published_planning, scenario):
    try:
        _s7_verified_read(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_663AC61551EA')
        raise


@pytest.mark.cer_assertion('ASSERT_FD5C326B64A0')
@pytest.mark.parametrize("scenario", ['absent', 'empty', 'malformed'], ids=['0-absent', '1-empty', '2-malformed'])
def test_contract_fd5c326b64a0(published_planning, scenario):
    # Absent query config contrasted malformed/corrupt/unreadable existing file
    try:
        _s7_missing_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_FD5C326B64A0')
        raise


@pytest.mark.cer_assertion('ASSERT_C4EF411007FE')
@pytest.mark.parametrize("scenario", ['same', 'unrelated-file', 'related-source', 'task-change'], ids=['0-same', '1-unrelated-file', '2-related-source', '3-task-change'])
def test_contract_c4ef411007fe(published_planning, scenario):
    # Recovery of failed/cancelled episode
    try:
        _s7_history_preservation(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_C4EF411007FE')
        raise


@pytest.mark.cer_assertion('ASSERT_9C630007325C')
def test_contract_9c630007325c(published_planning):
    # Native and VDD result/adoption recording
    try:
        _s7_audit(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_9C630007325C')
        raise


@pytest.mark.cer_assertion('ASSERT_79A83B840FB4')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_79a83b840fb4(published_planning, scenario):
    # Distinct hard/team/published policy/caller/personal limits including lower legal policy
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_79A83B840FB4')
        raise


@pytest.mark.cer_assertion('ASSERT_EE8FAD50FD50')
@pytest.mark.parametrize("scenario", ['terminal-reserve', 'utf8-cumulative-writer'])
def test_contract_ee8fad50fd50(published_planning, scenario):
    try:
        _s7_output(published_planning) if scenario=='terminal-reserve' else _s7_delivery_boundary(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_EE8FAD50FD50')
        raise


@pytest.mark.cer_assertion('ASSERT_4D7902276417')
@pytest.mark.parametrize("scenario", ['snapshot', 'main', 'branch', 'worktree', 'candidate-preservation', 'unauthorized-change'])
def test_contract_4d7902276417(published_planning, scenario):
    # Attributable permitted selected-source change versus unauthorized hash mutation
    try:
        _s7_identity(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_4D7902276417')
        raise


@pytest.mark.cer_assertion('ASSERT_639EEB9CC5A0')
@pytest.mark.parametrize("scenario", ['candidate-cap', 'episode-counter'])
def test_contract_639eeb9cc5a0(published_planning, scenario):
    # Duplicate candidates across calls
    try:
        _s7_budget(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_639EEB9CC5A0')
        raise


@pytest.mark.cer_assertion('ASSERT_43B295DB7583')
@pytest.mark.parametrize("scenario", ['same', 'unrelated-file', 'related-source', 'task-change'], ids=['0-same', '1-unrelated-file', '2-related-source', '3-task-change'])
def test_contract_43b295db7583(published_planning, scenario):
    # Retry/duplicate/recovery and explicit relevant input change
    try:
        _s7_recovery(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_43B295DB7583')
        raise


@pytest.mark.cer_assertion('ASSERT_49AD192F8507')
@pytest.mark.parametrize("scenario", ['integrity', 'publication-missing', 'policy', 'snapshot', 'stale', 'stale-integrity', 'stale-policy'])
def test_contract_49ad192f8507(published_planning, scenario):
    try:
        _s7_failure_priority(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_49AD192F8507')
        raise


@pytest.mark.cer_assertion('ASSERT_1EACFC8E1EAE')
@pytest.mark.parametrize("scenario", ['unknown-empty', 'blocked-empty', 'matched-empty'], ids=['0-unknown-empty', '1-blocked-empty', '2-matched-empty'])
def test_contract_1eacfc8e1eae(published_planning, scenario):
    # Legacy output blocked with exit0 and [] and minimal readonly diagnostics
    try:
        _s7_unknown(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_1EACFC8E1EAE')
        raise


@pytest.mark.cer_assertion('ASSERT_3036B6BC69BB')
@pytest.mark.parametrize("scenario", ['pointer', 'projection', 'catalog', 'policy'], ids=['0-pointer', '1-projection', '2-catalog', '3-policy'])
def test_contract_3036b6bc69bb(published_planning, scenario):
    # Denied candidate includes secret-like marker and out-of-bounds path
    try:
        _s7_integrity_guard(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_3036B6BC69BB')
        raise


@pytest.mark.cer_assertion('ASSERT_B56CECA98BA0')
def test_contract_b56ceca98ba0(published_planning):
    # Corrupt/out-of-bounds/denied/unknown result with exit0 or []
    try:
        _s7_blocked(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_B56CECA98BA0')
        raise


@pytest.mark.cer_assertion('ASSERT_AF2078FB2E4B')
@pytest.mark.parametrize("scenario", ['unknown-empty', 'blocked-empty', 'matched-empty'], ids=['0-unknown-empty', '1-blocked-empty', '2-matched-empty'])
def test_contract_af2078fb2e4b(published_planning, scenario):
    # Unknown status/exit/exception or mismatched outcome pair
    try:
        _s7_unknown(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_AF2078FB2E4B')
        raise


@pytest.mark.cer_assertion('ASSERT_6FF05E83E725')
@pytest.mark.parametrize("scenario", ['absent', 'empty', 'malformed'], ids=['0-absent', '1-empty', '2-malformed'])
def test_contract_6ff05e83e725(published_planning, scenario):
    # Confirmed missing required configuration
    try:
        _s7_missing_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_6FF05E83E725')
        raise


@pytest.mark.cer_assertion('ASSERT_8C9E227B4EAE')
@pytest.mark.parametrize("scenario", ['candidate-cap', 'episode-counter'])
def test_contract_8c9e227b4eae(published_planning, scenario):
    # Multiple returns with repeated candidate rows
    try:
        _s7_budget(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_8C9E227B4EAE')
        raise


@pytest.mark.cer_assertion('ASSERT_B0293AD5244C')
def test_contract_b0293ad5244c(published_planning):
    # Diagnosed availability failure then independent read unresolved
    try:
        _s7_direct(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_B0293AD5244C')
        raise


@pytest.mark.cer_assertion('ASSERT_7128DF18FB20')
@pytest.mark.parametrize("scenario", ['snapshot', 'main', 'branch', 'worktree', 'candidate-preservation', 'unauthorized-change'])
def test_contract_7128df18fb20(published_planning, scenario):
    # Confirmed generation and unavailable/unconfirmed generation
    try:
        _s7_identity(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_7128DF18FB20')
        raise


@pytest.mark.cer_assertion('ASSERT_E4594C06522D')
@pytest.mark.parametrize("scenario", ["valid", "publication-failure"])
def test_contract_e4594c06522d(published_planning, scenario):
    # Low hit rate/blocked output and large history
    try:
        _s7_no_mutation(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_E4594C06522D')
        raise


@pytest.mark.cer_assertion('ASSERT_6D014AB0CCF2')
@pytest.mark.parametrize("scenario", ['valid', 'publication-failure', 'episode-counters'])
def test_contract_6d014ab0ccf2(published_planning, scenario):
    try:
        _s7_no_mutation(published_planning, scenario) if scenario!='episode-counters' else _s7_budget(published_planning, 'episode-counter')
    except AssertionError:
        print('FAILURE_ID:KQ_6D014AB0CCF2')
        raise


@pytest.mark.cer_assertion('ASSERT_03DD2B8DEFDB')
@pytest.mark.parametrize("scenario", ["stdout", "stderr", "combined", "json-parser"])
def test_contract_03dd2b8defdb(published_planning, scenario):
    # Subprocess floods stdout, stderr or combined streams with multibyte content
    try:
        _s7_transport(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_03DD2B8DEFDB')
        raise


@pytest.mark.cer_assertion('ASSERT_9431A00FFFBA')
@pytest.mark.parametrize("scenario", ["valid", "publication-failure"])
def test_contract_9431a00fffba(published_planning, scenario):
    # Actual query argv/path selection
    try:
        _s7_no_mutation(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_9431A00FFFBA')
        raise


@pytest.mark.cer_assertion('ASSERT_1693A89D7360')
def test_contract_1693a89d7360(published_planning):
    # Integrity/policy error observed before cancellation
    try:
        _s7_cancel_prior_error(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_1693A89D7360')
        raise


@pytest.mark.cer_assertion('ASSERT_D1E9D110AFB1')
@pytest.mark.parametrize("scenario", [('malformed', None), ('unknown', None), ('max_candidates', True), ('max_candidates', 0), ('max_candidates', -1), ('max_candidates', 1.5), ('max_candidates', '3'), ('max_candidates', 21), ('max_output_bytes', True), ('max_output_bytes', 0), ('max_output_bytes', -1), ('max_output_bytes', 1.5), ('max_output_bytes', '3'), ('max_output_bytes', 131073), ('max_calls', True), ('max_calls', 0), ('max_calls', -1), ('max_calls', 1.5), ('max_calls', '3'), ('max_calls', 6), ('timeout_seconds', True), ('timeout_seconds', 0), ('timeout_seconds', -1), ('timeout_seconds', 1.5), ('timeout_seconds', '3'), ('timeout_seconds', 61), ('max_output_bytes', 4095)], ids=["0-('malformed', None)", "1-('unknown', None)", "2-('max_candidates', True)", "3-('max_candidates', 0)", "4-('max_candidates', -1)", "5-('max_candidates', 1.5)", "6-('max_candidates', '3')", "7-('max_candidates', 21)", "8-('max_output_bytes', True)", "9-('max_output_bytes', 0)", "10-('max_output_bytes', -1)", "11-('max_output_bytes', 1.5)", "12-('max_output_bytes', '3')", "13-('max_output_bytes', 131073)", "14-('max_calls', True)", "15-('max_calls', 0)", "16-('max_calls', -1)", "17-('max_calls', 1.5)", "18-('max_calls', '3')", "19-('max_calls', 6)", "20-('timeout_seconds', True)", "21-('timeout_seconds', 0)", "22-('timeout_seconds', -1)", "23-('timeout_seconds', 1.5)", "24-('timeout_seconds', '3')", "25-('timeout_seconds', 61)", "26-('max_output_bytes', 4095)"])
def test_contract_d1e9d110afb1(published_planning, scenario):
    # Existing file unreadable, malformed, unknown field or invalid value
    try:
        _s7_invalid_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_D1E9D110AFB1')
        raise


@pytest.mark.cer_assertion('ASSERT_1207E29C7AAF')
def test_contract_1207e29c7aaf(published_planning):
    # Official resolver appends equivalent hooks twice with identical stage/operation/task/scope/relevant input identities
    try:
        _s7_duplicate(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_1207E29C7AAF')
        raise


@pytest.mark.cer_assertion('ASSERT_41A0E85D2369')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_41a0e85d2369(published_planning, scenario):
    # Missing required config versus existing malformed/unreadable config versus unknown or unadmitted consumer
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_41A0E85D2369')
        raise


@pytest.mark.cer_assertion('ASSERT_FCA87D5A1DD3')
def test_contract_fca87d5a1dd3(published_planning):
    # Equivalent appended hooks
    try:
        _s7_duplicate(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_FCA87D5A1DD3')
        raise


@pytest.mark.cer_assertion('ASSERT_9A069365A1DC')
@pytest.mark.parametrize("scenario", ['same', 'unrelated-file', 'related-source', 'task-change'], ids=['0-same', '1-unrelated-file', '2-related-source', '3-task-change'])
def test_contract_9a069365a1dc(published_planning, scenario):
    # Related versus unrelated drift after prior query
    try:
        _s7_recovery(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_9A069365A1DC')
        raise


@pytest.mark.cer_assertion('ASSERT_D1CD48A38E94')
@pytest.mark.parametrize("scenario", ["valid", "publication-failure"])
def test_contract_d1cd48a38e94(published_planning, scenario):
    # Routine query with before/after git/index/history hashes and launch tracing
    try:
        _s7_no_mutation(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_D1CD48A38E94')
        raise


@pytest.mark.cer_assertion('ASSERT_48A9ADB890E3')
def test_contract_48a9adb890e3(published_planning):
    # Cancel query before complete source verification
    try:
        _s7_cancel(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_48A9ADB890E3')
        raise


@pytest.mark.cer_assertion('ASSERT_B9CC1CD8672A')
def test_contract_b9cc1cd8672a(published_planning):
    # Legal no_match/empty from raw insufficient_match
    try:
        _s7_zero(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_B9CC1CD8672A')
        raise


@pytest.mark.cer_assertion('ASSERT_D097E8932C6D')
@pytest.mark.parametrize("scenario", ["known-old", "unconfirmed"])
def test_contract_d097e8932c6d(published_planning, scenario):
    # Known valid generation versus absent/unconfirmed generation
    try:
        _s7_snapshot_truth_guard(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_D097E8932C6D')
        raise


@pytest.mark.cer_assertion('ASSERT_627B8C4B71A7')
@pytest.mark.parametrize("scenario", ['unknown-empty', 'blocked-empty', 'matched-empty'], ids=['0-unknown-empty', '1-blocked-empty', '2-matched-empty'])
def test_contract_627b8c4b71a7(published_planning, scenario):
    # Real core output and verified readonly diagnostics matrix
    try:
        _s7_unknown(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_627B8C4B71A7')
        raise


@pytest.mark.cer_assertion('ASSERT_5E3DA627C900')
@pytest.mark.parametrize("scenario", ['unknown-empty', 'blocked-empty', 'matched-empty'], ids=['0-unknown-empty', '1-blocked-empty', '2-matched-empty'])
def test_contract_5e3da627c900(published_planning, scenario):
    # Conflicting transport/business/integrity signals matrix
    try:
        _s7_unknown(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_5E3DA627C900')
        raise


@pytest.mark.cer_assertion('ASSERT_58D6151EF2C1')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_58d6151ef2c1(published_planning, scenario):
    # Different valid bounds plus bool/zero/negative/type/overcap/sub4096 inputs
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_58D6151EF2C1')
        raise


@pytest.mark.cer_assertion('ASSERT_1AC1A5752B1A')
def test_contract_1ac1a5752b1a(published_planning):
    # Cancel after observed validation error
    try:
        _s7_cancel(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_1AC1A5752B1A')
        raise


@pytest.mark.cer_assertion('ASSERT_C9F4C60FB490')
@pytest.mark.parametrize("scenario", ['integrity', 'publication-missing', 'policy', 'snapshot', 'stale', 'stale-integrity', 'stale-policy'])
def test_contract_c9f4c60fb490(published_planning, scenario):
    try:
        _s7_failure_priority(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_C9F4C60FB490')
        raise


@pytest.mark.cer_assertion('ASSERT_FAEF193B73BF')
def test_contract_faef193b73bf(published_planning):
    # Illegal request/config, corrupt JSON/hash, path escape, policy rejection, unknown status and exit0 blocked matrix
    try:
        _s7_blocked(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_FAEF193B73BF')
        raise


@pytest.mark.cer_assertion('ASSERT_5E6CC5C750BC')
def test_contract_5e6cc5c750bc(published_planning):
    # Diagnosed availability failure with independent source read success/failure
    try:
        _s7_direct(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_5E6CC5C750BC')
        raise


@pytest.mark.cer_assertion('ASSERT_971C0DC625C8')
@pytest.mark.parametrize("scenario", ['insufficient', 'low-confidence', 'missing-confidence'], ids=['0-insufficient', '1-low-confidence', '2-missing-confidence'])
def test_contract_971c0dc625c8(published_planning, scenario):
    # Verified stale/relevant source change after integrity/policy/scope checks, contrasted corrupted publication with stale flag
    try:
        _s7_degraded(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_971C0DC625C8')
        raise


@pytest.mark.cer_assertion('ASSERT_150240BC71C3')
@pytest.mark.parametrize("scenario", ['integrity', 'publication-missing', 'policy', 'snapshot', 'stale', 'stale-integrity', 'stale-policy'])
def test_contract_150240bc71c3(published_planning, scenario):
    try:
        _s7_failure_priority(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_150240BC71C3')
        raise


@pytest.mark.cer_assertion('ASSERT_9D64F32F363E')
def test_contract_9d64f32f363e(published_planning):
    # Terminal report with maximal diagnostic source
    try:
        _s7_output(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_9D64F32F363E')
        raise


@pytest.mark.cer_assertion('ASSERT_A06E38594D27')
def test_contract_a06e38594d27(published_planning):
    # Matched candidates before/after actual hash-verified read
    try:
        _s7_hit_read(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_A06E38594D27')
        raise


@pytest.mark.cer_assertion('ASSERT_BFA252173BA7')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_bfa252173ba7(published_planning, scenario):
    # Effective configuration query with repository, published policy and smaller caller values
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_BFA252173BA7')
        raise


@pytest.mark.cer_assertion('ASSERT_9F085544A2E4')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_9f085544a2e4(published_planning, scenario):
    # Official 6.12.4 resolver with repository and personal configuration combinations: absent, valid smaller, malformed, unknown fields and appended arrays
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_9F085544A2E4')
        raise


@pytest.mark.cer_assertion('ASSERT_B9783098460C')
def test_contract_b9783098460c(published_planning):
    # blocked/cancelled/budget_exhausted responses carrying input candidates
    try:
        _s7_output(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_B9783098460C')
        raise


@pytest.mark.cer_assertion('ASSERT_CC2672622099')
@pytest.mark.parametrize("scenario", ["stdout", "stderr", "combined", "json-parser"])
def test_contract_cc2672622099(published_planning, scenario):
    # Both child streams flood or end mid JSON
    try:
        _s7_transport(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_CC2672622099')
        raise


@pytest.mark.cer_assertion('ASSERT_06FDF04DDEA5')
@pytest.mark.parametrize("scenario", ['insufficient', 'low-confidence', 'missing-confidence'], ids=['0-insufficient', '1-low-confidence', '2-missing-confidence'])
def test_contract_06fdf04ddea5(published_planning, scenario):
    # Degraded result then separately verified direct source
    try:
        _s7_degraded(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_06FDF04DDEA5')
        raise


@pytest.mark.cer_assertion('ASSERT_3D2630E90BF0')
@pytest.mark.parametrize("scenario", ['snapshot', 'main', 'branch', 'worktree', 'candidate-preservation', 'unauthorized-change'])
def test_contract_3d2630e90bf0(published_planning, scenario):
    # Same path has distinct published snapshot, main, branch commit and uncommitted worktree bytes
    try:
        _s7_identity(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_3D2630E90BF0')
        raise


@pytest.mark.cer_assertion('ASSERT_88D9B960346B')
@pytest.mark.parametrize("scenario", ['terminal-reserve', 'utf8-cumulative-writer'])
def test_contract_88d9b960346b(published_planning, scenario):
    try:
        _s7_output(published_planning) if scenario=='terminal-reserve' else _s7_delivery_boundary(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_88D9B960346B')
        raise


@pytest.mark.cer_assertion('ASSERT_8914061E7998')
def test_contract_8914061e7998(published_planning):
    # Remaining ordinary bytes insufficient
    try:
        _s7_output(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_8914061E7998')
        raise


@pytest.mark.cer_assertion('ASSERT_8D11934293AE')
@pytest.mark.parametrize("scenario", ['candidate-cap', 'episode-counter'])
def test_contract_8d11934293ae(published_planning, scenario):
    # Native append duplicates same hook
    try:
        _s7_budget(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_8D11934293AE')
        raise


@pytest.mark.cer_assertion('ASSERT_D15067654AC2')
@pytest.mark.parametrize("scenario", ['unknown-empty', 'blocked-empty', 'matched-empty'], ids=['0-unknown-empty', '1-blocked-empty', '2-matched-empty'])
def test_contract_d15067654ac2(published_planning, scenario):
    # Generic blocked/nonzero/empty without reliable cause
    try:
        _s7_unknown(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_D15067654AC2')
        raise


@pytest.mark.cer_assertion('ASSERT_7DF0A2364C34')
@pytest.mark.parametrize("scenario", ['insufficient', 'low-confidence', 'missing-confidence'], ids=['0-insufficient', '1-low-confidence', '2-missing-confidence'])
def test_contract_7df0a2364c34(published_planning, scenario):
    # Nonempty insufficient_match after trust checks without higher-priority condition
    try:
        _s7_degraded(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_7DF0A2364C34')
        raise


@pytest.mark.cer_assertion('ASSERT_B9380328BF22')
def test_contract_b9380328bf22(published_planning):
    # Success/degraded/unavailable/blocked/cancelled/exhausted recovery records
    try:
        _s7_audit(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_B9380328BF22')
        raise


@pytest.mark.cer_assertion('ASSERT_0EECFA4AF377')
@pytest.mark.parametrize("scenario", ['integrity', 'publication-missing', 'policy', 'snapshot', 'stale', 'stale-integrity', 'stale-policy'])
def test_contract_0eecfa4af377(published_planning, scenario):
    try:
        _s7_failure_priority(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_0EECFA4AF377')
        raise


@pytest.mark.cer_assertion('ASSERT_AD21C3976803')
@pytest.mark.parametrize("scenario", ['same', 'unrelated-file', 'related-source', 'task-change'], ids=['0-same', '1-unrelated-file', '2-related-source', '3-task-change'])
def test_contract_ad21c3976803(published_planning, scenario):
    # Retry, duplicate hook, resume and unrelated index generation change for same judgment
    try:
        _s7_recovery(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_AD21C3976803')
        raise


@pytest.mark.cer_assertion('ASSERT_1B2DEF4F4ED8')
def test_planning_attempt_deadline_timeout(published_planning):
    # Controlled child at30/60 wallclock bounds and explicit cancellation
    try:
        _s7_timeout(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_1B2DEF4F4ED8')
        raise


@pytest.mark.cer_assertion('ASSERT_6ECFC199C2D2')
@pytest.mark.parametrize("scenario", ['insufficient', 'low-confidence', 'missing-confidence'], ids=['0-insufficient', '1-low-confidence', '2-missing-confidence'])
def test_contract_6ecfc199c2d2(published_planning, scenario):
    # Recognized stale or selected-source change after trust checks
    try:
        _s7_degraded(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_6ECFC199C2D2')
        raise


@pytest.mark.cer_assertion('ASSERT_7E78E000DDDC')
@pytest.mark.parametrize("scenario", ['pointer', 'projection', 'catalog', 'policy'], ids=['0-pointer', '1-projection', '2-catalog', '3-policy'])
def test_contract_7e78e000dddc(published_planning, scenario):
    # Corrupt/out-of-bounds result with sensitive sentinel
    try:
        _s7_integrity_guard(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_7E78E000DDDC')
        raise


@pytest.mark.cer_assertion('ASSERT_32C6C396BEC7')
@pytest.mark.parametrize("scenario", ["pointer", "projection", "catalog", "policy"])
def test_contract_32c6c396bec7(published_planning, scenario):
    # Hit/stale/empty alongside trust error
    try:
        _s7_integrity_guard(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_32C6C396BEC7')
        raise


@pytest.mark.cer_assertion('ASSERT_560D069494F3')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_560d069494f3(published_planning, scenario):
    # Personal budget narrowing versus stage removal/enabled=false/expansion
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_560D069494F3')
        raise


@pytest.mark.cer_assertion('ASSERT_08A195E40B8A')
@pytest.mark.parametrize("scenario", ["valid", "publication-failure"])
def test_contract_08a195e40b8a(published_planning, scenario):
    # Query failure with publisher callable monitored
    try:
        _s7_no_mutation(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_08A195E40B8A')
        raise


@pytest.mark.cer_assertion('ASSERT_3DC165490699')
@pytest.mark.parametrize("scenario", ['same', 'unrelated-file', 'related-source', 'task-change'], ids=['0-same', '1-unrelated-file', '2-related-source', '3-task-change'])
def test_contract_3dc165490699(published_planning, scenario):
    # Unchanged task/read-set on resume then relevant change in new stage
    try:
        _s7_recovery(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_3DC165490699')
        raise


@pytest.mark.cer_assertion('ASSERT_8376A58C8D9A')
def test_contract_8376a58c8d9a(published_planning):
    # Direct-source fallback while formal required module missing
    try:
        _s7_direct(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_8376A58C8D9A')
        raise


@pytest.mark.cer_assertion('ASSERT_23847110E04A')
@pytest.mark.parametrize("scenario", ['unknown-empty', 'blocked-empty', 'matched-empty'], ids=['0-unknown-empty', '1-blocked-empty', '2-matched-empty'])
def test_contract_23847110e04a(published_planning, scenario):
    # Matrix of legal matched, insufficient_match empty/nonempty, confirmed missing config/backend/timeout, invalid config, denied path/policy, broken publication, stale, cancelled and unknown outputs
    try:
        _s7_unknown(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_23847110E04A')
        raise


@pytest.mark.cer_assertion('ASSERT_D823F94E0DB3')
def test_contract_d823f94e0db3(published_planning):
    # Confirmed missing integration/config, diagnosed backend unavailability or timeout with accessible authorized current source
    try:
        _s7_direct(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_D823F94E0DB3')
        raise


@pytest.mark.cer_assertion('ASSERT_F9C89045878F')
@pytest.mark.parametrize("scenario", ['snapshot', 'main', 'branch', 'worktree', 'candidate-preservation', 'unauthorized-change'])
def test_contract_f9c89045878f(published_planning, scenario):
    # Published snapshot older than main and branch/worktree modifications to same path
    try:
        _s7_identity(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_F9C89045878F')
        raise


@pytest.mark.cer_assertion('ASSERT_8299476377C3')
@pytest.mark.parametrize("scenario", ['nonzero', 'unicode-argv'])
def test_contract_8299476377c3(published_planning, scenario):
    try:
        _s7_process_cause(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_8299476377C3')
        raise


@pytest.mark.cer_assertion('ASSERT_74A2254C30B4')
@pytest.mark.parametrize("scenario", ["matched", "empty", "insufficient", "unknown"])
def test_contract_74a2254c30b4(published_planning, scenario):
    # Legal empty and nonempty insufficient results with required module absent
    try:
        _s7_closed_pairs(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_74A2254C30B4')
        raise


@pytest.mark.cer_assertion('ASSERT_3C7A68FEFC3A')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_3c7a68fefc3a(published_planning, scenario):
    # Team scopes and required stages plus personal/model request for extra paths, arbitrary consumer, wider budget or disabled required stage
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_3C7A68FEFC3A')
        raise


@pytest.mark.cer_assertion('ASSERT_99AF9B9AC486')
@pytest.mark.parametrize("scenario", ['pointer', 'projection', 'catalog', 'policy'], ids=['0-pointer', '1-projection', '2-catalog', '3-policy'])
def test_contract_99af9b9ac486(published_planning, scenario):
    # Denied source contains sentinel and exception includes sensitive environment
    try:
        _s7_integrity_guard(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_99AF9B9AC486')
        raise


@pytest.mark.cer_assertion('ASSERT_F031D2D60A88')
@pytest.mark.parametrize("scenario", ['valid', 'publication-failure', 'episode-counters'])
def test_contract_f031d2d60a88(published_planning, scenario):
    try:
        _s7_no_mutation(published_planning, scenario) if scenario!='episode-counters' else _s7_budget(published_planning, 'episode-counter')
    except AssertionError:
        print('FAILURE_ID:KQ_F031D2D60A88')
        raise


@pytest.mark.cer_assertion('ASSERT_DB1051A2B636')
def test_contract_db1051a2b636(published_planning):
    # Allowed current source located by rg outside indexed path set
    try:
        _s7_direct(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_DB1051A2B636')
        raise


@pytest.mark.cer_assertion('ASSERT_C773656A60C5')
def test_contract_c773656a60c5(published_planning):
    # Confirmed backend unavailable or timeout then direct source check succeeds/fails
    try:
        _s7_direct(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_C773656A60C5')
        raise


@pytest.mark.cer_assertion('ASSERT_7D065E7B1877')
@pytest.mark.parametrize("scenario", ['pointer', 'projection', 'catalog', 'policy'], ids=['0-pointer', '1-projection', '2-catalog', '3-policy'])
def test_contract_7d065e7b1877(published_planning, scenario):
    # Denied secret-like source and exception environment
    try:
        _s7_integrity_guard(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_7D065E7B1877')
        raise


@pytest.mark.cer_assertion('ASSERT_C442B3B56FCE')
@pytest.mark.parametrize("scenario", ['same', 'unrelated-file', 'related-source', 'task-change'], ids=['0-same', '1-unrelated-file', '2-related-source', '3-task-change'])
def test_contract_c442b3b56fce(published_planning, scenario):
    # Prior record reused after permission/dependent-source changes
    try:
        _s7_recovery(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_C442B3B56FCE')
        raise


@pytest.mark.cer_assertion('ASSERT_F3B89696B975')
@pytest.mark.cer_assertion('ASSERT_CEAD20C83823')
@pytest.mark.cer_assertion('ASSERT_8C43A73A097A')
@pytest.mark.parametrize('scenario', ['matched', 'empty', 'blocked'])
def test_contract_8c43a73a097a(published_planning, scenario):
    try:
        _s7_raw_compatibility(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_8C43A73A097A')
        raise


@pytest.mark.cer_assertion('ASSERT_C9A0D76031FA')
def test_contract_c9a0d76031fa(published_planning):
    # Legal empty, nonempty insufficient, low confidence and ambiguity
    try:
        _s7_zero(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_C9A0D76031FA')
        raise


@pytest.mark.cer_assertion('ASSERT_A92FC8578FE6')
@pytest.mark.parametrize("scenario", ['same', 'unrelated-file', 'related-source', 'task-change'], ids=['0-same', '1-unrelated-file', '2-related-source', '3-task-change'])
def test_contract_a92fc8578fe6(published_planning, scenario):
    # Equivalent reordered scope, changed relevant input and unrelated index switch
    try:
        _s7_recovery(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_A92FC8578FE6')
        raise


@pytest.mark.cer_assertion('ASSERT_E4C91B5029D5')
@pytest.mark.parametrize("scenario", ["matched", "empty", "insufficient", "unknown"])
def test_contract_e4c91b5029d5(published_planning, scenario):
    # Every allowed outcome/reason and unknown/mismatched pair
    try:
        _s7_closed_pairs(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_E4C91B5029D5')
        raise


@pytest.mark.cer_assertion('ASSERT_E042DE12D872')
def test_contract_e042de12d872(published_planning):
    # Actual core returns insufficient_match and [] after all prerequisites and no higher-priority signal
    try:
        _s7_zero(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_E042DE12D872')
        raise


@pytest.mark.cer_assertion('ASSERT_D0C9017CF9BC')
def test_contract_d0c9017cf9bc(published_planning):
    # Confirmed absence/backend unavailable/timeout contrasted unknown failure
    try:
        _s7_direct(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_D0C9017CF9BC')
        raise


@pytest.mark.cer_assertion('ASSERT_8A097832E3DF')
@pytest.mark.parametrize("scenario", ['terminal-reserve', 'utf8-cumulative-writer'])
def test_contract_8a097832e3df(published_planning, scenario):
    try:
        _s7_output(published_planning) if scenario=='terminal-reserve' else _s7_delivery_boundary(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_8A097832E3DF')
        raise


@pytest.mark.cer_assertion('ASSERT_325E95636B4D')
@pytest.mark.parametrize("scenario", ['pointer', 'projection', 'catalog', 'policy'], ids=['0-pointer', '1-projection', '2-catalog', '3-policy'])
def test_contract_325e95636b4d(published_planning, scenario):
    # Binding/hash mismatch or denied path plus []
    try:
        _s7_integrity_guard(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_325E95636B4D')
        raise


@pytest.mark.cer_assertion('ASSERT_0DBBDB9AF5F0')
@pytest.mark.parametrize("scenario", ['unknown-empty', 'blocked-empty', 'matched-empty'], ids=['0-unknown-empty', '1-blocked-empty', '2-matched-empty'])
def test_contract_0dbbdb9af5f0(published_planning, scenario):
    # Exit0 blocked, malformed/truncated JSON, valid JSON nonzero, cancelled/timedout process and invalid source hash
    try:
        _s7_unknown(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_0DBBDB9AF5F0')
        raise


@pytest.mark.cer_assertion('ASSERT_9C582F662DBB')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_9c582f662dbb(published_planning, scenario):
    # Tracked [query] enabled/stages/four budgets plus malicious override command/path/consumer
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_9C582F662DBB')
        raise


@pytest.mark.cer_assertion('ASSERT_1907855D27FB')
def test_planning_request_structure_guard(published_planning):
    # Invalid request/config or denied policy/path
    try:
        _s7_blocked(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_1907855D27FB')
        raise


@pytest.mark.cer_assertion('ASSERT_EB0D7FBF2CC9')
@pytest.mark.parametrize("scenario", ['traversal', 'absolute', 'symlink', 'missing'], ids=['0-traversal', '1-absolute', '2-symlink', '3-missing'])
def test_contract_eb0d7fbf2cc9(published_planning, scenario):
    # Relative paths, nonexistent path, traversal and symlink escape
    try:
        _s7_paths(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_EB0D7FBF2CC9')
        raise


@pytest.mark.cer_assertion('ASSERT_C3ED964D28B0')
@pytest.mark.parametrize("scenario", ["matched", "empty", "insufficient", "unknown"])
def test_contract_c3ed964d28b0(published_planning, scenario):
    # Real core legal insufficient empty/nonempty plus unknown empty
    try:
        _s7_closed_pairs(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_C3ED964D28B0')
        raise


@pytest.mark.cer_assertion('ASSERT_69398B597306')
def test_contract_69398b597306(published_planning):
    # All diagnostics and existing memlog/execution records
    try:
        _s7_schema(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_69398B597306')
        raise


@pytest.mark.cer_assertion('ASSERT_AD31E8B711AA')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_ad31e8b711aa(published_planning, scenario):
    # Unknown fields, illegal values and personal widening
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_AD31E8B711AA')
        raise


@pytest.mark.cer_assertion('ASSERT_CE5ECD0F87CE')
@pytest.mark.parametrize("scenario", ['insufficient', 'low-confidence', 'missing-confidence'], ids=['0-insufficient', '1-low-confidence', '2-missing-confidence'])
def test_contract_ce5ecd0f87ce(published_planning, scenario):
    # Recognized stale/change after trusted publication and permission checks
    try:
        _s7_degraded(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_CE5ECD0F87CE')
        raise


@pytest.mark.cer_assertion('ASSERT_C86932028DD4')
@pytest.mark.parametrize("scenario", ['insufficient', 'low-confidence', 'missing-confidence'], ids=['0-insufficient', '1-low-confidence', '2-missing-confidence'])
def test_contract_c86932028dd4(published_planning, scenario):
    # Absent/below-threshold confidence, recognized ambiguity, verified stale/change
    try:
        _s7_degraded(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_C86932028DD4')
        raise


@pytest.mark.cer_assertion('ASSERT_59796BEEEC1F')
@pytest.mark.parametrize("scenario", ['candidate-cap', 'episode-counter'])
def test_contract_59796beeec1f(published_planning, scenario):
    # Mixed failures/timeouts/supplements and cancellation
    try:
        _s7_budget(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_59796BEEEC1F')
        raise


@pytest.mark.cer_assertion('ASSERT_F3B89696B975')
@pytest.mark.cer_assertion('ASSERT_CEAD20C83823')
@pytest.mark.cer_assertion('ASSERT_3FD712CCE882')
def test_contract_3fd712cce882(published_planning):
    _s7_exit_zero_blocked(published_planning)


@pytest.mark.cer_assertion('ASSERT_B09FE8B2FF4C')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_b09fe8b2ff4c(published_planning, scenario):
    # Tracked query config plus smaller legal published-policy/caller/personal values and invalid bool/zero/negative/unknown values
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_B09FE8B2FF4C')
        raise


@pytest.mark.cer_assertion('ASSERT_6A0DFDBB434A')
def test_contract_6a0dfdbb434a(published_planning):
    # Malformed config/request or unsupported identity
    try:
        _s7_blocked(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_6A0DFDBB434A')
        raise


@pytest.mark.cer_assertion('ASSERT_F2E10C1F034C')
@pytest.mark.parametrize("scenario", ["valid", "publication-failure"])
def test_contract_f2e10c1f034c(published_planning, scenario):
    # Query with missing optional dependency
    try:
        _s7_no_mutation(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_F2E10C1F034C')
        raise


@pytest.mark.cer_assertion('ASSERT_AE4526DE3C66')
@pytest.mark.parametrize("scenario", ['defaults', 'personal-narrowing', 'repository-disabled', 'personal-disable', 'remove-required-stage', 'over-hard-cap', 'arbitrary-consumer', 'free-command', 'path-expansion', 'legal-boundary', 'narrow-team'])
def test_contract_ae4526de3c66(published_planning, scenario):
    # Personal/model/natural-language requests to expand scopes, consumers, stages or budgets
    try:
        _s7_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_AE4526DE3C66')
        raise


@pytest.mark.cer_assertion('ASSERT_550968C7B8C5')
@pytest.mark.parametrize("scenario", ['candidate-cap', 'episode-counter'])
def test_planning_closed_episode_does_not_retry_call_cap(published_planning, scenario):
    # Same episode successful, failed, timedout and supplemental attempts
    try:
        _s7_budget(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_550968C7B8C5')
        raise


@pytest.mark.cer_assertion('ASSERT_8FD1E5E14DCA')
def test_contract_8fd1e5e14dca(published_planning):
    # Valid matched candidate with correct/mutated source
    try:
        _s7_hit_read(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_8FD1E5E14DCA')
        raise


@pytest.mark.cer_assertion('ASSERT_20D666972084')
@pytest.mark.parametrize("scenario", ['same', 'unrelated-file', 'related-source', 'task-change'], ids=['0-same', '1-unrelated-file', '2-related-source', '3-task-change'])
def test_contract_20d666972084(published_planning, scenario):
    # Prior read-set with unrelated generation/file change versus related file change
    try:
        _s7_recovery(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_20D666972084')
        raise


@pytest.mark.cer_assertion('ASSERT_D3739660D2DA')
@pytest.mark.parametrize("scenario", ["known-old", "unconfirmed"])
def test_contract_d3739660d2da(published_planning, scenario):
    # Catalog snapshot differs from HEAD
    try:
        _s7_snapshot_truth_guard(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_D3739660D2DA')
        raise


@pytest.mark.cer_assertion('ASSERT_B2ED3F3540EB')
def test_contract_b2ed3f3540eb(published_planning):
    # Required excerpt would exceed remaining ordinary allowance
    try:
        _s7_output(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_B2ED3F3540EB')
        raise


@pytest.mark.cer_assertion('ASSERT_0D09D61E0B4E')
@pytest.mark.parametrize("scenario", ['same', 'unrelated-file', 'related-source', 'task-change'], ids=['0-same', '1-unrelated-file', '2-related-source', '3-task-change'])
def test_contract_0d09d61e0b4e(published_planning, scenario):
    # Resume with unrelated index change or one related source change
    try:
        _s7_recovery(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_0D09D61E0B4E')
        raise


@pytest.mark.cer_assertion('ASSERT_FD1D93782C03')
def test_contract_fd1d93782c03(published_planning):
    # Two equivalent appended hooks in same stage and recovery
    try:
        _s7_duplicate(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_FD1D93782C03')
        raise


@pytest.mark.cer_assertion('ASSERT_5A35CFCD0192')
@pytest.mark.parametrize("scenario", ['pointer', 'projection', 'catalog', 'policy'], ids=['0-pointer', '1-projection', '2-catalog', '3-policy'])
def test_contract_5a35cfcd0192(published_planning, scenario):
    # Trust/authority/unknown error plus stale or []
    try:
        _s7_integrity_guard(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_5A35CFCD0192')
        raise


@pytest.mark.cer_assertion('ASSERT_F3B89696B975')
@pytest.mark.cer_assertion('ASSERT_CEAD20C83823')
@pytest.mark.cer_assertion('ASSERT_035DDCBA7E48')
def test_contract_035ddcba7e48(published_planning):
    # Terminal report with long paths/errors and exhausted ordinary budget
    try:
        _s7_output(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_035DDCBA7E48')
        raise


@pytest.mark.cer_assertion('ASSERT_8B5CFD412697')
def test_contract_8b5cfd412697(published_planning):
    try:
        _s7_generation_switch(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_8B5CFD412697')
        raise


@pytest.mark.cer_assertion('ASSERT_77997046881C')
@pytest.mark.parametrize("scenario", ['terminal-reserve', 'utf8-cumulative-writer'])
def test_contract_77997046881c(published_planning, scenario):
    try:
        _s7_output(published_planning) if scenario=='terminal-reserve' else _s7_delivery_boundary(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_77997046881C')
        raise


@pytest.mark.cer_assertion('ASSERT_EDA461017F8C')
@pytest.mark.parametrize("scenario", [('malformed', None), ('unknown', None), ('max_candidates', True), ('max_candidates', 0), ('max_candidates', -1), ('max_candidates', 1.5), ('max_candidates', '3'), ('max_candidates', 21), ('max_output_bytes', True), ('max_output_bytes', 0), ('max_output_bytes', -1), ('max_output_bytes', 1.5), ('max_output_bytes', '3'), ('max_output_bytes', 131073), ('max_calls', True), ('max_calls', 0), ('max_calls', -1), ('max_calls', 1.5), ('max_calls', '3'), ('max_calls', 6), ('timeout_seconds', True), ('timeout_seconds', 0), ('timeout_seconds', -1), ('timeout_seconds', 1.5), ('timeout_seconds', '3'), ('timeout_seconds', 61), ('max_output_bytes', 4095)], ids=["0-('malformed', None)", "1-('unknown', None)", "2-('max_candidates', True)", "3-('max_candidates', 0)", "4-('max_candidates', -1)", "5-('max_candidates', 1.5)", "6-('max_candidates', '3')", "7-('max_candidates', 21)", "8-('max_output_bytes', True)", "9-('max_output_bytes', 0)", "10-('max_output_bytes', -1)", "11-('max_output_bytes', 1.5)", "12-('max_output_bytes', '3')", "13-('max_output_bytes', 131073)", "14-('max_calls', True)", "15-('max_calls', 0)", "16-('max_calls', -1)", "17-('max_calls', 1.5)", "18-('max_calls', '3')", "19-('max_calls', 6)", "20-('timeout_seconds', True)", "21-('timeout_seconds', 0)", "22-('timeout_seconds', -1)", "23-('timeout_seconds', 1.5)", "24-('timeout_seconds', '3')", "25-('timeout_seconds', 61)", "26-('max_output_bytes', 4095)"])
def test_contract_eda461017f8c(published_planning, scenario):
    # Boundary matrix bool,zero,negative,float,string,overcap and output4095/4096
    try:
        _s7_invalid_config(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_EDA461017F8C')
        raise


@pytest.mark.cer_assertion('ASSERT_1907855D27FB')
@pytest.mark.parametrize('invalid', [{'query': None}, {'query': ''}, {'schema_version': 'unknown'}], ids=['null-query', 'empty-query', 'unknown-schema'])
def test_planning_request_structure(published_planning, invalid):
    """AD-6: malformed query identity is never an empty-match success."""
    _s7_write_config(published_planning)
    output = _planning_operation(published_planning, **invalid)
    try:
        assert output['outcome'] == 'blocked'
        assert output['reason_code'] == 'invalid_request'
        assert not output['candidates'] and not output['read_set']
    except AssertionError:
        print('FAILURE_ID:KQ_1907855D27FB')
        raise


@pytest.mark.cer_assertion('ASSERT_F3B89696B975')
@pytest.mark.cer_assertion('ASSERT_CEAD20C83823')
@pytest.mark.cer_assertion('ASSERT_1B2DEF4F4ED8')
def test_planning_attempt_deadline(published_planning, monkeypatch):
    """AD-3: the attempt deadline cannot restart for each Git child."""
    import subprocess
    import time
    _s7_write_config(published_planning, timeout_seconds=1)
    root, _, _ = published_planning
    spawn = subprocess.Popen
    reached = []
    def delayed(argv, *args, **kwargs):
        if list(argv[:3]) == ['git', '-C', str(root)]:
            reached.append(list(argv))
            return spawn([sys.executable, '-c',
                'import os,sys,time; time.sleep(.6); os.execvp(sys.argv[1],sys.argv[1:])',
                *argv], *args, **kwargs)
        return spawn(argv, *args, **kwargs)
    start = time.monotonic()
    with monkeypatch.context() as patch:
        patch.setattr(subprocess, 'Popen', delayed)
        output = _planning_operation(published_planning)
    assert reached, 'AUTHOR_BINDING: no real child reached the delay boundary'
    try:
        assert (output['outcome'], output['reason_code']) == ('unavailable', 'timeout')
        assert time.monotonic() - start < 1.75
        assert not output['candidates'] and not output['read_set']
    except AssertionError:
        print('FAILURE_ID:KQ_1B2DEF4F4ED8')
        raise


@pytest.mark.cer_assertion('ASSERT_F3B89696B975')
@pytest.mark.cer_assertion('ASSERT_CEAD20C83823')
@pytest.mark.cer_assertion('ASSERT_550968C7B8C5')
def test_planning_closed_episode_does_not_retry(published_planning, monkeypatch):
    """AD-3: delivery exhaustion closes the episode even below call cap."""
    _s7_write_config(published_planning, max_output_bytes=4096)
    root, _, _ = published_planning
    record = root/'execution-plans/example/memlog.md'
    record.write_text('# Existing caller record\n', encoding='utf-8')
    calls = []
    original = core.query_with_diagnostics
    def observed(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(core, 'query_with_diagnostics', observed)
        first = _planning_operation(published_planning, record_path=record.relative_to(root).as_posix())
        prior = record.read_bytes()
        second = _planning_operation(published_planning, record_path=record.relative_to(root).as_posix())
    try:
        assert first['outcome'] == 'budget_exhausted'
        assert second['episode_id'] == first['episode_id']
        assert len(calls) == 1
        assert second['budget_usage']['calls'] == 1
        assert second['diagnostic']['closed'] is True
        assert record.read_bytes().startswith(prior)
    except AssertionError:
        print('FAILURE_ID:KQ_550968C7B8C5')
        raise


# ADR-0048/AD-5 and ADR-0041: only the semantic transport is scripted. The
# public caller, source adapter, native compiler and record writers stay real.
def _vdd_public_run(published_vdd_base, tmp_path_factory, mode='enabled'):
    import shutil
    root = tmp_path_factory.mktemp('vdd-public-consumption')
    shutil.copytree(published_vdd_base, root, dirs_exist_ok=True)
    for name in ('scripts', '.agents/skills/vdd-execution-plan',
                 '.agents/skills/quick-dev-tdd-adapter'):
        shutil.copytree(ROOT / name, root / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    _put(root, 'src/compiler.py', b'VALUE = 1\n')
    _put(root, 'tests/test_compile.py',
         b'import runpy\nimport pytest\nfrom pathlib import Path\n@pytest.mark.cer_assertion("ASSERT-COMPILE")\ndef test_compile():\n'
         b'    assert runpy.run_path(str(Path(__file__).parents[1]/"src/compiler.py"))["VALUE"] == 1\n')
    _put(root, 'requirements.md',
         b'# FR-1\nRetain the existing VALUE = 1 in `src/compiler.py`; '
         b'keep its regression `tests/test_compile.py`. '
         b'`src/proposed.py` is a proposal, not existing implementation.\n')
    config = root / 'knowledge/planning-query.toml'
    config.write_text(config.read_text().replace('max_candidates = 12', 'max_candidates = 1'), encoding='utf-8')
    if mode == 'disabled':
        config.write_text(config.read_text().replace('enabled = true', 'enabled = false'), encoding='utf-8')
    if mode == 'unknown-fact':
        requirement=root/'requirements.md'
        requirement.write_text(requirement.read_text() + '\nThis decision requires verified current facts from `src/unknown.py`; unresolved facts must stop dependent scope.\n',encoding='utf-8')
    # Materialize only real, currently selected source bytes. No publisher,
    # knowledge generation, BMAD skill installation or reviewer is invoked.
    catalog = json.loads((root/'knowledge/catalogs/repository-knowledge-catalog.v2.json').read_text())
    policies = json.loads((root/'knowledge/policies/consumer-policies.v2.json').read_text())
    policy = next(p for p in policies['policies'] if p['consumer'] == 'vdd')
    preview = core.locate({'consumer':'vdd', 'query':'current source callers tests contracts requirements.md'},
                          catalog, policy=policy, max_candidates=1)
    for candidate in preview.get('candidates', []):
        name = candidate['path']
        assert not name.startswith(('_bmad/', '.agents/skills/jimuyun-')), name
        if not (root/name).exists():
            data = subprocess.check_output(['git','-C',str(ROOT),'show',
                catalog['source_snapshot']['commit'] + ':' + name], timeout=10)
            _put(root, name, data)
    runner = r'''
import copy, importlib.util, json, sys
from pathlib import Path
root=Path(sys.argv[1]); mode=sys.argv[2]; sys.path[:0]=[str(root/'scripts/sc'),str(root/'.agents/skills/vdd-execution-plan/scripts'),str(root)]
import _llm_backend
spec=importlib.util.spec_from_file_location('fixture_data', root/'.agents/skills/vdd-execution-plan/scripts/tests/test_ch456_compiler_closure.py')
data=importlib.util.module_from_spec(spec); spec.loader.exec_module(data)
expected=data._cache('src/compiler.py','tests/test_compile.py')
old_oid=expected['v3']['acceptances'][0]['obligation_ids'][0]
raw=expected['v1-FR-1']['obligations'][0]
raw.update(subject='existing compiler VALUE',trigger='existing VALUE is reused',state_before='VALUE = 1 implemented',
    state_after='VALUE = 1 retained',expected_behavior='reuse existing VALUE = 1 with its regression',
    observable_result='src/compiler.py VALUE equals 1; tests/test_compile.py verifies it',
    forbidden_result=['duplicate src/proposed.py implementation'])
from semantic_compiler import _normalize_obligation
new_oid=_normalize_obligation({'requirement_id':'FR-1','source_ref':'requirements.md#FR-1'},raw)['obligation_id']
expected=json.loads(json.dumps(expected).replace(old_oid,new_oid))
acceptance=expected['v3']['acceptances'][0]
acceptance.update(given='existing src/compiler.py VALUE = 1',when='the existing regression executes',
    then='retain VALUE = 1 without duplicate implementation',
    oracle={'observable':'src/compiler.py VALUE','expected':'1','forbidden':['duplicate implementation']})
hint=expected['v3']['slice_hints'][0]
hint.update(behavior_change='reuse existing VALUE = 1',state_transition='existing->retained')
if mode == 'unknown-fact':
    expected['v1-FR-1']['obligations'][0]['unresolved_fragments']=['Required current source fact unavailable: src/unknown.py']
trace=[]
def transport(**kwargs):
    stage=Path(kwargs['output_last_message']).name.split('-last-message')[0]
    payload=json.loads(kwargs['prompt'].rsplit('\n\nINPUT:\n',1)[1])
    trace.append({'stage':stage,'payload':payload,'sandbox':kwargs.get('codex_sandbox')})
    if stage.startswith('v1-'): answer=copy.deepcopy(expected['v1-FR-1'])
    elif stage.startswith('v3'): answer=copy.deepcopy(expected['v3'])
    elif stage == 'v4-atomic-recall': answer=copy.deepcopy(expected['v4-atomic-recall'])
    else: raise AssertionError('Unexpected semantic stage: '+stage)
    Path(kwargs['output_last_message']).write_text(json.dumps(answer),encoding='utf-8')
    return 0,'scripted semantic candidate; no model invocation',['deterministic-semantic-transport']
_llm_backend.run_llm_exec=transport
spec=importlib.util.spec_from_file_location('public_vdd',root/'scripts/vdd/compile_plan.py')
entry=importlib.util.module_from_spec(spec); spec.loader.exec_module(entry)
sys.argv=[str(root/'scripts/vdd/compile_plan.py'),'--requirements',str(root/'requirements.md'),
          '--out-dir',str(root/'execution-plans/sample'),'--stop-after','v3']
try: code=entry.main()
finally: (root/'transport-trace.json').write_text(json.dumps(trace),encoding='utf-8')
raise SystemExit(code)
'''
    proc = subprocess.run([sys.executable, '-B', '-c', runner, str(root), mode],
        cwd=root, capture_output=True, text=True, timeout=60, shell=False)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    result = json.loads(lines[-1]) if lines else {}
    return {'root':root, 'process':proc, 'result':result,
            'trace':json.loads((root/'transport-trace.json').read_text())}


@pytest.fixture(scope='module')
def vdd_public_consumption(published_vdd_base, tmp_path_factory):
    return _vdd_public_run(published_vdd_base, tmp_path_factory)


@pytest.fixture(scope='module')
def vdd_disabled_consumption(published_vdd_base, tmp_path_factory):
    return _vdd_public_run(published_vdd_base, tmp_path_factory, 'disabled')


@pytest.fixture(scope='module')
def vdd_unknown_consumption(published_vdd_base, tmp_path_factory):
    return _vdd_public_run(published_vdd_base, tmp_path_factory, 'unknown-fact')


def _vdd_current_episode(sample):
    assert sample['process'].returncode == 0, (sample['result'], sample['process'].stderr)
    assert sample['result']['status'] == 'paused', sample['result']
    assert sample['result']['completed_checks'] == ['V3','V3A','V3-execution-preflight']
    assert sample['trace'] and any(t['stage'].startswith('v3') for t in sample['trace'])
    # This is an actual public caller/native validator execution with scripted
    # author input, explicitly not real-model or end-to-end delivery evidence.
    observations = sample['trace'][0]['payload']['planning_source_observations']
    assert observations['status'] == 'prepared' and observations['queried']
    query = observations['query_result']
    assert query['outcome'] == 'hit' and query['read_set'], query
    return query


def _assert_vdd_caller_record(sample, query):
    """Read the actual native journal, not the adapter's advice or status."""
    import re
    root=sample['root']; output=root/'execution-plans/sample'
    text=(output/'execution-record.md').read_text(encoding='utf-8')
    caller=re.sub(r'<!-- planning-query\.v1 .*?-->', '', text, flags=re.S)
    rows=[json.loads(line) for line in caller.splitlines() if line.startswith('{')]
    rows=[row for row in rows if row.get('kind')=='planning-source-decision']
    reads={read['path']:read for read in query['read_set']}
    by_path={row['path']:row for row in rows}
    assert len(rows)==len(by_path)==len(reads) and set(by_path)==set(reads)
    checkpoint=Path(sample['result']['checkpoint']['path'])
    contract=checkpoint.relative_to(output).as_posix()
    candidate=json.loads(checkpoint.read_text(encoding='utf-8'))['candidate']
    hint=candidate['slice_hints'][0]
    for name,read in reads.items():
        row=by_path[name]
        assert row['consumer']=='vdd' and row['stage']==query['stage']
        assert row['task_id']=='execution-plans/sample' and row['episode_id']==query['episode_id']
        assert row['query_topic']=='current source callers tests contracts requirements.md'
        assert row['raw_status']==query['diagnostic'].get('raw_status') and row['outcome']==query['outcome']
        assert row['sha256']==read['sha256'] and row['read_identity']==read['read_identity']
        assert row['origin']==read['origin'] and row['reason']
        assert row['actual_use']['contract']==contract and row['actual_use']['effect']
        assert row['authority']=='observation-only' and row['authorizes']==[]
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==read['sha256'].removeprefix('sha256:')
    for name in ('src/compiler.py','tests/test_compile.py'):
        assert by_path[name]['decision']=='accepted'
        assert by_path[name]['actual_use']['obligation_ids']==sorted(hint['obligation_ids'])
    for item in query['candidates']:
        name=item['path']
        if name not in {*hint['production_owners'],*hint['execution_snapshot_paths'],'requirements.md'}:
            assert by_path[name]['decision']=='rejected'
            assert by_path[name]['actual_use']['effect']=='excluded from scope adoption'


@pytest.mark.cer_assertion('ASSERT_F3B89696B975')
@pytest.mark.cer_assertion('ASSERT_54829FE46AF9')
@pytest.mark.cer_assertion('ASSERT_CEAD20C83823')
@pytest.mark.cer_assertion('ASSERT_5F92AC05BCFA')
@pytest.mark.cer_assertion('ASSERT_3DAF23250361')
@pytest.mark.cer_assertion('ASSERT_63783142FD7B')
@pytest.mark.cer_assertion('ASSERT_4C1B8DE3882C')
@pytest.mark.cer_assertion('ASSERT_9E29614CA1B7')
@pytest.mark.cer_assertion('ASSERT_C5739C9FC820')
@pytest.mark.cer_assertion('ASSERT_F7FB563211E4')
def test_contract_f7fb563211e4(vdd_public_consumption):
    sample = vdd_public_consumption
    query = _vdd_current_episode(sample)
    try:
        _assert_vdd_caller_record(sample, query)
    except AssertionError:
        print('FAILURE_ID:KQ_3DAF23250361')
        print('FAILURE_ID:KQ_63783142FD7B')
        print('FAILURE_ID:KQ_4C1B8DE3882C')
        print('FAILURE_ID:KQ_9E29614CA1B7')
        print('FAILURE_ID:KQ_C5739C9FC820')
        print('FAILURE_ID:KQ_F7FB563211E4')
        raise



@pytest.mark.cer_assertion('ASSERT_05552304BD9E')
def test_contract_05552304bd9e(vdd_public_consumption):
    query = _vdd_current_episode(vdd_public_consumption)
    assert query['consumer'] == 'vdd'
    assert all(t['sandbox'] == 'read-only' for t in vdd_public_consumption['trace'])
    assert not (vdd_public_consumption['root']/'src/proposed.py').exists()


# ADR-0048: each group observes a distinct public consumer boundary. Native
# outputs below are evaluated, never authored by a fake receipt/plan writer.
@pytest.mark.cer_assertion('ASSERT_F3B89696B975')
@pytest.mark.cer_assertion('ASSERT_54829FE46AF9')
@pytest.mark.cer_assertion('ASSERT_CEAD20C83823')
@pytest.mark.cer_assertion('ASSERT_8E3D097B669C')
@pytest.mark.cer_assertion('ASSERT_121ED996CEAE')
@pytest.mark.cer_assertion('ASSERT_A37D4E43898B')
@pytest.mark.cer_assertion('ASSERT_2678EA925C89')
@pytest.mark.cer_assertion('ASSERT_996BF56C8518')
@pytest.mark.cer_assertion('ASSERT_314A186BF90E')
@pytest.mark.cer_assertion('ASSERT_E4C02160E0CC')
@pytest.mark.cer_assertion('ASSERT_03668F0ADF94')
def test_contract_8e3d097b669c(vdd_public_consumption):
    sample = vdd_public_consumption
    query = _vdd_current_episode(sample)
    root = sample['root']
    reads = {r['path']:r for r in query['read_set']}
    assert {'requirements.md','src/compiler.py','tests/test_compile.py'} <= reads.keys()
    assert 'src/compiler.py' not in {c['path'] for c in query['candidates']}
    for name in ('src/compiler.py','tests/test_compile.py'):
        actual = (root/name).read_bytes()
        assert reads[name]['origin'] == 'direct-source'
        assert reads[name]['sha256'].removeprefix('sha256:') == hashlib.sha256(actual).hexdigest()
        assert reads[name]['read_identity'] and reads[name]['excerpt_range']
    assert 'VALUE = 1' in reads['src/compiler.py']['excerpt']
    assert 'def test_compile' in reads['tests/test_compile.py']['excerpt']
    # Query/source reads are already present at V1, before any V3 boundary.
    assert sample['trace'][0]['stage'].startswith('v1-')
    assert all(t['payload']['planning_source_observations']['query_result']['read_set'] == query['read_set']
               for t in sample['trace'])
    v3 = next(t['payload'] for t in sample['trace'] if t['stage'].startswith('v3'))
    assert 'VALUE = 1 implemented' == v3['obligations'][0]['state_before']
    checkpoint = next((root/'execution-plans/sample/.compiler-work/v3-checkpoints').glob('*.json'))
    candidate = json.loads(checkpoint.read_text())['candidate']
    hint = candidate['slice_hints'][0]
    assert hint['production_owners'] == ['src/compiler.py']
    assert hint['execution_snapshot_paths'] == ['tests/test_compile.py']
    assert hint['planned_new_files'] == [] and not (root/'src/proposed.py').exists()
    assert 'src/proposed.py' in (root/'requirements.md').read_text()


@pytest.mark.cer_assertion('ASSERT_F3B89696B975')
@pytest.mark.cer_assertion('ASSERT_CEAD20C83823')
@pytest.mark.cer_assertion('ASSERT_14832D388C3C')
@pytest.mark.cer_assertion('ASSERT_FD756962A671')
@pytest.mark.cer_assertion('ASSERT_01DA6B7A91DC')
def test_contract_14832d388c3c(vdd_public_consumption, vdd_disabled_consumption):
    _vdd_current_episode(vdd_public_consumption)
    other = vdd_disabled_consumption
    assert other['process'].returncode == 0 and other['result']['status'] == 'paused'
    prepared = other['trace'][0]['payload']['planning_source_observations']
    assert not prepared['queried']
    query = prepared['query_result']
    assert (query['outcome'], query['reason_code']) == ('unavailable','disabled')
    assert query['read_set'] and all(r['origin'] == 'direct-source' for r in query['read_set'])
    _assert_vdd_caller_record(other,query)
    # Query enablement cannot create governance/authorization artifacts.
    for sample in (vdd_public_consumption, other):
        root=sample['root']; names=[p.name.lower() for p in (root/'execution-plans/sample').rglob('*') if p.is_file()]
        assert not any(word in name for name in names for word in ('attestation','authorization','conformance','source-freeze'))
        assert not sample['result'].get('authorizes')


@pytest.mark.cer_assertion('ASSERT_113D52ECE151')
@pytest.mark.cer_assertion('ASSERT_7F6AF9FDD617')
@pytest.mark.cer_assertion('ASSERT_B347CD2195F2')
def test_contract_113d52ece151(vdd_unknown_consumption):
    sample=vdd_unknown_consumption
    assert sample['process'].returncode != 0
    assert sample['result']['status'] == 'repair-vdd'
    assert 'active-unresolved' in json.dumps(sample['result']), sample['result']
    assert not any(t['stage'].startswith('v3') for t in sample['trace'])
    assert not list((sample['root']/'execution-plans/sample/.compiler-work').glob('v3-checkpoints/*.json'))
    assert not sample['result'].get('authorizes')


@pytest.mark.cer_assertion('ASSERT_6C6853493E27')
@pytest.mark.cer_assertion('ASSERT_09A30E743B67')
@pytest.mark.parametrize('phase,env_mode,explicit,enabled,source',[
    (None,None,None,False,'phase-service-state'),
    ('development',None,None,False,'phase-service-state'),
    ('test',None,None,True,'phase-service-state'),
    ('production',None,None,True,'phase-service-state'),
    ('development','on',None,True,'environment'),
    ('production','off',None,False,'environment'),
    ('development','on','off',False,'parameter'),
    ('production','off','on',True,'parameter')])
def test_contract_6c6853493e27(phase,env_mode,explicit,enabled,source):
    import importlib.util
    spec=importlib.util.spec_from_file_location('s10_governance',ROOT/'.agents/skills/quick-dev-tdd-adapter/tools/governance_policy.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    env={}
    if phase is not None:env['PHASEA_SERVICE_STATE']=phase
    if env_mode is not None:env['JIMUYUN_GOVERNANCE_MODE']=env_mode
    actual=module.resolve_governance_policy(explicit,environment=env)
    assert actual['enabled'] is enabled and actual['source'] == source


@pytest.mark.cer_assertion('ASSERT_812769EB2D98')
@pytest.mark.cer_assertion('ASSERT_891AB647E730')
@pytest.mark.parametrize('matched',[False,True])
def test_contract_812769eb2d98(published_planning,matched):
    assert _s7_required_gate(published_planning,nonempty=matched) in {'required_modules_unsatisfied','locator_result_not_matched'}


@pytest.mark.cer_assertion('ASSERT_CEAD20C83823')
@pytest.mark.cer_assertion('ASSERT_7694233DB1C7')
def test_contract_7694233db1c7(published_planning,monkeypatch):
    root,paths,request=published_planning
    _s7_write_config(published_planning)
    record=root/'execution-plans/example/memlog.md'
    _put(root,record.relative_to(root),b'# Existing native caller record\n')
    calls=[]
    real=core.query_with_diagnostics
    def observed(*args,**kwargs):
        calls.append(args[0]); return real(*args,**kwargs)
    monkeypatch.setattr(core,'query_with_diagnostics',observed)
    first=_planning_operation(published_planning,record_path=record.relative_to(root).as_posix())
    second=_planning_operation(published_planning,record_path=record.relative_to(root).as_posix())
    assert first['episode_id'] == second['episode_id'] and len(calls) == 1
    assert second['budget_usage']['calls'] == first['budget_usage']['calls'] == 1
    assert (root/'knowledge/planning-query.toml').is_file()
    assert first['budget_usage']['calls'] == 1


def _s10_guards():
    import importlib.util
    spec=importlib.util.spec_from_file_location('s10_retained_boundaries',ROOT/'tests/toolchain/knowledge_query/test_planning_boundaries.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.cer_assertion('ASSERT_5F92AC05BCFA')
@pytest.mark.cer_assertion('ASSERT_5165AA0D7344')
@pytest.mark.cer_assertion('ASSERT_B34E35470A88')
@pytest.mark.cer_assertion('ASSERT_6C0520FE0D5E')
def test_contract_5165aa0d7344():
    guards=_s10_guards()
    guards.package_guard(); guards.native_guard()


@pytest.mark.cer_assertion('ASSERT_5F92AC05BCFA')
@pytest.mark.cer_assertion('ASSERT_CE33174BFA28')
@pytest.mark.cer_assertion('ASSERT_01ABAC86036B')
@pytest.mark.cer_assertion('ASSERT_40CE012D7173')
def test_contract_ce33174bfa28():
    guards=_s10_guards()
    guards.scope_guard(); guards.authority_guard(); guards.dependency_guard()


@pytest.mark.cer_assertion('ASSERT_54829FE46AF9')
@pytest.mark.cer_assertion('ASSERT_5F92AC05BCFA')
@pytest.mark.cer_assertion('ASSERT_58D790ED2D22')
@pytest.mark.cer_assertion('ASSERT_11A7E3CEF26B')
def test_contract_58d790ed2d22(vdd_public_consumption):
    _vdd_current_episode(vdd_public_consumption)
    _current_windows_runtime_evidence()



@pytest.mark.cer_assertion('ASSERT_06A867E00BC5')
@pytest.mark.cer_assertion('ASSERT_BA9A0474912A')
@pytest.mark.cer_assertion('ASSERT_B7A571632018')
@pytest.mark.cer_assertion('ASSERT_F3B89696B975')
@pytest.mark.cer_assertion('ASSERT_54829FE46AF9')
@pytest.mark.cer_assertion('ASSERT_CEAD20C83823')
@pytest.mark.cer_assertion('ASSERT_5F92AC05BCFA')
def test_windows_planning_query_runtime_evidence():
    _current_windows_runtime_evidence()


# ADR-0048: current publication admission and permission-bound reuse.
@pytest.mark.cer_assertion('ASSERT_2E09F07252E1')
@pytest.mark.parametrize('missing', ['catalog', 'policy', 'projection', 'uninstalled'])
def test_contract_2e09f07252e1_public_caller_missing_component(published_vdd_base, tmp_path, monkeypatch, capsys, missing):
    root = tmp_path / 'caller'
    shutil.copytree(published_vdd_base, root)
    requirement = _put(root, 'requirements.md', b'# FR-1\nRetain existing source.\n')
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
    try:
        if missing == 'uninstalled':
            assert code == 0 and reached == [True]
        else:
            assert code != 0 and reached == [], 'Existing publication corruption reached semantic compilation'
            assert 'PLANNING_QUERY_BLOCKED:' in result.get('reason', '')
    except AssertionError:
        print('FAILURE_ID:KQ_2E09F07252E1')
        raise

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
        _put(generation_root, relative, payload)
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
    _put(generation_root, 'manifest.json', manifest_bytes)
    paths[1].write_bytes(updates['policy'])
    paths[2].write_bytes(updates['projections'])
    pointer = {**old, 'generation_id': generation,
               'generation_sha256': 'sha256:' + hashlib.sha256(manifest_bytes).hexdigest()}
    pointer_path.write_text(json.dumps(pointer), encoding='utf-8')
    assert core.verify_current_publication(root, catalog_path=paths[0],
        policy_path=paths[1], projections_path=paths[2])
    return policy, projection, pointer


@pytest.mark.cer_assertion('ASSERT_C442B3B56FCE')
@pytest.mark.parametrize('change', ['same', 'unrelated-generation', 'permission-revoked'])
def test_contract_c442b3b56fce_current_permissions(published_planning, monkeypatch, change):
    root, paths, request = published_planning
    _s7_write_config(published_planning)
    record = root / 'execution-plans/example/memlog.md'
    record.write_text('# Isolated diagnostic record\n', encoding='utf-8')
    options = {'record_path': record.relative_to(root).as_posix()}
    real_query = core.query_with_diagnostics
    calls = []
    def traced(*args, **kwargs):
        calls.append(True)
        return real_query(*args, **kwargs)
    monkeypatch.setattr(core, 'query_with_diagnostics', traced)
    first = _planning_operation(published_planning, **options)
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
    second = _planning_operation(published_planning, **options)
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
    try:
        assert allowed, 'A revoked candidate survived current policy/projection checks'
        if change != 'permission-revoked':
            assert second['diagnostic'].get('reused') is True and len(calls) == 1
            assert second['index_identity'] == first['index_identity']
        else:
            assert not second['diagnostic'].get('reused')
    except AssertionError:
        print('FAILURE_ID:KQ_C442B3B56FCE')
        raise


def _current_windows_runtime_evidence():
    """ADR-0048: verified11-case platform subset, never full acceptance.

    Preserve the13-case historical ZIP separately. This current original covers
    only its explicitly executed runtime nodes; none of the7 P1 cases is claimed.
    Reader-only source edits do not relabel the Windows author/source identity.
    """
    import ast
    import zipfile
    import xml.etree.ElementTree as ET
    evidence = ROOT / 'logs/windows-p1-result-40293104427/verified-original'
    archive = evidence / 'windows-query-verification-40293104427.zip'
    assert len(archive.read_bytes()) == 18327
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == '86428f5351e85929f348a07fca6506c2f9f9c1f9c1cef695bdfc69d404e96429'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist()) == 8
        decode = lambda name: z.read(name).decode('utf-8-sig').strip()
        assert decode('commit.txt') == 'cc70f153f1c4cded4a9dceca408d3faae54f8ad6'
        platform = json.loads(decode('platform.json'))
        assert platform['platform'] == 'win32' and platform['system'].startswith('Windows-2022Server-')
        assert decode('pytest-exit.txt') == '0'
        suite = ET.fromstring(z.read('junit.xml')).find('testsuite')
        assert suite is not None and int(suite.attrib['tests']) == 11
        assert all(int(suite.attrib[k]) == 0 for k in ('errors', 'failures', 'skipped'))
        cases = suite.findall('testcase')
        assert len(cases) == 11 and all(not list(c) for c in cases)
        required = ['test_contract_295a1ed8402c', 'test_contract_8299476377c3[nonzero]', 'test_contract_8299476377c3[unicode-argv]', 'test_contract_f7401102fe99[cancel]', 'test_contract_f7401102fe99[combined]', 'test_contract_f7401102fe99[stderr]', 'test_contract_f7401102fe99[stdout]', 'test_contract_f7401102fe99[timeout]', 'test_contract_f7401102fe99[unicode-argv]', 'test_planning_attempt_deadline', 'test_planning_attempt_deadline_timeout']
        assert {c.attrib['name'] for c in cases} == set(required)
        supervision = json.loads(decode('supervision.json'))
        assert supervision['exit_code'] == 0 and supervision['termination'] is None
        assert supervision['total_seconds'] == 1800 and supervision['silence_seconds'] == 600
        assert {arg.split('::', 1)[1] for arg in supervision['command'] if '.py::' in arg} == set(required)
        expected = {row['Path'].replace('\\', '/').split('/ji-mu-yun/ji-mu-yun/')[-1]: row['Hash'].lower()
                    for row in json.loads(decode('source-hashes.json'))}
        runtime = {'scripts/toolchain/knowledge_query/adapter.py', 'scripts/python/knowledge_locator.py',
                   'scripts/python/_knowledge_locator_core.py', 'knowledge/planning-query.toml'}
        assert set(expected) == runtime | {'scripts/toolchain/knowledge_query/tests/test_planning_query.py'}
        for relative in runtime:
            assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected[relative]
        original = (evidence / 'original-test_planning_query.py').read_bytes()
        assert hashlib.sha256(original).hexdigest() == expected['scripts/toolchain/knowledge_query/tests/test_planning_query.py']
        # Compare actual runtime author code without importing the archived file.
        # Only the3 evidence readers may differ; remove only the non-executed
        # windows-evidence branch of the mixed transport/reader function.
        def runtime_tree(raw):
            parsed = ast.parse(raw)
            parsed.body = [n for n in parsed.body if not (isinstance(n, ast.FunctionDef) and n.name in {
                'test_contract_58d790ed2d22', 'test_windows_planning_query_runtime_evidence',
                '_current_windows_runtime_evidence'})]
            for function in parsed.body:
                if isinstance(function, ast.FunctionDef) and function.name == 'test_contract_f7401102fe99':
                    for branch in function.body:
                        if isinstance(branch, ast.If) and ast.unparse(branch.test) == "scenario == 'windows-evidence'":
                            branch.body = [ast.Pass()]
            return ast.dump(parsed, include_attributes=False)
        assert runtime_tree(original) == runtime_tree(Path(__file__).read_bytes())
