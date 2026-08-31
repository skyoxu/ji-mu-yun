"""Canonical Quick Dev evidence primitives.

This module is deliberately independent from plan-local compatibility code.  It
owns the current evidence truth floor described by the Chapter 4/5/6 SPEC:
executor-only process receipts, judge-only observations, deterministic runtime
edges, typed closure validation, and current-snapshot resolution.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence


STAGES = ("red", "green", "refactor", "terminal")
SNAPSHOT_ROOT_KINDS = (
    "candidate_tree",
    "plan",
    "contract",
    "descriptor",
    "fixture",
    "source",
    "validator_judge",
    "plan_state_transition",
)
GOVERNANCE_ROOT_NAMES = {
    "registry",
    "architecture_registry",
    "memlog",
    "spine",
    "review",
    "binding",
    "authorization",
}
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_FAILURE_RE = re.compile(r"FAILURE_ID:([A-Z0-9][A-Z0-9._-]*)")
_PYTEST_CASE_RE = re.compile(
    r"(?:(\d+)\s+passed|(\d+)\s+failed|(\d+)\s+error(?:s)?|(\d+)\s+skipped)"
)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def _safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("path must be a non-empty repository-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError("path escapes repository")
    return path.as_posix()


def _resolve_regular_file(workspace: Path, relative: str) -> Path:
    relative = _safe_relative(relative)
    root = workspace.resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("path escapes repository") from exc
    if not target.is_file() or target.is_symlink():
        raise ValueError(f"bound file is missing or unsafe: {relative}")
    return target


def _atomic_json(path: Path, value: Mapping[str, Any]) -> Path:
    payload = canonical_bytes(dict(value))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"immutable evidence conflict: {path.name}")
        return path
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except FileExistsError as exc:
        raise ValueError(f"immutable evidence write raced: {path.name}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _atomic_bytes(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"immutable evidence conflict: {path.name}")
        return path
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except FileExistsError as exc:
        raise ValueError(f"immutable evidence write raced: {path.name}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _descriptor_identity(descriptor: Mapping[str, Any]) -> str:
    return sha256_value(dict(descriptor))


def _validate_descriptor(descriptor: Mapping[str, Any]) -> None:
    required = {"id", "executable", "argv", "cwd", "timeout_seconds", "shell"}
    if not isinstance(descriptor, Mapping) or set(descriptor) != required:
        raise ValueError("descriptor shape is invalid")
    if descriptor.get("shell") is not False:
        raise ValueError("descriptor must use shell=false")
    if not isinstance(descriptor.get("id"), str) or not descriptor["id"]:
        raise ValueError("descriptor id is invalid")
    if not isinstance(descriptor.get("executable"), str) or not descriptor["executable"]:
        raise ValueError("descriptor executable is invalid")
    argv = descriptor.get("argv")
    if not isinstance(argv, list) or any(not isinstance(item, str) for item in argv):
        raise ValueError("descriptor argv is invalid")
    cwd = descriptor.get("cwd")
    if cwd != ".":
        _safe_relative(cwd)
    timeout = descriptor.get("timeout_seconds")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("descriptor timeout is invalid")


def _hash_map(workspace: Path, refs: Sequence[str], *, fallback_key: str | None = None, fallback_hash: str | None = None) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in refs:
        path = _resolve_regular_file(workspace, raw)
        result[_safe_relative(raw)] = sha256_bytes(path.read_bytes())
    if not result and fallback_key and fallback_hash:
        result[_safe_relative(fallback_key)] = fallback_hash
    if not result:
        raise ValueError("at least one bound hash is required")
    return dict(sorted(result.items()))


def _case_count(output: str) -> int:
    total = 0
    for match in _PYTEST_CASE_RE.finditer(output):
        total += sum(int(value) for value in match.groups() if value is not None)
    return total or 1


def execute_descriptor(
    workspace: Path,
    run_dir: Path,
    stage: str,
    descriptor: Mapping[str, Any],
    *,
    candidate_hash: str,
    profile_identity: str,
    target_refs: Sequence[str],
    fixture_refs: Sequence[str],
    executor_identity: str = "quick-dev-process-executor.v1",
) -> dict[str, Any]:
    """Execute one frozen descriptor and persist only the process receipt."""
    if stage not in STAGES:
        raise ValueError("stage is invalid")
    _validate_descriptor(descriptor)
    if not isinstance(candidate_hash, str) or not _HASH_RE.fullmatch(candidate_hash):
        raise ValueError("candidate hash is invalid")
    if not isinstance(profile_identity, str) or not profile_identity:
        raise ValueError("profile identity is invalid")
    root = workspace.resolve()
    cwd = root if descriptor["cwd"] == "." else (root / _safe_relative(descriptor["cwd"])).resolve()
    try:
        cwd.relative_to(root)
    except ValueError as exc:
        raise ValueError("descriptor cwd escapes repository") from exc
    if not cwd.is_dir():
        raise ValueError("descriptor cwd is unavailable")

    descriptor_sha = _descriptor_identity(descriptor)
    target_hashes = _hash_map(root, list(target_refs), fallback_key="descriptor/target", fallback_hash=descriptor_sha)
    fixture_hashes = _hash_map(root, list(fixture_refs), fallback_key="descriptor/fixture", fallback_hash=descriptor_sha)
    started = datetime.now(timezone.utc)
    timed_out = False
    stdout = b""
    stderr = b""
    exit_code: int | None
    try:
        completed = subprocess.run(
            [descriptor["executable"], *descriptor["argv"]],
            cwd=cwd,
            shell=False,
            check=False,
            capture_output=True,
            timeout=descriptor["timeout_seconds"],
        )
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode("utf-8", errors="replace")
        if isinstance(stderr, str):
            stderr = stderr.encode("utf-8", errors="replace")
    ended = datetime.now(timezone.utc)

    evidence_dir = run_dir.resolve() / "canonical-evidence" / stage
    _atomic_bytes(evidence_dir / "stdout.bin", stdout)
    _atomic_bytes(evidence_dir / "stderr.bin", stderr)
    output_text = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
    receipt = {
        "schema": "quick-dev.process-receipt.v1",
        "receipt_id": f"RECEIPT-{stage.upper()}-{sha256_value([candidate_hash, descriptor_sha, stage])[7:19].upper()}",
        "descriptor_ref": f"descriptor:{descriptor['id']}",
        "stage": stage,
        "argv": [descriptor["executable"], *descriptor["argv"]],
        "cwd": "." if cwd == root else cwd.relative_to(root).as_posix(),
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "ended_at": ended.isoformat().replace("+00:00", "Z"),
        "process_attempts": 1,
        "test_executions": 1,
        "cases": _case_count(output_text),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "candidate_hash": candidate_hash,
        "descriptor_sha256": descriptor_sha,
        "target_hashes": target_hashes,
        "fixture_hashes": fixture_hashes,
        "profile_identity": profile_identity,
        "executor_identity": executor_identity,
    }
    _atomic_json(evidence_dir / "process-receipt.v1.json", receipt)
    return receipt


def _deterministic_failure_id(
    family: str,
    *,
    descriptor_sha256: str,
    candidate_hash: str,
    stage: str,
    observed_failure_ids: Sequence[str],
    receipt_fingerprint: str,
) -> str:
    digest = sha256_value(
        {
            "taxonomy": "quick-dev.failure-taxonomy.v1",
            "family": family,
            "descriptor_sha256": descriptor_sha256,
            "candidate_hash": candidate_hash,
            "stage": stage,
            "observed_failure_ids": sorted(set(observed_failure_ids)),
            "receipt_fingerprint": receipt_fingerprint,
        }
    )[7:23].upper()
    return f"QD-{family.upper().replace('_', '-').replace(' ', '-')}-{digest}"


def judge_receipt(
    run_dir: Path,
    stage: str,
    descriptor: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    expected_failure_ids: Sequence[str] = (),
    expected_exit: str | None = None,
    judge_identity: str = "quick-dev-independent-judge.v1",
) -> dict[str, Any]:
    """Classify an existing receipt without executing the SUT."""
    if stage not in STAGES:
        raise ValueError("stage is invalid")
    _validate_descriptor(descriptor)
    expected_descriptor = _descriptor_identity(descriptor)
    if receipt.get("schema") != "quick-dev.process-receipt.v1":
        raise ValueError("receipt schema is invalid")
    if receipt.get("descriptor_sha256") != expected_descriptor:
        raise ValueError("receipt descriptor binding is stale")
    if receipt.get("stage") != stage:
        raise ValueError("receipt stage is stale")
    if receipt.get("argv") != [descriptor["executable"], *descriptor["argv"]]:
        raise ValueError("receipt argv does not match descriptor")
    for field in ("candidate_hash", "stdout_sha256", "stderr_sha256"):
        if not isinstance(receipt.get(field), str) or not _HASH_RE.fullmatch(receipt[field]):
            raise ValueError(f"receipt {field} is invalid")

    evidence_dir = run_dir.resolve() / "canonical-evidence" / stage
    stdout_path, stderr_path = evidence_dir / "stdout.bin", evidence_dir / "stderr.bin"
    if not stdout_path.is_file() or not stderr_path.is_file():
        raise ValueError("receipt output bytes are missing")
    if sha256_bytes(stdout_path.read_bytes()) != receipt["stdout_sha256"] or sha256_bytes(stderr_path.read_bytes()) != receipt["stderr_sha256"]:
        raise ValueError("receipt output hash is stale")
    output = (stdout_path.read_bytes() + b"\n" + stderr_path.read_bytes()).decode("utf-8", errors="replace")
    observed_failure_ids = sorted(set(_FAILURE_RE.findall(output)))
    declared_failure_ids = sorted(set(expected_failure_ids))

    timed_out = receipt.get("timed_out") is True
    exit_code = receipt.get("exit_code")
    verification_outcome: str
    failure_family: str | None
    predicate_result: bool
    if timed_out:
        verification_outcome, failure_family, predicate_result = "blocked", "timeout-no-observation", False
    elif not isinstance(exit_code, int):
        verification_outcome, failure_family, predicate_result = "blocked", "test-harness-failure", False
    elif stage == "red":
        if exit_code == 0:
            verification_outcome, failure_family, predicate_result = "fail", "unexpected-green", False
        elif declared_failure_ids and observed_failure_ids == declared_failure_ids:
            verification_outcome, failure_family, predicate_result = "fail", "expected-red", True
        else:
            verification_outcome, failure_family, predicate_result = "fail", "semantic-contract-gap", False
    else:
        if exit_code == 0:
            verification_outcome, failure_family, predicate_result = "pass", None, True
        else:
            verification_outcome, failure_family, predicate_result = "fail", (
                "terminal-failure" if stage == "terminal" else "task-implementation-failure"
            ), False

    if expected_exit not in (None, "zero", "nonzero"):
        raise ValueError("expected exit is invalid")
    if expected_exit == "zero" and exit_code != 0:
        predicate_result = False
    if expected_exit == "nonzero" and (not isinstance(exit_code, int) or exit_code == 0):
        predicate_result = False

    receipt_fingerprint = sha256_value(dict(receipt))
    failure_id = None
    if failure_family is not None:
        failure_id = _deterministic_failure_id(
            failure_family,
            descriptor_sha256=expected_descriptor,
            candidate_hash=receipt["candidate_hash"],
            stage=stage,
            observed_failure_ids=observed_failure_ids,
            receipt_fingerprint=receipt_fingerprint,
        )
    observation = {
        "schema": "quick-dev.observation.v1",
        "observation_id": f"OBS-{stage.upper()}-{receipt_fingerprint[7:19].upper()}",
        "receipt_ref": f"canonical-evidence/{stage}/process-receipt.v1.json",
        "receipt_sha256": sha256_value(dict(receipt)),
        "stage": stage,
        "evidence_state": "observed-run",
        "verification_outcome": verification_outcome,
        "process_attempts": receipt["process_attempts"],
        "test_executions": receipt["test_executions"],
        "cases": receipt["cases"],
        "exit_code": exit_code,
        "timed_out": timed_out,
        "failure_family": failure_family,
        "failure_id": failure_id,
        "observed_failure_ids": observed_failure_ids,
        "expected_failure_ids": declared_failure_ids,
        "predicate_result": predicate_result,
        "judge_identity": judge_identity,
    }
    _atomic_json(evidence_dir / "observation.v1.json", observation)
    return observation


def runtime_assertion_edges(
    *,
    plan_id: str,
    plan_hash: str,
    slice_id: str,
    run_id: str,
    candidate_hash: str,
    stage: str,
    descriptor: Mapping[str, Any],
    receipt: Mapping[str, Any],
    observation: Mapping[str, Any],
    assertions: Sequence[Mapping[str, str]],
    selector_identity: str,
    producer_identity: str = "quick-dev-runtime-edge-validator.v1",
    validator_identity: str = "quick-dev-runtime-edge-validator.v1",
) -> list[dict[str, Any]]:
    """Build validated runtime edges after receipt and judge observation exist."""
    if stage not in STAGES or observation.get("stage") != stage or receipt.get("stage") != stage:
        raise ValueError("runtime edge stage lineage is invalid")
    descriptor_sha = _descriptor_identity(descriptor)
    if receipt.get("descriptor_sha256") != descriptor_sha:
        raise ValueError("runtime edge descriptor lineage is stale")
    if observation.get("receipt_sha256") != sha256_value(dict(receipt)):
        raise ValueError("runtime edge receipt lineage is stale")
    if not isinstance(assertions, Sequence) or not assertions:
        raise ValueError("runtime edges require assertions")

    targets = receipt.get("target_hashes")
    fixtures = receipt.get("fixture_hashes")
    if not isinstance(targets, dict) or not targets or not isinstance(fixtures, dict) or not fixtures:
        raise ValueError("runtime edge target/fixture lineage is incomplete")
    target_ref, target_sha = next(iter(sorted(targets.items())))
    fixture_ref, fixture_sha = next(iter(sorted(fixtures.items())))
    result: list[dict[str, Any]] = []
    for assertion in assertions:
        required = {"acceptance_id", "assertion_id", "case_source_ref"}
        if not isinstance(assertion, Mapping) or not required.issubset(assertion):
            raise ValueError("runtime assertion is invalid")
        edge = {
            "schema": "quick-dev.runtime-assertion-edge.v1",
            "plan_id": plan_id,
            "plan_hash": plan_hash,
            "slice_id": slice_id,
            "candidate_hash": candidate_hash,
            "observation_id": observation["observation_id"],
            "acceptance_id": assertion["acceptance_id"],
            "assertion_id": assertion["assertion_id"],
            "selector_identity": selector_identity,
            "stage": stage,
            "run_id": run_id,
            "receipt_ref": observation["receipt_ref"],
            "receipt_sha256": observation["receipt_sha256"],
            "observation_ref": f"canonical-evidence/{stage}/observation.v1.json",
            "observation_sha256": sha256_value(dict(observation)),
            "descriptor_sha256": descriptor_sha,
            "target_ref": target_ref,
            "target_sha256": target_sha,
            "fixture_ref": fixture_ref,
            "fixture_sha256": fixture_sha,
            "case_source_ref": assertion["case_source_ref"],
            "verification_outcome": observation["verification_outcome"],
            "failure_family": observation["failure_family"],
            "failure_id": observation["failure_id"],
            "producer_identity": producer_identity,
            "validator_identity": validator_identity,
            "derived_by": "deterministic-validator",
        }
        result.append(edge)
    return result


def validate_runtime_closure(
    tuples: Sequence[Mapping[str, Any]],
    expected_tuple_keys: Iterable[str],
    *,
    current_snapshot_sha256: str | None = None,
) -> tuple[bool, list[str]]:
    """Validate tuple-key uniqueness and exact V6A closure."""
    findings: list[str] = []
    expected = set(expected_tuple_keys)
    actual: list[str] = []
    for index, item in enumerate(tuples):
        if not isinstance(item, Mapping):
            findings.append(f"tuple[{index}]:not-object")
            continue
        slice_id, acceptance_id, stage = item.get("slice_id"), item.get("acceptance_id"), item.get("stage")
        key = item.get("tuple_key")
        canonical = f"{slice_id}|{acceptance_id}|{stage}"
        if key != canonical:
            findings.append(f"tuple[{index}]:tuple-key-mismatch")
        if stage not in STAGES:
            findings.append(f"tuple[{index}]:stage-invalid")
        for field in ("runtime_edge_sha256", "current_snapshot_sha256"):
            if not isinstance(item.get(field), str) or not _HASH_RE.fullmatch(item[field]):
                findings.append(f"tuple[{index}]:{field}-invalid")
        if current_snapshot_sha256 is not None and item.get("current_snapshot_sha256") != current_snapshot_sha256:
            findings.append(f"tuple[{index}]:snapshot-stale")
        if isinstance(key, str):
            actual.append(key)
    if len(actual) != len(set(actual)):
        findings.append("tuple-key-duplicate")
    if set(actual) != expected:
        findings.append("tuple-key-set-mismatch")
    if len(actual) != len(expected):
        findings.append("tuple-cardinality-mismatch")
    return not findings, findings


def _hash_path(path: Path) -> str:
    if path.is_symlink():
        raise ValueError("snapshot root may not be a symlink")
    if path.is_file():
        return sha256_bytes(path.read_bytes())
    if path.is_dir():
        rows: list[tuple[str, str]] = []
        for child in sorted(path.rglob("*")):
            if child.is_symlink():
                raise ValueError("snapshot tree contains a symlink")
            if child.is_file():
                rows.append((child.relative_to(path).as_posix(), sha256_bytes(child.read_bytes())))
        return sha256_value(rows)
    raise ValueError("snapshot root is missing")


def build_current_snapshot(
    workspace: Path,
    roots: Sequence[Mapping[str, str]],
    *,
    source_commit: str,
    base_commit: str | None = None,
) -> dict[str, Any]:
    """Resolve the closed eight-kind runtime snapshot."""
    root = workspace.resolve()
    if len(roots) != len(SNAPSHOT_ROOT_KINDS):
        raise ValueError("current snapshot must contain exactly eight roots")
    observed_kinds: list[str] = []
    resolved: list[dict[str, str]] = []
    allowed_prefixes: list[str] = []
    for item in roots:
        if not isinstance(item, Mapping):
            raise ValueError("snapshot root is invalid")
        kind, raw = item.get("root_kind"), item.get("repository_relative_posix_path")
        reason = item.get("inclusion_reason")
        if kind in GOVERNANCE_ROOT_NAMES or kind not in SNAPSHOT_ROOT_KINDS:
            raise ValueError(f"snapshot root kind is not runtime authority: {kind}")
        if not isinstance(raw, str) or not isinstance(reason, str) or not reason:
            raise ValueError("snapshot root fields are invalid")
        relative = _safe_relative(raw)
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("snapshot root escapes repository") from exc
        digest = _hash_path(target)
        resolved.append(
            {
                "root_kind": kind,
                "repository_relative_posix_path": relative,
                "content_sha256": digest,
                "source_commit": source_commit,
                "inclusion_reason": reason,
            }
        )
        observed_kinds.append(kind)
        allowed_prefixes.append(relative.rstrip("/"))
    if set(observed_kinds) != set(SNAPSHOT_ROOT_KINDS) or len(observed_kinds) != len(set(observed_kinds)):
        raise ValueError("snapshot root kinds must be an exact unique set")

    git_delta = {"base_commit": base_commit or source_commit, "additions": [], "deletions": [], "renames": []}
    if (root / ".git").exists() and (base_commit or source_commit):
        base = base_commit or source_commit
        completed = subprocess.run(
            ["git", "diff", "--name-status", "-M", base, "--"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise ValueError("git delta cannot be resolved")
        for line in completed.stdout.splitlines():
            parts = line.split("\t")
            if not parts:
                continue
            status = parts[0]
            if status.startswith("R") and len(parts) == 3:
                before, after = map(_safe_relative, parts[1:])
                after_path = root / after
                git_delta["renames"].append(
                    {
                        "from_path": before,
                        "to_path": after,
                        "before_sha256": sha256_bytes(
                            subprocess.run(["git", "show", f"{base}:{before}"], cwd=root, capture_output=True, check=True).stdout
                        ),
                        "after_sha256": _hash_path(after_path),
                    }
                )
            elif status == "A" and len(parts) == 2:
                path = _safe_relative(parts[1])
                git_delta["additions"].append({"path": path, "after_sha256": _hash_path(root / path)})
            elif status == "D" and len(parts) == 2:
                path = _safe_relative(parts[1])
                git_delta["deletions"].append(
                    {
                        "path": path,
                        "before_sha256": sha256_bytes(
                            subprocess.run(["git", "show", f"{base}:{path}"], cwd=root, capture_output=True, check=True).stdout
                        ),
                    }
                )
            elif len(parts) == 2:
                path = _safe_relative(parts[1])
                git_delta["deletions"].append(
                    {
                        "path": path,
                        "before_sha256": sha256_bytes(
                            subprocess.run(["git", "show", f"{base}:{path}"], cwd=root, capture_output=True, check=True).stdout
                        ),
                    }
                )
                git_delta["additions"].append({"path": path, "after_sha256": _hash_path(root / path)})

        changed_paths = {
            row["path"] for row in git_delta["additions"] + git_delta["deletions"]
        } | {
            row["from_path"] for row in git_delta["renames"]
        } | {
            row["to_path"] for row in git_delta["renames"]
        }
        for path in changed_paths:
            if not any(path == prefix or path.startswith(prefix + "/") for prefix in allowed_prefixes):
                raise ValueError(f"git delta contains an unlisted runtime root: {path}")

    manifest = {
        "schema": "current-snapshot-resolver.v1",
        "roots": sorted(resolved, key=lambda item: SNAPSHOT_ROOT_KINDS.index(item["root_kind"])),
        "git_delta": git_delta,
        "excluded_roots": sorted(GOVERNANCE_ROOT_NAMES),
    }
    manifest["sha256"] = sha256_value(manifest)
    return manifest


def probe_execution_environment() -> dict[str, str]:
    """Record the resolved environment without imposing exact universal versions."""
    python_version = subprocess.run(
        [sys.executable, "--version"], capture_output=True, text=True, check=False
    )
    pytest_version = subprocess.run(
        [sys.executable, "-m", "pytest", "--version"], capture_output=True, text=True, check=False
    )
    return {
        "launcher": sys.executable,
        "interpreter_version": (python_version.stdout or python_version.stderr).strip(),
        "test_runner_version": (pytest_version.stdout or pytest_version.stderr).strip(),
    }
