"""ADR-0041/0048/0062: ownerless planning guards, never production RED.

These tests check immutable input/owner contracts and negative authority paths.
They do not turn a plan, source selection, or a guard pass into runtime delivery.
The business consumer chains are tested separately in the declared S5/S7 surface.
"""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tomllib
from functools import lru_cache

import pytest

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT/'execution-plans/2026-10-23-bmad-vdd-knowledge-query-runtime-r23'
INPUT = ROOT/'logs/vdd-planning-input-2026-10-22'
SPEC = ROOT/'_bmad-output/specs/spec-bmad-vdd-knowledge-query/SPEC.md'
NATIVE_BASE = '127b26a4a22bcd97a4231296c471d06a3548521f'
SELECTION = 'sha256:373d280b03a68904e97306a7b82b797a88eff56eeb3d7989f6b28bdf6ef117c7'
sys.path[:0] = [str(ROOT), str(ROOT/'scripts/python'),
    str(ROOT/'.agents/skills/quick-dev-tdd-adapter/tools'),
    str(ROOT/'.agents/skills/vdd-execution-plan/scripts')]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(None)
def package_guard():
    owner = load('boundary_selection_owner', '.agents/skills/jimuyun-spec/scripts/canonical_package.py')
    pointer = ROOT/'_bmad-output/specs/canonical-spec-package-selections/current/SPEC-bmad-vdd-knowledge-query.json'
    actual = owner.validate_selection(ROOT, SPEC, pointer)
    assert actual['selection_hash'] == SELECTION
    descriptor, selection, semantic_hash = owner.build_contract(ROOT, SPEC)
    assert semantic_hash == SELECTION and len(selection['role_graph']) == 9
    assert len(descriptor['sources']) == 2
    assert all(x['role'] == 'provenance' for x in descriptor['sources'])
    assert {x['role'] for x in descriptor['companions']} == {'normative_companion', 'adopted_companion'}
    identities = read(INPUT/'source-identities.json')
    assert identities['selection_hash'] == SELECTION and not identities['authorizes']
    for source in identities['sources']:
        assert digest(ROOT/source['path']) == source['sha256']
        assert (ROOT/source['path']).read_bytes() == (INPUT/'source-snapshots'/source['path']).read_bytes()
    index = read(PLAN/'source-index.v1.json')
    assert index['sha256'] == 'sha256:f840cde80397603a380e2c790adbf86f545dc10ee7c549311ccc550a49ae6286'
    assert len(index['entries']) == 62 and len(index['companions']) == 7
    for item in index['companions']:
        assert 'sha256:'+digest(ROOT/item['repository_relative_source_path']) == item['source_sha256']
    mapping = read(INPUT/'source-map.json')
    assert not mapping['authorizes'] and mapping['selection_hash'] == SELECTION
    assert digest(INPUT/'compiler-input.md') == mapping['projection_sha256'].removeprefix('sha256:')
    for block in mapping['source_blocks']:
        data = (ROOT/block['path']).read_bytes()[block['byte_start']:block['byte_end']]
        assert hashlib.sha256(data).hexdigest() == block['sha256']
    for path in {b['path'] for b in mapping['source_blocks']}:
        blocks = sorted((b for b in mapping['source_blocks'] if b['path'] == path), key=lambda b:b['byte_start'])
        assert blocks[0]['byte_start'] == 0
        assert all(a['byte_end'] == b['byte_start'] for a,b in zip(blocks,blocks[1:]))
        assert blocks[-1]['byte_end'] == (ROOT/path).stat().st_size
    assert len(mapping['restatement_groups']) == 10
    for invalid in ('../outside.md', '/absolute.md', 'C:/secret.md', 'a\\b.md'):
        with pytest.raises(ValueError):
            owner.validate_path(ROOT, invalid)
    return descriptor


@lru_cache(None)
def original_source_guard():
    path = ROOT/'_bmad-output/planning-artifacts/prds/prd-bmad-vdd-knowledge-query-2026-10-22/sources/bmad-vdd-knowledge-query-requirements.md'
    assert digest(path) == 'ce45693489d02227442c04c9b4e7220121a897d81dab03abc7867e6ceff11950'
    package_guard()


@lru_cache(None)
def native_guard():
    from scripts.toolchain.bmad_native import verify, load_lock
    lock = verify(ROOT)
    assert lock['version'] == '6.12.4'
    assert lock == load_lock()
    for name, expected in {**lock['files'], **lock['runtime']}.items():
        assert digest(ROOT/name) == expected
    assert sys.version_info >= (3,11)
    assert (ROOT/'_bmad/custom/bmad-prd.toml').is_file()
    for name in ('jimuyun-spec/scripts/bridge.py', 'jimuyun-architecture/scripts/invoke.py'):
        assert (ROOT/'.agents/skills'/name).is_file()
    assert not (ROOT/'.agents/skills/bmad-quick-dev/SKILL.md').exists()
    assert not (ROOT/'.agents/skills/bmad-gds/SKILL.md').exists()
    # Existing native merge behavior, including duplicates in ordinary arrays.
    merge = load('boundary_native_merge', '_bmad/scripts/config_utils.py')
    assert merge.structural_merge({'nested':{'a':1},'steps':['x']},
        {'nested':{'b':2},'steps':['x','y']}) == {'nested':{'a':1,'b':2},'steps':['x','x','y']}


