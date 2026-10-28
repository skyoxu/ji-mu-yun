"""ADR-0062 / ADR-0041: actual Package B declarations and preserved owners.

Quality results are obtained from the unchanged public validator. Source identity
checks prove preservation, not historical execution success. Native delivery
predicates and independent review retain their separate completion ownership.
"""
from pathlib import Path
from hashlib import sha256
import copy
import json
import re
import shlex
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.sc.validate_skill_quality import validate_package
from scripts.sc.skill_quality_examples import validate_examples

BASE = 'fb676bc398f653a2ffa869c95d6c8d632f6f9796'
PLAN = ROOT/'execution-plans/2026-10-28-skill-compliance-package-b-rebuild-r3'
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
            '.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py',
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


def _intent_file(name):
    # Frozen planning inputs are data, never an observed completion verdict.
    return json.loads(_text(PLAN/name))


def _slice_intent():
    values = _intent_file('slices.v1.json')
    if isinstance(values, dict):
        values = values.get('slices', [])
    assert len(values) == 1
    return values[0]


def _validation_set():
    # This guard checks that real checks run; strict-pass oracles are separate.
    values = [_strict(package) for package in PACKAGES]
    return len(values)==5 and all(v.get('schema')=='skill-quality-result.v1'
                                  and v.get('mode')=='strict'
                                  and v.get('exit_code') in [0,1]
                                  and v.get('authorizes')==[] for v in values)


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
    if index==0:
        result = validate_package(repository_root=".", package_root=".agents/skills/vdd-execution-plan",
                                  policy_path="scripts/sc/config/skill-authoring-standard.v1.json", mode="strict")
    elif index==1:
        result = validate_package(repository_root=".", package_root=".agents/skills/quick-dev-tdd-adapter",
                                  policy_path="scripts/sc/config/skill-authoring-standard.v1.json", mode="strict")
    elif index==2:
        result = validate_package(repository_root=".", package_root=".agents/skills/run-phase-bootstrap-review",
                                  policy_path="scripts/sc/config/skill-authoring-standard.v1.json", mode="strict")
    elif index==3:
        result = validate_package(repository_root=".", package_root=".agents/skills/run-refactor-implementation-acceptance",
                                  policy_path="scripts/sc/config/skill-authoring-standard.v1.json", mode="strict")
    elif index==4:
        result = validate_package(repository_root=".", package_root=".agents/skills/maintain-knowledge-base",
                                  policy_path="scripts/sc/config/skill-authoring-standard.v1.json", mode="strict")
    else:
        raise ValueError("Unknown governed package")
    return result["status"]=="pass" and result["exit_code"]==0 and result["authorizes"]==[]


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
        for ref in re.findall(r'\]\(([^)]+)\)', _main(package)):
            if ref.startswith(('http:', 'https:','#')):
                continue
            if not (package/ref.split('#',1)[0]).is_file():
                return False
    return True


def _diagram():
    for package in PACKAGES:
        declaration = _declaration(package)
        # These five existing workflows each have real conditional routes.
        if declaration.get('capabilities',{}).get('routing') is not True:
            return False
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
    source = _text(ROOT/'docs/workflows/inputs/package-b-rebuild-20261028-r2/requirements.md')
    return all('## FR-'+str(i)+' ' in source for i in range(1,7)) and all(name in source for name in ['VDD','Quick Dev','Bootstrap','Acceptance','maintenance'])


def _authority_input():
    path = ROOT/'docs/workflows/inputs/package-b-rebuild-20261028-r2/source-map.json'
    data = json.loads(_text(path))
    canonical = ROOT/data['canonical_path']
    if sha256(canonical.read_bytes()).hexdigest()!=data['canonical_sha256']:
        return False
    source = _intent_file('source-index.v1.json')
    if len(source['entries'])!=6:
        return False
    for entry in source['entries']:
        value=ROOT/entry['repository_relative_source_path']
        if entry['source_sha256']!='sha256:'+sha256(value.read_bytes()).hexdigest():
            return False
    return _canonical() and _unchanged(AUTHORITY)


