"""Fail-closed TC-D1 execution bindings (Accepted ADR-0058 and ADR-0060).

Repository Git objects are the existing-validator source of record. A candidate
descriptor cannot approve changed validator dependencies. Alternative validator
approval and Consumer exceptions remain C3 decisions outside this adapter.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import zipfile
from pathlib import Path

TRUST_BASELINE = "e289d7d3f8572595ca28c498adc798d1fa2a2bf7"
TIMEOUT_SECONDS = 60
OUTPUT_LIMIT = 8 * 1024 * 1024
PACKAGE_ROOTS = (".agents/skills/run-refactor-implementation-acceptance", ".agents/skills/vdd-execution-plan")
SOURCE_ROOTS = (*PACKAGE_ROOTS, ".agents/skills/quick-dev-tdd-adapter", "scripts/sc", "scripts/python", "scripts/toolchain", "scripts/vdd", "scripts/quick_dev", "knowledge", "docs/adr")
CONSUMERS = (
    ("vdd-execution-plan", ".agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py"),
    ("run-refactor-implementation-acceptance", ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py"),
    ("workflow-model-routing", "scripts/sc/tests/test_workflow_model_routing.py"),
)
KNOWLEDGE_CALLER = "scripts/python/validate_knowledge_workflow_integration.py"
KNOWLEDGE_CHECKS = {
    "knowledge-workflow-vdd-package": "vdd-contract",
    "knowledge-workflow-acceptance-package": "refactor-acceptance-package",
}


def sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical(value) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def relative(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or any(character in name for character in ("\\", "\n", "\r", "\0")):
        raise ValueError("path must be a normalized repository-relative identity")
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != name:
        raise ValueError("path must be a normalized repository-relative identity")
    result = root / path
    result.resolve().relative_to(root.resolve())
    return result


def files(root: Path, names) -> list[Path]:
    result = set()
    for name in names:
        path = relative(root, name)
        candidates = path.rglob("*") if path.is_dir() else (path,)
        for item in candidates:
            if item.is_symlink():
                raise ValueError("symlink is not a supported replay input: " + name)
            if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc":
                item.resolve().relative_to(root.resolve())
                result.add(item)
    return sorted(result)


def bindings(root: Path, names) -> list[dict]:
    return [{"path": p.relative_to(root).as_posix(), "sha256": sha(p.read_bytes())} for p in files(root, names)]


def child_environment() -> dict:
    # Do not inherit candidate Python injection or arbitrary model credentials.
    permitted = ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG", "LC_ALL")
    value = {name: os.environ[name] for name in permitted if name in os.environ}
    value.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return value


def execute(command: list[str], root: Path, timeout: float = TIMEOUT_SECONDS, output_limit: int = OUTPUT_LIMIT) -> subprocess.CompletedProcess:
    if timeout <= 0 or timeout > TIMEOUT_SECONDS:
        raise ValueError("execution time budget is outside the bounded adapter")
    if not isinstance(output_limit, int) or isinstance(output_limit, bool) or not 0 < output_limit <= OUTPUT_LIMIT:
        raise ValueError("execution output budget is outside the bounded adapter")
    # File-backed output avoids unbounded communicate() buffers on either OS.
    with tempfile.TemporaryDirectory(prefix="tc-d1-output-") as directory:
        out, err = Path(directory) / "stdout", Path(directory) / "stderr"
        with out.open("wb") as stdout, err.open("wb") as stderr:
            process = subprocess.Popen(command, cwd=root, stdout=stdout, stderr=stderr, env=child_environment())
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                code = 124
        if out.stat().st_size + err.stat().st_size > output_limit:
            raise ValueError("aggregate output budget exhausted")
        result = subprocess.CompletedProcess(command, code, out.read_bytes().decode("utf-8"), err.read_bytes().decode("utf-8"))
        result.pid = process.pid
        if code == 124:
            raise ValueError("validator or Consumer timed out")
        return result


def git(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(["git", *arguments], cwd=root, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError("immutable Git input is unavailable: " + " ".join(arguments[:2]))
    if len(result.stdout) > 64 * 1024 * 1024:
        raise ValueError("Git input exceeds the bounded adapter")
    return result.stdout


def trust_commit(root: Path) -> str:
    requested = TRUST_BASELINE
    override = os.environ.get("TC_D1_TRUST_COMMIT")
    if override is not None and override != requested:
        raise ValueError("an environment override cannot grant independent Trust Approval (C3)")
    if not re.fullmatch(r"[0-9a-f]{40}", requested):
        raise ValueError("trust source must be an externally supplied full commit identity")
    actual = git(root, "rev-parse", "--verify", requested + "^{commit}").decode().strip()
    if actual != requested:
        raise ValueError("trust commit identity mismatch")
    return actual


def git_bytes(root: Path, commit: str, path: str) -> bytes:
    relative(root, path)
    return git(root, "show", commit + ":" + path)


def git_blob_identities(root: Path, commit: str, paths: list[str]) -> dict[str, str]:
    for name in paths:
        relative(root, name)
    request = "".join(commit + ":" + name + "\n" for name in paths).encode("utf-8")
    result = subprocess.run(["git", "cat-file", "--batch"], cwd=root, input=request, capture_output=True, timeout=30, check=False)
    if result.returncode or len(result.stdout) > 64 * 1024 * 1024:
        raise ValueError("immutable Git dependency batch is unavailable or exceeds its budget")
    data, offset, identities = result.stdout, 0, {}
    for name in paths:
        end = data.find(b"\n", offset)
        header = data[offset:end].split()
        if end < 0 or len(header) != 3 or header[1] != b"blob":
            raise ValueError("immutable Git dependency is missing: " + name)
        size = int(header[2])
        raw = data[end + 1:end + 1 + size]
        if len(raw) != size or data[end + 1 + size:end + 2 + size] != b"\n":
            raise ValueError("immutable Git dependency batch is truncated")
        identities[name] = sha(raw)
        offset = end + 2 + size
    if offset != len(data):
        raise ValueError("immutable Git dependency batch contains unbound data")
    return identities


def dependency_closure(root: Path, seeds) -> list[dict]:
    """Conservative owning resources plus local import closure to a fixed point.

    Whole owner directories cover data/policy/configuration even when no Probe
    reaches them. Static local imports expand beyond the owner, including
    imports in functions. Ambiguous local names are all bound, never guessed.
    Dynamic additions seen by a supported adapter must be declared as seeds.
    """
    selected = set(files(root, seeds))
    search = [root, root / "scripts/python", root / "scripts/sc", root / "scripts/toolchain", *(root / owner / "scripts" for owner in PACKAGE_ROOTS)]
    pending = list(selected)
    while pending:
        path = pending.pop()
        if path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names.add(module)
                names.update(".".join(filter(None, (module, alias.name))) for alias in node.names)
        found = set()
        for name in names:
            parts = name.split(".")
            for base in [path.parent, *search]:
                candidate = base.joinpath(*parts)
                if candidate.with_suffix(".py").is_file():
                    found.add(candidate.with_suffix(".py"))
                if (candidate / "__init__.py").is_file():
                    found.update(files(root, [candidate.relative_to(root).as_posix()]))
        for item in found:
            item.resolve().relative_to(root.resolve())
            if item not in selected:
                selected.add(item)
                pending.append(item)
    result = []
    for path in sorted(selected):
        kind = "executable" if path.suffix in {".py", ".ps1", ".sh"} else ("policy" if "policies" in path.parts else ("configuration" if path.suffix in {".json", ".yaml", ".toml"} else "data"))
        result.append({"kind": kind, "path": path.relative_to(root).as_posix(), "sha256": sha(path.read_bytes())})
    return result


def verify_trust(root: Path, validator: Path, value: dict, capability_path: str | None = None) -> dict:
    source = relative(root, value.get("validator_source"))
    if source.resolve() == validator.resolve():
        raise ValueError("validator cannot be its own independent source")
    rules = value.get("required_rules")
    if not isinstance(rules, list) or any(not isinstance(rule, str) or not rule for rule in rules):
        raise ValueError("required rule declaration is invalid")
    checks = {rule: rule in validator.read_text(encoding="utf-8") for rule in rules}
    missing = [rule for rule, present in checks.items() if not present]
    if missing:
        raise ValueError("independent validator verification missing required rule: " + ",".join(missing))
    commit = trust_commit(root)
    allowed = value["allowed_root"]
    # The entire immutable owner is included, not only the entrypoint.
    seeds = [allowed, value["validator_source"]]
    if capability_path:
        seeds.append(capability_path)
    closure = dependency_closure(root, seeds)
    paths = [row["path"] for row in closure]
    frozen_owner = git(root, "ls-tree", "-r", "--name-only", commit, "--", allowed).decode("utf-8").splitlines()
    current_owner = [row["path"] for row in bindings(root, [allowed])]
    if frozen_owner != current_owner:
        raise ValueError("validator dependency membership drift requires independent Trust Approval (C3)")
    frozen_identities = git_blob_identities(root, commit, paths)
    for row in closure:
        if frozen_identities[row["path"]] != row["sha256"]:
            raise ValueError("validator dependency drift requires independent Trust Approval (C3): " + row["path"])
    declared_content = sha(validator.read_bytes())
    if declared_content != value.get("validator_sha256") or sha(source.read_bytes()) != value.get("validator_source_sha256"):
        raise ValueError("validator or source identity drift")
    if source.suffix == ".json":
        declaration = json.loads(source.read_text(encoding="utf-8"))
        if declaration.get("validator_path") != validator.relative_to(root).as_posix() or declaration.get("validator_sha256") != declared_content or declaration.get("authorizes") != []:
            raise ValueError("independent validator source does not bind the validator")
    elif source.read_bytes() != validator.read_bytes():
        raise ValueError("independent validator source does not bind the validator")
    # Rule strings are diagnostic only; immutable bytes and closure decide trust.
    return {"schema": "jimuyun.independent-validator-verification.v2", "status": "pass", "independent": True, "source_path": value["validator_source"], "source_sha256": sha(source.read_bytes()), "declared_source_sha256": value["validator_source_sha256"], "content_sha256": declared_content, "source_matches_declaration": True, "content_matches_source": True, "required_rule_checks": checks, "trust_commit": commit, "semantic_dependencies": closure, "dependency_closure_sha256": canonical(closure), "authorizes": []}


def observed_validator(root: Path, validator: Path, value: dict, target: Path, timeout_ms=None):
    with tempfile.TemporaryDirectory(prefix="tc-d1-observer-") as directory:
        output, nonce = Path(directory) / "reads.json", secrets.token_hex(24)
        observer = Path(__file__).with_name("skill_replay_observer.py")
        command = [sys.executable, "-X", "utf8", "-I", "-S", "-B", str(observer), str(validator), str(target), str(output), nonce, *[str(target) if item == "{target}" else item for item in value["probe_args"]]]
        result = execute(command, root, min(TIMEOUT_SECONDS, timeout_ms / 1000) if timeout_ms is not None else TIMEOUT_SECONDS)
        if not output.is_file():
            raise ValueError("validator did not complete its independent read observation")
        witness = json.loads(output.read_text(encoding="utf-8"))
        if witness.get("nonce") != nonce or witness.get("pid") != result.pid or witness.get("target") != str(target.resolve()):
            raise ValueError("validator read observation identity mismatch")
        result.read_witness = witness
        return result


def findings(result) -> list[str]:
    try:
        payload = json.loads(result.stdout)
    except (ValueError, TypeError):
        return []
    if not isinstance(payload, dict):
        return []
    values = payload.get("findings", [])
    return [row if isinstance(row, str) else str(row.get("rule_id", "")) for row in values if isinstance(row, (str, dict))]


def negative_oracle(value: dict) -> dict:
    declared = value.get("negative_probe")
    if declared is None and value.get("allowed_root") == PACKAGE_ROOTS[0]:
        declared = {"path": "fixtures/negative-cases.v1.json", "replacement": {}, "diagnostic": "fixture-catalog-invalid"}
    if not isinstance(declared, dict) or not isinstance(declared.get("diagnostic"), str) or not declared["diagnostic"]:
        raise ValueError("detached negative Probe requires a declared defect and diagnostic")
    return declared


def require_reads(result, target: Path) -> list[dict]:
    reads = getattr(result, "read_witness", {}).get("reads", [])
    if not reads or not any(row.get("bytes_read", 0) > 0 for row in reads):
        raise ValueError("validator produced no execution-time target reads")
    for row in reads:
        path = relative(target, row["path"])
        if not path.is_file():
            raise ValueError("validator read observation does not name a real target file")
    return reads


def assert_identity(root: Path, expected: list[dict]) -> None:
    for row in expected:
        path = relative(root, row["path"])
        if not path.is_file() or sha(path.read_bytes()) != row["sha256"]:
            raise ValueError("dirty baseline: " + row["path"])


def require_disjoint_read_set(read_set: list[str], changed_paths: list[str]) -> None:
    collision = sorted(set(read_set) & set(changed_paths))
    if collision:
        raise ValueError("knowledge read-set collision: " + ",".join(collision))


def require_closed_policy_index(policy: dict, index: list[str]) -> None:
    required = policy.get("required_decisions")
    if policy.get("state") != "closed" or not isinstance(required, list) or not required or not all(isinstance(p, str) and p for p in required):
        raise ValueError("closed policy contract is invalid")
    if set(required) - set(index):
        raise ValueError("closed policy/index gap")


def environment_binding() -> dict:
    values = child_environment()
    stdlib = Path(sysconfig.get_path("stdlib"))
    library_files = []
    for directory, subdirs, names in os.walk(stdlib):
        subdirs[:] = [name for name in subdirs if name not in {"site-packages", "__pycache__"}]
        library_files.extend(Path(directory) / name for name in names if Path(name).suffix in {".py", ".so", ".pyd", ".dll", ".zip"})
    library_files.sort()
    library_identity = canonical([{"path": path.relative_to(stdlib).as_posix(), "sha256": sha(path.read_bytes())} for path in library_files])
    return {"kind": "environment", "python": {"implementation": platform.python_implementation(), "version": list(sys.version_info[:3]), "executable_sha256": sha(Path(sys.executable).read_bytes()), "stdlib_sha256": library_identity, "isolated": True, "site_disabled": True, "utf8": True}, "platform": sys.platform, "os_version": platform.version(), "machine": platform.machine(), "child_environment_sha256": canonical(values), "time_budget_seconds": TIMEOUT_SECONDS, "output_budget_bytes": OUTPUT_LIMIT}


def consumer_manifest(root: Path) -> dict:
    entries = []
    for name, path in CONSUMERS:
        entry = relative(root, path)
        if not entry.is_file():
            raise ValueError("required Consumer entrypoint is absent: " + path)
        target = PACKAGE_ROOTS[0] if name == "run-refactor-implementation-acceptance" else (PACKAGE_ROOTS[1] if name == "vdd-execution-plan" else "scripts/sc")
        entries.append({"consumer": name, "path": path, "target": target, "sha256": sha(entry.read_bytes())})
    caller = relative(root, KNOWLEDGE_CALLER)
    if caller.is_file():
        for name, check in KNOWLEDGE_CHECKS.items():
            target = PACKAGE_ROOTS[1] if check == "vdd-contract" else PACKAGE_ROOTS[0]
            entries.append({"consumer": name, "path": KNOWLEDGE_CALLER, "interface": "_declared_checks", "declared_check": check, "target": target, "sha256": sha(caller.read_bytes())})
    known = {path for _, path in CONSUMERS} | {"scripts/sc/skill_package_replay.py", "scripts/sc/skill_replay_runtime.py", KNOWLEDGE_CALLER}
    discovered, missing = [], []
    for path in files(root, SOURCE_ROOTS):
        if path.suffix != ".py" or "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        aliases = {"validate_package", "validate_skill"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                aliases.update(alias.asname or alias.name for alias in node.names if alias.name in {"validate_package", "validate_skill"})
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and ((isinstance(node.func, ast.Name) and node.func.id in aliases) or (isinstance(node.func, ast.Attribute) and node.func.attr in {"validate_package", "validate_skill"}))]
        literals = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        native_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"run", "Popen", "run_path"}]
        if native_calls and any(value == "validate-package" or value.endswith("/validate_skill_contract.py") for value in literals):
            calls.extend(native_calls)
        if calls:
            name = path.relative_to(root).as_posix()
            discovered.append({"path": name, "lines": sorted(node.lineno for node in calls), "sha256": sha(path.read_bytes())})
            if name not in known:
                missing.append(name)
    if missing:
        raise ValueError("Consumer Manifest has undeclared real call surfaces: " + ",".join(sorted(missing)))
    closure = dependency_closure(root, SOURCE_ROOTS)
    identity = {"entries": entries, "call_surface": discovered, "dependencies": closure}
    return {**identity, "version": canonical(identity), "bidirectional_reconciled": True, "missing_callers": [], "orphan_manifest_entries": [], "frozen_before_review": True, "mutable_after_freeze": False}


def snapshot(root: Path, target: str, capability_path: str, validator: Path, schema: str, include_git=True) -> dict:
    declaration = json.loads(relative(root, capability_path).read_text(encoding="utf-8"))
    source = declaration.get("validator_source")
    source_names = (source,) if isinstance(source, str) else ()
    closure = dependency_closure(root, (*SOURCE_ROOTS, target, capability_path, validator.parent.relative_to(root).as_posix(), *source_names))
    matrix = "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/stable-candidate-replay-matrix.v1.json"
    historical = "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd"
    data = bindings(root, (matrix, historical))
    environment = environment_binding()
    inputs = {"dependencies": closure, "data": data, "environment": environment}
    if include_git:
        try:
            inputs["git_baseline"] = git(root, "rev-parse", "HEAD").decode().strip()
            inputs["trust_baseline"] = trust_commit(root)
        except ValueError:
            # Structural unit tests may inspect an unversioned tree. This is
            # never eligible to publish a complete replay snapshot.
            inputs["git_baseline"] = None
            inputs["trust_baseline"] = None
    package = bindings(root, (target,))
    plan_path = relative(root, matrix)
    fixture = {"positive_bindings": package, "negative_oracle": negative_oracle(declaration)}
    roots = [
        {"root_kind": "candidate_tree", "identity_kind": "directory-manifest", "path": target, "sha256": canonical(package)},
        {"root_kind": "plan", "identity_kind": "file-or-absence", "path": matrix, "sha256": sha(plan_path.read_bytes()) if plan_path.is_file() else canonical({"absent": matrix})},
        {"root_kind": "contract", "identity_kind": "file", "path": capability_path, "sha256": sha(relative(root, capability_path).read_bytes())},
        {"root_kind": "descriptor", "identity_kind": "inline-manifest", "name": "runtime-inputs", "sha256": canonical(inputs)},
        {"root_kind": "fixture", "identity_kind": "inline-manifest", "name": "detached-probe-inputs", "value": fixture, "sha256": canonical(fixture)},
        {"root_kind": "source", "identity_kind": "file", "path": "scripts/sc/skill_package_replay.py", "sha256": sha(relative(root, "scripts/sc/skill_package_replay.py").read_bytes()), "dependency_closure_sha256": canonical(closure)},
        {"root_kind": "validator_judge", "identity_kind": "file", "path": validator.relative_to(root).as_posix(), "sha256": sha(validator.read_bytes())},
        {"root_kind": "plan_state_transition", "identity_kind": "inline-manifest", "name": "consumer-call-interfaces", "sha256": canonical(bindings(root, tuple(path for _, path in CONSUMERS)))},
    ]
    return {"schema": schema, "sha256": canonical({"roots": roots, "inputs": inputs}), "roots": roots, "inputs": inputs, "complete": bool(inputs.get("git_baseline") and inputs.get("trust_baseline"))}


def materialize_git(root: Path, commit: str, destination: Path, paths) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    archive = destination.with_suffix(".zip")
    try:
        git(root, "archive", "--format=zip", commit, "-o", str(archive), "--", *paths)
        with zipfile.ZipFile(archive) as bundle:
            for name in bundle.namelist():
                relative(destination, name.rstrip("/"))
            bundle.extractall(destination)
    finally:
        archive.unlink(missing_ok=True)


def command(consumer: str, target: str) -> list[str]:
    python = [sys.executable, "-X", "utf8", "-I", "-S", "-B"]
    if consumer == "vdd-execution-plan":
        return [*python, CONSUMERS[0][1], "--skill-root", target]
    if consumer == "run-refactor-implementation-acceptance":
        return [*python, CONSUMERS[1][1], "validate-package", "--skill-root", target]
    if consumer == "workflow-model-routing":
        return [*python, CONSUMERS[2][1], "-q"]
    raise ValueError("unknown Consumer")


def outcome(result) -> dict:
    return {"exit_code": result.returncode, "verdict": "pass" if result.returncode == 0 else "execution-failed", "diagnostic_category": "exit-zero" if result.returncode == 0 else "consumer-rejected", "stdout_sha256": sha(result.stdout.encode()), "stderr_sha256": sha(result.stderr.encode())}


def route_transitions(root: Path, requested_target: str, frozen: dict, capability_path: str) -> dict:
    commit = trust_commit(root)
    declaration = json.loads(relative(root, capability_path).read_text(encoding="utf-8"))
    acceptance_oracle = negative_oracle(declaration)
    with tempfile.TemporaryDirectory(prefix="tc-d1-prior-route-") as directory:
        prior = Path(directory) / "prior"
        archive_paths = [name for name in (*SOURCE_ROOTS, requested_target) if relative(root, name).exists()]
        materialize_git(root, commit, prior, archive_paths)
        prior_manifest = consumer_manifest(prior)
        if [e["consumer"] for e in prior_manifest["entries"]] != [e["consumer"] for e in frozen["entries"]]:
            raise ValueError("Prior Route Consumer set differs; an exception requires C3 approval")
        route_ids = {"Prior Route": canonical({"commit": commit, "manifest": prior_manifest}), "Candidate Route": canonical(frozen)}
        baselines, calls, transitions = {}, [], []

        def invoke(location, entry, stage, fixture):
            consumer = entry["consumer"]
            acceptance_consumer = consumer in {"run-refactor-implementation-acceptance", "knowledge-workflow-acceptance-package"}
            selected = requested_target if acceptance_consumer else entry["target"]
            target_root = relative(location, selected)
            invocation_target = str(target_root)
            expected = None
            if fixture == "invalid-package":
                oracle = acceptance_oracle if acceptance_consumer else {"path": "scripts/skill-contract.json", "replacement": [], "diagnostic": "VDD-SKILL-CONTRACT"}
                package = Path(directory) / "fixtures" / stage / consumer
                shutil.copytree(target_root, package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                defect = relative(package, oracle["path"])
                if not defect.is_file():
                    raise ValueError("required Consumer rollback fixture is absent: " + oracle["path"])
                defect.write_text(json.dumps(oracle["replacement"]), encoding="utf-8", newline="\n")
                target_root, invocation_target, expected = package, str(package), oracle["diagnostic"]
            caller_binding = None
            if consumer in KNOWLEDGE_CHECKS:
                source = relative(location, entry["path"])
                if git_blob_identities(root, commit, [entry["path"]])[entry["path"]] != sha(source.read_bytes()):
                    raise ValueError("existing Consumer factory changed; review its change authority before replay")
                specification = importlib.util.spec_from_file_location("tc_d1_knowledge_caller", source)
                module = importlib.util.module_from_spec(specification)
                specification.loader.exec_module(module)
                checks = dict(module._declared_checks())
                emitted = checks[entry["declared_check"]]
                leaf = "vdd-execution-plan" if consumer == "knowledge-workflow-vdd-package" else "run-refactor-implementation-acceptance"
                canonical_command = command(leaf, invocation_target)
                prefix = len([sys.executable, "-X", "utf8", "-I", "-S", "-B"])
                expected_original = [sys.executable, "-B", canonical_command[prefix]]
                expected_original += ["--skill-root", PACKAGE_ROOTS[1]] if leaf == "vdd-execution-plan" else ["validate-package"]
                if emitted != expected_original:
                    raise ValueError("Consumer factory emitted an undeclared package-validation command")
                invocation = canonical_command
                caller_binding = {"source": entry["path"], "source_sha256": sha(source.read_bytes()), "interface": entry["interface"], "declared_check": entry["declared_check"], "emitted_command": emitted, "invocation_target": invocation_target}
            else:
                invocation = command(consumer, invocation_target)
            # The native observer measures this Consumer's own target reads.
            # Workflow routing observes its terminal policy/schema interface.
            prefix = len([sys.executable, "-X", "utf8", "-I", "-S", "-B"])
            entry_path, arguments = invocation[prefix], invocation[prefix + 1:]
            probe_args = ["{target}" if argument == invocation_target else argument for argument in arguments]
            result = observed_validator(location, relative(location, entry_path), {"probe_args": probe_args}, target_root)
            if expected is None:
                matched = result.returncode == 0
                diagnostic = "exit-zero" if matched else "consumer-rejected"
                verdict = "pass" if matched else "execution-failed"
            else:
                matched = result.returncode in {1, 2} and expected in findings(result) and not result.stderr.strip()
                diagnostic, verdict = expected, "expected-rejection"
            if not matched:
                raise ValueError("required Consumer failed during " + stage + ": " + consumer + "/" + fixture + ": " + result.stdout + result.stderr)
            try:
                reads = require_reads(result, target_root)
            except ValueError as exc:
                raise ValueError("required Consumer failed during " + stage + ": " + consumer + ": " + str(exc)) from exc
            return {"consumer": consumer, "path": entry["path"], "target": selected, "actual_target": str(target_root), "fixture": fixture, "command": invocation, "caller_binding": caller_binding, "executed": True, "pid": result.pid, "stage": stage, "matched_expected": True, **outcome(result), "verdict": verdict, "diagnostic_category": diagnostic, "reads": reads, "stdout": result.stdout, "stderr": result.stderr}

        for entry in prior_manifest["entries"]:
            fixtures = ("valid-package", "invalid-package") if entry["consumer"] != "workflow-model-routing" else ("terminal-policy-observation",)
            for fixture in fixtures:
                observed = invoke(prior, entry, "prior-baseline", fixture)
                key = entry["consumer"] + ":" + fixture
                baselines[key] = {"route_identity": route_ids["Prior Route"], **observed}
        for stage, route in (("enable", "Candidate Route"), ("disable", "Prior Route"), ("rollback", "Prior Route"), ("re-enable", "Candidate Route")):
            location = prior if route == "Prior Route" else root
            for entry in frozen["entries"]:
                fixtures = ("valid-package", "invalid-package") if entry["consumer"] != "workflow-model-routing" else ("terminal-policy-observation",)
                for fixture in fixtures:
                    observed = invoke(location, entry, stage, fixture)
                    baseline = baselines[entry["consumer"] + ":" + fixture]
                    if route == "Prior Route" and any(observed[field] != baseline[field] for field in ("exit_code", "verdict", "diagnostic_category")):
                        raise ValueError("Prior Route did not reproduce its captured behavior")
                    calls.append({**observed, "route": route, "route_identity": route_ids[route]})
                    baseline_match = route == "Prior Route" and all(observed[field] == baseline[field] for field in ("exit_code", "verdict", "diagnostic_category"))
                    transitions.append({**observed, "transition": stage, "status": "completed", "route": route, "route_identity": route_ids[route], "baseline": baseline, "baseline_match": baseline_match, "post_rollback_prior_behavior_baseline": {"observed": baseline_match, "identity": route_ids["Prior Route"]}})
        if consumer_manifest(root) != frozen or consumer_manifest(prior) != prior_manifest:
            raise ValueError("frozen Consumer Manifest changed during execution")
        return {"calls": calls, "transitions": transitions, "prior_baselines": baselines, "route_identities": route_ids}


SCENARIOS = ("positive", "negative", "historical_compatibility", "dirty_baseline", "knowledge_read_set", "closed_policy")


def subject_bindings(root: Path, target: str) -> list[dict]:
    # The replay entry and its runtime adapters are part of the evaluated
    # package's semantic execution boundary, not differentiating label files.
    return bindings(root, (target, "scripts/sc/skill_package_replay.py", "scripts/sc/skill_replay_runtime.py", "scripts/sc/skill_replay_observer.py"))


def evaluate_scenario(root: Path, target: str, validator: Path, value: dict, fixture: dict) -> dict:
    scenario = fixture.get("scenario")
    if scenario not in SCENARIOS or fixture.get("authorizes") != []:
        raise ValueError("unknown or authorizing Matrix scenario")
    target_root = relative(root, target)
    source_identity = canonical(bindings(root, (target,)))
    oracle = negative_oracle(value)
    calls, state_observations = [], []

    def native(package: Path, expected_defect: str | None = None):
        result = observed_validator(root, validator, value, package)
        reads = require_reads(result, package)
        if expected_defect is None:
            if result.returncode:
                raise ValueError("Matrix package rejected: " + result.stdout + result.stderr)
        elif result.returncode == 0 or expected_defect not in findings(result) or result.stderr.strip():
            raise ValueError("Matrix rejection did not observe its intended defect")
        calls.append({"pid": result.pid, "command": result.args, "target": str(package), **outcome(result), "stdout": result.stdout, "stderr": result.stderr, "reads": reads})

    def rejected_then_repaired(check, repair):
        before = canonical(bindings(root, (target,)))
        try:
            check()
        except ValueError as exc:
            diagnostic = str(exc)
        else:
            raise ValueError("Matrix faulty state was not rejected")
        repair()
        check()
        after = canonical(bindings(root, (target,)))
        state_observations.append({"fault_identity": before, "repaired_identity": after, "rejection": diagnostic, "repaired_verdict": "pass"})

    if scenario == "negative":
        defect = relative(target_root, oracle["path"])
        if not defect.is_file():
            raise ValueError("Matrix defect fixture is absent")
        defect.write_text(json.dumps(oracle["replacement"]), encoding="utf-8", newline="\n")
        native(target_root, oracle["diagnostic"])
    else:
        native(target_root)
        if scenario == "historical_compatibility":
            records = fixture.get("historical_bindings")
            if not isinstance(records, list) or len(records) != 2 or fixture.get("portability") != "machine-bound":
                raise ValueError("historical compatibility requires original validator and command bindings")
            for record in records:
                path = relative(root, record["path"])
                raw = path.read_bytes()
                if sha(raw) != record["sha256"]:
                    raise ValueError("historical input drift")
                state_observations.append({"path": record["path"], "bytes_read": len(raw), "sha256": sha(raw), "portability": "machine-bound", "current_authority": False})
        elif scenario in {"dirty_baseline", "knowledge_read_set"}:
            path = relative(target_root, fixture.get("mutation_path", "SKILL.md"))
            original = path.read_bytes()
            frozen = [{"path": path.relative_to(root).as_posix(), "sha256": sha(original)}]
            path.write_bytes(original + b"\nTC-D1 independently introduced contamination\n")
            if scenario == "dirty_baseline":
                rejected_then_repaired(lambda: assert_identity(root, frozen), lambda: path.write_bytes(original))
            else:
                read_set = [frozen[0]["path"]]

                def collision_check():
                    changed = [row["path"] for row in frozen if sha(relative(root, row["path"]).read_bytes()) != row["sha256"]]
                    require_disjoint_read_set(read_set, changed)

                rejected_then_repaired(collision_check, lambda: path.write_bytes(original))
            native(target_root)
        elif scenario == "closed_policy":
            # Real closed policy and index files, read independently at both
            # states; a .matrix-input marker is never consumed as behavior.
            directory = target_root / ".tc-d1-policy-fixture"
            directory.mkdir()
            policy_path, index_path = directory / "policy.json", directory / "index.json"
            decision = "ADR-0058-toolchain-skill-replay-portability-and-evaluation-seeds"
            policy_path.write_text(json.dumps({"state": "closed", "required_decisions": [decision]}), encoding="utf-8")
            index_path.write_text("[]", encoding="utf-8")

            def policy_check():
                require_closed_policy_index(json.loads(policy_path.read_text(encoding="utf-8")), json.loads(index_path.read_text(encoding="utf-8")))

            rejected_then_repaired(policy_check, lambda: index_path.write_text(json.dumps([decision]), encoding="utf-8"))
            shutil.rmtree(directory)
            native(target_root)
    return {"scenario": scenario, "source_package_identity": source_identity, "final_fixture_identity": canonical(bindings(root, (target,))), "status": "pass", "calls": calls, "state_observations": state_observations, "executed": True, "authorizes": []}


def invalid_matrix(matrix: dict, reason: str, terminal_state="contract-rejected", elapsed_ms=0.0) -> tuple[dict, int]:
    cases = matrix.get("cases", [])
    required = matrix.get("required_matrix_cases", [])
    present = {case.get("case_id") for case in cases if isinstance(case, dict)}
    missing = sorted(set(required) - present) if isinstance(required, list) else []
    return {"status": "invalid", "exit_code": 1, "aggregate_valid": False, "aggregate_status": "invalid", "invalid_reasons": [reason], "missing_cases": missing, "case_results": [{"case_id": case.get("case_id"), "category": case.get("category"), "status": "fail", "executed": False, "terminal_state": terminal_state, "elapsed_ms": elapsed_ms, "rejection_reason": reason} for case in cases if isinstance(case, dict)], "authorizes": []}, 1


def replay_matrix(root: Path, matrix: dict) -> tuple[dict, int]:
    started = time.monotonic()
    # Every matrix uses this gate. The previous opt-in subject_contract cannot
    # leave a successful legacy route around the provenance requirement.
    if matrix.get("schema_version") != "jimuyun.stable-candidate-replay-matrix.v3" or matrix.get("authorizes") != []:
        return invalid_matrix(matrix, "native v3 fixtures and immutable Stable provenance are required")
    cases, stable, candidate = matrix.get("cases"), matrix.get("stable"), matrix.get("candidate")
    if not isinstance(cases, list) or len(cases) != 6 or {case.get("category") for case in cases if isinstance(case, dict)} != set(SCENARIOS):
        return invalid_matrix(matrix, "exactly the six distinct semantic scenarios are required")
    ids = [case.get("case_id") for case in cases]
    if len(set(ids)) != 6 or any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) for value in ids):
        return invalid_matrix(matrix, "Matrix case identities must be unique")
    if not isinstance(stable, dict) or not re.fullmatch(r"[0-9a-f]{40}", str(stable.get("commit", ""))) or not isinstance(candidate, dict):
        return invalid_matrix(matrix, "source-supported Stable commit and Candidate bindings are required")
    time_limit, output_limit, output_used = TIMEOUT_SECONDS, OUTPUT_LIMIT, 0
    for case in cases:
        milliseconds = case.get("aggregate_time_bound_ms", TIMEOUT_SECONDS * 1000)
        byte_limit = case.get("aggregate_output_bound_bytes", OUTPUT_LIMIT)
        if (isinstance(milliseconds, bool) or not isinstance(milliseconds, (int, float)) or not math.isfinite(milliseconds)
                or isinstance(byte_limit, bool) or not isinstance(byte_limit, int)):
            return invalid_matrix(matrix, "Matrix budget declaration is invalid")
        if milliseconds <= 0 or byte_limit <= 0:
            return invalid_matrix(matrix, "aggregate Matrix budget exhausted before execution", "budget-exhausted", (time.monotonic() - started) * 1000)
        time_limit = min(time_limit, milliseconds / 1000)
        output_limit = min(output_limit, byte_limit)

    def remaining():
        duration = time_limit - (time.monotonic() - started)
        if duration <= 0 or output_used >= output_limit:
            raise ValueError("aggregate Matrix budget exhausted")
        return duration, output_limit - output_used

    def bounded_execute(command, location):
        nonlocal output_used
        duration, capacity = remaining()
        result = execute(command, location, duration, capacity)
        output_used += len(result.stdout.encode("utf-8")) + len(result.stderr.encode("utf-8"))
        remaining()
        return result

    results = []
    try:
        target, cap_path = candidate["target"], matrix["capability"]
        if stable.get("target") != target:
            raise ValueError("Stable and Candidate logical targets must match")
        value = json.loads(relative(root, cap_path).read_text(encoding="utf-8"))
        validator = relative(root, value["allowed_root"] + "/" + value["validator_entrypoint"])
        verify_trust(root, validator, value, cap_path)
        current = subject_bindings(root, target)
        if candidate.get("bindings") != current:
            raise ValueError("Candidate identity is stale")
        with tempfile.TemporaryDirectory(prefix="tc-d1-matrix-") as directory:
            frozen = Path(directory) / "stable"
            existing = [name for name in (*SOURCE_ROOTS, target, cap_path, value["allowed_root"], value["validator_source"], "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd") if relative(root, name).exists()]
            materialize_git(root, stable["commit"], frozen, existing)
            git_directory = git(root, "rev-parse", "--absolute-git-dir").decode().strip()
            (frozen / ".git").write_text("gitdir: " + git_directory + "\n", encoding="utf-8")
            prior = subject_bindings(frozen, target)
            if stable.get("bindings") != prior:
                raise ValueError("Stable identity does not match immutable provenance")
            prior_map = {row["path"]: row["sha256"] for row in prior}
            changes = []
            for row in current:
                name = row["path"]
                if not name.endswith(".py") or "/tests/" in name or row["sha256"] == prior_map.get(name):
                    continue
                before = relative(frozen, name)
                old_ast = ast.dump(ast.parse(before.read_text(encoding="utf-8-sig"))) if before.is_file() else None
                new_ast = ast.dump(ast.parse(relative(root, name).read_text(encoding="utf-8-sig")))
                if new_ast != old_ast:
                    changes.append(name)
            if not changes:
                raise ValueError("Candidate contains no relevant executable change")
            seen_inputs = set()
            for case in cases:
                remaining()
                source = relative(root, case["fixture"]["path"])
                raw = source.read_bytes()
                if sha(raw) != case["fixture"]["sha256"] or sha(raw) in seen_inputs:
                    raise ValueError("case fixture is stale or reused")
                seen_inputs.add(sha(raw))
                fixture = json.loads(raw)
                if fixture.get("scenario") != case["category"]:
                    raise ValueError("fixture scenario does not match its frozen case")
                subjects = []
                for subject, origin in (("Stable", frozen), ("Candidate", root)):
                    # Exercise the subject's own replay entry as well as the
                    # independent scenario oracle. A source hash beside calls
                    # made exclusively through Candidate code is insufficient.
                    entry = relative(origin, "scripts/sc/skill_package_replay.py")
                    wrapper_command = [sys.executable, "-X", "utf8", "-I", "-S", "-B", str(entry), "validate-package", "--target", target, "--capability", cap_path]
                    wrapper_call = bounded_execute(wrapper_command, origin)
                    if wrapper_call.returncode:
                        raise ValueError("subject's own package replay rejected its positive fixture: " + wrapper_call.stdout + wrapper_call.stderr)
                    destination = Path(directory) / case["case_id"] / subject
                    destination.mkdir(parents=True)
                    shutil.copytree(relative(origin, target), relative(destination, target))
                    # Historical native bytes are inputs, never inferred from
                    # a command string, success count, or copied expected output.
                    for record in fixture.get("historical_bindings", []):
                        output = relative(destination, record["path"])
                        output.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(relative(origin, record["path"]), output)
                    spec = {"root": str(destination), "target": target, "validator": str(validator), "capability": value, "fixture": fixture}
                    request = destination / "scenario-request.json"
                    request.write_text(json.dumps(spec), encoding="utf-8", newline="\n")
                    native = bounded_execute([sys.executable, "-X", "utf8", "-I", "-S", "-B", str(Path(__file__).resolve()), "scenario", str(request)], root)
                    if native.returncode:
                        raise ValueError("native Matrix scenario failed: " + native.stdout + native.stderr)
                    observation = json.loads(native.stdout)
                    if observation.get("scenario") != case["category"] or observation.get("status") != "pass" or not observation.get("calls"):
                        raise ValueError("Matrix scenario emitted incomplete execution evidence")
                    before = prior if subject == "Stable" else current
                    after = subject_bindings(origin, target)
                    if after != before:
                        raise ValueError(subject + " source changed during native Matrix execution")
                    subjects.append({"subject": subject, "executed": True, "target": str(relative(destination, target)), "fixture_identity": observation["source_package_identity"], "provenance": stable["commit"] if subject == "Stable" else "current-bound-candidate", "subject_identity": canonical(before), "pre_identity": canonical(before), "post_identity": canonical(after), "pid": native.pid, "invocation": {"executed": True, "exit_code": native.returncode}, "wrapper_invocation": {"command": wrapper_command, "pid": wrapper_call.pid, "entry_sha256": sha(entry.read_bytes()), **outcome(wrapper_call), "stdout": wrapper_call.stdout, "stderr": wrapper_call.stderr}, "observation": observation, "stdout_sha256": sha(native.stdout.encode()), "stderr_sha256": sha(native.stderr.encode())})
                if subjects[0]["pid"] == subjects[1]["pid"]:
                    raise ValueError("Matrix subject process evidence was reused")
                results.append({"case_id": case["case_id"], "category": case["category"], "status": "pass", "executed": True, "terminal_state": "pass", "elapsed_ms": (time.monotonic() - started) * 1000, "stable_subject": subjects[0], "candidate_subject": subjects[1], "subject_executions": subjects, "fixture": case["fixture"], "expected_result": "declared-scenario-postconditions", "observed_result": "declared-scenario-postconditions", "authorizes": []})
                if len(json.dumps(results).encode("utf-8")) > output_limit:
                    raise ValueError("aggregate Matrix output budget exhausted")
        if subject_bindings(root, target) != current:
            raise ValueError("Candidate changed during Matrix execution")
        verify_trust(root, validator, value, cap_path)
        remaining()
    except (KeyError, ValueError, OSError, TypeError) as exc:
        terminal_state = "timeout" if "timed out" in str(exc) else ("budget-exhausted" if "budget exhausted" in str(exc) else "contract-rejected")
        invalid, code = invalid_matrix(matrix, str(exc), terminal_state, (time.monotonic() - started) * 1000)
        invalid["completed_case_results"] = results
        return invalid, code
    return {"status": "pass", "exit_code": 0, "aggregate_valid": True, "aggregate_status": "valid", "case_results": results, "missing_cases": [], "invalid_reasons": [], "stable_provenance": stable, "candidate": candidate, "relevant_changed_executables": changes, "authorizes": []}, 0


def prepare_matrix(root: Path, target: str, cap_path: str, stable_commit: str, output: str) -> dict:
    resolved = git(root, "rev-parse", "--verify", stable_commit + "^{commit}").decode().strip()
    destination = relative(root, output)
    if destination.exists():
        raise ValueError("Matrix preparation is append-only")
    historical = "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd"
    with tempfile.TemporaryDirectory(prefix="tc-d1-stable-freeze-") as directory:
        frozen = Path(directory) / "stable"
        value = json.loads(relative(root, cap_path).read_text(encoding="utf-8"))
        existing = [name for name in (*SOURCE_ROOTS, target, cap_path, value["allowed_root"], value["validator_source"], historical) if relative(root, name).exists()]
        materialize_git(root, resolved, frozen, existing)
        stable_bindings = subject_bindings(frozen, target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cases = []
    for scenario in SCENARIOS:
        fixture = {"scenario": scenario, "authorizes": []}
        if scenario == "historical_compatibility":
            fixture.update(portability="machine-bound", historical_bindings=bindings(root, (historical + "/tools/validate_implementation.py", historical + "/95-implementation-evolution-and-completion-report.md")))
        if scenario in {"dirty_baseline", "knowledge_read_set"}:
            fixture["mutation_path"] = "SKILL.md"
        fixture_path = destination.parent / (destination.stem + "-fixtures") / (scenario + ".json")
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        with fixture_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(fixture, stream, sort_keys=True, indent=2)
            stream.write("\n")
        cases.append({"case_id": "case-" + scenario, "category": scenario, "fixture": {"path": fixture_path.relative_to(root).as_posix(), "sha256": sha(fixture_path.read_bytes())}})
    matrix = {"schema_version": "jimuyun.stable-candidate-replay-matrix.v3", "stable": {"commit": resolved, "target": target, "bindings": stable_bindings}, "candidate": {"target": target, "bindings": subject_bindings(root, target)}, "capability": cap_path, "required_matrix_cases": [case["case_id"] for case in cases], "cases": cases, "authorizes": []}
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(matrix, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return matrix


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "scenario":
        raise SystemExit("internal Matrix scenario request required")
    request = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    try:
        result = evaluate_scenario(Path(request["root"]), request["target"], Path(request["validator"]), request["capability"], request["fixture"])
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "execution-failed", "diagnostic": str(exc), "authorizes": []}, sort_keys=True))
        raise SystemExit(1)
    print(json.dumps(result, sort_keys=True))