@lru_cache(None)
def scope_guard():
    bundle = read(PLAN/'semantic-plan-bundle.v1.json')
    approved = {
        '.agents/skills/jimuyun-architecture/scripts/invoke.py',
        '.agents/skills/jimuyun-spec/scripts/bridge.py', '_bmad/custom/bmad-prd.toml',
        'knowledge/contracts/knowledge-consumer-projections.v1.schema.json',
        'knowledge/contracts/knowledge-locator-request.v1.schema.json',
        'knowledge/planning-query.toml','knowledge/policies/consumer-policies.v2.json',
        'scripts/python/_knowledge_catalog_builder.py','scripts/python/_knowledge_locator_core.py',
        'scripts/python/knowledge_locator.py','scripts/toolchain/knowledge_query/adapter.py',
        'scripts/vdd/compile_plan.py'}
    assert {p for s in bundle['slices'] for p in s['production_owners']} == approved
    allowed = {p for s in bundle['slices'] for p in s['allowed_write_paths']}
    allowed.add('docs/adr/ADR-0048-repository-knowledge-locator-workflow-consumption.md')
    changed = subprocess.check_output(['git','-C',str(ROOT),'diff','--name-only',NATIVE_BASE], text=True).splitlines()
    assert set(changed) <= allowed, sorted(set(changed)-allowed)
    assert not any(p.startswith(('PhaseA.','runtime/','addons/','scenes/','scripts/sc/')) for p in approved)
    own = next(s for s in bundle['slices'] if s['slice_id'] == 'S2')
    assert own['production_owners'] == []
    assert own['allowed_write_paths'] == ['tests/toolchain/knowledge_query/test_planning_boundaries.py']
    intents = {f['failure_intent_id']:f for f in bundle['failure_intents']}
    assert all(intents[i]['failure_family'] == 'semantic-contract-gap' for i in own['failure_intent_ids'])
    # A pure guard cannot gain a production RED role through a forged intent.
    from quick_dev_handoff import repair_runtime_red_roles
    before = json.dumps(bundle, sort_keys=True)
    with pytest.raises(ValueError, match='lacks production/assertion/observable binding'):
        repair_runtime_red_roles(bundle, [own['failure_intent_ids'][0]])
    assert json.dumps(bundle, sort_keys=True) == before


@lru_cache(None)
def stable_owner_guard():
    # These are current hosting/evidence owners, not candidate VDD integration.
    prefixes = ('.agents/skills/quick-dev-tdd-adapter/',
                '.agents/skills/vdd-execution-plan/',
                '.agents/skills/run-refactor-implementation-acceptance/',
                'scripts/quick_dev/', 'scripts/sc/')
    changed = subprocess.check_output(['git','-C',str(ROOT),'diff','--name-only',NATIVE_BASE], text=True).splitlines()
    assert not [p for p in changed if p.startswith(prefixes)]
    for path in ['scripts/quick_dev/run.py',
        '.agents/skills/quick-dev-tdd-adapter/tools/independent_judge_v2.py',
        '.agents/skills/quick-dev-tdd-adapter/tools/process_executor_v2.py',
        '.agents/skills/quick-dev-tdd-adapter/tools/coverage_predicates.py',
        '.agents/skills/vdd-execution-plan/scripts/semantic_compiler.py']:
        frozen = subprocess.check_output(['git','-C',str(ROOT),'show',NATIVE_BASE+':'+path])
        assert (ROOT/path).read_bytes() == frozen
    original_source_guard()


@lru_cache(None)
def governance_guard():
    from governance_policy import resolve_governance_policy, GOVERNANCE_CHECKS
    for phase in ('development','test','production'):
        env={'PHASEA_SERVICE_STATE':phase}
        assert resolve_governance_policy(None,environment=env)['enabled'] == (phase!='development')
        assert resolve_governance_policy('off',environment={**env,'JIMUYUN_GOVERNANCE_MODE':'on'})['enabled'] is False
        enabled=resolve_governance_policy('on',environment={**env,'JIMUYUN_GOVERNANCE_MODE':'off'})
        assert enabled['enabled'] is True and enabled['checks'] == list(GOVERNANCE_CHECKS)
    assert resolve_governance_policy(None,environment={})['enabled'] is False
    assert resolve_governance_policy(None,environment={'JIMUYUN_GOVERNANCE_MODE':'on'})['enabled'] is True
    with pytest.raises(ValueError):resolve_governance_policy('unknown',environment={})
    publication_guard()


@lru_cache(None)
def publication_guard():
    import publish_knowledge_catalog as owner
    sha='a'*40
    request={'schema_version':owner.PUBLICATION_REQUEST_SCHEMA_VERSION,'request_id':'boundary-only',
        'caller':'maintain-knowledge-base','trigger':'operator-requested','target_plan':'execution-plans/example',
        'main_commit':sha,'automatic':False,'maintainer_confirmation':True,
        'recorded_at':'2026-10-23T00:00:00+00:00','authorizes':['knowledge-publication'],'source_route':None}
    # Validation only: do not invoke any publication writer.
    assert owner._validate_publication_request(request,expected_main=sha)['caller']=='maintain-knowledge-base'
    for change,reason in [({'automatic':True},'confirmation'),({'maintainer_confirmation':False},'confirmation'),
        ({'caller':'bmad-planning'},'caller'),({'caller':'vdd'},'caller'),({'authorizes':[]},'authority'),
        ({'main_commit':'b'*40},'main_mismatch')]:
        with pytest.raises(ValueError,match=reason):owner._validate_publication_request({**request,**change},expected_main=sha)


@lru_cache(None)
def authority_guard():
    from coverage_predicates import _validate_detached_binding
    for label in ('plan-ready','passed','implementation-complete','acceptance-passed'):
        with pytest.raises(ValueError):_validate_detached_binding({'status':label},'self-hosted')
    bundle=read(PLAN/'semantic-plan-bundle.v1.json')
    from behavior_routing import validate_plan
    validate_plan(bundle)
    assert not bundle.get('authorizes')
    assert not any(i.get('disposition') in {'present','missing'} for i in bundle['behavior_routing']['intents'])
    package_guard()
    scope_guard()


@lru_cache(None)
def dependency_guard():
    source=(ROOT/'scripts/toolchain/knowledge_query/adapter.py').read_text()
    tree=ast.parse(source)
    imports={n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    imports.update(a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names)
    assert '_knowledge_locator_core' in imports
    forbidden=('publish_knowledge','bootstrap','sqlite','psycopg','fastapi','requests','httpx','openai','chromadb','faiss')
    assert not {name for name in imports if any(part in name for part in forbidden)}
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'eval','exec','__import__'} for n in ast.walk(tree))
    assert 'query_with_diagnostics' in source
    assert 'allow_unpublished=True' not in source and 'allow_stale=True' not in source
    scope_guard()
    publication_guard()


