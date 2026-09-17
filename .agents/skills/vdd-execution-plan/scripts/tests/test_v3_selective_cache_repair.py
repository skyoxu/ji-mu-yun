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


    def test_valid_cache_needs_no_worker(self):
        payload, original, cache, out, calls = setup_run(self.root, self, bad=False)
        repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert calls == []
        assert json.loads(cache.read_text()) == original


    def test_missing_planned_test_remains_eligible_for_cache_reuse(self):
        payload, original, cache, out, calls = setup_run(self.root, self)
        original['obligation_contracts']['O-2']['slice_hint']['planned_new_files'] = ['tests/test_missing.py']
        cache.write_text(json.dumps(original), encoding='utf-8')
        repair._live_group_repair(root=self.root, out_dir=out, payload=payload, prompt='Repair.')
        assert calls == []


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

if __name__ == "__main__":
    unittest.main()
