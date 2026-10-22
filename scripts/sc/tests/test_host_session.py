"""ADR-0041: exercise the real caller-session transport without a fake CLI."""
import json
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import host_session as host
import _llm_backend as backend


class HostSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'logs/session'
        host.initialize(self.root, self.directory, 'test-caller')
        self.env = patch.dict(os.environ, {host.ENV: str(self.directory)})
        self.env.start()
        os.environ.pop(host.TIMEOUT_ENV, None)
        self.addCleanup(self.env.stop)

    def start(self, mode='read-only', timeout=5):
        self.result = []
        self.output = self.root / 'output.txt'
        thread = threading.Thread(target=lambda: self.result.append(backend.run_llm_exec(
            backend='host-session', root=self.root, prompt='Real test request',
            output_last_message=self.output, timeout_sec=timeout, codex_sandbox=mode)))
        thread.start()
        self.addCleanup(thread.join, 6)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            requests = host.pending(self.directory)
            if requests:
                self.request = host.read(Path(requests[0]['request_path']))
                self.call = Path(requests[0]['request_path']).parent
                return thread
            time.sleep(.01)
        self.fail('transport did not publish request')

    def answer(self, text='{"answer": 1}'):
        return host.respond(self.directory, self.request['request_id'], host.digest(self.request), text)

    def test_actual_read_only_exchange_and_one_shot_binding(self):
        thread = self.start()
        self.assertEqual('read-only', self.request['mode'])
        self.answer()
        thread.join(3)
        self.assertEqual(0, self.result[0][0])
        self.assertEqual({'answer': 1}, json.loads(self.output.read_text()))
        self.assertEqual([], host.read(self.call / 'result.json')['authorizes'])
        with self.assertRaises(ValueError):
            self.answer()

    def test_workspace_write_returns_only_after_caller_edits(self):
        thread = self.start('workspace-write')
        target = self.root / 'production.py'
        target.write_text('value = 1\n')
        self.answer('Edited declared production path; native guards must validate.')
        thread.join(3)
        self.assertEqual(0, self.result[0][0])
        self.assertEqual('workspace-write', self.request['mode'])
        self.assertEqual('value = 1\n', target.read_text())

    def test_wrong_hash_is_rejected_without_consuming_request(self):
        thread = self.start()
        with self.assertRaises(ValueError):
            host.respond(self.directory, self.request['request_id'], 'wrong', 'answer')
        self.assertFalse((self.call / 'response.json').exists())
        self.answer()
        thread.join(3)
        self.assertEqual(0, self.result[0][0])

    def test_tampered_response_does_not_write_native_output(self):
        thread = self.start()
        host.create(self.call / 'response.json', {'output_text': 'pass', 'authorizes': ['plan-ready']})
        thread.join(3)
        self.assertEqual(2, self.result[0][0])
        self.assertFalse(self.output.exists())

    def test_cancel_and_late_response_rejected(self):
        thread = self.start()
        host.create(self.call / 'cancel.json', {'authorizes': []})
        thread.join(3)
        self.assertEqual(130, self.result[0][0])
        with self.assertRaises(ValueError):
            self.answer()
        self.assertFalse(self.output.exists())

    def test_timeout_preserves_request_and_has_no_output(self):
        thread = self.start(timeout=.2)
        thread.join(3)
        self.assertEqual(124, self.result[0][0])
        self.assertTrue((self.call / 'request.json').exists())
        with self.assertRaises(ValueError):
            self.answer()
        self.assertFalse(self.output.exists())

    def test_default_budget_is_native_and_explicit_budget_is_recorded(self):
        with patch.dict(os.environ, {host.TIMEOUT_ENV: '2'}):
            thread = self.start(timeout=.2)
            self.assertEqual(.2, self.request['native_timeout_seconds'])
            self.assertEqual(2, self.request['effective_timeout_seconds'])
            self.assertEqual('explicit-host-override', self.request['timeout_source'])
            # The caller opted into a longer budget before this request began.
            time.sleep(.25)
            self.answer()
            thread.join(3)
            self.assertEqual(0, self.result[0][0])

    def test_absent_override_never_extends_the_native_budget(self):
        thread = self.start(timeout=.2)
        self.assertEqual(.2, self.request['effective_timeout_seconds'])
        self.assertEqual('native-worker', self.request['timeout_source'])
        thread.join(3)
        self.assertEqual(124, self.result[0][0])

    def test_explicit_budget_can_shorten_but_cannot_be_unbounded(self):
        self.assertEqual(1, host.timeout_budget(600, '1'))
        self.assertEqual(host.MAX_TIMEOUT_SECONDS, host.timeout_budget(180, str(host.MAX_TIMEOUT_SECONDS)))
        for value in ('0', '-1', '3601', '1.5', 'nan', 'inf', '', ' 5', True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                host.timeout_budget(180, value)
        for value in (0, -1, float('nan'), float('inf'), True):
            with self.subTest(native=value), self.assertRaises(ValueError):
                host.timeout_budget(value)
        with patch.dict(os.environ, {host.TIMEOUT_ENV: '3601'}):
            code, _, _ = backend.run_llm_exec(
                backend='host-session', root=self.root, prompt='must not launch',
                output_last_message=self.root / 'unused', timeout_sec=180)
        self.assertEqual(2, code)
        self.assertEqual([], host.pending(self.directory))

    def test_wrapper_requires_explicit_budget_and_retains_native_exit(self):
        specification = importlib.util.spec_from_file_location(
            'host_wrapper_under_test', Path(__file__).resolve().parents[2] / 'workflow_host.py')
        wrapper = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(wrapper)
        for options, expected in (([], None), (['--host-timeout-seconds', '900'], '900')):
            argv = ['workflow_host.py', '--session', str(self.directory), *options, 'vdd', '--', '--help']
            with patch.object(wrapper, 'ROOT', self.root), patch.object(sys, 'argv', argv), \
                    patch.dict(os.environ, {host.TIMEOUT_ENV: '3600'}), \
                    patch.object(wrapper.subprocess, 'call', return_value=7) as launch:
                self.assertEqual(7, wrapper.main())
            self.assertEqual(expected, launch.call_args.kwargs['env'].get(host.TIMEOUT_ENV))
            self.assertFalse(launch.call_args.kwargs['shell'])
            self.assertEqual('host-session', launch.call_args.kwargs['env']['SC_LLM_BACKEND'])

    def test_repository_and_log_containment_fail_closed(self):
        with self.assertRaises(ValueError):
            host.session(self.directory, self.root / 'other')
        with self.assertRaises(ValueError):
            host.initialize(self.root, self.root / 'production', 'test')
        with self.assertRaises(ValueError):
            host.respond(self.directory, '../outside', 'hash', 'text')

    def test_backend_default_and_missing_configuration(self):
        with patch.dict(os.environ, {'SC_LLM_BACKEND': ''}):
            self.assertEqual('codex-cli', backend.resolve_llm_backend(None))
        self.assertTrue(backend.inspect_llm_backend('host-session')['available'])
        with patch.dict(os.environ, {host.ENV: str(self.root / 'missing')}):
            self.assertFalse(backend.inspect_llm_backend('host-session')['available'])


if __name__ == '__main__':
    unittest.main()
