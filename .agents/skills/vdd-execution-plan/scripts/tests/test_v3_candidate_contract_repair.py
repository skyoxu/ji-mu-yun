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


if __name__ == '__main__':
    unittest.main()