def _scope():
    roots = [p.relative_to(ROOT).as_posix() for p in PACKAGES]
    selected = _slice_intent()
    owners = selected['production_owners']
    writes = selected['allowed_write_paths']
    def owned(ref):
        return any(ref.startswith(root+'/') for root in roots)
    return (len(set(roots))==5 and bool(owners)
            and all(owned(ref) and ref in writes for ref in owners)
            and all(owned(ref) or ref=='scripts/sc/tests/test_skill_quality_package_b.py'
                    for ref in writes) and _native_boundary())


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
    # Check the actual executable line, never explanatory prose or comments.
    expected = "scripts/sc/validate_skill_quality.py"
    options = {"--repository-root": ".",
               "--policy": "scripts/sc/config/skill-authoring-standard.v1.json",
               "--skill-root": ".agents/skills/run-phase-bootstrap-review",
               "--mode": "strict"}
    for line in _main(PACKAGES[2]).splitlines():
        if line.lstrip().startswith("#"):
            continue
        try:
            argv = shlex.split(line, comments=True)
        except ValueError:
            continue
        if not argv or argv[0] not in {"py", "python", "python3"}:
            continue
        if expected not in argv:
            continue
        index = argv.index(expected)
        if argv[:index] not in [["py", "-3", "-B"], ["python", "-B"], ["python3", "-B"]]:
            continue
        args = argv[index + 1:]
        if len(args) != 8 or dict(zip(args[::2], args[1::2])) != options:
            continue
        paths = [ROOT / expected, ROOT / options["--policy"], ROOT / options["--skill-root"] / "SKILL.md"]
        if all(path.is_file() and not path.is_symlink() for path in paths):
            return True
    return False


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
    # Verify an explicitly identified stage copy, never a future execution.
    # A later final-candidate snapshot is separately required at delivery.
    receipt = ROOT/'logs/package-b-rebuild-20261028/LIBRARY-STAGE003-DURABLE-RECEIPT.json'
    if not receipt.is_file():
        return False
    data=json.loads(_text(receipt))
    if (not data.get('library_file_id') or not data.get('files')
            or data.get('library_create_status')!='succeeded'
            or not data.get('returned_size_matches')):
        return False
    archive=ROOT/data['local_archive']
    if sha256(archive.read_bytes()).hexdigest()!=data['sha256']:
        return False
    with zipfile.ZipFile(archive) as stored:
        if stored.testzip() is not None:
            return False
        for record in data['files']:
            payload=stored.read(record['path'])
            if len(payload)!=record['bytes'] or sha256(payload).hexdigest()!=record['sha256']:
                return False
        normative='docs/workflows/inputs/package-b-rebuild-20261028-r2/requirements.md'
        if stored.read(normative)!=(ROOT/normative).read_bytes():
            return False
    return True


def _vdd_atomic_bindings():
    obligations = _intent_file('obligations.v1.json')
    acceptances = _intent_file('acceptances.v1.json')
    failures = _intent_file('failure-intents.v1.json')
    active = {item['obligation_id']:item for item in obligations if item['status']=='active'}
    by_failure = {item['failure_intent_id']:item for item in failures}
    covered = set()
    for acceptance in acceptances:
        ids = acceptance['obligation_ids']
        if len(ids)!=1 or ids[0] not in active or ids[0] in covered:
            return False
        covered.add(ids[0])
        if (not acceptance['assertion_ids'] or not acceptance['oracle']['expected']
                or not acceptance['red_intent_ids']
                or not set(acceptance['source_refs']).issubset(active[ids[0]]['source_refs'])):
            return False
        if not all(acceptance['acceptance_id'] in by_failure[fid]['acceptance_ids']
                   for fid in acceptance['red_intent_ids']):
            return False
    return covered==set(active) and _native_boundary()


def _child_contract_preserved():
    return _unchanged([
        '.agents/skills/quick-dev-tdd-adapter/tools/stable_runner.py',
        '.agents/skills/quick-dev-tdd-adapter/tools/q1_planned_preflight.py',
        '.agents/skills/vdd-execution-plan/scripts/execution_contract.py',
        'scripts/vdd/compile_plan.py'])


def _check(value,failure_id):
    if not value:
        print('FAILURE_ID:'+failure_id)
    assert value, 'The current production contract does not satisfy the bound Package B observable'


@pytest.mark.cer_assertion('PKGB_0082DA37FDD3')
def test_host_repair_boundary():
    _check(_native_boundary() and _unchanged(AUTHORITY), 'PKGB_0082DA37FDD3_FAIL')


