"""ADR-0041/0043: source-bound Phase routing must retain default exclusions."""
from pathlib import Path
import sys
import copy
import hashlib
import json

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import semantic_compiler as sc
import semantic_feasibility_patch  # noqa: F401 - public CLI patch ordering
from semantic_worker_v3_execution_contract_patch import _findings
from test_ch456_v3_execution_contract import _obligation, _acceptance, _failure, _hint


def scoped_bundle(selected):
    import semantic_phase_source_scope as scope
    hint = candidate(selected.root)['slice_hints'][0]
    hint['execution_snapshot_paths'] += [p for p, _ in selected.dependencies]
    hint['slice_id'] = 'S1'
    return {'profile': 'resumable', 'slices': [hint], 'agent_contexts': [
        {'slice_id': 'S1', 'allowed_paths': hint['allowed_write_paths'], 'forbidden_paths': []}],
        'source_scope': scope.description(selected.root)}


@pytest.mark.parametrize('change', ['same', 'withdrawn', 'changed'])
def test_completed_resume_rechecks_published_scope(tmp_path, approved, monkeypatch, change):
    import semantic_compiler_gate as gate
    scope, req, path, value = approved
    selected = scope.load(tmp_path, req, path)
    with scope.session(tmp_path, selected):
        bundle = scoped_bundle(selected)
    out = tmp_path/'plan'
    out.mkdir()
    (out/'compiler-state.v1.json').write_text(json.dumps({'state': 'plan-ready',
        'semantic_plan_sha256': sc.sha256_value(bundle)}))
    (out/'semantic-plan-bundle.v1.json').write_text(json.dumps(bundle))
    (out/'source-index.v1.json').write_text(json.dumps({'sha256': 'source'}))
    # Isolate the scope guard from unrelated structural requirements.
    monkeypatch.setattr(gate, 'validate_semantic_bundle_with_preflight', lambda b: (True, []))
    if change == 'changed':
        value['support_paths'].append('tests/another.py')
        path.write_text(json.dumps(value))
    selected = None if change == 'withdrawn' else scope.load(tmp_path, req, path)
    with scope.session(tmp_path, selected):
        if change == 'same':
            assert gate._completed_resume(out, source_index_sha256='source', profile='resumable')['status'] == 'plan-ready'
        else:
            with pytest.raises(ValueError, match='source-scope:'):
                gate._completed_resume(out, source_index_sha256='source', profile='resumable')


@pytest.mark.parametrize('defect', ['support_forbidden', 'outside_write', 'missing_dependency', 'context_write'])
def test_final_bundle_rejects_post_projection_scope_drift(tmp_path, approved, defect):
    scope, req, path, _ = approved
    selected = scope.load(tmp_path, req, path)
    with scope.session(tmp_path, selected):
        bundle = scoped_bundle(selected)
        scope.validate_bundle(tmp_path, bundle)
        if defect == 'support_forbidden':
            bundle['slices'][0]['allowed_write_paths'].append('tests/test_owner.py')
            bundle['agent_contexts'][0]['forbidden_paths'] = ['tests/**']
        elif defect == 'outside_write':
            bundle['slices'][0]['planned_new_files'].append('tests/outside.py')
        elif defect == 'missing_dependency':
            bundle['slices'][0]['execution_snapshot_paths'].remove('scope.json')
        else:
            bundle['agent_contexts'][0]['allowed_paths'] = ['tests/outside.py']
        with pytest.raises(ValueError, match='source-scope:'):
            scope.validate_bundle(tmp_path, bundle)


def test_support_forbidden_survives_explicit_path_normalization(tmp_path, approved):
    from semantic_worker_v3_explicit_path_contract_patch import normalize_explicit_path_contracts
    scope, req, path, _ = approved
    selected = scope.load(tmp_path, req, path)
    value = candidate(tmp_path)
    hint = value['slice_hints'][0]
    hint['forbidden_paths'] = ['tests/test_owner.py']
    hint['execution_snapshot_paths'] += [p for p, _ in selected.dependencies]
    payload = {'obligations': [_obligation('O-1')]}
    payload['source_contracts'] = [{'source_ref': payload['obligations'][0]['source_refs'][0],
        'source_text': 'Must create `tests/test_owner.py`.'}]
    with scope.session(tmp_path, selected):
        result = normalize_explicit_path_contracts(tmp_path, 'v3', payload, value)
        assert 'tests/test_owner.py' in result['slice_hints'][0]['forbidden_paths']
        assert any('forbidden-path:tests/test_owner.py' in f for f in _findings(tmp_path, 'v3', payload, result))


