"""ADR-0041/0043: exact caller dependencies are metadata, not legacy authority."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_phase_source_scope import approved, candidate
from test_ch456_v3_execution_contract import _obligation
import semantic_phase_source_scope as scope
from semantic_worker_v3_execution_contract_patch import _findings, _normalize_production_write_sets
from semantic_worker_v3_path_grounding_patch import ground_v3_paths


@pytest.fixture
def routed(tmp_path, approved):
    _, req, path, definition = approved
    for name in ('PhaseA.Platform/PhaseA.Platform.csproj', 'PhaseA.Platform/packages.lock.json'):
        p = tmp_path/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{}\n')
    definition['read_paths'] = ['PhaseA.Platform/PhaseA.Platform.csproj', 'PhaseA.Platform/packages.lock.json']
    definition['support_paths'] += ['PhaseA.Platform.Tests/Security/SnapshotTests.cs']
    path.write_text(json.dumps(definition))
    selected = scope.load(tmp_path, req, path)
    assert len(selected.dependencies) == 6
    value = candidate(tmp_path)
    h = value['slice_hints'][0]
    alias = 'PhaseA.Platform.Tests/Security/SnapshotTests.cs'
    h['execution_snapshot_paths'].append(alias)
    h['planned_new_files'].append(alias)
    h['allowed_write_paths'].append(alias)
    # A distinct selected class must not trigger a substring legacy match.
    h['validation_commands'].append(['dotnet', 'test', '--filter', 'FullyQualifiedName~S206SnapshotBoundaryTests'])
    return selected, value


@pytest.mark.parametrize('frozen', ['complete', 'three', 'none'])
def test_current_scope_preserves_contract_and_projects_only_exact_metadata(tmp_path, routed, frozen):
    selected, value = routed
    deps = [p for p, _ in selected.dependencies]
    value['slice_hints'][0]['execution_snapshot_paths'] += deps if frozen == 'complete' else deps[:3] if frozen == 'three' else []
    before = deepcopy(value)
    with scope.session(tmp_path, selected):
        grounded, changes = ground_v3_paths(tmp_path, {'obligations': [_obligation('O-1')]}, value)
        assert grounded == before and changes == []
        result = _normalize_production_write_sets(tmp_path, grounded)
        expected = deepcopy(before)
        expected['slice_hints'][0]['execution_snapshot_paths'] = list(dict.fromkeys([*before['slice_hints'][0]['execution_snapshot_paths'], *deps]))
        assert result == expected
        assert value == before
        assert not _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, result)
        scope.validate_hints(tmp_path, result['slice_hints'])
        assert _normalize_production_write_sets(tmp_path, result) == result


@pytest.mark.parametrize('defect', ['forbidden-read', 'unknown-write'])
def test_projection_keeps_explicit_boundaries_for_strict_gate(tmp_path, routed, defect):
    selected, value = routed
    h = value['slice_hints'][0]
    if defect == 'forbidden-read':
        h['forbidden_paths'] = [selected.dependencies[0][0]]
    else:
        h['allowed_write_paths'].append('PhaseA.Platform/Unknown.cs')
    with scope.session(tmp_path, selected):
        result = _normalize_production_write_sets(tmp_path, value)
        findings = _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, result)
        assert any(('protected-forbidden-path:' if defect == 'forbidden-read' else 'outside-source-scope:') in f for f in findings)
        with pytest.raises(ValueError, match='source-scope:'):
            scope.validate_hints(tmp_path, result['slice_hints'])


@pytest.mark.parametrize('dependency', range(6))
def test_projection_rechecks_each_current_dependency_before_use(tmp_path, routed, dependency):
    selected, value = routed
    with scope.session(tmp_path, selected):
        p = tmp_path/selected.dependencies[dependency][0]
        p.write_bytes(p.read_bytes()+b'changed\n')
        with pytest.raises(ValueError, match='dependency changed'):
            _normalize_production_write_sets(tmp_path, value)
        with pytest.raises(ValueError, match='dependency changed'):
            ground_v3_paths(tmp_path, {}, value)


@pytest.mark.parametrize('forged', [False, True])
def test_no_caller_scope_cannot_project_metadata_or_grant_phase(tmp_path, routed, forged):
    selected, value = routed
    if forged:
        value['source_scope'] = {'inputs': [{'path': p, 'sha256': h} for p, h in selected.dependencies]}
    with scope.session(tmp_path, None):
        result = _normalize_production_write_sets(tmp_path, value)
        assert all(p not in result['slice_hints'][0]['execution_snapshot_paths'] for p, _ in selected.dependencies)
        assert any('phase-protected-path:' in f for f in _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, result))


def test_default_legacy_path_and_selector_mapping_stays_compatible(tmp_path):
    value = candidate(tmp_path)
    value['slice_hints'][0]['execution_snapshot_paths'] = ['PhaseA.Platform.Tests/Security/SnapshotTests.cs']
    with scope.session(tmp_path, None):
        result, changes = ground_v3_paths(tmp_path, {}, value)
        assert changes
        canonical = 'PhaseA.Platform.Tests/PhaseB/Repair/SnapshotBoundaryTests.cs'
        assert result['slice_hints'][0]['execution_snapshot_paths'] == [canonical]
        result = _normalize_production_write_sets(tmp_path, result)
        assert canonical in result['slice_hints'][0]['planned_new_files']


def node_contract(tmp_path, approved, state):
    _, req, path, _ = approved
    selected = scope.load(tmp_path, req, path)
    value = candidate(tmp_path)
    node = 'tests/test_owner.py::test_value'
    h = value['slice_hints'][0]
    h['execution_snapshot_paths'] = [node]
    h['validation_commands'] = [['python', '-m', 'pytest', node]]
    if state == 'existing':
        target = tmp_path/'tests/test_owner.py'
        target.parent.mkdir(exist_ok=True)
        target.write_text('import pytest\n@pytest.mark.cer_assertion("ASSERT-LEDGER")\ndef test_value(): assert True\n')
        h['planned_new_files'] = []
    return selected, value, node


def consumer_bundle(hint):
    """Minimal real consumer contract; no semantic transport or gate is mocked."""
    return {'plan_id': 'scoped-node-contract',
        'obligations': [_obligation('O-1')],
        'acceptances': [{'acceptance_id': 'A1', 'obligation_ids': ['O-1'],
                         'assertion_ids': ['ASSERT-LEDGER'], 'red_intent_ids': ['F1']}],
        'failure_intents': [{'failure_intent_id': 'F1', 'failure_family': 'expected-red'}],
        'slices': [{**hint, 'slice_id': 'S1', 'acceptance_ids': ['A1'],
                    'proof': {'selector_intents': [hint['validation_commands'][0][-1]]}}],
        'agent_contexts': [{'slice_id': 'S1', 'acceptance_ids': ['A1'],
            'selector_intents': [hint['validation_commands'][0][-1]],
            'validation_commands': hint['validation_commands'], 'forbidden_paths': hint['forbidden_paths']}]}


@pytest.mark.parametrize('state', ['planned', 'existing'])
@pytest.mark.parametrize('consumer', ['handoff', 'q1'])
def test_selected_node_preserves_argv_and_reaches_real_consumer(tmp_path, approved, state, consumer):
    from quick_dev_handoff import handoff_findings
    tools = Path(__file__).resolve().parents[5]/'.agents/skills/quick-dev-tdd-adapter/tools'
    sys.path.insert(0, str(tools))
    from q1_planned_preflight import validate_planned_preflight
    selected, value, node = node_contract(tmp_path, approved, state)
    before = deepcopy(value)
    with scope.session(tmp_path, selected):
        normalized = _normalize_production_write_sets(tmp_path, value)
        bundle = consumer_bundle(normalized['slice_hints'][0])
        if consumer == 'handoff':
            # This writer owns execution-role checks; semantic route validation
            # remains an independent gate, not the subject of this fixture.
            assert handoff_findings({**bundle, 'behavior_routing': {}}, workspace=tmp_path) == []
        else:
            result = validate_planned_preflight(workspace=tmp_path, bundle=bundle,
                                               slice_id='S1', timeout_seconds=30)
            assert result['status'] == 'planned-contract-valid'
            assert result['target_refs'] == ['tests/test_owner.py']
            assert result['argv'] == ['python', '-m', 'pytest', node]
            assert not result['model_called'] and not result['tests_executed'] and not result['writes_performed']
        expected = deepcopy(before)
        expected['slice_hints'][0]['execution_snapshot_paths'] = ['tests/test_owner.py', *[p for p, _ in selected.dependencies]]
        assert normalized == expected and value == before
        scope.validate_hints(tmp_path, normalized['slice_hints'])


@pytest.mark.parametrize('defect', ['unplanned', 'symlink', 'escape'])
def test_selected_node_projection_keeps_unsafe_or_undeclared_inputs_rejected(tmp_path, approved, defect):
    selected, value, node = node_contract(tmp_path, approved, 'planned')
    h = value['slice_hints'][0]
    if defect == 'unplanned':
        h['planned_new_files'] = []
    elif defect == 'escape':
        h['execution_snapshot_paths'] = ['../outside.py::test_value']
        h['planned_new_files'] = ['../outside.py']
    else:
        target = tmp_path/'tests/test_owner.py'
        target.parent.mkdir(exist_ok=True)
        real = tmp_path/'other.py'
        real.write_text('def test_value(): pass\n')
        target.symlink_to(real)
    with scope.session(tmp_path, selected):
        if defect == 'symlink':
            with pytest.raises(ValueError, match='source-scope: symlink'):
                _normalize_production_write_sets(tmp_path, value)
        else:
            result = _normalize_production_write_sets(tmp_path, value)
            assert result['slice_hints'][0]['execution_snapshot_paths'][0] == h['execution_snapshot_paths'][0]
            assert _findings(tmp_path, 'v3', {'obligations': [_obligation('O-1')]}, result)