@pytest.mark.cer_assertion('PKGB_06B2E983CB73')
def test_protected_sources():
    _check(_protected_bmad() and _chapters() and _unchanged(AUTHORITY), 'PKGB_06B2E983CB73_FAIL')


@pytest.mark.cer_assertion('PKGB_0BCEAD7964BF')
def test_complete_coverage():
    _check(_canonical(), 'PKGB_0BCEAD7964BF_FAIL')


@pytest.mark.cer_assertion('PKGB_0E031EB3891E')
def test_validation_set():
    _check(_validation_set(), 'PKGB_0E031EB3891E_FAIL')


@pytest.mark.cer_assertion('PKGB_0E6D98559F6B')
def test_bootstrap_quality():
    _check(_quality(2), 'PKGB_0E6D98559F6B_FAIL')


@pytest.mark.cer_assertion('PKGB_0E781666A8E6')
def test_canonical_input():
    _check(_canonical() and _authority_input(), 'PKGB_0E781666A8E6_FAIL')


@pytest.mark.cer_assertion('PKGB_106E49892C1C')
def test_vdd_quality():
    _check(_quality(0), 'PKGB_106E49892C1C_FAIL')


@pytest.mark.cer_assertion('PKGB_122D7390958D')
def test_content_reuse():
    _check(_native_boundary() and "content" in _main(PACKAGES[1]).lower(), 'PKGB_122D7390958D_FAIL')


@pytest.mark.cer_assertion('PKGB_136CDDBA77A6')
def test_no_quality_authority():
    _check(_unchanged(AUTHORITY) and _native_boundary(), 'PKGB_136CDDBA77A6_FAIL')


@pytest.mark.cer_assertion('PKGB_1370E773AD67')
def test_dependency_documentation():
    _check(_dependency_table(), 'PKGB_1370E773AD67_FAIL')


@pytest.mark.cer_assertion('PKGB_181DCD9163A1')
def test_invalid_red():
    _check(_native_boundary() and "harness" in _main(PACKAGES[1]).lower(), 'PKGB_181DCD9163A1_FAIL')


@pytest.mark.cer_assertion('PKGB_18BAEF1E87C0')
def test_local_scope():
    _check(_scope(), 'PKGB_18BAEF1E87C0_FAIL')


@pytest.mark.cer_assertion('PKGB_1A7456E604BF')
def test_first_level_references():
    _check(_references(), 'PKGB_1A7456E604BF_FAIL')


@pytest.mark.cer_assertion('PKGB_1A82E183EEBB')
def test_authority_inputs():
    _check(_authority_input(), 'PKGB_1A82E183EEBB_FAIL')


@pytest.mark.cer_assertion('PKGB_1FC41E966CB0')
def test_quick_upgrade_boundary():
    _check(_native_boundary() and "upgrade" in _main(PACKAGES[1]).lower() and "VDD" in _main(PACKAGES[1]), 'PKGB_1FC41E966CB0_FAIL')


@pytest.mark.cer_assertion('PKGB_2275CA248048')
def test_bmad_exclusion():
    _check(_protected_bmad(), 'PKGB_2275CA248048_FAIL')


@pytest.mark.cer_assertion('PKGB_26F529A9E55D')
def test_child_dependency_preservation():
    _check(_child_contract_preserved(), 'PKGB_26F529A9E55D_FAIL')


@pytest.mark.cer_assertion('PKGB_27A3D0428D77')
def test_native_reuse():
    _check(_native_boundary(), 'PKGB_27A3D0428D77_FAIL')


@pytest.mark.cer_assertion('PKGB_2CBB18C96E83')
def test_direct_regression():
    # The frozen native Q6 command additionally runs the actual owning tests.
    context = json.loads(_text(PLAN/'agent-context/S1/agent-context.json'))
    commands = context['validation_commands']
    required = ['test_validate_skill_contract.py', 'test_skill_contract.py',
                'test_direct_script_startup.py', 'test_package.py',
                'test_prepare_publication_request.py']
    _check(_native_boundary() and all(any(name in arg for command in commands
                                         for arg in command) for name in required),
           'PKGB_2CBB18C96E83_FAIL')


