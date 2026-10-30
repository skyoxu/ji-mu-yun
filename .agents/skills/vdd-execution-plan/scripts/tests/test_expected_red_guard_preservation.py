"""Accepted ADR-0041: guard failures never acquire implementation RED authority."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parents[3]/'.agents/skills/quick-dev-tdd-adapter/tools'))
from semantic_worker_v3_execution_contract_patch import _normalize_expected_red_for_product_behavior
from semantic_worker_contract_patch import _worker_schema_findings
from semantic_worker_v3_expected_red_eligibility_patch import _expected_red_eligibility_findings
from quick_dev_handoff import handoff_findings
from case_evidence import contract_for

CASES = json.loads((Path(__file__).parent/'fixtures/expected_red_guard_returned.json').read_text())['cases']


def normalize(case, stage='v3'):
    obligation = deepcopy(case['obligation'])
    failures = [{**deepcopy(f), 'obligation_ids': [obligation['obligation_id']]}
                for f in case['raw_failure_intents']]
    value = {'failure_intents': failures}
    before = deepcopy(value)
    payload = {'obligations': [obligation]}
    if stage != 'v3':
        payload = {'input': payload}
    result = _normalize_expected_red_for_product_behavior(stage, payload, value)
    assert value == before
    return result, before, payload


@pytest.mark.parametrize('case', CASES, ids=lambda c:c['obligation']['obligation_id'])
@pytest.mark.parametrize('stage', ['v3', 'v3-schema-repair-chunk-01'])
def test_real_returned_contract_failure_roles_are_preserved(case, stage):
    result, before, payload = normalize(case, stage)
    expected = deepcopy(before)
    for f in expected['failure_intents']:
        if f['failure_family'] == 'task-implementation-failure':
            f['failure_family'] = 'expected-red'
            f['selector_intent'] += '; Negate required behavior: '+case['obligation']['expected_behavior']
    assert result == expected
    assert _expected_red_eligibility_findings(stage, payload, result) == []
    assert _normalize_expected_red_for_product_behavior(stage, payload, result) == result


@pytest.mark.parametrize('family', ['test-harness-failure','artifact-integrity','target-binding-failure',
    'semantic-contract-gap','timeout-no-observation','repo-noise','unexpected-green',
    'repeated-deterministic-failure','not-a-family',None])
def test_guard_and_unknown_families_are_not_silently_reclassified(family):
    case = deepcopy(CASES[0])
    case['raw_failure_intents'] = [{**case['raw_failure_intents'][0], 'failure_family': family}]
    result, before, _ = normalize(case)
    assert result == before
    if family not in {'test-harness-failure','artifact-integrity','target-binding-failure',
        'semantic-contract-gap','timeout-no-observation','repo-noise','unexpected-green','repeated-deterministic-failure'}:
        assert any('failure_family:invalid' in f for f in _worker_schema_findings('v3', result))


@pytest.mark.parametrize('kind,requirement_type', [('constraint','Platform'),('behavior','Governance'),
                                                 ('quality','Governance')])
def test_noneligible_implementation_failure_is_not_promoted(kind, requirement_type):
    case = deepcopy(next(c for c in CASES if c['obligation']['obligation_id']=='O-D37ED811069E'))
    case['obligation'].update(obligation_kind=kind, requirement_type=requirement_type)
    result, before, _ = normalize(case)
    assert result == before


def consumer_metadata():
    failures, assertions, acceptances, obligations, slices, contexts = [], [], [], [], [], []
    for index,case in enumerate(CASES):
        result, _, _ = normalize(case)
        aid = case['acceptance_id']
        ids = []
        for f in result['failure_intents']:
            # The consumer needs intent references, not a fabricated canonical
            # FI hash. Fixture-local indices are not published plan identities.
            key = f'fixture-intent-{len(failures)}'
            ids.append(key)
            failures.append({**f, 'acceptance_ids':[aid], 'failure_intent_id':key})
        assertions += [{'acceptance_id':aid, 'assertion_id':s} for s in case['assertion_ids']]
        acceptances.append({'acceptance_id':aid,'obligation_ids':[case['obligation']['obligation_id']],
                            'assertion_ids':case['assertion_ids'],'red_intent_ids':ids})
        obligations.append(case['obligation'])
        sid = f'S{index+1}'
        target = 'tests/test_contract.py'
        slices.append({'slice_id':sid,'acceptance_ids':[aid],'production_owners':['src/owner.py'],
                       'execution_snapshot_paths':[target],'planned_new_files':[target]})
        contexts.append({'slice_id':sid,'validation_commands':[['python','-m','pytest',target]],
                         'forbidden_paths':[]})
    return {'failure_intents':failures,'acceptances':acceptances,'obligations':obligations,
            'slices':slices,'agent_contexts':contexts}, assertions


def test_real_consumer_collects_only_two_business_red_markers():
    bundle, assertions = consumer_metadata()
    result = contract_for(bundle, assertions)
    expected = {'S206_AC08_REQUIRED_FIXTURE_BUSINESS_RESULTS_INCORRECT','S206_EF4E213E7263'}
    observed = {fid for row in result['bindings'] for fid in row['expected_failure_ids']}
    assert observed == expected
    for case in CASES:
        aid = case['acceptance_id']
        rows = [r for r in result['bindings'] if r['acceptance_id']==aid]
        if case['obligation']['obligation_id'] not in {'O-D37ED811069E','O-EF4E213E7263'}:
            assert rows and all(not r['expected_failure_ids'] for r in rows)


def test_fourteen_quality_guard_only_routes_still_fail_real_handoff():
    bundle, _ = consumer_metadata()
    findings = handoff_findings({**bundle,'behavior_routing':{}})
    missing = [f for f in findings if ':missing-behavior-red-route:' in f]
    assert len(missing) == 14
    guarded = {c['acceptance_id'] for c in CASES
               if c['obligation']['obligation_id'] not in {'O-D37ED811069E','O-EF4E213E7263'}}
    assert {f.rsplit(':',1)[1] for f in missing} == guarded