@pytest.mark.parametrize('active', [True, False])
def test_final_v3_consumer_rechecks_repair_overlay(tmp_path, approved, monkeypatch, active):
    scope, req, path, _ = approved
    selected = scope.load(tmp_path, req, path)
    value = candidate(tmp_path)
    value['slice_hints'][0]['execution_snapshot_paths'] += [p for p, _ in selected.dependencies]
    value['slice_hints'][0]['allowed_write_paths'].append('tests/overlay-outside.py')
    monkeypatch.setattr(sc, 'invoke_worker', lambda **kwargs: value)
    with scope.session(tmp_path, selected if active else None):
        with pytest.raises(ValueError, match='source-scope:'):
            sc.compile_acceptances(root=tmp_path, out_dir=tmp_path/'plan',
                                   obligations=[_obligation('O-1')], worker_cache=None)


def test_handoff_repair_checks_scope_before_creating_successor(tmp_path, approved):
    import quick_dev_handoff
    scope, req, path, _ = approved
    selected = scope.load(tmp_path, req, path)
    with scope.session(tmp_path, selected):
        bundle = scoped_bundle(selected)
    predecessor = tmp_path/'predecessor'
    predecessor.mkdir()
    (predecessor/'semantic-plan-bundle.v1.json').write_text(json.dumps(bundle))
    successor = tmp_path/'successor'
    with scope.session(tmp_path, None):
        with pytest.raises(ValueError, match='source-scope:'):
            quick_dev_handoff.publish_repair(root=tmp_path, requirements=req,
                predecessor=predecessor, out_dir=successor, test_root='tests')
    assert not successor.exists()


def test_final_publisher_guard_rejects_scoped_bundle_without_current_scope(tmp_path, approved):
    import semantic_compiler_gate as gate
    scope, req, path, _ = approved
    with scope.session(tmp_path, scope.load(tmp_path, req, path)):
        bundle = scoped_bundle(scope.current(tmp_path))
    with scope.session(tmp_path, None):
        with pytest.raises(ValueError, match='source-scope:'):
            gate.validate_semantic_bundle_with_preflight(bundle)


@pytest.mark.parametrize('outside', [False, True])
def test_real_execution_preflight_carries_scope_without_authorizing(tmp_path, approved, monkeypatch, outside):
    import execution_preflight
    scope, req, path, _ = approved
    selected = scope.load(tmp_path, req, path)
    raw = candidate(tmp_path)
    raw['slice_hints'][0]['execution_snapshot_paths'] += [p for p, _ in selected.dependencies]
    monkeypatch.setattr(sc, 'invoke_worker', lambda **kwargs: raw)
    with scope.session(tmp_path, selected):
        acceptances, failures, hints = sc.compile_acceptances(root=tmp_path,
            out_dir=tmp_path/'plan', obligations=[_obligation('O-1')], worker_cache=None)
        if outside:
            hints[0]['allowed_write_paths'].append('tests/outside.py')
        result = execution_preflight.inspect_candidate(sc, tmp_path, [_obligation('O-1')],
            acceptances, failures, hints, profile='resumable')
    assert result['authorizes'] == []
    if outside:
        assert any('source-scope:' in f for f in result['findings']), result
    else:
        assert not any('source-scope:' in f for f in result['findings']), result
        assert result['valid'], result


def candidate(root):
    for name, data in {
        'src/owner.py': 'VALUE = 1\n',
        'PhaseA.Platform/Node.cs': 'namespace PhaseA.Platform; public class Node {}\n',
    }.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data, encoding='utf-8')
    hint = _hint(['O-1'], allowed=['PhaseA.Platform/Node.cs'],
                 planned=['tests/test_owner.py'])
    hint['production_owners'] = ['PhaseA.Platform/Node.cs']
    hint['rollback_scope']['production_paths'] = ['PhaseA.Platform/Node.cs']
    return {'acceptances': [_acceptance(['O-1'])],
            'failure_intents': [_failure(['O-1'])], 'slice_hints': [hint]}


def test_generic_prompt_does_not_inject_unrelated_toolchain_requirements(tmp_path, monkeypatch):
    seen = []
    hint = _hint(['O-1'], allowed=['src/owner.py'], planned=['tests/test_owner.py'])
    def worker(**kwargs):
        seen.append(kwargs['prompt'])
        return {'acceptances': [_acceptance(['O-1'])],
                'failure_intents': [_failure(['O-1'])], 'slice_hints': [hint]}
    monkeypatch.setattr(sc, 'invoke_worker', worker)
    sc.compile_acceptances(root=tmp_path, out_dir=tmp_path/'plan',
                           obligations=[_obligation('O-1')], worker_cache=None)
    assert 'FR-9 Consumer Manifest' not in seen[0]
    assert 'for this Toolchain plan' not in seen[0]


