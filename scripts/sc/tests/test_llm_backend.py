#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
SC_DIR = REPO_ROOT / "scripts" / "sc"
if str(SC_DIR) not in sys.path:
    sys.path.insert(0, str(SC_DIR))


def _load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"failed to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


llm_backend = _load_module("sc_llm_backend_module", "scripts/sc/_llm_backend.py")


class LlmBackendTests(unittest.TestCase):
    # ADR-0041: exercise real child processes without contacting an LLM backend.
    def test_process_preserves_utf8_stdin_output_and_nonzero_exit(self):
        prompt = "payload-\u4e2d\u6587"
        code, output = llm_backend._run_codex_process(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()); sys.exit(7)"],
            root=REPO_ROOT, prompt=prompt, timeout_sec=5)
        self.assertEqual(7, code)
        self.assertEqual(prompt, output)

    def test_timeout_stops_child_with_inherited_output_handles(self):
        with tempfile.TemporaryDirectory() as td:
            heartbeat = Path(td) / "heartbeat"
            child = (
                "import time,sys\n"
                "with open(sys.argv[1], 'ab', buffering=0) as f:\n"
                " while True:\n"
                "  f.write(b'x'); time.sleep(.02)\n"
            )
            parent = (
                "import subprocess,sys,time\n"
                "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]])\n"
                "print('child launched', flush=True)\n"
                "time.sleep(60)\n"
            )
            started = time.monotonic()
            code, output = llm_backend._run_codex_process(
                [sys.executable, "-c", parent, child, str(heartbeat)],
                root=REPO_ROOT, prompt="", timeout_sec=2)
            elapsed = time.monotonic() - started
            self.assertEqual(124, code)
            self.assertIn("child launched", output)
            self.assertNotIn("cleanup incomplete", output)
            self.assertLess(elapsed, 20)
            size = heartbeat.stat().st_size
            self.assertGreater(size, 0)
            time.sleep(.15)
            self.assertEqual(size, heartbeat.stat().st_size)

    def test_windows_tree_cleanup_is_bounded_and_reports_failure(self):
        process = mock.Mock(pid=123)
        process.wait.side_effect = subprocess.TimeoutExpired("worker", 5)
        with mock.patch.object(llm_backend.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("taskkill", 10)) as kill:
            errors = llm_backend._stop_codex_tree(process, windows=True)
        self.assertTrue(errors)
        self.assertEqual(["taskkill", "/PID", "123", "/T", "/F"], kill.call_args.args[0])
        self.assertEqual(subprocess.DEVNULL, kill.call_args.kwargs["stdout"])
        self.assertEqual(10, kill.call_args.kwargs["timeout"])
        process.kill.assert_called_once()
        process.wait.assert_called_once_with(timeout=5)

    def test_public_backend_preserves_timeout_and_partial_output(self):
        with mock.patch.object(llm_backend.shutil, "which", return_value="codex"), \
                mock.patch.object(llm_backend, "_run_codex_process",
                                  return_value=(124, "partial\ncodex exec timeout\n")):
            code, output, command = llm_backend.run_llm_exec(
                backend="codex-cli", root=REPO_ROOT, prompt="hello",
                output_last_message=REPO_ROOT / "unused.json", timeout_sec=180)
        self.assertEqual(124, code)
        self.assertIn("partial", output)
        self.assertIn("codex exec timeout", output)
        self.assertEqual("codex", command[0])

    def test_codex_transient_gateway_failure_retries_five_times(self):
        responses = [(1, "503 Service Unavailable: no available channel\n")] * 5 + [(0, "ok")]
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(llm_backend.shutil, "which", return_value="codex"), \
                mock.patch.object(llm_backend, "_run_codex_process", side_effect=responses) as run_mock, \
                mock.patch.object(llm_backend.time, "sleep") as sleep_mock:
            output_path = Path(td) / "last-message.json"
            output_path.write_text("stale\n", encoding="utf-8")
            code, output, _command = llm_backend.run_llm_exec(
                backend="codex-cli", root=REPO_ROOT, prompt="hello",
                output_last_message=output_path, timeout_sec=10)

        self.assertEqual(0, code)
        self.assertIn("llm transient retries: 5", output)
        self.assertEqual(6, run_mock.call_count)
        self.assertEqual([mock.call(float(i)) for i in range(1, 6)], sleep_mock.call_args_list)

    def test_codex_timeout_is_not_retried(self):
        with mock.patch.object(llm_backend.shutil, "which", return_value="codex"), \
                mock.patch.object(llm_backend, "_run_codex_process", return_value=(124, "codex exec timeout\n")) as run_mock, \
                mock.patch.object(llm_backend.time, "sleep") as sleep_mock:
            code, output, _command = llm_backend.run_llm_exec(
                backend="codex-cli", root=REPO_ROOT, prompt="hello",
                output_last_message=REPO_ROOT / "unused.json", timeout_sec=10)

        self.assertEqual(124, code)
        self.assertIn("codex exec timeout", output)
        run_mock.assert_called_once()
        sleep_mock.assert_not_called()

    def test_inspect_openai_backend_should_publish_non_secret_runtime_identity(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_BASE_URL": "https://example.invalid/v1",
                "SC_OPENAI_MODEL": "gpt-5.6-test",
            },
            clear=False,
        ), mock.patch.object(llm_backend.importlib.util, "find_spec", return_value=object()), \
            mock.patch.object(llm_backend.importlib.metadata, "version", return_value="9.8.7"):
            info = llm_backend.inspect_llm_backend("openai-api")

        self.assertTrue(info["available"])
        self.assertEqual("gpt-5.6-test", info["model"])
        self.assertEqual(llm_backend._sha256_text("https://example.invalid/v1"), info["endpoint_sha256"])
        self.assertEqual("9.8.7", info["sdk_version"])
        self.assertEqual(llm_backend._sha256_text("9.8.7"), info["sdk_version_sha256"])
        self.assertNotIn("sk-test", json.dumps(info, sort_keys=True))

    def test_reasoning_effort_parser_supports_policy_efforts(self) -> None:
        for effort in ("medium", "high", "max", "xhigh"):
            with self.subTest(effort=effort):
                self.assertEqual(
                    effort,
                    llm_backend._extract_reasoning_effort([f'model_reasoning_effort="{effort}"']),
                )

    def test_run_llm_exec_should_fail_on_openai_backend_before_implementation(self) -> None:
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False), \
            mock.patch.object(llm_backend.importlib.util, "find_spec", return_value=None):
            rc, out, cmd = llm_backend.run_llm_exec(
                backend="openai-api",
                root=REPO_ROOT,
                prompt="hello",
                output_last_message=REPO_ROOT / "tmp.md",
                timeout_sec=10,
            )

        self.assertEqual(2, rc)
        self.assertIn("openai-api backend is not runnable", out)
        self.assertEqual(["openai-api"], cmd)

    def test_run_llm_exec_should_report_missing_codex(self) -> None:
        with mock.patch.object(llm_backend.shutil, "which", return_value=None):
            rc, out, cmd = llm_backend.run_llm_exec(
                backend="codex-cli",
                root=REPO_ROOT,
                prompt="hello",
                output_last_message=REPO_ROOT / "tmp.md",
                timeout_sec=10,
            )

        self.assertEqual(127, rc)
        self.assertIn("codex executable not found", out)
        self.assertEqual(["codex"], cmd)

    def test_run_llm_exec_should_invoke_codex_cli(self) -> None:
        proc = (0, "ok")
        with mock.patch.object(llm_backend.shutil, "which", return_value="codex"), mock.patch.object(
            llm_backend, "_run_codex_process", return_value=proc
        ) as run_mock:
            rc, out, cmd = llm_backend.run_llm_exec(
                backend="codex-cli",
                root=REPO_ROOT,
                prompt="hello",
                output_last_message=REPO_ROOT / "tmp.md",
                timeout_sec=10,
                codex_configs=['model_reasoning_effort="low"'],
            )

        self.assertEqual(0, rc)
        self.assertEqual("ok", out)
        self.assertIn("codex", cmd[0])
        self.assertIn("-c", cmd)
        self.assertIn('model_reasoning_effort="low"', cmd)
        run_mock.assert_called_once()

    def test_run_llm_exec_should_support_workspace_write_codex_protocol(self) -> None:
        proc = (0, "ok")
        with mock.patch.object(llm_backend.shutil, "which", return_value="codex"), mock.patch.object(
            llm_backend, "_run_codex_process", return_value=proc
        ) as run_mock:
            rc, out, cmd = llm_backend.run_llm_exec(
                backend="codex-cli",
                root=REPO_ROOT,
                prompt="hello",
                output_last_message=REPO_ROOT / "codex-output.txt",
                timeout_sec=10,
                codex_model="gpt-5.5",
                codex_configs=['model_reasoning_effort="high"', 'approval_policy="never"'],
                codex_json=True,
                codex_sandbox="workspace-write",
                codex_skip_git_repo_check=True,
                codex_output_arg="-o",
                codex_cd_arg="--cd",
            )

        self.assertEqual(0, rc)
        self.assertEqual("ok", out)
        self.assertIn("--json", cmd)
        self.assertIn("gpt-5.5", cmd)
        self.assertIn("--sandbox", cmd)
        self.assertIn("workspace-write", cmd)
        self.assertIn("--skip-git-repo-check", cmd)
        self.assertIn("--cd", cmd)
        self.assertIn("-o", cmd)
        self.assertEqual("-", cmd[-1])
        run_mock.assert_called_once()
        self.assertEqual("hello", run_mock.call_args.kwargs["prompt"])

    def test_run_llm_exec_should_invoke_openai_backend_and_write_output(self) -> None:
        class _FakeResponses:
            def create(self, **kwargs):
                self.kwargs = dict(kwargs)
                return type("Response", (), {"id": "resp_123", "output_text": "review output"})()

        class _FakeClient:
            last_timeout = None

            def __init__(self, *, timeout):
                _FakeClient.last_timeout = timeout
                self.responses = _FakeResponses()

        fake_openai = type("FakeOpenAI", (), {"OpenAI": _FakeClient})
        with tempfile.TemporaryDirectory() as td, \
            mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "SC_OPENAI_MODEL": "gpt-5"}, clear=False), \
            mock.patch.object(llm_backend.importlib.util, "find_spec", return_value=object()), \
            mock.patch.dict(sys.modules, {"openai": fake_openai}):
            out_path = Path(td) / "review.md"
            rc, out, cmd = llm_backend.run_llm_exec(
                backend="openai-api",
                root=REPO_ROOT,
                prompt="hello",
                output_last_message=out_path,
                timeout_sec=15,
                codex_configs=['model_reasoning_effort="low"'],
            )

            self.assertEqual(0, rc)
            self.assertIn('"backend": "openai-api"', out)
            self.assertEqual(["openai-api", "gpt-5"], cmd)
            self.assertTrue(out_path.is_file())
            self.assertEqual("review output\n", out_path.read_text(encoding="utf-8"))
            self.assertEqual(15.0, _FakeClient.last_timeout)

    def test_run_llm_exec_should_surface_openai_request_failures(self) -> None:
        class _FailingResponses:
            def create(self, **kwargs):  # noqa: ARG002
                raise RuntimeError("boom")

        class _FailingClient:
            def __init__(self, *, timeout):  # noqa: ARG002
                self.responses = _FailingResponses()

        fake_openai = type("FakeOpenAI", (), {"OpenAI": _FailingClient})
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False), \
            mock.patch.object(llm_backend.importlib.util, "find_spec", return_value=object()), \
            mock.patch.dict(sys.modules, {"openai": fake_openai}):
            rc, out, cmd = llm_backend.run_llm_exec(
                backend="openai-api",
                root=REPO_ROOT,
                prompt="hello",
                output_last_message=REPO_ROOT / "tmp.md",
                timeout_sec=15,
            )

        self.assertEqual(1, rc)
        self.assertIn("openai-api request failed", out)
        self.assertEqual(["openai-api"], cmd)


if __name__ == "__main__":
    unittest.main()
