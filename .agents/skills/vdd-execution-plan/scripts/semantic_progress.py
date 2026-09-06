"""ADR-0041: append-only execution diagnostics, never semantic authority."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid


def emit(out_dir, stage, event, call_id, **fields):
    path = Path(out_dir) / ".compiler-work" / "compiler-progress.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"schema": "vdd.compiler-progress.v1", "stage": stage, "event": event,
              "call_id": call_id, "pid": os.getpid(),
              "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def stage_call(progress_dir, stage, function, *args, **kwargs):
    return _call(progress_dir, stage, "stage", function, args, kwargs, {})


def worker_call(function, *, progress_dir, progress_stage, **kwargs):
    details = {"timeout_seconds": kwargs.get("timeout_sec"),
               "output_last_message": str(kwargs.get("output_last_message", "")),
               "backend": kwargs.get("backend")}
    return _call(progress_dir, progress_stage, "worker", function, (), kwargs, details)


def _call(out_dir, stage, kind, function, args, kwargs, details):
    call_id = uuid.uuid4().hex
    started = time.monotonic()
    emit(out_dir, stage, kind + "-started", call_id, **details)
    try:
        result = function(*args, **kwargs)
    except BaseException as exc:
        emit(out_dir, stage, kind + "-raised", call_id,
             elapsed_seconds=time.monotonic() - started, error_type=type(exc).__name__)
        raise
    fields = {"elapsed_seconds": time.monotonic() - started}
    if kind == "worker":
        fields["exit_code"] = result[0]
    elif isinstance(result, dict):
        fields["result_status"] = result.get("status")
    emit(out_dir, stage, kind + "-returned", call_id, **fields)
    return result
