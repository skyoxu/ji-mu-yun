"""ADR-0041/0043: never merge individually legal contexts into forbidden reads."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import semantic_compiler as sc
import semantic_feasibility_patch
import semantic_compiler_gate as gate
import semantic_phase_source_scope as scope
from execution_preflight import inspect_candidate
from test_phase_source_scope import approved
from test_ch456_v3_total_coverage_and_slice_cohesion import _obligation, _acceptance, _hint


@pytest.fixture
def contexts(tmp_path, approved):
    _, req, path, definition = approved
    read = 'PhaseA.Platform/Security/AccountIdentity.cs'
    p = tmp_path/read
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('class AccountIdentity {}\n')
    definition['read_paths'] = [read]
    definition['support_paths'] += ['tests/test_one.py', 'tests/test_two.py']
    path.write_text(json.dumps(definition))
    selected = scope.load(tmp_path, req, path)
    obligations = [_obligation('O-1'), _obligation('O-2')]
    acceptances = [_acceptance('O-1', 'A-1'), _acceptance('O-2', 'A-2')]
    hints, failures = [], []
    for i, test in enumerate(['tests/test_one.py', 'tests/test_two.py'], start=1):
        h = _hint(test)
        h.update(obligation_ids=[f'O-{i}'], production_owners=['PhaseA.Platform/Node.cs'],
                 allowed_write_paths=['PhaseA.Platform/Node.cs', test],
                 rollback_scope={'production_paths': ['PhaseA.Platform/Node.cs'],
                                 'state_or_schema_compatibility': 'backward-compatible'})
        h['execution_snapshot_paths'] += [p for p, _ in selected.dependencies]
        h.update(gate._preflight_contract(h))
        acceptances[i-1].update(gate._preflight_contract(h))
        hints.append(h)
        failures.append({'failure_intent_id': f'FI-O-{i}', 'failure_id': f'F-{i}',
            'acceptance_ids': [f'A-{i}'], 'failure_family': 'expected-red',
            'selector_intent': test, 'expected_outcome': 'fail'})
    hints[1]['execution_snapshot_paths'].append(read)
    return selected, (obligations, acceptances, failures, hints), read


@pytest.mark.parametrize('pattern', ['exact', 'prefix', 'glob', 'case-glob'])
@pytest.mark.parametrize('reverse', [False, True])
def test_selected_legal_hints_stay_legal_through_real_preflight(tmp_path, contexts, pattern, reverse):
    selected, inputs, read = contexts
    hints = inputs[3]
    hints[0]['forbidden_paths'] = [read if pattern == 'exact' else 'PhaseA.Platform/Security'
        if pattern == 'prefix' else 'PhaseA.Platform/Security/**' if pattern == 'glob'
        else 'phasea.platform/security/*']
    if reverse:
        for group in inputs:
            group.reverse()
    before = deepcopy(inputs)
    with scope.session(tmp_path, selected):
        for h in hints:
            scope.validate_hints(tmp_path, [h])
        result = inspect_candidate(sc, tmp_path, *inputs, profile='resumable')
        assert result['valid'], result
        slices, by = sc.partition_slices(*inputs)
        assert len(slices) == 2
        assert sorted(a for s in slices for a in s['acceptance_ids']) == ['A-1', 'A-2']
        assert sorted(o for s in slices for o in s['obligation_ids']) == ['O-1', 'O-2']
        projected = sc.agent_contexts(slices, *inputs[:2], by)
        for s,c in zip(slices, projected):
            original = by[s['acceptance_ids'][0]]
            assert set(c['forbidden_paths']) == set(original['forbidden_paths'])
            assert c['validation_commands'] == original['validation_commands']
            assert set(s['execution_snapshot_paths']) == set(original['execution_snapshot_paths'])
            assert s['production_owners'] == original['production_owners']
        assert inputs == before


@pytest.mark.parametrize('role', ['allowed_write_paths', 'planned_new_files', 'rollback'])
def test_selected_prefix_and_glob_write_conflicts_separate_without_mutating_inputs(tmp_path, contexts, role):
    selected, inputs, _ = contexts
    target = 'tests/test_two.py'
    h1,h2 = inputs[3]
    h1['forbidden_paths'] = ['tests/test_two*']
    h2['execution_snapshot_paths'] = [p for p in h2['execution_snapshot_paths'] if p != target]
    h2['allowed_write_paths'] = [p for p in h2['allowed_write_paths'] if p != target]
    h2['planned_new_files'] = []
    if role == 'rollback':
        h2['rollback_scope']['production_paths'].append(target)
    else:
        h2[role].append(target)
    before = deepcopy(inputs)
    with scope.session(tmp_path, selected):
        assert len(sc.partition_slices(*inputs)[0]) == 2
    assert inputs == before


@pytest.mark.parametrize('protected', [False, True])
def test_default_read_conflict_retains_existing_boundary_without_forged_scope(tmp_path, protected):
    from semantic_slice_cohesion_patch import cohesive_partition_slices
    obs = [_obligation('O-1'), _obligation('O-2')]
    acc = [_acceptance('O-1', 'A-1'), _acceptance('O-2', 'A-2')]
    hints = [{**_hint('tests/test_one.py'), 'obligation_ids': ['O-1']},
             {**_hint('tests/test_two.py'), 'obligation_ids': ['O-2']}]
    read = 'PhaseA.Platform/Security/AccountIdentity.cs' if protected else 'docs/source.md'
    hints[0]['forbidden_paths'] = [read.rsplit('/',1)[0]+'/**']
    hints[1]['execution_snapshot_paths'].append(read)
    # Payload dictionaries cannot select the private caller scope.
    hints[0]['source_scope'] = {'authorizes': ['read'], 'read_paths': [read]}
    with scope.session(tmp_path, None):
        slices,_ = cohesive_partition_slices(obs, acc, [], hints)
    assert len(slices) == (2 if protected else 1)


def test_selected_raw_self_conflict_remains_rejected(tmp_path, contexts):
    selected, inputs, read = contexts
    inputs[3][1]['forbidden_paths'] = [read]
    with scope.session(tmp_path, selected):
        result = inspect_candidate(sc, tmp_path, *inputs, profile='resumable')
        assert not result['valid'] and any('forbidden read' in f for f in result['findings'])
