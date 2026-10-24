"""ADR-0048/ADR-0041: shared Locator diagnostics retain legacy CLI behavior."""
import io
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts/python'))
from scripts.toolchain.knowledge_query.adapter import diagnose
import knowledge_locator as cli
import _knowledge_locator_core as core


def _check_diagnostic(condition):
    if not condition:
        print('FAILURE_ID:KQ_CA335D988AF5')
    assert condition


@pytest.mark.cer_assertion('ASSERT_CA335D988AF5')
def test_contract_ca335d988af5(tmp_path, monkeypatch, capsys):
    request = {'schema_version': 'jimuyun.knowledge-locator-request.v1',
               'request_id': 'shared-preflight', 'consumer': 'vdd', 'query': 'contract',
               'snapshot': {'ref': 'refs/heads/main', 'commit': 'a' * 40},
               'policy_revision': 'test-policy'}
    paths = [tmp_path / n for n in ('catalog.json', 'policies.json', 'projections.json')]
    for path, content in zip(paths, [
        {'entries': []},
        {'policy_revision': 'test-policy', 'policies': [{'consumer': 'vdd'}]}, {}]):
        path.write_text(json.dumps(content), encoding='utf-8')
    def run_cli():
        monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(request)))
        monkeypatch.setattr(sys, 'argv', ['knowledge_locator.py', '--repository-root', str(tmp_path),
            '--catalog', str(paths[0]), '--policies', str(paths[1]), '--projections', str(paths[2])])
        code = cli.main()
        output = json.loads(capsys.readouterr().out)
        return code, output
    code, legacy = run_cli()
    assert code == 0 and legacy['status'] == 'blocked'
    assert legacy['request_id'] == request['request_id'] and legacy['snapshot'] == request['snapshot']
    actual = diagnose(request, tmp_path, *paths)
    _check_diagnostic(isinstance(actual, dict) and actual.get('result') == legacy)
    _check_diagnostic(any(d.get('code') == 'snapshot_missing' for d in actual.get('diagnostics', [])))
    # Both callers must use the same real read-only routine, not duplicated checks.
    shared = getattr(core, 'query_with_diagnostics', None)
    _check_diagnostic(callable(shared))
    calls = []
    def tracked(*args, **kwargs):
        calls.append((args, kwargs))
        return shared(*args, **kwargs)
    monkeypatch.setattr(core, 'query_with_diagnostics', tracked)
    repeated = diagnose(request, tmp_path, *paths)
    repeated_code, repeated_legacy = run_cli()
    _check_diagnostic(len(calls) == 2 and repeated == actual and repeated_code == code and repeated_legacy == legacy)


def test_existing_locator_statuses_remain_unchanged():
    catalog = {'entries': [{'path': 'docs/example.md', 'content': 'shared locator', 'source_sha256': 'a' * 64}]}
    assert core.locate({'query': 'shared locator'}, catalog)['status'] == 'matched'
    assert core.locate({'query': 'zzzzunmatched'}, catalog)['status'] == 'insufficient_match'


@pytest.mark.cer_assertion('ASSERT_5CC00384D23A')
def test_contract_5cc00384d23a(tmp_path):
    import _knowledge_catalog_builder as builder
    consumers = builder._consumer_ids('toolchain')
    if 'bmad-planning' not in consumers:
        print('FAILURE_ID:KQ_5CC00384D23A')
    assert 'bmad-planning' in consumers
    request_schema = json.loads((ROOT / 'knowledge/contracts/knowledge-locator-request.v1.schema.json').read_text())
    projection_schema = json.loads((ROOT / 'knowledge/contracts/knowledge-consumer-projections.v1.schema.json').read_text())
    assert 'bmad-planning' in request_schema['properties']['consumer']['enum']
    assert 'bmad-planning' in projection_schema['properties']['projections']['items']['properties']['consumer']['enum']
    policies = json.loads((ROOT / 'knowledge/policies/consumer-policies.v2.json').read_text())
    policy = next(p for p in policies['policies'] if p['consumer'] == 'bmad-planning')
    catalog = {'source_snapshot': {'snapshot_id': 'sha256:' + 'a' * 64}, 'modules': [
        {'module_id': 'allowed', 'source_path': 'docs/example.md', 'semantic_eligible': True,
         'lifecycle': 'repository-source', 'consumer_ids': consumers, 'visibility': {'toolchain': 'active'}}]}
    projection = builder.build_consumer_projections(catalog, policies)
    selected = next(p for p in projection['projections'] if p['consumer'] == policy['consumer'])
    assert selected['eligible_module_ids'] == ['allowed']
    assert projection['catalog_sha256'] == builder.prefixed_sha256(builder.canonical_bytes(catalog))
    assert not list(tmp_path.iterdir())  # Producer calculation does not publish a generation.
    assert not core.verify_current_publication(tmp_path, catalog_path=tmp_path/'catalog.json',
        policy_path=tmp_path/'policy.json', projections_path=tmp_path/'projection.json')


@pytest.mark.cer_assertion('ASSERT_2E09F07252E1')
def test_contract_2e09f07252e1(tmp_path):
    # Installed Locator + missing/corrupt publication must never claim admission.
    paths = [tmp_path / n for n in ('catalog.json', 'policy.json', 'projection.json')]
    request = {'request_id': 'not-admitted', 'consumer': 'bmad-planning', 'query': 'contract',
               'snapshot': {'ref': 'refs/heads/main', 'commit': 'a' * 40}, 'policy_revision': 'test-policy'}
    assert not core.verify_current_publication(tmp_path, catalog_path=paths[0],
        policy_path=paths[1], projections_path=paths[2])
    with pytest.raises(FileNotFoundError):
        diagnose(request, tmp_path, *paths)
    paths[0].write_text('{broken', encoding='utf-8')
    with pytest.raises(json.JSONDecodeError):
        diagnose(request, tmp_path, *paths)
    index = tmp_path / 'knowledge/indexes/current.json'
    index.parent.mkdir(parents=True)
    index.write_text('{broken', encoding='utf-8')
    before = index.read_bytes()
    assert not core.verify_current_publication(tmp_path, catalog_path=paths[0],
        policy_path=paths[1], projections_path=paths[2])
    assert index.read_bytes() == before


def _planning_policy():
    policies = json.loads((ROOT / 'knowledge/policies/consumer-policies.v2.json').read_text())
    return next(p for p in policies['policies'] if p['consumer'] == 'bmad-planning')


def _planning_module(**changes):
    entry = dict(module_id='planning-contract', source_path='docs/example.md',
                 content='planning contract', source_sha256='a' * 64,
                 primary_domain='toolchain', visibility={'toolchain': 'active'},
                 lifecycle='repository-source', status='active',
                 consumer_ids=['bmad-planning'], semantic_eligible=True,
                 enforcement_level='reference')
    entry.update(changes)
    return entry


def _located(entry, query='planning contract'):
    return core.locate({'query': query}, {'modules': [entry]}, policy=_planning_policy())['candidates']


@pytest.mark.cer_assertion('ASSERT_482C87E0D4A0')
def test_contract_482c87e0d4a0():
    policy = _planning_policy()
    assert set(policy['path_prefixes']) == {'.agents/skills/', 'docs/', 'knowledge/', 'execution-plans/', 'scripts/python/'}
    assert set(policy['exact_paths']) == {'AGENTS.md', 'README.md'}
    for path in ['.agents/skills/example/SKILL.md', 'docs/example.md', 'knowledge/example.md',
                 'execution-plans/example/plan.md', 'scripts/python/example.py', 'AGENTS.md', 'README.md']:
        assert _located(_planning_module(source_path=path))
    for path in ['runtime/phase-a/secret.py', 'scripts/toolchain/example.py', 'AGENTS.md.other', 'docs/migration/history.md']:
        assert not _located(_planning_module(source_path=path))
    # Outside-index reads cannot enter a Locator result or gain its provenance.


@pytest.mark.cer_assertion('ASSERT_84C5EA6C39EC')
def test_contract_84c5ea6c39ec():
    policy = _planning_policy()
    assert set(policy['domains']) == {'toolchain', 'phase'}
    assert set(policy['visibility']) == {'active', 'dependency', 'conditional'}
    assert policy['lifecycles'] == ['repository-source']
    assert set(policy['statuses']) == {'active', 'conditional', 'historical'}
    assert policy['historical_mode'] == 'exact-only'
    for domain in ['toolchain', 'phase']:
        for visibility in ['active', 'dependency', 'conditional']:
            assert _located(_planning_module(visibility={domain: visibility}))
    for domain in ['workspace', 'marketplace']:
        assert not _located(_planning_module(primary_domain=domain, visibility={domain: 'active'}))
    assert not _located(_planning_module(lifecycle='workspace'))
    assert not _located(_planning_module(status='retired'))
    assert not _located(_planning_module(status='historical'), 'planning contract')
    assert _located(_planning_module(status='historical'), 'docs/example.md')


@pytest.mark.cer_assertion('ASSERT_BD7C42FF441E')
def test_contract_bd7c42ff441e():
    # Real Locator policy enforcement cannot turn Hosted data into repository sources.
    assert not _located(_planning_module(source_path='logs/phase-a-innernet/workspaces/w/repo/secret.md',
        lifecycle='workspace', primary_domain='workspace', visibility={'workspace': 'active'},
        enforcement_level='required'))
    candidate = _located(_planning_module(enforcement_level='reference'))[0]
    assert candidate['enforcement_level'] == 'reference'
    assert candidate['lifecycle'] == 'repository-source'
    assert candidate['visibility'] == {'toolchain': 'active'}
    assert not any(k in candidate for k in ['hosted_authorization', 'completion', 'acceptance_passed'])


@pytest.mark.cer_assertion('ASSERT_94C2D2FA535D')
def test_contract_94c2d2fa535d(tmp_path):
    import _knowledge_catalog_builder as builder
    policies = json.loads((ROOT / 'knowledge/policies/consumer-policies.v2.json').read_text())
    catalog = {'source_snapshot': {'snapshot_id': 'sha256:' + 'a' * 64}, 'modules': [
        _planning_module(consumer_ids=builder._consumer_ids('toolchain')),
        _planning_module(module_id='outside', source_path='runtime/phase-a/x.py'),
        _planning_module(module_id='unadmitted', consumer_ids=['vdd'])]}
    document = builder.build_consumer_projections(catalog, policies)
    projection = next(p for p in document['projections'] if p['consumer'] == 'bmad-planning')
    assert projection['eligible_module_ids'] == ['planning-contract']
    assert document['catalog_sha256'] == builder.prefixed_sha256(builder.canonical_bytes(catalog))
    assert document['policy_sha256'] == builder.prefixed_sha256(builder.canonical_bytes(policies))
    assert 'bmad-planning' not in builder._consumer_ids('marketplace')
    assert not list(tmp_path.iterdir())


@pytest.mark.cer_assertion('ASSERT_2B5B0BA2BE94')
def test_contract_2b5b0ba2be94(tmp_path):
    paths = [tmp_path / n for n in ('catalog.json', 'policies.json', 'projection.json')]
    paths[0].write_text(json.dumps({'modules': []}), encoding='utf-8')
    paths[1].write_text(json.dumps({'policy_revision': 'test', 'policies': []}), encoding='utf-8')
    paths[2].write_text('{}', encoding='utf-8')
    for consumer in [None, 'bmad-planning']:
        request = dict(request_id='missing-authority', query='planning', consumer=consumer,
                       snapshot={'ref': 'refs/heads/main', 'commit': 'a' * 40}, policy_revision='test')
        output = diagnose(request, tmp_path, *paths)
        assert output['result']['status'] == 'blocked'
        assert output['result']['candidates'] == []
        codes = {d['code'] for d in output['diagnostics']}
        assert 'policy_missing' in codes and 'projection_invalid' in codes
        assert not core.verify_current_publication(tmp_path, catalog_path=paths[0],
            policy_path=paths[1], projections_path=paths[2])


@pytest.mark.cer_assertion('ASSERT_F96ECD3253A2')
def test_contract_f96ecd3253a2(tmp_path):
    paths = [tmp_path / n for n in ('catalog.json', 'policies.json', 'projection.json')]
    paths[0].write_text(json.dumps({'entries': []}), encoding='utf-8')
    paths[1].write_text(json.dumps({'policies': []}), encoding='utf-8')
    paths[2].write_text('{}', encoding='utf-8')
    for stage, consumer in [('prd', 'bmad-planning'), ('spec', 'bmad-planning'),
                            ('architecture', 'bmad-planning'), ('vdd-create', 'vdd'), ('vdd-repair', 'vdd')]:
        request = dict(request_id='stage-' + stage, consumer=consumer, query='planning',
                       snapshot={'ref': 'refs/heads/main', 'commit': 'a' * 40},
                       policy_revision='test', stage=stage)
        output = diagnose(request, tmp_path, *paths)
        if output.get('stage') != stage or output.get('consumer') != consumer:
            print('FAILURE_ID:KQ_F96ECD3253A2')
        assert output.get('stage') == stage and output.get('consumer') == consumer
        assert output['result']['status'] == 'blocked'
        assert 'stage' not in output['result']  # Stage metadata cannot change legacy result schema.


@pytest.fixture
def published_planning(tmp_path):
    """An isolated owner-built publication; never the repository generation."""
    import subprocess
    import _knowledge_catalog_builder as builder
    import publish_knowledge_catalog as publisher
    root = tmp_path / 'isolated-repository'
    root.mkdir()
    def put(path, content):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    for path in ['AGENTS.md', 'README.md']:
        put(path, b'# Repository knowledge authority\nPlanning contract source.\n')
    for path in ['docs/architecture/ADR_INDEX_PHASE.md', 'docs/architecture/ADR_INDEX_GODOT.md',
                 'execution-plans/example/00-index.md']:
        put(path, b'# Isolated planning fixture\n')
    for path in ['scripts/python/knowledge_locator.py', 'scripts/python/_knowledge_locator_core.py']:
        put(path, (ROOT / path).read_bytes())
    for path in publisher.INPUT_PATHS.values():
        put(path, (ROOT / path).read_bytes())
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE).decode().strip()
    git('init', '-b', 'main')
    git('add', '.')
    git('-c', 'user.name=Isolated Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'Isolated publication sources')
    commit = git('rev-parse', 'HEAD')
    policies = json.loads((root / publisher.INPUT_PATHS['policy']).read_text())
    exclusions = json.loads((root / publisher.INPUT_PATHS['exclusions']).read_text())
    layers = builder.build_layers(root, policy=policies, exclusions=exclusions)
    request = dict(schema_version='jimuyun.knowledge-publication-request.v1', request_id='isolated-test',
        caller='maintain-knowledge-base', trigger='operator-requested', target_plan='execution-plans/example',
        main_commit=commit, automatic=False, maintainer_confirmation=True,
        recorded_at='2026-10-23T00:00:00+00:00', authorizes=['knowledge-publication'], source_route=None)
    request_path = Path('logs/knowledge-context/publication-requests/isolated-test.json')
    put(request_path, json.dumps(request).encode())
    authorization = publisher._load_publication_request(root, request_path, expected_main=commit)
    report = dict(snapshot=layers[0], policy_revision=policies['policy_revision'], summary={'fixture': True})
    publisher._publish_bundle(root, main_commit=commit,
        layer_bytes={name: publisher._render(value) for name, value in zip(publisher.LAYER_PATHS, layers)},
        input_bytes={name: (root / path).read_bytes() for name, path in publisher.INPUT_PATHS.items()},
        report_bytes=publisher._render(report), report=report, publication_authorization=authorization)
    paths = [root / publisher.LAYER_PATHS['catalog_v2'], root / publisher.INPUT_PATHS['policy'],
             root / publisher.LAYER_PATHS['projections']]
    request = dict(schema_version='jimuyun.knowledge-locator-request.v1', request_id='planning-test',
        consumer='bmad-planning', stage='prd', query='repository knowledge authority',
        snapshot={'ref': 'refs/heads/main', 'commit': commit}, policy_revision=policies['policy_revision'])
    return root, paths, request


def _query_published(fixture, **overrides):
    root, paths, request = fixture
    return diagnose({**request, **overrides}, root, *paths)


@pytest.mark.cer_assertion('ASSERT_31BA1038EB57')
def test_contract_31ba1038eb57(published_planning):
    for stage in ['prd', 'spec', 'architecture']:
        output = _query_published(published_planning, stage=stage)
        assert output['consumer'] == 'bmad-planning' and output['stage'] == stage
        assert output['result']['status'] == 'matched'
    for stage in ['vdd-create', 'vdd-repair']:
        assert _query_published(published_planning, stage=stage, consumer='vdd')['consumer'] == 'vdd'
    with pytest.raises(ValueError, match='consumer_stage_mismatch'):
        _query_published(published_planning, consumer='bootstrap')


@pytest.mark.cer_assertion('ASSERT_9C72720F8F91')
def test_contract_9c72720f8f91(published_planning):
    test_contract_84c5ea6c39ec()
    test_contract_bd7c42ff441e()
    root, paths, _ = published_planning
    assert core.verify_current_publication(root, catalog_path=paths[0], policy_path=paths[1], projections_path=paths[2])
    for path in paths:
        before = path.read_bytes()
        path.write_bytes(before + b' ')
        assert not core.verify_current_publication(root, catalog_path=paths[0], policy_path=paths[1], projections_path=paths[2])
        assert _query_published(published_planning)['result']['status'] == 'blocked'
        path.write_bytes(before)


@pytest.mark.cer_assertion('ASSERT_9D537AF787EB')
def test_contract_9d537af787eb(published_planning):
    output = _query_published(published_planning)
    assert output['consumer'] == 'bmad-planning'
    assert output['result']['status'] == 'matched'
    for candidate in output['result']['candidates']:
        assert 'bmad-planning' in candidate['consumer_ids']
        assert candidate['lifecycle'] == 'repository-source'
        assert candidate['primary_domain'] in ['toolchain', 'phase']
    test_contract_482c87e0d4a0()


@pytest.mark.cer_assertion('ASSERT_65F3B954FB04')
def test_contract_65f3b954fb04(published_planning):
    output = _query_published(published_planning, stage=None, consumer='unknown')
    assert output['result']['status'] == 'blocked'
    assert 'policy_missing' in {d['code'] for d in output['diagnostics']}
    root, paths, request = published_planning
    policy = json.loads(paths[1].read_text())
    policy['policies'] = [p for p in policy['policies'] if p['consumer'] != 'bmad-planning']
    paths[1].write_text(json.dumps(policy), encoding='utf-8')
    output = _query_published(published_planning)
    assert output['consumer'] == request['consumer'] and output['result']['status'] == 'blocked'


@pytest.mark.cer_assertion('ASSERT_085B1807BD2E')
def test_contract_085b1807bd2e(published_planning):
    test_contract_31ba1038eb57(published_planning)
    output = _query_published(published_planning, stage=None, consumer=None)
    assert output['result']['status'] == 'blocked'
    assert not output['result']['candidates']


@pytest.mark.cer_assertion('ASSERT_B4DDDFEB665F')
def test_contract_b4dddfeb665f(published_planning):
    import hashlib
    root, paths, _ = published_planning
    before = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in root.rglob('*') if p.is_file()}
    output = _query_published(published_planning)
    assert output['result']['status'] == 'matched'
    after = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in root.rglob('*') if p.is_file()}
    assert before == after
    assert core.verify_current_publication(root, catalog_path=paths[0], policy_path=paths[1], projections_path=paths[2])


