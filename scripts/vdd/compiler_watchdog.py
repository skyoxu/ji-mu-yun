"""ADR-0041: bound a compiler subprocess and preserve its diagnostics."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import math


def positive_timeout(value):
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("compile timeout must be finite and positive")
    return seconds


def last_checkpoint(path):
    if not Path(path).is_file():
        return None
    for line in reversed(Path(path).read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def _terminate_tree(process):
    if os.name == "nt":
        result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                capture_output=True, timeout=10, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"taskkill failed with exit code {result.returncode}")
    else:
        os.killpg(process.pid, signal.SIGKILL)


def run_compiler(command, *, cwd, run_dir, timeout_seconds, env=None):
    timeout_seconds = positive_timeout(timeout_seconds)
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    result = {"timeout_seconds": timeout_seconds, "command": list(command),
              "timed_out": False, "cleanup_error": None}
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with (run_dir / "compiler-stdout.log").open("wb") as stdout, (run_dir / "compiler-stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr, **options)
        result["pid"] = process.pid
        try:
            process.wait(timeout=max(0.001, timeout_seconds - (time.monotonic() - started)))
        except subprocess.TimeoutExpired:
            result["timed_out"] = True
            try:
                _terminate_tree(process)
            except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
                result["cleanup_error"] = str(exc)
                process.kill()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                result["cleanup_error"] = "compiler process did not exit after termination"
        result["exit_code"] = process.returncode
    result["elapsed_seconds"] = time.monotonic() - started
    result["last_checkpoint"] = last_checkpoint(run_dir / "plan/.compiler-work/compiler-progress.jsonl")
    (run_dir / "watchdog-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
