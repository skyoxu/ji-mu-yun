"""Bounded CI processes with durable output (ADR-0005).

File-backed output survives wrapper termination and avoids inherited pipe handles
blocking communicate() after timeout. All descendants must stop before the next
gate starts; a timeout remains exit code 124.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid


def env_timeout_ms(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f'{name} must be a positive integer in milliseconds') from exc
    if value <= 0:
        raise ValueError(f'{name} must be a positive integer in milliseconds')
    return value


def stop_process_tree(process: subprocess.Popen) -> None:
    if os.name == 'nt':
        result = subprocess.run(
            ['taskkill', '/PID', str(process.pid), '/T', '/F'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=15, check=False,
        )
        if result.returncode and process.poll() is None:
            raise RuntimeError(f'cannot terminate CI process tree pid={process.pid}')
    else:
        # Nested CI wrappers can start their own sessions. On Linux, include
        # those descendants as well as children inheriting our process group.
        parents = {}
        if Path('/proc').is_dir():
            for entry in Path('/proc').iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    stat = (entry / 'stat').read_text()
                    parents[int(entry.name)] = int(stat.rsplit(')', 1)[1].split()[1])
                except (OSError, ValueError, IndexError):
                    continue
        descendants = [process.pid]
        for parent in descendants:
            descendants.extend(pid for pid, ppid in parents.items() if ppid == parent and pid not in descendants)
        for pid in reversed(descendants[1:]):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=15)


def run_logged_command(args, cwd=None, timeout=900_000, *, separate_stderr=False, heartbeat_seconds=30, env=None, log_root=None):
    if timeout <= 0 or heartbeat_seconds <= 0:
        raise ValueError('CI process timeout and heartbeat must be positive')
    root = Path(log_root or cwd or os.getcwd())
    directory = root / 'logs' / 'ci' / dt.date.today().isoformat() / 'process-output'
    directory.mkdir(parents=True, exist_ok=True)
    stem = uuid.uuid4().hex
    stdout_path = directory / f'{stem}.stdout.log'
    stderr_path = directory / f'{stem}.stderr.log'
    label = Path(str(args[0])).name
    print(f'CI_PROCESS START executable={label} timeout_ms={timeout} stdout={stdout_path}', flush=True)
    started = time.monotonic()
    with stdout_path.open('wb') as stdout_file, stderr_path.open('wb') as stderr_file:
        kwargs = {'start_new_session': True} if os.name != 'nt' else {}
        process = subprocess.Popen(
            args, cwd=cwd, env=env, stdout=stdout_file,
            stderr=stderr_file if separate_stderr else subprocess.STDOUT,
            **kwargs,
        )
        # ADR-0005: expose liveness without publishing child output or command secrets.
        deadline = started + timeout / 1000
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stop_process_tree(process)
                rc = 124
                break
            try:
                rc = process.wait(timeout=min(remaining, heartbeat_seconds))
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    stop_process_tree(process)
                    rc = 124
                    break
                print(f'CI_PROCESS HEARTBEAT executable={label} elapsed_s={round(time.monotonic() - started, 1)} '
                      f'stdout_bytes={stdout_path.stat().st_size} stderr_bytes={stderr_path.stat().st_size}', flush=True)
    out = stdout_path.read_bytes().decode('utf-8', errors='replace')
    err = stderr_path.read_bytes().decode('utf-8', errors='replace') if separate_stderr else ''
    elapsed = round(time.monotonic() - started, 3)
    metadata = {'executable': label, 'timeout_ms': timeout, 'elapsed_s': elapsed,
                'rc': rc, 'stdout_bytes': stdout_path.stat().st_size,
                'stderr_bytes': stderr_path.stat().st_size}
    (directory / f'{stem}.timing.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(f'CI_PROCESS END executable={label} rc={rc} elapsed_s={elapsed} stdout={stdout_path}', flush=True)
    return rc, out, err
