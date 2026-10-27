"""ADR-0041: one Q7 invocation deduplicates originals, never edge authority."""
import json
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coverage_predicates as q7
import shared_execution
from runtime_evidence import sha256_value, sha256_bytes


def original(root):
    evidence = root / 'evidence'
    evidence.mkdir()
    dependency = root / 'dependency.txt'
    dependency.write_text('original')
    (root / 'plan.json').write_text('{}')
    descriptor = {'stage': 'regression', 'argv': ['python', '-m', 'pytest'], 'cwd': '.'}
    receipt = {'profile_identity': 'standard'}
    for name, data in [('descriptor.json', descriptor), ('process-receipt.v2.json', receipt),
                       ('reuse-request.v1.json', {'semantic_plan': 'plan.json', 'input': {
                           'files': {'dependency.txt': {'sha256': sha256_bytes(b'original')}},
                           'environment': {'files': {}}, 'engine': {}}})]:
        (evidence / name).write_text(json.dumps(data))
    return evidence, descriptor, receipt, dependency


def add(scope, evidence, descriptor, receipt):
    scope.saved(evidence, evidence / 'descriptor.json', descriptor,
                evidence / 'process-receipt.v2.json', receipt)


def test_same_original_checked_once_per_invocation(tmp_path, monkeypatch):
    evidence, descriptor, receipt, _ = original(tmp_path)
    calls = []
    monkeypatch.setattr(shared_execution, 'validate_saved_request', lambda *a: calls.append(a))
    progress = []
    scope = q7._Q7OriginalChecks(tmp_path, progress.append)
    for _ in range(139):
        add(scope, evidence, deepcopy(descriptor), deepcopy(receipt))
    assert calls == []  # No partially verified hit becomes edge authority.
    scope.finish()
    assert len(calls) == 1 and len(progress) == 1
    another = q7._Q7OriginalChecks(tmp_path, progress.append)
    add(another, evidence, descriptor, receipt)
    another.finish()
    assert len(calls) == 2  # No cross-call persistent cache.


@pytest.mark.parametrize('change', ['descriptor', 'receipt', 'path'])
def test_distinct_original_or_context_never_merges(tmp_path, monkeypatch, change):
    evidence, descriptor, receipt, _ = original(tmp_path)
    calls = []
    monkeypatch.setattr(shared_execution, 'validate_saved_request', lambda *a: calls.append(a))
    if change == 'path':
        (tmp_path / 'other/evidence').mkdir(parents=True)
    scope = q7._Q7OriginalChecks(tmp_path, lambda _: None)
    add(scope, evidence, descriptor, receipt)
    descriptor, receipt = deepcopy(descriptor), deepcopy(receipt)
    if change == 'descriptor':
        descriptor['argv'].append('-k different')
    elif change == 'receipt':
        receipt['profile_identity'] = 'self-hosted'
    else:
        evidence = tmp_path / 'other/evidence'
    add(scope, evidence, descriptor, receipt)
    scope.finish()
    assert len(calls) == 2


@pytest.mark.parametrize('change', ['content', 'replacement', 'new_dependency', 'empty_directory', 'environment', 'request'])
def test_mutation_during_validation_rejected(tmp_path, monkeypatch, change):
    evidence, descriptor, receipt, dependency = original(tmp_path)
    (tmp_path / 'empty').mkdir()
    def validate(*_):
        if change == 'content':
            dependency.write_text('changed!')
        elif change == 'replacement':
            replacement = tmp_path / 'replacement'
            replacement.write_text('original')
            replacement.replace(dependency)
        elif change == 'new_dependency':
            (tmp_path / 'new.py').write_text('new input')
        elif change == 'empty_directory':
            (tmp_path / 'empty/new.py').write_text('new input')
        elif change == 'environment':
            monkeypatch.setenv('Q7_REAL_TEST_INPUT', 'changed')
        else:
            (evidence / 'reuse-request.v1.json').write_text('{}')
    monkeypatch.setattr(shared_execution, 'validate_saved_request', validate)
    scope = q7._Q7OriginalChecks(tmp_path, lambda _: None)
    add(scope, evidence, descriptor, receipt)
    with pytest.raises(ValueError, match='changed during validation'):
        scope.finish()


def test_damaged_original_not_accepted_as_dedup_hit(tmp_path, monkeypatch):
    evidence, descriptor, receipt, _ = original(tmp_path)
    def validate(*_):
        raise ValueError('reuse-request-incomplete-or-tampered')
    monkeypatch.setattr(shared_execution, 'validate_saved_request', validate)
    progress = []
    scope = q7._Q7OriginalChecks(tmp_path, progress.append)
    for _ in range(5):
        add(scope, evidence, descriptor, receipt)
    with pytest.raises(ValueError, match='tampered'):
        scope.finish()
    assert progress == []