@pytest.mark.cer_assertion('ASSERT_3F7D90E3D044')
def test_contract_3f7d90e3d044(published_planning):
    root, _, _ = published_planning
    pointer = root / 'knowledge/indexes/current.json'
    original = pointer.read_bytes()
    pointer.unlink()
    output = _query_published(published_planning)
    assert output['result']['status'] == 'blocked' and output['result']['candidates'] == []
    if 'publication_missing' not in {d['code'] for d in output['diagnostics']}:
        print('FAILURE_ID:KQ_3F7D90E3D044')
    assert 'publication_missing' in {d['code'] for d in output['diagnostics']}
    pointer.write_bytes(original + b'corrupt')
    output = _query_published(published_planning)
    if 'integrity_failed' not in {d['code'] for d in output['diagnostics']}:
        print('FAILURE_ID:KQ_3F7D90E3D044')
    assert output['result']['status'] == 'blocked' and output['result']['candidates'] == []
    assert 'integrity_failed' in {d['code'] for d in output['diagnostics']}


@pytest.mark.cer_assertion('ASSERT_850A2D68C126')
def test_contract_850a2d68c126(published_planning, monkeypatch):
    import publish_knowledge_catalog as publisher
    def forbidden(*args, **kwargs):
        raise AssertionError('Query attempted publication')
    monkeypatch.setattr(publisher, '_publish_bundle', forbidden)
    monkeypatch.setattr(publisher, 'run', forbidden)
    test_contract_b4dddfeb665f(published_planning)


@pytest.mark.cer_assertion('ASSERT_D64F7E6FDF45')
def test_contract_d64f7e6fdf45(published_planning):
    test_contract_31ba1038eb57(published_planning)
    test_contract_9d537af787eb(published_planning)
    output = _query_published(published_planning)
    assert not any(k in output for k in ['acceptance_passed', 'implementation_complete', 'authorizes'])


@pytest.mark.cer_assertion('ASSERT_DCF68B1ABA8F')
def test_contract_dcf68b1aba8f(published_planning):
    import publish_knowledge_catalog as publisher
    root, paths, _ = published_planning
    pointer = json.loads((root / 'knowledge/indexes/current.json').read_text())
    manifest, payloads = publisher._generation_payloads(root, pointer)
    assert set(payloads) == publisher.REQUIRED_ARTIFACTS
    policy = json.loads(payloads['policy'])
    catalog = json.loads(payloads['catalog_v2'])
    projection = json.loads(payloads['projections'])
    import _knowledge_catalog_builder as builder
    assert projection == builder.build_consumer_projections(catalog, policy)
    assert any('bmad-planning' in m['consumer_ids'] for m in catalog['modules'])
    assert core.verify_current_publication(root, catalog_path=paths[0], policy_path=paths[1], projections_path=paths[2])


@pytest.mark.cer_assertion('ASSERT_2D078C89F59A')
def test_contract_2d078c89f59a(published_planning):
    test_contract_9c72720f8f91(published_planning)
    test_contract_482c87e0d4a0()
    test_contract_bd7c42ff441e()


# S7 exercises the planning-operation envelope through the real adapter entry.
# Caller metadata is separate from the underlying Locator request and result.
def _planning_operation(fixture, **options):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    root, paths, base = fixture
    request = {**base, 'operation': 'create', 'task_id': 'bounded-planning',
               'scope': ['AGENTS.md'], 'relevant_inputs': {}, **options}
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
    output=_planning_operation(fixture)
    effective=output.get('diagnostic',{}).get('effective_config',{})
    assert effective, 'Actual tracked query configuration is not consumed or reported'
    assert effective.get('max_candidates') <= values.get('max_candidates',12)
    for field, default in [('max_calls',3),('max_output_bytes',65536),('timeout_seconds',30)]:
        assert effective.get(field)==values.get(field,default)
    assert effective.get('origins') and effective.get('consumer')=='bmad-planning'


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