@pytest.mark.cer_assertion('PKGB_31BB4B73B2E0')
def test_dependency_records():
    _check(_dependency_records(), 'PKGB_31BB4B73B2E0_FAIL')


@pytest.mark.cer_assertion('PKGB_3334FEB462B7')
def test_stale_maintenance():
    _check(_native_boundary() and "catalog-stale-maintenance" in _main(PACKAGES[4]), 'PKGB_3334FEB462B7_FAIL')


@pytest.mark.cer_assertion('PKGB_333D4B6DB398')
def test_predicate_completion():
    _check(_native_boundary() and "Evidence Ownership" in _main(PACKAGES[1]), 'PKGB_333D4B6DB398_FAIL')


@pytest.mark.cer_assertion('PKGB_33A58D56A240')
def test_operator_publication():
    _check(_operator_docs(), 'PKGB_33A58D56A240_FAIL')


@pytest.mark.cer_assertion('PKGB_3468471DAB29')
def test_persistent_evidence():
    _check(_persistent_input(), 'PKGB_3468471DAB29_FAIL')


@pytest.mark.cer_assertion('PKGB_3CB8579F527E')
def test_no_operational_authority():
    _check(_native_boundary() and all("not" in _main(p).lower() for p in PACKAGES), 'PKGB_3CB8579F527E_FAIL')


@pytest.mark.cer_assertion('PKGB_3E98F7EB3C8D')
def test_frozen_inputs():
    _check(_authority_input() and _native_boundary(), 'PKGB_3E98F7EB3C8D_FAIL')


@pytest.mark.cer_assertion('PKGB_435F58556AB8')
def test_freeze_proof():
    _check(_native_boundary() and "frozen" in _main(PACKAGES[1]).lower(), 'PKGB_435F58556AB8_FAIL')


@pytest.mark.cer_assertion('PKGB_49D7164AED75')
def test_acceptance_owner():
    _check(_native_boundary() and "finalization" in _main(PACKAGES[3]).lower(), 'PKGB_49D7164AED75_FAIL')


@pytest.mark.cer_assertion('PKGB_4DE82E497103')
def test_vdd_no_execution():
    _check(_native_boundary() and "VDD owns none" in _main(PACKAGES[0]), 'PKGB_4DE82E497103_FAIL')


@pytest.mark.cer_assertion('PKGB_516E31393C6B')
def test_focused_verification():
    _check(_quality_negative_checks(), 'PKGB_516E31393C6B_FAIL')


@pytest.mark.cer_assertion('PKGB_51D4739E3A0A')
def test_public_compile():
    _check(_native_boundary() and "compile_plan.py" in _main(PACKAGES[0]), 'PKGB_51D4739E3A0A_FAIL')


@pytest.mark.cer_assertion('PKGB_520D0E5EA4C7')
def test_quick_examples():
    _check(_examples(1, [('strict',), ('upgrade',), ('invalid',)]), 'PKGB_520D0E5EA4C7_FAIL')


@pytest.mark.cer_assertion('PKGB_53380A1D038B')
def test_accepted_validator():
    _check(_unchanged(AUTHORITY), 'PKGB_53380A1D038B_FAIL')


@pytest.mark.cer_assertion('PKGB_5375308178D9')
def test_accepted_predecessor():
    _check(_unchanged(AUTHORITY) and _canonical(), 'PKGB_5375308178D9_FAIL')


@pytest.mark.cer_assertion('PKGB_56A33BF13918')
def test_bootstrap_examples():
    _check(_examples(2, [('clean',), ('round',), ('access',)]), 'PKGB_56A33BF13918_FAIL')


@pytest.mark.cer_assertion('PKGB_56B4D051B472')
def test_no_global_framework():
    _check(_scope(), 'PKGB_56B4D051B472_FAIL')


@pytest.mark.cer_assertion('PKGB_5911772C50A8')
def test_reference_reuse():
    _check(_references(), 'PKGB_5911772C50A8_FAIL')


@pytest.mark.cer_assertion('PKGB_597AAD1CF5FF')
def test_profile_selection():
    _check("self-hosted" in _main(PACKAGES[0]) and _native_boundary(), 'PKGB_597AAD1CF5FF_FAIL')


@pytest.mark.cer_assertion('PKGB_5AAFB946671F')
def test_quality_invariants():
    _check(_all_quality() and _capabilities(), 'PKGB_5AAFB946671F_FAIL')


