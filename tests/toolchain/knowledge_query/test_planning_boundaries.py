"""ADR-0041/0048/0062: retained scope and authority regression guards.

Delivered documents are read-only inputs. No BMAD entry, generation, reviewer,
installation verifier, publisher or real model is invoked by this module.
These unit observations do not grant implementation or Acceptance authority.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tomllib
from functools import lru_cache

import pytest

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / 'execution-plans/2026-10-25-vdd-knowledge-query-caller-runtime-role'
SPEC = ROOT / '_bmad-output/specs/spec-bmad-vdd-knowledge-query/SPEC.md'
REVIEW = ROOT / 'review-materials/vdd-quick-dev-scoped-plan-20261025'
PUBLISHED_HOST = '965df2e34f71ef197fffd8afb68f037688486ca2'
ENVIRONMENT_HOST = 'b9c701c1cfe662d679d747533920f992379c4b06'
OPTION_HOST = 'b908cb3915cb50c6860445e27c1e1012137e60bb'
Q7_HOST = '93d06e67b0276ec8cc2e7ae7298aff8ac8e5fbf6'
STABLE_HOST = 'd86539b9602d9cff7cfe1d96ae6a58b287ce7b3d'
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts/python'),
    str(ROOT / '.agents/skills/quick-dev-tdd-adapter/tools'),
    str(ROOT / '.agents/skills/vdd-execution-plan/scripts')]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(None)
def original_source_guard():
    manifest = read(REVIEW / 'publication-manifest.json')
    sources = [p for p in manifest['files'] if p.startswith('_bmad-output/')]
    assert sources
    for path in sources:
        assert digest(ROOT / path) == manifest['files'][path]['sha256'], path
    original = ROOT / '_bmad-output/planning-artifacts/prds/prd-bmad-vdd-knowledge-query-2026-10-22/sources/bmad-vdd-knowledge-query-requirements.md'
    assert digest(original) == 'ce45693489d02227442c04c9b4e7220121a897d81dab03abc7867e6ceff11950'


@lru_cache(None)
def package_guard():
    # The delivered-package parser checks roles/bytes only, never approval or
    # the wrapper CLI. Its publish path is deliberately not called.
    owner = load('retained_package_parser', '.agents/skills/jimuyun-spec/scripts/canonical_package.py')
    pointer = ROOT / '_bmad-output/specs/canonical-spec-package-selections/current/SPEC-bmad-vdd-knowledge-query.json'
    selection = owner.validate_selection(ROOT, SPEC, pointer)
    assert selection['selection_hash'] == 'sha256:373d280b03a68904e97306a7b82b797a88eff56eeb3d7989f6b28bdf6ef117c7'
    descriptor, graph, identity = owner.build_contract(ROOT, SPEC)
    assert identity == selection['selection_hash'] and len(graph['role_graph']) == 9
    assert all(source['role'] == 'provenance' for source in descriptor['sources'])
    assert {c['role'] for c in descriptor['companions']} == {'normative_companion', 'adopted_companion'}
    for invalid in ('../outside.md', '/absolute.md', 'C:/secret.md', 'a\\b.md'):
        with pytest.raises(ValueError):
            owner.validate_path(ROOT, invalid)
    index = read(PLAN / 'source-index.v1.json')
    assert len(index['entries']) == 61
    for entry in index['entries']:
        assert 'sha256:' + digest(ROOT / entry['repository_relative_source_path']) == entry['source_sha256']
        assert entry['source_ref'].endswith('#' + entry['anchor'])
    bundle = read(PLAN / 'semantic-plan-bundle.v1.json')
    refs = {entry['source_ref'] for entry in index['entries']}
    assert len(bundle['obligations']) == 305
    for obligation in bundle['obligations']:
        assert obligation['source_refs'] and set(obligation['source_refs']) <= refs
    mapping = read(ROOT / 'logs/scoped-input-preparation-20261024-v3/old-to-draft-map.json')
    assert mapping['draft_effective_clauses'] == 305
    assert mapping['deployment_only_rows'] == 25 and len(mapping['items']) == 330
    assert sorted(mapping['counts'].values()) == [25, 59, 246]
    assert not mapping['authorizes']  # Traceability never becomes execution proof.
    original_source_guard()


@lru_cache(None)
def scope_guard():
    bundle = read(PLAN / 'semantic-plan-bundle.v1.json')
    approved = {
        'knowledge/contracts/knowledge-consumer-projections.v1.schema.json',
        'knowledge/contracts/knowledge-locator-request.v1.schema.json',
        'knowledge/planning-query.toml', 'knowledge/policies/consumer-policies.v2.json',
        'scripts/python/_knowledge_catalog_builder.py', 'scripts/python/_knowledge_locator_core.py',
        'scripts/python/knowledge_locator.py', 'scripts/toolchain/knowledge_query/adapter.py',
        'scripts/vdd/compile_plan.py'}
    assert {p for s in bundle['slices'] for p in s['production_owners']} == approved
    assert not any(p.startswith(('PhaseA.', 'runtime/', 'addons/', 'scenes/', 'scripts/sc/', '_bmad/', '.agents/skills/jimuyun-')) for p in approved)
    own = next(s for s in bundle['slices'] if s['slice_id'] == 'S2')
    assert own['production_owners'] == [] and own['depends_on'] == []
    assert own['allowed_write_paths'] == ['tests/toolchain/knowledge_query/test_planning_boundaries.py']
    intents = {f['failure_intent_id']: f for f in bundle['failure_intents']}
    assert all(intents[i]['failure_family'] == 'semantic-contract-gap' for i in own['failure_intent_ids'])
    from quick_dev_handoff import repair_runtime_red_roles
    before = json.dumps(bundle, sort_keys=True)
    with pytest.raises(ValueError, match='lacks production/assertion/observable binding'):
        repair_runtime_red_roles(bundle, [own['failure_intent_ids'][0]])
    assert json.dumps(bundle, sort_keys=True) == before
    dependency_guard()


@lru_cache(None)
def stable_owner_guard():
    inventory = read(REVIEW / 'review-tree-inventory.json')['inventory']
    # The maintainer approved this exact six-file environment repair, then its
    # verified bytes were committed separately from this candidate test. Keep
    # the original publication immutable and verify the bounded successor via
    # actual Git objects rather than replacing historical inventory hashes.
    approved = {
        '.agents/skills/quick-dev-tdd-adapter/tools/execution_environment.py',
        '.agents/skills/quick-dev-tdd-adapter/tools/shared_execution.py',
        '.agents/skills/quick-dev-tdd-adapter/tools/process_executor_v2.py',
        '.agents/skills/quick-dev-tdd-adapter/tools/tests/test_execution_environment.py',
        '.agents/skills/quick-dev-tdd-adapter/references/shared-execution.md',
        'docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md',
    }
    def git(*args):
        return subprocess.check_output(['git', '-C', str(ROOT), *args], timeout=10)
    assert git('rev-parse', ENVIRONMENT_HOST + '^').decode().strip() == PUBLISHED_HOST
    changed = set(git('diff-tree', '--no-commit-id', '--name-only', '-r', ENVIRONMENT_HOST).decode().splitlines())
    assert changed == approved
    # The separately approved Q6 operand repair is exactly this two-file child.
    option_repair = {
        '.agents/skills/quick-dev-tdd-adapter/tools/regression_gate.py',
        '.agents/skills/quick-dev-tdd-adapter/tools/tests/test_ch456_q6_regression_gate.py',
    }
    assert git('rev-parse', OPTION_HOST + '^').decode().strip() == ENVIRONMENT_HOST
    assert set(git('diff-tree', '--no-commit-id', '--name-only', '-r', OPTION_HOST).decode().splitlines()) == option_repair
    approved |= option_repair
    # Exact separately approved Q7 reader repair, with no business files mixed in.
    q7_repair = {
        '.agents/skills/quick-dev-tdd-adapter/tools/coverage_predicates.py',
        '.agents/skills/quick-dev-tdd-adapter/tools/regression_gate.py',
        '.agents/skills/quick-dev-tdd-adapter/tools/tests/test_q7_original_checks.py',
        '.agents/skills/quick-dev-tdd-adapter/references/shared-execution.md',
    }
    assert git('rev-parse', Q7_HOST + '^').decode().strip() == OPTION_HOST
    assert set(git('diff-tree', '--no-commit-id', '--name-only', '-r', Q7_HOST).decode().splitlines()) == q7_repair
    approved |= q7_repair
    q8_repair = {
        '.agents/skills/quick-dev-tdd-adapter/tools/coverage_predicates.py',
        '.agents/skills/quick-dev-tdd-adapter/tools/tests/test_coverage_predicates.py',
        '.agents/skills/quick-dev-tdd-adapter/references/shared-execution.md',
    }
    assert git('rev-parse', STABLE_HOST + '^').decode().strip() == Q7_HOST
    assert set(git('diff-tree', '--no-commit-id', '--name-only', '-r', STABLE_HOST).decode().splitlines()) == q8_repair
    approved |= q8_repair
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', STABLE_HOST, 'HEAD'],
                   check=True, capture_output=True, timeout=10)
    prefixes = ('.agents/skills/quick-dev-tdd-adapter/', '.agents/skills/vdd-execution-plan/',
                'scripts/quick_dev/', 'scripts/sc/')
    checked = []
    for path, expected in inventory.items():
        if path.startswith(prefixes) and expected.get('state') == 'present':
            expected_hash = (hashlib.sha256(git('show', STABLE_HOST + ':' + path)).hexdigest()
                             if path in approved else expected['sha256'])
            assert digest(ROOT / path) == expected_hash, path
            checked.append(path)
    for path in approved:
        assert (ROOT / path).read_bytes() == git('show', STABLE_HOST + ':' + path), path
    assert 'scripts/quick_dev/run.py' in checked
    assert any('independent_judge' in path for path in checked)
    package_guard()


@lru_cache(None)
def native_guard():
    # Protect delivered wrappers without starting their skill/installer/native
    # verifier. Only repository sources present in the publication are read.
    manifest = read(REVIEW / 'publication-manifest.json')['files']
    # These exact hashes are the original main a1e783c5 bytes, statically
    # compared with this publication before test authoring. No Git subprocess
    # or native verification/installation is run by these unit tests.
    originals = {
        '.agents/skills/jimuyun-spec/scripts/bridge.py': 'aa7c640f1c5e5b8df1f78659c1e5b42c75ca68835cd523cab45b7e9afbf3f77d',
        '.agents/skills/jimuyun-architecture/scripts/invoke.py': '32ab790740dfeb1a98f236210f661c5cd13323c7ead10ae50683dc44272445ad',
    }
    for path, expected in originals.items():
        assert digest(ROOT / path) == expected, path
    assert sys.version_info >= (3, 11)
    for path in ('scripts/toolchain/knowledge_query/adapter.py', 'scripts/python/_knowledge_locator_core.py'):
        ast.parse((ROOT / path).read_text(encoding='utf-8'), feature_version=(3, 11))
    config = tomllib.loads((ROOT / 'knowledge/planning-query.toml').read_text(encoding='utf-8'))
    assert type(config['query']['enabled']) is bool
    assert set(config['query']['stages']) >= {'vdd-create', 'vdd-repair'}
    original_source_guard()


@lru_cache(None)
def publication_guard():
    import publish_knowledge_catalog as owner
    sha = 'a' * 40
    request = {'schema_version': owner.PUBLICATION_REQUEST_SCHEMA_VERSION, 'request_id': 'boundary-only',
        'caller': 'maintain-knowledge-base', 'trigger': 'operator-requested', 'target_plan': 'execution-plans/example',
        'main_commit': sha, 'automatic': False, 'maintainer_confirmation': True,
        'recorded_at': '2026-10-25T00:00:00+00:00', 'authorizes': ['knowledge-publication'], 'source_route': None}
    assert owner._validate_publication_request(request, expected_main=sha)['caller'] == 'maintain-knowledge-base'
    for change, reason in [({'automatic': True}, 'confirmation'), ({'maintainer_confirmation': False}, 'confirmation'),
        ({'caller': 'vdd'}, 'caller'), ({'authorizes': []}, 'authority'), ({'main_commit': 'b' * 40}, 'main_mismatch')]:
        with pytest.raises(ValueError, match=reason):
            owner._validate_publication_request({**request, **change}, expected_main=sha)


@lru_cache(None)
def governance_guard():
    from governance_policy import resolve_governance_policy, GOVERNANCE_CHECKS
    for phase in ('development', 'test', 'production'):
        env = {'PHASEA_SERVICE_STATE': phase}
        assert resolve_governance_policy(None, environment=env)['enabled'] == (phase != 'development')
        assert resolve_governance_policy('off', environment={**env, 'JIMUYUN_GOVERNANCE_MODE': 'on'})['enabled'] is False
        enabled = resolve_governance_policy('on', environment={**env, 'JIMUYUN_GOVERNANCE_MODE': 'off'})
        assert enabled['enabled'] is True and enabled['checks'] == list(GOVERNANCE_CHECKS)
    assert resolve_governance_policy(None, environment={})['enabled'] is False
    assert resolve_governance_policy(None, environment={'JIMUYUN_GOVERNANCE_MODE': 'on'})['enabled'] is True
    with pytest.raises(ValueError):
        resolve_governance_policy('unknown', environment={})
    publication_guard()


@lru_cache(None)
def authority_guard():
    from coverage_predicates import _validate_detached_binding
    for label in ('plan-ready', 'passed', 'implementation-complete', 'acceptance-passed'):
        with pytest.raises(ValueError):
            _validate_detached_binding({'status': label}, 'self-hosted')
    from behavior_routing import validate_plan
    bundle = read(PLAN / 'semantic-plan-bundle.v1.json')
    validate_plan(bundle)
    assert not bundle.get('authorizes')
    assert not any(i.get('disposition') in {'present', 'missing'} for i in bundle['behavior_routing']['intents'])
    from scripts.toolchain.knowledge_query import adapter
    result = adapter.diagnose({'operation': 'create'}, ROOT, *[ROOT / p for p in adapter._CANONICAL])
    assert result['outcome'] == 'blocked' and not result.get('authorizes')
    assert result['schema'] == 'planning-query.v1'
    assert 'runtime_edges' not in result and 'acceptance_status' not in result


@lru_cache(None)
def dependency_guard():
    source = (ROOT / 'scripts/toolchain/knowledge_query/adapter.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    imports = {n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports.update(a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names)
    assert '_knowledge_locator_core' in imports
    forbidden = ('publish_knowledge', 'bootstrap', 'sqlite', 'psycopg', 'fastapi', 'requests', 'httpx', 'openai', 'chromadb', 'faiss')
    assert not {name for name in imports if any(part in name for part in forbidden)}
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {'eval', 'exec', '__import__'} for n in ast.walk(tree))
    assert 'query_with_diagnostics' in source
    assert 'allow_unpublished=True' not in source and 'allow_stale=True' not in source
    compiler = (ROOT / 'scripts/vdd/compile_plan.py').read_text(encoding='utf-8')
    assert 'knowledge_query' in compiler and 'consumption' in compiler
    publication_guard()


@lru_cache(None)
def budget_guard():
    source = (SPEC.parent / 'behavior-contracts.md').read_text(encoding='utf-8')
    data = tomllib.loads((ROOT / 'knowledge/planning-query.toml').read_text(encoding='utf-8'))['query']
    from scripts.toolchain.knowledge_query import adapter
    expected = {'max_candidates': (12, 20), 'max_output_bytes': (65536, 131072), 'max_calls': (3, 5), 'timeout_seconds': (30, 60)}
    for key, (default, cap) in expected.items():
        assert f'| {key} | {default} | {cap} |' in source
        assert data[key] == default and type(data[key]) is int
        assert adapter._LIMITS[key][1] == cap
    assert adapter._LIMITS['max_output_bytes'][0] == 4096
    assert '4096' in source and '512' in source
    # Real parser rejects widening, including booleans masquerading as integers.
    for name, (_, cap) in expected.items():
        for bad in (cap + 1, True):
            with pytest.raises(adapter._Stop, match='invalid_config'):
                adapter._configuration(ROOT, {'consumer': 'vdd', 'narrow_overrides': {name: bad}})
    governance_guard()


@lru_cache(None)
def legacy_guard():
    import _knowledge_locator_core as core
    catalog = {'entries': [{'path': 'docs/example.md', 'content': 'planning contract', 'source_sha256': 'a' * 64}]}
    assert core.locate({'query': 'planning contract'}, catalog)['status'] == 'matched'
    empty = core.locate({'query': 'unmatcheduniquevalue'}, catalog)
    assert empty['status'] == 'insufficient_match' and empty['candidates'] == []
    enum = read(ROOT / 'knowledge/contracts/knowledge-locator-result.v1.schema.json')['properties']['status']['enum']
    assert {'matched', 'insufficient_match', 'blocked'} <= set(enum)
    assert not set(enum) & {'hit', 'no_match', 'unavailable', 'budget_exhausted', 'cancelled'}
    from scripts.toolchain.knowledge_query import adapter
    # The legacy facade must preserve actual raw status, exit and evidence,
    # including exit-zero blocked; no model or child process is needed.
    for status, code in (('matched', 0), ('insufficient_match', 0), ('blocked', 0), ('blocked', 2)):
        raw = {'result': {'status': status, 'candidates': []}, 'diagnostics': [], 'exit_code': code, 'evidence_refs': ['original']}
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(core, 'query_with_diagnostics', lambda *args, **kwargs: copy.deepcopy(raw))
            actual = adapter.diagnose({'consumer': 'vdd'}, ROOT, *[ROOT / p for p in adapter._CANONICAL])
        assert actual == raw
    dependency_guard()


def diagnostic_priority_guard():
    """Exercise the real mapper with explicit core outcomes, never [] guesses.

    Publication validation is a controlled unit boundary here, not a claim of
    real publication validity. Actual catalog/policy/source bytes are read.
    """
    from scripts.toolchain.knowledge_query import adapter
    policy = read(ROOT / adapter._CANONICAL[1])
    request = {'schema_version': 'jimuyun.knowledge-locator-request.v1',
        'request_id': 'retained-boundary', 'consumer': 'vdd', 'query': 'scope',
        'snapshot': {'ref': 'refs/heads/main', 'commit': 'a' * 40},
        'policy_revision': policy['policy_revision'], 'stage': 'vdd-create',
        'operation': 'create', 'task_id': 'retained-boundary', 'scope': ['AGENTS.md']}
    cases = [
        ('insufficient_match', [], 'no_match', 'empty'),
        ('insufficient_match', ['stale'], 'degraded', 'stale_verified'),
        ('blocked', [], 'blocked', 'unknown_failure'),
        ('matched', [], 'blocked', 'unknown_failure'),
        ('insufficient_match', ['policy_missing'], 'blocked', 'policy_denied'),
        ('insufficient_match', ['snapshot_mismatch', 'stale'], 'blocked', 'integrity_failed'),
        ('insufficient_match', ['publication_invalid', 'stale'], 'blocked', 'integrity_failed'),
    ]
    for status, codes, outcome, reason in cases:
        raw = {'result': {'status': status, 'candidates': []},
               'diagnostics': [{'code': c} for c in codes]}
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(adapter.core, 'verify_current_publication', lambda *args, **kwargs: True)
            patch.setattr(adapter.core, 'query_with_diagnostics', lambda *args, **kwargs: copy.deepcopy(raw))
            actual = adapter.diagnose(request, ROOT, *[ROOT / p for p in adapter._CANONICAL])
        assert (actual['outcome'], actual['reason_code']) == (outcome, reason)
        assert actual['diagnostic']['raw_status'] == status
        assert not actual.get('authorizes')


@lru_cache(None)
def adr_guard():
    text = (ROOT / 'docs/adr/ADR-0048-repository-knowledge-locator-workflow-consumption.md').read_text(encoding='utf-8')
    assert 'Accepted' in text and 'Applicability amendment: ordinary planning advice (2026-10-23)' in text
    for adr in ('ADR-0044', 'ADR-0050', 'ADR-0057', 'ADR-0059'):
        assert adr in text
    assert 'before implementing' in text and 'does not assert' in text
    governance_guard()


@lru_cache(None)
def schedule_guard():
    original_source_guard()
    text = (SPEC.parent / 'scope-and-decisions.md').read_text(encoding='utf-8')
    assert 'S2' in text and ('\u5f85' in text or 'pending' in text.lower())
    assert 'Package B' in text
    # Dependency support alone never mints execution or parallel authority.
    bundle = read(PLAN / 'semantic-plan-bundle.v1.json')
    assert not bundle.get('authorizes')
    assert not bundle.get('parallel_authorized', False)
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_5C02BA0AA1E1')
def test_contract_5c02ba0aa1e1():
    'Do not add UI, market metrics or latency targets no UI/market metric/latency target'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_AD2F023A4D8A')
def test_contract_ad2f023a4d8a():
    'Query and PRD internal review cannot replace existing formal Acceptance owner existing Acceptance owner alone decides completion, planning checks not substituted'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_0CDCD2C2092C')
def test_contract_0cdcd2c2092c():
    'Query assists judgment but does not become fact, implementation-completion or Acceptance authority'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_3879A47B5106')
def test_contract_3879a47b5106():
    'Architecture defines actual diagnostics distinguishing these cases; model guesses and empty candidates cannot establish the cause mapping derives actual diagnostics, not model guess or [] alone; exact insufficient_match split and higher priorities preserved'
    legacy_guard()
    diagnostic_priority_guard()


@pytest.mark.cer_assertion('ASSERT_CA2BCB3A2C9C')
def test_contract_ca2bcb3a2c9c():
    '保留不修改已有原生资源、typed publication/Acceptance owner 和查询不获新权威'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_493AA5C5D9AA')
def test_contract_493aa5c5d9aa():
    'Use Locator only to narrow search scope, not replace call-chain verification actual current caller/code/test/control references required; index location alone cannot prove implementation or dependency completeness'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_7BA160A9B5B5')
def test_contract_7ba160a9b5b5():
    'Use proposed scripts/toolchain/knowledge_query/ for shared read-only adapter with one diagnostic/state contract and knowledge/planning-query.toml for tracked team configuration single shared scripts/toolchain/knowledge_query adapter plus tracked knowledge/planning-query.toml, no duplicate state contract or premature implemented claim'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_60CF612F2E06')
def test_contract_60cf612f2e06():
    'Keep Python3.11+ support; Python3.12.14 and uv0.12.23 are verified reference environment versions, not mandatory patch upgrades for other platforms Python3.11+ supported, reference3.12.14/uv0.12.23 not forced patches'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_DD430724E6FF')
def test_contract_dd430724e6ff():
    'Preserve original scope-binding constraints on formal plan validity formal owner still rejects validity; query cache does not waive scope/source binding'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_C624DEC0A9FE')
def test_contract_c624dec0a9fe():
    'Only new consumer interface returns planning-query.v1 diagnostics; never force new states on unmigrated callers planning-query.v1 only new interface, legacy state/exit fields unchanged'
    legacy_guard()


@pytest.mark.cer_assertion('ASSERT_29E1D61C9DA3')
def test_contract_29e1d61c9da3():
    'Keep Locator the sole locating core; new code adds only shared adaptation and stage consumption, no index service/RAG/database or duplicate retrieval implementation only existing Locator retrieves; no duplicate retrieval/index/RAG/database'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_542A00BA0AD5')
def test_contract_542a00ba0ad5():
    'Exclude automatic publication, automatic Bootstrap/general entrypoint/internal reviewer platform/slice parallel scheduling, historical evidence rewriting and query results as completion authority no publication/Bootstrap/general entrypoint/reviewer platform/parallel scheduler; no historical rewrite; query never authorizes completion'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_8B96BF63114D')
def test_contract_8b96bf63114d():
    'Maintainer decides S2 timing before S2 work; technical non-dependency grants no parallel right maintainer decides before S2, no parallel permission'
    schedule_guard()


@pytest.mark.cer_assertion('ASSERT_349975159E12')
def test_contract_349975159e12():
    '保留 VDD public compiler→共享 adapter→现有 core/config/source reader，治理与 publisher 独立'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_FEBAECE3EF68')
def test_contract_febaece3ef68():
    'Stage adapter depends on shared query which depends on existing core; query does not invoke publisher, governance authorization or other workflows stage->shared->existing core only, no publisher/authorization/otherworkflow call'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_81030489D3CB')
def test_contract_81030489d3cb():
    'Keep original Locator return fields/status and old-consumer semantics unchanged; this rule specifies future adapter behavior and does not prove implementation already exists fields/status/exit/old consumers unchanged; planned adapter not reported already implemented'
    legacy_guard()


@pytest.mark.cer_assertion('ASSERT_72AB405FF8A5')
def test_contract_72ab405ff8a5():
    'Historical execution records grant no new phase or scheduling authority'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_A6DEA3F8BB0A')
def test_contract_a6dea3f8bb0a():
    'Regress existing behavior without fake RED or duplicate implementation and without requiring rerun of all historical requirements retain current regression coverage, no obsolete/fake RED/duplicate work or all-history rerun'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_A7CEB271CC36')
def test_contract_a7ceb271cc36():
    '保留仓库持久配置、有效值/来源可查，不依赖易覆盖默认文件'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_9EF76B702BB8')
def test_contract_9ef76b702bb8():
    'Maintainer confirms S2 schedule before execution; technical non-dependency does not authorize parallel work or block current product planning S2 pending maintainer schedule, no inferred parallel work'
    schedule_guard()


@pytest.mark.cer_assertion('ASSERT_C174B53AAD4B')
def test_contract_c174b53aad4b():
    'Use the architecturally reviewed conservative starting values fixed in behavior-contracts.md; future changes require owner refresh candidate/output/call/timeout defaults and caps match behavior-contracts; any future revision has formal SPEC owner refresh, not runtime widening'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_DE11C0FEE9B2')
def test_contract_de11c0fee9b2():
    'Do not change governance priority or development/auto default-off; query creates no freeze, extra authorization, attestation or review lineage default development/auto off and precedence unchanged; no freeze, authorization, attestation or lineage created by ordinary query'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_59D16A20F138')
def test_contract_59d16a20f138():
    'Continue existing hash verification; do not add whole-repository freeze for lightweight query; formal planning and acceptance retain their original binding contracts existing hashes remain checked, no whole-repository freeze added and plan/Acceptance binding unchanged'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_155F3E22923E')
def test_contract_155f3e22923e():
    'Use stable verified tooling to host current requirement, test candidates only in isolated samples and follow existing self-hosted rules without mid-task replacement stable verified host unchanged, candidate only isolated validation not self-host this requirement'
    stable_owner_guard()


@pytest.mark.cer_assertion('ASSERT_9D7F7CF7D1C0')
def test_contract_9d7f7cf7d1c0():
    '原 PRD/需求溯源和已交付 typed 包/selection 输入字节继续保留'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_D85FF56BA020')
def test_contract_d85ff56ba020():
    'Do not implement Package B, S1/S2 game business or sandbox refactoring in this round no PackageB, S1/S2 game business or sandbox refactoring work'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_8F38F3C92E38')
def test_contract_8f38f3c92e38():
    'Do not predefine new services, long-lived processes, databases, separate evaluation engines or new governance framework no daemon/database/new evaluation engine/governance framework'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_2921ABE187A0')
def test_contract_2921abe187a0():
    'Provenance remains traceability rather than independent normative authority'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_20B744439A62')
def test_contract_20b744439a62():
    'Plan regression verification for existing behavior; never use old paths or duplicate implementation merely to manufacture RED route retains regression/probe coverage; no obsolete path/missing import/duplicate code used to fabricate behavioral RED'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_B97840991292')
def test_contract_b97840991292():
    'Treat Locator as location information, not authoritative fact answers; adopted conclusions require reading valid sources and state impact/use, not completion proof actual valid read and use/impact recorded, query/adoption alone not completion proof'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_CACDDF9C9C16')
def test_contract_cacddf9c9c16():
    'SPEC owner fixes budgets through jimuyun-spec native derive/refresh; owner wording and numbers must converge before VDD; Architecture does not directly edit SPEC/selection and future changes cannot auto-expand at runtime SPEC owner native refresh only, no Architecture direct kernel/selection edit or runtime expansion'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_0E26CE73B585')
def test_contract_0e26ce73b585():
    'Do not replace downstream-required normative content with provenance-only inputs all mandatory downstream clauses remain canonical/normative/adopted, provenance supplies traceability only'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_05FD661FC842')
def test_contract_05fd661fc842():
    'Require explicit maintainer authorization after merge for first publication no publish action; future first generation requires separate explicit owner authorization after main merge'
    publication_guard()


@pytest.mark.cer_assertion('ASSERT_69EDF6ED6888')
def test_contract_69edf6ed6888():
    'Use repository-owned stage integrations depending on a shared read-only query adapter that depends on existing Locator core, configuration resolution and source readers stage -> shared readonly adapter -> existing Locator/config/reader; no replacement platform or publisher dependency'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_A7F119F56C39')
def test_contract_a7f119f56c39():
    "Exclude full standard migration of Package B's five skills, redoing 8-05/8-06/7-31, and TC-D2/D4/D5/D6 no PackageB five-skill migration, redo8-05/8-06/7-31 or TC-D2/D4/D5/D6"
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_6A927E42C816')
def test_contract_6a927e42c816():
    'Exclude Package B full migration, redoing existing stages, TC-D2/D4/D5/D6, S1/S2 game business and sandbox refactoring no Package B full migration, stage redo, TC-D2/D4/D5/D6, S1/S2 game or sandbox tasks'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_67E63C3F227A')
def test_contract_67e63c3f227a():
    '保留普通 VDD 建议与正式门禁分开及 ADR44/50/57/59 保护'
    adr_guard()


@pytest.mark.cer_assertion('ASSERT_D4DA2D8966A8')
def test_contract_d4da2d8966a8():
    'Exclude new knowledge platform, vector database, general RAG, Memory/Miner, whole-repository index rebuild and mandatory full publication no new knowledge platform/vector DB/RAG/Memory/Miner/index rebuild/full publication mandate'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_C11029194DF3')
def test_contract_c11029194df3():
    'Technical support means this capability is not a new runtime prerequisite; Q1 determines whether and in what order to execute and provides no parallel permission Q1 maintainer schedule remains unresolved, no S2/parallel permission inferred'
    schedule_guard()


@pytest.mark.cer_assertion('ASSERT_BCC9695149FF')
def test_contract_bcc9695149ff():
    'Exclude Phase services, Hosted isolation, accounts/production nodes, game business, Package B and whole-repository index/RAG; none becomes implicit deployment work no Phase/Hosted/accounts/production/game/PackageB/index/RAG work implied'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_FD4509758AAB')
def test_contract_fd4509758aab():
    'Preserve normative/provenance division, typed package and selection rules'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_BAD87DEA440C')
def test_contract_bad87dea440c():
    'PRD-time references to this round and installation/cache/download/review are historical evidence, not product obligations or current permission not product duties or current authorization; current gates remain explicit'
    original_source_guard()


@pytest.mark.cer_assertion('ASSERT_8E9A6B056EA1')
def test_contract_8e9a6b056ea1():
    'Historical plans, checkmarks and reports cannot alone prove implementation complete cannot label implemented/complete; require real current source/call/test and formal owner evidence'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_59F8C120CE6F')
def test_contract_59f8c120ce6f():
    'Reuse approved unchanged inputs without mechanically repeating PRD lookup; historical reuse text is not evidence of new implementation or Locator execution no mechanical repeat or fabricated new Locator execution/implementation from historical reuse text'
    original_source_guard()


@pytest.mark.cer_assertion('ASSERT_FAF1559ED039')
def test_contract_faf1559ed039():
    'Do not infer permission for immediate S2 execution, parallel implementation or changed schedule; Q1 requires maintainer confirmation no immediate/parallel S2 execution or changed schedule; maintainer confirmation remains pending'
    schedule_guard()


@pytest.mark.cer_assertion('ASSERT_AC8D10DEA116')
def test_contract_ac8d10dea116():
    '保留 Package B/7-31 不在本轮、采用保留能力须在正式交付之后'
    schedule_guard()


@pytest.mark.cer_assertion('ASSERT_999DE5B58B6A')
def test_contract_999de5b58b6a():
    'Permit actual default query without creating frozen knowledge, Skill-input attestation, extra authorization, review lineage or the full governance artifacts query occurs without frozen knowledge, attestation, authorization, review lineage or governance package'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_E50A12910925')
def test_contract_e50a12910925():
    'Do not interpret budget values as a performance SLA no measured SLA or latency promise inferred from conservative resource caps'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_17CD3FC9ABEA')
def test_contract_17cd3fc9abea():
    'Scoped delivered normative inputs retain typed source identity'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_13CE2513BEF1')
def test_contract_13ce2513bef1():
    '保留阶段末独立审查与工作方认可，旧阶段状态不重开、不授予并行权限'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_B4AAE71E87A7')
def test_contract_b4aae71e87a7():
    'Maintain existing hash gates and do not introduce whole-repository freeze formal hash gates retained, no whole-repository freeze'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_E9074C067973')
def test_contract_e9074c067973():
    '保留阶段末门禁、未通过不得最终 push/PR/Acceptance 的边界'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_7A2E25478BB9')
def test_contract_7a2e25478bb9():
    '保留共享接口/诊断/记录和已固化预算，读取交付输入不重新评审上游'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_ED8CDEBD1170')
def test_contract_ed8cdebd1170():
    'Do not borrow another consumer identity, hand-edit generated projections or bypass publication/freshness checks; preserve formal owners, typed roles, selection, source hashes and Acceptance authority no borrowed consumer or hand-edited generated projection, no bypass flags, owner/hash/selection preserved; query result remains advisory'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_C46BA64DF35B')
def test_contract_c46ba64df35b():
    'Preserve development/auto governance-off behavior resolver preserves explicit > environment > phase precedence; development auto is off; artifact diff shows no governance package synthesized by query'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_C82CF2422089')
def test_contract_c82cf2422089():
    'Preserve formal governance and typed SPEC/VDD/Quick Dev/Acceptance contracts; define result compatibility strategy before implementation new planning-query.v1 isolated from legacy Locator status/exit; original governance/SPEC/VDD/QuickDev/Acceptance contracts remain'
    legacy_guard()


@pytest.mark.cer_assertion('ASSERT_F8706C4018E8')
def test_contract_f8706c4018e8():
    '保留 VDD 普通建议与正式治理的明确适用记录，不伪造批准状态'
    adr_guard()


@pytest.mark.cer_assertion('ASSERT_0505499A0382')
def test_contract_0505499a0382():
    'Current requirement uses fixed stable hosting toolchain; VDD self-changes follow self-hosted contract and candidate is only for isolated validation stable fixed host unchanged, isolated candidate samples only'
    stable_owner_guard()


@pytest.mark.cer_assertion('ASSERT_7CB91BB2FA76')
def test_contract_7cb91bb2fa76():
    'Use the stable verified toolchain; validate future candidate query/VDD only in isolated samples without replacing the hosting toolchain or changing frozen inputs hosting compiler/QuickDev/Acceptance remain stable and input hashes unchanged; candidate tools run only in isolated validation and cannot host this requirement'
    stable_owner_guard()


@pytest.mark.cer_assertion('ASSERT_370A27148C69')
def test_contract_370a27148c69():
    'Preserve existing fields, status meanings and exit semantics; do not delete, rename or reinterpret existing return values; do not force new finer states on unmigrated consumers fields/status meanings/exit codes equal; unmigrated consumers never see new planning-query outcomes'
    legacy_guard()


@pytest.mark.cer_assertion('ASSERT_1CF333F248B4')
def test_contract_1cf333f248b4():
    'Trace current source, callers, tests and control contracts; regress existing behavior without fake RED; label out-of-Locator direct verification direct-source existing behavior regression no fakeRED, direct-source origin honest'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_27A22F872C63')
def test_contract_27a22f872c63():
    'Budget design creates no new governance switch, freeze or publication; unsuitable real-sample values require explicit return to SPEC owner for revision no governance/freeze/publication side effects or runtime widening; revision returns to SPEC owner refresh'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_D5C9FCC32C39')
def test_contract_d5c9fcc32c39():
    'Maintainer separately authorizes initial knowledge publication after implementation verification and main merge; this planning stage does not publish planning does not publish; later separate maintainer authorization only after verification/main merge'
    publication_guard()


@pytest.mark.cer_assertion('ASSERT_C3348AF86BDA')
def test_contract_c3348af86bda():
    'Retain required modules, freezing, source integrity and authorization checks; lightweight outcome cannot satisfy or replace them formal gate remains blocking despite lightweight outcome'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_63748AAE8521')
def test_contract_63748aae8521():
    "Obtain maintainer confirmation of the specific S2 schedule before execution; technical non-dependency is not parallel permission and does not block this requirement's planning no S2 task or parallel execution inferred; Q1 remains maintainer-owned and does not block this planning scope"
    schedule_guard()


@pytest.mark.cer_assertion('ASSERT_C2008D13B20C')
def test_contract_c2008d13b20c():
    'Set finite upper bounds for candidates, output and calls; Architecture proposes technical design and SPEC owner fixes values/accounting through native derive/refresh; subsequent changes remain SPEC-owner decisions without invented latency SLA finite candidate/output/call limits match normative owner; changes require native derive/refresh and no fabricated SLA'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_02A80F5DFA2C')
def test_contract_02a80f5dfa2c():
    'Validate candidates only in isolated samples, keep stable toolchain hosting this requirement, obey self-hosted contract and do not modify frozen inputs stable host and original inputs unchanged, candidate only isolated self-hosted validation'
    stable_owner_guard()


@pytest.mark.cer_assertion('ASSERT_7FFACC7748F0')
def test_contract_7ffacc7748f0():
    'Complete formal Acceptance through the existing owner stage4 claims planning only and eventual formal Acceptance uses run-refactor-implementation-acceptance owner; no author self-check replaces required external review or Acceptance'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_B4C8A4D06236')
def test_contract_b4c8a4d06236():
    'Do not rewrite historical plans, evidence or generations original bytes unchanged, failed/cancel records retained'
    original_source_guard()


@pytest.mark.cer_assertion('ASSERT_0393FA36BBE5')
def test_contract_0393fa36bbe5():
    'Fixtures prove only deterministic branches; formal completion remains Acceptance owner and architecture-stage specification does not mean future capability ran fixtures prove branches only, architecture not executed capability, Acceptance owner remains'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_0F3F35C7D966')
def test_contract_0f3f35c7d966():
    'Maintainer explicitly publishes through the existing process when a valid new generation is first needed; routine query never triggers publication no publication occurs; existing maintainer-owned process requires separate authorization for first generation'
    publication_guard()


@pytest.mark.cer_assertion('ASSERT_1A430B96D85A')
def test_contract_1a430b96d85a():
    'Do not claim completion from configuration text alone completion rejected until real trigger/query/read/adoption and required verification exist'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_DB03166C507E')
def test_contract_db03166c507e():
    '保留本仓配置有效值、同一判断去重及不修改既有合并行为'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_A63BCAFECC82')
def test_contract_a63bcafecc82():
    'Continue mandatory validation, freezing and authorization; required-module or integrity failures block formal validation/freeze/authorization still block; no query substitute'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_D5BE6F9B0842')
def test_contract_d5be6f9b0842():
    'Treat defaults as conservative engineering values, not measured performance SLA; revise through owner explicitly rather than silently widening conservative not measured SLA, unsuitable samples return owner refresh, no silent widening'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_4B9C0852F067')
def test_contract_4b9c0852f067():
    '保留 VDD caller 的独立 read/use 决定、查询建议非权威和 typed 输入角色不变'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_8BF65710077E')
def test_contract_8bf65710077e():
    'Implementation may choose internal split/test filenames based on existing organization but must not create a second validation/diagnostic semantics filenames may vary under declared write scope, no second diagnostic/validation semantics'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_2DAB31E5B3B7')
def test_contract_2dab31e5b3b7():
    'Downstream obligations must enter normative content or applicable typed companions; valid selection cannot substitute for body completeness every downstream duty present in normative/adopted content; valid selection alone not completeness'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_C710C48E3CAC')
def test_contract_c710c48e3cac():
    '保留既有 SPEC/Architecture 外壳和退役路径边界，不修改其原有功能'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_D3207953C3F7')
def test_contract_d3207953c3f7():
    'Use these as consumer decision categories under CAP-7/FR-07, not claims that current CLI has those status fields; do not introduce a new public Locator schema legacy callers retain vocabulary; planning-query.v1 only new consumer-facing interface, no claim those are existing Locator status fields'
    legacy_guard()


@pytest.mark.cer_assertion('ASSERT_2F2D26DDB39F')
def test_contract_2f2d26ddb39f():
    'Follow existing mandatory governance repair contracts without using lightweight query as a bypass existing owner repair contract enforced; lightweight query cannot waive mandatory action'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_FE2232D898AE')
def test_contract_fe2232d898ae():
    'Run only within existing local repository process/file boundaries; no new daemon, cloud provider, database, Phase API, credential or production deployment change existing local process/files only, no daemon/cloud/DB/Phase/credential/deployment change'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_89793D285B4F')
def test_contract_89793d285b4f():
    '保留规划/包有效性不等于实施和 Acceptance；范围内验收各自有真实证据'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_48CE539981D7')
def test_contract_48ce539981d7():
    'Exclude Codex kernel, context compaction, automatic new threads and app-server/SDK changes no Codex kernel/context compaction/new thread/appserver/SDK feature'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_D1D454E5D9F2')
def test_contract_d1d454e5d9f2():
    'Do not hand-edit generated projections, forge publication records or enable debug options that skip publication/freshness checks no generated projection edit, forged generation or allow-unpublished/allow-stale/noncanonical catalog bypass'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_B0E4247583D1')
def test_contract_b0e4247583d1():
    'Follow the approved single-maintainer internal capability model without inventing UI, market metrics or latency targets single maintainer internal tooling only; no UI, market metric or latency targets introduced'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_455649B5C62A')
def test_contract_455649b5c62a():
    'Do not treat PRD internal checks as satisfying future feature implementation AC PRD checks never marked implementation AC passed'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_BA91C94355C2')
def test_contract_ba91c94355c2():
    'Use failure-modes.md for FR-07 decision order without replacing existing contracts when governance is enabled full failure-mode order applied without substituting lightweight diagnostic for required formal gate'
    legacy_guard()
    diagnostic_priority_guard()


@pytest.mark.cer_assertion('ASSERT_725D2792FC8F')
def test_contract_725d2792fc8f():
    '保留现有外壳功能、原生不改、退役 Stock QuickDev/GDS 不恢复和安装事实不冒称'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_E805FAE00D8C')
def test_contract_e805fae00d8c():
    '保留实际 owner 记录、建议不自动变 Accepted 和保留能力的适用边界'
    adr_guard()


@pytest.mark.cer_assertion('ASSERT_11076BE609FA')
def test_contract_11076be609fa():
    'Continue using jimuyun-spec canonical SPEC package, typed companion/provenance and external selection commitment; preserve typed roles, package integrity and selection rules canonical_package validate_selection verifies actual current/record and every source hash; no handwritten selection/kernel'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_F8B848EA6CBB')
def test_contract_f8b848ea6cbb():
    '保留原始全文和来源 ID；新范围内义务须从正文/适用 companion 完整承接'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_CBF51EF51371')
def test_contract_cbf51ef51371():
    '已完成阶段不重开；后续阶段末 A/B 与工作方认可、用户逐步确认边界继续'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_F3CF264E79D0')
def test_contract_f3cf264e79d0():
    'Exclude automatic Bootstrap, general entrypoint skill, internal reviewer platform and slice parallel scheduling no automatic Bootstrap/general entrypoint/reviewer platform/slice scheduler'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_A8145B6CF565')
def test_contract_a8145b6cf565():
    'Exclude new knowledge platform, general RAG/vector store, whole-repository index rebuild, Codex kernel/app-server/SDK and Phase/Hosted feature changes no new knowledge platform/general RAG/vector store/index rebuild/Codex internals/Phase Hosted features; reuse existing Locator'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_D8B2FD0C58CA')
def test_contract_d8b2fd0c58ca():
    'Exclude Phase API/accounts/production nodes/user sandbox/Hosted game features and S1/S2 game business or sandbox refactoring no Phase/accounts/production nodes/sandbox/Hosted/S1/S2 business changes'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_966987A5BADF')
def test_contract_966987a5badf():
    'Native BMAD consumes only externally supplied context and retains original bytes; formal governance, knowledge publication and Acceptance retain their respective owners native bytes unchanged, only external context; governance/publication/Acceptance remain original owners'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_99F96E43AB70')
def test_contract_99f96e43ab70():
    '保留不修改官方 BMAD 文件的既有边界和既有外壳完整性'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_A559CD58DB04')
def test_contract_a559cd58db04():
    'Use behavior-contracts.md formally refreshed candidate/output/call/timeout defaults, hard caps, accounting and terminal rules; numeric changes require SPEC owner refresh, not runtime expansion values/accounting/reserve match normative behavior-contracts; future numeric edit requires SPEC refresh'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_45F233F69106')
def test_contract_45f233f69106():
    '读取完整已交付输入，失败优先级与保留的安全/来源条款完整承接'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_80CDBEFE451B')
def test_contract_80cdbefe451b():
    'Keep query switch independent and create no frozen knowledge, Skill-input attestation, authorization, review lineage or governance package query switch independent, no freeze/attestation/authorization/lineage/governance package'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_2687DDBEA58E')
def test_contract_2687ddbea58e():
    'Preserve original section 7 without byte edits whole original source SHA256 ce45693489d02227442c04c9b4e7220121a897d81dab03abc7867e6ceff11950 unchanged including section7'
    original_source_guard()


@pytest.mark.cer_assertion('ASSERT_8903766FC3B9')
def test_contract_8903766fc3b9():
    'Do not introduce a new whole-repository freeze only existing caller-owned result/memlog is changed; no new whole-repository freeze/control plane or modified formal source-freeze owner'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_4C2F3548DB28')
def test_contract_4c2f3548db28():
    'VDD/共享查询与正式治理的适用区分仍需明确且不伪造 Accepted'
    adr_guard()


@pytest.mark.cer_assertion('ASSERT_25A45D343A1E')
def test_contract_25a45d343a1e():
    'Honor the remaining explicit exclusions in scope-and-decisions.md no PackageB, TC-D2/D4/D5/D6, sandbox/game/Phase/Hosted, general platform/RAG, automatic publication, reviewer/scheduler or history rewrite included'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_AB866697B090')
def test_contract_ab866697b090():
    """Planning labels and future Windows/Acceptance text confer no runtime proof."""
    from closure_predicate import validate_runtime_closure
    from shared_execution import admissible
    from runtime_evidence import sha256_value

    state = read(PLAN / 'compiler-state.v1.json')
    bundle = read(PLAN / 'semantic-plan-bundle.v1.json')
    assert state['state'] == 'plan-ready' and not bundle.get('authorizes')
    selected = next(s for s in bundle['slices'] if s['slice_id'] == 'S5')
    expected = {f'S5|{aid}|terminal' for aid in selected['acceptance_ids']}
    # Invoke the pure denial predicate only, never the Q8 publisher. These
    # deliberately incomplete unit inputs are not emitted as runtime records.
    for claim in ('plan-ready', 'examples-specified', 'windows-required', 'acceptance-passed'):
        asserted = {'status': claim, 'cases': 108, 'test_executions': 1,
                    'exit_code': 0, 'timed_out': False}
        with pytest.raises(ValueError, match='reuse-unsuccessful-or-incomplete-execution'):
            admissible(asserted)
        valid, findings = validate_runtime_closure(
            [{'status': claim}], expected, sha256_value({'unit': 'unexecuted-claim'}))
        assert not valid and 'tuple-key-set-mismatch' in findings
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_5777409A39C1')
def test_contract_5777409a39c1():
    """Accepted applicability preserves VDD governance and actual Windows duties."""
    from governance_policy import resolve_governance_policy, GOVERNANCE_CHECKS

    text = (ROOT / 'docs/adr/ADR-0048-repository-knowledge-locator-workflow-consumption.md').read_text(encoding='utf-8')
    assert '- Status: Accepted' in text
    assert 'It does not assert that the integration,' in text
    assert 'Windows verification, or implementation Acceptance has completed.' in text
    assert 'First publication for the new consumer remains a separate maintainer action' in text
    for owner in ('ADR-0044', 'ADR-0050', 'ADR-0057', 'ADR-0059'):
        assert owner in text
    assert resolve_governance_policy(None, environment={})['enabled'] is False
    assert resolve_governance_policy('auto', environment={'PHASEA_SERVICE_STATE': 'development'})['enabled'] is False
    forced = resolve_governance_policy('on', environment={'PHASEA_SERVICE_STATE': 'development', 'JIMUYUN_GOVERNANCE_MODE': 'off'})
    assert forced['enabled'] is True and forced['checks'] == list(GOVERNANCE_CHECKS)
    # The real existing publication request validator retains owner/confirmation
    # denials. It performs no publication or historical upstream review.
    publication_guard()


@pytest.mark.cer_assertion('ASSERT_1FBF989D87FE')
def test_contract_1fbf989d87fe():
    """Only complete observed phases qualify; OS identity cannot be relabeled."""
    import platform
    from runtime_evidence import sha256_value
    from shared_execution import admissible, invalidation_reason, ENVIRONMENT_SCHEMA

    # In-memory schema fixtures exercise the admission boundary only. They are
    # never written to native evidence directories or claimed as real runs.
    node = 'unit-fixture::observed-case'
    report = {'selected': [node], 'collected': {node: {}}, 'complete': True,
              'errors': [], 'exit_code': 0, 'events': [
                  {'node_id': node, 'phase': phase, 'outcome': 'passed', 'xfail': False}
                  for phase in ('setup', 'call', 'teardown')]}
    fixture = {'schema': 'quick-dev.process-receipt.v2', 'exit_code': 0,
               'timed_out': False, 'case_report': report,
               'case_report_sha256': sha256_value(report)}
    admissible(fixture)
    for mutation in ('summary-only', 'missing-call', 'skipped', 'incomplete', 'tampered', 'timeout'):
        invalid = copy.deepcopy(fixture)
        if mutation == 'summary-only':
            invalid.pop('case_report')
        elif mutation == 'missing-call':
            invalid['case_report']['events'] = [e for e in invalid['case_report']['events'] if e['phase'] != 'call']
        elif mutation == 'skipped':
            invalid['case_report']['events'][1]['outcome'] = 'skipped'
        elif mutation == 'incomplete':
            invalid['case_report']['complete'] = False
        elif mutation == 'tampered':
            invalid['case_report_sha256'] = 'sha256:' + '0' * 64
        else:
            invalid['timed_out'] = True
        if 'case_report' in invalid and mutation != 'tampered':
            invalid['case_report_sha256'] = sha256_value(invalid['case_report'])
        with pytest.raises(ValueError):
            admissible(invalid)
    current = {'environment': {'schema': ENVIRONMENT_SCHEMA, 'system': platform.system()}}
    assert invalidation_reason(current, copy.deepcopy(current)) is None
    different = copy.deepcopy(current)
    different['environment']['system'] = 'Windows' if platform.system() != 'Windows' else 'Linux'
    assert invalidation_reason(current, different) == 'reuse-environment-changed:system'
