"""Current Quick Dev runtime evidence primitives."""
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
ROOT_KINDS = ("candidate_tree", "plan", "contract", "descriptor", "fixture", "source", "validator_judge", "plan_state_transition")
GOVERNANCE_ROOTS = {"registry", "architecture_registry", "memlog", "spine", "review", "binding", "authorization"}
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
FAILURE_RE = re.compile(r"FAILURE_ID:([A-Z0-9][A-Z0-9._-]*)")
PYTEST_COUNT_RE = re.compile(r"(\d+)\s+(passed|failed|errors?|skipped)")


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("path must be a repository-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError("path escapes repository")
    return path.as_posix()


def resolve_file(root: Path, relative: str) -> Path:
    relative = safe_relative(relative)
    workspace = root.resolve()
    target = (workspace / relative).resolve()
    try:
        target.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("path escapes repository") from exc
    if not target.is_file() or target.is_symlink():
        raise ValueError(f"bound file is missing or unsafe: {relative}")
    return target


def create_immutable(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"immutable artifact conflict: {path}")
        return path
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != payload:
                raise ValueError(f"immutable artifact raced: {path}")
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def create_json(path: Path, value: Mapping[str, Any]) -> Path:
    return create_immutable(path, canonical_bytes(dict(value)))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def validate_descriptor(descriptor: Mapping[str, Any]) -> None:
    required = {"id", "executable", "argv", "cwd", "timeout_seconds", "shell"}
    if not isinstance(descriptor, Mapping) or set(descriptor) != required:
        raise ValueError("descriptor shape is invalid")
    if descriptor.get("shell") is not False:
        raise ValueError("descriptor must use shell=false")
    if not isinstance(descriptor.get("id"), str) or not descriptor["id"]:
        raise ValueError("descriptor id is invalid")
    if not isinstance(descriptor.get("executable"), str) or not descriptor["executable"]:
        raise ValueError("descriptor executable is invalid")
    if not isinstance(descriptor.get("argv"), list) or any(not isinstance(item, str) for item in descriptor["argv"]):
        raise ValueError("descriptor argv is invalid")
    cwd = descriptor.get("cwd")
    if cwd != ".":
        safe_relative(cwd)
    timeout = descriptor.get("timeout_seconds")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("descriptor timeout is invalid")


def hash_refs(root: Path, refs: Sequence[str]) -> dict[str, str]:
    if not refs:
        raise ValueError("target/fixture refs must be explicit and non-empty")
    result: dict[str, str] = {}
    for ref in refs:
        relative = safe_relative(ref)
        result[relative] = sha256_bytes(resolve_file(root, relative).read_bytes())
    return dict(sorted(result.items()))


def process_counts(output: str, *, timed_out: bool, exit_code: int | None) -> tuple[int, int]:
    total = sum(int(match.group(1)) for match in PYTEST_COUNT_RE.finditer(output))
    if total == 0 and not timed_out and isinstance(exit_code, int) and (exit_code == 0 or FAILURE_RE.search(output)):
        total = 1
    return (1 if total > 0 else 0, total)


def execute_process(workspace: Path, run_dir: Path, stage: str, descriptor: Mapping[str, Any], *, candidate_hash: str, profile_identity: str, target_refs: Sequence[str], fixture_refs: Sequence[str]) -> dict[str, Any]:
    """Executor trust zone: execute the SUT and persist only process facts."""
    if stage not in STAGES:
        raise ValueError("stage is invalid")
    validate_descriptor(descriptor)
    if not HASH_RE.fullmatch(candidate_hash or ""):
        raise ValueError("candidate hash is invalid")
    if not isinstance(profile_identity, str) or not profile_identity:
        raise ValueError("profile identity is invalid")
    root = workspace.resolve()
    cwd = root if descriptor["cwd"] == "." else (root / safe_relative(descriptor["cwd"])).resolve()
    try:
        cwd.relative_to(root)
    except ValueError as exc:
        raise ValueError("descriptor cwd escapes repository") from exc
    if not cwd.is_dir():
        raise ValueError("descriptor cwd is unavailable")
    target_hashes, fixture_hashes = hash_refs(root, target_refs), hash_refs(root, fixture_refs)
    descriptor_sha = sha256_value(dict(descriptor))
    started = datetime.now(timezone.utc)
    stdout, stderr, timed_out = b"", b"", False
    exit_code: int | None
    try:
        completed = subprocess.run([descriptor["executable"], *descriptor["argv"]], cwd=cwd, shell=False, check=False, capture_output=True, timeout=descriptor["timeout_seconds"])
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out, exit_code = True, None
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        if isinstance(stdout, str): stdout = stdout.encode("utf-8", errors="replace")
        if isinstance(stderr, str): stderr = stderr.encode("utf-8", errors="replace")
    ended = datetime.now(timezone.utc)
    evidence = run_dir.resolve() / "canonical-evidence" / stage
    create_immutable(evidence / "stdout.bin", stdout)
    create_immutable(evidence / "stderr.bin", stderr)
    output = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
    test_executions, cases = process_counts(output, timed_out=timed_out, exit_code=exit_code)
    receipt = {
        "schema": "quick-dev.process-receipt.v2",
        "receipt_id": f"RECEIPT-{stage.upper()}-{sha256_value([candidate_hash, descriptor_sha, stage])[7:19].upper()}",
        "stage": stage, "descriptor_ref": f"descriptor:{descriptor['id']}",
        "argv": [descriptor["executable"], *descriptor["argv"]], "cwd": "." if cwd == root else cwd.relative_to(root).as_posix(),
        "started_at": started.isoformat().replace("+00:00", "Z"), "ended_at": ended.isoformat().replace("+00:00", "Z"),
        "process_attempts": 1, "test_executions": test_executions, "cases": cases,
        "exit_code": exit_code, "timed_out": timed_out,
        "stdout_sha256": sha256_bytes(stdout), "stderr_sha256": sha256_bytes(stderr),
        "candidate_hash": candidate_hash, "descriptor_sha256": descriptor_sha,
        "target_hashes": target_hashes, "fixture_hashes": fixture_hashes,
        "profile_identity": profile_identity, "executor_identity": "quick-dev-process-executor.v2",
    }
    create_json(evidence / "process-receipt.v2.json", receipt)
    return receipt


def deterministic_failure_id(family: str, descriptor_sha: str, candidate_hash: str, stage: str, observed: Sequence[str], receipt_sha: str) -> str:
    digest = sha256_value({"taxonomy": "quick-dev.failure-taxonomy.v1", "family": family, "descriptor_sha256": descriptor_sha, "candidate_hash": candidate_hash, "stage": stage, "observed_failure_ids": sorted(set(observed)), "receipt_sha256": receipt_sha})[7:23].upper()
    return f"QD-{family.upper().replace('_', '-')}-{digest}"


def judge_receipt(run_dir: Path, stage: str, descriptor: Mapping[str, Any], receipt: Mapping[str, Any], *, expected_failure_ids: Sequence[str] = (), expected_exit: str | None = None) -> dict[str, Any]:
    """Independent judge trust zone; this function never executes the SUT."""
    validate_descriptor(descriptor)
    descriptor_sha = sha256_value(dict(descriptor))
    if receipt.get("schema") != "quick-dev.process-receipt.v2" or receipt.get("stage") != stage or receipt.get("descriptor_sha256") != descriptor_sha:
        raise ValueError("receipt binding is invalid")
    if receipt.get("argv") != [descriptor["executable"], *descriptor["argv"]]:
        raise ValueError("receipt argv is stale")
    evidence = run_dir.resolve() / "canonical-evidence" / stage
    stdout_path, stderr_path = evidence / "stdout.bin", evidence / "stderr.bin"
    if not stdout_path.is_file() or not stderr_path.is_file():
        raise ValueError("receipt output bytes are missing")
    if sha256_bytes(stdout_path.read_bytes()) != receipt.get("stdout_sha256") or sha256_bytes(stderr_path.read_bytes()) != receipt.get("stderr_sha256"):
        raise ValueError("receipt output hashes are stale")
    output = (stdout_path.read_bytes() + b"\n" + stderr_path.read_bytes()).decode("utf-8", errors="replace")
    observed, declared = sorted(set(FAILURE_RE.findall(output))), sorted(set(expected_failure_ids))
    exit_code, timed_out = receipt.get("exit_code"), receipt.get("timed_out") is True
    executions, cases = receipt.get("test_executions"), receipt.get("cases")
    if timed_out:
        outcome, family, predicate = "blocked", "timeout-no-observation", False
    elif not isinstance(exit_code, int) or not isinstance(executions, int) or executions < 1 or not isinstance(cases, int) or cases < 1:
        outcome, family, predicate = "blocked", "test-harness-failure", False
    elif stage == "red" and exit_code == 0:
        outcome, family, predicate = "fail", "unexpected-green", False
    elif stage == "red" and declared and observed == declared:
        outcome, family, predicate = "fail", "expected-red", True
    elif stage == "red":
        outcome, family, predicate = "fail", "semantic-contract-gap", False
    elif exit_code == 0:
        outcome, family, predicate = "pass", None, True
    else:
        outcome, family, predicate = "fail", ("terminal-failure" if stage == "terminal" else "task-implementation-failure"), False
    if expected_exit not in (None, "zero", "nonzero"):
        raise ValueError("expected exit is invalid")
    if expected_exit == "zero" and exit_code != 0: predicate = False
    if expected_exit == "nonzero" and (not isinstance(exit_code, int) or exit_code == 0): predicate = False
    receipt_sha = sha256_value(dict(receipt))
    failure_id = None if family is None else deterministic_failure_id(family, descriptor_sha, receipt["candidate_hash"], stage, observed, receipt_sha)
    observation = {
        "schema": "quick-dev.observation.v2", "observation_id": f"OBS-{stage.upper()}-{receipt_sha[7:19].upper()}",
        "receipt_ref": f"canonical-evidence/{stage}/process-receipt.v2.json", "receipt_sha256": receipt_sha,
        "stage": stage, "evidence_state": "observed-run", "verification_outcome": outcome,
        "process_attempts": receipt["process_attempts"], "test_executions": executions, "cases": cases,
        "exit_code": exit_code, "timed_out": timed_out, "failure_family": family, "failure_id": failure_id,
        "observed_failure_ids": observed, "expected_failure_ids": declared, "predicate_result": predicate,
        "judge_identity": "quick-dev-independent-judge.v2",
    }
    create_json(evidence / "observation.v2.json", observation)
    return observation


def selector_identity(selector: str, target_refs: Sequence[str], fixture_refs: Sequence[str], assertion_ids: Sequence[str], cwd: str) -> str:
    if not isinstance(selector, str) or not selector:
        raise ValueError("selector is invalid")
    return sha256_value({"selector": selector, "target_refs": sorted(target_refs), "fixture_refs": sorted(fixture_refs), "assertion_ids": sorted(assertion_ids), "cwd": cwd})


def build_runtime_edges(*, plan_id: str, plan_hash: str, slice_id: str, run_id: str, candidate_hash: str, stage: str, descriptor: Mapping[str, Any], receipt: Mapping[str, Any], observation: Mapping[str, Any], assertions: Sequence[Mapping[str, str]], selector_hash: str) -> list[dict[str, Any]]:
    if stage not in STAGES or receipt.get("stage") != stage or observation.get("stage") != stage:
        raise ValueError("runtime edge stage lineage is invalid")
    descriptor_sha = sha256_value(dict(descriptor))
    if receipt.get("descriptor_sha256") != descriptor_sha or observation.get("receipt_sha256") != sha256_value(dict(receipt)):
        raise ValueError("runtime edge lineage is stale")
    targets, fixtures = receipt.get("target_hashes"), receipt.get("fixture_hashes")
    if not isinstance(targets, dict) or not targets or not isinstance(fixtures, dict) or not fixtures:
        raise ValueError("runtime edge target/fixture lineage is incomplete")
    target_ref, target_sha = next(iter(sorted(targets.items())))
    fixture_ref, fixture_sha = next(iter(sorted(fixtures.items())))
    result = []
    for assertion in assertions:
        if not isinstance(assertion, Mapping) or not {"acceptance_id", "assertion_id", "case_source_ref"}.issubset(assertion):
            raise ValueError("runtime assertion is invalid")
        result.append({
            "schema": "quick-dev.runtime-assertion-edge.v2", "plan_id": plan_id, "plan_hash": plan_hash,
            "slice_id": slice_id, "run_id": run_id, "candidate_hash": candidate_hash, "stage": stage,
            "acceptance_id": assertion["acceptance_id"], "assertion_id": assertion["assertion_id"], "case_source_ref": assertion["case_source_ref"],
            "selector_identity": selector_hash, "receipt_ref": observation["receipt_ref"], "receipt_sha256": observation["receipt_sha256"],
            "observation_ref": f"canonical-evidence/{stage}/observation.v2.json", "observation_sha256": sha256_value(dict(observation)),
            "descriptor_sha256": descriptor_sha, "target_ref": target_ref, "target_sha256": target_sha,
            "fixture_ref": fixture_ref, "fixture_sha256": fixture_sha,
            "verification_outcome": observation["verification_outcome"], "failure_family": observation["failure_family"], "failure_id": observation["failure_id"],
            "producer_identity": "quick-dev-runtime-edge-validator.v2", "validator_identity": "quick-dev-runtime-edge-validator.v2", "derived_by": "deterministic-validator",
        })
    if not result:
        raise ValueError("runtime edges require assertions")
    return result


def validate_closure(tuples: Sequence[Mapping[str, Any]], expected_keys: Iterable[str], snapshot_sha: str) -> tuple[bool, list[str]]:
    findings, actual = [], []
    expected = set(expected_keys)
    selector_by_acceptance: dict[tuple[str, str], str] = {}
    for index, item in enumerate(tuples):
        if not isinstance(item, Mapping):
            findings.append(f"tuple[{index}]:not-object"); continue
        key = item.get("tuple_key")
        canonical = f"{item.get('slice_id')}|{item.get('acceptance_id')}|{item.get('stage')}"
        if key != canonical: findings.append(f"tuple[{index}]:tuple-key-mismatch")
        if item.get("stage") not in STAGES: findings.append(f"tuple[{index}]:stage-invalid")
        if not HASH_RE.fullmatch(str(item.get("runtime_edge_sha256", ""))): findings.append(f"tuple[{index}]:runtime-edge-hash-invalid")
        if item.get("current_snapshot_sha256") != snapshot_sha: findings.append(f"tuple[{index}]:snapshot-stale")
        selector = item.get("selector_identity")
        pair = (str(item.get("slice_id")), str(item.get("acceptance_id")))
        if not isinstance(selector, str) or not selector: findings.append(f"tuple[{index}]:selector-missing")
        elif pair in selector_by_acceptance and selector_by_acceptance[pair] != selector: findings.append(f"tuple[{index}]:selector-drift")
        else: selector_by_acceptance[pair] = selector
        if isinstance(key, str): actual.append(key)
    if len(actual) != len(set(actual)): findings.append("tuple-key-duplicate")
    if set(actual) != expected: findings.append("tuple-key-set-mismatch")
    if len(actual) != len(expected): findings.append("tuple-cardinality-mismatch")
    return not findings, findings


def hash_path(path: Path) -> str:
    if path.is_symlink(): raise ValueError("snapshot root may not be a symlink")
    if path.is_file(): return sha256_bytes(path.read_bytes())
    if path.is_dir():
        rows = []
        for child in sorted(path.rglob("*")):
            if child.is_symlink(): raise ValueError("snapshot tree contains a symlink")
            if child.is_file(): rows.append((child.relative_to(path).as_posix(), sha256_bytes(child.read_bytes())))
        return sha256_value(rows)
    raise ValueError("snapshot root is missing")


def current_snapshot(workspace: Path, roots: Sequence[Mapping[str, str]], *, source_commit: str, base_commit: str | None = None) -> dict[str, Any]:
    root = workspace.resolve()
    if len(roots) != len(ROOT_KINDS): raise ValueError("current snapshot requires exactly eight roots")
    resolved, kinds, prefixes = [], [], []
    for item in roots:
        kind, raw, reason = item.get("root_kind"), item.get("repository_relative_posix_path"), item.get("inclusion_reason")
        if kind in GOVERNANCE_ROOTS or kind not in ROOT_KINDS: raise ValueError(f"snapshot root kind is not runtime authority: {kind}")
        if not isinstance(raw, str) or not isinstance(reason, str) or not reason: raise ValueError("snapshot root fields are invalid")
        relative = safe_relative(raw); target = (root / relative).resolve()
        try: target.relative_to(root)
        except ValueError as exc: raise ValueError("snapshot root escapes repository") from exc
        resolved.append({"root_kind": kind, "repository_relative_posix_path": relative, "content_sha256": hash_path(target), "source_commit": source_commit, "inclusion_reason": reason})
        kinds.append(kind); prefixes.append(relative.rstrip("/"))
    if set(kinds) != set(ROOT_KINDS) or len(kinds) != len(set(kinds)): raise ValueError("snapshot root kinds must be the exact unique set")
    base = base_commit or source_commit
    delta: dict[str, Any] = {"base_commit": base, "additions": [], "deletions": [], "renames": []}
    if (root / ".git").exists() and base:
        diff = subprocess.run(["git", "diff", "--name-status", "-M", base, "--"], cwd=root, capture_output=True, text=True, check=False)
        if diff.returncode != 0: raise ValueError("git delta cannot be resolved")
        for line in diff.stdout.splitlines():
            parts = line.split("\t"); status = parts[0] if parts else ""
            if status.startswith("R") and len(parts) == 3:
                before, after = safe_relative(parts[1]), safe_relative(parts[2]); delta["renames"].append({"from_path": before, "to_path": after})
            elif status == "A" and len(parts) == 2:
                path = safe_relative(parts[1]); delta["additions"].append({"path": path, "after_sha256": hash_path(root / path)})
            elif status == "D" and len(parts) == 2:
                delta["deletions"].append({"path": safe_relative(parts[1])})
            elif len(parts) == 2:
                path = safe_relative(parts[1]); delta["deletions"].append({"path": path}); delta["additions"].append({"path": path, "after_sha256": hash_path(root / path)})
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=root, capture_output=True, text=True, check=False)
        if untracked.returncode != 0: raise ValueError("untracked git delta cannot be resolved")
        additions = {item["path"] for item in delta["additions"]}
        for raw in untracked.stdout.splitlines():
            if raw.strip():
                path = safe_relative(raw.strip())
                if path not in additions: delta["additions"].append({"path": path, "after_sha256": hash_path(root / path)})
        changed = {item["path"] for item in delta["additions"] + delta["deletions"]} | {item["from_path"] for item in delta["renames"]} | {item["to_path"] for item in delta["renames"]}
        for path in changed:
            if not any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes): raise ValueError(f"git delta contains an unlisted runtime root: {path}")
    manifest = {"schema": "current-snapshot-resolver.v2", "roots": sorted(resolved, key=lambda item: ROOT_KINDS.index(item["root_kind"])), "git_delta": delta, "excluded_roots": sorted(GOVERNANCE_ROOTS)}
    manifest["sha256"] = sha256_value(manifest)
    return manifest


def environment_probe() -> dict[str, str]:
    python = subprocess.run([sys.executable, "--version"], capture_output=True, text=True, check=False)
    pytest = subprocess.run([sys.executable, "-m", "pytest", "--version"], capture_output=True, text=True, check=False)
    return {"launcher": sys.executable, "interpreter_version": (python.stdout or python.stderr).strip(), "test_runner_version": (pytest.stdout or pytest.stderr).strip()}
