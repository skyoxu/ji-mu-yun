#!/usr/bin/env python3
"""ADR-0041: explicit caller-session transport, never lifecycle authority.

A trusted host agent answers actual pending requests. This is not a model API,
process sandbox, fixture cache, or permission to overwrite native evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

ENV = "JIMUYUN_HOST_SESSION_DIR"
TIMEOUT_ENV = "JIMUYUN_HOST_TIMEOUT_SECONDS"
MAX_TIMEOUT_SECONDS = 3600


def timeout_budget(native_timeout, override=None):
    """ADR-0041: only an explicit bounded host choice overrides a native budget."""
    if isinstance(native_timeout, bool) or not math.isfinite(native_timeout) or native_timeout <= 0:
        raise ValueError("native timeout must be finite and positive")
    if override is None:
        return native_timeout
    if isinstance(override, bool) or str(override).strip() != str(override):
        raise ValueError("host timeout must be an integer number of seconds")
    try:
        value = int(override)
    except (TypeError, ValueError) as exc:
        raise ValueError("host timeout must be an integer number of seconds") from exc
    if str(value) != str(override) or not 1 <= value <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"host timeout must be between 1 and {MAX_TIMEOUT_SECONDS} seconds")
    return value


def digest(value):
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                              separators=(",", ":")).encode()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def create(path, value):
    # Complete bytes become visible atomically; unique immutable target names.
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink()


def contained(root, path):
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("host session path escapes repository logs")
    return resolved


def session(directory, root=None):
    directory = Path(directory).resolve()
    data = read(directory / "session.json")
    if data.get("schema") != "jimuyun.host-session.v1" or data.get("authorizes") != []:
        raise ValueError("invalid host session")
    repository = Path(data["repository_root"]).resolve()
    if root is not None and repository != Path(root).resolve():
        raise ValueError("host session belongs to another repository")
    contained(repository / "logs", directory)
    return directory, data


def initialize(root, directory, caller):
    root = root.resolve()
    directory = contained(root / "logs", directory)
    if not caller.strip():
        raise ValueError("caller label is required")
    directory.mkdir(parents=True, exist_ok=True)
    data = {"schema": "jimuyun.host-session.v1", "session_id": uuid.uuid4().hex,
            "repository_root": str(root), "caller": caller, "authorizes": []}
    create(directory / "session.json", data)
    return data


def pending(directory):
    directory, data = session(directory)
    result = []
    # Listing is discovery only, never latest-success or evidence selection.
    for path in sorted(directory.glob("*/request.json")):
        request = read(path)
        if not (path.parent / "result.json").exists() and not (path.parent / "response.json").exists():
            result.append({"request_id": request["request_id"], "request_path": str(path),
                           "deadline": request["deadline"], "expired": time.time() >= request["deadline"],
                           "mode": request["mode"]})
    return result


def respond(directory, request_id, request_hash, output_text):
    directory, data = session(directory)
    if not request_id or any(c not in "0123456789abcdef" for c in request_id):
        raise ValueError("invalid request id")
    call = contained(directory, directory / request_id)
    request = read(call / "request.json")
    if digest(request) != request_hash or request["session_id"] != data["session_id"]:
        raise ValueError("request binding mismatch")
    if time.time() >= request["deadline"] or (call / "result.json").exists():
        raise ValueError("request is expired or already completed")
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError("nonempty output text is required")
    response = {"schema": "jimuyun.host-response.v1", "session_id": data["session_id"],
                "request_id": request_id, "request_sha256": request_hash,
                "output_text": output_text, "authorizes": []}
    create(call / "response.json", response)
    return {"status": "submitted", "request_id": request_id, "authorizes": []}


def execute(*, root, prompt, output_last_message, timeout_sec, mode):
    try:
        directory, data = session(os.environ.get(ENV, ""), root)
        output = Path(output_last_message).resolve()  # Native caller-owned sink; may be a temporary file.
        if mode not in {"read-only", "workspace-write"}:
            raise ValueError("unsupported host session mode")
        override = os.environ.get(TIMEOUT_ENV)
        effective_timeout = timeout_budget(timeout_sec, override)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return 2, f"host-session unavailable: {exc}\n", ["host-session"]
    request_id = uuid.uuid4().hex
    call = directory / request_id
    call.mkdir()
    request = {"schema": "jimuyun.host-request.v1", "session_id": data["session_id"],
               "request_id": request_id, "repository_root": str(Path(root).resolve()),
               "prompt": prompt, "mode": mode, "deadline": time.time() + effective_timeout,
               "native_timeout_seconds": timeout_sec, "effective_timeout_seconds": effective_timeout,
               "timeout_source": "explicit-host-override" if override is not None else "native-worker",
               "output_path": str(output), "authorizes": []}
    create(call / "request.json", request)
    binding = digest(request)
    deadline = time.monotonic() + effective_timeout
    code, status, text = 124, "timeout", ""
    try:
        while time.monotonic() < deadline:
            if (call / "cancel.json").exists():
                code, status = 130, "cancelled"
                break
            if (call / "response.json").exists():
                response = read(call / "response.json")
                if (read(call / "request.json") != request or
                    response.get("schema") != "jimuyun.host-response.v1" or
                    response.get("session_id") != data["session_id"] or
                    response.get("request_id") != request_id or
                    response.get("request_sha256") != binding or response.get("authorizes") != [] or
                    not isinstance(response.get("output_text"), str) or not response["output_text"].strip()):
                    code, status = 2, "invalid-response"
                    break
                text = response["output_text"]
                code, status = 0, "returned"
                break
            time.sleep(min(.1, max(0, deadline - time.monotonic())))
    except (OSError, ValueError, TypeError):
        code, status = 2, "invalid-response"
    except BaseException:
        create(call / "result.json", {"status": "interrupted", "authorizes": []})
        raise
    if code == 0:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text.rstrip() + "\n", encoding="utf-8")
    result = {"backend": "host-session", "status": status, "request_id": request_id,
              "request_sha256": binding, "caller": data["caller"], "authorizes": []}
    create(call / "result.json", result)
    return code, json.dumps(result) + "\n", ["host-session", request_id]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init")
    init.add_argument("--root", type=Path, default=Path.cwd())
    init.add_argument("--session", type=Path, required=True)
    init.add_argument("--caller", required=True)
    for name in ("pending", "respond", "cancel"):
        command = sub.add_parser(name)
        command.add_argument("--session", type=Path, required=True)
        if name != "pending":
            command.add_argument("--request-id", required=True)
        if name == "respond":
            command.add_argument("--request-sha256", required=True)
            command.add_argument("--output-text-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "init":
            value = initialize(args.root, args.session, args.caller)
        elif args.action == "pending":
            value = pending(args.session)
        elif args.action == "respond":
            value = respond(args.session, args.request_id, args.request_sha256,
                            args.output_text_file.read_text(encoding="utf-8"))
        else:
            directory, _ = session(args.session)
            if not args.request_id or any(c not in "0123456789abcdef" for c in args.request_id):
                raise ValueError("invalid request id")
            call = contained(directory, directory / args.request_id)
            read(call / "request.json")
            create(call / "cancel.json", {"authorizes": []})
            value = {"status": "cancel-requested", "authorizes": []}
        print(json.dumps(value, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc), "authorizes": []}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