@lru_cache(None)
def budget_guard():
    source=(SPEC.parent/'behavior-contracts.md').read_text()
    data=tomllib.loads((ROOT/'knowledge/planning-query.toml').read_text())['query']
    from scripts.toolchain.knowledge_query import adapter
    expected={'max_candidates':(12,20),'max_output_bytes':(65536,131072),
              'max_calls':(3,5),'timeout_seconds':(30,60)}
    for key,(default,cap) in expected.items():
        assert f'| {key} | {default} | {cap} |' in source
        assert data[key]==default and type(data[key]) is int
        assert adapter._LIMITS[key][1]==cap
    assert adapter._LIMITS['max_output_bytes'][0]==4096
    assert '4096' in source and '512' in source
    assert len(data['stages'])==5 and data['enabled'] is True
    package_guard()
    governance_guard()


@lru_cache(None)
def legacy_guard():
    import _knowledge_locator_core as core
    catalog={'entries':[{'path':'docs/example.md','content':'planning contract','source_sha256':'a'*64}]}
    assert core.locate({'query':'planning contract'},catalog)['status']=='matched'
    empty=core.locate({'query':'unmatcheduniquevalue'},catalog)
    assert empty['status']=='insufficient_match' and empty['candidates']==[]
    schema=read(ROOT/'knowledge/contracts/knowledge-locator-result.v1.schema.json')
    enum=schema['properties']['status']['enum']
    assert 'matched' in enum and 'insufficient_match' in enum and 'blocked' in enum
    assert not set(enum)&{'hit','no_match','unavailable','budget_exhausted','cancelled'}
    dependency_guard()


@lru_cache(None)
def adr_guard():
    text=(ROOT/'docs/adr/ADR-0048-repository-knowledge-locator-workflow-consumption.md').read_text()
    assert 'Accepted' in text and 'Applicability amendment: ordinary planning advice (2026-10-23)' in text
    for adr in ('ADR-0044','ADR-0050','ADR-0057','ADR-0059'):assert adr in text
    assert 'before implementing' in text and 'does not assert' in text
    governance_guard()


@lru_cache(None)
def schedule_guard():
    original_source_guard()
    text=(SPEC.parent/'scope-and-decisions.md').read_text()
    assert 'S2' in text and ('\u5f85' in text or 'pending' in text.lower())
    assert 'Package B' in text
    scope_guard()
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_60CF612F2E06')
def test_contract_60cf612f2e06():
    'Keep Python3.11+ support; Python3.12.14 and uv0.12.23 are verified reference environment versions, not mandatory patch upgrades for other platforms Python3.11+ supported, reference3.12.14/uv0.12.23 not forced patches'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_DB03166C507E')
def test_contract_db03166c507e():
    'Preserve existing override and array merge semantics nested override and ordinary-array append semantics unchanged; dedup occurs in shared episode layer not modified native merge'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_89793D285B4F')
def test_contract_89793d285b4f():
    'All 14 AC are future implementation obligations; SPEC generation/package validation is not execution success and existing Acceptance owner retains formal completion authority generation/selection validity not feature execution or Acceptance; all14 future AC remain distinct'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_0CDCD2C2092C')
def test_contract_0cdcd2c2092c():
    'Query assists judgment but does not become fact, implementation-completion or Acceptance authority. adopted factual conclusions require verified read identity; no hit/output file marks implementation-complete or acceptance-passed; native/typed/Acceptance owners stay authoritative'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_C11029194DF3')
def test_contract_c11029194df3():
    'Technical support means this capability is not a new runtime prerequisite; Q1 determines whether and in what order to execute and provides no parallel permission Q1 maintainer schedule remains unresolved, no S2/parallel permission inferred'
    schedule_guard()


@pytest.mark.cer_assertion('ASSERT_8903766FC3B9')
def test_contract_8903766fc3b9():
    'Do not introduce a new whole-repository freeze only existing caller-owned result/memlog is changed; no new whole-repository freeze/control plane or modified formal source-freeze owner'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_8F38F3C92E38')
def test_contract_8f38f3c92e38():
    'Do not predefine new services, long-lived processes, databases, separate evaluation engines or new governance framework no daemon/database/new evaluation engine/governance framework'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_1CF333F248B4')
def test_contract_1cf333f248b4():
    'Trace current source, callers, tests and control contracts; regress existing behavior without fake RED; label out-of-Locator direct verification direct-source existing behavior regression no fakeRED, direct-source origin honest'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_02A80F5DFA2C')
def test_contract_02a80f5dfa2c():
    'Validate candidates only in isolated samples, keep stable toolchain hosting this requirement, obey self-hosted contract and do not modify frozen inputs stable host and original inputs unchanged, candidate only isolated self-hosted validation'
    stable_owner_guard()


@pytest.mark.cer_assertion('ASSERT_0505499A0382')
def test_contract_0505499a0382():
    'Current requirement uses fixed stable hosting toolchain; VDD self-changes follow self-hosted contract and candidate is only for isolated validation stable fixed host unchanged, isolated candidate samples only'
    stable_owner_guard()


@pytest.mark.cer_assertion('ASSERT_80CDBEFE451B')
def test_contract_80cdbefe451b():
    'Keep query switch independent and create no frozen knowledge, Skill-input attestation, authorization, review lineage or governance package query switch independent, no freeze/attestation/authorization/lineage/governance package'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_29E1D61C9DA3')
def test_contract_29e1d61c9da3():
    'Keep Locator the sole locating core; new code adds only shared adaptation and stage consumption, no index service/RAG/database or duplicate retrieval implementation only existing Locator retrieves; no duplicate retrieval/index/RAG/database'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_F8706C4018E8')
