"""ADR-0041: repair invalid V3 contracts without regenerating valid peers."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import types

import unittest
from unittest import mock
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import semantic_worker_v3_group_repair_patch as repair


def contract(target):
    return {
        'acceptance': {'source_refs': ['req.md#FR-1'], 'given': 'input', 'when': 'checked',
                       'then': 'rejected', 'oracle': {'observable': 'verdict', 'expected': 'reject', 'forbidden': ['accept']},
                       'assertion_ids': ['ASSERT-REJECT']},
        'failure_intents': [{'failure_family': 'expected-red', 'selector_intent': 'assert rejection',
                            'expected_outcome': 'fail', 'failure_id': 'REJECT'}],
        'slice_hint': {'production_owners': ['src/owner.py'], 'verification_lane': 'unit',
                       'behavior_change': 'reject invalid input', 'affected_subjects': ['input'],
                       'state_transition': 'unchecked -> rejected',
                       'rollback_scope': {'production_paths': ['src/owner.py'], 'state_or_schema_compatibility': 'compatible'},
                       'allowed_write_paths': ['src/owner.py'], 'execution_snapshot_paths': [target],
                       'planned_new_files': [], 'terminal_predicate': 'rejection observed', 'forbidden_paths': [],
                       'validation_commands': [[sys.executable, '-m', 'pytest', target]]},
    }


def setup_run(tmp_path, monkeypatch, bad=True):
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src/owner.py').write_text('value = 1\n')
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/test_real.py').write_text('def test_real(): assert True\n')
    payload = {'original_stage': 'v3', 'input': {'obligations': [
        {'obligation_id': oid, 'source_refs': ['req.md#FR-1'], 'status': 'active',
         'requirement_type': 'Product', 'obligation_kind': 'behavior'} for oid in ['O-1', 'O-2']
    ]}, 'validator_findings': ['selector target missing']}
    original = {'obligation_contracts': {
        'O-1': contract('tests/test_real.py'),
        'O-2': contract('tests/test_missing.py' if bad else 'tests/test_real.py'),
    }}
    out = tmp_path / 'plan'
    cache = out / '.compiler-cache' / repair.sc._worker_cache_key(
        repair._GROUP_STAGE + '-chunk-01', repair._narrow_repair_payload(payload, ['O-1', 'O-2']))
    repair.sc.atomic_json(cache, original)
    monkeypatch.enterContext(mock.patch.object(repair, 'enrich_repository_context', lambda root, value: value))
    calls = []
    def run(**kwargs):
        request = json.loads(kwargs['prompt'].rsplit('\n\nINPUT:\n', 1)[1])
        ids = [o['obligation_id'] for o in request['input']['obligations']]
        calls.append((ids, kwargs['prompt']))
        value = {'obligation_contracts': {oid: contract('tests/test_real.py') for oid in ids}}
        kwargs['output_last_message'].write_text(json.dumps(value), encoding='utf-8')
        return 0, '', []
    monkeypatch.enterContext(mock.patch.dict(sys.modules, {'_llm_backend': types.SimpleNamespace(
        run_llm_exec=run, resolve_llm_backend=lambda _: 'fixture')}))
    return payload, original, cache, out, calls


class SelectiveCacheRepairTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(temporary)

    def test_oracle_repair_context_contains_only_exact_conflicting_peers(self):
        """ADR-0041: unrelated proofs must not crowd frozen input out of context."""
        acceptance = contract('tests/test_real.py')['acceptance']
        values = [dict(deepcopy(acceptance), obligation_ids=[oid]) for oid in ('O-1', 'O-2', 'O-3')]
        values[2]['oracle']['expected'] = 'an unrelated result'
        summary = repair._conflicting_oracle_peers({'acceptances': values}, 'O-1')
        assert set(summary) == {'O-2'}
        assert summary['O-2']['oracle'] == values[1]['oracle']
        assert repair._conflicting_oracle_peers({'acceptances': values}, 'O-3') == {}

    def test_parent_merge_passes_only_conflicting_peers_to_worker(self):
        obligations = [dict(obligation_id=f'O-{i}', status='active', source_refs=['req.md#FR-1'],
                            requirement_type='Product', obligation_kind='behavior',
                            expected_behavior=f'behavior {i}') for i in range(5)]
        forced = []
        def worker(**kwargs):
            payload = kwargs['payload']
            values = {}
            for item in payload['input']['obligations']:
                oid = item['obligation_id']
                value = contract('tests/test_real.py')
                if oid not in ('O-0', 'O-4') or payload.get('_force_semantic_repair'):
                    value['acceptance']['oracle']['expected'] = oid
                values[oid] = value
            if payload.get('_force_semantic_repair'):
                forced.append(kwargs['prompt'])
                assert '"O-1"' not in kwargs['prompt']
                assert '"O-2"' not in kwargs['prompt']
                assert '"O-3"' not in kwargs['prompt']
            return repair._project({'obligation_contracts': values})
        self.enterContext(mock.patch.object(repair, '_live_group_repair_one', worker))
        payload = {'input': {'obligations': obligations}}
        result = repair._live_group_repair(
            root=self.root, out_dir=self.root / 'plan', payload=payload, prompt='Repair.')
        assert len(forced) == 2
        assert repair.v3_domain._domain_findings('v3-schema-repair', payload, result) == []

    def test_only_invalid_contract_is_requested_and_prior_cache_is_preserved(self):
        payload, original, cache, out, calls = setup_run(self.root, self)
        old_bytes = cache.read_bytes()
        result = repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert [ids for ids, _ in calls] == [['O-2']]
        assert 'tests/test_missing.py' in calls[0][1]
        refreshed = json.loads(cache.read_text())
        assert refreshed['obligation_contracts']['O-1'] == original['obligation_contracts']['O-1']
        assert any(p.read_bytes() == old_bytes for p in cache.parent.glob(cache.name + '.stale-*'))
        assert not repair.sc._v3_cache_requires_contract_refresh(result, self.root, payload)

    def test_parent_reuses_repaired_peers_only_after_complete_domain_validation(self):
        """ADR-0041: completed singleton repairs survive stale positional child caches."""
        payload, _, _, out, calls = setup_run(self.root, self, bad=False)
        payload['input']['obligations'] = [
            dict(payload['input']['obligations'][0], obligation_id=f'O-{i}', expected_behavior=f'behavior {i}')
            for i in range(5)
        ]
        repaired = {}
        for item in payload['input']['obligations']:
            oid = item['obligation_id']
            value = contract('tests/test_real.py')
            value['acceptance']['oracle']['expected'] = oid
            repaired[oid] = value
        for oid, value in repaired.items():
            repair.sc.atomic_json(out / '.compiler-cache' / (repair._GROUP_STAGE + '-repaired-' + oid + '.json'),
                                  {'obligation_contracts': {oid: value}})
        repair.sc.atomic_json(out / '.compiler-cache' / (repair._GROUP_STAGE + '-replayed-children.json'),
                              {'obligation_contracts': {oid: contract('tests/test_real.py') for oid in repaired}})
        self.enterContext(mock.patch.object(repair, '_contract_matches_obligation', return_value=True))
        recovered = repair._reusable_prior_contracts(
            root=self.root, cache_dir=out / '.compiler-cache', payload=payload, ids=sorted(repaired))
        assert {oid: value['acceptance']['oracle']['expected'] for oid, value in recovered.items()} == {
            oid: oid for oid in repaired}

        def stale_child(**kwargs):
            assert not kwargs['payload'].get('_force_semantic_repair'), 'validated repairs must be reused'
            return repair._project({'obligation_contracts': {
                item['obligation_id']: contract('tests/test_real.py')
                for item in kwargs['payload']['input']['obligations']
            }})

        self.enterContext(mock.patch.object(repair, '_live_group_repair_one', stale_child))
        result = repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert repair.v3_domain._domain_findings('v3-schema-repair', payload, result) == []
        assert calls == []


    def test_valid_cache_needs_no_worker(self):
        payload, original, cache, out, calls = setup_run(self.root, self, bad=False)
        repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert calls == []
        assert json.loads(cache.read_text()) == original

    def test_empty_required_fields_repair_only_the_invalid_cached_contract(self):
        """ADR-0041: cache admission must use the current publication schema."""
        import semantic_worker_contract_patch as contract_schema
        self.enterContext(mock.patch.object(
            repair.gate, '_worker_schema_findings', contract_schema._worker_schema_findings))
        payload, original, cache, out, calls = setup_run(self.root, self, bad=False)
        hint = original['obligation_contracts']['O-2']['slice_hint']
        hint['production_owners'] = []
        hint['rollback_scope']['production_paths'] = []
        cache.write_text(json.dumps(original), encoding='utf-8')
        result = repair._live_group_repair(
            root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert [ids for ids, _ in calls] == [['O-2']]
        assert repair.gate._worker_schema_findings('v3', result) == []
        assert json.loads(cache.read_text())['obligation_contracts']['O-1'] == original['obligation_contracts']['O-1']


    def test_missing_planned_test_remains_eligible_for_cache_reuse(self):
        payload, original, cache, out, calls = setup_run(self.root, self)
        original['obligation_contracts']['O-2']['slice_hint']['planned_new_files'] = ['tests/test_missing.py']
        cache.write_text(json.dumps(original), encoding='utf-8')
        repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert calls == []

    def test_missing_unplanned_production_owner_invalidates_cache(self):
        payload, original, cache, out, calls = setup_run(self.root, self, bad=False)
        hint = original['obligation_contracts']['O-1']['slice_hint']
        hint['production_owners'] = ['src/missing_owner.py']
        hint['allowed_write_paths'] = ['src/missing_owner.py']
        hint['planned_new_files'] = []
        cache.write_text(json.dumps(original), encoding='utf-8')
        repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert [ids for ids, _ in calls] == [['O-1']]

    def test_pytest_node_snapshot_reuses_existing_or_planned_file(self):
        """ADR-0041: selector suffixes do not invalidate an admitted file target."""
        payload, original, cache, out, calls = setup_run(self.root, self, bad=False)
        for target, planned, expected in (
            ('tests/test_real.py::test_real', [], False),
            ('tests/test_real.py::TestReal::test_case[value]', [], False),
            ('tests/test_missing.py::test_new', ['tests/test_missing.py'], False),
            ('tests/test_missing.py::test_new', [], True),
        ):
            with self.subTest(target=target, planned=planned):
                value = deepcopy(original)
                hint = value['obligation_contracts']['O-1']['slice_hint']
                hint['execution_snapshot_paths'] = [target]
                hint['planned_new_files'] = planned
                assert repair.sc._v3_cache_requires_contract_refresh(value, self.root, payload) is expected


    def test_repeated_missing_selector_still_fails_execution_contract(self):
        from semantic_worker_v3_execution_contract_patch import _findings
        payload, original, cache, out, calls = setup_run(self.root, self)
        def broken_worker(**kwargs):
            request = json.loads(kwargs['prompt'].rsplit('\n\nINPUT:\n', 1)[1])
            ids = [o['obligation_id'] for o in request['input']['obligations']]
            value = {'obligation_contracts': {oid: contract('tests/test_missing.py') for oid in ids}}
            kwargs['output_last_message'].write_text(json.dumps(value), encoding='utf-8')
            return 0, '', []
        self.enterContext(mock.patch.object(sys.modules['_llm_backend'], 'run_llm_exec', broken_worker))
        result = repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        findings = _findings(self.root, 'v3-schema-repair', payload, result)
        assert any('selector-target-missing-not-planned' in f for f in findings)

    def test_changed_group_input_reuses_each_executable_contract(self):
        payload, original, cache, out, calls = setup_run(self.root, self, bad=False)
        payload['input']['frozen_source_index_sha256'] = 'sha256:new-input'
        repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert calls == []
        assert json.loads(cache.read_text()) == original

    def test_changed_group_input_requests_only_the_unusable_contract(self):
        payload, original, cache, out, calls = setup_run(self.root, self)
        payload['input']['frozen_source_index_sha256'] = 'sha256:new-input'
        repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert [ids for ids, _ in calls] == [['O-2']]

    def test_governance_failure_intent_does_not_invalidate_an_executable_contract(self):
        payload, original, cache, out, calls = setup_run(self.root, self, bad=False)
        payload['input']['obligations'][0].update({'requirement_type': 'Governance', 'obligation_kind': 'constraint'})
        repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert calls == []

    def test_phase_path_is_not_a_cache_refresh_reason(self):
        payload, original, cache, out, calls = setup_run(self.root, self, bad=False)
        original['obligation_contracts']['O-1']['slice_hint']['production_owners'] = ['PhaseA.Platform/Program.cs']
        cache.write_text(json.dumps(original), encoding='utf-8')
        repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert calls == []

    def test_unknown_cached_obligation_is_not_silently_dropped(self):
        payload, original, cache, out, calls = setup_run(self.root, self)
        original['obligation_contracts']['O-FOREIGN'] = deepcopy(original['obligation_contracts']['O-1'])
        cache.write_text(json.dumps(original), encoding='utf-8')
        with self.assertRaises(ValueError):
            repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert calls == []

    def test_semantically_identical_renamed_obligation_is_rebound_without_worker(self):
        (self.root / 'src').mkdir()
        (self.root / 'src/owner.py').write_text('value = 1\n')
        (self.root / 'tests').mkdir()
        (self.root / 'tests/test_real.py').write_text('def test_real(): assert True\n')
        payload = {'original_stage': 'v3', 'input': {'obligations': [{
            'obligation_id': 'O-NEW', 'source_refs': ['req.md#FR-1'], 'status': 'active',
            'subject': 'input', 'expected_behavior': 'reject invalid input',
            'observable_result': 'verdict is rejected',
        }]}}
        cached = contract('tests/test_real.py')
        cached['acceptance'].update({
            'source_refs': ['req.md#FR-1'], 'given': 'input is invalid',
            'when': 'the operation runs', 'then': 'reject invalid input',
        })
        cached['acceptance']['oracle'].update({
            'observable': 'verdict is rejected', 'expected': 'rejected',
        })
        cached['slice_hint']['affected_subjects'] = ['input']
        out = self.root / 'plan'
        cache_dir = out / '.compiler-cache'
        cache_dir.mkdir(parents=True)
        path = cache_dir / (repair._GROUP_STAGE + '-chunk-01.json')
        repair.sc.atomic_json(path, {'obligation_contracts': {'O-OLD': cached}})
        recovered = repair._reusable_prior_contracts(
            root=self.root, cache_dir=cache_dir, payload=payload, ids=['O-NEW'])
        assert set(recovered) == {'O-NEW'}
        assert recovered['O-NEW']['acceptance']['source_refs'] == ['req.md#FR-1']

    def test_semantic_mismatch_or_ambiguous_match_is_not_rebound(self):
        payload = {'original_stage': 'v3', 'input': {'obligations': [{
            'obligation_id': 'O-NEW', 'source_refs': ['req.md#FR-1'], 'status': 'active',
            'subject': 'input', 'expected_behavior': 'reject invalid input',
            'observable_result': 'verdict is rejected',
        }]}}
        first = contract('tests/test_real.py')
        first['acceptance'].update({'source_refs': ['req.md#FR-1'], 'then': 'reject invalid input'})
        first['acceptance']['oracle']['observable'] = 'verdict is rejected'
        first['slice_hint']['affected_subjects'] = ['input']
        second = json.loads(json.dumps(first))
        out = self.root / 'plan'; cache_dir = out / '.compiler-cache'; cache_dir.mkdir(parents=True)
        repair.sc.atomic_json(cache_dir / (repair._GROUP_STAGE + '-chunk-01.json'),
                              {'obligation_contracts': {'O-A': first, 'O-B': second}})
        assert repair._reusable_prior_contracts(
            root=self.root, cache_dir=cache_dir, payload=payload, ids=['O-NEW']) == {}

    def test_global_v3_validation_identifies_only_bad_cached_contract_ids(self):
        payload = {'original_stage': 'v3', 'input': {'obligations': [
            {'obligation_id': 'O-1', 'source_refs': ['req.md#FR-1'], 'status': 'active',
             'subject': 'first', 'trigger': 'run', 'state_before': 'before', 'state_after': 'after',
             'expected_behavior': 'first behavior', 'observable_result': 'first result',
             'obligation_kind': 'constraint', 'requirement_type': 'Platform'},
            {'obligation_id': 'O-2', 'source_refs': ['req.md#FR-1'], 'status': 'active',
             'subject': 'second', 'trigger': 'run', 'state_before': 'before', 'state_after': 'after',
             'expected_behavior': 'second behavior', 'observable_result': 'second result',
             'obligation_kind': 'behavior', 'requirement_type': 'Platform'},
        ]}}
        first, second = contract('tests/test_real.py'), contract('tests/test_real.py')
        for item in (first, second):
            item['acceptance']['source_refs'] = ['req.md#FR-1']
            item['acceptance']['assertion_ids'] = ['SHARED']
            item['failure_intents'][0]['failure_family'] = 'expected-red'
        bad = repair._invalid_contract_ids(payload, {'O-1': first, 'O-2': second})
        assert bad == {'O-1', 'O-2'}

    def test_missing_candidate_identity_fixture_is_declared_planned(self):
        value = {'slice_hint': {
            'execution_snapshot_paths': ['.agents/skills/quick-dev-tdd-adapter/tools/fixtures/candidate-identity.v1.json'],
            'planned_new_files': [],
        }}
        repair._declare_supported_missing_fixture(value)
        assert value['slice_hint']['planned_new_files'] == [
            '.agents/skills/quick-dev-tdd-adapter/tools/fixtures/candidate-identity.v1.json']

if __name__ == "__main__":
    unittest.main()