def test_default_phase_owner_remains_denied(tmp_path):
    result = _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]},
                       candidate(tmp_path))
    assert any('phase-protected-path' in item for item in result)


@pytest.mark.parametrize('alias', ['./PhaseA.Platform/Node.cs', 'PhaseA.Platform//Node.cs'])
def test_default_phase_path_alias_does_not_bypass_exclusion(tmp_path, alias):
    value = candidate(tmp_path)
    hint = value['slice_hints'][0]
    hint['production_owners'] = [alias]
    hint['allowed_write_paths'] = [alias]
    hint['rollback_scope']['production_paths'] = [alias]
    findings = _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, value)
    assert any('phase-protected-path:' in f for f in findings)


def test_worker_payload_cannot_self_authorize_phase(tmp_path):
    payload = {'obligations': [_obligation('O-1')],
               'source_scope': {'scope': 'phase-service',
                                'write_paths': ['PhaseA.Platform/Node.cs'],
                                'approved': True}}
    result = _findings(tmp_path, 'v3-schema-repair', {'input': payload}, candidate(tmp_path))
    assert any('phase-protected-path' in item for item in result)


def test_default_runtime_read_dependency_is_not_promoted_to_write(tmp_path):
    value = candidate(tmp_path)
    hint = value['slice_hints'][0]
    hint['production_owners'] = ['src/owner.py']
    hint['allowed_write_paths'] = ['src/owner.py']
    hint['rollback_scope']['production_paths'] = ['src/owner.py']
    runtime = tmp_path/'runtime/phase-a/read.py'
    runtime.parent.mkdir(parents=True)
    runtime.write_text('VALUE = 1\n')
    hint['execution_snapshot_paths'].append('runtime/phase-a/read.py')
    assert not _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, value)
    hint['allowed_write_paths'].append('runtime/phase-a/read.py')
    assert any('phase-protected-path:runtime/phase-a/read.py' in f
               for f in _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, value))


@pytest.fixture
def approved(tmp_path):
    import semantic_phase_source_scope as scope
    candidate(tmp_path)
    adr_name = 'docs/adr/ADR-9999-s2-scope.md'
    adr = tmp_path/adr_name
    adr.parent.mkdir(parents=True)
    section = '## S2-06 approved local boundary'
    adr.write_text('# ADR\n- Status: Accepted\n\n'+section+'\nUse the existing local node boundary.\n')
    req = tmp_path/'requirements.md'
    req.write_text('# FR-1 S2-06\nAuthority: '+adr_name+'\n'+section+
                   '\nUse the existing local node boundary.\n')
    auth = tmp_path/'authorization.json'
    auth.write_text(json.dumps({'user_request': 'Complete S2-06', 'workspace': str(tmp_path),
                               'authorized_stages': ['VDD', 'Quick Dev TDD']}))
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    value = {'schema': 'vdd.phase-source-scope.v1', 'task_id': 'S2-06',
             'requirements': {'path': 'requirements.md', 'sha256': digest(req)},
             'adr': {'path': adr_name, 'sha256': digest(adr), 'section': section},
             'authorization': {'path': 'authorization.json', 'sha256': digest(auth)},
             'write_paths': ['PhaseA.Platform/Node.cs'], 'read_paths': [],
             'support_paths': ['tests/test_owner.py'], 'authorizes': []}
    path = tmp_path/'scope.json'
    path.write_text(json.dumps(value))
    return scope, req, path, value


@pytest.mark.parametrize('stage', ['v3', 'v3-schema-repair', 'v3-schema-repair-chunk-01'])
def test_source_bound_exact_phase_contract_is_admitted(tmp_path, approved, stage):
    scope, req, path, _ = approved
    selected = scope.load(tmp_path, req, path)
    with scope.session(tmp_path, selected):
        value = candidate(tmp_path)
        value['slice_hints'][0]['execution_snapshot_paths'] += [p for p, _h in selected.dependencies]
        payload = {'obligations': [_obligation('O-1')]}
        if stage != 'v3': payload = {'input': payload}
        result = _findings(tmp_path, stage, payload, value)
    assert not result, result


@pytest.mark.parametrize('change', ['schema', 'unknown', 'requirement_hash', 'adr_hash',
    'authorization_hash', 'proposed', 'unrelated_authorization', 'empty', 'directory',
    'glob', 'escape', 'runtime', 'case_alias', 'dot', 'symlink', 'workspace',
    'task_suffix', 'authority_writable', 'authorizes', 'role_conflict', 'toolchain_support'])