def test_contract_f8706c4018e8():
    'Existing ADR owner records adoption of ADR-0048 applicability increment before related implementation; spine must not fabricate Accepted status existing owner records actual adoption, spine recommendation not fabricated Accepted; absence blocks related implementation'
    adr_guard()


@pytest.mark.cer_assertion('ASSERT_B97840991292')
def test_contract_b97840991292():
    'Treat Locator as location information, not authoritative fact answers; adopted conclusions require reading valid sources and state impact/use, not completion proof actual valid read and use/impact recorded, query/adoption alone not completion proof'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_E805FAE00D8C')
def test_contract_e805fae00d8c():
    'Have the ADR owner record the applicability-scope increment before related implementation as specified in scope-and-decisions.md actual owner adoption record exists before production edits; architecture recommendation alone is not Accepted status; unresolved record blocks related implementation'
    adr_guard()


@pytest.mark.cer_assertion('ASSERT_C46BA64DF35B')
def test_contract_c46ba64df35b():
    'Preserve development/auto governance-off behavior resolver preserves explicit > environment > phase precedence; development auto is off; artifact diff shows no governance package synthesized by query'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_FEBAECE3EF68')
def test_contract_febaece3ef68():
    'Stage adapter depends on shared query which depends on existing core; query does not invoke publisher, governance authorization or other workflows stage->shared->existing core only, no publisher/authorization/otherworkflow call'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_0F3F35C7D966')
def test_contract_0f3f35c7d966():
    'Maintainer explicitly publishes through the existing process when a valid new generation is first needed; routine query never triggers publication no publication occurs; existing maintainer-owned process requires separate authorization for first generation'
    publication_guard()


@pytest.mark.cer_assertion('ASSERT_20B744439A62')
def test_contract_20b744439a62():
    'Plan regression verification for existing behavior; never use old paths or duplicate implementation merely to manufacture RED route retains regression/probe coverage; no obsolete path/missing import/duplicate code used to fabricate behavioral RED'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_D85FF56BA020')
def test_contract_d85ff56ba020():
    'Do not implement Package B, S1/S2 game business or sandbox refactoring in this round no PackageB, S1/S2 game business or sandbox refactoring work'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_F3CF264E79D0')
def test_contract_f3cf264e79d0():
    'Exclude automatic Bootstrap, general entrypoint skill, internal reviewer platform and slice parallel scheduling no automatic Bootstrap/general entrypoint/reviewer platform/slice scheduler'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_59D16A20F138')
def test_contract_59d16a20f138():
    'Continue existing hash verification; do not add whole-repository freeze for lightweight query; formal planning and acceptance retain their original binding contracts existing hashes remain checked, no whole-repository freeze added and plan/Acceptance binding unchanged'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_AB866697B090')
def test_contract_ab866697b090():
    'Do not claim examples, Windows verification or functional acceptance already ran merely because specified here only actual executed planning checks called complete; future consumer samples, Windows and functional Acceptance remain unexecuted until evidence'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_999DE5B58B6A')
def test_contract_999de5b58b6a():
    'Permit actual default query without creating frozen knowledge, Skill-input attestation, extra authorization, review lineage or the full governance artifacts query occurs without frozen knowledge, attestation, authorization, review lineage or governance package'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_AD2F023A4D8A')
def test_contract_ad2f023a4d8a():
    'Query and PRD internal review cannot replace existing formal Acceptance owner existing Acceptance owner alone decides completion, planning checks not substituted'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_FD4509758AAB')
def test_contract_fd4509758aab():
    'Preserve normative/provenance division, typed package and selection rules. owner validate_selection confirms role graph/current/record; no candidate query provenance becomes normative duty or changes selection'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_BAD87DEA440C')
def test_contract_bad87dea440c():
    'PRD-time references to this round and installation/cache/download/review are historical evidence, not product obligations or current permission not product duties or current authorization; current gates remain explicit'
    original_source_guard()


@pytest.mark.cer_assertion('ASSERT_9EF76B702BB8')
def test_contract_9ef76b702bb8():
    'Maintainer confirms S2 schedule before execution; technical non-dependency does not authorize parallel work or block current product planning S2 pending maintainer schedule, no inferred parallel work'
    schedule_guard()


@pytest.mark.cer_assertion('ASSERT_0E26CE73B585')
def test_contract_0e26ce73b585():
    'Do not replace downstream-required normative content with provenance-only inputs all mandatory downstream clauses remain canonical/normative/adopted, provenance supplies traceability only'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_C710C48E3CAC')
def test_contract_c710c48e3cac():
    'Continue through jimuyun SPEC/Architecture wrappers without restoring retired paths SPEC uses jimuyun-spec bridge then original native derive, Architecture uses jimuyun-architecture prepare and required reviewer lifecycle; retired GDS/quick-dev paths remain absent'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_CBF51EF51371')
def test_contract_cbf51ef51371():
    'Follow PRD then SPEC then Architecture then maintainer-explicit VDD then Quick Dev TDD then formal Acceptance with per-stage external review; subsequent stages require independent A/B and work-session agreement; historical pause does not reopen completed review external A/B plus work agreement before each next stage; historical pause does not reopen already completed gates'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_155F3E22923E')
def test_contract_155f3e22923e():
    'Use stable verified tooling to host current requirement, test candidates only in isolated samples and follow existing self-hosted rules without mid-task replacement stable verified host unchanged, candidate only isolated validation not self-host this requirement'
    stable_owner_guard()


@pytest.mark.cer_assertion('ASSERT_26F699ABA5E9')
def test_contract_26f699aba5e9():
    'Use fixed BMAD-METHOD 6.12.4 without claiming it is latest fixed6.12.4 original, not claimed latest'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_9D7F7CF7D1C0')