def _s7_corruption(fixture, scenario):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    _s7_write_config(fixture)
    root, paths, _ = fixture
    if scenario == 'pointer':
        (root/'knowledge/indexes/current.json').write_bytes(b'{DENIED_CONTENT_SENTINEL')
    elif scenario == 'projection':
        paths[2].write_bytes(paths[2].read_bytes() + b' ')
    elif scenario == 'catalog':
        paths[0].write_bytes(paths[0].read_bytes() + b' ')
    elif scenario == 'policy':
        paths[1].write_bytes(paths[1].read_bytes() + b' ')
    output = _planning_operation(fixture, query='zzzz-no-match')
    assert (output.get('outcome'), output.get('reason_code')) == ('blocked', 'integrity_failed')
    assert 'DENIED_CONTENT_SENTINEL' not in json.dumps(output)
    assert output.get('candidates') == [] and output.get('read_set') == []
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
        catalog_path=paths[0], policies_path=paths[1], projections_path=paths[2])
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
    raw = core.query_with_diagnostics({k: v for k, v in request.items() if k != 'stage'},
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
    response = core.query_with_diagnostics({k: v for k, v in request.items() if k != 'stage'},
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
    raw=core.query_with_diagnostics({k:v for k,v in request.items() if k!='stage'},root,
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
    response = core.query_with_diagnostics(raw_request, root, catalog_path=paths[0],
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
    raw = core.query_with_diagnostics({k: v for k, v in request.items() if k != 'stage'},
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



# Test-only probes for the actual adapter/core boundary. No production owner,
# formal gate, publication outside a temporary repository or runtime role added.
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


def _s7_generation_switch(fixture):
    __tracebackhide__ = True  # Presentation only; collector retains every exception and case.
    import subprocess
    from unittest.mock import patch
    import publish_knowledge_catalog as publisher
    import _knowledge_catalog_builder as builder
    _s7_write_config(fixture)
    root,paths,request=fixture
    before=json.loads((root/'knowledge/indexes/current.json').read_text())
    assert core.verify_current_publication(root,catalog_path=paths[0],policy_path=paths[1],projections_path=paths[2])
    from scripts.toolchain.knowledge_query import adapter as planning_adapter
    original=planning_adapter._stream_source_hashes
    switches=[]
    consumed=[]
    original_locate=core.locate
    def trace_locate(req,catalog,*args,**kwargs):
        consumed.append(json.loads(json.dumps(catalog)))
        return original_locate(req,catalog,*args,**kwargs)
    def switch_after_freshness(*args,**kwargs):
        result=original(*args,**kwargs)
        (root/'README.md').write_text('# New published repository knowledge authority\nChanged generation source.\n',encoding='utf-8')
        subprocess.run(['git','-C',str(root),'add','README.md'],check=True,capture_output=True)
        subprocess.run(['git','-C',str(root),'-c','user.name=Isolated Test','-c','user.email=test@example.invalid','commit','-m','New isolated publication generation'],check=True,capture_output=True)
        commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
        policy=json.loads(paths[1].read_text()); exclusions=json.loads((root/publisher.INPUT_PATHS['exclusions']).read_text())
        layers=builder.build_layers(root,policy=policy,exclusions=exclusions)
        reqpath=Path('logs/knowledge-context/publication-requests/isolated-switch.json')
        req=dict(schema_version='jimuyun.knowledge-publication-request.v1',request_id='isolated-switch',caller='maintain-knowledge-base',trigger='operator-requested',target_plan='execution-plans/example',main_commit=commit,automatic=False,maintainer_confirmation=True,recorded_at='2026-10-23T00:00:00+00:00',authorizes=['knowledge-publication'],source_route=None)
        (root/reqpath).write_text(json.dumps(req),encoding='utf-8')
        auth=publisher._load_publication_request(root,reqpath,expected_main=commit)
        report=dict(snapshot=layers[0],policy_revision=policy['policy_revision'],summary={'fixture':'switch'})
        publisher._publish_bundle(root,main_commit=commit,layer_bytes={name:publisher._render(value) for name,value in zip(publisher.LAYER_PATHS,layers)},input_bytes={name:(root/path).read_bytes() for name,path in publisher.INPUT_PATHS.items()},report_bytes=publisher._render(report),report=report,publication_authorization=auth)
        assert core.verify_current_publication(root,catalog_path=paths[0],policy_path=paths[1],projections_path=paths[2])
        switches.append(json.loads((root/'knowledge/indexes/current.json').read_text()))
        return result
    with patch.object(planning_adapter,'_stream_source_hashes',switch_after_freshness), patch.object(core,'locate',trace_locate):
        output=_planning_operation(fixture)
    if len(switches)!=1:raise RuntimeError('AUTHOR_BINDING: generation switch barrier not reached once')
    assert before['generation_id']!=switches[0]['generation_id']
    print('S7_REAL_GENERATION_SWITCH:'+json.dumps({'before':before,'after':switches[0]}))
    if output.get('result',output).get('status',output.get('outcome'))=='blocked':
        assert not output.get('read_set') and not output.get('adopted')
    else:
        assert len(consumed)==1
        assert consumed[0]['source_snapshot']['commit']==before['main_commit']
        delivered=output.get('result',output)['candidates']
        source_hashes={x['source_path']:x['source_sha256'] for x in consumed[0]['modules']}
        assert all(c['source_sha256']==source_hashes[c['path']] for c in delivered)
        manifest=json.loads((root/'knowledge/indexes/generations'/before['generation_id']/'manifest.json').read_text())
        frozen=(root/'knowledge/indexes/generations'/before['generation_id']/manifest['artifacts']['catalog_v2']['bundle_path']).read_bytes()
        assert __import__('hashlib').sha256(frozen).hexdigest()==manifest['artifacts']['catalog_v2']['sha256'].removeprefix('sha256:')
        assert json.loads(frozen)==consumed[0]
        identity=output.get('index_identity')
        assert isinstance(identity,dict), 'Successful query must bind its pinned publication generation'
        assert before['generation_id'] in json.dumps(identity), 'Loaded pre-switch data cannot be attributed to post-switch generation'
        assert switches[0]['generation_id'] not in json.dumps(identity)


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
    # BMAD request and all source version kinds
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


@pytest.mark.cer_assertion('ASSERT_3DAF23250361')
def test_contract_3daf23250361(native_caller_decision):
    # Actual native owner reads a source and records its effect on scope.
    try:
        added = _native_decision_body(native_caller_decision)
        assert 'accepted' in added and 'cap-1' in added
        assert 'retain' in added or 'reuse' in added
        assert 'CAP-1' in native_caller_decision['spec']
        assert native_caller_decision['locator_request']['query'].lower() in added
        assert native_caller_decision['locator_request']['consumer'] in added
        assert native_caller_decision['locator_result']['status'] in added
        assert 'worktree' in added and 'direct-source' in added
        assert native_caller_decision['locator_request']['snapshot']['commit'] in added
    except AssertionError:
        print('FAILURE_ID:KQ_3DAF23250361')
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
def test_contract_1b2def4f4ed8(published_planning):
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


@pytest.mark.cer_assertion('ASSERT_F7FB563211E4')
def test_contract_f7fb563211e4(native_caller_decision):
    # This guard has no expected-red role. A real failure remains blocking.
    added = _native_decision_body(native_caller_decision)
    assert 'accepted' in added and 'rejected' in added
    rejected = [line for line in added.splitlines() if '(decision)' in line and 'rejected' in line]
    assert any('docs/source.md' in line and native_caller_decision['source_hash'] in line
        and 'obsolete' in line and ('replacement' in line or 'proposal' in line)
        and any(term in line for term in ('scope', 'exclude', 'not adopt', 'non-goal')) for line in rejected)
    assert 'retain' in added or 'reuse' in added
    from scripts.toolchain.bmad_native.testing import load
    canonical = load('planning_native_selection_check',
        '.agents/skills/jimuyun-spec/scripts/canonical_package.py')
    root = native_caller_decision['root']
    descriptor, _, _ = canonical.build_contract(root, root/'_bmad-output/specs/spec-example/SPEC.md')
    assert descriptor['sources'] == native_caller_decision['roles']['sources']
    assert not any(e['path'] == 'docs/source.md' for e in descriptor['companions'])
    assert (root/'docs/source.md').read_bytes() == native_caller_decision['source_bytes']


@pytest.mark.cer_assertion('ASSERT_D823F94E0DB3')
def test_contract_d823f94e0db3(published_planning):
    # Confirmed missing integration/config, diagnosed backend unavailability or timeout with accessible authorized current source
    try:
        _s7_direct(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_D823F94E0DB3')
        raise


@pytest.mark.cer_assertion('ASSERT_F7401102FE99')
@pytest.mark.parametrize("scenario", ["stdout", "stderr", "combined", "json-parser"])
def test_contract_f7401102fe99(published_planning, scenario):
    # Actual Windows/Linux argv subprocess with spaces/Unicode and cancellation
    try:
        _s7_transport(published_planning, scenario)
    except AssertionError:
        print('FAILURE_ID:KQ_F7401102FE99')
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
def test_contract_1907855d27fb(published_planning):
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
def test_contract_550968c7b8c5(published_planning, scenario):
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


def _s7_exit_zero_blocked(fixture):
    __tracebackhide__ = True
    import subprocess
    from unittest.mock import patch
    root,paths,request=fixture
    _s7_write_config(fixture)
    denied={**request,'policy_revision':'not-authorized'}
    raw=core.query_with_diagnostics({k:v for k,v in denied.items() if k!='stage'},root,
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
    proc=subprocess.run([sys.executable,str(ROOT/'scripts/python/knowledge_locator.py'),'--repository-root',str(root),'--catalog',str(paths[0]),'--policies',str(paths[1]),'--projections',str(paths[2])],input=json.dumps(raw_request),capture_output=True,text=True,encoding='utf-8',check=False)
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
    raw=core.query_with_diagnostics(req,root,catalog_path=paths[0],policies_path=paths[1],projections_path=paths[2])['result']
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
    raw=core.query_with_diagnostics({k:v for k,v in request.items() if k!='stage'},root,catalog_path=paths[0],policies_path=paths[1],projections_path=paths[2])
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


@pytest.fixture(scope='module')
def native_runtime_environment():
    """Use the supplied native dependency cache without writing the user home."""
    import os
    import tempfile
    cache = Path(os.environ.get('UV_CACHE_DIR') or (Path(tempfile.gettempdir())/'ji-mu-yun-uv-cache'))
    cache.mkdir(parents=True, exist_ok=True)
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv('UV_CACHE_DIR', str(cache))
        environment.setenv('UV_OFFLINE', '1')
        environment.setenv('PYTHONDONTWRITEBYTECODE', '1')
        yield cache


def _execute_native_caller_decision(tmp_path_factory, native_runtime_environment):
    """ADR-0062/AD-7: real native owner, not a synthesized adoption fixture.

    This bounded live sample uses the supported caller-session transport. The
    external caller must execute the verified native Skill; transport failure
    is an environment failure, never behavioral RED. A new pytest invocation
    creates a new isolated project and cannot reuse previous native evidence.
    """
    import hashlib
    import os
    from scripts.toolchain.bmad_native.testing import fixture, load
    from scripts.toolchain.bmad_native import verify
    sys.path.insert(0, str(ROOT / 'scripts/sc'))
    from _llm_backend import run_llm_exec
    import host_session

    import subprocess
    import shutil
    base = tmp_path_factory.mktemp('s5-native-caller')
    root, locator_paths, locator_request = published_planning.__wrapped__(base)
    _s7_write_config((root, locator_paths, locator_request))
    installed = fixture(base / 'native-install')
    # Copy verified native runtime, retaining the actual publication's AGENTS.
    for prefix in ('.agents', '_bmad'):
        shutil.copytree(installed/prefix, root/prefix, dirs_exist_ok=True)
    verify(root)
    locator_call = subprocess.run(
        [sys.executable, '-B', str(ROOT/'scripts/python/knowledge_locator.py'),
         '--repository-root', str(root), '--catalog', str(locator_paths[0]),
         '--policies', str(locator_paths[1]), '--projections', str(locator_paths[2])],
        input=json.dumps(locator_request), text=True, encoding='utf-8',
        capture_output=True, shell=False, timeout=30)
    if locator_call.returncode:
        raise RuntimeError(f'LOCATOR_SAMPLE_UNAVAILABLE: {locator_call.stderr}')
    locator_result = json.loads(locator_call.stdout)
    if locator_result.get('status') == 'blocked':
        raise RuntimeError(f'LOCATOR_SAMPLE_BLOCKED: {locator_result}')
    bridge_tests = load('planning_native_bridge_fixture',
        '.agents/skills/jimuyun-spec/scripts/tests/test_bridge.py')
    bridge_tests.initial(root)
    source = root / 'docs/source.md'
    # A concrete decision source, not a prewritten decision or expected output.
    source.write_text(
        '# Current source evidence\n'
        'Existing CAP-1 behavior is supported by the maintained local source.\n'
        'Retain CAP-1 and its existing accepted behavior; do not rebuild it.\n'
        'An earlier proposal to replace CAP-1 is obsolete and must be rejected.\n'
        'This document is provenance, not a new normative companion.\n'
        'The detailed functional criteria of the original accepted behavior are unconfirmed. '
        'Keep that necessary question open: do not invent an additional capability or '
        'authorize a replacement until the owner supplies those details.\n',
        encoding='utf-8')
    # Rebuild the fixture selection through its real owner after changing input.
    descriptor, selection, selection_hash = bridge_tests.canonical.build_contract(
        root, root / bridge_tests.SPEC)
    registry = root / '_bmad-output/specs/canonical-spec-package-selections'
    bridge_tests.canonical.write_json(registry / (selection_hash.replace(':', '-') + '.json'), selection)
    bridge_tests.canonical.write_json(registry / 'current/SPEC-example.json', {
        'package_id': 'SPEC-example', 'schema': bridge_tests.canonical.CURRENT_SCHEMA,
        'selection_hash': selection_hash})
    before_memory = (root / bridge_tests.SPEC).parent.joinpath('.memlog.md').read_text(encoding='utf-8')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    result = bridge_tests.bridge.prepare(root, bridge_tests.SPEC, 'logs/bmad-wrappers/live-decision')
    native = root / 'logs/bmad-wrappers/live-decision/native'
    session = native / 'logs/native-caller-session'
    host_session.initialize(native, session, 'chatgpt-work-mode')
    prompt = (root / result['invocation']).read_text(encoding='utf-8') + (
        '\nBounded live consumer integration sample. Execute the complete verified bmad-spec '
        'headless update and all required native checks. Read docs/source.md yourself; '
        'verify its actual bytes and decide whether to retain the existing capability '
        'and whether to adopt the obsolete proposal. Record your own decisions through '
        'the official memlog command, with source path/hash, accepted/rejected, '
        'reason and actual use. Preserve typed roles at outer publication; no automatic '
        'provenance promotion. Do not claim any adapter query or default hook ran unless '
        'it actually did. Do not create fixture decisions or edit any test. '
        'Return the native headless result; this sample does not authorize implementation.\n')
    prompt += ('Actual public Locator invocation for this sample: ' + json.dumps({
        'topic': locator_request['query'], 'consumer': locator_request['consumer'],
        'status': locator_result['status'], 'result': locator_result,
        'source_read_identity': 'worktree',
        'base_commit': locator_request['snapshot']['commit']}) +
        '\nThis is an explicitly requested caller sample, not a default-hook claim. '
        'The additional docs/source.md is direct-source discovery; do not label it a '
        'Locator hit. Record the actual topic, consumer, raw status, direct-source origin, '
        'worktree identity and base commit alongside its verified byte hash and use.\n')
    old = {k: os.environ.get(k) for k in ('JIMUYUN_HOST_SESSION_DIR', 'JIMUYUN_HOST_TIMEOUT_SECONDS')}
    try:
        os.environ['JIMUYUN_HOST_SESSION_DIR'] = str(session)
        os.environ.pop('JIMUYUN_HOST_TIMEOUT_SECONDS', None)
        code, trace, argv = run_llm_exec(backend='host-session', root=native,
            prompt=prompt, output_last_message=native/'logs/native-result.txt',
            timeout_sec=1800, codex_sandbox='workspace-write')
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    if code:
        raise RuntimeError(f'NATIVE_CALLER_EXECUTION_UNAVAILABLE: exit={code}; session={session}; {trace}')
    publication = bridge_tests.bridge.publish(root, 'logs/bmad-wrappers/live-decision')
    verify(root)
    verify(native)
    after_memory = (root / bridge_tests.SPEC).parent.joinpath('.memlog.md').read_text(encoding='utf-8')
    actual = bridge_tests.canonical.validate_selection(root, root/bridge_tests.SPEC,
        registry/'current/SPEC-example.json')
    return dict(root=root, native=native, before=before_memory, after=after_memory,
        source_hash=source_hash, source_bytes=source.read_bytes(), roles=descriptor,
        selection=actual, publication=publication, locator_request=locator_request, locator_result=locator_result, spec=(root/bridge_tests.SPEC).read_text(encoding='utf-8'))


def _native_decision_body(sample):
    # Native memlog's updated metadata is mutable; its chronological body is not.
    old_body = sample['before'].split('\n---\n', 1)[1]
    new_body = sample['after'].split('\n---\n', 1)[1]
    assert new_body.strip().startswith(old_body.strip()), 'Native caller rewrote prior decisions'
    added = new_body.strip()[len(old_body.strip()):]
    assert 'docs/source.md' in added and sample['source_hash'] in added
    assert '(decision)' in added
    return added.lower()


@pytest.mark.cer_assertion('ASSERT_09A30E743B67')
@pytest.mark.parametrize('phase,environment_mode,explicit', [
    (None, None, None),
    (None, None, 'auto'),
    (None, None, 'on'),
    (None, None, 'off'),
    (None, 'auto', None),
    (None, 'auto', 'auto'),
    (None, 'auto', 'on'),
    (None, 'auto', 'off'),
    (None, 'on', None),
    (None, 'on', 'auto'),
    (None, 'on', 'on'),
    (None, 'on', 'off'),
    (None, 'off', None),
    (None, 'off', 'auto'),
    (None, 'off', 'on'),
    (None, 'off', 'off'),
    ('development', None, None),
    ('development', None, 'auto'),
    ('development', None, 'on'),
    ('development', None, 'off'),
    ('development', 'auto', None),
    ('development', 'auto', 'auto'),
    ('development', 'auto', 'on'),
    ('development', 'auto', 'off'),
    ('development', 'on', None),
    ('development', 'on', 'auto'),
    ('development', 'on', 'on'),
    ('development', 'on', 'off'),
    ('development', 'off', None),
    ('development', 'off', 'auto'),
    ('development', 'off', 'on'),
    ('development', 'off', 'off'),
    ('test', None, None),
    ('test', None, 'auto'),
    ('test', None, 'on'),
    ('test', None, 'off'),
    ('test', 'auto', None),
    ('test', 'auto', 'auto'),
    ('test', 'auto', 'on'),
    ('test', 'auto', 'off'),
    ('test', 'on', None),
    ('test', 'on', 'auto'),
    ('test', 'on', 'on'),
    ('test', 'on', 'off'),
    ('test', 'off', None),
    ('test', 'off', 'auto'),
    ('test', 'off', 'on'),
    ('test', 'off', 'off'),
    ('production', None, None),
    ('production', None, 'auto'),
    ('production', None, 'on'),
    ('production', None, 'off'),
    ('production', 'auto', None),
    ('production', 'auto', 'auto'),
    ('production', 'auto', 'on'),
    ('production', 'auto', 'off'),
    ('production', 'on', None),
    ('production', 'on', 'auto'),
    ('production', 'on', 'on'),
    ('production', 'on', 'off'),
    ('production', 'off', None),
    ('production', 'off', 'auto'),
    ('production', 'off', 'on'),
    ('production', 'off', 'off'),
], ids=['case-0', 'case-1', 'case-2', 'case-3', 'case-4', 'case-5', 'case-6', 'case-7', 'case-8', 'case-9', 'case-10', 'case-11', 'case-12', 'case-13', 'case-14', 'case-15', 'case-16', 'case-17', 'case-18', 'case-19', 'case-20', 'case-21', 'case-22', 'case-23', 'case-24', 'case-25', 'case-26', 'case-27', 'case-28', 'case-29', 'case-30', 'case-31', 'case-32', 'case-33', 'case-34', 'case-35', 'case-36', 'case-37', 'case-38', 'case-39', 'case-40', 'case-41', 'case-42', 'case-43', 'case-44', 'case-45', 'case-46', 'case-47', 'case-48', 'case-49', 'case-50', 'case-51', 'case-52', 'case-53', 'case-54', 'case-55', 'case-56', 'case-57', 'case-58', 'case-59', 'case-60', 'case-61', 'case-62', 'case-63'])
def test_contract_09a30e743b67(phase, environment_mode, explicit):
    # ADR-0041 / AD-9: exercise the existing owner, including all precedence tiers.
    from scripts.toolchain.bmad_native.testing import load
    owner = load('planning_governance_policy',
        '.agents/skills/quick-dev-tdd-adapter/tools/governance_policy.py')
    env = {}
    if phase is not None:
        env['PHASEA_SERVICE_STATE'] = phase
    if environment_mode is not None:
        env['JIMUYUN_GOVERNANCE_MODE'] = environment_mode
    actual = owner.resolve_governance_policy(explicit, environment=env)
    expected_mode = explicit if explicit is not None else environment_mode or 'auto'
    expected_phase = phase or 'development'
    expected_source = 'parameter' if explicit is not None else (
        'environment' if environment_mode is not None else 'phase-service-state')
    try:
        assert actual['mode'] == expected_mode
        assert actual['phase_service_state'] == expected_phase
        assert actual['source'] == expected_source
        assert actual['enabled'] == (expected_mode == 'on' or (
            expected_mode == 'auto' and expected_phase in {'test', 'production'}))
    except AssertionError:
        print('FAILURE_ID:KQ_09A30E743B67')
        raise


@pytest.mark.cer_assertion('ASSERT_6C6853493E27')
@pytest.mark.parametrize('query_switch,phase,environment_mode,explicit', [
    ('on', None, None, None),
    ('on', None, 'on', None),
    ('on', None, 'off', None),
    ('on', None, 'on', 'off'),
    ('on', None, 'off', 'on'),
    ('on', None, 'on', 'auto'),
    ('on', 'development', None, None),
    ('on', 'development', 'on', None),
    ('on', 'development', 'off', None),
    ('on', 'development', 'on', 'off'),
    ('on', 'development', 'off', 'on'),
    ('on', 'development', 'on', 'auto'),
    ('on', 'test', None, None),
    ('on', 'test', 'on', None),
    ('on', 'test', 'off', None),
    ('on', 'test', 'on', 'off'),
    ('on', 'test', 'off', 'on'),
    ('on', 'test', 'on', 'auto'),
    ('on', 'production', None, None),
    ('on', 'production', 'on', None),
    ('on', 'production', 'off', None),
    ('on', 'production', 'on', 'off'),
    ('on', 'production', 'off', 'on'),
    ('on', 'production', 'on', 'auto'),
    ('off', None, None, None),
    ('off', None, 'on', None),
    ('off', None, 'off', None),
    ('off', None, 'on', 'off'),
    ('off', None, 'off', 'on'),
    ('off', None, 'on', 'auto'),
    ('off', 'development', None, None),
    ('off', 'development', 'on', None),
    ('off', 'development', 'off', None),
    ('off', 'development', 'on', 'off'),
    ('off', 'development', 'off', 'on'),
    ('off', 'development', 'on', 'auto'),
    ('off', 'test', None, None),
    ('off', 'test', 'on', None),
    ('off', 'test', 'off', None),
    ('off', 'test', 'on', 'off'),
    ('off', 'test', 'off', 'on'),
    ('off', 'test', 'on', 'auto'),
    ('off', 'production', None, None),
    ('off', 'production', 'on', None),
    ('off', 'production', 'off', None),
    ('off', 'production', 'on', 'off'),
    ('off', 'production', 'off', 'on'),
    ('off', 'production', 'on', 'auto'),
], ids=['case-0', 'case-1', 'case-2', 'case-3', 'case-4', 'case-5', 'case-6', 'case-7', 'case-8', 'case-9', 'case-10', 'case-11', 'case-12', 'case-13', 'case-14', 'case-15', 'case-16', 'case-17', 'case-18', 'case-19', 'case-20', 'case-21', 'case-22', 'case-23', 'case-24', 'case-25', 'case-26', 'case-27', 'case-28', 'case-29', 'case-30', 'case-31', 'case-32', 'case-33', 'case-34', 'case-35', 'case-36', 'case-37', 'case-38', 'case-39', 'case-40', 'case-41', 'case-42', 'case-43', 'case-44', 'case-45', 'case-46', 'case-47'])
def test_contract_6c6853493e27(query_switch, phase, environment_mode, explicit, tmp_path, monkeypatch):
    from scripts.toolchain.bmad_native.testing import load
    owner = load('planning_governance_policy_independence',
        '.agents/skills/quick-dev-tdd-adapter/tools/governance_policy.py')
    config = tmp_path/'knowledge/planning-query.toml'
    config.parent.mkdir()
    config.write_text('[query]\nenabled = ' + ('true' if query_switch == 'on' else 'false') + '\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    env = {}
    if phase is not None:
        env['PHASEA_SERVICE_STATE'] = phase
    if environment_mode is not None:
        env['JIMUYUN_GOVERNANCE_MODE'] = environment_mode
    actual = owner.resolve_governance_policy(explicit, environment=env)
    mode = explicit if explicit is not None else environment_mode or 'auto'
    state = phase or 'development'
    try:
        assert actual['mode'] == mode and actual['phase_service_state'] == state
        assert actual['enabled'] == (mode == 'on' or (mode == 'auto' and state != 'development'))
        config.write_text('[query]\nenabled = ' + ('false' if query_switch == 'on' else 'true') + '\n', encoding='utf-8')
        assert actual == owner.resolve_governance_policy(explicit, environment=env)
        assert actual['checks'] == list(owner.GOVERNANCE_CHECKS)
    except AssertionError:
        print('FAILURE_ID:KQ_6C6853493E27')
        raise


@pytest.mark.cer_assertion('ASSERT_BA9A0474912A')
@pytest.mark.cer_assertion('ASSERT_06A867E00BC5')
@pytest.mark.cer_assertion('ASSERT_B7A571632018')
@pytest.mark.parametrize('scenario', ['unicode-path-utf8', 'subprocess-timeout', 'subprocess-cancel'])
def test_windows_planning_query_runtime(tmp_path, scenario):
    # FR-10 / AC-14: the OS prerequisite is not a product failure or a skipped pass.
    import os
    import subprocess
    if sys.platform != 'win32':
        _assert_recorded_windows_evidence(scenario)
        return
    base = tmp_path / 'space \u4e2d\u6587'
    base.mkdir()
    root, paths, request = published_planning.__wrapped__(base)
    argv = [sys.executable, '-B', str(ROOT/'scripts/python/knowledge_locator.py'),
        '--repository-root', str(root), '--catalog', str(paths[0]),
        '--policies', str(paths[1]), '--projections', str(paths[2])]
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    if scenario == 'unicode-path-utf8':
        child = subprocess.run(argv, input=json.dumps(request, ensure_ascii=False),
            capture_output=True, text=True, encoding='utf-8', shell=False, env=env, timeout=30)
        assert child.returncode == 0, child.stderr
        actual = json.loads(child.stdout)
        expected = _query_published((root, paths, request))['result']
        assert actual == expected
        assert actual['request_id'] == request['request_id']
    else:
        # Actual public Locator process waiting for request bytes on stdin.
        # The harness owns termination; this is platform transport proof only,
        # not evidence that the planning adapter's cancellation is implemented.
        child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, shell=False, env=env)
        try:
            if scenario == 'subprocess-timeout':
                with pytest.raises(subprocess.TimeoutExpired):
                    child.wait(timeout=0.05)
                child.kill()
            else:
                child.terminate()
            child.wait(timeout=5)
            assert child.poll() is not None and child.returncode != 0
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            for stream in (child.stdin, child.stdout, child.stderr):
                stream.close()

# ADR-0041/ADR-0062 and adopted AD-5/AD-7.
# Merge into the shared test module; depends on ROOT and published_planning.

@pytest.fixture(scope='module')
def architecture_consumer_sample(tmp_path_factory, native_runtime_environment):
    import hashlib
    import os
    import shutil
    from unittest.mock import patch
    from scripts.toolchain.bmad_native.testing import fixture, load
    from scripts.toolchain.bmad_native import verify
    from scripts.toolchain.knowledge_query import adapter

    base = tmp_path_factory.mktemp('s5-architecture-consumer')
    root, paths, request = published_planning.__wrapped__(base)
    installed = fixture(base / 'verified-native')
    for prefix in ('.agents', '_bmad'):
        shutil.copytree(installed/prefix, root/prefix, dirs_exist_ok=True)
    # Preserve publication AGENTS and its source identity.
    source_texts = {
        'docs/current-adr.md': '# ADR-TEST (Accepted)\nThe current transport uses stdio. '
            'TCP is excluded. TransportOwner owns this contract.\n',
        'src/transport.py': 'def transport_kind():\n    return "stdio"\n',
        'docs/upstream.md': '# Approved scope\nReuse the current transport. '
            'No transport replacement is authorized. A prior adopted factual '
            'conclusion said the transport used TCP; reconcile that claim against '
            'the current accepted ADR and actual implementation.\n',
        'docs/old-plan.md': '# Historical plan, not implemented\n'
            'An earlier proposal planned a TCP transport.\n',
        'docs/task.md': '# Architecture request\nCreate a discussion architecture '
            'for reuse of the current transport. Check accepted ADRs, current '
            'owners/interfaces and source before choosing scope. Explicitly '
            'resolve the old TCP claim and preserve the approved no-replacement '
            'scope. Do not implement anything.\n',
    }
    for path, text in source_texts.items():
        target = root/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
    # The configuration is input, not a fabricated query result.
    _s7_write_config((root, paths, request))
    calls = []
    original = adapter.diagnose
    def observe(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append({'request': args[0] if args else kwargs.get('request'), 'result': json.loads(json.dumps(result))})
        return result
    # Import after patch so a direct import also observes the real implementation.
    with patch.object(adapter, 'diagnose', observe):
        invoke = load('planning_architecture_live', '.agents/skills/jimuyun-architecture/scripts/invoke.py')
        prepared = invoke.prepare(root, 'logs/bmad-wrappers/architecture-live',
            list(source_texts), purpose='discussion')
    verify(root)
    native = root/'logs/bmad-wrappers/architecture-live/native'
    verify(native)
    source_hashes = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in source_texts}
    state = dict(root=root, native=native, prepared=prepared, calls=calls,
        hashes=source_hashes, inputs=source_texts, locator_paths=paths, locator_request=request, completed=False)

    state['finish'] = lambda: _architecture_finish(state)
    return state



def _architecture_predecision_read(sample, required):
    import hashlib
    assert sample['calls'], 'Actual Architecture prepare did not call the shared query adapter'
    results = [c['result'] for c in sample['calls']]
    assert all(r.get('schema') == 'planning-query.v1' for r in results)
    assert all(r.get('stage') == 'architecture' for r in results)
    assert all(r.get('consumer') == 'bmad-planning' for r in results)
    reads = {item['path']: item for r in results for item in r.get('read_set', [])}
    assert set(required) <= set(reads), 'Prepare did not verify required source before native decision'
    for path in required:
        item = reads[path]
        assert item['sha256'].removeprefix('sha256:') == sample['hashes'][path]
        assert item['origin'] in {'locator', 'direct-source'}
        identity = json.dumps(item['read_identity'])
        assert 'worktree' in identity and sample['hashes'][path] in identity
        assert item.get('excerpt_range')
        assert hashlib.sha256((sample['root']/path).read_bytes()).hexdigest() == sample['hashes'][path]
    return reads



def _architecture_decisions(sample):
    actual = sample['finish']()
    decisions = [line.lower() for line in actual['memory'].splitlines() if '(decision)' in line]
    assert decisions, 'Real native owner did not record a decision'
    return actual, decisions



def _architecture_source_decision(sample, decisions, path):
    matches = [line for line in decisions if path in line and sample['hashes'][path] in line]
    assert matches, 'Native decision must bind the actual read source: '+path
    return '\n'.join(matches)



@pytest.mark.cer_assertion('ASSERT_4658282A03DF')
def test_contract_4658282a03df(architecture_consumer_sample):
    sample = architecture_consumer_sample
    try:
        _architecture_predecision_read(sample, ['docs/current-adr.md', 'docs/upstream.md', 'src/transport.py'])
        _, decisions = _architecture_decisions(sample)
        upstream = _architecture_source_decision(sample, decisions, 'docs/upstream.md')
        current = _architecture_source_decision(sample, decisions, 'src/transport.py')
        assert 'tcp' in upstream and ('reject' in upstream or 'conflict' in upstream)
        assert 'stdio' in current and ('reuse' in current or 'retain' in current
            or ('accepted actual' in current and 'no replacement' in current))
    except AssertionError:
        print('FAILURE_ID:KQ_4658282A03DF')
        raise



@pytest.mark.cer_assertion('ASSERT_C20CFAFDB4D0')
def test_contract_c20cfafdb4d0(architecture_consumer_sample):
    sample = architecture_consumer_sample
    try:
        _architecture_predecision_read(sample, ['docs/current-adr.md', 'src/transport.py', 'docs/upstream.md'])
        actual, decisions = _architecture_decisions(sample)
        adr = _architecture_source_decision(sample, decisions, 'docs/current-adr.md')
        code = _architecture_source_decision(sample, decisions, 'src/transport.py')
        assert 'accepted' in adr and 'stdio' in adr
        assert 'stdio' in code
        assert 'TransportOwner' in actual['spine']
        assert 'transport_kind' in actual['spine'] or 'src/transport.py' in actual['spine']
    except AssertionError:
        print('FAILURE_ID:KQ_C20CFAFDB4D0')
        raise



@pytest.mark.cer_assertion('ASSERT_B4C65F02340C')
def test_contract_b4c65f02340c(architecture_consumer_sample):
    sample = architecture_consumer_sample
    try:
        _architecture_predecision_read(sample, ['docs/current-adr.md', 'src/transport.py', 'docs/upstream.md'])
        actual, decisions = _architecture_decisions(sample)
        upstream = _architecture_source_decision(sample, decisions, 'docs/upstream.md')
        assert 'tcp' in upstream and ('reject' in upstream or 'conflict' in upstream)
        spine = actual['spine'].lower()
        assert ('no-replacement' in spine or 'no transport replacement' in spine
            or 'tcp and transport replacement are excluded' in spine)
        assert (sample['root']/'docs/upstream.md').read_text(encoding='utf-8') == sample['inputs']['docs/upstream.md']
    except AssertionError:
        print('FAILURE_ID:KQ_B4C65F02340C')
        raise



@pytest.mark.cer_assertion('ASSERT_765306749370')
def test_contract_765306749370(architecture_consumer_sample):
    sample = architecture_consumer_sample
    try:
        _architecture_predecision_read(sample, ['docs/current-adr.md', 'docs/old-plan.md', 'src/transport.py'])
        _, decisions = _architecture_decisions(sample)
        old = _architecture_source_decision(sample, decisions, 'docs/old-plan.md')
        current = _architecture_source_decision(sample, decisions, 'docs/current-adr.md')
        assert 'rejected' in old and ('historical' in old or 'not implemented' in old)
        assert 'accepted' in current and 'stdio' in current
    except AssertionError:
        print('FAILURE_ID:KQ_765306749370')
        raise



@pytest.mark.cer_assertion('ASSERT_DA1D012CDA24')
def test_contract_da1d012cda24(architecture_consumer_sample):
    sample = architecture_consumer_sample
    try:
        _architecture_predecision_read(sample, ['docs/current-adr.md', 'docs/upstream.md', 'docs/old-plan.md'])
        actual, decisions = _architecture_decisions(sample)
        conflicts = '\n'.join(line for line in decisions if 'conflict' in line or 'rejected' in line)
        assert 'tcp' in conflicts and 'stdio' in '\n'.join(decisions)
        assert 'TransportOwner' in actual['spine']
        assert any(('reuse' in line or 'retain' in line
            or ('accepted actual' in line and 'no replacement' in line))
            and 'stdio' in line for line in decisions)
    except AssertionError:
        print('FAILURE_ID:KQ_DA1D012CDA24')
        raise



# ADR-0041 / AD-5: public VDD preplanning boundary, not completed plan evidence.
# Merge into the declared shared test module. Requires its existing ROOT,
# published_planning and _s7_write_config helpers. No fake model response is used.


def _vdd_public_first_worker(fixture, tmp_path, *, governance='off', resume=False):
    """Observe the real public process before its first semantic worker.

    The genuine host request is cancelled through its public owner. This
    exposes a preplanning counterexample without producing a plan or pretending
    that a model adopted a source. It must not be reused for full-plan oracles.
    """
    import os
    import shutil
    import subprocess
    import time

    root, _, _ = fixture
    for relative in ('scripts', '.agents/skills/vdd-execution-plan',
                     '.agents/skills/quick-dev-tdd-adapter/tools'):
        shutil.copytree(ROOT/relative, root/relative, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    _s7_write_config(fixture)
    source = root/'requirements.md'
    if not source.exists():
        source.write_text(
            '# FR-1\nPreserve the current repository knowledge authority. '
            'Inspect AGENTS.md and the existing source and tests before deciding '
            'whether any implementation change is needed.\n', encoding='utf-8')
    out = root/'execution-plans/preplanning-boundary'
    run_name = 'repair' if resume else 'create'
    session = root/'logs'/('boundary-session-' + run_name)
    owner_cli = root/'scripts/sc/host_session.py'
    initialized = subprocess.run(
        [sys.executable, '-B', str(owner_cli), 'init', '--session', str(session),
         '--caller', 'chatgpt-work-mode'], cwd=root, capture_output=True,
        text=True, encoding='utf-8', shell=False, timeout=15)
    if initialized.returncode:
        raise RuntimeError('VDD_TEST_SESSION_UNAVAILABLE: ' + initialized.stderr + initialized.stdout)
    trace = root/'logs'/('boundary-trace-' + run_name + '.jsonl')
    # The instrumentation records only reached production calls/returns. It
    # never substitutes an adapter result, compiler function or model response.
    bootstrap = r'''
import json, pathlib, runpy, sys, time
root, trace = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
args = sys.argv[3:]
stream = trace.open('x', encoding='utf-8')
def observe(frame, event, arg):
    if event not in {'call', 'return'}:
        return
    # Ignore unrelated code before filesystem resolution. The exact contained
    # source checks below still govern every recorded event.
    filename = frame.f_code.co_filename.replace('\\', '/')
    if not filename.endswith(('scripts/toolchain/knowledge_query/adapter.py',
                              'scripts/python/_knowledge_locator_core.py',
                              'scripts/sc/host_session.py')):
        return
    # Keep the same POSIX representation for containment and event identity.
    prefix = root.as_posix() + '/'
    if not filename.startswith(prefix):
        return
    relative = filename[len(prefix):]
    name = frame.f_code.co_name
    if (relative == 'scripts/toolchain/knowledge_query/adapter.py'
        or (relative == 'scripts/python/_knowledge_locator_core.py' and name == 'query_with_diagnostics')
        or (relative == 'scripts/sc/host_session.py' and name == 'execute')):
        stream.write(json.dumps({'path': relative, 'function': name,
            'event': event, 'monotonic_ns': time.monotonic_ns()}) + '\n')
        stream.flush()
sys.path.insert(0, str(root))
sys.argv = [str(root/'scripts/vdd/compile_plan.py'), *args]
sys.setprofile(observe)
try:
    runpy.run_path(sys.argv[0], run_name='__main__')
finally:
    sys.setprofile(None)
    stream.close()
'''
    args = ['--requirements', str(source), '--out-dir', str(out), '--profile', 'self-hosted']
    if resume:
        args += ['--resume-from', 'first-failed-stage']
    env = {**os.environ, 'SC_LLM_BACKEND': 'host-session',
           'JIMUYUN_HOST_SESSION_DIR': str(session), 'JIMUYUN_GOVERNANCE_MODE': governance,
           'PHASEA_SERVICE_STATE': 'development', 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTHONUTF8': '1'}
    env.pop('JIMUYUN_HOST_TIMEOUT_SECONDS', None)
    stdout = root/'logs'/('boundary-' + run_name + '.stdout')
    stderr = root/'logs'/('boundary-' + run_name + '.stderr')
    request = None
    with stdout.open('wb') as output, stderr.open('wb') as errors:
        child = subprocess.Popen([sys.executable, '-B', '-c', bootstrap, str(root), str(trace), *args],
                                 cwd=root, env=env, stdout=output, stderr=errors, shell=False)
        deadline = time.monotonic() + 35
        try:
            while child.poll() is None and time.monotonic() < deadline:
                # Discovery is scoped to this unique live transport session;
                # it does not select prior successful evidence.
                pending = list(session.glob('*/request.json'))
                if pending:
                    if len(pending) != 1:
                        raise RuntimeError('VDD_TEST_AMBIGUOUS_LIVE_REQUEST')
                    request = json.loads(pending[0].read_text(encoding='utf-8'))
                    cancellation = subprocess.run(
                        [sys.executable, '-B', str(owner_cli), 'cancel', '--session', str(session),
                         '--request-id', request['request_id']], cwd=root, capture_output=True,
                        text=True, encoding='utf-8', shell=False, timeout=15)
                    if cancellation.returncode:
                        raise RuntimeError('VDD_TEST_CANCEL_FAILED: ' + cancellation.stdout + cancellation.stderr)
                    break
                time.sleep(0.05)
            if request is None:
                raise RuntimeError('VDD_PRESEMANTIC_REACHABILITY_UNAVAILABLE: ' +
                                   stdout.read_text(encoding='utf-8') + stderr.read_text(encoding='utf-8'))
            child.wait(timeout=15)
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
    events = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
    worker = next((i for i, e in enumerate(events)
                   if e['path'] == 'scripts/sc/host_session.py' and e['event'] == 'call'), None)
    if worker is None:
        raise RuntimeError('VDD_WORKER_ENTRY_NOT_OBSERVED')
    return {'events': events, 'before_worker': events[:worker], 'request': request,
            'exit_code': child.returncode, 'out': out, 'root': root}


def _assert_actual_vdd_prequery(observation):
    events = observation['before_worker']
    adapter_calls = [e for e in events if e['path'] == 'scripts/toolchain/knowledge_query/adapter.py'
                     and e['event'] == 'call']
    locator_calls = [e for e in events if e['path'] == 'scripts/python/_knowledge_locator_core.py'
                     and e['function'] == 'query_with_diagnostics' and e['event'] == 'call']
    locator_returns = [e for e in events if e['path'] == 'scripts/python/_knowledge_locator_core.py'
                       and e['function'] == 'query_with_diagnostics' and e['event'] == 'return']
    assert adapter_calls, 'Actual public VDD process reached semantic worker without shared adapter'
    assert locator_calls and locator_returns, 'Default-enabled preplanning did not complete real Locator diagnosis'
    assert adapter_calls[0]['monotonic_ns'] <= locator_calls[0]['monotonic_ns'] < locator_returns[-1]['monotonic_ns']
    assert locator_returns[-1]['monotonic_ns'] - locator_calls[0]['monotonic_ns'] <= 30_000_000_000


@pytest.mark.cer_assertion('ASSERT_05552304BD9E')
def test_contract_05552304bd9e(published_planning, tmp_path):
    observation = _vdd_public_first_worker(published_planning, tmp_path)
    try:
        _assert_actual_vdd_prequery(observation)
    except AssertionError:
        print('FAILURE_ID:KQ_05552304BD9E')
        raise


@pytest.mark.cer_assertion('ASSERT_FD756962A671')
@pytest.mark.parametrize('proposal', [False, True], ids=['existing-source', 'proposed-new-path'])
def test_contract_fd756962a671(published_planning, tmp_path, proposal):
    if proposal:
        root, _, _ = published_planning
        (root/'requirements.md').write_text(
            '# FR-1\nInspect AGENTS.md and preserve the current behavior before '
            'planning a new feature in `src/proposed.py`. That path is proposed '
            'and does not yet exist; it is not current source evidence.\n', encoding='utf-8')
        assert not (root/'src/proposed.py').exists()
    try:
        try:
            created = _vdd_public_first_worker(published_planning, tmp_path, governance='off')
        except RuntimeError as exc:
            # An observed structured production denial of a valid proposal is
            # behavioral failure. Other transport/harness errors stay errors.
            if (proposal and str(exc).startswith('VDD_PRESEMANTIC_REACHABILITY_UNAVAILABLE:')
                    and 'consumption_reference_denied' in str(exc)):
                assert 'consumption_reference_denied' not in str(exc), str(exc)
            raise
        _assert_actual_vdd_prequery(created)
        # A real failed predecessor is reused through the public recovery flag;
        # no successful cache, V1 answer or authority is manufactured.
        repaired = _vdd_public_first_worker(published_planning, tmp_path, governance='off', resume=True)
        _assert_actual_vdd_prequery(repaired)
    except AssertionError:
        print('FAILURE_ID:KQ_FD756962A671')
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


def _architecture_finish(state):
    import os
    import hashlib
    from scripts.toolchain.bmad_native import verify
    root, native, prepared = state['root'], state['native'], state['prepared']
    source_hashes = state['hashes']
    # Called only after each test establishes the actual prepare/query/read
    # precondition. No native text or success record is synthesized here.
    if state['completed']:
        return state
    sys.path.insert(0, str(ROOT/'scripts/sc'))
    from _llm_backend import run_llm_exec
    import host_session
    session = native/'logs/architecture-live-session'
    host_session.initialize(native, session, 'chatgpt-work-mode')
    prompt = (root/prepared['invocation']).read_text(encoding='utf-8') + (
        '\nExecute the complete verified native architecture Skill, including '
        'required source reconciliation and reviewer lifecycle. The fixture '
        'files are source inputs, not desired decisions. Read them and hash '
        'the actual bytes. Record your own source decisions in the native '
        'memlog using the official command: path/hash, accepted/rejected, '
        'reason and actual scope impact. Explicitly reconcile the prior TCP '
        'claim against the current ADR, owner/interface and code. Preserve '
        'the approved no-replacement scope. Do not invent that a query ran. '
        'Do not implement or modify tests, source inputs or native Skill bytes.\n')
    prompt += state.get('prompt_suffix', '')
    keys = ('JIMUYUN_HOST_SESSION_DIR', 'JIMUYUN_HOST_TIMEOUT_SECONDS')
    previous = {k: os.environ.get(k) for k in keys}
    try:
        os.environ['JIMUYUN_HOST_SESSION_DIR'] = str(session)
        os.environ.pop('JIMUYUN_HOST_TIMEOUT_SECONDS', None)
        code, trace, _ = run_llm_exec(backend='host-session', root=native,
            prompt=prompt, output_last_message=native/'logs/architecture-result.txt',
            timeout_sec=1800, codex_sandbox='workspace-write')
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    if code:
        raise RuntimeError(f'ARCHITECTURE_NATIVE_ENVIRONMENT: exit={code}; {session}; {trace}')
    workspace = root/prepared['doc_workspace']
    state['spine'] = (workspace/'ARCHITECTURE-SPINE.md').read_text(encoding='utf-8')
    state['memory'] = (workspace/'.memlog.md').read_text(encoding='utf-8')
    verify(root)
    verify(native)
    for path, expected in source_hashes.items():
        if hashlib.sha256((root/path).read_bytes()).hexdigest() != expected:
            raise RuntimeError('ARCHITECTURE_NATIVE_MODIFIED_READ_ONLY_INPUT: '+path)
    state['completed'] = True
    return state


@pytest.mark.cer_assertion('ASSERT_44BC8197CE64')
@pytest.mark.parametrize('reason', ['new-question', 'missing-basis', 'related-source-change'])
def test_contract_44bc8197ce64(architecture_consumer_sample, reason, tmp_path):
    import hashlib
    from unittest.mock import patch
    from scripts.toolchain.bmad_native.testing import load
    from scripts.toolchain.knowledge_query import adapter
    sample = architecture_consumer_sample
    try:
        _architecture_predecision_read(sample, ['docs/current-adr.md', 'docs/upstream.md', 'src/transport.py'])
    except AssertionError:
        print('FAILURE_ID:KQ_44BC8197CE64')
        raise
    # Establish the predecessor using an explicit current public Locator call
    # and real native source reading. This is NOT an automatic prepare-hook
    # claim and does not require the future S5 lookup implementation.
    if not sample['completed']:
        import subprocess
        root = sample['root']
        paths = sample['locator_paths']
        request = {**sample['locator_request'], 'stage': 'architecture'}
        observed = subprocess.run([sys.executable, '-B',
            str(ROOT/'scripts/python/knowledge_locator.py'), '--repository-root', str(root),
            '--catalog', str(paths[0]), '--policies', str(paths[1]),
            '--projections', str(paths[2])], input=json.dumps(request), text=True,
            encoding='utf-8', capture_output=True, shell=False, timeout=30)
        if observed.returncode:
            raise RuntimeError('SUPPLEMENT_BASELINE_LOCATOR_UNAVAILABLE: '+observed.stderr)
        raw = json.loads(observed.stdout)
        if raw.get('status') == 'blocked':
            raise RuntimeError('SUPPLEMENT_BASELINE_LOCATOR_BLOCKED: '+json.dumps(raw))
        actual_hashes = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sample['inputs']}
        if actual_hashes != sample['hashes']:
            raise RuntimeError('SUPPLEMENT_BASELINE_SOURCE_CHANGED')
        sample['prompt_suffix'] = ('\nExplicit test-arranged predecessor lookup, not an '
            'automatic wrapper hook: '+json.dumps(raw)+'. These additional task-input '
            'sources are direct-source discoveries, not manufactured Locator hits: '+
            json.dumps(actual_hashes)+'. Read them yourself and verify the actual bytes '
            'before forming and recording your own architecture source decisions.\n')
    baseline = sample['finish']()
    import shutil
    root = tmp_path/'supplement-root'
    shutil.copytree(sample['root'], root)
    # Exact prior history is an input, not current proof. Each parameter owns
    # its own current root so changing sources cannot alter another case.
    prior = baseline
    old_workspace = root/prior['prepared']['doc_workspace']
    old_memory = (old_workspace/'.memlog.md').read_text(encoding='utf-8')
    unchanged_path = 'docs/current-adr.md'
    unchanged_hash = hashlib.sha256((root/unchanged_path).read_bytes()).hexdigest()
    inputs = list(sample['inputs'])
    if reason == 'new-question':
        extra = 'docs/new-question.md'
        text = ('# New architecture question\nCan the current stdio interface '
            'support a binary payload? The previously verified interface only '
            'specifies transport kind. Check actual current source; leave an '
            'unsupported answer open rather than infer a feature.\n')
    elif reason == 'missing-basis':
        extra = 'docs/encoding-basis.md'
        text = ('# Accepted interface clarification\nTransportOwner requires UTF-8 '
            'text at the existing stdio boundary. This supplies the encoding basis '
            'that was absent from the preceding architecture discussion. It does '
            'not authorize replacing the transport.\n')
    else:
        extra = 'src/transport.py'
        text = ('def transport_kind():\n    return "stdio"\n\n'
            'def text_encoding():\n    return "utf-8"\n')
    (root/extra).parent.mkdir(parents=True, exist_ok=True)
    (root/extra).write_text(text, encoding='utf-8')
    if extra not in inputs:
        inputs.append(extra)
    task = ('# Supplemental architecture request\nReason: '+reason+
        '. Reuse unchanged verified ADR evidence, but verify the new or changed '
        'source '+extra+' before deciding. Record the qualifying reason and '
        'concrete scope impact. Preserve prior decisions chronologically and '
        'retain the no-replacement boundary.\n')
    (root/'docs/task.md').write_text(task, encoding='utf-8')
    inputs += [(old_workspace/'ARCHITECTURE-SPINE.md').relative_to(root).as_posix(),
               (old_workspace/'.memlog.md').relative_to(root).as_posix()]
    hashes = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in inputs}
    calls = []
    original = adapter.diagnose
    def observe(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append({'request': args[0] if args else kwargs.get('request'),
                      'result': json.loads(json.dumps(result))})
        return result
    with patch.object(adapter, 'diagnose', observe):
        invoke = load('architecture_supplement_'+reason.replace('-', '_'),
            '.agents/skills/jimuyun-architecture/scripts/invoke.py')
        prepared = invoke.prepare(root, 'logs/bmad-wrappers/supplement-'+reason,
            inputs, intent='update', purpose='discussion')
    updated = dict(root=root, native=root/('logs/bmad-wrappers/supplement-'+reason+'/native'),
        prepared=prepared, calls=calls, hashes=hashes, completed=False,
        prompt_suffix='\nThis actual update was requested for '+reason+
        '. Record that trigger, the verified changed/new source and the concrete '
        'impact; explicitly explain reuse of unchanged ADR evidence.\n')
    updated['finish'] = lambda: _architecture_finish(updated)
    try:
        _architecture_predecision_read(updated, [extra])
        assert len(calls) <= 3, 'Supplement exceeded the approved call budget'
        assert hashlib.sha256((root/unchanged_path).read_bytes()).hexdigest() == unchanged_hash
        # These three cases exercise the real supplemental prepare boundary.
        # Base native adoption is separately observed by the five tests above.
        invocation = (root/prepared['invocation']).read_text(encoding='utf-8')
        assert extra in invocation and hashes[extra] in invocation
        assert 'no-replacement' in (root/'docs/task.md').read_text(encoding='utf-8')
        assert (old_workspace/'.memlog.md').read_text(encoding='utf-8') == old_memory
        current = json.dumps([call['result'] for call in calls])
        assert reason in current or extra in current
    except AssertionError:
        print('FAILURE_ID:KQ_44BC8197CE64')
        raise



@pytest.fixture(scope='module')
def spec_supplement_cache():
    # The key identifies one immutable case episode, not a prior run receipt.
    # A new pytest process has an empty cache. No native authority is fabricated.
    return {}


def _spec_supplement_episode(baseline, reason, tmp_path_factory, cache):
    import hashlib
    import shutil
    from unittest.mock import patch
    from scripts.toolchain.bmad_native.testing import load
    from scripts.toolchain.bmad_native import verify
    from scripts.toolchain.knowledge_query import adapter
    if reason in cache:
        return cache[reason]
    root = tmp_path_factory.mktemp('s5-spec-'+reason)/'repository'
    shutil.copytree(baseline['root'], root)
    # Exact prior native memory is inherited input. Current prepare revalidates
    # source bytes and selection; the old runtime result grants no current edge.
    bridge = load('planning_spec_'+reason.replace('-', '_'),
        '.agents/skills/jimuyun-spec/scripts/bridge.py')
    canonical = load('planning_spec_owner_'+reason.replace('-', '_'),
        '.agents/skills/jimuyun-spec/scripts/canonical_package.py')
    spec = '_bmad-output/specs/spec-example/SPEC.md'
    source = root/'docs/source.md'
    before_source = source.read_bytes()
    old_memory = (root/spec).parent.joinpath('.memlog.md').read_text(encoding='utf-8')
    before_contract, _, _ = canonical.build_contract(root, root/spec)
    if reason == 'new-question':
        suffix = '\nNew question: Does retained CAP-1 guarantee Unicode normalization? '
        suffix += 'Check the current basis; leave this unverified guarantee open rather than invent it.\n'
    elif reason == 'missing-basis':
        suffix = '\nPreviously missing accepted basis: CAP-1 is local-only and must not initiate network access.\n'
    elif reason == 'related-source-change':
        suffix = '\nRelevant accepted source clarification: CAP-1 supports UTF-8 text while preserving its existing behavior.\n'
    elif reason == 'preserve-upstream':
        suffix = ('\nApproved upstream constraints: CAP-1 is local-only. '
            'Package B is an explicit non-goal. The S2 schedule is an unresolved '
            'maintainer question and does not authorize parallel execution. '
            'Preserve these along with CAP-1 when deriving the contract.\n')
    elif reason == 'unchanged':
        suffix = ''
    else:
        raise ValueError('Unsupported test scenario: '+reason)
    if suffix:
        source.write_bytes(before_source+suffix.encode('utf-8'))
        # This is the source author's changed input, not an arbitrary mutation of
        # a derived selection: recompute it through the actual canonical owner.
        descriptor, selection, selection_hash = canonical.build_contract(root, root/spec)
        registry = root/'_bmad-output/specs/canonical-spec-package-selections'
        canonical.write_json(registry/(selection_hash.replace(':', '-')+'.json'), selection)
        canonical.write_json(registry/'current/SPEC-example.json', {
            'schema': canonical.CURRENT_SCHEMA, 'package_id': 'SPEC-example',
            'selection_hash': selection_hash})
    actual_source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    calls = []
    original = adapter.diagnose
    def observe(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append({'request': args[0] if args else kwargs.get('request'),
                      'result': json.loads(json.dumps(result))})
        return result
    with patch.object(adapter, 'diagnose', observe):
        # Load after the spy in case the candidate uses a direct import.
        bridge = load('planning_spec_preparation_'+reason.replace('-', '_'),
            '.agents/skills/jimuyun-spec/scripts/bridge.py')
        prepared = bridge.prepare(root, spec, 'logs/bmad-wrappers/spec-'+reason)
    verify(root)
    canonical.validate_selection(root, root/spec,
        root/'_bmad-output/specs/canonical-spec-package-selections/current/SPEC-example.json')
    state = dict(root=root, spec=spec, reason=reason, bridge=bridge,
        canonical=canonical, prepared=prepared, calls=calls,
        old_memory=old_memory, old_contract=before_contract,
        source_bytes=source.read_bytes(), source_hash=actual_source_hash, complete=False)
    cache[reason] = state
    return state


def _spec_supplement_precondition(state):
    if state['reason'] == 'unchanged':
        assert not state['calls'], 'Unchanged verified inheritance triggered unnecessary query'
        return
    assert state['calls'], 'A qualifying factual gap/change did not trigger actual SPEC supplemental query'
    assert len(state['calls']) <= 3
    reads = []
    for call in state['calls']:
        result = call['result']
        assert result.get('schema') == 'planning-query.v1'
        assert result.get('stage') == 'spec' and result.get('consumer') == 'bmad-planning'
        reads.extend(result.get('read_set', []))
    selected = [r for r in reads if r.get('path') == 'docs/source.md']
    assert selected, 'Supplement did not verify the changed/current factual source'
    assert all(r['sha256'].removeprefix('sha256:') == state['source_hash'] for r in selected)
    assert all(r.get('origin') in {'locator', 'direct-source'} and r.get('read_identity') for r in selected)


def _spec_finish_supplement(state):
    import os
    from scripts.toolchain.bmad_native import verify
    if state['complete']:
        return state
    root = state['root']
    run = 'logs/bmad-wrappers/spec-'+state['reason']
    native = root/run/'native'
    sys.path.insert(0, str(ROOT/'scripts/sc'))
    from _llm_backend import run_llm_exec
    import host_session
    session = native/'logs/spec-supplement-session'
    host_session.initialize(native, session, 'chatgpt-work-mode')
    prompt = (root/state['prepared']['invocation']).read_text(encoding='utf-8') + (
        '\nActual native SPEC update sample. Input change class: '+state['reason']+
        '. Read the current source and actual inherited native record; verify source '
        'bytes. Execute the complete native derive and both self-checks. Preserve '
        'CAP-1, valid constraints, non-goals and open questions. Do not promote '
        'provenance into normative companions. Record your own actual reuse or '
        'supplement reason, current source path/hash, read identity and scope impact '
        'through the official memlog command. An unchanged run is cosmetic reuse, '
        'not new query proof. Never claim a hook/query ran unless it actually did. '
        'Do not implement business code or modify test/native resources.\n')
    previous = {k: os.environ.get(k) for k in ('JIMUYUN_HOST_SESSION_DIR','JIMUYUN_HOST_TIMEOUT_SECONDS')}
    try:
        os.environ['JIMUYUN_HOST_SESSION_DIR'] = str(session)
        os.environ.pop('JIMUYUN_HOST_TIMEOUT_SECONDS', None)
        code, trace, _ = run_llm_exec(backend='host-session', root=native,
            prompt=prompt, output_last_message=native/'logs/spec-result.txt',
            timeout_sec=1800, codex_sandbox='workspace-write')
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key,None)
            else:
                os.environ[key]=value
    if code:
        raise RuntimeError(f'SPEC_NATIVE_ENVIRONMENT: exit={code}; {session}; {trace}')
    state['bridge'].publish(root,run)
    canonical=state['canonical']
    descriptor, selection, _ = canonical.build_contract(root,root/state['spec'])
    canonical.validate_selection(root,root/state['spec'],
        root/'_bmad-output/specs/canonical-spec-package-selections/current/SPEC-example.json')
    verify(root);verify(native)
    assert descriptor['sources'] == state['old_contract']['sources']
    assert [(r['path'],r['role']) for r in descriptor['companions']] == [
        (r['path'],r['role']) for r in state['old_contract']['companions']]
    assert (root/'docs/source.md').read_bytes() == state['source_bytes']
    memory=(root/state['spec']).parent.joinpath('.memlog.md').read_text(encoding='utf-8')
    before=state['old_memory'].split('\n---\n',1)[1].strip()
    after=memory.split('\n---\n',1)[1].strip()
    assert after.startswith(before), 'Native update rewrote prior chronological decisions'
    state['added']=after[len(before):].lower()
    state['rendered']=(root/state['spec']).read_text(encoding='utf-8')
    for entry in descriptor['companions']:
        if entry['role']=='normative_companion':
            state['rendered']+='\n'+(root/entry['path']).read_text(encoding='utf-8')
    state['complete']=True
    return state


def _spec_reuse_or_supplement(state):
    _spec_supplement_precondition(state)
    root=state['root']
    native=root/('logs/bmad-wrappers/spec-'+state['reason']+'/native')
    source=native/'docs/source.md'
    assert source.read_bytes()==state['source_bytes']
    invocation=(root/state['prepared']['invocation']).read_text(encoding='utf-8')
    # Actual preparation must carry evidence to the native owner. Native
    # adoption is tested independently, not fabricated for each branch.
    assert 'docs/source.md' in invocation and state['source_hash'] in invocation
    if state['reason']=='unchanged':
        assert 'reuse' in invocation.lower() or 'unchanged' in invocation.lower()
    else:
        assert state['calls'] and state['source_hash'] in json.dumps(state['calls'])
    assert (root/state['spec']).parent.joinpath('.memlog.md').read_text(encoding='utf-8')==state['old_memory']
    state['canonical'].validate_selection(root,root/state['spec'],
        root/'_bmad-output/specs/canonical-spec-package-selections/current/SPEC-example.json')
    return state


@pytest.mark.cer_assertion('ASSERT_B14283217516')
@pytest.mark.parametrize('reason',['unchanged','new-question','missing-basis','related-source-change'])
def test_contract_b14283217516(native_caller_decision,tmp_path_factory,spec_supplement_cache,reason):
    state=_spec_supplement_episode(native_caller_decision,reason,tmp_path_factory,spec_supplement_cache)
    try:
        _spec_reuse_or_supplement(state)
    except AssertionError:
        print('FAILURE_ID:KQ_B14283217516')
        raise


@pytest.mark.cer_assertion('ASSERT_D44E7CF213F2')
@pytest.mark.parametrize('reason',['unchanged','new-question','missing-basis','related-source-change'])
def test_contract_d44e7cf213f2(native_caller_decision,tmp_path_factory,spec_supplement_cache,reason):
    state=_spec_supplement_episode(native_caller_decision,reason,tmp_path_factory,spec_supplement_cache)
    try:
        _spec_reuse_or_supplement(state)
    except AssertionError:
        print('FAILURE_ID:KQ_D44E7CF213F2')
        raise


@pytest.mark.cer_assertion('ASSERT_6C0520FE0D5E')
@pytest.mark.parametrize('reason',['unchanged','new-question','missing-basis','related-source-change'])
def test_contract_6c0520fe0d5e(native_caller_decision,tmp_path_factory,spec_supplement_cache,reason):
    state=_spec_supplement_episode(native_caller_decision,reason,tmp_path_factory,spec_supplement_cache)
    try:
        _spec_reuse_or_supplement(state)
    except AssertionError:
        print('FAILURE_ID:KQ_6C0520FE0D5E')
        raise


@pytest.mark.cer_assertion('ASSERT_B34E35470A88')
@pytest.mark.parametrize('reason',['unchanged','related-source-change'])
def test_contract_b34e35470a88(native_caller_decision,tmp_path_factory,spec_supplement_cache,reason):
    state=_spec_supplement_episode(native_caller_decision,reason,tmp_path_factory,spec_supplement_cache)
    try:
        _spec_reuse_or_supplement(state)
    except AssertionError:
        print('FAILURE_ID:KQ_B34E35470A88')
        raise


@pytest.mark.cer_assertion('ASSERT_21EB4214946A')
def test_contract_21eb4214946a(native_caller_decision,tmp_path_factory,spec_supplement_cache):
    state=_spec_supplement_episode(native_caller_decision,'preserve-upstream',tmp_path_factory,spec_supplement_cache)
    try:
        _spec_supplement_precondition(state)
        actual=_spec_finish_supplement(state)
        rendered=actual['rendered'].lower()
        assert 'cap-1' in rendered and 'local-only' in rendered
        assert 'package b' in rendered
        assert 's2' in rendered and ('unresolved' in rendered or 'pending' in rendered)
        assert ('does not authorize parallel' in rendered or 'no parallel' in rendered
            or 'not parallel permission' in rendered)
    except AssertionError:
        print('FAILURE_ID:KQ_21EB4214946A')
        raise



def _execute_prd_source_consumer_sample(tmp_path_factory, native_runtime_environment):
    import hashlib
    import os
    import shutil
    from scripts.toolchain.bmad_native.testing import fixture
    from scripts.toolchain.bmad_native import verify, write_config
    sys.path.insert(0, str(ROOT/'scripts/sc'))
    from _llm_backend import run_llm_exec
    import host_session

    base = tmp_path_factory.mktemp('s5-prd-source-consumer')
    root, paths, request = published_planning.__wrapped__(base)
    installed = fixture(base/'verified-native')
    for prefix in ('.agents', '_bmad'):
        shutil.copytree(installed/prefix, root/prefix, dirs_exist_ok=True)
    # These additional original skills are installed from the pinned upstream
    # tree by the environment owner, not supplied by this test as replacements.
    for skill in ('bmad-prd', 'bmad-review'):
        shutil.copytree(ROOT/'.agents/skills'/skill, root/'.agents/skills'/skill)
    for relative in ('scripts/toolchain', 'scripts/python'):
        shutil.copytree(ROOT/relative, root/relative, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    custom = root/'_bmad/custom/bmad-prd.toml'
    custom.parent.mkdir(parents=True, exist_ok=True)
    custom.write_bytes((ROOT/'_bmad/custom/bmad-prd.toml').read_bytes())
    write_config(root)
    verify(root)
    _s7_write_config((root, paths, request))
    sources = {
        'src/current.py': 'def normalize_name(value):\n    return value.strip().lower()\n',
        'docs/history.md': '# Historical plan only\nBulk export was proposed but never implemented.\n',
        'docs/exclusions.md': '# Approved exclusions\nRemote synchronization is excluded.\n',
        'docs/rumor.md': '# Unverified claim\nA partner may support spreadsheet import; no implementation or confirmed interface is supplied.\n',
        'docs/request.md': '# Internal solo utility increment\n'
            'The maintained utility has a current name-normalization function. '
            'Create a small PRD that reuses current behavior and adds name deduplication. '
            'Read the local current code and the supplied historical/exclusion/unverified '
            'sources before deciding what already exists and what work is proposed. '
            'Bulk export is only historical planning. Remote synchronization stays excluded. '
            'Spreadsheet import remains awaiting verification. The genuine new requested '
            'behavior is deduplication. Do not implement code or design an architecture.\n',
    }
    for relative, content in sources.items():
        target = root/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    source_hashes = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sources}
    native_files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in (root/'.agents/skills/bmad-prd', root/'.agents/skills/bmad-review', root/'_bmad/scripts')
        for p in folder.rglob('*') if p.is_file()}

    import subprocess
    configured = subprocess.run(['uv', 'run', str(root/'_bmad/scripts/resolve_customization.py'),
        '--project-root', str(root), '--skill', str(root/'.agents/skills/bmad-prd'), '--key', 'workflow'],
        capture_output=True, text=True, encoding='utf-8', shell=False, timeout=30)
    if configured.returncode:
        raise RuntimeError('PRD_NATIVE_RESOLVER_UNAVAILABLE: '+configured.stderr)
    effective = json.loads(configured.stdout)['workflow']
    hooks = effective.get('activation_steps_prepend', []) + effective.get('activation_steps_append', [])
    assert any('prepare-consumption' in hook for hook in hooks), 'Native resolver has no default predecision query hook'

    # Observe real child calls without replacing adapter/Locator results. Every
    # native Python invocation must retain this test-only PYTHONPATH. Absence of
    # all observed memlog calls is a harness error, never evidence of missing query.
    observer = base/'observer'
    observer.mkdir()
    trace = base/'native-calls.jsonl'
    observer_code = r'''
import json, os, sys, time
from pathlib import Path
root = Path(os.environ['JIMUYUN_PRD_TEST_ROOT']).resolve()
trace = Path(os.environ['JIMUYUN_PRD_TEST_TRACE'])
prefix = str(root) + os.sep

def observe(frame, event, value):
    filename = frame.f_code.co_filename
    if not filename.startswith(prefix):
        return
    relative = filename[len(prefix):].replace(os.sep, '/')
    name = frame.f_code.co_name
    record = None
    if relative == '_bmad/scripts/memlog.py' and name == 'cmd_append' and event == 'call':
        args = frame.f_locals.get('args')
        record = {'kind': 'memlog-append', 'type': getattr(args, 'type', None),
                  'text': getattr(args, 'text', None)}
    elif relative == 'scripts/toolchain/knowledge_query/adapter.py' and event == 'return':
        if isinstance(value, dict) and value.get('schema') == 'planning-query.v1':
            record = {'kind': 'query-return', 'function': name, 'value': value}
    if record is not None:
        record['monotonic_ns'] = time.monotonic_ns()
        with trace.open('a', encoding='utf-8') as output:
            output.write(json.dumps(record, ensure_ascii=False) + '\n')
sys.setprofile(observe)
'''
    (observer/'sitecustomize.py').write_text(observer_code, encoding='utf-8')
    session = root/'logs/prd-native-session'
    host_session.initialize(root, session, 'chatgpt-work-mode')
    workspace = root/'_bmad-output/planning-artifacts/prds/prd-source-sample'
    prompt = (
        'Execute the complete original project-local bmad-prd Skill at '
        + str(root/'.agents/skills/bmad-prd/SKILL.md')
        + '. Read all references required by its headless Create path. '
        'Project root: '+str(root)+'. headless=true; intent=create. '
        'Input brief: docs/request.md; additional source inputs: '
        + json.dumps(list(sources)) + '. doc_workspace='+str(workspace)+'. '
        'This is an isolated small internal/solo sample. Preserve source files and '
        'official Skill/runtime bytes. Use only actual source findings, and keep '
        'native memlog ownership and all required native self-checks. Do not '
        'implement code, run downstream stages, write test output or manufacture '
        'a query result. Return the official headless JSON result.\n'
        'Test instrumentation only, not a workflow customization: for EVERY '
        'Python/uv command preserve PYTHONDONTWRITEBYTECODE=1, UV_OFFLINE=1, '
        'UV_CACHE_DIR=/tmp/ji-mu-yun-uv-cache and the following environment: '
        + json.dumps({'PYTHONPATH': str(observer), 'JIMUYUN_PRD_TEST_ROOT': str(root),
                      'JIMUYUN_PRD_TEST_TRACE': str(trace)})
        + '. Do not write or edit the observer or trace. The observer only records '
        'actually reached adapter returns and official memlog append calls.\n')
    previous = {k: os.environ.get(k) for k in ('JIMUYUN_HOST_SESSION_DIR', 'JIMUYUN_HOST_TIMEOUT_SECONDS')}
    try:
        os.environ['JIMUYUN_HOST_SESSION_DIR'] = str(session)
        os.environ.pop('JIMUYUN_HOST_TIMEOUT_SECONDS', None)
        code, transport, _ = run_llm_exec(backend='host-session', root=root,
            prompt=prompt, output_last_message=root/'logs/native-prd-result.txt',
            timeout_sec=1800, codex_sandbox='workspace-write')
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    if code:
        raise RuntimeError(f'PRD_NATIVE_EXECUTION_UNAVAILABLE: {code}; {session}; {transport}')
    verify(root)
    for path, expected in {**source_hashes, **native_files}.items():
        if hashlib.sha256((root/path).read_bytes()).hexdigest() != expected:
            raise RuntimeError('PRD_NATIVE_MODIFIED_READ_ONLY_SOURCE: '+path)
    if not trace.is_file():
        raise RuntimeError('PRD_NATIVE_INSTRUMENTATION_NOT_REACHED')
    events = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
    if not any(e['kind'] == 'memlog-append' for e in events):
        raise RuntimeError('PRD_NATIVE_MEMLOG_OBSERVER_NOT_REACHED')
    memory = (workspace/'.memlog.md').read_text(encoding='utf-8')
    prd = (workspace/'prd.md').read_text(encoding='utf-8')
    addendum = (workspace/'addendum.md').read_text(encoding='utf-8') if (workspace/'addendum.md').exists() else ''
    return dict(root=root, memory=memory, prd=prd, addendum=addendum,
        events=events, source_hashes=source_hashes, workspace=workspace)


def _prd_source_decision(sample, path):
    lines = [line.lower() for line in sample['memory'].splitlines()
             if '(decision)' in line and path in line]
    assert lines, 'Native caller did not bind a source decision: '+path
    matching = [line for line in lines if sample['source_hashes'][path] in line]
    assert matching, 'Native source decision does not identify actual read bytes: '+path
    return '\n'.join(matching)


@pytest.mark.cer_assertion('ASSERT_03668F0ADF94')
def test_contract_03668f0adf94(prd_source_consumer_sample):
    sample = prd_source_consumer_sample
    try:
        current = _prd_source_decision(sample, 'src/current.py')
        history = _prd_source_decision(sample, 'docs/history.md')
        excluded = _prd_source_decision(sample, 'docs/exclusions.md')
        unverified = _prd_source_decision(sample, 'docs/rumor.md')
        request = _prd_source_decision(sample, 'docs/request.md')
        assert 'normaliz' in current and ('existing' in current or 'implemented' in current)
        assert 'bulk export' in history and any(term in history for term in ('planning-only', 'not implemented', 'never implemented'))
        assert 'remote synchronization' in excluded and ('excluded' in excluded or 'non-goal' in excluded)
        assert 'spreadsheet import' in unverified and ('unverified' in unverified or 'awaiting verification' in unverified)
        assert 'deduplication' in request and ('new' in request or 'proposed' in request)
    except AssertionError:
        print('FAILURE_ID:KQ_03668F0ADF94')
        raise


@pytest.mark.cer_assertion('ASSERT_920AD324F19B')
def test_contract_920ad324f19b(prd_source_consumer_sample):
    sample = prd_source_consumer_sample
    try:
        existing = _prd_source_decision(sample, 'src/current.py')
        proposed = _prd_source_decision(sample, 'docs/request.md')
        assert 'normaliz' in existing and ('reuse' in existing or 'retain' in existing)
        assert 'deduplication' in proposed and ('new' in proposed or 'gap' in proposed)
        scope = (sample['prd']+'\n'+sample['addendum']).lower()
        assert 'deduplication' in scope and 'normaliz' in scope
        assert ('reuse' in scope or 'retain' in scope) and ('non-goal' in scope or 'excluded' in scope)
        # The real producer must never preclaim the native owner's adoption.
        results = [e['value'] for e in sample['events'] if e['kind'] == 'query-return']
        assert results, 'No actual adapter return was observed; adoption ownership cannot be inferred from an empty set'
        assert all(not r.get('adopted') and not r.get('authorizes') for r in results)
    except AssertionError:
        print('FAILURE_ID:KQ_920AD324F19B')
        raise


@pytest.mark.cer_assertion('ASSERT_4E03A6CCB9A1')
def test_contract_4e03a6ccb9a1(prd_source_consumer_sample):
    sample = prd_source_consumer_sample
    try:
        query = [e for e in sample['events'] if e['kind'] == 'query-return']
        assert query, 'Actual PRD source judgment had no observed planning-query result'
        relevant_decisions = [e for e in sample['events'] if e['kind'] == 'memlog-append'
            and e['type'] == 'decision' and any(p in str(e.get('text')) for p in sample['source_hashes'])]
        assert relevant_decisions
        first_decision = min(e['monotonic_ns'] for e in relevant_decisions)
        before = [e for e in query if e['monotonic_ns'] < first_decision]
        assert before, 'The actual query/read did not precede the source judgment'
        reads = {r['path']: r for e in before for r in e['value'].get('read_set', [])}
        for path in ('src/current.py', 'docs/history.md', 'docs/rumor.md'):
            assert path in reads
            assert reads[path]['sha256'].removeprefix('sha256:') == sample['source_hashes'][path]
            _prd_source_decision(sample, path)
        current = _prd_source_decision(sample, 'src/current.py')
        history = _prd_source_decision(sample, 'docs/history.md')
        uncertain = _prd_source_decision(sample, 'docs/rumor.md')
        assert 'reuse' in current or 'retain' in current
        assert any(term in history for term in ('planning-only', 'not implemented', 'never implemented'))
        assert 'unverified' in uncertain or 'awaiting verification' in uncertain
    except AssertionError:
        print('FAILURE_ID:KQ_4E03A6CCB9A1')
        raise



def _execute_vdd_complete_consumption(tmp_path_factory):
    import hashlib
    import os
    import shutil
    import subprocess

    pre_base = tmp_path_factory.mktemp('s5-vdd-prequery')
    pre_fixture = published_planning.__wrapped__(pre_base)
    pre_observation = _vdd_public_first_worker(pre_fixture, pre_base, governance='off')
    _assert_actual_vdd_prequery(pre_observation)
    base = tmp_path_factory.mktemp('s5-vdd-complete')
    fixture = published_planning.__wrapped__(base)
    root, _, _ = fixture
    for relative in ('scripts', '.agents/skills/vdd-execution-plan',
                     '.agents/skills/quick-dev-tdd-adapter/tools'):
        shutil.copytree(ROOT/relative, root/relative, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    _s7_write_config(fixture)
    files = {
        'src/existing.py': 'def indexed_value():\n    return 13\n',
        'src/unindexed.py': 'def unindexed_value():\n    return 29\n',
        'src/combined.py': 'def combined():\n    return None\n',
        'src/caller.py': 'from combined import combined\ndef report():\n    return combined()\n',
        'tests/test_combined.py': (
            'from pathlib import Path\nimport sys\nimport hashlib\nimport pytest\n'
            "sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))\n"
            'from combined import combined\nfrom existing import indexed_value\n'
            'from unindexed import unindexed_value\n'
            "ROOT = Path(__file__).resolve().parents[1]\n"
            "@pytest.mark.cer_assertion('ASSERT_COMBINED')\n"
            'def test_combined():\n    assert combined() == 42\n'
            "@pytest.mark.cer_assertion('ASSERT_SOURCE_READS')\n"
            'def test_source_inputs():\n'
            "    for name in ('src/existing.py', 'src/unindexed.py', 'src/caller.py', 'docs/control.md'):\n"
            "        assert (ROOT/name).read_text(encoding='utf-8').strip()\n"
            '    assert indexed_value() == 13 and unindexed_value() == 29\n'
            "@pytest.mark.cer_assertion('ASSERT_WRITE_BOUNDARY')\n"
            'def test_protected_sources():\n'
            '    for name, expected in PROTECTED_HASHES.items():\n'
            '        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected\n'
            "@pytest.mark.cer_assertion('ASSERT_HARNESS')\n"
            'def test_real_entry():\n'
            '    assert callable(combined) and callable(indexed_value) and callable(unindexed_value)\n'),
        'docs/control.md': '# Current control\nExisting helper APIs are read-only; do not duplicate their implementations.\n',
    }
    # These inputs are deliberately added after the real publication, so the
    # unindexed helper cannot be inferred absent merely from a valid index miss.
    for relative, content in files.items():
        target = root/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    protected = {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                 for name in ('src/existing.py', 'src/unindexed.py', 'src/caller.py', 'docs/control.md')}
    files['tests/test_combined.py'] += '\nPROTECTED_HASHES = ' + repr(protected) + '\n'
    (root/'tests/test_combined.py').write_text(files['tests/test_combined.py'], encoding='utf-8')
    requirements = root/'requirements.md'
    requirements.write_text(
        '# FR-1\n'
        'Implement `src/combined.py::combined` to return the sum of the current '
        'return values of `src/existing.py::indexed_value` and '
        '`src/unindexed.py::unindexed_value`. Inspect their actual current source; '
        'do not infer either value or absence from index coverage. Reuse those '
        'helpers unchanged, and do not create replacement implementations. '
        'Inspect the actual caller `src/caller.py`, test `tests/test_combined.py`, '
        'and control contract `docs/control.md` before forming scope. '
        'Production owner: `src/combined.py`. Production implementation may modify '
        'only the production owner. Existing fixture `tests/test_combined.py`. '
        'Preserve both helper APIs and their current behavior. Do not modify '
        '`src/existing.py`, `src/unindexed.py`, `src/caller.py`, or `docs/control.md`. '
        'Use the existing real pytest entry; missing imports or harness failures '
        'are not behavioral RED.\n', encoding='utf-8')
    before = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files}
    session = root/'logs/live-vdd-consumption'
    owner_cli = root/'scripts/sc/host_session.py'
    init = subprocess.run([sys.executable, '-B', str(owner_cli), 'init', '--session', str(session),
        '--caller', 'chatgpt-work-mode'], cwd=root, capture_output=True, text=True,
        encoding='utf-8', shell=False, timeout=15)
    if init.returncode:
        raise RuntimeError('VDD_LIVE_SESSION_SETUP_FAILED: ' + init.stdout + init.stderr)
    trace = root/'logs/live-vdd-trace.jsonl'
    bootstrap = r'''
import json, pathlib, runpy, sys, time
root, trace = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
args = sys.argv[3:]
stream = trace.open('x', encoding='utf-8')
def observe(frame, event, arg):
    if event not in {'call', 'return'}:
        return
    filename = frame.f_code.co_filename.replace('\\', '/')
    if not filename.endswith(('scripts/toolchain/knowledge_query/adapter.py',
                              'scripts/python/_knowledge_locator_core.py',
                              'scripts/sc/host_session.py')):
        return
    try:
        relative = pathlib.Path(frame.f_code.co_filename).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return
    name = frame.f_code.co_name
    relevant = (relative == 'scripts/toolchain/knowledge_query/adapter.py'
        or (relative == 'scripts/python/_knowledge_locator_core.py' and name == 'query_with_diagnostics')
        or (relative == 'scripts/sc/host_session.py' and name == 'execute'))
    if not relevant:
        return
    row = {'path': relative, 'function': name, 'event': event, 'monotonic_ns': time.monotonic_ns()}
    if event == 'return' and relative.endswith('/adapter.py') and isinstance(arg, dict):
        # The actual return value, not a fabricated fixture result.
        row['actual_return'] = arg
    stream.write(json.dumps(row, sort_keys=True) + '\n')
    stream.flush()
sys.path.insert(0, str(root))
sys.argv = [str(root/'scripts/vdd/compile_plan.py'), *args]
sys.setprofile(observe)
try:
    runpy.run_path(sys.argv[0], run_name='__main__')
finally:
    sys.setprofile(None)
    stream.close()
'''
    out = root/'execution-plans/live-consumption'
    result = root/'logs/live-compiler-result.json'
    env = {**os.environ, 'SC_LLM_BACKEND': 'host-session',
           'JIMUYUN_HOST_SESSION_DIR': str(session), 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTHONUTF8': '1'}
    for name in ('JIMUYUN_HOST_TIMEOUT_SECONDS', 'JIMUYUN_GOVERNANCE_MODE', 'PHASEA_SERVICE_STATE'):
        env.pop(name, None)
    stdout, stderr = root/'logs/live-vdd.stdout', root/'logs/live-vdd.stderr'
    with stdout.open('wb') as output, stderr.open('wb') as errors:
        child = subprocess.Popen([sys.executable, '-B', '-c', bootstrap, str(root), str(trace),
            '--requirements', str(requirements), '--out-dir', str(out), '--profile', 'self-hosted',
            '--result-json', str(result)], cwd=root, env=env, stdout=output, stderr=errors, shell=False)
        try:
            child.wait(timeout=1800)
        except subprocess.TimeoutExpired as exc:
            child.terminate()
            child.wait(timeout=10)
            raise RuntimeError('VDD_LIVE_SAMPLE_TIMEOUT: actual compiler did not finish inside the frozen test budget; ' + str(session)) from exc
    if child.returncode != 0 or not result.is_file():
        raise RuntimeError('VDD_LIVE_SAMPLE_FAILED: ' + stdout.read_text(encoding='utf-8') + stderr.read_text(encoding='utf-8'))
    native_result = json.loads(result.read_text(encoding='utf-8'))
    if native_result.get('status') != 'plan-ready':
        raise RuntimeError('VDD_LIVE_SAMPLE_NOT_READY: ' + json.dumps(native_result))
    bundle = json.loads((out/'semantic-plan-bundle.v1.json').read_text(encoding='utf-8'))
    source_index = json.loads((out/'source-index.v1.json').read_text(encoding='utf-8'))
    events = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
    requests = []
    for path in session.glob('*/request.json'):
        request = json.loads(path.read_text(encoding='utf-8'))
        if '\n\nINPUT:\n' in request['prompt']:
            requests.append(json.loads(request['prompt'].split('\n\nINPUT:\n', 1)[1]))
    return dict(root=root, out=out, before=before, files=files, bundle=bundle,
        source_index=source_index, events=events, requests=requests,
        requirement_sha256=hashlib.sha256(requirements.read_bytes()).hexdigest())


def _vdd_actual_read_context(sample):
    import hashlib
    events = sample['events']
    first_worker = next((e['monotonic_ns'] for e in events
                         if e['path'] == 'scripts/sc/host_session.py' and e['event'] == 'call'), None)
    if first_worker is None:
        raise RuntimeError('VDD_LIVE_SAMPLE_HAS_NO_REAL_SEMANTIC_REQUEST')
    responses = [e['actual_return'] for e in events if e.get('actual_return', {}).get('schema') == 'planning-query.v1'
                 and e['monotonic_ns'] < first_worker]
    assert responses, 'No actual planning-query return preceded semantic extraction'
    assert all(r['consumer'] == 'vdd' and r['stage'] == 'vdd-create' for r in responses)
    read_rows = [row for response in responses for row in response['read_set']]
    required = {'src/existing.py', 'src/unindexed.py', 'src/caller.py',
                'tests/test_combined.py', 'docs/control.md'}
    for path in required:
        matches = [row for row in read_rows if row.get('path') == path]
        assert matches, 'Actual preplanning read missing: ' + path
        assert any(row.get('sha256', '').removeprefix('sha256:') == sample['before'][path] for row in matches)
        assert hashlib.sha256((sample['root']/path).read_bytes()).hexdigest() == sample['before'][path]
    for path in ('src/existing.py', 'src/unindexed.py'):
        assert any(row.get('path') == path and row.get('origin') == 'direct-source' for row in read_rows)
    return responses, read_rows


def _vdd_real_scope(sample):
    bundle = sample['bundle']
    assert bundle['obligations'] and bundle['acceptances'] and bundle['slices']
    owners = {path for piece in bundle['slices'] for path in piece['production_owners']}
    assert owners == {'src/combined.py'}, 'Native scope duplicated or rewrote an existing helper'
    for piece in bundle['slices']:
        assert set(piece['allowed_write_paths']) <= {'src/combined.py', 'tests/test_combined.py'}
        assert not piece['planned_new_files'], 'All authorized production/test entries already exist'
    relevant = [a for a in bundle['acceptances'] if 'combined' in json.dumps(a['oracle']).lower()]
    assert relevant, 'The requested genuine gap has no native Acceptance'
    assert all(a['obligation_ids'] for a in relevant)
    for acceptance in relevant:
        owners_for_acceptance = {path for piece in bundle['slices']
            if acceptance['acceptance_id'] in piece['acceptance_ids'] for path in piece['production_owners']}
        assert owners_for_acceptance == {'src/combined.py'}
    # Validating this graph does not label runtime behavior present or missing.
    # Those classifications still belong to the later controlled probe.
    assert all(intent.get('disposition') not in {'present', 'missing'}
               for intent in bundle.get('behavior_routing', {}).get('intents', []))
    return relevant


@pytest.mark.cer_assertion('ASSERT_E4C02160E0CC')
def test_contract_e4c02160e0cc(vdd_complete_consumption):
    try:
        _vdd_actual_read_context(vdd_complete_consumption)
        _vdd_real_scope(vdd_complete_consumption)
    except AssertionError:
        print('FAILURE_ID:KQ_E4C02160E0CC')
        raise


@pytest.mark.cer_assertion('ASSERT_2678EA925C89')
def test_contract_2678ea925c89(vdd_complete_consumption):
    try:
        _vdd_actual_read_context(vdd_complete_consumption)
        relevant = _vdd_real_scope(vdd_complete_consumption)
        # The native V3 producer must have received the frozen requirement bytes,
        # not an unbound substitute. Source hashes are checked independently of
        # successful compiler exit or the existence of a context file.
        contracts = []
        for request in vdd_complete_consumption['requests']:
            # The public V3 group-repair transport wraps the same frozen input.
            # Unwrap only that explicit protocol, never an arbitrary nested object.
            producer = request
            if request.get('original_stage') == 'v3':
                assert isinstance(request.get('input'), dict)
                producer = request['input']
            contracts.extend(producer.get('source_contracts', []))
        assert contracts
        import hashlib
        actual_text = (vdd_complete_consumption['root']/'requirements.md').read_text(encoding='utf-8').strip()
        for contract in contracts:
            assert contract['source_text'] == actual_text
            assert hashlib.sha256(contract['source_text'].encode('utf-8')).hexdigest() == contract['text_sha256'].removeprefix('sha256:')
        assert all(c['source_sha256'].removeprefix('sha256:') ==
                   vdd_complete_consumption['requirement_sha256'] for c in contracts)
        refs = {c['source_ref'] for c in contracts}
        assert all(set(a['source_refs']) <= refs for a in relevant)
    except AssertionError:
        print('FAILURE_ID:KQ_2678EA925C89')
        raise


@pytest.mark.cer_assertion('ASSERT_A37D4E43898B')
def test_contract_a37d4e43898b(vdd_complete_consumption):
    try:
        _, reads = _vdd_actual_read_context(vdd_complete_consumption)
        assert any(r['path'] == 'src/unindexed.py' and r['origin'] == 'direct-source' for r in reads)
        _vdd_real_scope(vdd_complete_consumption)
    except AssertionError:
        print('FAILURE_ID:KQ_A37D4E43898B')
        raise


@pytest.mark.cer_assertion('ASSERT_121ED996CEAE')
def test_contract_121ed996ceae(vdd_complete_consumption):
    try:
        _vdd_actual_read_context(vdd_complete_consumption)
        _vdd_real_scope(vdd_complete_consumption)
        # Existing source is executed here independently of the plan's prose.
        import runpy
        root = vdd_complete_consumption['root']
        assert runpy.run_path(str(root/'src/existing.py'))['indexed_value']() == 13
        assert runpy.run_path(str(root/'src/unindexed.py'))['unindexed_value']() == 29
        existing = {'src/existing.py', 'src/unindexed.py'}
        assert not any(existing & set(s['production_owners']) for s in vdd_complete_consumption['bundle']['slices'])
    except AssertionError:
        print('FAILURE_ID:KQ_121ED996CEAE')
        raise



def _s5_prd_chain(sample):
    """Join actual hook result, verified reads and native use by source identity."""
    decisions = [e for e in sample['events'] if e['kind'] == 'memlog-append'
                 and e.get('type') == 'decision']
    assert decisions
    first = min(e['monotonic_ns'] for e in decisions)
    results = [e['value'] for e in sample['events']
               if e['kind'] == 'query-return' and e['monotonic_ns'] < first]
    assert results, 'No actual predecision PRD hook/query return'
    assert all(r['consumer'] == 'bmad-planning' and r['stage'] == 'prd' for r in results)
    assert all(r['diagnostic']['effective_config']['enabled'] is True for r in results)
    assert all(r['diagnostic']['effective_config']['origins'] for r in results)
    reads = {r['path']: r for result in results for r in result['read_set']}
    for path in ('src/current.py', 'docs/history.md', 'docs/exclusions.md', 'docs/rumor.md'):
        assert path in reads and reads[path]['sha256'].removeprefix('sha256:') == sample['source_hashes'][path]
        assert reads[path]['read_identity']
        decision = _prd_source_decision(sample, path)
        assert ('accepted' in decision or 'rejected' in decision
            or ('unverified' in decision and 'not adopted' in decision))
    current = _prd_source_decision(sample, 'src/current.py')
    assert 'reuse' in current or 'retain' in current
    assert any(term in _prd_source_decision(sample, 'docs/history.md')
        for term in ('planning-only', 'not implemented', 'never implemented'))
    assert all(not r.get('adopted') and not r.get('authorizes') for r in results)
    return results


def _s5_unverified_scope(sample):
    _s5_prd_chain(sample)
    unknown = _prd_source_decision(sample, 'docs/rumor.md')
    assert 'spreadsheet import' in unknown and ('unverified' in unknown or 'awaiting verification' in unknown)
    assert any(word in unknown for word in ('defer', 'pending', 'blocked', 'not adopted', 'rejected'))
    current = _prd_source_decision(sample, 'src/current.py')
    assert 'normaliz' in current and ('reuse' in current or 'retain' in current)
    scope = (sample['prd'] + '\n' + sample['addendum']).lower()
    assert 'deduplication' in scope
    assert 'spreadsheet import' in scope and any(word in scope for word in ('unverified', 'pending', 'open question'))
    assert 'remote synchronization' in scope and any(word in scope for word in ('excluded', 'non-goal'))


def _s5_all_consumers(prd, architecture, native, vdd):
    _s5_prd_chain(prd)
    _architecture_predecision_read(architecture, ['docs/current-adr.md', 'docs/upstream.md', 'src/transport.py'])
    actual, decisions = _architecture_decisions(architecture)
    assert 'TransportOwner' in actual['spine']
    assert 'stdio' in _architecture_source_decision(architecture, decisions, 'src/transport.py')
    added = _native_decision_body(native)
    assert 'accepted' in added and 'rejected' in added and 'retain' in added
    _vdd_actual_read_context(vdd)
    _vdd_real_scope(vdd)
    # These are native decisions, not an adapter-adopted field or static prompt.
    for result in _s5_prd_chain(prd):
        assert not result.get('authorizes') and not result.get('adopted')


def _s5_direct_discovery(vdd):
    _, rows = _vdd_actual_read_context(vdd)
    _vdd_real_scope(vdd)
    import hashlib
    for name in ('src/existing.py', 'src/unindexed.py'):
        found = [r for r in rows if r['path'] == name]
        assert found and all(r['origin'] == 'direct-source' for r in found)
        assert all(r['sha256'].removeprefix('sha256:') == hashlib.sha256((vdd['root']/name).read_bytes()).hexdigest() for r in found)
    assert all(not r.get('adopted') and not r.get('authorizes') for r in vdd['events'] if isinstance(r, dict))


def _s5_required_gate(fixture):
    _s7_write_config(fixture)
    result = _planning_operation(fixture)
    assert result['outcome'] == 'hit'
    assert not result.get('authorizes') and not result.get('required_gate_satisfied')
    assert _s7_required_gate(fixture, True) == 'required_modules_unsatisfied'
    from scripts.toolchain.bmad_native.testing import load
    owner = load('s5_required_governance_owner', '.agents/skills/quick-dev-tdd-adapter/tools/governance_policy.py')
    for phase in ('development', 'test', 'production'):
        policy = owner.resolve_governance_policy('on', environment={'PHASEA_SERVICE_STATE': phase})
        assert policy['enabled'] is True and policy['checks'] == list(owner.GOVERNANCE_CHECKS)


def _s5_default_vdd(fixture, tmp_path):
    observation = _vdd_public_first_worker(fixture, tmp_path, governance='off')
    _assert_actual_vdd_prequery(observation)
    # The intentionally cancelled first worker did not publish completed scope.
    assert not (observation['out']/'semantic-plan-bundle.v1.json').exists()
    names = [p.name.lower() for p in observation['out'].rglob('*') if p.is_file()]
    assert not any('attestation' in name or 'knowledge-freeze' in name for name in names)


def _s5_native_configuration(sample):
    import subprocess, hashlib
    from scripts.toolchain.bmad_native import verify
    root = sample['root']
    native_before = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for prefix in ('.agents/skills/bmad-prd', '.agents/skills/bmad-review', '_bmad/scripts')
        for p in (root/prefix).rglob('*') if p.is_file()}
    custom = root/'_bmad/custom/bmad-prd.toml'
    before = custom.read_bytes()
    resolved = subprocess.run(['uv', 'run', str(root/'_bmad/scripts/resolve_customization.py'),
        '--project-root', str(root), '--skill', str(root/'.agents/skills/bmad-prd'), '--key', 'workflow'],
        capture_output=True, text=True, encoding='utf-8', shell=False, timeout=30)
    if resolved.returncode:
        raise RuntimeError('OFFICIAL_CUSTOMIZATION_RESOLVER_UNAVAILABLE: '+resolved.stderr)
    workflow = json.loads(resolved.stdout)['workflow']
    hooks = workflow.get('activation_steps_prepend', []) + workflow.get('activation_steps_append', [])
    assert hooks and any('prepare-consumption' in hook for hook in hooks)
    assert custom.read_bytes() == before
    verify(root)
    assert native_before == {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in native_before}
    results = _s5_prd_chain(sample)
    episodes = {r['episode_id'] for r in results}
    assert len(episodes) == 1, 'One unchanged input trigger must not create new episodes'
    assert max(r['budget_usage']['calls'] for r in results) == 1


def _s5_cosmetic(native, tmp_path_factory, cache):
    unchanged = _spec_supplement_episode(native, 'unchanged', tmp_path_factory, cache)
    changed = _spec_supplement_episode(native, 'related-source-change', tmp_path_factory, cache)
    _spec_reuse_or_supplement(unchanged)
    _spec_reuse_or_supplement(changed)
    assert not unchanged['calls'] and changed['calls']
    assert unchanged['source_hash'] != changed['source_hash']


def _s5_windows_current(tmp_path):
    # Real platform execution only. No skip, canned result, or Linux substitute.
    for scenario in ('unicode-path-utf8', 'subprocess-timeout', 'subprocess-cancel'):
        folder = tmp_path/scenario
        folder.mkdir()
        test_windows_planning_query_runtime(folder, scenario)


def _s5_prd_identity(fixture, mode):
    """AD-5: exercise the public hook before and after input becomes known."""
    import subprocess
    root, paths, request = fixture
    _s7_write_config(fixture)
    def invoke(task):
        payload = {'stage': 'prd', 'operation': 'create', 'task_id': task,
            'mode': mode, 'inputs': ['AGENTS.md'], 'query': 'repository rules',
            'scope': ['AGENTS.md'], 'record_path': 'logs/prd-query.md'}
        result = subprocess.run([sys.executable, '-B',
            str(ROOT/'scripts/toolchain/knowledge_query/adapter.py'),
            'prepare-consumption', '--repository-root', str(root)],
            input=json.dumps(payload), text=True, encoding='utf-8',
            capture_output=True, shell=False, timeout=35)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip(), 'Public prepare-consumption returned no observation'
        return json.loads(result.stdout)
    pending = invoke(None)
    assert pending['status'] == 'awaiting-input'
    assert not pending.get('queried') and not pending.get('query_result')
    known = invoke('prd-identity-'+mode)
    assert known['status'] == 'prepared' and known['queried'] is True
    result = known['query_result']
    assert result['stage'] == 'prd' and result['consumer'] == 'bmad-planning'
    assert any(r['path'] == 'AGENTS.md' for r in result['read_set'])
    assert not known.get('adopted') and not known.get('authorizes')


def _s5_reinstall(sample, tmp_path):
    """Real scoped native reinstall with external customization preserved."""
    import shutil, hashlib, subprocess
    from scripts.toolchain.bmad_native import verify
    source_receipt = json.loads((ROOT/'_bmad/jimuyun-native-install.json').read_text())
    source = Path(source_receipt['installed_from'])
    if not source.is_dir():
        raise OSError('PINNED_OFFICIAL_REINSTALL_SOURCE_UNAVAILABLE')
    target = tmp_path/'reinstall'
    shutil.copytree(sample['root'], target)
    custom = target/'_bmad/custom/bmad-prd.toml'
    before_custom = custom.read_bytes()
    before = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for prefix in ('.agents/skills/bmad-prd', '.agents/skills/bmad-review',
                       '.agents/skills/bmad-spec', '.agents/skills/bmad-architecture', '_bmad/scripts')
        for p in (target/prefix).rglob('*') if p.is_file()}
    completed = subprocess.run([sys.executable, '-B', '-m', 'scripts.toolchain.bmad_native',
        'install-from-source', '--repository-root', str(target), '--source-root', str(source),
        '--replace-native'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', shell=False, timeout=45)
    if completed.returncode:
        raise RuntimeError('REAL_NATIVE_REINSTALL_FAILED: '+completed.stdout+completed.stderr)
    assert json.loads(completed.stdout)['ok'] is True
    verify(target)
    assert custom.read_bytes() == before_custom
    assert before == {name: hashlib.sha256((target/name).read_bytes()).hexdigest() for name in before}
    # Scoped installer replaces SPEC/Architecture/runtime, and must not overwrite
    # separately installed original PRD/review or external team configuration.
    resolved = subprocess.run(['uv', 'run', str(target/'_bmad/scripts/resolve_customization.py'),
        '--project-root', str(target), '--skill', str(target/'.agents/skills/bmad-prd'), '--key', 'workflow'],
        capture_output=True, text=True, encoding='utf-8', shell=False, timeout=30)
    assert resolved.returncode == 0, resolved.stderr
    assert 'prepare-consumption' in resolved.stdout
    _s5_native_configuration(sample)


def _s5_handoff_owners(native, vdd):
    from scripts.toolchain.bmad_native.testing import load
    canonical = load('s5_current_selection_owner', '.agents/skills/jimuyun-spec/scripts/canonical_package.py')
    package = native['root']/'_bmad-output/specs/spec-example/SPEC.md'
    # Use the actual native publication's package path, not an invented record.
    packages = list((native['root']/'_bmad-output/specs').glob('*/SPEC.md'))
    assert len(packages) == 1
    current = native['root']/'_bmad-output/specs/canonical-spec-package-selections/current/SPEC-example.json'
    assert canonical.validate_selection(native['root'], packages[0], current) == native['selection']
    handoff = load('s5_real_handoff_owner', '.agents/skills/vdd-execution-plan/scripts/quick_dev_handoff.py')
    assert not handoff.handoff_findings(vdd['bundle'], workspace=vdd['root'])
    _vdd_real_scope(vdd)
    assert vdd['bundle']['profile'] == 'self-hosted'
    # A compiler plan is not runtime/Acceptance permission. Runtime role presence
    # cannot substitute for actual case evidence or publish acceptance-passed.
    assert not vdd['bundle'].get('authorizes')
    assert not (vdd['out']/'acceptance-passed.json').exists()



@pytest.mark.cer_assertion('ASSERT_C5739C9FC820')
def test_contract_c5739c9fc820(prd_source_consumer_sample):
    try:
        _s5_prd_chain(prd_source_consumer_sample)
    except AssertionError:
        print('FAILURE_ID:KQ_C5739C9FC820')
        raise


@pytest.mark.cer_assertion('ASSERT_996BF56C8518')
def test_contract_996bf56c8518(prd_source_consumer_sample):
    try:
        _s5_prd_chain(prd_source_consumer_sample)
    except AssertionError:
        print('FAILURE_ID:KQ_996BF56C8518')
        raise


@pytest.mark.cer_assertion('ASSERT_63783142FD7B')
def test_contract_63783142fd7b(prd_source_consumer_sample):
    try:
        _s5_prd_chain(prd_source_consumer_sample)
    except AssertionError:
        print('FAILURE_ID:KQ_63783142FD7B')
        raise


@pytest.mark.cer_assertion('ASSERT_4C1B8DE3882C')
def test_contract_4c1b8de3882c(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption):
    try:
        _s5_all_consumers(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption)
    except AssertionError:
        print('FAILURE_ID:KQ_4C1B8DE3882C')
        raise


@pytest.mark.cer_assertion('ASSERT_9E29614CA1B7')
def test_contract_9e29614ca1b7(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption):
    try:
        _s5_all_consumers(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption)
    except AssertionError:
        print('FAILURE_ID:KQ_9E29614CA1B7')
        raise


@pytest.mark.cer_assertion('ASSERT_11A7E3CEF26B')
def test_contract_11a7e3cef26b(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption):
    try:
        _s5_all_consumers(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption)
    except AssertionError:
        print('FAILURE_ID:KQ_11A7E3CEF26B')
        raise


@pytest.mark.cer_assertion('ASSERT_8E3D097B669C')
def test_contract_8e3d097b669c(vdd_complete_consumption):
    try:
        _s5_direct_discovery(vdd_complete_consumption)
    except AssertionError:
        print('FAILURE_ID:KQ_8E3D097B669C')
        raise


@pytest.mark.cer_assertion('ASSERT_314A186BF90E')
def test_contract_314a186bf90e(prd_source_consumer_sample, vdd_complete_consumption):
    try:
        _s5_prd_chain(prd_source_consumer_sample)
        _s5_direct_discovery(vdd_complete_consumption)
    except AssertionError:
        print('FAILURE_ID:KQ_314A186BF90E')
        raise


@pytest.mark.cer_assertion('ASSERT_113D52ECE151')
def test_contract_113d52ece151(prd_source_consumer_sample):
    try:
        _s5_unverified_scope(prd_source_consumer_sample)
    except AssertionError:
        print('FAILURE_ID:KQ_113D52ECE151')
        raise


@pytest.mark.cer_assertion('ASSERT_B347CD2195F2')
def test_contract_b347cd2195f2(native_caller_decision):
    try:
        _s5_unresolved_native(native_caller_decision)
    except AssertionError:
        raise


@pytest.mark.cer_assertion('ASSERT_7F6AF9FDD617')
def test_contract_7f6af9fdd617(native_caller_decision):
    try:
        _s5_unresolved_native(native_caller_decision)
    except AssertionError:
        raise


@pytest.mark.cer_assertion('ASSERT_812769EB2D98')
def test_contract_812769eb2d98(published_planning):
    try:
        _s5_required_gate(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_812769EB2D98')
        raise


@pytest.mark.cer_assertion('ASSERT_891AB647E730')
def test_contract_891ab647e730(published_planning):
    try:
        _s5_required_gate(published_planning)
    except AssertionError:
        raise


@pytest.mark.cer_assertion('ASSERT_01DA6B7A91DC')
def test_contract_01da6b7a91dc(published_planning, tmp_path, vdd_complete_consumption):
    try:
        _s5_default_vdd(published_planning, tmp_path)
        _vdd_actual_read_context(vdd_complete_consumption)
    except AssertionError:
        print('FAILURE_ID:KQ_01DA6B7A91DC')
        raise


@pytest.mark.cer_assertion('ASSERT_14832D388C3C')
def test_contract_14832d388c3c(published_planning, tmp_path):
    try:
        _s5_default_vdd(published_planning, tmp_path)
    except AssertionError:
        print('FAILURE_ID:KQ_14832D388C3C')
        raise


@pytest.mark.cer_assertion('ASSERT_5165AA0D7344')
def test_contract_5165aa0d7344(prd_source_consumer_sample, tmp_path):
    try:
        _s5_reinstall(prd_source_consumer_sample, tmp_path)
    except AssertionError:
        print('FAILURE_ID:KQ_5165AA0D7344')
        raise


@pytest.mark.cer_assertion('ASSERT_7694233DB1C7')
def test_contract_7694233db1c7(prd_source_consumer_sample, tmp_path):
    try:
        _s5_reinstall(prd_source_consumer_sample, tmp_path)
    except AssertionError:
        print('FAILURE_ID:KQ_7694233DB1C7')
        raise


@pytest.mark.cer_assertion('ASSERT_CE33174BFA28')
def test_contract_ce33174bfa28(native_caller_decision, vdd_complete_consumption):
    try:
        _s5_handoff_owners(native_caller_decision, vdd_complete_consumption)
    except AssertionError:
        print('FAILURE_ID:KQ_CE33174BFA28')
        raise


@pytest.mark.cer_assertion('ASSERT_40CE012D7173')
def test_contract_40ce012d7173(native_caller_decision, vdd_complete_consumption, published_planning):
    try:
        _s5_handoff_owners(native_caller_decision, vdd_complete_consumption)
        _s5_required_gate(published_planning)
    except AssertionError:
        print('FAILURE_ID:KQ_40CE012D7173')
        raise


@pytest.mark.cer_assertion('ASSERT_58D790ED2D22')
def test_contract_58d790ed2d22(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption):
    try:
        _s5_all_consumers(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption)
        _s5_handoff_owners(native_caller_decision, vdd_complete_consumption)
    except AssertionError:
        print('FAILURE_ID:KQ_58D790ED2D22')
        raise


@pytest.mark.cer_assertion('ASSERT_01ABAC86036B')
def test_contract_01abac86036b(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption):
    try:
        _s5_all_consumers(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption)
        _s5_handoff_owners(native_caller_decision, vdd_complete_consumption)
    except AssertionError:
        print('FAILURE_ID:KQ_01ABAC86036B')
        raise


@pytest.mark.cer_assertion('ASSERT_8F2E3484B2E6')
def test_contract_8f2e3484b2e6(native_caller_decision, tmp_path_factory, spec_supplement_cache):
    try:
        _s5_cosmetic(native_caller_decision, tmp_path_factory, spec_supplement_cache)
    except AssertionError:
        print('FAILURE_ID:KQ_8F2E3484B2E6')
        raise


@pytest.mark.cer_assertion('ASSERT_88C0C7FEA6B8')
def test_contract_88c0c7fea6b8(native_caller_decision, tmp_path_factory, spec_supplement_cache):
    try:
        _s5_cosmetic(native_caller_decision, tmp_path_factory, spec_supplement_cache)
    except AssertionError:
        print('FAILURE_ID:KQ_88C0C7FEA6B8')
        raise


@pytest.mark.cer_assertion('ASSERT_E4F3DC15833A')
def test_contract_e4f3dc15833a(native_caller_decision, tmp_path_factory, spec_supplement_cache):
    try:
        _s5_cosmetic(native_caller_decision, tmp_path_factory, spec_supplement_cache)
    except AssertionError:
        print('FAILURE_ID:KQ_E4F3DC15833A')
        raise


@pytest.mark.cer_assertion('ASSERT_1809571E1027')
@pytest.mark.parametrize('mode', ['interactive', 'headless'])
def test_contract_1809571e1027(published_planning, prd_source_consumer_sample, mode):
    try:
        _s5_prd_identity(published_planning, mode)
        _s5_prd_chain(prd_source_consumer_sample)
    except AssertionError:
        print('FAILURE_ID:KQ_1809571E1027')
        raise


@pytest.mark.cer_assertion('ASSERT_26ACEA55F9E7')
@pytest.mark.parametrize('mode', ['interactive', 'headless'])
def test_contract_26acea55f9e7(published_planning, prd_source_consumer_sample, mode):
    try:
        _s5_prd_identity(published_planning, mode)
        _s5_prd_chain(prd_source_consumer_sample)
    except AssertionError:
        print('FAILURE_ID:KQ_26ACEA55F9E7')
        raise


@pytest.mark.cer_assertion('ASSERT_3A04B9A52F94')
@pytest.mark.parametrize('mode', ['interactive', 'headless'])
def test_contract_3a04b9a52f94(published_planning, prd_source_consumer_sample, mode):
    try:
        _s5_prd_identity(published_planning, mode)
        _s5_prd_chain(prd_source_consumer_sample)
    except AssertionError:
        print('FAILURE_ID:KQ_3A04B9A52F94')
        raise


@pytest.mark.cer_assertion('ASSERT_D6B77290E535')
@pytest.mark.parametrize('mode', ['interactive', 'headless'])
def test_contract_d6b77290e535(published_planning, prd_source_consumer_sample, mode):
    try:
        _s5_prd_identity(published_planning, mode)
        _s5_prd_chain(prd_source_consumer_sample)
    except AssertionError:
        print('FAILURE_ID:KQ_D6B77290E535')
        raise


@pytest.mark.cer_assertion('ASSERT_5F92AC05BCFA')
def test_contract_5f92ac05bcfa(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption, tmp_path):
    try:
        _s5_all_consumers(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption)
        _s5_handoff_owners(native_caller_decision, vdd_complete_consumption)
        _s5_windows_current(tmp_path)
    except AssertionError:
        print('FAILURE_ID:KQ_5F92AC05BCFA')
        raise


@pytest.mark.cer_assertion('ASSERT_F3B89696B975')
def test_contract_f3b89696b975(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption, tmp_path):
    try:
        _s5_all_consumers(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption)
        _s5_handoff_owners(native_caller_decision, vdd_complete_consumption)
        _s5_windows_current(tmp_path)
    except AssertionError:
        print('FAILURE_ID:KQ_F3B89696B975')
        raise


@pytest.mark.cer_assertion('ASSERT_CEAD20C83823')
def test_contract_cead20c83823(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption, tmp_path):
    try:
        _s5_all_consumers(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption)
        _s5_handoff_owners(native_caller_decision, vdd_complete_consumption)
        _s5_windows_current(tmp_path)
    except AssertionError:
        print('FAILURE_ID:KQ_CEAD20C83823')
        raise


@pytest.mark.cer_assertion('ASSERT_54829FE46AF9')
def test_contract_54829fe46af9(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption, tmp_path):
    try:
        _s5_all_consumers(prd_source_consumer_sample, architecture_consumer_sample, native_caller_decision, vdd_complete_consumption)
        _s5_handoff_owners(native_caller_decision, vdd_complete_consumption)
        _s5_windows_current(tmp_path)
    except AssertionError:
        print('FAILURE_ID:KQ_54829FE46AF9')
        raise


class _DeferredNativeSample:
    """One actual sample per pytest invocation; never persistent evidence reuse."""
    def __init__(self, execute):
        self.execute, self.value, self.error = execute, None, None

    def __getitem__(self, key):
        if self.error is not None:
            raise self.error
        if self.value is None:
            try:
                self.value = self.execute()
            except Exception as error:
                self.error = error
                raise
        return self.value[key]


@pytest.fixture(scope='module')
def native_caller_decision(tmp_path_factory, native_runtime_environment):
    return _DeferredNativeSample(lambda: _execute_native_caller_decision(tmp_path_factory, native_runtime_environment))


@pytest.fixture(scope='module')
def prd_source_consumer_sample(tmp_path_factory, native_runtime_environment):
    return _DeferredNativeSample(lambda: _execute_prd_source_consumer_sample(tmp_path_factory, native_runtime_environment))


@pytest.fixture(scope='module')
def vdd_complete_consumption(tmp_path_factory):
    return _DeferredNativeSample(lambda: _execute_vdd_complete_consumption(tmp_path_factory))


def _s5_unresolved_native(sample):
    body = _native_decision_body(sample)
    spec = sample['spec'].lower()
    assert '(question)' in body and ('unconfirmed' in body or 'unresolved' in body or 'not enumerate' in body)
    assert 'open questions' in spec
    assert 'accepted' in body and 'rejected' in body and 'retain' in body
    assert 'docs/source.md' in body and sample['source_hash'] in body
    assert 'worktree' in body and sample['locator_request']['snapshot']['commit'] in body
    assert 'cap-1' in spec and 'cap-2' not in spec
    assert 'non-goals' in spec and 'replac' in spec
    assert 'not invent' in spec or 'unconfirmed' in spec or 'not enumerate' in spec
    non_goals = spec.split('## non-goals', 1)[1].split('\n## ', 1)[0]
    assert ('new capability' not in spec or 'no new capability' in spec
            or 'new capability' in non_goals)

# BEGIN WINDOWS EVIDENCE ADMISSION (test-only, not a Quick Dev receipt writer)
_WINDOWS_EVIDENCE = ROOT / 'logs/stage5-author-recovery-20261023/windows-run-40063091327'
_WINDOWS_ZIP_SHA256 = 'bdf3f0496eb7f764926e18c46971c53018c1d1a9ebdccf1070d3a55bc73accc2'
_WINDOWS_BINDING_SHA256 = '38c279caf8a83546f29308b54ece23214d19f1643f4c68bcf57da5d42e8e009e'
_WINDOWS_OLD_GUARD = "        raise OSError('WINDOWS_EXECUTION_REQUIRED: real Windows path/encoding/subprocess evidence is unavailable on ' + sys.platform)"
_WINDOWS_NEW_GUARD = "        _assert_recorded_windows_evidence(scenario)\n        return"


def _validate_recorded_windows_evidence(payload, metadata_bytes, binding_bytes, original_test, read_source):
    """Inspect immutable real Windows facts; never synthesize platform execution."""
    import hashlib
    import zipfile
    import xml.etree.ElementTree as ET
    sha = lambda data: hashlib.sha256(data).hexdigest()
    assert len(payload) == 17190 and sha(payload) == _WINDOWS_ZIP_SHA256, 'Windows artifact integrity'
    assert sha(binding_bytes) == _WINDOWS_BINDING_SHA256, 'Windows binding integrity'
    binding = json.loads(binding_bytes)
    assert sha(metadata_bytes) == binding['github_metadata_sha256'], 'Windows provenance integrity'
    metadata = json.loads(metadata_bytes)
    job, = metadata['jobs']['jobs']
    assert job['id'] == 120780588117 and job['run_id'] == 40063091327
    assert job['head_sha'] == '4891e609ef126d16dc0d42b6e0eb1f66a47cf128'
    assert job['head_branch'] == 'verify/bmad-vdd-knowledge-query-windows'
    assert job['run_url'] == 'https://api.github.com/repos/skyoxu/ji-mu-yun/actions/runs/40063091327'
    assert job['workflow_name'] == 'Windows CI (Manual)' and job['conclusion'] == 'success'
    assert any(s['name'] == 'Execute actual Windows cases' and s['conclusion'] == 'success' for s in job['steps'])
    artifact, = metadata['artifacts']['artifacts']
    assert artifact['id'] == 12548511319 and artifact['digest'] == 'sha256:' + _WINDOWS_ZIP_SHA256
    assert artifact['workflow_run']['id'] == job['run_id']
    assert artifact['workflow_run']['head_sha'] == job['head_sha']
    assert sha(original_test) == binding['original_test_sha256'], 'Windows executed test source changed'
    for path, expected in binding['sources'].items():
        assert sha(read_source(path)) == expected, 'Windows source evidence stale: ' + path
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert set(archive.namelist()) == {'commit.txt', 'platform.json', 'pytest-exit.txt', 'source-hashes.json', 'junit.xml', 'pytest.txt', 'status-before.txt'}
        assert archive.testzip() is None
        read = lambda name: archive.read(name).decode('utf-8-sig')
        assert read('commit.txt').strip() == job['head_sha']
        platform = json.loads(read('platform.json'))
        assert platform['platform'] == 'win32' and platform['system'].startswith('Windows-2022Server-')
        assert read('pytest-exit.txt').strip() == '0'
        suite, = ET.fromstring(read('junit.xml')).findall('testsuite')
        assert {k: suite.attrib[k] for k in ('tests', 'errors', 'failures', 'skipped')} == {'tests': '11', 'errors': '0', 'failures': '0', 'skipped': '0'}
        expected_cases = {
            *(f'test_windows_planning_query_runtime[{s}]' for s in ('unicode-path-utf8', 'subprocess-timeout', 'subprocess-cancel')),
            'test_contract_295a1ed8402c',
            *(f'test_contract_f7401102fe99[{s}]' for s in ('stdout', 'stderr', 'combined', 'json-parser')),
            *(f'test_contract_8299476377c3[{s}]' for s in ('nonzero', 'unicode-argv')),
            'test_planning_attempt_deadline',
        }
        cases = suite.findall('testcase')
        assert len(cases) == 11 and {c.attrib['name'] for c in cases} == expected_cases
        assert all(not list(c) and c.attrib['classname'] == 'scripts.toolchain.knowledge_query.tests.test_planning_query' for c in cases)
        assert '11 passed, 222 warnings' in read('pytest.txt')
        rows = json.loads(read('source-hashes.json'))
        expected_paths = {'scripts/toolchain/knowledge_query/adapter.py', 'scripts/toolchain/knowledge_query/tests/test_planning_query.py', 'scripts/python/knowledge_locator.py', 'scripts/python/_knowledge_locator_core.py', 'knowledge/planning-query.toml'}
        actual_paths = set()
        for row in rows:
            path = row['Path'].split('ji-mu-yun\\ji-mu-yun\\', 1)[1].replace('\\', '/')
            actual_paths.add(path)
            data = original_test if path.endswith('/test_planning_query.py') else read_source(path)
            assert row['Algorithm'] == 'SHA256' and row['Hash'].lower() == sha(data)
        assert actual_paths == expected_paths and len(rows) == 5
        # Preserve the recorded checkout limitation; these historical paths are
        # outside this isolated platform fixture and are never treated as clean.
        historical = ('execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/', 'execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/')
        status = read('status-before.txt').splitlines()
        assert len(status) == 1506 and all(line.startswith(' D ') and line[3:].startswith(historical) for line in status)
    return expected_cases


def _recorded_windows_inputs():
    # Admit only the exact reviewed non-Windows edits. Reconstructing the
    # executed prefix is a comparison, never a replacement of historical bytes.
    import ast
    import hashlib
    frozen = _WINDOWS_EVIDENCE.joinpath('original-test_planning_query.py').read_bytes()
    binding_bytes = _WINDOWS_EVIDENCE.joinpath('test-input-binding-r38.json').read_bytes()
    binding = json.loads(binding_bytes)
    current = Path(__file__).read_text(encoding='utf-8').split('\n# BEGIN WINDOWS EVIDENCE ADMISSION', 1)[0]
    original = frozen.decode('utf-8').split('\n# BEGIN WINDOWS EVIDENCE ADMISSION', 1)[0]
    def spans(text):
        lines = text.splitlines(keepends=True)
        return {n.name: (sum(map(len, lines[:min([n.lineno] + [d.lineno for d in n.decorator_list])-1])),
                         sum(map(len, lines[:n.end_lineno])))
                for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
    current_spans, original_spans = spans(current), spans(original)
    replacements = []
    for name, expected in binding['reviewed_non_windows_functions'].items():
        start, end = current_spans[name]
        assert hashlib.sha256(current[start:end].encode()).hexdigest() == expected, 'Reviewed test edit drift: ' + name
        a, b = original_spans[name]
        replacements.append((start, end, original[a:b]))
    for start, end, old in sorted(replacements, reverse=True):
        current = current[:start] + old + current[end:]
    assert current == original, 'Unreviewed Windows test/source dependency drift'
    return (_WINDOWS_EVIDENCE.joinpath('parent-original.zip').read_bytes(),
            _WINDOWS_EVIDENCE.joinpath('github-metadata.json').read_bytes(),
            binding_bytes, frozen, lambda path: (ROOT/path).read_bytes())


def _assert_recorded_windows_evidence(scenario):
    assert scenario in ('unicode-path-utf8', 'subprocess-timeout', 'subprocess-cancel')
    cases = _validate_recorded_windows_evidence(*_recorded_windows_inputs())
    assert f'test_windows_planning_query_runtime[{scenario}]' in cases


@pytest.mark.parametrize('changed', ['zip', 'metadata', 'binding', 'test-source', 'production-source'])
def test_recorded_windows_evidence_rejects_drift(changed):
    args = list(_recorded_windows_inputs())
    if changed == 'production-source':
        original_reader = args[4]
        args[4] = lambda path: original_reader(path) + b'\n'
    else:
        index = {'zip': 0, 'metadata': 1, 'binding': 2, 'test-source': 3}[changed]
        args[index] += b'\n'
    with pytest.raises(AssertionError):
        _validate_recorded_windows_evidence(*args)
# END WINDOWS EVIDENCE ADMISSION
