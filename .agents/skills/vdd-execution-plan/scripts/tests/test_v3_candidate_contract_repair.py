"""ADR-0041: bounded candidate input must not become semantic approval."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import semantic_v3_contract_repair as repair
from test_v3_selective_cache_repair import contract


class CandidateRepairTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for name in ['src/owner.py', 'tests/test_real.py']:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# fixture\n', encoding='utf-8')
        self.requirements = self.root / 'req.md'
        self.requirements.write_text('# FR-1\nReject invalid input.\n', encoding='utf-8')
        self.payload = {'original_stage': 'v3', 'input': {'obligations': [
            {'obligation_id': oid, 'source_refs': ['req.md#FR-1'], 'status': 'active',
             'requirement_type': 'Product', 'obligation_kind': 'behavior'}
            for oid in ['O-1', 'O-2']]}}
        self.original = {'obligation_contracts': {
            oid: contract('tests/test_real.py') for oid in ['O-1', 'O-2']}}
        self.projected = repair.group._project_current_output(
            self.original, repair.group._obligation_refs(self.payload))
        updated = deepcopy(self.original['obligation_contracts']['O-2'])
        updated['acceptance']['assertion_ids'] = ['CURRENT-ASSERTION']
        updated['failure_intents'][0]['failure_id'] = 'CURRENT_RED'
        updated['failure_intents'][0]['selector_intent'] = 'exercise the current rejection boundary'
        self.value = {'schema': 'vdd.v3-candidate-repair.v1', 'authorizes': [],
                      'requirements_sha256': 'sha256:' + hashlib.sha256(self.requirements.read_bytes()).hexdigest(),
                      'obligation_contracts': {'O-2': updated}}

    def load(self):
        path = self.root / 'repair.json'
        path.write_text(json.dumps(self.value), encoding='utf-8')
        return repair.load_repair(path, self.requirements)

    def test_only_selected_proof_and_execution_contract_changes(self):
        before = deepcopy(self.projected)
        result = repair.apply_repair(self.projected, self.payload, self.load(), self.root)
        for field in ['acceptances', 'failure_intents', 'slice_hints']:
            self.assertEqual([x for x in result[field] if x['obligation_ids'] == ['O-1']],
                             [x for x in before[field] if x['obligation_ids'] == ['O-1']])
        self.assertEqual(self.projected, before)
        self.assertEqual(result['acceptances'][-1]['assertion_ids'], ['CURRENT-ASSERTION'])
        self.assertEqual(result['failure_intents'][-1]['failure_id'], 'CURRENT_RED')
        self.assertEqual(repair.apply_repair(result, self.payload, self.value, self.root), result)

    def test_stale_source_and_authorizing_input_are_rejected(self):
        self.requirements.write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.load()
        self.value['authorizes'] = ['plan-ready']
        with self.assertRaisesRegex(ValueError, 'non-authorizing'):
            self.load()

    def test_foreign_source_reference_is_rejected(self):
        self.value['obligation_contracts']['O-2']['acceptance']['source_refs'] = ['req.md#OTHER']
        with self.assertRaisesRegex(ValueError, 'source binding'):
            repair.apply_repair(self.projected, self.payload, self.value, self.root)

    def test_missing_unplanned_selector_still_fails(self):
        hint = self.value['obligation_contracts']['O-2']['slice_hint']
        hint['execution_snapshot_paths'] = ['tests/missing.py']
        hint['validation_commands'] = [[sys.executable, '-m', 'pytest', 'tests/missing.py']]
        with self.assertRaisesRegex(ValueError, 'contract validation'):
            repair.apply_repair(self.projected, self.payload, self.value, self.root)

    def test_shared_contract_cannot_be_silently_split(self):
        self.projected['acceptances'][0]['obligation_ids'] = ['O-1', 'O-2']
        with self.assertRaisesRegex(ValueError, 'shared contract'):
            repair.apply_repair(self.projected, self.payload, self.value, self.root)

    def test_missing_target_contract_is_rejected(self):
        self.projected['failure_intents'] = self.projected['failure_intents'][:1]
        with self.assertRaisesRegex(ValueError, 'target missing'):
            repair.apply_repair(self.projected, self.payload, self.value, self.root)

    def install_fixture(self):
        self.base = self.enterContext(mock.patch.object(repair.group.sc, 'invoke_worker', return_value=self.projected))
        self.align = self.enterContext(mock.patch.object(repair.group.sc, 'semantic_align', return_value={
            'valid': False, 'findings': ['v4:still-misaligned']}))
        repair.install(self.value)

    def test_independent_v4_failure_is_preserved_and_no_cache_is_modified(self):
        self.install_fixture()
        out = self.root / 'plan'
        cache = out / '.compiler-cache' / 'prior.json'
        cache.parent.mkdir(parents=True)
        cache.write_text(json.dumps(self.original), encoding='utf-8')
        before = cache.read_bytes()
        result = repair.group.sc.invoke_worker(root=self.root, out_dir=out, stage="v3",
                                                 payload=self.payload['input'], prompt='normal V3')
        verdict = repair.group.sc.semantic_align(obligations=self.payload['input']['obligations'],
                                                acceptances=result['acceptances'])
        self.assertFalse(verdict['valid'])
        self.align.assert_called_once()
        self.assertEqual(cache.read_bytes(), before)
        repair.group.sc.invoke_worker(root=self.root, out_dir=out, stage="v3", payload=self.payload['input'], prompt='normal V3')
        self.assertEqual(len(list((out / '.compiler-work/candidate-repairs').glob('*.json'))), 1)

    def test_missing_final_domain_target_blocks_before_v4(self):
        self.install_fixture()
        with self.assertRaisesRegex(ValueError, 'final active domain'):
            repair.group.sc.semantic_align(obligations=self.payload['input']['obligations'][:1],
                                           acceptances=self.projected['acceptances'])
        self.align.assert_not_called()

    def test_cached_old_assertions_cannot_skip_candidate_consumption(self):
        self.install_fixture()
        with self.assertRaisesRegex(ValueError, 'not consumed'):
            repair.group.sc.semantic_align(obligations=self.payload['input']['obligations'],
                                           acceptances=self.projected['acceptances'])
        self.align.assert_not_called()

    def test_public_cli_rejects_completed_plan_before_any_worker(self):
        out = self.root / 'plan'
        out.mkdir()
        (out / 'compiler-state.v1.json').write_text('{"state":"plan-ready"}', encoding='utf-8')
        cli = Path(__file__).resolve().parents[5] / 'scripts/vdd/compile_plan.py'
        result = subprocess.run([sys.executable, str(cli), '--requirements', str(self.requirements),
                                 '--out-dir', str(out), '--v3-contract-repair', str(self.root / 'unused.json')],
                                capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)
        self.assertIn('failed or unpublished', result.stderr)
        self.assertFalse((out / '.compiler-work').exists())

    def test_public_cli_rejects_fixture_injection_with_candidate_repair(self):
        cli = Path(__file__).resolve().parents[5] / 'scripts/vdd/compile_plan.py'
        result = subprocess.run([sys.executable, str(cli), '--requirements', str(self.requirements),
                                 '--out-dir', str(self.root / 'plan'), '--v3-contract-repair', 'unused.json',
                                 '--worker-cache', 'unused-fixture.json'], capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)
        self.assertIn('cannot combine fixtures', result.stderr)

    def test_public_cli_requires_explicit_correction_for_published_reuse(self):
        cli = Path(__file__).resolve().parents[5] / 'scripts/vdd/compile_plan.py'
        result = subprocess.run([sys.executable, str(cli), '--requirements', str(self.requirements),
                                 '--out-dir', str(self.root / 'successor'),
                                 '--repair-published-v3-from', str(self.root / 'plan')],
                                capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)
        self.assertIn('requires --v3-contract-repair', result.stderr)

    def test_real_compiler_rebuilds_acceptance_and_red_links(self):
        self.install_fixture()
        acceptances, failures, hints = repair.group.sc.compile_acceptances(
            root=self.root, out_dir=self.root / 'plan',
            obligations=self.payload['input']['obligations'], worker_cache=None)
        target = next(a for a in acceptances if a['obligation_ids'] == ['O-2'])
        failure = next(f for f in failures if f['acceptance_ids'] == [target['acceptance_id']])
        self.assertEqual(target['assertion_ids'], ['CURRENT-ASSERTION'])
        self.assertEqual(failure['failure_id'], 'CURRENT_RED')
        self.assertEqual(target['red_intent_ids'], [failure['failure_intent_id']])
        self.assertEqual(len(hints), 2)

    def test_published_predecessor_requires_bound_bundle_and_empty_successor(self):
        predecessor = self.root / 'plan'
        predecessor.mkdir()
        successor = self.root / 'successor'
        bundle = {'schema_version': 'vdd.semantic-plan.v1', 'obligations': []}
        (predecessor / 'semantic-plan-bundle.v1.json').write_text(json.dumps(bundle), encoding='utf-8')
        (predecessor / 'compiler-state.v1.json').write_text(json.dumps({
            'state': 'plan-ready', 'semantic_plan_sha256': repair.group.sc.sha256_value(bundle),
        }), encoding='utf-8')
        entries = [{'repository_relative_source_path': 'req.md',
                    'source_sha256': repair.group.sc.sha256_bytes(self.requirements.read_bytes())}]
        (predecessor / 'source-index.v1.json').write_text(json.dumps({
            'entries': entries, 'sha256': repair.group.sc.sha256_value(entries),
        }), encoding='utf-8')
        (predecessor / 'semantic-alignment.v1.json').write_text('{"valid": true}', encoding='utf-8')
        (predecessor / 'atomic-recall-alignment.v1.json').write_text(json.dumps({
            'valid': True, 'worker': {'supported_obligation_ids': []},
        }), encoding='utf-8')
        with mock.patch('semantic_plan_contract.validate_semantic_bundle', return_value=(True, [])), \
             mock.patch('semantic_chain_audit.audit_bundle', return_value={'valid': True}):
            self.assertEqual(repair.load_published_predecessor(
                predecessor, successor, self.requirements, self.root)['bundle'], bundle)
            successor.mkdir()
            (successor / 'prior.txt').write_text('keep', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'empty successor'):
                repair.load_published_predecessor(predecessor, successor, self.requirements, self.root)
            (successor / 'prior.txt').unlink()
            successor.rmdir()
            (predecessor / 'compiler-state.v1.json').write_text(json.dumps({
                'state': 'plan-ready', 'semantic_plan_sha256': 'sha256:stale',
            }), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash-bound'):
                repair.load_published_predecessor(predecessor, successor, self.requirements, self.root)

    def test_published_predecessor_rejects_hash_bound_but_invalid_semantics(self):
        predecessor = self.root / 'plan'
        predecessor.mkdir()
        bundle = {'schema_version': 'invalid', 'obligations': []}
        (predecessor / 'semantic-plan-bundle.v1.json').write_text(json.dumps(bundle), encoding='utf-8')
        (predecessor / 'compiler-state.v1.json').write_text(json.dumps({
            'state': 'plan-ready', 'semantic_plan_sha256': repair.group.sc.sha256_value(bundle),
        }), encoding='utf-8')
        entries = [{'repository_relative_source_path': 'req.md',
                    'source_sha256': repair.group.sc.sha256_bytes(self.requirements.read_bytes())}]
        (predecessor / 'source-index.v1.json').write_text(json.dumps({
            'entries': entries, 'sha256': repair.group.sc.sha256_value(entries),
        }), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'semantic contract'):
            repair.load_published_predecessor(
                predecessor, self.root / 'successor', self.requirements, self.root)

    def test_published_v3_projection_preserves_unselected_oracle_and_failure(self):
        acceptance = deepcopy(self.projected['acceptances'][0])
        acceptance['acceptance_id'] = 'A-1'
        acceptance['red_intent_ids'] = ['FI-1']
        failure = deepcopy(self.projected['failure_intents'][0])
        failure['acceptance_ids'] = ['A-1']
        failure['failure_intent_id'] = 'FI-1'
        bundle = {'obligations': [self.payload['input']['obligations'][0]],
                  'acceptances': [acceptance], 'failure_intents': [failure],
                  'slices': [{'slice_id': 'S1', 'obligation_ids': ['O-1'],
                              'production_owners': ['src/owner.py'], 'verification_lane': 'unit',
                              'behavior_change': 'reject invalid input', 'affected_subjects': ['input'],
                              'state_transition': 'valid to rejected', 'rollback_scope': {
                                  'production_paths': ['src/owner.py'], 'state_or_schema_compatibility': 'none'},
                              'allowed_write_paths': ['src/owner.py'],
                              'execution_snapshot_paths': ['tests/test_real.py'],
                              'planned_new_files': [], 'terminal_predicate': 'pytest passes'}],
                  'agent_contexts': [{'slice_id': 'S1', 'forbidden_paths': [],
                                      'validation_commands': [['python', '-m', 'pytest', 'tests/test_real.py']]}]}
        raw = repair.project_published_v3(bundle)
        self.assertEqual(raw['acceptances'][0]['oracle'], acceptance['oracle'])
        self.assertEqual(raw['failure_intents'][0]['failure_id'], failure['failure_id'])
        self.assertEqual(raw['slice_hints'][0]['obligation_ids'], ['O-1'])
        self.assertEqual(raw['slice_hints'][0]['production_owners'], ['src/owner.py'])

    def test_published_v3_reuse_bypasses_only_v3_worker(self):
        raw = {'acceptances': [], 'failure_intents': [], 'slice_hints': []}
        with mock.patch.object(repair.group.sc, 'invoke_worker', return_value={'v4': 'fresh'}) as worker:
            repair.install_published_v3_reuse(raw)
            self.assertEqual(repair.group.sc.invoke_worker(
                root=self.root, out_dir=self.root, stage='v3', payload={}, prompt=''), raw)
            self.assertEqual(repair.group.sc.invoke_worker(
                root=self.root, out_dir=self.root, stage='v4', payload={}, prompt=''), {'v4': 'fresh'})
            worker.assert_called_once()

    def test_published_projection_must_pass_worker_schema_before_reuse(self):
        with self.assertRaisesRegex(ValueError, 'published V3 projection'):
            repair.validate_published_v3_projection(
                {'acceptances': [], 'failure_intents': [], 'slice_hints': []},
                self.payload['input']['obligations'], self.root)

    def test_published_successor_rejects_unselected_acceptance_drift(self):
        original = {'obligations': [{'obligation_id': 'O-1'}, {'obligation_id': 'O-2'}],
                    'acceptances': [
                        {'acceptance_id': 'A-1', 'obligation_ids': ['O-1'], 'oracle': {'expected': 'old'}},
                        {'acceptance_id': 'A-2', 'obligation_ids': ['O-2'], 'oracle': {'expected': 'old'}}],
                    'failure_intents': [], 'slices': []}
        current = deepcopy(original)
        current['acceptances'][1]['oracle']['expected'] = 'new'
        repair.check_unaffected_published_semantics(original, original, {'O-2'})
        with self.assertRaisesRegex(ValueError, 'unselected Acceptance drift'):
            repair.check_unaffected_published_semantics(original, current, {'O-1'})


if __name__ == '__main__':
    unittest.main()