def test_contract_9d7f7cf7d1c0():
    'Treat PRD/original requirements as provenance, addendum and finalized architecture as adopted companions; consume AD-1 through AD-11 downstream and preserve adopted source bytes read-only provenance original/PRD and adopted addendum/architecture roles correct; all11AD consumed, adopted bytes unchanged'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_7FFACC7748F0')
def test_contract_7ffacc7748f0():
    'Complete formal Acceptance through the existing owner stage4 claims planning only and eventual formal Acceptance uses run-refactor-implementation-acceptance owner; no author self-check replaces required external review or Acceptance'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_349975159E12')
def test_contract_349975159e12():
    'PRD team hook, jimuyun-spec source reuse, jimuyun-architecture prepare and VDD public compiler depend on repository query adapter; adapter uses original TOML resolver, existing Locator/verified publication, bounded source reader and caller-owned memlog/execution record; VDD separately retains enabled governance gates; explicit maintainer publication feeds Locator; do not reverse these directions all stages depend on common adapter then native resolver/existing Locator/verified publication/bounded reader; caller owns records, VDD retains governance and publisher never called from query'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_FE2232D898AE')
def test_contract_fe2232d898ae():
    'Run only within existing local repository process/file boundaries; no new daemon, cloud provider, database, Phase API, credential or production deployment change existing local process/files only, no daemon/cloud/DB/Phase/credential/deployment change'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_A559CD58DB04')
def test_contract_a559cd58db04():
    'Use behavior-contracts.md formally refreshed candidate/output/call/timeout defaults, hard caps, accounting and terminal rules; numeric changes require SPEC owner refresh, not runtime expansion values/accounting/reserve match normative behavior-contracts; future numeric edit requires SPEC refresh'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_5C02BA0AA1E1')
def test_contract_5c02ba0aa1e1():
    'Do not add UI, market metrics or latency targets no UI/market metric/latency target'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_63748AAE8521')
def test_contract_63748aae8521():
    "Obtain maintainer confirmation of the specific S2 schedule before execution; technical non-dependency is not parallel permission and does not block this requirement's planning no S2 task or parallel execution inferred; Q1 remains maintainer-owned and does not block this planning scope"
    schedule_guard()


@pytest.mark.cer_assertion('ASSERT_CA2BCB3A2C9C')
def test_contract_ca2bcb3a2c9c():
    'Do not replace native BMAD 6.12.4, jimuyun-spec typed publication or jimuyun-architecture reviewer lifecycle; query records are not new authority 6.12.4 original/typed publication/reviewer lifecycle unchanged; query records no new authority'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_CACDDF9C9C16')
def test_contract_cacddf9c9c16():
    'SPEC owner fixes budgets through jimuyun-spec native derive/refresh; owner wording and numbers must converge before VDD; Architecture does not directly edit SPEC/selection and future changes cannot auto-expand at runtime SPEC owner native refresh only, no Architecture direct kernel/selection edit or runtime expansion'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_48CE539981D7')
def test_contract_48ce539981d7():
    'Exclude Codex kernel, context compaction, automatic new threads and app-server/SDK changes no Codex kernel/context compaction/new thread/appserver/SDK feature'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_27A22F872C63')
def test_contract_27a22f872c63():
    'Budget design creates no new governance switch, freeze or publication; unsuitable real-sample values require explicit return to SPEC owner for revision no governance/freeze/publication side effects or runtime widening; revision returns to SPEC owner refresh'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_A7CEB271CC36')
def test_contract_a7ceb271cc36():
    'Prefer team overrides and existing parsers; upgrade-overwritten native defaults must not be the sole persistent configuration team override survives supported install; native defaults not sole persisted config; original files unchanged'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_FAF1559ED039')
def test_contract_faf1559ed039():
    'Do not infer permission for immediate S2 execution, parallel implementation or changed schedule; Q1 requires maintainer confirmation no immediate/parallel S2 execution or changed schedule; maintainer confirmation remains pending'
    schedule_guard()


@pytest.mark.cer_assertion('ASSERT_B4AAE71E87A7')
def test_contract_b4aae71e87a7():
    'Maintain existing hash gates and do not introduce whole-repository freeze formal hash gates retained, no whole-repository freeze'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_C174B53AAD4B')
def test_contract_c174b53aad4b():
    'Use the architecturally reviewed conservative starting values fixed in behavior-contracts.md; future changes require owner refresh candidate/output/call/timeout defaults and caps match behavior-contracts; any future revision has formal SPEC owner refresh, not runtime widening'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_D8B2FD0C58CA')
def test_contract_d8b2fd0c58ca():
    'Exclude Phase API/accounts/production nodes/user sandbox/Hosted game features and S1/S2 game business or sandbox refactoring no Phase/accounts/production nodes/sandbox/Hosted/S1/S2 business changes'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_11076BE609FA')
def test_contract_11076be609fa():
    'Continue using jimuyun-spec canonical SPEC package, typed companion/provenance and external selection commitment; preserve typed roles, package integrity and selection rules canonical_package validate_selection verifies actual current/record and every source hash; no handwritten selection/kernel'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_25A45D343A1E')
def test_contract_25a45d343a1e():
    'Honor the remaining explicit exclusions in scope-and-decisions.md no PackageB, TC-D2/D4/D5/D6, sandbox/game/Phase/Hosted, general platform/RAG, automatic publication, reviewer/scheduler or history rewrite included'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_E50A12910925')
def test_contract_e50a12910925():
    'Do not interpret budget values as a performance SLA no measured SLA or latency promise inferred from conservative resource caps'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_3879A47B5106')
def test_contract_3879a47b5106():
    'Architecture defines actual diagnostics distinguishing these cases; model guesses and empty candidates cannot establish the cause mapping derives actual diagnostics, not model guess or [] alone; exact insufficient_match split and higher priorities preserved'
    legacy_guard()


@pytest.mark.cer_assertion('ASSERT_C624DEC0A9FE')
def test_contract_c624dec0a9fe():
    'Only new consumer interface returns planning-query.v1 diagnostics; never force new states on unmigrated callers planning-query.v1 only new interface, legacy state/exit fields unchanged'
    legacy_guard()