def test_each_edge_keeps_independent_identity_checks(tmp_path, monkeypatch):
    import case_evidence
    run = tmp_path / 'run'
    stage = run / 'canonical-evidence/regression'
    stage.mkdir(parents=True)
    (run / 'descriptors').mkdir()
    (tmp_path / 'test.py').write_text('pass')
    descriptor = {'cwd': '.', 'stage': 'regression'}
    receipt = {'case_report_sha256': 'report', 'target_hashes': {'test.py': sha256_bytes(b'pass')}}
    observation = {'receipt_sha256': sha256_value(receipt)}
    result = {}
    for path, data in [(run/'descriptors/regression.json', descriptor),
                       (stage/'receipt.json', receipt), (stage/'observation.json', observation),
                       (stage/'stage-result.v2.json', result)]:
        path.write_text(json.dumps(data))
    cases = {('A', 'AS1'): ['test.py::test_one'], ('A', 'AS2'): ['test.py::test_two']}
    monkeypatch.setattr(case_evidence, 'assertion_cases', lambda *a: cases)
    monkeypatch.setattr(shared_execution, 'validate_saved_request', lambda *a: None)
    scope = q7._Q7OriginalChecks(tmp_path, lambda _: None)
    edge = {'slice_id': 'S1', 'stage': 'regression', 'selector_identity': 'selector',
            'acceptance_id': 'A', 'assertion_id': 'AS1', 'case_ids': cases['A', 'AS1'],
            'case_evidence_schema': case_evidence.VERSION, 'case_report_sha256': 'report',
            'observation_ref': 'canonical-evidence/regression/observation.json',
            'receipt_ref': 'canonical-evidence/regression/receipt.json',
            'observation_sha256': sha256_value(observation), 'receipt_sha256': sha256_value(receipt),
            'descriptor_sha256': sha256_value(descriptor), 'target_ref': 'test.py', 'fixture_ref': 'test.py',
            'target_sha256': sha256_bytes(b'pass'), 'fixture_sha256': sha256_bytes(b'pass'),
            'predicate_result': True, 'observed': True}
    def check(value):
        path = run/'edge.json'
        path.write_text(json.dumps(value))
        return q7._reread_edge(tmp_path, run, {'path': 'edge.json', 'sha256': sha256_value(value)},
            slice_id='S1', stage='regression', selector_identity='selector', originals=scope)
    check(edge)
    other = {**edge, 'assertion_id': 'AS2', 'case_ids': cases['A', 'AS2']}
    check(other)
    with pytest.raises(ValueError, match='case-edge-binding-stale'):
        check({**other, 'case_ids': cases['A', 'AS1']})
    with pytest.raises(ValueError, match='identity stale'):
        check({**other, 'selector_identity': 'wrong'})


def test_genuine_completion_does_not_reset_unit_total():
    from workflow_unit_budget import Budget
    budget = Budget(total=1800, idle=600)
    budget.apply({'event': 'start', 'at': 0, 'call': 'Q7', 'key': 'same-input', 'label': 'Q7'})
    for at in (500, 1000, 1500):
        budget.apply({'event': 'progress', 'at': at, 'call': 'Q7', 'digest': 'completed:' + str(at)})
    assert budget.tick(1800)['reason'] == 'unit-total'


def test_139_edges_check_three_q6_originals_and_main_only_four_times(tmp_path, monkeypatch):
    import regression_gate
    main = tmp_path / 'main'
    main.mkdir()
    evidence, descriptor, receipt, _ = original(main)
    commands = []
    for index in range(3):
        root = tmp_path / str(index)
        root.mkdir()
        other, desc, rec, _ = original(root)
        rec.update({'stdout_sha256': sha256_bytes(b''), 'stderr_sha256': sha256_bytes(b'')})
        (other/'process-receipt.v2.json').write_text(json.dumps(rec))
        (other/'stdout.bin').write_bytes(b'')
        (other/'stderr.bin').write_bytes(b'')
        commands.append({'receipt_ref': str((other/'process-receipt.v2.json').relative_to(tmp_path)),
                         'receipt_sha256': sha256_value(rec), 'descriptor': desc})
    gate = {'commands': commands}
    gate_path = tmp_path/'gate.json'
    gate_path.write_text(json.dumps(gate))
    calls, gates = [], []
    monkeypatch.setattr(shared_execution, 'admissible', lambda r: None)
    monkeypatch.setattr(shared_execution, 'validate_saved_request', lambda *a: calls.append(a))
    real = regression_gate.validate_regression_references
    def validate(*a, **kw):
        gates.append(1)
        return real(*a, **kw)
    monkeypatch.setattr(regression_gate, 'validate_regression_references', validate)
    scope = q7._Q7OriginalChecks(tmp_path, lambda _: None)
    for _ in range(139):
        scope.gate(gate_path, deepcopy(gate))
        add(scope, evidence, deepcopy(descriptor), deepcopy(receipt))
    scope.finish()
    assert len(calls) == 4 and len(gates) == 1
    (tmp_path/'0/evidence/stdout.bin').write_bytes(b'tampered')
    other_scope = q7._Q7OriginalChecks(tmp_path, lambda _: None)
    with pytest.raises(ValueError, match='Q6 original output changed'):
        other_scope.gate(gate_path, gate)