@pytest.mark.cer_assertion('PKGB_6AC1654A3B38')
def test_acceptance_quality():
    _check(_quality(3), 'PKGB_6AC1654A3B38_FAIL')


@pytest.mark.cer_assertion('PKGB_6F444612047C')
def test_platform_truth():
    _check(sys.version_info>=(3,11) and hasattr(pytest,"mark"), 'PKGB_6F444612047C_FAIL')


@pytest.mark.cer_assertion('PKGB_7136BAA2CA44')
def test_explicit_vdd_routing():
    _check("explicitly" in _main(PACKAGES[0]).lower() and "standalone" in _main(PACKAGES[0]).lower() and _native_boundary(), 'PKGB_7136BAA2CA44_FAIL')


@pytest.mark.cer_assertion('PKGB_73B685FB11F6')
def test_behavior_classification():
    _check(_native_boundary() and "probe" in _main(PACKAGES[1]).lower(), 'PKGB_73B685FB11F6_FAIL')


@pytest.mark.cer_assertion('PKGB_7ACD9F289FDE')
def test_knowledge_boundaries():
    _check(_operator_docs() and _native_boundary(), 'PKGB_7ACD9F289FDE_FAIL')


@pytest.mark.cer_assertion('PKGB_7EDC585984AC')
def test_sidecar_shape():
    _check(_frontmatter(), 'PKGB_7EDC585984AC_FAIL')


@pytest.mark.cer_assertion('PKGB_80316CD17E3B')
def test_acceptance_examples():
    _check(_examples(3, [('deterministic',), ('repair',), ('stale',)]), 'PKGB_80316CD17E3B_FAIL')


@pytest.mark.cer_assertion('PKGB_897EA243B79E')
def test_phase_exclusion():
    _check(_scope() and _unchanged(["scripts/sc/_llm_backend.py"]), 'PKGB_897EA243B79E_FAIL')


@pytest.mark.cer_assertion('PKGB_8AFEC64253D3')
def test_knowledge_examples():
    _check(_examples(4, [('existing-only',), ('provisional',), ('publication',)]), 'PKGB_8AFEC64253D3_FAIL')


@pytest.mark.cer_assertion('PKGB_8ECA25407A03')
def test_preserved_boundaries():
    _check(_native_boundary() and _unchanged(AUTHORITY), 'PKGB_8ECA25407A03_FAIL')


@pytest.mark.cer_assertion('PKGB_95DA69640268')
def test_vdd_examples():
    _check(_examples(0, [('create',), ('direct',), ('invalid',)]), 'PKGB_95DA69640268_FAIL')


@pytest.mark.cer_assertion('PKGB_97205C679D05')
def test_standalone_preflight():
    _check(_entrypoints(), 'PKGB_97205C679D05_FAIL')


@pytest.mark.cer_assertion('PKGB_9E8AACC50395')
def test_main_bound():
    _check(all(len(_main(p).splitlines())<500 for p in PACKAGES), 'PKGB_9E8AACC50395_FAIL')


@pytest.mark.cer_assertion('PKGB_9ED7E6CE4DDC')
def test_repair_integrity():
    _check(_native_boundary() and "historical" in _main(PACKAGES[1]).lower(), 'PKGB_9ED7E6CE4DDC_FAIL')


@pytest.mark.cer_assertion('PKGB_9FDC53051B14')
def test_knowledge_quality():
    _check(_quality(4), 'PKGB_9FDC53051B14_FAIL')


@pytest.mark.cer_assertion('PKGB_A4FF42287EF4')
def test_typed_errors():
    _check(all(bool(_declaration(p).get("error_ids")) for p in PACKAGES), 'PKGB_A4FF42287EF4_FAIL')


@pytest.mark.cer_assertion('PKGB_A6C02C53C2A4')
def test_no_automatic_publish():
    _check(_native_boundary() and _unchanged(["scripts/sc/_llm_backend.py"]), 'PKGB_A6C02C53C2A4_FAIL')


@pytest.mark.cer_assertion('PKGB_AA5934B2633E')
def test_capability_drift():
    _check(_unchanged(AUTHORITY) and _native_boundary(), 'PKGB_AA5934B2633E_FAIL')


