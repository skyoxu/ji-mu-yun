"""ADR-0062: current declarations remain strict and non-authorizing."""
import json
from pathlib import Path
import sys
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.sc.validate_skill_quality import validate_package

@pytest.mark.parametrize('name', ['vdd-execution-plan', 'quick-dev-tdd-adapter'])
def test_current_toolchain_package_keeps_the_adopted_quality_contract(name):
    package = ROOT / '.agents/skills' / name
    result = validate_package(repository_root=ROOT, package_root=package,
        policy_path='scripts/sc/config/skill-authoring-standard.v1.json', mode='strict')
    assert result['status'] == 'pass' and result['exit_code'] == 0
    assert result['authorizes'] == []
    declaration = json.loads((package / 'skill-quality.v1.json').read_text())
    assert declaration['authorizes'] == [] and declaration['schema'] == 'skill-quality.v1'
    assert declaration['dependencies'] and all(d['when_missing'] == d['when_mismatch'] == 'block'
                                            for d in declaration['dependencies'])


# These observables are the still-current parts of mixed Package B assertions.
# The original 77 functions remain unchanged and also run on their published tree.
from scripts.sc.tests import test_skill_quality_package_b as package_b

CURRENT_TERMS = [
    (1, ('content',)), (1, ('harness',)), (1, ('upgrade', 'VDD')),
    (4, ('catalog-stale-maintenance',)), (1, ('Evidence Ownership',)),
    (1, ('frozen',)), (3, ('finalization',)), (0, ('VDD owns none',)),
    (0, ('compile_plan.py',)), (0, ('self-hosted',)), (0, ('explicitly', 'standalone')),
    (1, ('probe',)), (1, ('historical',)), (1, ('external Acceptance',)),
    (1, ('1800', '600')), (2, ('authority',)),
]

@pytest.mark.parametrize('index,terms', CURRENT_TERMS)
def test_current_mixed_package_b_instructions(index, terms):
    text = package_b._main(package_b.PACKAGES[index])
    assert all(term.lower() in text.lower() for term in terms)


def test_current_mixed_package_b_separate_non_authorizing_owners():
    assert package_b._unchanged(package_b.AUTHORITY)
    assert package_b._canonical() and package_b._authority_input()
    assert package_b._operator_docs()
    assert package_b._unchanged(['scripts/sc/_llm_backend.py'])
    for package in package_b.PACKAGES:
        text = package_b._main(package).lower()
        assert 'not' in text
        assert 'histor' in text or 'append' in text
    context = package_b._intent_file('agent-context/S1/agent-context.json')
    for name in ('test_validate_skill_contract.py', 'test_skill_contract.py',
                 'test_direct_script_startup.py', 'test_package.py', 'test_prepare_publication_request.py'):
        assert any(name in arg for command in context['validation_commands'] for arg in command)


def test_current_package_b_frozen_scope_and_atomic_sources():
    # Frozen plan data must remain internally complete; it grants no new writes.
    roots = [p.relative_to(ROOT).as_posix() for p in package_b.PACKAGES]
    selected = package_b._slice_intent()
    owned = lambda ref: any(ref.startswith(root + '/') for root in roots)
    assert len(set(roots)) == 5 and selected['production_owners']
    assert all(owned(ref) and ref in selected['allowed_write_paths']
               for ref in selected['production_owners'])
    assert all(owned(ref) or ref == 'scripts/sc/tests/test_skill_quality_package_b.py'
               for ref in selected['allowed_write_paths'])
    active = {v['obligation_id']: v for v in package_b._intent_file('obligations.v1.json')
              if v['status'] == 'active'}
    failures = {v['failure_intent_id']: v for v in package_b._intent_file('failure-intents.v1.json')}
    covered = set()
    for acceptance in package_b._intent_file('acceptances.v1.json'):
        ids = acceptance['obligation_ids']
        assert len(ids) == 1 and ids[0] in active and ids[0] not in covered
        covered.add(ids[0])
        assert acceptance['assertion_ids'] and acceptance['oracle']['expected'] and acceptance['red_intent_ids']
        assert set(acceptance['source_refs']).issubset(active[ids[0]]['source_refs'])
        assert all(acceptance['acceptance_id'] in failures[fid]['acceptance_ids']
                   for fid in acceptance['red_intent_ids'])
    assert covered == set(active)


def test_package_b_current_mapping_keeps_every_original_case_and_executable_witness():
    import ast
    mapping = json.loads((ROOT / '.agents/skill-baselines/package-b-current-coverage.v1.json').read_text())
    original = ast.parse((ROOT / 'scripts/sc/tests/test_skill_quality_package_b.py').read_text())
    names = {n.name for n in original.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')}
    rows = mapping['cases']
    assert len(rows) == len(names) == 77 and {r['original_case'] for r in rows} == names
    policy = json.loads((ROOT / '.agents/skill-baselines/policy.v1.json').read_text())
    suites = {t for skill in policy['skills'].values() for t in skill['suites']}
    live = [r for r in rows if r['classification'] == 'current-unmodified']
    assert len(live) == 39
    for row in rows:
        assert row['original_expression'] and row['reason']
        for target in row['current_tests']:
            path, name = target.split('::')
            assert path in suites or target in suites
            parsed = ast.parse((ROOT / path).read_text())
            assert name in {n.name for n in parsed.body if isinstance(n, ast.FunctionDef)}
        if row['classification'] != 'current-unmodified':
            assert any('/tools/tests/' in t or '/scripts/tests/' in t for t in row['current_tests'])
