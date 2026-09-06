#!/usr/bin/env python3
"""
Internal LLM backend seam for sc scripts.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KNOWN_LLM_BACKENDS = ("codex-cli", "openai-api")


def _stop_codex_tree(process, *, windows=None):
    """ADR-0041: bounded cleanup; never drain inherited output pipes."""
    windows = os.name == "nt" if windows is None else windows
    errors = []
    try:
        if windows:
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=10, check=False,
            )
            if result.returncode:
                errors.append(f"taskkill exit code {result.returncode}")
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        errors.append(type(exc).__name__)
    if errors:
        try:
            process.kill()
        except OSError as exc:
            errors.append(type(exc).__name__)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        errors.append("process still running after cleanup")
    return errors


def _run_codex_process(cmd, *, root, prompt, timeout_sec):
    """ADR-0041: file-backed UTF-8 stdin/output keeps timeout independent of EOF."""
    options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
               if os.name == "nt" else {"start_new_session": True})
    # Anonymous temporary files avoid workspace deltas and pipe-reader joins.
    # Do not use Popen's context manager: its exit waits without a deadline.
    with tempfile.TemporaryFile() as stdin, tempfile.TemporaryFile() as stdout:
        stdin.write(prompt.encode("utf-8"))
        stdin.seek(0)
        started = time.monotonic()
        process = subprocess.Popen(cmd, cwd=str(root), stdin=stdin, stdout=stdout,
                                   stderr=subprocess.STDOUT, **options)
        timed_out = False
        cleanup_errors = []
        try:
            process.wait(timeout=max(0.001, timeout_sec - (time.monotonic() - started)))
        except subprocess.TimeoutExpired:
            timed_out = True
            cleanup_errors = _stop_codex_tree(process)
        except BaseException:
            _stop_codex_tree(process)
            raise
        # Read only the bytes currently present, even if cleanup was unsuccessful.
        size = os.fstat(stdout.fileno()).st_size
        stdout.seek(0)
        output = stdout.read(size).decode("utf-8", errors="replace")
        if timed_out:
            output += "\ncodex exec timeout\n"
            if cleanup_errors:
                output += "codex cleanup incomplete: " + "; ".join(cleanup_errors) + "\n"
            return 124, output
        return process.returncode or 0, output


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_llm_backend(raw: str | None) -> str:
    value = str(raw or os.environ.get("SC_LLM_BACKEND") or "codex-cli").strip().lower()
    if value in KNOWN_LLM_BACKENDS:
        return value
    return value or "codex-cli"


def inspect_llm_backend(backend: str | None) -> dict[str, object]:
    backend_name = resolve_llm_backend(backend)
    payload: dict[str, object] = {
        "backend": backend_name,
        "available": False,
        "blocking_errors": [],
    }
    if backend_name == "codex-cli":
        executable = shutil.which("codex")
        payload["executable"] = executable or ""
        if not executable:
            payload["blocking_errors"] = ["codex executable not found in PATH"]
            return payload
        payload["available"] = True
        return payload
    if backend_name == "openai-api":
        module_spec = importlib.util.find_spec("openai")
        api_key = str(os.environ.get("OPENAI_API_KEY") or "").strip()
        endpoint = str(os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
        blocking_errors: list[str] = []
        payload["python_module"] = "openai"
        payload["python_module_found"] = bool(module_spec)
        payload["api_key_env"] = "OPENAI_API_KEY"
        payload["api_key_present"] = bool(api_key)
        payload["model"] = _resolve_openai_model()
        payload["endpoint_sha256"] = _sha256_text(endpoint)
        try:
            sdk_version = importlib.metadata.version("openai")
            payload["sdk_version"] = sdk_version
            payload["sdk_version_sha256"] = _sha256_text(sdk_version)
        except importlib.metadata.PackageNotFoundError:
            payload["sdk_version"] = "unresolved"
            payload["sdk_version_sha256"] = "unresolved"
        if module_spec is None:
            blocking_errors.append("python package 'openai' is not installed")
        if not api_key:
            blocking_errors.append("OPENAI_API_KEY is not set")
        payload["blocking_errors"] = blocking_errors
        payload["available"] = len(blocking_errors) == 0
        return payload
    payload["blocking_errors"] = [f"unsupported llm backend: {backend_name}"]
    return payload


def _extract_reasoning_effort(codex_configs: list[str] | None) -> str:
    for item in list(codex_configs or []):
        text = str(item or "").strip()
        if not text.startswith("model_reasoning_effort="):
            continue
        _, raw = text.split("=", 1)
        value = raw.strip().strip('"').strip("'").strip().lower()
        if value in {"low", "medium", "high", "xhigh", "max", "none", "minimal"}:
            return value
    return ""


def _resolve_openai_model() -> str:
    return str(os.environ.get("SC_OPENAI_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-5").strip() or "gpt-5"


def _extract_response_output_text(response: object) -> str:
    direct = str(getattr(response, "output_text", "") or "").strip()
    if direct:
        return direct
    output_items = getattr(response, "output", None)
    if isinstance(output_items, list):
        chunks: list[str] = []
        for item in output_items:
            content = getattr(item, "content", None)
            if not isinstance(content, list):
                continue
            for part in content:
                text = str(getattr(part, "text", "") or "").strip()
                if text:
                    chunks.append(text)
        if chunks:
            return "\n".join(chunks).strip()
    if isinstance(response, dict):
        direct = str(response.get("output_text") or "").strip()
        if direct:
            return direct
    return ""


def run_llm_exec(
    *,
    backend: str,
    root: Path,
    prompt: str,
    output_last_message: Path,
    timeout_sec: int,
    codex_configs: list[str] | None = None,
    codex_model: str | None = None,
    codex_json: bool = False,
    codex_sandbox: str = "read-only",
    codex_skip_git_repo_check: bool = False,
    codex_output_arg: str = "--output-last-message",
    codex_cd_arg: str = "-C",
    codex_extra_args: list[str] | None = None,
) -> tuple[int, str, list[str]]:
    backend_name = resolve_llm_backend(backend)
    if backend_name == "openai-api":
        info = inspect_llm_backend(backend_name)
        blocking_errors = [str(item).strip() for item in list(info.get("blocking_errors") or []) if str(item).strip()]
        if blocking_errors:
            details = "; ".join(blocking_errors)
            return 2, f"openai-api backend is not runnable: {details}\n", [backend_name]
        try:
            openai_module = sys.modules.get("openai")
            if openai_module is None:
                import openai as openai_module  # type: ignore
            OpenAI = getattr(openai_module, "OpenAI")
        except Exception as exc:  # noqa: BLE001
            return 1, f"openai-api backend failed to import SDK: {exc}\n", [backend_name]

        model = _resolve_openai_model()
        reasoning_effort = _extract_reasoning_effort(codex_configs)
        kwargs: dict[str, object] = {
            "model": model,
            "input": prompt,
        }
        if reasoning_effort:
            kwargs["reasoning"] = {"effort": reasoning_effort}
        try:
            client = OpenAI(timeout=float(timeout_sec))
            response = client.responses.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            return 1, f"openai-api request failed: {exc}\n", [backend_name]

        output_text = _extract_response_output_text(response)
        if output_text:
            output_last_message.parent.mkdir(parents=True, exist_ok=True)
            output_last_message.write_text(output_text.rstrip() + "\n", encoding="utf-8")
        trace = {
            "backend": backend_name,
            "model": model,
            "reasoning_effort": reasoning_effort or None,
            "response_id": str(getattr(response, "id", "") or ""),
            "output_chars": len(output_text),
        }
        return (0 if output_text else 1), json.dumps(trace, ensure_ascii=False, indent=2) + "\n", [backend_name, model]
    if backend_name != "codex-cli":
        return 2, f"unsupported llm backend: {backend_name}\n", [backend_name]

    exe = shutil.which("codex")
    if not exe:
        return 127, "codex executable not found in PATH\n", ["codex"]

    extra_config = [c for c in (codex_configs or []) if str(c).strip()]
    extra_config_args: list[str] = []
    for item in extra_config:
        extra_config_args.extend(["-c", str(item)])
    model = str(codex_model or "").strip()
    sandbox = str(codex_sandbox or "read-only").strip() or "read-only"
    output_arg = str(codex_output_arg or "--output-last-message").strip() or "--output-last-message"
    cd_arg = str(codex_cd_arg or "-C").strip() or "-C"

    cmd = [
        exe,
        "exec",
        *(["--json"] if codex_json else []),
        *(["-m", model] if model else []),
        *extra_config_args,
        "--sandbox" if sandbox != "read-only" else "-s",
        sandbox,
        *(["--skip-git-repo-check"] if codex_skip_git_repo_check else []),
        cd_arg,
        str(root),
        output_arg,
        str(output_last_message),
        *[str(item) for item in (codex_extra_args or [])],
        "-",
    ]
    try:
        code, output = _run_codex_process(cmd, root=root, prompt=prompt, timeout_sec=timeout_sec)
    except Exception as exc:  # noqa: BLE001
        return 1, f"codex exec failed to start: {exc}\n", cmd
    return code, output, cmd