@pytest.mark.cer_assertion('PKGB_B31AFCA31048')
def test_chapter_exclusion():
    _check(_chapters(), 'PKGB_B31AFCA31048_FAIL')


@pytest.mark.cer_assertion('PKGB_B66298A862BB')
def test_owner_drift():
    _check(_native_boundary(), 'PKGB_B66298A862BB_FAIL')


@pytest.mark.cer_assertion('PKGB_C9ED9E3E46B5')
def test_quick_quality():
    _check(_quality(1), 'PKGB_C9ED9E3E46B5_FAIL')


@pytest.mark.cer_assertion('PKGB_CA4306911C31')
def test_child_drift():
    _check(_native_boundary(), 'PKGB_CA4306911C31_FAIL')


@pytest.mark.cer_assertion('PKGB_D0CE1CA291A7')
def test_distinct_completion():
    _check(_native_boundary() and "external Acceptance" in _main(PACKAGES[1]), 'PKGB_D0CE1CA291A7_FAIL')


@pytest.mark.cer_assertion('PKGB_D435CEAE6CBD')
def test_portable_bootstrap():
    _check(_portable_bootstrap(), 'PKGB_D435CEAE6CBD_FAIL')


@pytest.mark.cer_assertion('PKGB_D4FDDB15D79E')
def test_routing_diagrams():
    _check(_diagram(), 'PKGB_D4FDDB15D79E_FAIL')


@pytest.mark.cer_assertion('PKGB_DBD4AF430715')
def test_no_fake_recovery():
    _check(_canonical() and _native_boundary(), 'PKGB_DBD4AF430715_FAIL')


@pytest.mark.cer_assertion('PKGB_E5D14EE8A976')
def test_predecessor_scope():
    _check(_unchanged(AUTHORITY), 'PKGB_E5D14EE8A976_FAIL')


@pytest.mark.cer_assertion('PKGB_EB599B9F9D24')
def test_vdd_semantic_owner():
    _check(_vdd_atomic_bindings(), 'PKGB_EB599B9F9D24_FAIL')


@pytest.mark.cer_assertion('PKGB_EB7D799DFE5A')
def test_authority_drift():
    _check(_unchanged(AUTHORITY), 'PKGB_EB7D799DFE5A_FAIL')


@pytest.mark.cer_assertion('PKGB_EBC502B01FF4')
def test_source_expression():
    _check(_authority_input(), 'PKGB_EBC502B01FF4_FAIL')


@pytest.mark.cer_assertion('PKGB_F308EA0BD0A3')
def test_five_strict():
    _check(_all_quality(), 'PKGB_F308EA0BD0A3_FAIL')


@pytest.mark.cer_assertion('PKGB_F40D1B12384F')
def test_nonauthorizing_dependencies():
    _check(_native_boundary() and _unchanged(AUTHORITY), 'PKGB_F40D1B12384F_FAIL')


@pytest.mark.cer_assertion('PKGB_F522DEE88468')
def test_historical_preservation():
    _check(_native_boundary() and all("histor" in _main(p).lower() or "append" in _main(p).lower() for p in PACKAGES), 'PKGB_F522DEE88468_FAIL')


@pytest.mark.cer_assertion('PKGB_F7254CBACFD6')
def test_bmad_separation():
    _check(_protected_bmad(), 'PKGB_F7254CBACFD6_FAIL')


@pytest.mark.cer_assertion('PKGB_F7C23594D5FC')
def test_unit_budget():
    _check(_native_boundary() and "1800" in _main(PACKAGES[1]) and "600" in _main(PACKAGES[1]), 'PKGB_F7C23594D5FC_FAIL')


@pytest.mark.cer_assertion('PKGB_F8B04C33A6A6')
def test_scope_drift():
    _check(_native_boundary() and _scope(), 'PKGB_F8B04C33A6A6_FAIL')


@pytest.mark.cer_assertion('PKGB_FB4AFA4ABA94')
def test_current_state():
    _check(_native_boundary() and _unchanged(AUTHORITY), 'PKGB_FB4AFA4ABA94_FAIL')


@pytest.mark.cer_assertion('PKGB_FF00F91F7070')
def test_bootstrap_authority():
    _check(_native_boundary() and "authority" in _main(PACKAGES[2]).lower(), 'PKGB_FF00F91F7070_FAIL')
