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
REPO_NOISE_RE = re.compile(r"(?:^|\n)REPO_NOISE:", re.I)
PYTEST_COUNT_RE = re.compile(r"(\d+)\s+(passed|failed|errors?|skipped)")
EXPLICIT_CASES_RE = re.compile(r"(?:^|\n)CASES:(\d+)\b")
EXPLICIT_EXECUTIONS_RE = re.compile(r"(?:^|\n)TEST_EXECUTIONS:(\d+)\b")
DESCRIPTOR_FIELDS = {
    "run_id", "plan_id", "slice_id", "stage", "candidate_hash", "argv", "cwd", "shell",
    "timeout_seconds", "target_refs", "fixture_refs", "acceptance_assertions",
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("path must be repository-relative POSIX")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
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
    if not isinstance(descriptor, Mapping) or set(descriptor) - {"case_contract", "behavior_route"} != DESCRIPTOR_FIELDS:
        raise ValueError("descriptor shape is invalid")
    for field in ("run_id", "plan_id", "slice_id", "stage", "candidate_hash", "cwd"):
        if not isinstance(descriptor.get(field), str) or not descriptor[field]:
            raise ValueError(f"descriptor {field} is invalid")
    if descriptor["stage"] not in (*STAGES, "probe", "regression"):
        raise ValueError("descriptor stage is invalid")
    if not HASH_RE.fullmatch(descriptor["candidate_hash"]):
        raise ValueError("descriptor candidate hash is invalid")
    if descriptor.get("shell") is not False:
        raise ValueError("descriptor must use shell=false")
    argv = descriptor.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise ValueError("descriptor argv is invalid")
    if descriptor["cwd"] != ".":
        safe_relative(descriptor["cwd"])
    timeout = descriptor.get("timeout_seconds")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("descriptor timeout is invalid")
    for field in ("target_refs", "fixture_refs"):
        values = descriptor.get(field)
        if not isinstance(values, list) or not values or any(not isinstance(item, str) or not item for item in values):
            raise ValueError(f"descriptor {field} is invalid")
        for item in values:
            safe_relative(item)
    assertions = descriptor.get("acceptance_assertions")
    if not isinstance(assertions, list) or not assertions:
        raise ValueError("descriptor acceptance assertions are invalid")
    seen: set[tuple[str, str]] = set()
    for item in assertions:
        if not isinstance(item, Mapping) or set(item) - {"acceptance_id", "assertion_id", "case_source_ref", "target_ref", "fixture_ref"}:
            raise ValueError("descriptor assertion shape is invalid")
        for field in ("acceptance_id", "assertion_id", "case_source_ref"):
            if not isinstance(item.get(field), str) or not item[field]:
                raise ValueError("descriptor assertion identity is invalid")
        key = (item["acceptance_id"], item["assertion_id"])
        if key in seen:
            raise ValueError("descriptor assertion duplicate")
        seen.add(key)
        for field in ("target_ref", "fixture_ref"):
            if field in item:
                safe_relative(str(item[field]))


def selector_identity_from_descriptor(descriptor: Mapping[str, Any]) -> str:
    validate_descriptor(descriptor)
    return sha256_value({
        "argv": descriptor["argv"], "cwd": descriptor["cwd"],
        **({"case_contract": descriptor["case_contract"]} if "case_contract" in descriptor else {}),
        **({"behavior_route": descriptor["behavior_route"]} if "behavior_route" in descriptor else {}),
        "target_refs": sorted(descriptor["target_refs"]), "fixture_refs": sorted(descriptor["fixture_refs"]),
        "acceptance_assertions": sorted(
            [{"acceptance_id": a["acceptance_id"], "assertion_id": a["assertion_id"], "case_source_ref": a["case_source_ref"]} for a in descriptor["acceptance_assertions"]],
            key=lambda a: (a["acceptance_id"], a["assertion_id"], a["case_source_ref"]),
        ),
    })


def hash_refs(root: Path, refs: Sequence[str]) -> dict[str, str]:
    if not refs:
        raise ValueError("refs must be non-empty")
    result: dict[str, str] = {}
    for ref in refs:
        relative = safe_relative(ref)
        result[relative] = sha256_bytes(resolve_file(root, relative).read_bytes())
    return dict(sorted(result.items()))


def process_counts(output: str, *, timed_out: bool) -> tuple[int, int]:
    if timed_out:
        return 0, 0
    explicit_cases = EXPLICIT_CASES_RE.search(output)
    explicit_exec = EXPLICIT_EXECUTIONS_RE.search(output)
    if explicit_cases or explicit_exec:
        cases = int(explicit_cases.group(1)) if explicit_cases else 0
        executions = int(explicit_exec.group(1)) if explicit_exec else (1 if cases > 0 else 0)
        return executions, cases
    total = sum(int(match.group(1)) for match in PYTEST_COUNT_RE.finditer(output))
    return (1 if total > 0 else 0), total


def _pre_execution_receipt(descriptor: Mapping[str, Any], stage: str, profile_identity: str, error_code: str) -> dict[str, Any]:
    return {
        "schema": "quick-dev.process-receipt.v2", "stage": stage,
        "descriptor_ref": "frozen-descriptor", "descriptor_sha256": sha256_value(dict(descriptor)),
        "argv": list(descriptor.get("argv", [])), "cwd": descriptor.get("cwd"),
        "started_at": None, "ended_at": None, "process_attempts": 0, "test_executions": 0, "cases": 0,
        "exit_code": None, "timed_out": False, "stdout_sha256": sha256_bytes(b""), "stderr_sha256": sha256_bytes(b""),
        "candidate_hash": descriptor.get("candidate_hash"), "target_hashes": {}, "fixture_hashes": {},
        "profile_identity": profile_identity, "executor_identity": "quick-dev-process-executor.v2",
        "pre_execution_error_code": error_code,
    }


def execute_process(workspace: Path, run_dir: Path, stage: str, descriptor: Mapping[str, Any], *, profile_identity: str) -> dict[str, Any]:
    """Executor trust zone: persist process facts only."""
    evidence = run_dir.resolve() / "canonical-evidence" / stage
    try:
        validate_descriptor(descriptor)
    except ValueError:
        receipt = _pre_execution_receipt(descriptor, stage, profile_identity, "ARTIFACT_INTEGRITY")
        create_immutable(evidence / "stdout.bin", b""); create_immutable(evidence / "stderr.bin", b"")
        create_json(evidence / "process-receipt.v2.json", receipt)
        return receipt
    if descriptor["stage"] != stage or descriptor["run_id"] != run_dir.name:
        receipt = _pre_execution_receipt(descriptor, stage, profile_identity, "ARTIFACT_INTEGRITY")
        create_immutable(evidence / "stdout.bin", b""); create_immutable(evidence / "stderr.bin", b"")
        create_json(evidence / "process-receipt.v2.json", receipt)
        return receipt
    root = workspace.resolve()
    cwd = root if descriptor["cwd"] == "." else (root / safe_relative(descriptor["cwd"])).resolve()
    try:
        cwd.relative_to(root)
        if not cwd.is_dir():
            raise ValueError
        target_hashes = hash_refs(root, descriptor["target_refs"])
        fixture_hashes = hash_refs(root, descriptor["fixture_refs"])
    except (OSError, ValueError):
        receipt = _pre_execution_receipt(descriptor, stage, profile_identity, "TARGET_BINDING")
        create_immutable(evidence / "stdout.bin", b""); create_immutable(evidence / "stderr.bin", b"")
        create_json(evidence / "process-receipt.v2.json", receipt)
        return receipt
    started = datetime.now(timezone.utc)
    stdout, stderr, timed_out = b"", b"", False
    exit_code: int | None
    try:
        completed = subprocess.run(descriptor["argv"], cwd=cwd, shell=False, check=False, capture_output=True, timeout=descriptor["timeout_seconds"])
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out, exit_code = True, None
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        if isinstance(stdout, str): stdout = stdout.encode("utf-8", errors="replace")
        if isinstance(stderr, str): stderr = stderr.encode("utf-8", errors="replace")
    ended = datetime.now(timezone.utc)
    create_immutable(evidence / "stdout.bin", stdout); create_immutable(evidence / "stderr.bin", stderr)
    output = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
    test_executions, cases = process_counts(output, timed_out=timed_out)
    receipt = {
        "schema": "quick-dev.process-receipt.v2", "stage": stage, "descriptor_ref": "frozen-descriptor",
        "descriptor_sha256": sha256_value(dict(descriptor)), "argv": list(descriptor["argv"]), "cwd": descriptor["cwd"],
        "started_at": started.isoformat().replace("+00:00", "Z"), "ended_at": ended.isoformat().replace("+00:00", "Z"),
        "process_attempts": 1, "test_executions": test_executions, "cases": cases, "exit_code": exit_code,
        "timed_out": timed_out, "stdout_sha256": sha256_bytes(stdout), "stderr_sha256": sha256_bytes(stderr),
        "candidate_hash": descriptor["candidate_hash"], "target_hashes": target_hashes, "fixture_hashes": fixture_hashes,
        "profile_identity": profile_identity, "executor_identity": "quick-dev-process-executor.v2", "pre_execution_error_code": None,
    }
    create_json(evidence / "process-receipt.v2.json", receipt)
    return receipt


def deterministic_failure_id(family: str, descriptor_sha: str, candidate_hash: str, stage: str, observed: Sequence[str], receipt_sha: str) -> str:
    digest = sha256_value({"taxonomy": "quick-dev.failure-taxonomy.v1", "family": family, "descriptor_sha256": descriptor_sha, "candidate_hash": candidate_hash, "stage": stage, "observed_failure_ids": sorted(set(observed)), "receipt_sha256": receipt_sha})[7:23].upper()
    return f"QD-{family.upper().replace('_', '-')}-{digest}"


def judge_receipt(run_dir: Path, stage: str, descriptor: Mapping[str, Any], receipt: Mapping[str, Any], *, expected_failure_ids: Sequence[str] = ()) -> dict[str, Any]:
    """Independent judge; never executes the SUT."""
    evidence = run_dir.resolve() / "canonical-evidence" / stage
    integrity_error = False
    try:
        validate_descriptor(descriptor)
        if descriptor["stage"] != stage or receipt.get("schema") != "quick-dev.process-receipt.v2" or receipt.get("stage") != stage:
            raise ValueError
        if receipt.get("descriptor_sha256") != sha256_value(dict(descriptor)) or receipt.get("candidate_hash") != descriptor["candidate_hash"]:
            raise ValueError
        if receipt.get("argv") != descriptor["argv"] or receipt.get("cwd") != descriptor["cwd"]:
            raise ValueError
        stdout_path, stderr_path = evidence / "stdout.bin", evidence / "stderr.bin"
        if not stdout_path.is_file() or not stderr_path.is_file():
            raise ValueError
        if sha256_bytes(stdout_path.read_bytes()) != receipt.get("stdout_sha256") or sha256_bytes(stderr_path.read_bytes()) != receipt.get("stderr_sha256"):
            raise ValueError
    except (OSError, ValueError):
        integrity_error = True
    stdout = (evidence / "stdout.bin").read_bytes() if (evidence / "stdout.bin").is_file() else b""
    stderr = (evidence / "stderr.bin").read_bytes() if (evidence / "stderr.bin").is_file() else b""
    output = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
    observed, declared = sorted(set(FAILURE_RE.findall(output))), sorted(set(expected_failure_ids))
    exit_code = receipt.get("exit_code")
    timed_out = receipt.get("timed_out") is True
    executions, cases = receipt.get("test_executions"), receipt.get("cases")
    pre_error = receipt.get("pre_execution_error_code")
    evidence_state = "observed-run"
    if integrity_error or pre_error == "ARTIFACT_INTEGRITY":
        outcome, family, predicate, evidence_state = "blocked", "artifact-integrity", False, "invalid-run"
    elif pre_error == "TARGET_BINDING":
        outcome, family, predicate = "blocked", "target-binding-failure", False
    elif timed_out:
        outcome, family, predicate = "blocked", "timeout-no-observation", False
    elif REPO_NOISE_RE.search(output):
        outcome, family, predicate = "blocked", "repo-noise", False
    elif not isinstance(exit_code, int) or not isinstance(executions, int) or executions < 1 or not isinstance(cases, int) or cases < 1:
        outcome, family, predicate = "blocked", "test-harness-failure", False
    elif stage == "red" and exit_code == 0:
        outcome, family, predicate = "fail", "unexpected-green", False
    elif stage == "red" and declared and observed == declared and exit_code != 0:
        outcome, family, predicate = "fail", "expected-red", True
    elif stage == "red":
        outcome, family, predicate = "fail", "semantic-contract-gap", False
    elif exit_code == 0:
        outcome, family, predicate = "pass", None, True
    else:
        outcome, family, predicate = "fail", "task-implementation-failure", False
    receipt_sha = sha256_value(dict(receipt))
    descriptor_sha = sha256_value(dict(descriptor)) if isinstance(descriptor, Mapping) else sha256_value({})
    candidate_hash = str(receipt.get("candidate_hash") or descriptor.get("candidate_hash") or "sha256:" + "0" * 64)
    failure_id = None if family is None else deterministic_failure_id(family, descriptor_sha, candidate_hash, stage, observed, receipt_sha)
    observation = {
        "schema": "quick-dev.observation.v2", "observation_id": f"OBS-{stage.upper()}-{receipt_sha[7:19].upper()}",
        "receipt_ref": f"canonical-evidence/{stage}/process-receipt.v2.json", "receipt_sha256": receipt_sha,
        "stage": stage, "evidence_state": evidence_state, "verification_outcome": outcome,
        "process_attempts": receipt.get("process_attempts", 0), "test_executions": executions if isinstance(executions, int) else 0,
        "cases": cases if isinstance(cases, int) else 0, "exit_code": exit_code, "timed_out": timed_out,
        "failure_family": family, "failure_id": failure_id, "observed_failure_ids": observed,
        "expected_failure_ids": declared, "predicate_result": predicate, "judge_identity": "quick-dev-independent-judge.v2",
    }
    create_json(evidence / "observation.v2.json", observation)
    return observation


def build_runtime_edges(*, plan_id: str, plan_hash: str, slice_id: str, run_id: str, candidate_hash: str, stage: str, descriptor: Mapping[str, Any], receipt: Mapping[str, Any], observation: Mapping[str, Any], selector_hash: str) -> list[dict[str, Any]]:
    validate_descriptor(descriptor)
    if descriptor["plan_id"] != plan_id or descriptor["slice_id"] != slice_id or descriptor["run_id"] != run_id or descriptor["candidate_hash"] != candidate_hash or descriptor["stage"] != stage:
        raise ValueError("runtime edge descriptor lineage is invalid")
    if receipt.get("descriptor_sha256") != sha256_value(dict(descriptor)) or observation.get("receipt_sha256") != sha256_value(dict(receipt)):
        raise ValueError("runtime edge receipt/observation lineage is stale")
    targets, fixtures = receipt.get("target_hashes"), receipt.get("fixture_hashes")
    if not isinstance(targets, dict) or not isinstance(fixtures, dict):
        raise ValueError("runtime edge target/fixture hashes are invalid")
    from case_evidence import assertion_cases
    if observation.get("predicate_result") is not True or stage == "probe":
        return []
    case_map = assertion_cases(descriptor, receipt)
    result: list[dict[str, Any]] = []
    for assertion in descriptor["acceptance_assertions"]:
        target_ref = assertion.get("target_ref") or descriptor["target_refs"][0]
        fixture_ref = assertion.get("fixture_ref") or descriptor["fixture_refs"][0]
        if target_ref not in targets or fixture_ref not in fixtures:
            if observation.get("predicate_result") is True:
                raise ValueError("runtime edge assertion target/fixture is not bound")
            continue
        expected_stage_outcome = "fail" if stage == "red" else "pass"
        actual_stage_outcome = "pass" if observation.get("verification_outcome") == "pass" else "fail"
        result.append({
            "plan_id": plan_id, "plan_hash": plan_hash, "slice_id": slice_id, "candidate_hash": candidate_hash,
            "observation_id": observation["observation_id"], "acceptance_id": assertion["acceptance_id"], "assertion_id": assertion["assertion_id"],
            "selector_identity": selector_hash, "stage": stage, "run_id": run_id,
            "result_ref": f"canonical-evidence/{stage}/process-receipt.v2.json", "result_sha256": sha256_value(dict(receipt)),
            "receipt_ref": f"canonical-evidence/{stage}/process-receipt.v2.json", "receipt_sha256": sha256_value(dict(receipt)),
            "observation_ref": f"canonical-evidence/{stage}/observation.v2.json", "observation_sha256": sha256_value(dict(observation)),
            "descriptor_sha256": sha256_value(dict(descriptor)), "target_sha256": targets[target_ref], "fixture_sha256": fixtures[fixture_ref],
            "observed": observation.get("evidence_state") == "observed-run", "expected_stage_outcome": expected_stage_outcome,
            "actual_stage_outcome": actual_stage_outcome, "predicate_result": observation.get("predicate_result") is True,
            "verification_outcome": observation.get("verification_outcome"), "failure_family": observation.get("failure_family"),
            "failure_id": observation.get("failure_id"), "target_ref": target_ref, "fixture_ref": fixture_ref,
            "case_source_ref": assertion["case_source_ref"],
            "case_evidence_schema": "quick-dev.case-contract.v1",
            "case_ids": case_map[(assertion["acceptance_id"], assertion["assertion_id"])],
            "case_report_sha256": receipt["case_report_sha256"], "producer_identity": "quick-dev-runtime-edge-validator.v2",
            "validator_identity": "quick-dev-runtime-edge-validator.v2", "derived_by": "deterministic-validator",
        })
    if observation.get("predicate_result") is True and not result:
        raise ValueError("successful stage requires runtime assertion edges")
    return result


def expected_tuple_keys(bundle: Mapping[str, Any]) -> set[str]:
    cover = bundle.get("final_plan_coverage")
    if not isinstance(cover, list):
        raise ValueError("final plan coverage missing")
    keys: set[str] = set()
    for edge in cover:
        if not isinstance(edge, Mapping) or edge.get("stage_scope") != list(STAGES):
            raise ValueError("final plan coverage stage scope invalid")
        sid, aid = edge.get("slice_id"), edge.get("acceptance_id")
        if not isinstance(sid, str) or not isinstance(aid, str):
            raise ValueError("final plan coverage identity invalid")
        for stage in STAGES:
            keys.add(f"{sid}|{aid}|{stage}")
    return keys


def validate_closure(tuples: Sequence[Mapping[str, Any]], expected_keys: Iterable[str], snapshot_sha: str) -> tuple[bool, list[str]]:
    findings: list[str] = []; actual: list[str] = []
    expected = set(expected_keys); selectors: dict[tuple[str, str], str] = {}
    for index, item in enumerate(tuples):
        if not isinstance(item, Mapping): findings.append(f"tuple[{index}]:not-object"); continue
        key = item.get("tuple_key"); canonical = f"{item.get('slice_id')}|{item.get('acceptance_id')}|{item.get('stage')}"
        if key != canonical: findings.append(f"tuple[{index}]:tuple-key-mismatch")
        if item.get("stage") not in STAGES: findings.append(f"tuple[{index}]:stage-invalid")
        if not HASH_RE.fullmatch(str(item.get("runtime_edge_sha256", ""))): findings.append(f"tuple[{index}]:runtime-edge-hash-invalid")
        if item.get("current_snapshot_sha256") != snapshot_sha: findings.append(f"tuple[{index}]:snapshot-stale")
        selector = item.get("selector_identity"); pair = (str(item.get("slice_id")), str(item.get("acceptance_id")))
        if not isinstance(selector, str) or not selector: findings.append(f"tuple[{index}]:selector-missing")
        elif pair in selectors and selectors[pair] != selector: findings.append(f"tuple[{index}]:selector-drift")
        else: selectors[pair] = selector
        if isinstance(key, str): actual.append(key)
    if len(actual) != len(set(actual)): findings.append("tuple-key-duplicate")
    if set(actual) != expected: findings.append("tuple-key-set-mismatch")
    if len(actual) != len(expected): findings.append("tuple-cardinality-mismatch")
    return not findings, findings


def hash_path(path: Path) -> str:
    if path.is_symlink(): raise ValueError("snapshot root may not be symlink")
    if path.is_file(): return sha256_bytes(path.read_bytes())
    if path.is_dir():
        rows = []
        for child in sorted(path.rglob("*")):
            if child.is_symlink(): raise ValueError("snapshot tree contains symlink")
            if child.is_file(): rows.append((child.relative_to(path).as_posix(), sha256_bytes(child.read_bytes())))
        return sha256_value(rows)
    raise ValueError("snapshot root missing")


def _git_before_hash(root: Path, base: str, path: str) -> str:
    proc = subprocess.run(["git", "show", f"{base}:{path}"], cwd=root, capture_output=True, check=False)
    if proc.returncode != 0:
        raise ValueError(f"cannot read baseline bytes: {path}")
    return sha256_bytes(proc.stdout)


def _in_runtime_roots(path: str, prefixes: Sequence[str]) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


def _known_runtime_exclusion(path: str) -> bool:
    """Return True only for changes the normative matrix excludes by default.

    Explicitly bound runtime roots are checked before this function, so a docs
    file that is actually the declared source/contract still participates in
    the snapshot. Outside those roots, ordinary text documentation and known
    governance/provenance artifacts are excluded. Unknown code/config remains
    fail-closed.
    """
    normalized = safe_relative(path)
    pure = PurePosixPath(normalized)
    lower = normalized.lower()
    if pure.suffix.lower() in {".md", ".txt", ".rst"} and (
        normalized.startswith("docs/") or normalized.startswith("_bmad-output/")
    ):
        return True
    governance_tokens = (
        ".memlog", "architecture-decision-registry", "architecture-spine",
        "/reviews/", "review-", "candidate-binding", "authorization",
    )
    return any(token in lower for token in governance_tokens)


def _outside_declared_runtime_scope(path: str, prefixes: Sequence[str]) -> bool:
    """Whether a worktree delta is outside this slice's declared snapshot.

    A current run is closed over its eight explicitly declared runtime roots.
    Changes belonging to another slice must not become an implicit input merely
    because both slices share one worktree.  The caller still fails closed for
    every change that intersects a declared root; this predicate only prevents
    unrelated pending work from invalidating a slice before Q4 can start.
    """
    return not _in_runtime_roots(path, prefixes)


def current_snapshot(workspace: Path, roots: Sequence[Mapping[str, str]], *, source_commit: str, base_commit: str | None = None) -> dict[str, Any]:
    root = workspace.resolve()
    if len(roots) != len(ROOT_KINDS): raise ValueError("current snapshot requires exactly eight roots")
    resolved: list[dict[str, str]] = []; kinds: list[str] = []; prefixes: list[str] = []
    for item in roots:
        kind, raw, raws, reason = item.get("root_kind"), item.get("repository_relative_posix_path"), item.get("repository_relative_posix_paths"), item.get("inclusion_reason")
        if kind not in ROOT_KINDS or kind in GOVERNANCE_ROOTS: raise ValueError(f"invalid runtime root kind: {kind}")
        if not isinstance(reason, str) or not reason: raise ValueError("snapshot root fields invalid")
        if isinstance(raw, str) and raws is None:
            relatives = [safe_relative(raw)]
        elif isinstance(raws, list) and raws and all(isinstance(value, str) for value in raws) and raw is None:
            relatives = sorted({safe_relative(value) for value in raws})
        else:
            raise ValueError("snapshot root paths invalid")
        targets = [(root / relative).resolve() for relative in relatives]
        for target in targets: target.relative_to(root)
        digest = hash_path(targets[0]) if len(targets) == 1 else sha256_value([(relative, hash_path(target)) for relative, target in zip(relatives, targets)])
        resolved_item = {"root_kind": kind, "content_sha256": digest, "source_commit": source_commit, "inclusion_reason": reason}
        if len(relatives) == 1: resolved_item["repository_relative_posix_path"] = relatives[0]
        else: resolved_item["repository_relative_posix_paths"] = relatives
        resolved.append(resolved_item)
        kinds.append(kind); prefixes.extend(relative.rstrip("/") for relative in relatives)
    if set(kinds) != set(ROOT_KINDS) or len(kinds) != len(set(kinds)): raise ValueError("snapshot root kinds must be exact unique set")
    base = base_commit or source_commit
    delta: dict[str, Any] = {"base_commit": base, "additions": [], "deletions": [], "renames": []}
    if (root / ".git").exists() and base:
        proc = subprocess.run(["git", "diff", "--name-status", "-M", base, "--"], cwd=root, capture_output=True, text=True, check=False)
        if proc.returncode != 0: raise ValueError("git delta cannot be resolved")
        for line in proc.stdout.splitlines():
            parts = line.split("\t"); status = parts[0] if parts else ""
            if status.startswith("R") and len(parts) == 3:
                before, after = safe_relative(parts[1]), safe_relative(parts[2])
                before_runtime, after_runtime = _in_runtime_roots(before, prefixes), _in_runtime_roots(after, prefixes)
                if not before_runtime and not after_runtime:
                    continue
                if before_runtime != after_runtime:
                    raise ValueError(f"git rename crosses runtime root boundary: {before} -> {after}")
                delta["renames"].append({"from_path": before, "to_path": after, "before_sha256": _git_before_hash(root, base, before), "after_sha256": hash_path(root / after)})
            elif status == "A" and len(parts) == 2:
                path = safe_relative(parts[1])
                if _outside_declared_runtime_scope(path, prefixes):
                    continue
                delta["additions"].append({"path": path, "after_sha256": hash_path(root / path)})
            elif status == "D" and len(parts) == 2:
                path = safe_relative(parts[1])
                if _outside_declared_runtime_scope(path, prefixes):
                    continue
                delta["deletions"].append({"path": path, "before_sha256": _git_before_hash(root, base, path)})
            elif len(parts) == 2:
                path = safe_relative(parts[1])
                if _outside_declared_runtime_scope(path, prefixes):
                    continue
                delta["deletions"].append({"path": path, "before_sha256": _git_before_hash(root, base, path)})
                delta["additions"].append({"path": path, "after_sha256": hash_path(root / path)})
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=root, capture_output=True, text=True, check=False)
        if untracked.returncode != 0: raise ValueError("untracked git delta cannot be resolved")
        known_additions = {item["path"] for item in delta["additions"]}
        for raw in untracked.stdout.splitlines():
            if raw.strip():
                path = safe_relative(raw.strip())
                if _outside_declared_runtime_scope(path, prefixes):
                    continue
                if path not in known_additions: delta["additions"].append({"path": path, "after_sha256": hash_path(root / path)})
    manifest = {"schema": "current-snapshot-resolver.v1", "roots": sorted(resolved, key=lambda item: ROOT_KINDS.index(item["root_kind"])), "git_delta": delta, "excluded_roots": sorted(GOVERNANCE_ROOTS)}
    manifest["sha256"] = sha256_value(manifest)
    return manifest


def environment_probe() -> dict[str, Any]:
    py = subprocess.run([sys.executable, "--version"], capture_output=True, text=True, check=False)
    pytest = subprocess.run([sys.executable, "-m", "pytest", "--version"], capture_output=True, text=True, check=False)
    return {"launcher": sys.executable, "interpreter_version": (py.stdout or py.stderr).strip(), "test_runner_version": (pytest.stdout or pytest.stderr).strip(), "available": py.returncode == 0 and pytest.returncode == 0}
