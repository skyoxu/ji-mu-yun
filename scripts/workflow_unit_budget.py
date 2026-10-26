"""ADR-0041: VDD/Quick Dev process supervision, never completion authority.

Only executable public entries enable this monitor. Unit events describe actual
calls/output, not heartbeats. The diagnostic ledger cannot create workflow proof.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import uuid

EVENT_ENV = "JIMUYUN_WORKFLOW_UNIT_EVENTS"
TOTAL_ENV = "JIMUYUN_WORKFLOW_UNIT_SECONDS"
IDLE_ENV = "JIMUYUN_WORKFLOW_IDLE_SECONDS"
_parent = ContextVar("workflow_unit_parent", default="entry")
_lock = threading.Lock()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def execution_environment():
    """Tests cannot observe supervisor routing; hash exactly this environment."""
    return {k: v for k, v in os.environ.items() if k not in (EVENT_ENV, TOTAL_ENV, IDLE_ENV)}


def worker_input(prompt, fallback):
    """Budget lineage only: query-attempt metadata cannot renew a task budget.

    This deliberately does NOT alter semantic/execution cache fingerprints.
    """
    try:
        payload, _ = json.JSONDecoder().raw_decode(prompt.split("\n\nINPUT:\n", 1)[1])
    except (IndexError, ValueError):
        return fallback
    # Schema repair diagnostics are not a new work domain. Retrying the same
    # frozen input must not renew its allowance because the error text changed.
    while isinstance(payload, dict) and isinstance(payload.get("input"), dict):
        payload = payload["input"]
    def stable(value):
        if isinstance(value, dict):
            return {k: stable(v) for k, v in value.items() if k != "planning_source_observations"}
        if isinstance(value, list):
            return [stable(v) for v in value]
        return value
    return stable(payload)


def event(kind, **fields):
    path = os.environ.get(EVENT_ENV)
    if path:
        record = {"event": kind, "at": time.monotonic(), **fields}
        with _lock, open(path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()


@contextmanager
def unit(key, label, *, container=False):
    """Repeated calls with the same content key spend the same allowance."""
    call = uuid.uuid4().hex
    event("start", call=call, key=identity(key), label=label, parent=_parent.get(), container=container)
    token = _parent.set(call)
    try:
        yield call
    finally:
        _parent.reset(token)
        event("end", call=call)


def progress(call, data):
    # Called only on actual subprocess bytes or completed native sub-units.
    if data and data.strip():
        event("progress", call=call, digest=hashlib.sha256(data).hexdigest())


def run_command(argv, *, cwd, timeout):
    """Non-pytest Q6 command: stream real bytes to the unit monitor."""
    with unit([str(cwd), argv], "Quick Dev regression command") as call:
        process = subprocess.Popen(argv, cwd=cwd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=os.name != "nt", env=execution_environment())
        event("owned", call=call, pid=process.pid)
        buffers = [bytearray(), bytearray()]
        def drain(pipe, buf):
            with pipe:
                while True:
                    data = pipe.read1(65536)
                    if not data:
                        break
                    buf.extend(data)
                    progress(call, data)
        threads = [threading.Thread(target=drain, args=(pipe, buf), daemon=True)
                   for pipe, buf in zip((process.stdout, process.stderr), buffers)]
        for thread in threads:
            thread.start()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate_tree(process)
            process.wait()
            for thread in threads:
                thread.join(timeout=1)
            raise subprocess.TimeoutExpired(argv, timeout, bytes(buffers[0]), bytes(buffers[1]))
        finally:
            if process.poll() is None:
                terminate_tree(process)
                process.wait()
            event("reaped", call=call, pid=process.pid)
        for thread in threads:
            thread.join(timeout=1)
        return subprocess.CompletedProcess(argv, process.returncode, bytes(buffers[0]), bytes(buffers[1]))


class Budget:
    """Deterministic exclusive-time accounting; no aggregate round deadline."""
    def __init__(self, total=1800, idle=600, spent=None, now=0):
        if not math.isfinite(total) or not math.isfinite(idle) or total <= 0 or idle <= 0:
            raise ValueError("unit budgets must be positive")
        self.total, self.idle = total, idle
        self.spent = dict(spent or {})
        self.calls = {}
        self.owned = set()
        self.last = now
        self.violation = None

    def tick(self, now):
        if now < self.last:
            raise ValueError("non-monotonic unit clock")
        # Container stages do not charge time spent in independent children.
        parents = {c["parent"] for c in self.calls.values()}
        has_work = any(not c.get("container") for c in self.calls.values())
        for call, c in self.calls.items():
            if call in parents or (c.get("container") and has_work) or (call == "entry" and len(self.calls) > 1):
                c["idle"] = 0
                continue
            delta = now - self.last
            self.spent[c["key"]] = self.spent.get(c["key"], 0) + delta
            c["idle"] += delta
            if self.spent[c["key"]] >= self.total:
                self.violation = {"reason": "unit-total", "key": c["key"], "label": c["label"]}
            elif c["idle"] >= self.idle:
                self.violation = {"reason": "unit-idle", "key": c["key"], "label": c["label"]}
        self.last = now
        return self.violation

    def apply(self, row):
        self.tick(max(row["at"], self.last))
        kind, call = row["event"], row["call"]
        if kind == "owned":
            self.owned.add(row["pid"])
            return
        if kind == "reaped":
            self.owned.discard(row["pid"])
            return
        if kind == "start":
            self.calls[call] = {"key": row["key"], "label": row["label"],
                                "parent": row.get("parent"), "idle": 0, "seen": set(),
                                "container": row.get("container", False)}
            if self.spent.get(row["key"], 0) >= self.total:
                self.violation = {"reason": "unit-total", "key": row["key"], "label": row["label"]}
        elif kind == "progress" and call in self.calls:
            c = self.calls[call]
            digest = row["digest"]
            if digest not in c["seen"]:
                c["seen"].add(digest)
                c["idle"] = 0
        elif kind == "end":
            c = self.calls.pop(call, None)
            if c and c["parent"] in self.calls:
                self.calls[c["parent"]]["idle"] = 0


def terminate_tree(process):
    """Terminate the owned tree before reaping; never target an unrelated PID."""
    pid = process if isinstance(process, int) else process.pid
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False, timeout=10)
    else:
        # Model/test launchers can own a separate process session. Capture their
        # actual ancestry before the parent exits instead of killing only one PGID.
        children = []
        proc = Path("/proc")
        if proc.is_dir():
            by_parent = {}
            for item in proc.iterdir():
                if not item.name.isdigit():
                    continue
                try:
                    fields = (item / "stat").read_text().rsplit(")", 1)[1].split()
                    by_parent.setdefault(int(fields[1]), []).append(int(item.name))
                except (OSError, ValueError, IndexError):
                    continue
            pending = [pid]
            while pending:
                current = pending.pop()
                for child in by_parent.get(current, []):
                    children.append(child)
                    pending.append(child)
        for child in reversed(children):
            try:
                os.kill(child, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if not isinstance(process, int):
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
        # The leader may exit before a descendant; kill the owned group too.
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for child in reversed(children):
            try:
                os.kill(child, signal.SIGKILL)
            except ProcessLookupError:
                pass


def supervise(argv, *, cwd, directory, total=1800, idle=600, cancel=None, env=None):
    """Run one native entry, retaining per-unit costs across explicit resumes."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    ledger = directory / "budget-ledger.json"
    spent = json.loads(ledger.read_text())["spent"] if ledger.exists() else {}
    if not isinstance(spent, dict) or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in spent.values()):
        raise ValueError("invalid unit-budget ledger")
    attempt = uuid.uuid4().hex
    events = directory / (attempt + ".events.jsonl")
    events.touch(exist_ok=False)
    child_env = dict(os.environ if env is None else env)
    child_env.update({EVENT_ENV: str(events.resolve()), TOTAL_ENV: str(total), IDLE_ENV: str(idle)})
    started = time.monotonic()
    budget = Budget(total, idle, spent, started)
    budget.apply({"event": "start", "at": started, "call": "entry", "key": identity(argv),
                  "label": "entry overhead", "parent": None, "container": True})
    process = subprocess.Popen(argv, cwd=cwd, env=child_env, shell=False,
                               start_new_session=os.name != "nt")
    reason = None
    prior_term = None
    if threading.current_thread() is threading.main_thread():
        prior_term = signal.getsignal(signal.SIGTERM)
        def cancelled_signal(_number, _frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, cancelled_signal)
    def cleanup():
        for pid in tuple(budget.owned):
            terminate_tree(pid)
        terminate_tree(process)
    def checkpoint():
        temp = ledger.with_suffix(".tmp")
        temp.write_text(json.dumps({"spent": budget.spent}, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(ledger)
    try:
        with events.open(encoding="utf-8") as stream:
            while True:
                # Only complete records count. Polling/mtime changes are not progress.
                while True:
                    pos = stream.tell()
                    line = stream.readline()
                    if not line.endswith("\n"):
                        stream.seek(pos)
                        break
                    budget.apply(json.loads(line))
                budget.tick(time.monotonic())
                checkpoint()
                if cancel is not None and cancel.is_set():
                    reason = {"reason": "cancelled"}
                elif budget.violation:
                    reason = budget.violation
                if reason:
                    cleanup()
                    break
                if process.poll() is not None:
                    break
                time.sleep(.05)
    except (KeyboardInterrupt, SystemExit):
        reason = {"reason": "cancelled"}
        cleanup()
    except BaseException:
        cleanup()
        raise
    finally:
        if prior_term is not None:
            signal.signal(signal.SIGTERM, prior_term)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        checkpoint()
    code = 130 if reason and reason["reason"] == "cancelled" else 124 if reason else process.returncode
    report = {"schema": "workflow.unit-budget-run.v1", "authorizes": [], "argv": argv,
              "exit_code": code, "reason": reason, "elapsed_seconds": time.monotonic() - started,
              "unit_seconds": total, "idle_seconds": idle, "spent": budget.spent,
              "active_at_stop": [{k: v for k, v in c.items() if k != "seen"} for c in budget.calls.values()]}
    (directory / (attempt + ".json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return code


def public_entry(kind, root, argv):
    """Return None inside the monitored child/read-only CLI; otherwise run it."""
    if os.environ.get(EVENT_ENV) or any(x in argv for x in ("--recommendation-only", "--help", "-h")):
        return None
    if "--action" in argv and argv[argv.index("--action") + 1:argv.index("--action") + 2] in (["inspect-selection"], ["preflight-session"]):
        return None
    args = list(argv)
    limits = [1800, 600]
    for i, flag in enumerate(("--unit-timeout-seconds", "--idle-timeout-seconds")):
        if flag in args:
            n = args.index(flag)
            limits[i] = int(args[n + 1])
            del args[n:n + 2]
    if any(v <= 0 for v in limits):
        raise ValueError("unit budgets must be positive")
    scope = None
    for flag in ("--out-dir", "--run-dir", "--plan"):
        if flag in args:
            scope = str(Path(args[args.index(flag) + 1]).resolve())
            break
    if scope is None:
        return None  # Native argparse owns invalid invocation diagnostics.
    scope_path = Path(scope)
    if not scope_path.is_relative_to(Path(root).resolve()):
        raise ValueError("workflow budget scope escapes repository")
    directory = Path(root) / "logs" / "workflow-unit-budgets" / kind / identity(scope)
    env = dict(os.environ)
    # The host transport must not retain the old implicit 600-second total.
    if env.get("SC_LLM_BACKEND") == "host-session" and "JIMUYUN_HOST_TIMEOUT_SECONDS" not in env:
        env["JIMUYUN_HOST_TIMEOUT_SECONDS"] = str(limits[0])
    return supervise([sys.executable, "-B", *args], cwd=root, directory=directory,
                     total=limits[0], idle=limits[1], env=env)
