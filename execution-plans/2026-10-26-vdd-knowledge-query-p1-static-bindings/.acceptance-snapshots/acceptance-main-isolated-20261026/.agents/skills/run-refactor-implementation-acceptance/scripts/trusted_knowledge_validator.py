"""ADR-0053/0058: execute immutable main code against candidate data only.

This private worker adds no selectable trust source or execution authority.
Its temporary Git view pins actual main without modifying repository refs.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

FILES = ("knowledge_context_validation.py", "_knowledge_locator_core.py")
OPERATIONS = {"validate_context", "validate_worktree_sources", "validate_catalog_freshness", "refresh_context_read_set"}
FLAGS = dict(verify_catalog=True, verify_sources=True, expected_consumer="refactor-acceptance",
             require_selection=True, require_preflight=True)
STDLIB = {"__future__", "hashlib", "json", "copy", "re", "subprocess", "pathlib", "typing", "os", "tempfile"}
GIT = shutil.which("git")


def _environment():
    if not GIT:
        raise ValueError("trusted validator Git is unavailable")
    result = {k: os.environ[k] for k in ("SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP") if k in os.environ}
    result.update(PATH=str(Path(GIT).resolve().parent) + os.pathsep + os.defpath,
                  GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                  GIT_CONFIG_SYSTEM=os.devnull, GIT_NO_REPLACE_OBJECTS="1", GIT_TERMINAL_PROMPT="0")
    return result


def _git(root, *arguments):
    result = subprocess.run([GIT, "-C", str(root), *arguments], env=_environment(),
                            shell=False, capture_output=True, check=False, timeout=30)
    if result.returncode:
        raise ValueError("trusted validator main Git object is unavailable")
    return result.stdout


def _main(root):
    if Path(_git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve() != root:
        raise ValueError("trusted validator candidate root is invalid")
    value = _git(root, "rev-parse", "--verify", "refs/heads/main^{commit}").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("trusted validator main identity is invalid")
    return value


def _dependencies(payload):
    for node in ast.walk(ast.parse(payload)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module == "_knowledge_locator_core" and node.level in (0, 1):
                continue
            if node.level:
                raise ValueError("trusted validator dependency is unsupported")
            names = [node.module]
        else:
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"__import__", "eval", "exec"}:
                raise ValueError("trusted validator dynamic dependency is unsupported")
            continue
        if any(name not in STDLIB for name in names):
            raise ValueError("trusted validator dependency is unsupported")


def _safe_file(root, raw):
    if not isinstance(raw, str) or "\\" in raw:
        raise ValueError("trusted validator data path is invalid")
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts or any(p in {".", ".."} for p in path.parts) or ":" in raw:
        raise ValueError("trusted validator data path escapes root")
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("trusted validator data path uses a symlink")
    try:
        current.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError("trusted validator data path escapes root") from exc
    return current


def _check_data_paths(root, payload):
    # Main retains all schema, authorization and source hash decisions.
    for path in ("knowledge/catalogs/repository-knowledge-catalog.v2.json",
                 "knowledge/catalogs/repository-knowledge-catalog.v1.json",
                 "knowledge/projections/consumer-projections.v1.json",
                 "knowledge/policies/consumer-policies.v2.json",
                 "knowledge/policies/source-exclusions.v1.json",
                 "knowledge/snapshots/repository-source-snapshot.v1.json",
                 "knowledge/evaluation/repository-knowledge-query-suite.v1.json",
                 "knowledge/indexes/current.json"):
        _safe_file(root, path)
    pointer = _safe_file(root, "knowledge/indexes/current.json")
    if pointer.is_file():
        value = json.loads(pointer.read_bytes())
        generation = value.get("generation_id") if isinstance(value, dict) else None
        if isinstance(generation, str) and re.fullmatch(r"[0-9a-f]{64}", generation):
            parent = "knowledge/indexes/generations/" + generation + "/"
            manifest = _safe_file(root, parent + "manifest.json")
            if manifest.is_file():
                body = json.loads(manifest.read_bytes())
                artifacts = body.get("artifacts") if isinstance(body, dict) else None
                report = artifacts.get("query_report") if isinstance(artifacts, dict) else None
                if isinstance(report, dict) and isinstance(report.get("bundle_path"), str):
                    _safe_file(root, parent + report["bundle_path"])
    result = payload.get("locator_result") if isinstance(payload, dict) else None
    candidates = result.get("candidates", []) if isinstance(result, dict) else []
    if isinstance(candidates, list):
        for item in candidates:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("path"), str):
                _safe_file(root, item["path"])
            read_set = item.get("read_set", [])
            if isinstance(read_set, list):
                for row in read_set:
                    if isinstance(row, dict) and isinstance(row.get("path"), str):
                        _safe_file(root, row["path"])


def _run_child(directory, request, *, timeout=600):
    # The child emits only its completed result;600 seconds without it is idle.
    if (directory / "worker.py").is_symlink() or (directory / "worker.py").read_bytes() != Path(__file__).read_bytes():
        raise ValueError("trusted validator worker identity mismatch")
    environment = _environment()
    environment.update(GIT_DIR=str(directory / "git-view"), GIT_WORK_TREE=request["root"],
                       GIT_ALTERNATE_OBJECT_DIRECTORIES=request["objects"])
    process = subprocess.Popen([sys.executable, "-I", "-S", "-B", str(directory / "worker.py")],
                               cwd=directory, env=environment, shell=False,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=os.name != "nt",
                               creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
    try:
        stdout, stderr = process.communicate(json.dumps(request).encode(), timeout=timeout)
    except BaseException:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            import signal
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.communicate(timeout=10)
        raise
    if process.returncode or stderr or len(stdout) > 4 * 1024 * 1024:
        raise ValueError("trusted validator child failed")
    try:
        value = json.loads(stdout)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("trusted validator child response is invalid") from exc
    expected = {"nonce", "main", "hashes", "operation", "result"}
    if not isinstance(value, dict) or set(value) != expected or any(value[key] != request[key] for key in expected - {"result"}):
        raise ValueError("trusted validator child identity is invalid")
    if request["operation"] == "refresh_context_read_set":
        if not isinstance(value["result"], dict):
            raise ValueError("trusted validator refresh response is invalid")
    elif value["result"] is not None and not isinstance(value["result"], str):
        raise ValueError("trusted validator validation response is invalid")
    return value["result"]


class TrustedMainValidator:
    def __init__(self, repository_root, error_type=ValueError):
        self.root = Path(repository_root).resolve()
        self.error_type = error_type
        self.commit = _main(self.root)
        self.blobs = {}
        for name in FILES:
            path = "scripts/python/" + name
            entry = _git(self.root, "ls-tree", "-z", self.commit, "--", path)
            parts = entry.rstrip(b"\0").split(b"\t")
            if len(parts) != 2 or parts[1].decode() != path or parts[0].split()[:2] not in ([b"100644", b"blob"], [b"100755", b"blob"]):
                raise ValueError("trusted validator main dependency is missing or unsafe")
            data = _git(self.root, "show", self.commit + ":" + path)
            _dependencies(data)
            self.blobs[name] = data
        common = Path(_git(self.root, "rev-parse", "--git-common-dir").decode().strip())
        self.objects = str(((self.root / common) if not common.is_absolute() else common).resolve() / "objects")

    def _call(self, operation, payload=None):
        try:
            if operation not in OPERATIONS:
                raise ValueError("trusted validator operation is invalid")
            if _main(self.root) != self.commit:
                raise ValueError("trusted validator main changed")
            _check_data_paths(self.root, payload)
            with tempfile.TemporaryDirectory(prefix="acceptance-trusted-main-") as temporary:
                directory = Path(temporary).resolve()
                for name, data in self.blobs.items():
                    (directory / name).write_bytes(data)
                (directory / "worker.py").write_bytes(Path(__file__).read_bytes())
                subprocess.run([GIT, "init", "--bare", "-q", str(directory / "git-view")],
                               env=_environment(), shell=False, check=True, capture_output=True, timeout=30)
                ref = directory / "git-view/refs/heads/main"
                ref.parent.mkdir(parents=True, exist_ok=True)
                ref.write_text(self.commit + "\n", encoding="ascii")
                request = dict(root=str(self.root), objects=self.objects, main=self.commit,
                               hashes={name: hashlib.sha256(data).hexdigest() for name, data in self.blobs.items()},
                               operation=operation, nonce=uuid.uuid4().hex, payload=payload)
                result = _run_child(directory, request)
            if _main(self.root) != self.commit:
                raise ValueError("trusted validator main changed")
            return result
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            raise self.error_type(str(exc)) from exc

    def _root(self, root):
        if Path(root).resolve() != self.root:
            raise self.error_type("trusted validator data root changed")

    def validate_context(self, payload, *, repository_root, **flags):
        self._root(repository_root)
        if flags != FLAGS:
            raise self.error_type("trusted validator context flags are invalid")
        return self._call("validate_context", payload)

    def validate_worktree_sources(self, payload, repository_root):
        self._root(repository_root)
        return self._call("validate_worktree_sources", payload)

    def validate_catalog_freshness(self, repository_root):
        self._root(repository_root)
        return self._call("validate_catalog_freshness")

    def refresh_context_read_set(self, payload, repository_root):
        self._root(repository_root)
        return self._call("refresh_context_read_set", payload)


def _child():
    request = json.load(sys.stdin)
    if not isinstance(request, dict) or set(request) != {"root", "objects", "main", "hashes", "operation", "nonce", "payload"}:
        raise ValueError("invalid trusted validator request")
    if request["operation"] not in OPERATIONS or set(request["hashes"]) != set(FILES):
        raise ValueError("invalid trusted validator operation or dependency")
    directory = Path(__file__).resolve().parent
    modules = {}
    for name in reversed(FILES):
        path = directory / name
        if path.is_symlink():
            raise ValueError("unsafe trusted validator module")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != request["hashes"][name]:
            raise ValueError("trusted validator identity mismatch")
        _dependencies(data)
        module_name = Path(name).stem
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        # Execute held verified bytes, not a second unchecked file read.
        exec(compile(data, str(path), "exec"), module.__dict__)
        modules[module_name] = module
    validator = modules["knowledge_context_validation"]
    root = Path(request["root"]).resolve()
    _check_data_paths(root, request["payload"])
    if request["operation"] == "validate_context":
        result = validator.validate_context(request["payload"], repository_root=root, **FLAGS)
    elif request["operation"] == "validate_catalog_freshness":
        result = validator.validate_catalog_freshness(root)
    else:
        result = getattr(validator, request["operation"])(request["payload"], root)
    response = {key: request[key] for key in ("nonce", "main", "hashes", "operation")}
    response["result"] = result
    print(json.dumps(response, sort_keys=True))


if __name__ == "__main__":
    try:
        _child()
    except Exception:
        # Do not disclose candidate content, credentials or untrusted diagnostics.
        raise SystemExit(1)
