"""ADR-0041: complete input identity and bounded pre-validation corrections."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import semantic_compiler_authority
import semantic_v3_contract_repair as repair
import semantic_worker_v3_execution_contract_patch as execution
from test_v3_selective_cache_repair import contract


class TestPathInputRepairTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.old = 'scripts/tool/tests/test_boundary.py'
        self.new = 'tests/test_boundary.py'
        self.req = self.root / 'req.md'
        self.req.write_text('# FR-1\nPreserve boundary.\n', encoding='utf-8')
        self.value = {'obligation_contracts': {}}
        self.payload = {'input': {'obligations': []}}
        for oid in ('O-1', 'O-2'):
            c = contract(self.old)
            c['failure_intents'][0].update(failure_family='semantic-contract-gap',
                selector_intent=self.old + '::test_boundary')
            c['slice_hint'].update(production_owners=[], rollback_scope={
                'production_paths': [], 'state_or_schema_compatibility': 'unchanged'},
                allowed_write_paths=[self.old], planned_new_files=[self.old])
            self.value['obligation_contracts'][oid] = c
            self.payload['input']['obligations'].append(dict(obligation_id=oid,
                source_refs=['req.md#FR-1'], status='active', obligation_kind='constraint',
                requirement_type='Product'))
        self.correction = dict(schema='vdd.v3-candidate-repair.v1', authorizes=[],
            requirements_sha256='sha256:' + hashlib.sha256(self.req.read_bytes()).hexdigest(),
            source_index_sha256='sha256:' + '1' * 64,
            test_path_replacements={self.old: self.new},
            obligation_contracts=json.loads(json.dumps(self.value['obligation_contracts']).replace(self.old, self.new)))
        self.enterContext(mock.patch.object(repair, '_ACTIVE_PATH_REPAIR', self.correction))

    def apply(self, value=None, payload=None, stage='v3'):
        return execution.normalize_v3_cached_result(root=self.root, out_dir=self.root / 'plan',
            stage=stage, payload=(payload or self.payload) if stage.startswith('v3-schema-repair') else (payload or self.payload)['input'], value=value or self.value)

    def test_real_gate_rejects_old_then_accepts_bounded_group_without_mutating_input(self):
        before = deepcopy(self.value)
        with mock.patch.object(repair, '_ACTIVE_PATH_REPAIR', None):
            with self.assertRaisesRegex(ValueError, 'unowned-production-behavior'):
                self.apply(repair.group._project_current_output(self.value, repair.group._obligation_refs(self.payload)))
        result = self.apply()
        self.assertEqual(len(result['slice_hints']), 2)
        self.assertTrue(all(h['allowed_write_paths'] == [self.new] for h in result['slice_hints']))
        self.assertEqual(before, self.value)
        self.assertEqual(self.apply(result, stage='v3-schema-repair'), result)

    def test_single_contract_uses_same_early_gate(self):
        payload = deepcopy(self.payload)
        payload['input']['obligations'] = payload['input']['obligations'][:1]
        result = self.apply({'obligation_contracts': {'O-1': self.value['obligation_contracts']['O-1']}}, payload)
        self.assertEqual(len(result['slice_hints']), 1)
        self.assertEqual(result['slice_hints'][0]['allowed_write_paths'], [self.new])

    def test_semantic_correction_is_not_a_path_correction(self):
        self.correction['obligation_contracts']['O-1']['acceptance']['then'] = 'weakened'
        with self.assertRaisesRegex(ValueError, 'exceeds test path scope'):
            self.apply()

    def test_forged_ownerless_behavior_is_rejected(self):
        self.payload['input']['obligations'][0]['obligation_kind'] = 'behavior'
        with self.assertRaisesRegex(ValueError, 'ownerless constraint guard'):
            self.apply()

    def test_missing_or_wrong_full_identity_blocks(self):
        for index in ({}, {'sha256': 'sha256:' + '2' * 64}):
            with self.assertRaisesRegex(ValueError, 'source-index identity mismatch'):
                repair.validate_active_input(index)
        repair.validate_active_input({'sha256': self.correction['source_index_sha256']})

    def test_companion_bytes_must_be_represented_not_just_a_matching_digest(self):
        companion = self.root / 'companion.md'
        companion.write_text('Unindexed normative content.', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'does not bind complete companion bytes'):
            repair.validate_active_input({'sha256': self.correction['source_index_sha256'],
                                          'entries': []}, root=self.root, companions=[companion])

    def test_path_scope_rejects_escape_and_production_destination(self):
        for old, new in (('../tests/a.py', self.new), (self.old, 'src/owner.py')):
            self.correction['test_path_replacements'] = {old: new}
            p = self.root / 'repair.json'
            p.write_text(json.dumps(self.correction), encoding='utf-8')
            with self.assertRaises(ValueError):
                repair.load_repair(p, self.req)


    def test_public_cli_rejects_missing_drifted_and_wrong_companion_identity(self):
        repo = Path(__file__).resolve().parents[5]
        directory = Path(self.enterContext(tempfile.TemporaryDirectory(dir=repo / 'logs')))
        req, companion = directory / 'requirements.md', directory / 'companion.md'
        req.write_text('| <a id="SM-T01"></a>T01 | constraint | retain | planning | companion.md | Preserve boundary. |\n', encoding='utf-8')
        companion.write_text('Complete normative boundary.\n', encoding='utf-8')
        index = repair.group.sc.build_source_index(repo, req, [companion])
        correction = deepcopy(self.correction)
        correction['requirements_sha256'] = 'sha256:' + hashlib.sha256(req.read_bytes()).hexdigest()
        correction['source_index_sha256'] = index['sha256']
        path = directory / 'repair.json'
        for case in ('missing', 'drift', 'wrong'):
            with self.subTest(case=case):
                correction['source_index_sha256'] = index['sha256'] if case != 'wrong' else 'sha256:' + '0' * 64
                companion.write_text('Changed boundary.\n' if case == 'drift' else 'Complete normative boundary.\n', encoding='utf-8')
                path.write_text(json.dumps(correction), encoding='utf-8')
                argv = [sys.executable, '-B', str(repo / 'scripts/vdd/compile_plan.py'),
                        '--requirements', str(req), '--out-dir', str(directory / case),
                        '--v3-contract-repair', str(path)]
                if case != 'missing':
                    argv += ['--companion', str(companion)]
                result = subprocess.run(argv, cwd=repo, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('complete source-index identity mismatch', result.stdout + result.stderr)
                self.assertFalse((directory / case / '.compiler-work').exists())

if __name__ == '__main__':
    unittest.main()