@pytest.mark.cer_assertion('ASSERT_7CB91BB2FA76')
def test_contract_7cb91bb2fa76():
    'Use the stable verified toolchain; validate future candidate query/VDD only in isolated samples without replacing the hosting toolchain or changing frozen inputs hosting compiler/QuickDev/Acceptance remain stable and input hashes unchanged; candidate tools run only in isolated validation and cannot host this requirement'
    stable_owner_guard()


@pytest.mark.cer_assertion('ASSERT_DE11C0FEE9B2')
def test_contract_de11c0fee9b2():
    'Do not change governance priority or development/auto default-off; query creates no freeze, extra authorization, attestation or review lineage default development/auto off and precedence unchanged; no freeze, authorization, attestation or lineage created by ordinary query'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_C2008D13B20C')
def test_contract_c2008d13b20c():
    'Set finite upper bounds for candidates, output and calls; Architecture proposes technical design and SPEC owner fixes values/accounting through native derive/refresh; subsequent changes remain SPEC-owner decisions without invented latency SLA finite candidate/output/call limits match normative owner; changes require native derive/refresh and no fabricated SLA'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_966987A5BADF')
def test_contract_966987a5badf():
    'Native BMAD consumes only externally supplied context and retains original bytes; formal governance, knowledge publication and Acceptance retain their respective owners native bytes unchanged, only external context; governance/publication/Acceptance remain original owners'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_370A27148C69')
def test_contract_370a27148c69():
    'Preserve existing fields, status meanings and exit semantics; do not delete, rename or reinterpret existing return values; do not force new finer states on unmigrated consumers fields/status meanings/exit codes equal; unmigrated consumers never see new planning-query outcomes'
    legacy_guard()


@pytest.mark.cer_assertion('ASSERT_BC840DFBB176')
def test_contract_bc840dfbb176():
    'Use official _bmad/custom/<skill>.toml and native resolver without modifying native customize.toml official _bmad/custom hooks only, native customize.toml/resolver unchanged'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_7BA160A9B5B5')
def test_contract_7ba160a9b5b5():
    'Use proposed scripts/toolchain/knowledge_query/ for shared read-only adapter with one diagnostic/state contract and knowledge/planning-query.toml for tracked team configuration single shared scripts/toolchain/knowledge_query adapter plus tracked knowledge/planning-query.toml, no duplicate state contract or premature implemented claim'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_F8B848EA6CBB')
def test_contract_f8b848ea6cbb():
    'Use behavior-contracts.md as the complete normative obligations for FR-01 through FR-10 corresponding to CAP-1 through CAP-10 all FR01-10 normative clauses retained with CAP mappings; kernel summary never substitutes for detailed behavior-contracts'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_B0E4247583D1')
def test_contract_b0e4247583d1():
    'Follow the approved single-maintainer internal capability model without inventing UI, market metrics or latency targets single maintainer internal tooling only; no UI, market metric or latency targets introduced'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_2F2D26DDB39F')
def test_contract_2f2d26ddb39f():
    'Follow existing mandatory governance repair contracts without using lightweight query as a bypass existing owner repair contract enforced; lightweight query cannot waive mandatory action'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_05FD661FC842')
def test_contract_05fd661fc842():
    'Require explicit maintainer authorization after merge for first publication no publish action; future first generation requires separate explicit owner authorization after main merge'
    publication_guard()


@pytest.mark.cer_assertion('ASSERT_1A430B96D85A')
def test_contract_1a430b96d85a():
    'Do not claim completion from configuration text alone completion rejected until real trigger/query/read/adoption and required verification exist'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_493AA5C5D9AA')
def test_contract_493aa5c5d9aa():
    'Use Locator only to narrow search scope, not replace call-chain verification actual current caller/code/test/control references required; index location alone cannot prove implementation or dependency completeness'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_79D48DB540E2')
def test_contract_79d48db540e2():
    'Place native PRD hook externally in _bmad/custom/bmad-prd.toml with original skill untouched; retain .agents/skills/jimuyun-spec/ typed owner for necessary supplement only and .agents/skills/jimuyun-architecture/ native invocation boundary external _bmad/custom/bmad-prd.toml only, unchanged native; SPEC typed owner and Architecture native boundary retained'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_8B96BF63114D')
def test_contract_8b96bf63114d():
    'Maintainer decides S2 timing before S2 work; technical non-dependency grants no parallel right maintainer decides before S2, no parallel permission'
    schedule_guard()


@pytest.mark.cer_assertion('ASSERT_99F96E43AB70')
def test_contract_99f96e43ab70():
    'Keep native BMAD 6.12.4 unchanged and place new customization externally native verify succeeds with identical original bytes; custom hook resides outside native tree and no python3-to-py patch exists'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_C3348AF86BDA')
def test_contract_c3348af86bda():
    'Retain required modules, freezing, source integrity and authorization checks; lightweight outcome cannot satisfy or replace them formal gate remains blocking despite lightweight outcome'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_A63BCAFECC82')
def test_contract_a63bcafecc82():
    'Continue mandatory validation, freezing and authorization; required-module or integrity failures block formal validation/freeze/authorization still block; no query substitute'
    governance_guard()


@pytest.mark.cer_assertion('ASSERT_45F233F69106')
def test_contract_45f233f69106():
    'Read behavior-contracts.md for all FR obligations, failure-modes.md for failure priority and acceptance.md for AC-01 through AC-14 all10FR behavior clauses, failure ordering and14AC are read from complete normative companions rather than kernel-only intake; adopted architecture11AD retained'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_BA91C94355C2')
def test_contract_ba91c94355c2():
    'Use failure-modes.md for FR-07 decision order without replacing existing contracts when governance is enabled full failure-mode order applied without substituting lightweight diagnostic for required formal gate'
    legacy_guard()


