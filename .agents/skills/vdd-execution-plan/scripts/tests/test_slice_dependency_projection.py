"""ADR-0041: source-derived edges and strict historical omission handling."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from execution_contract import derive_slice_dependencies, bind_slice_dependencies
from test_ch456_v3_total_coverage_and_slice_cohesion import _obligation, _acceptance, _hint
import semantic_slice_cohesion_patch as cohesion


def fixture():
    return ([_obligation('O-1'), _obligation('O-2', depends_on=['O-1'])],
            [{'slice_id': 'S1', 'obligation_ids': ['O-1']},
             {'slice_id': 'S2', 'obligation_ids': ['O-2']}])


def test_producer_emits_v1_edges_and_stable_hashes():
    obs, _ = fixture()
    acc = [_acceptance('O-1', 'A-1'), _acceptance('O-2', 'A-2')]
    failures = [{'failure_intent_id': 'FI-O-' + str(i), 'acceptance_ids': ['A-' + str(i)],
                 'failure_family': 'expected-red', 'selector_intent': f'tests/test_{i}.py'} for i in (1, 2)]
    hints = [{**_hint(f'tests/test_{i}.py'), 'obligation_ids': [f'O-{i}']} for i in (1, 2)]
    slices, _ = cohesion.cohesive_partition_slices(obs, acc, failures, hints)
    assert len(slices) == 2
    expected = derive_slice_dependencies(obs, slices)
    assert sum(map(len, expected.values())) == 1
    assert {s['slice_id']: s['depends_on'] for s in slices} == expected
    again, _ = cohesion.cohesive_partition_slices(obs, acc, failures, hints)
    assert slices == again


def test_missing_fields_fill_idempotently_without_changing_source():
    obs, slices = fixture()
    frozen = deepcopy(obs)
    expected = derive_slice_dependencies(obs, slices)
    assert expected == {'S1': [], 'S2': ['S1']}
    bind_slice_dependencies(slices, expected)
    snapshot = deepcopy(slices)
    bind_slice_dependencies(slices, expected)
    assert slices == snapshot and obs == frozen


@pytest.mark.parametrize('bad', [[], ['S2'], ['S1', 'S2'], ['MISSING'], ['S1', 'S1'], None, 'S1'])
def test_explicit_errors_reject_before_filling_any_omission(bad):
    obs, slices = fixture()
    expected = derive_slice_dependencies(obs, slices)
    slices[1]['depends_on'] = bad
    with pytest.raises(ValueError, match='explicit-edges-mismatch'):
        bind_slice_dependencies(slices, expected)
    assert 'depends_on' not in slices[0]


def test_prose_does_not_gain_authority():
    obs, slices = fixture()
    obs[1]['depends_on'] = ['S1', 'after core publication', 'see O-1']
    assert derive_slice_dependencies(obs, slices) == {'S1': [], 'S2': []}


@pytest.mark.parametrize('kind', ['dangling', 'cycle', 'self', 'duplicate_membership', 'contracted_cycle'])
def test_invalid_v1_or_membership_rejects(kind):
    obs, slices = fixture()
    if kind == 'dangling':
        obs[1]['depends_on'] = ['O-MISSING']
    elif kind == 'cycle':
        obs[0]['depends_on'] = ['O-2']
    elif kind == 'self':
        obs[0]['depends_on'] = ['O-1']
    elif kind == 'duplicate_membership':
        slices[1]['obligation_ids'].append('O-1')
    else:
        obs.append(_obligation('O-3', depends_on=['O-2']))
        slices[0]['obligation_ids'].append('O-3')
    with pytest.raises(ValueError, match='dependency:'):
        derive_slice_dependencies(obs, slices)
