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
    def test_runtime_preflight_requires_both_successful_process_and_readiness_result(self):
        import json
        for rc, result, expected in ((0, {}, 1), (0, {'status': 'fail'}, 1),
                                     (2, {'status': 'ok'}, 1), (0, {'status': 'ok'}, 0)):
            with self.subTest(rc=rc, result=result), tempfile.TemporaryDirectory() as directory:
                old = os.getcwd()
                os.chdir(directory)
                try:
                    with mock.patch.object(ci_pipeline, 'run_cmd', return_value=(rc, 'runtime output')), \
                         mock.patch.object(ci_pipeline, 'read_json', return_value=result):
                        self.assertEqual(expected, ci_pipeline.run_runtime_preflight('godot', 'project.godot'))
                    summary = json.loads(next(Path(directory).rglob('runtime-preflight-summary.json')).read_text())
                    self.assertEqual('runtime_preflight_only', summary['scope'])
                    self.assertEqual('ok' if expected == 0 else 'fail', summary['status'])
                    self.assertFalse(list(Path(directory).rglob('ci-pipeline-summary.json')))
                finally:
                    os.chdir(old)

    def test_runtime_cli_routes_through_existing_ci_driver(self):
        with mock.patch.object(sys, 'argv', ['ci_pipeline.py', 'runtime', '--godot-bin', 'godot']), \
             mock.patch.object(ci_pipeline, 'run_runtime_preflight', return_value=1) as runtime:
            self.assertEqual(1, ci_pipeline.main())
            runtime.assert_called_once_with('godot', 'project.godot')

    def test_full_pipeline_rejects_stale_or_missing_runtime_success(self):
        import json
        cases = ((124, {'status': 'ok'}, 1), (0, {}, 1),
                 (0, {'status': 'fail'}, 1), (0, {'status': 'ok'}, 0))
        for runtime_rc, receipt, expected in cases:
            with self.subTest(runtime_rc=runtime_rc, receipt=receipt), tempfile.TemporaryDirectory() as directory:
                old = os.getcwd()
                os.chdir(directory)
                def command(args, cwd=None, timeout=900000):
                    return (runtime_rc, 'runtime output') if 'scripts/python/godot_selfcheck.py' in args and 'run' in args else (0, '')
                def result(path):
                    return receipt if path.endswith('selfcheck-summary.json') else {'status': 'ok'}
                try:
                    with mock.patch.object(sys, 'argv', ['ci_pipeline.py', 'all', '--solution', 'Game.sln', '--godot-bin', 'godot']), \
                         mock.patch.object(ci_pipeline, 'resolve_test_solution_arg', return_value='Game.sln'), \
                         mock.patch.object(ci_pipeline, 'run_cmd', side_effect=command), \
                         mock.patch.object(ci_pipeline, 'read_json', side_effect=result):
                        self.assertEqual(expected, ci_pipeline.main())
                    summary = json.loads(next(Path(directory).rglob('ci-pipeline-summary.json')).read_text())
                    self.assertEqual('ok' if expected == 0 else 'fail', summary['selfcheck']['status'])
                    self.assertEqual(runtime_rc, summary['selfcheck']['wrapper_rc'])
                finally:
                    os.chdir(old)

    def test_failed_test_names_include_long_vstest_durations_and_xunit_diagnostics(self):
        output = '\n'.join([
            'Failed Namespace.Fixture.LongFailure [3 m 12 s]',
            '[xUnit.net 00:03:12.03] Namespace.Fixture.LongFailure [FAIL]',
            'Failed Namespace.Fixture.SecondFailure [11 s]',
            'Failed Namespace.Fixture.HourFailure [1 h 2 m]',
            'X Namespace.Fixture.MillisecondFailure [123ms]',
            '[FAIL] Namespace.Fixture.PlainFailure',
            'Passed Namespace.Fixture.Success [3 m 12 s]',
        ])
        self.assertEqual([
            'Namespace.Fixture.LongFailure',
            'Namespace.Fixture.SecondFailure',
            'Namespace.Fixture.HourFailure',
            'Namespace.Fixture.MillisecondFailure',
            'Namespace.Fixture.PlainFailure',
        ], ci_pipeline.extract_failed_tests(output))

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
                     mock.patch.object(ci_pipeline, 'read_json', return_value={'status': 'ok'}):
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

    def test_reused_build_keeps_coverage_hang_diagnosis_and_aborted_artifacts(self):
        import json
        calls = []
        def fake(args, cwd=None, timeout=900000):
            calls.append(list(args))
            return 124, 'aborted host'
        with tempfile.TemporaryDirectory() as directory:
            old = os.getcwd()
            os.chdir(directory)
            try:
                result = Path('PhaseA.Platform.Tests/TestResults/run/host_Sequence.xml')
                result.parent.mkdir(parents=True)
                result.write_text('<Sequence />')
                with mock.patch.object(sys, 'argv', ['run_dotnet.py', '--solution', 'Game.sln', '--no-build', '--no-restore', '--hang-timeout', '10m']), \
                     mock.patch.object(run_dotnet, 'resolve_test_solution_arg', return_value='Game.sln'), \
                     mock.patch.object(run_dotnet, 'resolve_dotnet', return_value='dotnet'), \
                     mock.patch.object(run_dotnet, 'run_cmd', side_effect=fake):
                    self.assertEqual(1, run_dotnet.main())
                summary = json.loads(next(Path(directory).rglob('summary.json')).read_text())
                self.assertFalse(summary['execution_complete'])
                self.assertTrue(summary['restore_reused'])
                self.assertEqual(1, len(summary['project_result_artifacts']))
            finally:
                os.chdir(old)
        self.assertEqual(1, len(calls))
        self.assertIn('--collect:XPlat Code Coverage', calls[0])
        self.assertIn('--no-build', calls[0])
        self.assertIn('--no-restore', calls[0])
        self.assertIn('--blame-hang-timeout', calls[0])
        self.assertEqual('none', calls[0][calls[0].index('--blame-hang-dump-type') + 1])

    def test_hang_collector_abort_is_incomplete_even_with_exit_one(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            old = os.getcwd()
            os.chdir(directory)
            try:
                with mock.patch.object(sys, 'argv', ['run_dotnet.py', '--solution', 'Game.sln', '--no-build', '--no-restore']), \
                     mock.patch.object(run_dotnet, 'resolve_test_solution_arg', return_value='Game.sln'), \
                     mock.patch.object(run_dotnet, 'resolve_dotnet', return_value='dotnet'), \
                     mock.patch.object(run_dotnet, 'run_cmd', return_value=(1, 'The active test run was aborted.')):
                    self.assertEqual(1, run_dotnet.main())
                summary = json.loads(next(Path(directory).rglob('summary.json')).read_text())
                self.assertFalse(summary['execution_complete'])
                self.assertEqual('tests_failed', summary['status'])
            finally:
                os.chdir(old)

    def test_fail_fast_forwards_reuse_and_records_later_gates_not_run(self):
        import json
        calls = []
        def fake(args, cwd=None, timeout=900000):
            calls.append(list(args))
            return (124, 'aborted') if 'scripts/python/run_dotnet.py' in args else (0, '')
        with tempfile.TemporaryDirectory() as directory:
            old = os.getcwd()
            os.chdir(directory)
            try:
                with mock.patch.object(sys, 'argv', ['ci_pipeline.py', 'all', '--solution', 'Game.sln', '--godot-bin', 'godot', '--no-build', '--no-restore', '--hang-timeout', '10m', '--fail-fast']), \
                     mock.patch.object(ci_pipeline, 'resolve_test_solution_arg', return_value='Game.sln'), \
                     mock.patch.object(ci_pipeline, 'run_cmd', side_effect=fake), \
                     mock.patch.object(ci_pipeline, 'read_json', return_value={'status': 'tests_failed'}):
                    self.assertEqual(1, ci_pipeline.main())
                summary = json.loads(next(Path(directory).rglob('ci-pipeline-summary.json')).read_text())
                self.assertEqual('fail', summary['status'])
                self.assertEqual('not_run', summary['selfcheck']['status'])
                self.assertEqual('not_run', summary['encoding']['status'])
            finally:
                os.chdir(old)
        dotnet = next(command for command in calls if 'scripts/python/run_dotnet.py' in command)
        self.assertIn('--no-build', dotnet)
        self.assertIn('--no-restore', dotnet)
        self.assertIn('--hang-timeout', dotnet)
        self.assertFalse(any('scripts/python/godot_selfcheck.py' in command for command in calls))


if __name__ == '__main__':
    unittest.main()