def test_invalid_scope_cannot_expand_phase(tmp_path, approved, change):
    scope, req, path, original = approved
    value = copy.deepcopy(original)
    if change == 'schema': value['schema'] = 'invented'
    elif change == 'unknown': value['approved'] = True
    elif change.endswith('_hash'):
        key = {'requirement_hash': 'requirements', 'adr_hash': 'adr',
               'authorization_hash': 'authorization'}[change]
        value[key]['sha256'] = '0'*64
    elif change == 'proposed':
        p = tmp_path/value['adr']['path'];p.write_text(p.read_text().replace('Accepted', 'Proposed'))
        value['adr']['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    elif change == 'unrelated_authorization':
        p = tmp_path/'authorization.json';p.write_text(json.dumps({'user_request': 'Other task',
            'authorized_stages': ['VDD', 'Quick Dev TDD']}))
        value['authorization']['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    elif change == 'empty': value['write_paths'] = []
    elif change == 'directory': value['write_paths'] = ['PhaseA.Platform']
    elif change == 'glob': value['write_paths'] = ['PhaseA.Platform/*.cs']
    elif change == 'escape': value['write_paths'] = ['PhaseA.Platform/../Other.cs']
    elif change == 'runtime': value['write_paths'] = ['runtime/phase-a/start.cs']
    elif change == 'case_alias': value['write_paths'] = ['phasea.platform/Node.cs']
    elif change == 'dot': value['requirements']['path'] = '.'
    elif change == 'symlink':
        p = tmp_path/'PhaseA.Platform/Node.cs';p.unlink();p.symlink_to(tmp_path/'src/owner.py')
    elif change in {'workspace', 'task_suffix'}:
        p = tmp_path/'authorization.json';record = json.loads(p.read_text())
        if change == 'workspace': record['workspace'] = str(tmp_path/'other')
        else: record['user_request'] = 'Complete S2-060'
        p.write_text(json.dumps(record))
        value['authorization']['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    elif change == 'authority_writable': value['support_paths'].append(value['adr']['path'])
    elif change == 'authorizes': value['authorizes'] = ['write']
    elif change == 'role_conflict': value['read_paths'] = value['write_paths'][:]
    elif change == 'toolchain_support': value['support_paths'].append('scripts/sc/_llm_backend.py')
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='source-scope:'):
        scope.load(tmp_path, req, path)


def test_scope_context_clears_and_rechecks_dependency_bytes(tmp_path, approved):
    scope, req, path, _ = approved
    selected = scope.load(tmp_path, req, path)
    with scope.session(tmp_path, selected):
        assert scope.description(tmp_path)['sha256'] == selected.identity
        req.write_text(req.read_text()+'Changed requirement\n')
        with pytest.raises(ValueError, match='dependency changed'):
            scope.description(tmp_path)
    assert scope.description(tmp_path) is None


def test_scope_does_not_cross_repository_or_overlap(tmp_path, approved):
    scope, req, path, _ = approved
    with scope.session(tmp_path, scope.load(tmp_path, req, path)):
        assert scope.description(tmp_path/'other-repository') is None
        with pytest.raises(ValueError, match='overlapping'):
            with scope.session(tmp_path, None):
                pass


def test_authority_fragment_is_not_affected_by_unrelated_code_fences(tmp_path, approved):
    scope, req, path, value = approved
    adr = tmp_path/value['adr']['path']
    adr.write_text(adr.read_text().replace('existing local', 'existing `local`'))
    req.write_text('```text\nUnrelated example\n```\n'+
                   req.read_text().replace('existing local', 'existing `local`'))
    value['adr']['sha256'] = hashlib.sha256(adr.read_bytes()).hexdigest()
    value['requirements']['sha256'] = hashlib.sha256(req.read_bytes()).hexdigest()
    path.write_text(json.dumps(value))
    assert scope.load(tmp_path, req, path).task_id == 'S2-06'


@pytest.mark.parametrize('field', ['production_owners', 'allowed_write_paths',
    'execution_snapshot_paths', 'planned_new_files', 'rollback'])
def test_unapproved_path_cannot_enter_any_contract_role(tmp_path, approved, field):
    scope, req, path, _ = approved
    selected = scope.load(tmp_path, req, path)
    value = candidate(tmp_path)
    hint = value['slice_hints'][0]
    hint['execution_snapshot_paths'] += [p for p, _h in selected.dependencies]
    extra = 'PhaseA.Platform/Unapproved.cs'
    if field == 'rollback': hint['rollback_scope']['production_paths'].append(extra)
    else: hint[field].append(extra)
    payload = {'obligations': [_obligation('O-1')],
               'source_scope': {'write_paths': [extra], 'approved': True}}
    with scope.session(tmp_path, selected):
        findings = _findings(tmp_path, 'v3', payload, value)
    assert any('phase-protected-path:'+extra in f for f in findings)


@pytest.mark.parametrize('forbidden', ['PhaseA.Platform/Node.cs', 'PhaseA.Platform',
                                      'PhaseA.Platform/**', 'phasea.platform/*'])
def test_explicit_protected_forbidden_wins_over_scope(tmp_path, approved, forbidden):
    scope, req, path, _ = approved
    selected = scope.load(tmp_path, req, path)
    value = candidate(tmp_path)
    hint = value['slice_hints'][0]
    hint['execution_snapshot_paths'] += [p for p, _h in selected.dependencies]
    hint['forbidden_paths'] = [forbidden]
    with scope.session(tmp_path, selected):
        findings = _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, value)
    assert any('protected-forbidden-path:' in f for f in findings)


def test_protected_forbidden_survives_both_normalizers(tmp_path):
    import semantic_worker_v3_explicit_path_contract_patch as explicit
    from semantic_worker_v3_write_set_projection_patch import project_with_owner_write_set
    value = candidate(tmp_path)
    hint = value['slice_hints'][0]
    target = 'PhaseA.Platform/Node.cs'
    hint['forbidden_paths'] = [target]
    facts = {'owners': [target], 'planned': [target], 'existing_fixtures': [], 'owner_only': False}
    normalized = explicit._normalize_hint(tmp_path, hint, refs_by_oid={'O-1': {'req.md#FR-1'}},
                                         contracts_by_ref={'req.md#FR-1': facts})
    assert normalized['forbidden_paths'] == [target]
    group = {'groups': [{'obligation_ids': ['O-1'],
        'acceptance': {k: v for k, v in value['acceptances'][0].items() if k != 'obligation_ids'},
        'failure_intents': [{k: v for k, v in value['failure_intents'][0].items() if k != 'obligation_ids'}],
        'slice_hint': {k: v for k, v in hint.items() if k != 'obligation_ids'}}]}
    assert project_with_owner_write_set(group)['slice_hints'][0]['forbidden_paths'] == [target]


def test_protected_forbidden_survives_group_safety_normalizer(tmp_path, approved):
    import semantic_worker_v3_group_safety_patch as group_safety
    scope, req, path, _ = approved
    selected = scope.load(tmp_path, req, path)
    value = candidate(tmp_path)
    hint = value['slice_hints'][0]
    target = 'PhaseA.Platform/Node.cs'
    hint['forbidden_paths'] = [target]
    hint['execution_snapshot_paths'] += [p for p, _h in selected.dependencies]
    value['slice_hints'][0] = group_safety._normalize_hint(tmp_path, hint)
    assert value['slice_hints'][0]['forbidden_paths'] == [target]
    with scope.session(tmp_path, selected):
        findings = _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, value)
    assert any('protected-forbidden-path:' in f for f in findings)


