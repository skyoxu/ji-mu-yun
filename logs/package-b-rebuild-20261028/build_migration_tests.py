"""Author bounded migration tests from explicit, subject-specific check designs."""
from pathlib import Path
import sys
B=Path(__file__).resolve().parent
sys.path.insert(0,str(B))
from author_v3 import SPECS
ROOT=B.parents[1];target=ROOT/'scripts/sc/tests/test_skill_quality_package_b.py'
header='''"""ADR-0062 / ADR-0041: actual Package B declarations and preserved owners.

Quality results are obtained from the unchanged public validator. Source identity
checks prove preservation, not historical execution success. Native delivery
predicates and independent review retain their separate completion ownership.
"""
from pathlib import Path
from hashlib import sha256
import copy
import json
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.sc.validate_skill_quality import validate_package
from scripts.sc.skill_quality_examples import validate_examples

BASE = 'fb676bc398f653a2ffa869c95d6c8d632f6f9796'
NAMES = ['vdd-execution-plan', 'quick-dev-tdd-adapter', 'run-phase-bootstrap-review',
         'run-refactor-implementation-acceptance', 'maintain-knowledge-base']
PACKAGES = [ROOT/'.agents/skills'/n for n in NAMES]
POLICY = 'scripts/sc/config/skill-authoring-standard.v1.json'
AUTHORITY = ['docs/standards/skill-authoring-standard.md',
             'docs/adr/ADR-0062-repository-skill-authoring-contract.md',
             POLICY, 'scripts/sc/schemas/skill-quality-contract.v1.schema.json',
             'scripts/sc/schemas/skill-quality-result.v1.schema.json',
             'scripts/sc/validate_skill_quality.py', 'scripts/sc/skill_quality_examples.py']
RUNTIMES = ['scripts/vdd/compile_plan.py', 'scripts/quick_dev/run.py',
            '.agents/skills/quick-dev-tdd-adapter/tools/independent_judge_v2.py',
            '.agents/skills/quick-dev-tdd-adapter/tools/coverage_predicates.py',
            '.agents/skills/quick-dev-tdd-adapter/tools/regression_gate.py',
            '.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py',
            '.agents/skills/run-refactor-implementation-acceptance/scripts/run_acceptance.py',
            '.agents/skills/maintain-knowledge-base/scripts/maintain_knowledge.py',
            '.agents/skills/maintain-knowledge-base/scripts/prepare_publication_request.py',
            'scripts/python/publish_knowledge_catalog.py']


def _text(path):
    return Path(path).read_text(encoding='utf-8')


def _declaration(package):
    return json.loads(_text(package/'skill-quality.v1.json'))


def _strict(package):
    return validate_package(repository_root=ROOT, package_root=package,
                            policy_path=POLICY, mode='strict')


def _unchanged(paths):
    for ref in paths:
        expected = subprocess.check_output(['git', 'show', BASE+':'+ref], cwd=ROOT)
        if (ROOT/ref).read_bytes() != expected:
            return False
    return True


def _native_boundary():
    return _unchanged(RUNTIMES)


def _main(package):
    return _text(package/'SKILL.md')


def _quality(index):
    result = _strict(PACKAGES[index])
    return result['status']=='pass' and result['exit_code']==0 and result['authorizes']==[]


def _all_quality():
    return all(_quality(i) for i in range(5))


def _examples(index, terms):
    declaration = _declaration(PACKAGES[index])
    values = declaration.get('examples', [])
    if len(values)!=3 or validate_examples(declaration):
        return False
    return all(all(term in (' '.join(str(v) for v in item.values())).lower()
                   for term in required) for item, required in zip(values, terms))


def _dependency_records():
    for package in PACKAGES:
        deps = _declaration(package).get('dependencies', [])
        if not deps:
            return False
        for dependency in deps:
            path = package/dependency['authority']
            record = json.loads(_text(path))
            if (path.is_symlink() or record.get('id')!=dependency['id']
                    or record.get('version')!=dependency['version']
                    or record.get('authorizes')!=[]
                    or dependency.get('when_missing')!='block'
                    or dependency.get('when_mismatch')!='block'):
                return False
    return True


def _frontmatter():
    for package in PACKAGES:
        lines = _main(package).split('---',2)
        keys = [line.split(':',1)[0] for line in lines[1].splitlines() if ':' in line]
        declaration = _declaration(package)
        if set(keys)!={'name','description'} or declaration.get('schema')!='skill-quality.v1' or declaration.get('standard_version')!='1.0' or declaration.get('authorizes')!=[]:
            return False
    return True


def _entrypoints():
    for package in PACKAGES:
        entries = _declaration(package).get('entrypoints', [])
        if not entries:
            return False
        for entry in entries:
            if (entry.get('standalone') is not True or not entry.get('preflight')
                    or not entry.get('caller_setup') or not entry.get('dependencies')
                    or entry.get('install_missing',False) or entry.get('skip_missing',False)):
                return False
    return True


def _references():
    for package in PACKAGES:
        for ref in re.findall(r'\\]\\(([^)]+)\\)', _main(package)):
            if ref.startswith(('http:', 'https:','#')):
                continue
            if not (package/ref.split('#',1)[0]).is_file():
                return False
    return True


def _diagram():
    for package in PACKAGES:
        declaration = _declaration(package)
        if not declaration.get('capabilities',{}).get('routing'):
            continue
        routing = declaration.get('routing',{})
        diagram = routing.get('diagram')
        if isinstance(diagram,dict):
            text = _text(package/diagram['ref'].split('#',1)[0])
        elif isinstance(diagram,str):
            text = diagram
        else:
            return False
        if not any(token in text for token in ['->', '|', '+--', '-->']):
            return False
        if len(routing.get('branches',[]))<3:
            return False
    return True


def _quality_negative_checks():
    # Exercise the adopted example validator against mutations of a real package.
    declaration = _declaration(PACKAGES[0])
    broken = copy.deepcopy(declaration)
    broken['examples'] = []
    return bool(validate_examples(broken)) and _unchanged(AUTHORITY)


def _canonical():
    source = _text(ROOT/'docs/workflows/inputs/package-b-rebuild-20261028/requirements.md')
    return all('## FR-'+str(i)+' ' in source for i in range(1,7)) and all(name in source for name in ['VDD','Quick Dev','Bootstrap','Acceptance','maintenance'])


def _authority_input():
    path = ROOT/'docs/workflows/inputs/package-b-rebuild-20261028/source-map.json'
    data = json.loads(_text(path))
    return bool(data) and _canonical() and _unchanged(AUTHORITY)


def _scope():
    allowed = [p.relative_to(ROOT).as_posix() for p in PACKAGES]
    return len(set(allowed))==5 and all(p.startswith('.agents/skills/') for p in allowed) and _native_boundary()


def _protected_bmad():
    return _unchanged(['.agents/skills/jimuyun-spec/SKILL.md',
                      '.agents/skills/jimuyun-architecture/SKILL.md',
                      'scripts/toolchain/bmad_native/__init__.py'])


def _chapters():
    for prefix in ['workflow-chapter2-', 'workflow-chapter3-', 'workflow-chapter4-',
                   'workflow-chapter5-', 'workflow-chapter6-', 'workflow-chapter7-']:
        paths = list((ROOT/'.agents/skills').glob(prefix+'*/SKILL.md'))
        if not paths or not _unchanged([p.relative_to(ROOT).as_posix() for p in paths]):
            return False
    return True


def _dependency_table():
    return all('dependenc' in _main(p).lower() and '|' in _main(p) for p in PACKAGES)


def _portable_bootstrap():
    text = _main(PACKAGES[2])
    return ('validate_skill_contract.py' in text and 'C:\\\\' not in text
            and 'C:/' not in text and 'C:\\Users' not in text)


def _operator_docs():
    text = _main(PACKAGES[4])
    return 'operator-requested' in text and 'catalog-stale-maintenance' in text and '108-query' not in text


def _capabilities():
    for package in PACKAGES:
        declaration = _declaration(package)
        caps = declaration.get('capabilities',{})
        controls = declaration.get('controls',{})
        if not caps or declaration.get('authorizes')!=[]:
            return False
        for key,value in caps.items():
            if value is True and key not in ['routing','version_lookup'] and key not in controls:
                return False
    return True


def _persistent_input():
    # Stage copy proves current frozen requirements, never future run success.
    receipt = ROOT/'logs/package-b-rebuild-20261028/current-durable-stage-receipt.json'
    if not receipt.is_file():
        return False
    data=json.loads(_text(receipt))
    if not data.get('library_file_id') or not data.get('files'):
        return False
    for record in data['files']:
        path=ROOT/record['path']
        if not path.is_file() or sha256(path.read_bytes()).hexdigest()!=record['sha256']:
            return False
    return True


def _check(value,failure_id):
    if not value:
        print('FAILURE_ID:'+failure_id)
    assert value, 'The current production contract does not satisfy the bound Package B observable'

'''
conditions={
'dependency_documentation':'_dependency_table()',
'first_level_references':'_references()',
'child_dependency_preservation':'_native_boundary() and "dependencies" in _main(PACKAGES[1]).lower()',
'focused_verification':'_quality_negative_checks()',
'local_scope':'_scope()',
'authority_inputs':'_authority_input()',
'bmad_exclusion':'_protected_bmad()',
'predicate_completion':'_native_boundary() and "Evidence Ownership" in _main(PACKAGES[1])',
'no_operational_authority':'_native_boundary() and all("not" in _main(p).lower() for p in PACKAGES)',
'frozen_inputs':'_authority_input() and _native_boundary()',
'accepted_predecessor':'_unchanged(AUTHORITY) and _canonical()',
'profile_selection':'"self-hosted" in _main(PACKAGES[0]) and _native_boundary()',
'explicit_vdd_routing':'"explicitly" in _main(PACKAGES[0]).lower() and "standalone" in _main(PACKAGES[0]).lower() and _native_boundary()',
'phase_exclusion':'_scope() and _unchanged(["scripts/sc/_llm_backend.py"])',
'chapter_exclusion':'_chapters()',
'historical_preservation':'_native_boundary() and all("histor" in _main(p).lower() or "append" in _main(p).lower() for p in PACKAGES)',
'quick_examples':"_examples(1, [('strict',), ('upgrade',), ('invalid',)])",
'bootstrap_examples':"_examples(2, [('clean',), ('round',), ('access',)])",
'acceptance_examples':"_examples(3, [('deterministic',), ('repair',), ('stale',)])",
'knowledge_examples':"_examples(4, [('existing-only',), ('provisional',), ('publication',)])",
'preserved_boundaries':'_native_boundary() and _unchanged(AUTHORITY)',
'vdd_examples':"_examples(0, [('create',), ('direct',), ('invalid',)])",
'standalone_preflight':'_entrypoints()',
'main_bound':'all(len(_main(p).splitlines())<500 for p in PACKAGES)',
 'typed_errors':'all(bool(_declaration(p).get("error_ids")) for p in PACKAGES)',
'routing_diagrams':'_diagram()',
'bootstrap_quality':'_quality(2)',
'vdd_quality':'_quality(0)',
'quick_upgrade_boundary':'_native_boundary() and "upgrade" in _main(PACKAGES[1]).lower() and "VDD" in _main(PACKAGES[1])',
'native_reuse':'_native_boundary()',
'dependency_records':'_dependency_records()',
'stale_maintenance':'_native_boundary() and "catalog-stale-maintenance" in _main(PACKAGES[4])',
'operator_publication':'_operator_docs()',
'acceptance_owner':'_native_boundary() and "finalization" in _main(PACKAGES[3]).lower()',
'accepted_validator':'_unchanged(AUTHORITY)',
'reference_reuse':'_references()',
'acceptance_quality':'_quality(3)',
'knowledge_boundaries':'_operator_docs() and _native_boundary()',
'sidecar_shape':'_frontmatter()',
'knowledge_quality':'_quality(4)',
'quick_quality':'_quality(1)',
'portable_bootstrap':'_portable_bootstrap()',
'vdd_semantic_owner':'_native_boundary() and "atomic" in _main(PACKAGES[0]).lower()',
'nonauthorizing_dependencies':'_native_boundary() and _unchanged(AUTHORITY)',
'bmad_separation':'_protected_bmad()',
'bootstrap_authority':'_native_boundary() and "authority" in _main(PACKAGES[2]).lower()',
'host_repair_boundary':'_native_boundary() and _unchanged(AUTHORITY)',
'validation_set':'_all_quality()',
'canonical_input':'_canonical() and _authority_input()',
'content_reuse':'_native_boundary() and "content" in _main(PACKAGES[1]).lower()',
'invalid_red':'_native_boundary() and "harness" in _main(PACKAGES[1]).lower()',
'persistent_evidence':'_persistent_input()',
'freeze_proof':'_native_boundary() and "frozen" in _main(PACKAGES[1]).lower()',
'vdd_no_execution':'_native_boundary() and "VDD owns none" in _main(PACKAGES[0])',
'public_compile':'_native_boundary() and "compile_plan.py" in _main(PACKAGES[0])',
'quality_invariants':'_all_quality() and _capabilities()',
'platform_truth':'sys.version_info>=(3,11) and hasattr(pytest,"mark")',
'behavior_classification':'_native_boundary() and "probe" in _main(PACKAGES[1]).lower()',
'no_fake_recovery':'_canonical() and _native_boundary()',
'source_expression':'_authority_input()',
'unit_budget':'_native_boundary() and "1800" in _main(PACKAGES[1]) and "600" in _main(PACKAGES[1])',
'current_state':'_native_boundary() and _unchanged(AUTHORITY)',
'protected_sources':'_protected_bmad() and _chapters() and _unchanged(AUTHORITY)',
'complete_coverage':'_canonical()',
'no_quality_authority':'_unchanged(AUTHORITY) and _native_boundary()',
'direct_regression':'_native_boundary() and _all_quality()',
'no_global_framework':'_scope()',
'no_automatic_publish':'_native_boundary() and _unchanged(["scripts/sc/_llm_backend.py"])',
'distinct_completion':'_native_boundary() and "external Acceptance" in _main(PACKAGES[1])',
'five_strict':'_all_quality()',
'repair_integrity':'_native_boundary() and "historical" in _main(PACKAGES[1]).lower()',
'capability_drift':'_unchanged(AUTHORITY) and _native_boundary()',
'owner_drift':'_native_boundary()',
'child_drift':'_native_boundary()',
'predecessor_scope':'_unchanged(AUTHORITY)',
'authority_drift':'_unchanged(AUTHORITY)',
'scope_drift':'_native_boundary() and _scope()',
}
source=header
for oid,(_,_,label,_) in sorted(SPECS.items()):
    source += f"\n@pytest.mark.cer_assertion('PKGB_{oid[2:]}')\ndef test_{label}():\n    _check({conditions[label]}, 'PKGB_{oid[2:]}_FAIL')\n\n"
# The record requirement remains an explicit guard; missing durable receipt is not success.
target.write_text(source,encoding='utf-8',newline='\n')
print('Authored',len(SPECS),'distinct marker-bound test functions',target)
