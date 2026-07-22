from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from candidate_lineage_guards import fold_accepted_attempts, load_candidate_lineage, validate_candidate_lineage_model, validate_candidate_result_ref, validate_candidate_supersession_model
from contract_guards import contained_file, schema_error
from replay_baseline_guards import load_replay_baseline


HASH_RE = "sha256:"
FILE_KEYS = {
    "change_type", "baseline_path", "candidate_path", "before_sha256",
    "after_sha256", "roles", "scope",
}


def _finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}
def bytes_hash(value: bytes) -> str:
    return HASH_RE + hashlib.sha256(value).hexdigest()
def value_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return bytes_hash(payload)
def manifest_root_hash(document: dict[str, Any]) -> str:
    value = dict(document)
    value.pop("root_hash", None)
    return value_hash(value)
def _git(repository_root: Path, *args: str, accepted: set[int] | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", *args],
        cwd=repository_root,
        capture_output=True,
        check=False,
    )
    allowed = accepted or {0}
    if result.returncode not in allowed:
        raise ValueError(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout
def _normalize_pattern(plan_root: Path, repository_root: Path, pattern: str) -> str | None:
    normalized = pattern.replace("\\", "/").strip("/")
    if not normalized or "<" in normalized or normalized.casefold().startswith("logs/"):
        return None
    prefixes = (".agents/", ".github/", "decision-logs/", "docs/", "execution-plans/", "scripts/", "runtime/", "PhaseA.Platform/", "Game.", "Tests.")
    if normalized in {".gitignore", "AGENTS.md", "README.md", "agentbuild.txt"} or normalized.startswith(prefixes):
        return normalized
    return f"{plan_root.relative_to(repository_root).as_posix()}/{normalized}"
def _matches(path: str, patterns: set[str]) -> bool:
    folded = path.replace("\\", "/").casefold()
    for pattern in patterns:
        candidate = pattern.casefold()
        if candidate.endswith("/**") and (folded == candidate[:-3] or folded.startswith(candidate[:-2])):
            return True
        if fnmatch.fnmatchcase(folded, candidate):
            return True
    return False
def scope_policy(plan_root: Path, repository_root: Path, contract: dict[str, Any], slice_id: str) -> dict[str, set[str]]:
    slices = contract.get("slices", [])
    selected = next((index for index, item in enumerate(slices) if item.get("slice_id") == slice_id), None)
    if selected is None:
        raise ValueError(f"unknown candidate scope: {slice_id}")
    policy = {key: set() for key in ("production", "test", "documentation", "execution_read", "dependency", "forbidden")}
    for item in slices[: selected + 1]:
        allowed = item.get("allowed_changes", {})
        raw = {
            "production": allowed.get("production", []),
            "test": allowed.get("tests", []),
            "documentation": allowed.get("documentation", []),
            "execution_read": item.get("execution_read_set", []),
            "dependency": item.get("dependency_closure", []),
            "forbidden": item.get("forbidden_changes", []),
        }
        for role, patterns in raw.items():
            policy[role].update(filter(None, (_normalize_pattern(plan_root, repository_root, value) for value in patterns)))
    return policy
def _classify(path: str, policy: dict[str, set[str]]) -> tuple[list[str], str]:
    roles = [role for role in ("production", "test", "documentation", "execution_read", "dependency", "forbidden") if _matches(path, policy[role])]
    if "forbidden" in roles:
        return roles, "forbidden"
    if any(role in roles for role in ("production", "test", "documentation")):
        return roles, "allowed"
    return roles or ["dependency"], "unrelated"
def _head_blob(repository_root: Path, path: str) -> bytes | None:
    listing = _git(repository_root, "ls-tree", "-z", "HEAD", "--", path)
    if not listing:
        return None
    header = listing.split(b"\t", 1)[0].decode("ascii")
    object_id = header.split()[2]
    return _git(repository_root, "cat-file", "blob", object_id)
def _file_entry(repository_root: Path, path: str, policy: dict[str, set[str]]) -> dict[str, Any]:
    before = _head_blob(repository_root, path)
    current_path = repository_root / path
    safe_path = contained_file(repository_root, path) if current_path.exists() else None
    if current_path.exists() and safe_path is None:
        raise ValueError(f"candidate path crosses repository containment: {path}")
    after = safe_path.read_bytes() if safe_path is not None else None
    change_type = "add" if before is None else "delete" if after is None else "modify"
    roles, scope = _classify(path, policy)
    return {
        "change_type": change_type,
        "baseline_path": None if change_type == "add" else path,
        "candidate_path": None if change_type == "delete" else path,
        "before_sha256": None if before is None else bytes_hash(before),
        "after_sha256": None if after is None else bytes_hash(after),
        "roles": roles,
        "scope": scope,
    }
def _entry_path(entry: dict[str, Any]) -> str:
    return str(entry.get("candidate_path") or entry.get("baseline_path") or "")
def _canonical_test_patch(repository_root: Path, entries: list[dict[str, Any]]) -> bytes:
    tests = [entry for entry in entries if "test" in entry.get("roles", []) and entry.get("scope") == "allowed"]
    tracked = [_entry_path(entry) for entry in tests if entry.get("change_type") != "add"]
    added = [_entry_path(entry) for entry in tests if entry.get("change_type") == "add"]
    flags = ["--binary", "--full-index", "--no-renames", "--no-ext-diff", "--no-textconv"]
    chunks: list[bytes] = []
    if tracked:
        chunks.append(_git(repository_root, "diff", *flags, "HEAD", "--", *sorted(tracked, key=str.casefold)))
    for path in sorted(added, key=str.casefold):
        chunks.append(_git(repository_root, "diff", "--no-index", *flags, "--", "/dev/null", path, accepted={0, 1}))
    return b"".join(chunks)


def derive_candidate_snapshot(plan_root: Path, repository_root: Path, contract: dict[str, Any], slice_id: str = "RMAP-S6", replay_baseline_ref: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], bytes, set[str]]:
    policy = scope_policy(plan_root, repository_root, contract, slice_id)
    monitored = set().union(*policy.values())
    tracked = _git(repository_root, "diff", "--no-renames", "--name-only", "-z", "HEAD", "--").decode("utf-8").split("\0")
    untracked = _git(repository_root, "ls-files", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")
    paths = sorted({path for path in [*tracked, *untracked] if path and _matches(path, monitored)}, key=str.casefold)
    entries = [_file_entry(repository_root, path, policy) for path in paths]
    exclusions, findings = load_replay_baseline(plan_root, repository_root, replay_baseline_ref, {_entry_path(item): item for item in entries})
    if findings:
        raise ValueError("; ".join(item["message"] for item in findings))
    entries = [item for item in entries if _entry_path(item) not in exclusions]
    return entries, _canonical_test_patch(repository_root, entries), exclusions


def _core(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = ("change_type", "baseline_path", "candidate_path", "before_sha256", "after_sha256")
    return [{key: entry.get(key) for key in keys} for entry in entries]


def validate_candidate_diff(
    plan_root: Path,
    repository_root: Path,
    contract: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: str,
    test_patch: bytes,
    lineage: dict[str, Any],
    current: dict[str, str],
    candidate_run_id: str,
) -> list[dict[str, str]]:
    if manifest.get("schema_version") == "jimuyun.candidate-diff-manifest.v2":
        return validate_committed_candidate_diff(plan_root, repository_root, contract, manifest, manifest_path, test_patch, candidate_run_id)
    expected, expected_patch, exclusions = derive_candidate_snapshot(plan_root, repository_root, contract, replay_baseline_ref=lineage.get("replay_baseline_ref"))
    folded, fold_hash, fold_findings = load_candidate_lineage(plan_root, repository_root, lineage, candidate_run_id, current, exclusions)
    if fold_findings:
        return fold_findings
    return validate_candidate_model(
        plan_root,
        manifest,
        manifest_path,
        test_patch,
        expected,
        expected_patch,
        folded,
        fold_hash,
        current,
        candidate_run_id,
    )


def validate_committed_candidate_diff(
    plan_root: Path, repository_root: Path, contract: dict[str, Any], manifest: dict[str, Any],
    manifest_path: str, test_patch: bytes, candidate_run_id: str,
) -> list[dict[str, str]]:
    """Independently recompute the declared committed-range migration candidate."""
    try:
        run_dir = (repository_root / manifest_path).resolve().parent
        range_path = run_dir / "committed-candidate-range.json"
        range_map = json.loads(range_path.read_text(encoding="utf-8"))
        if manifest.get("run_id") != candidate_run_id or manifest.get("basis") != "committed-range":
            raise ValueError("candidate run identity or basis is invalid")
        ref = manifest.get("range_map_ref", {})
        if ref != {"path_type": "run_path", "path": "committed-candidate-range.json", "sha256": value_hash(range_map)}:
            raise ValueError("candidate range map reference is stale")
        if range_map.get("schema_version") != "jimuyun.committed-candidate-range.v1" or range_map.get("authorizes") != [] or range_map.get("rename_policy") != "delete-add-no-renames" or range_map.get("root_hash") != value_hash({key: value for key, value in range_map.items() if key != "root_hash"}):
            raise ValueError("committed range map is malformed or authoritative")
        base, head = str(range_map["base_commit"]), str(range_map["head_commit"])
        if _git(repository_root, "merge-base", "--is-ancestor", base, head) != b"":
            raise ValueError("committed range ancestry is invalid")
        paths = [item for item in _git(repository_root, "diff", "--no-renames", "--name-only", "-z", base, head).decode("utf-8").split("\0") if item]
        if len(paths) != len(range_map.get("files", [])):
            raise ValueError("committed range file coverage is incomplete")
        expected: list[dict[str, Any]] = []
        for path in sorted(paths, key=str.casefold):
            before = _git(repository_root, "show", f"{base}:{path}", accepted={0, 128}) if _git(repository_root, "cat-file", "-e", f"{base}:{path}", accepted={0, 1}) == b"" else None
            after = _git(repository_root, "show", f"{head}:{path}", accepted={0, 128}) if _git(repository_root, "cat-file", "-e", f"{head}:{path}", accepted={0, 1}) == b"" else None
            change = "add" if before is None else "delete" if after is None else "modify"
            matches = []
            for index in range(7):
                policy = scope_policy(plan_root, repository_root, contract, f"RMAP-S{index}")
                if any(_matches(path, policy[role]) for role in ("production", "test", "documentation")) and not _matches(path, policy["forbidden"]):
                    matches.append(f"RMAP-S{index}")
            if not matches:
                raise ValueError(f"committed candidate path outside declared closure: {path}")
            expected.append({"change_type": change, "baseline_path": None if change == "add" else path, "candidate_path": None if change == "delete" else path, "before_sha256": None if before is None else bytes_hash(before), "after_sha256": None if after is None else bytes_hash(after), "slice_id": matches[0], "commit_hashes": _git(repository_root, "log", "--format=%H", f"{base}..{head}", "--", path).decode("ascii").split()})
        patch = _git(repository_root, "diff", "--binary", "--full-index", "--no-renames", "--no-ext-diff", "--no-textconv", base, head, "--")
        if range_map.get("files") != expected or manifest.get("files") != expected or test_patch != patch or manifest.get("test_diff_ref", {}).get("sha256") != bytes_hash(patch):
            raise ValueError("committed range candidate differs from independent Git recomputation")
        if manifest.get("root_hash") != manifest_root_hash(manifest):
            raise ValueError("committed range candidate root hash is stale")
        return []
    except (OSError, UnicodeError, KeyError, ValueError, json.JSONDecodeError) as exc:
        return [_finding("RMAP-COMMITTED-RANGE-EXACT", manifest_path, str(exc))]


def validate_candidate_model(
    plan_root: Path,
    manifest: dict[str, Any],
    manifest_path: str,
    test_patch: bytes,
    expected: list[dict[str, Any]],
    expected_patch: bytes,
    folded: list[dict[str, Any]],
    fold_hash: str,
    current: dict[str, str],
    candidate_run_id: str,
) -> list[dict[str, str]]:
    schema = json.loads((plan_root / "schemas" / "candidate-diff-manifest.v1.schema.json").read_text(encoding="utf-8"))
    error = schema_error(manifest, schema)
    if error:
        return [_finding("RMAP-CANDIDATE-DIFF-EXACT", manifest_path, error)]
    baseline = manifest.get("baseline_identity", {})
    identity = manifest.get("candidate_identity", {})
    if baseline != {"head": current.get("head"), "index_tree": current.get("index_tree")}:
        return [_finding("RMAP-CANDIDATE-DIFF-EXACT", manifest_path, "candidate diff baseline identity is stale")]
    expected_identity = {key: current.get(key) for key in ("tracked_diff_hash", "untracked_manifest_hash", "candidate_worktree_hash")}
    if identity != expected_identity or manifest.get("run_id") != candidate_run_id:
        return [_finding("RMAP-CANDIDATE-DIFF-EXACT", manifest_path, "candidate diff run or worktree identity is stale")]
    if _core(expected) != folded:
        return [_finding("RMAP-CANDIDATE-LEDGER-FOLD", manifest_path, "accepted-attempt fold differs from the independently recomputed candidate")]
    files = manifest.get("files", [])
    if files != expected:
        return [_finding("RMAP-CANDIDATE-DIFF-EXACT", manifest_path, "manifest differs from the scoped Git candidate diff")]
    if manifest.get("accepted_attempt_fold_hash") != fold_hash:
        return [_finding("RMAP-CANDIDATE-LEDGER-FOLD", manifest_path, "accepted-attempt fold hash is stale")]
    if any(entry.get("scope") != "allowed" for entry in expected):
        return [_finding("RMAP-CANDIDATE-DIFF-SCOPE", manifest_path, "candidate includes forbidden or dependency drift")]
    patch_ref = manifest.get("test_diff_ref", {})
    if test_patch != expected_patch or patch_ref.get("sha256") != bytes_hash(test_patch):
        return [_finding("RMAP-CANDIDATE-TEST-PATCH", manifest_path, "test patch is empty, stale, or not reproducible")]
    if manifest.get("root_hash") != manifest_root_hash(manifest):
        return [_finding("RMAP-CANDIDATE-DIFF-EXACT", manifest_path, "candidate diff root hash is stale")]
    return []


def _mutate(value: Any, mutation: dict[str, Any]) -> Any:
    result = json.loads(json.dumps(value))
    parts = mutation["path"].strip("/").split("/")
    parent = result
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    key = parts[-1]
    if mutation["op"] == "remove":
        if isinstance(parent, list):
            del parent[int(key)]
        else:
            del parent[key]
    elif mutation["op"] == "replace":
        if isinstance(parent, list):
            parent[int(key)] = mutation["value"]
        else:
            parent[key] = mutation["value"]
    elif mutation["op"] == "add":
        if isinstance(parent, list):
            parent.append(mutation["value"]) if key == "-" else parent.insert(int(key), mutation["value"])
        else:
            parent[key] = mutation["value"]
    return result


def validate_candidate_fixture_suite(plan_root: Path) -> list[dict[str, str]]:
    fixture_path = plan_root / "fixtures" / "candidate-diff-cases.v1.json"
    document = json.loads(fixture_path.read_text(encoding="utf-8"))
    base = document["base"]
    findings: list[dict[str, str]] = []
    base_observed = validate_candidate_model(
        plan_root,
        base["manifest"],
        "valid-candidate-diff",
        base["test_patch"].encode("utf-8"),
        base["expected_files"],
        base["expected_test_patch"].encode("utf-8"),
        base["folded_files"],
        value_hash(base["folded_files"]),
        base["current_identity"],
        base["candidate_run_id"],
    )
    if base_observed:
        findings.append(_finding("RMAP-STRUCT-FIXTURE", "valid-candidate-diff", f"valid fixture failed: {sorted({item['rule_id'] for item in base_observed})}"))
    valid_lineage = validate_candidate_lineage_model(
        plan_root,
        base["lineage"],
        [(item["document"], item["raw"].encode("utf-8")) for item in base["lineage_runs"]],
        base["candidate_run_id"],
        base["current_identity"],
    )
    if valid_lineage[2]:
        findings.append(_finding("RMAP-STRUCT-FIXTURE", "valid-candidate-lineage", f"valid fixture failed: {sorted({item['rule_id'] for item in valid_lineage[2]})}"))
    for case in document["cases"]:
        if case["target"] == "lineage":
            lineage = json.loads(json.dumps(base["lineage"]))
            for mutation in case.get("mutations", []):
                lineage = _mutate(lineage, mutation)
            observed = validate_candidate_lineage_model(plan_root, lineage, [(item["document"], item["raw"].encode("utf-8")) for item in base["lineage_runs"]], base["candidate_run_id"], base["current_identity"])
            rules = {item["rule_id"] for item in observed[2]}
            if rules != {case["expected_rule"]}:
                findings.append(_finding("RMAP-STRUCT-FIXTURE", case["id"], f"expected {case['expected_rule']}, observed {sorted(rules)}"))
            continue
        if case["target"] in {"supersession", "supersession_index"}:
            recovery = json.loads(json.dumps(base["supersession_recovery"]))
            successor_run_ids = list(base["supersession_successor_run_ids"])
            for mutation in case.get("mutations", []):
                if case["target"] == "supersession":
                    recovery = _mutate(recovery, mutation)
                else:
                    successor_run_ids = _mutate(successor_run_ids, mutation)
            observed = validate_candidate_supersession_model(plan_root, base["supersession_proof"], recovery, base["supersession_events"], successor_run_ids, base["candidate_run_id"])
            rules = {item["rule_id"] for item in observed}
            if rules != {case["expected_rule"]}:
                findings.append(_finding("RMAP-STRUCT-FIXTURE", case["id"], f"expected {case['expected_rule']}, observed {sorted(rules)}"))
            continue
        if case["target"] == "candidate_ref":
            candidate = base["candidate_document"]
            candidate_bytes = json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode("utf-8")
            candidate_ref = json.loads(json.dumps(base["candidate_ref"]))
            for mutation in case.get("mutations", []):
                candidate_ref = _mutate(candidate_ref, mutation)
            observed = validate_candidate_result_ref(
                plan_root,
                candidate_ref,
                case["id"],
                base["candidate_path"],
                candidate_bytes,
                candidate,
            )
            rules = {item["rule_id"] for item in observed}
            if rules != {case["expected_rule"]}:
                findings.append(_finding("RMAP-STRUCT-FIXTURE", case["id"], f"expected {case['expected_rule']}, observed {sorted(rules)}"))
            continue
        manifest = json.loads(json.dumps(base["manifest"]))
        expected = json.loads(json.dumps(base["expected_files"]))
        folded = json.loads(json.dumps(base["folded_files"]))
        test_patch = base["test_patch"].encode("utf-8")
        expected_patch = base["expected_test_patch"].encode("utf-8")
        target = case["target"]
        for mutation in case.get("mutations", []):
            if target == "manifest":
                manifest = _mutate(manifest, mutation)
            elif target == "expected_files":
                expected = _mutate(expected, mutation)
            elif target == "folded_files":
                folded = _mutate(folded, mutation)
            elif target == "test_patch":
                test_patch = mutation["value"].encode("utf-8")
        observed = validate_candidate_model(
            plan_root,
            manifest,
            case["id"],
            test_patch,
            expected,
            expected_patch,
            folded,
            value_hash(folded),
            base["current_identity"],
            base["candidate_run_id"],
        )
        rules = {item["rule_id"] for item in observed}
        if rules != {case["expected_rule"]}:
            findings.append(_finding("RMAP-STRUCT-FIXTURE", case["id"], f"expected {case['expected_rule']}, observed {sorted(rules)}"))
    return findings