def test_scoped_read_only_dependency_never_becomes_writable(tmp_path, approved):
    scope, req, path, value = approved
    read = tmp_path/'PhaseA.Platform/ReadOnly.cs'
    read.write_text('namespace PhaseA.Platform; public class ReadOnly {}\n')
    value['read_paths'] = ['PhaseA.Platform/ReadOnly.cs']
    path.write_text(json.dumps(value))
    selected = scope.load(tmp_path, req, path)
    result = candidate(tmp_path)
    hint = result['slice_hints'][0]
    hint['execution_snapshot_paths'] += [p for p, _h in selected.dependencies] + [value['read_paths'][0]]
    with scope.session(tmp_path, selected):
        assert not _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, result)
        hint['allowed_write_paths'].append(value['read_paths'][0])
        assert any('phase-protected-path:PhaseA.Platform/ReadOnly.cs' in f
                   for f in _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, result))


def test_scope_dependency_must_remain_frozen_in_execution_inputs(tmp_path, approved):
    scope, req, path, _ = approved
    with scope.session(tmp_path, scope.load(tmp_path, req, path)):
        findings = _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, candidate(tmp_path))
    assert any('phase-scope-input-not-frozen:' in f for f in findings)


def test_runtime_and_case_alias_remain_forbidden_with_approved_phase_scope(tmp_path, approved):
    scope, req, path, _ = approved
    value = candidate(tmp_path)
    hint = value['slice_hints'][0]
    hint['allowed_write_paths'] += ['runtime/phase-a/start.cs', 'phasea.platform/Node.cs']
    with scope.session(tmp_path, scope.load(tmp_path, req, path)):
        findings = _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, value)
    for name in ['runtime/phase-a/start.cs', 'phasea.platform/Node.cs']:
        assert any('phase-protected-path:'+name in f for f in findings)


