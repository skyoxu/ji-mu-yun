"""Stage orchestration regression for ADR-0005; no product tests are skipped."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'python'))
import ci_pipeline
import run_dotnet


class CiStageBudgetTests(unittest.TestCase):
    def test_pipeline_honors_configured_stage_and_all_selfcheck_attempts(self):
        calls = []
        def fake(args, cwd=None, timeout=900000):
            calls.append((list(args), timeout))
            return 0, ''
        with tempfile.TemporaryDirectory() as directory:
            old = os.getcwd()
            os.chdir(directory)
            try:
                with mock.patch.dict(os.environ, {'CI_DOTNET_STAGE_TIMEOUT_MS': '4200000'}), \
                     mock.patch.object(sys, 'argv', ['ci_pipeline.py', 'all', '--solution', 'Game.sln', '--godot-bin', 'godot', '--build-solutions']), \
                     mock.patch.object(ci_pipeline, 'resolve_test_solution_arg', return_value='Game.sln'), \
                     mock.patch.object(ci_pipeline, 'run_cmd', side_effect=fake), \
                     mock.patch.object(ci_pipeline, 'read_json', return_value={}):
                    self.assertEqual(0, ci_pipeline.main())
            finally:
                os.chdir(old)
        dotnet = next(item for item in calls if 'scripts/python/run_dotnet.py' in item[0])
        selfcheck = next(item for item in calls if 'run' in item[0] and 'scripts/python/godot_selfcheck.py' in item[0])
        self.assertEqual(4260000, dotnet[1])
        self.assertEqual(1380000, selfcheck[1])

    def test_dotnet_test_uses_remaining_stage_budget_and_failure_stays_failed(self):
        calls = []
        def fake(args, cwd=None, timeout=900000):
            calls.append((list(args), timeout))
            return (0, '') if 'restore' in args else (124, 'partial output')
        with tempfile.TemporaryDirectory() as directory:
            old = os.getcwd()
            os.chdir(directory)
            try:
                with mock.patch.dict(os.environ, {'CI_DOTNET_STAGE_TIMEOUT_MS': '4200000'}), \
                     mock.patch.object(sys, 'argv', ['run_dotnet.py', '--solution', 'Game.sln']), \
                     mock.patch.object(run_dotnet, 'resolve_test_solution_arg', return_value='Game.sln'), \
                     mock.patch.object(run_dotnet, 'resolve_dotnet', return_value='dotnet'), \
                     mock.patch.object(run_dotnet.time, 'monotonic', side_effect=[100.0, 102.0]), \
                     mock.patch.object(run_dotnet, 'run_cmd', side_effect=fake):
                    self.assertEqual(1, run_dotnet.main())
                import json
                summary_path = next(Path(directory).rglob('summary.json'))
                summary = json.loads(summary_path.read_text(encoding='utf-8'))
                self.assertEqual('tests_failed', summary['status'])
                self.assertEqual(124, summary['test_rc'])
            finally:
                os.chdir(old)
        self.assertEqual(900000, calls[0][1])
        self.assertEqual(4198000, calls[1][1])


if __name__ == '__main__':
    unittest.main()