@pytest.mark.cer_assertion('ASSERT_D4DA2D8966A8')
def test_contract_d4da2d8966a8():
    'Exclude new knowledge platform, vector database, general RAG, Memory/Miner, whole-repository index rebuild and mandatory full publication no new knowledge platform/vector DB/RAG/Memory/Miner/index rebuild/full publication mandate'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_DD430724E6FF')
def test_contract_dd430724e6ff():
    'Preserve original scope-binding constraints on formal plan validity formal owner still rejects validity; query cache does not waive scope/source binding'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_13CE2513BEF1')
def test_contract_13ce2513bef1():
    'Require independent A/B review and work-session agreement per stage; historical stage-3 pending text does not reopen completed reviews or authorize future stages or parallel work each transition has external A/B GO and work-session agreement; no reuse of historical phase3 pending text to reopen closed gate or authorize future stage/S2 parallelism'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_A7F119F56C39')
def test_contract_a7f119f56c39():
    "Exclude full standard migration of Package B's five skills, redoing 8-05/8-06/7-31, and TC-D2/D4/D5/D6 no PackageB five-skill migration, redo8-05/8-06/7-31 or TC-D2/D4/D5/D6"
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_AC8D10DEA116')
def test_contract_ac8d10dea116():
    'Place this requirement after Package A and before Package B; new requirements adopt the capability only after acceptance and merge to main; Package B actual-difference migration and subsequent 7-31 are later arrangements, not current work after PackageA beforeB; new requirements only after acceptance/main merge; PackageB/7-31 remain later excluded arrangements'
    schedule_guard()


@pytest.mark.cer_assertion('ASSERT_D1D454E5D9F2')
def test_contract_d1d454e5d9f2():
    'Do not hand-edit generated projections, forge publication records or enable debug options that skip publication/freshness checks no generated projection edit, forged generation or allow-unpublished/allow-stale/noncanonical catalog bypass'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_2DAB31E5B3B7')
def test_contract_2dab31e5b3b7():
    'Downstream obligations must enter normative content or applicable typed companions; valid selection cannot substitute for body completeness every downstream duty present in normative/adopted content; valid selection alone not completeness'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_6A927E42C816')
def test_contract_6a927e42c816():
    'Exclude Package B full migration, redoing existing stages, TC-D2/D4/D5/D6, S1/S2 game business and sandbox refactoring no Package B full migration, stage redo, TC-D2/D4/D5/D6, S1/S2 game or sandbox tasks'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_81030489D3CB')
def test_contract_81030489d3cb():
    'Keep original Locator return fields/status and old-consumer semantics unchanged; this rule specifies future adapter behavior and does not prove implementation already exists fields/status/exit/old consumers unchanged; planned adapter not reported already implemented'
    legacy_guard()


@pytest.mark.cer_assertion('ASSERT_542A00BA0AD5')
def test_contract_542a00ba0ad5():
    'Exclude automatic publication, automatic Bootstrap/general entrypoint/internal reviewer platform/slice parallel scheduling, historical evidence rewriting and query results as completion authority no publication/Bootstrap/general entrypoint/reviewer platform/parallel scheduler; no historical rewrite; query never authorizes completion'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_D5C9FCC32C39')
def test_contract_d5c9fcc32c39():
    'Maintainer separately authorizes initial knowledge publication after implementation verification and main merge; this planning stage does not publish planning does not publish; later separate maintainer authorization only after verification/main merge'
    publication_guard()


@pytest.mark.cer_assertion('ASSERT_69EDF6ED6888')
def test_contract_69edf6ed6888():
    'Use repository-owned stage integrations depending on a shared read-only query adapter that depends on existing Locator core, configuration resolution and source readers stage -> shared readonly adapter -> existing Locator/config/reader; no replacement platform or publisher dependency'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_E9074C067973')
def test_contract_e9074c067973():
    'Require independent Work A/B review and work-session agreement for each sequential stage; push/PR only after all work completes; PRD-time pause is historical and does not reset completed gates sequential gates remain required; no implementation/Acceptance/push before their actual gate; PRD historical pause cannot reset already completed gates'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_455649B5C62A')
def test_contract_455649b5c62a():
    'Do not treat PRD internal checks as satisfying future feature implementation AC PRD checks never marked implementation AC passed'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_725D2792FC8F')
def test_contract_725d2792fc8f():
    'Use latest owners rather than old requirement paths; retain external customization and unchanged official BMAD; do not infer small wrapper installer contains PRD or restore retired stock quick-dev/GDS paths current external wrappers/native6.12.4 unchanged; small wrapper installer not called PRD install; retired paths absent'
    native_guard()


@pytest.mark.cer_assertion('ASSERT_BCC9695149FF')
def test_contract_bcc9695149ff():
    'Exclude Phase services, Hosted isolation, accounts/production nodes, game business, Package B and whole-repository index/RAG; none becomes implicit deployment work no Phase/Hosted/accounts/production/game/PackageB/index/RAG work implied'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_17CD3FC9ABEA')
def test_contract_17cd3fc9abea():
    'Treat SPEC and its companions as the complete behavior contract; normative duties must not require rereading provenance. every planned obligation maps to seven complete canonical/normative/adopted sources; removing provenance leaves all mandatory behavior available; original role/hash and selection remain exact'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_5777409A39C1')
def test_contract_5777409a39c1():
    'Architecture and maintainer determine Accepted ADR applicability increment, explicit first-generation publication steps and Windows environment/samples before affected implementation/rollout; no automatic publication or silent formal-governance weakening ADR applicability owner record, explicit later first-publication sequence and real Windows environment/sample arrangement required before affected work; unresolved owner prerequisite remains blocking, never fabricated'
    adr_guard()


@pytest.mark.cer_assertion('ASSERT_2687DDBEA58E')
def test_contract_2687ddbea58e():
    'Preserve original section 7 without byte edits whole original source SHA256 ce45693489d02227442c04c9b4e7220121a897d81dab03abc7867e6ceff11950 unchanged including section7'
    original_source_guard()