def test_phase_scope_cannot_authorize_other_domain_writes(tmp_path, approved):
    scope, req, path, _ = approved
    value = candidate(tmp_path)
    value['slice_hints'][0]['allowed_write_paths'].append('scripts/sc/_llm_backend.py')
    with scope.session(tmp_path, scope.load(tmp_path, req, path)):
        findings = _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, value)
    assert any('outside-source-scope:scripts/sc/_llm_backend.py' in f for f in findings)


def test_exact_phase_readme_support_does_not_allow_other_phase_documents(tmp_path, approved):
    scope, req, path, value = approved
    value['support_paths'].append('PhaseA.Platform/README.md')
    path.write_text(json.dumps(value))
    selected = scope.load(tmp_path, req, path)
    result = candidate(tmp_path)
    hint = result['slice_hints'][0]
    hint['execution_snapshot_paths'] += [p for p, _h in selected.dependencies]
    hint['allowed_write_paths'].append('PhaseA.Platform/README.md')
    with scope.session(tmp_path, selected):
        assert not _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, result)
    value['support_paths'].append('PhaseA.Platform/appsettings.json')
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='source-scope:'):
        scope.load(tmp_path, req, path)


def test_checkpoint_identity_contains_verified_scope(tmp_path, approved):
    import semantic_v3_checkpoint as checkpoint
    scope, req, path, _ = approved
    with checkpoint.session(root=tmp_path, out_dir=tmp_path/'plan', enabled=True, resume=False):
        checkpoint.prepare(source_index={'sha256': 'source'}, obligations=[_obligation('O-1')], profile='resumable')
        original = checkpoint._current['identity']
        with scope.session(tmp_path, scope.load(tmp_path, req, path)):
            checkpoint.prepare(source_index={'sha256': 'source'}, obligations=[_obligation('O-1')], profile='resumable')
            changed = checkpoint._current['identity']
    assert 'source_scope' not in original
    assert changed['source_scope']['sha256']
    assert original != changed


def test_public_cli_validates_scope_before_admission_and_clears_context(tmp_path, approved, monkeypatch):
    import importlib.util
    import execution_preflight
    import semantic_phase_source_scope as scope
    scope_module, req, path, _ = approved
    entry = Path(__file__).resolve().parents[5]/'scripts/vdd/compile_plan.py'
    spec = importlib.util.spec_from_file_location('scope_cli_under_test', entry)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    seen = []
    def inspect(*args, **kwargs):
        seen.append(scope.description(tmp_path))
        return {'status': 'pending', 'authorizes': []}
    monkeypatch.setattr(execution_preflight, 'inspect_admission', inspect)
    monkeypatch.setattr(sys, 'argv', ['compile_plan.py', '--requirements', str(req),
        '--out-dir', str(tmp_path/'plan'), '--source-scope', str(path), '--admission-only'])
    assert cli.main() == 0
    assert seen[0]['task_id'] == 'S2-06'
    assert scope.description(tmp_path) is None
    path.write_text(path.read_text().replace('vdd.phase-source-scope.v1', 'unknown'))
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert len(seen) == 1


BUILD_METADATA = ['PhaseA.Platform/PhaseA.Platform.csproj',
                  'PhaseA.Platform/packages.lock.json']


@pytest.fixture(params=BUILD_METADATA)
def build_metadata(tmp_path, request):
    path = tmp_path/request.param
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<Project />\n' if path.suffix == '.csproj' else '{}\n')
    return request.param


def test_exact_existing_build_metadata_is_read_only_snapshot(tmp_path, approved, build_metadata):
    scope, req, path, value = approved
    value['read_paths'] = [build_metadata]
    path.write_text(json.dumps(value))
    selected = scope.load(tmp_path, req, path)
    assert selected.read_paths == frozenset([build_metadata])
    assert build_metadata not in selected.write_paths | selected.support_paths
    assert (build_metadata, hashlib.sha256((tmp_path/build_metadata).read_bytes()).hexdigest()) in selected.dependencies
    with scope.session(tmp_path, selected):
        bundle = scoped_bundle(selected)
        hint = bundle['slices'][0]
        assert not _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]},
                             dict(candidate(tmp_path), slice_hints=[hint]))
        scope.validate_bundle(tmp_path, bundle)
        assert bundle['source_scope']['authorizes'] == []


def test_build_metadata_changed_bytes_invalidate_current_scope(tmp_path, approved, build_metadata):
    scope, req, path, value = approved
    value['read_paths'] = [build_metadata]
    path.write_text(json.dumps(value))
    selected = scope.load(tmp_path, req, path)
    with scope.session(tmp_path, selected):
        (tmp_path/build_metadata).write_text('Changed production build metadata\n')
        with pytest.raises(ValueError, match='current dependency changed'):
            scope.description(tmp_path)


def test_build_metadata_must_be_frozen_in_every_hint(tmp_path, approved, build_metadata):
    scope, req, path, value = approved
    value['read_paths'] = [build_metadata]
    path.write_text(json.dumps(value))
    with scope.session(tmp_path, scope.load(tmp_path, req, path)):
        bundle = scoped_bundle(scope.current(tmp_path))
        hint = bundle['slices'][0]
        hint['execution_snapshot_paths'] = [p for p in hint['execution_snapshot_paths'] if p != build_metadata]
        assert any('phase-scope-input-not-frozen:'+build_metadata in f for f in
                   _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]},
                             dict(candidate(tmp_path), slice_hints=[hint])))
        with pytest.raises(ValueError, match='final dependency not frozen'):
            scope.validate_bundle(tmp_path, bundle)


@pytest.mark.parametrize('role', ['write_paths', 'support_paths'])
def test_build_metadata_cannot_be_declared_writable(tmp_path, approved, build_metadata, role):
    scope, req, path, value = approved
    value[role].append(build_metadata)
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='source-scope:'):
        scope.load(tmp_path, req, path)


@pytest.mark.parametrize('role', ['production_owners', 'allowed_write_paths',
    'planned_new_files', 'rollback'])
def test_read_only_build_metadata_cannot_enter_write_roles(tmp_path, approved, build_metadata, role):
    scope, req, path, value = approved
    value['read_paths'] = [build_metadata]
    path.write_text(json.dumps(value))
    with scope.session(tmp_path, scope.load(tmp_path, req, path)):
        bundle = scoped_bundle(scope.current(tmp_path))
        hint = bundle['slices'][0]
        hint['execution_snapshot_paths'].append(build_metadata)
        target = hint['rollback_scope']['production_paths'] if role == 'rollback' else hint[role]
        target.append(build_metadata)
        assert any('phase-protected-path:'+build_metadata in f for f in
                   _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]},
                             dict(candidate(tmp_path), slice_hints=[hint])))
        with pytest.raises(ValueError, match='final write outside scope'):
            scope.validate_bundle(tmp_path, bundle)


@pytest.mark.parametrize('when', ['load', 'current'])
def test_read_only_build_metadata_must_remain_existing(tmp_path, approved, build_metadata, when):
    scope, req, path, value = approved
    value['read_paths'] = [build_metadata]
    path.write_text(json.dumps(value))
    if when == 'load':
        (tmp_path/build_metadata).unlink()
        with pytest.raises(ValueError, match='missing file'):
            scope.load(tmp_path, req, path)
    else:
        selected = scope.load(tmp_path, req, path)
        (tmp_path/build_metadata).unlink()
        with scope.session(tmp_path, selected), pytest.raises(ValueError, match='missing file'):
            scope.description(tmp_path)


def test_build_metadata_symlink_is_rejected(tmp_path, approved, build_metadata):
    scope, req, path, value = approved
    (tmp_path/build_metadata).unlink()
    (tmp_path/build_metadata).symlink_to(tmp_path/'src/owner.py')
    value['read_paths'] = [build_metadata]
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='symlink path'):
        scope.load(tmp_path, req, path)


@pytest.mark.parametrize('read', ['PhaseA.Platform/Other.csproj',
    'PhaseA.Platform/Nested/PhaseA.Platform.csproj', 'PhaseA.Platform/other.lock.json',
    'PhaseA.Platform/appsettings.json', 'PhaseA.Platform/.env',
    'phasea.platform/PhaseA.Platform.csproj', './PhaseA.Platform/PhaseA.Platform.csproj',
    'PhaseA.Platform//PhaseA.Platform.csproj', 'PhaseA.Platform/../PhaseA.Platform/PhaseA.Platform.csproj',
    'PhaseA.Platform/*.csproj', 'PhaseA.Platform', 'runtime/phase-a/packages.lock.json'])
def test_build_metadata_allowance_is_exact(tmp_path, approved, read):
    scope, req, path, value = approved
    value['read_paths'] = [read]
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='source-scope:'):
        scope.load(tmp_path, req, path)


def test_build_metadata_worker_claim_cannot_enable_default_scope(tmp_path, build_metadata):
    value = candidate(tmp_path)
    value['slice_hints'][0]['execution_snapshot_paths'].append(build_metadata)
    payload = {'obligations': [_obligation('O-1')],
               'source_scope': {'read_paths': [build_metadata], 'approved': True}}
    assert any('phase-protected-path:'+build_metadata in f for f in
               _findings(tmp_path, 'v3', payload, value))