@pytest.mark.cer_assertion('ASSERT_59F8C120CE6F')
def test_contract_59f8c120ce6f():
    'Reuse approved unchanged inputs without mechanically repeating PRD lookup; historical reuse text is not evidence of new implementation or Locator execution no mechanical repeat or fabricated new Locator execution/implementation from historical reuse text'
    original_source_guard()


@pytest.mark.cer_assertion('ASSERT_2921ABE187A0')
def test_contract_2921abe187a0():
    'Use sources only for traceability, without promoting them to independent mandatory requirements. source-map and generated obligations never promote source-only statements into duties; current pointer/record remains owner-validated'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_72AB405FF8A5')
def test_contract_72ab405ff8a5():
    'Interpret PRD execution records as historical state, not permission for a new stage. no historical completed flag is consumed as current authorization; current phase remains subject to explicit external A/B gate; no S2 scheduling or implementation authorization inferred'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_B4C8A4D06236')
def test_contract_b4c8a4d06236():
    'Do not rewrite historical plans, evidence or generations original bytes unchanged, failed/cancel records retained'
    original_source_guard()


@pytest.mark.cer_assertion('ASSERT_4C2F3548DB28')
def test_contract_4c2f3548db28():
    'Architecture proposes an explicit applicability-scope increment when coordination is needed; do not silently weaken formal mode explicit owner adoption precedes affected implementation; no silently weakened formal mode or fabricated Accepted status'
    adr_guard()


@pytest.mark.cer_assertion('ASSERT_C82CF2422089')
def test_contract_c82cf2422089():
    'Preserve formal governance and typed SPEC/VDD/Quick Dev/Acceptance contracts; define result compatibility strategy before implementation new planning-query.v1 isolated from legacy Locator status/exit; original governance/SPEC/VDD/QuickDev/Acceptance contracts remain'
    legacy_guard()


@pytest.mark.cer_assertion('ASSERT_1FBF989D87FE')
def test_contract_1fbf989d87fe():
    'Do not equate static existence with actual run verification or historical directories/status markers with delivered implementation; treat new consumer wiring, first publication generation and Windows effects as requiring actual verification static/history not real run proof; new wiring/generation/Windows require actual respective evidence'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_0393FA36BBE5')
def test_contract_0393fa36bbe5():
    'Fixtures prove only deterministic branches; formal completion remains Acceptance owner and architecture-stage specification does not mean future capability ran fixtures prove branches only, architecture not executed capability, Acceptance owner remains'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_67E63C3F227A')
def test_contract_67e63c3f227a():
    'Record ADR-0048 scope increment separating ordinary readonly planning advice from formal gates before implementation; preserve ADR-0044/0050/0057/0059 permission, publication and self-change rules actual adopted applicability increment separates advice/formal gate while preserving ADR44/50/57/59; no fabricated acceptance or silent weakening'
    adr_guard()


@pytest.mark.cer_assertion('ASSERT_8BF65710077E')
def test_contract_8bf65710077e():
    'Implementation may choose internal split/test filenames based on existing organization but must not create a second validation/diagnostic semantics filenames may vary under declared write scope, no second diagnostic/validation semantics'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_D5BE6F9B0842')
def test_contract_d5be6f9b0842():
    'Treat defaults as conservative engineering values, not measured performance SLA; revise through owner explicitly rather than silently widening conservative not measured SLA, unsuitable samples return owner refresh, no silent widening'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_ED8CDEBD1170')
def test_contract_ed8cdebd1170():
    'Do not borrow another consumer identity, hand-edit generated projections or bypass publication/freshness checks; preserve formal owners, typed roles, selection, source hashes and Acceptance authority no borrowed consumer or hand-edited generated projection, no bypass flags, owner/hash/selection preserved; query result remains advisory'
    dependency_guard()


@pytest.mark.cer_assertion('ASSERT_4B9C0852F067')
def test_contract_4b9c0852f067():
    'Treat query result as advice; record native caller read/use decision separately; preserve SPEC normative/provenance roles and selection advisory separate from native read/use, normative/provenance roles and selection unchanged'
    package_guard()


@pytest.mark.cer_assertion('ASSERT_D3207953C3F7')
def test_contract_d3207953c3f7():
    'Use these as consumer decision categories under CAP-7/FR-07, not claims that current CLI has those status fields; do not introduce a new public Locator schema legacy callers retain vocabulary; planning-query.v1 only new consumer-facing interface, no claim those are existing Locator status fields'
    legacy_guard()


@pytest.mark.cer_assertion('ASSERT_8E9A6B056EA1')
def test_contract_8e9a6b056ea1():
    'Historical plans, checkmarks and reports cannot alone prove implementation complete cannot label implemented/complete; require real current source/call/test and formal owner evidence'
    authority_guard()


@pytest.mark.cer_assertion('ASSERT_A8145B6CF565')
def test_contract_a8145b6cf565():
    'Exclude new knowledge platform, general RAG/vector store, whole-repository index rebuild, Codex kernel/app-server/SDK and Phase/Hosted feature changes no new knowledge platform/general RAG/vector store/index rebuild/Codex internals/Phase Hosted features; reuse existing Locator'
    scope_guard()


@pytest.mark.cer_assertion('ASSERT_7A2E25478BB9')
def test_contract_7a2e25478bb9():
    'Read adopted architecture for identity/policy, external integration, interface representation and records; use behavior-contracts.md for normative budgets choices match adopted AD1-11 and normative behavior-contracts budget values rather than reopening Q2/Q3'
    budget_guard()


@pytest.mark.cer_assertion('ASSERT_A6DEA3F8BB0A')
def test_contract_a6dea3f8bb0a():
    'Regress existing behavior without fake RED or duplicate implementation and without requiring rerun of all historical requirements retain current regression coverage, no obsolete/fake RED/duplicate work or all-history rerun'
    authority_guard()