def test_build_metadata_explicit_forbidden_still_wins(tmp_path, approved, build_metadata):
    scope, req, path, value = approved
    value['read_paths'] = [build_metadata]
    path.write_text(json.dumps(value))
    with scope.session(tmp_path, scope.load(tmp_path, req, path)):
        result = candidate(tmp_path)
        hint = result['slice_hints'][0]
        hint['execution_snapshot_paths'] += [p for p, _ in scope.current(tmp_path).dependencies]
        hint['execution_snapshot_paths'].append(build_metadata)
        hint['forbidden_paths'] = [build_metadata]
        assert any('protected-forbidden-path:'+build_metadata in f for f in
                   _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, result))


@pytest.mark.parametrize('read', BUILD_METADATA + ['PhaseA.Platform/ReadOnly.cs', 'src/owner.py'])
@pytest.mark.parametrize('consumer', ['hint', 'bundle', 'context'])
@pytest.mark.parametrize('pattern', ['exact', 'glob'])
def test_final_consumers_reject_forbidden_read_snapshot(tmp_path, approved, read, consumer, pattern):
    scope, req, path, value = approved
    (tmp_path/read).write_text('Read-only dependency\n')
    if read.startswith('PhaseA.Platform/'):
        value['read_paths'] = [read]
    path.write_text(json.dumps(value))
    selected = scope.load(tmp_path, req, path)
    with scope.session(tmp_path, selected):
        bundle = scoped_bundle(selected)
        hint = bundle['slices'][0]
        if read not in hint['execution_snapshot_paths']:
            hint['execution_snapshot_paths'].append(read)
        scope.validate_hints(tmp_path, [hint])
        scope.validate_bundle(tmp_path, bundle)
        forbidden = read if pattern == 'exact' else read[:-1]+'?'
        if consumer == 'context':
            bundle['agent_contexts'][0]['forbidden_paths'] = [forbidden]
        else:
            hint['forbidden_paths'] = [forbidden]
        with pytest.raises(ValueError, match='final forbidden read: '+read):
            if consumer == 'hint':
                scope.validate_hints(tmp_path, [hint])
            else:
                scope.validate_bundle(tmp_path, bundle)


def test_installed_repair_forbidden_read_reaches_real_final_consumer(tmp_path, approved, build_metadata, monkeypatch):
    import semantic_v3_contract_repair as repair
    scope, req, path, value = approved
    value['read_paths'] = [build_metadata]
    path.write_text(json.dumps(value))
    selected = scope.load(tmp_path, req, path)
    raw = candidate(tmp_path)
    raw['slice_hints'][0]['execution_snapshot_paths'] += [p for p, _ in selected.dependencies]
    payload = {'obligations': [_obligation('O-1')]}
    contract = {
        'acceptance': {k: copy.deepcopy(v) for k, v in raw['acceptances'][0].items() if k != 'obligation_ids'},
        'failure_intents': [{k: copy.deepcopy(v) for k, v in raw['failure_intents'][0].items() if k != 'obligation_ids'}],
        'slice_hint': {k: copy.deepcopy(v) for k, v in raw['slice_hints'][0].items() if k != 'obligation_ids'},
    }
    contract['slice_hint']['forbidden_paths'] = [build_metadata]
    repair_path = tmp_path/'repair.json'
    repair_path.write_text(json.dumps({'schema': 'vdd.v3-candidate-repair.v1', 'authorizes': [],
        'requirements_sha256': 'sha256:'+hashlib.sha256(req.read_bytes()).hexdigest(),
        'obligation_contracts': {'O-1': contract}}))
    selected_repair = repair.load_repair(repair_path, req)
    seen = []
    def checked_fixture_worker(**kwargs):
        findings = _findings(tmp_path, kwargs['stage'], kwargs['payload'], raw)
        assert not findings, findings
        seen.append(kwargs['stage'])
        return copy.deepcopy(raw)
    monkeypatch.setattr(sc, 'invoke_worker', checked_fixture_worker)
    monkeypatch.setattr(sc, 'semantic_align', sc.semantic_align)
    monkeypatch.setattr(repair, '_ACTIVE_PATH_REPAIR', None)
    repair.install(selected_repair)
    with scope.session(tmp_path, selected):
        assert not _findings(tmp_path, 'v3', payload, raw)
        projected = repair.apply_repair(raw, {'input': payload}, selected_repair, tmp_path)
        assert projected['slice_hints'][0]['forbidden_paths'] == [build_metadata]
        assert build_metadata in projected['slice_hints'][0]['execution_snapshot_paths']
        with pytest.raises(ValueError, match='final forbidden read: '+build_metadata):
            sc.compile_acceptances(root=tmp_path, out_dir=tmp_path/'plan',
                                   obligations=payload['obligations'], worker_cache=None)
        assert seen == ['v3']
        receipts = list((tmp_path/'plan/.compiler-work/candidate-repairs').glob('*.json'))
        assert len(receipts) == 1
        assert json.loads(receipts[0].read_text())['authorizes'] == []
