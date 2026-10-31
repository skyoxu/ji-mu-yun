"""ADR-0041: content-addressed execution originals and non-executing uses.

The index is an exact content key, never a latest-success/history scan. A use
retains the original report identity and rechecks its original bytes at closure.
"""
from copy import deepcopy
import importlib.metadata
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig

from runtime_evidence import (create_json, create_immutable, load_json,
                              sha256_bytes, sha256_value, resolve_file, hash_refs)
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
from execution_environment import execution_environment, ENVIRONMENT_SCHEMA

SCHEMA = "quick-dev.shared-execution.v1"
EXCLUDED = {"logs", "execution-plans"}


def environment_identity():
    files = set()
    packages = []
    for dist in importlib.metadata.distributions():
        listed = dist.files
        if listed is None:
            raise ValueError("reuse-environment-unknown: distribution has no file inventory")
        packages.append((dist.metadata.get("Name", ""), dist.version))
        # Hash installed bytes, not merely version strings or RECORD claims.
        for relative in listed:
            path = Path(dist.locate_file(relative))
            if path.suffix not in {".pyc", ".pyo"} and path.is_file():
                files.add(path.resolve())
    stdlib = Path(sysconfig.get_path("stdlib"))
    for directory, children, names in os.walk(stdlib):
        children[:] = [name for name in children if name not in {"site-packages", "__pycache__"}]
        files.update((Path(directory) / name).resolve() for name in names if Path(name).suffix in {".py", ".so", ".pyd", ".dll", ".zip"})
    files.add(Path(sys.executable).resolve())
    # Common child tool entrypoints are content-bound, without invoking them.
    for name in ("git", "dotnet", "node", "npm", "codex", "uv", "pwsh", "bash"):
        found = shutil.which(name)
        if found:
            files.add(Path(found).resolve())
    size, hashes = 0, {}
    if len(files) > 50000:
        raise ValueError("reuse-environment-budget-exceeded: files")
    for path in sorted(files):
        size += path.stat().st_size
        if size > 2 * 1024 * 1024 * 1024:
            raise ValueError("reuse-environment-budget-exceeded: bytes")
        hashes[str(path)] = sha256_bytes(path.read_bytes())
    # Values are hashed, never persisted (the inherited environment may contain secrets).
    return {"schema": ENVIRONMENT_SCHEMA,
            "system": platform.system(), "release": platform.release(), "machine": platform.machine(),
            "python": sys.version, "executable": str(Path(sys.executable).resolve()),
            "files": hashes, "installed_content": sha256_value(hashes), "packages": sha256_value(sorted(packages)),
            "environment": sha256_value(execution_environment())}


def command_identity(argv):
    argv = list(argv)
    if "-m" not in argv or argv[argv.index("-m") + 1:argv.index("-m") + 2] != ["pytest"]:
        raise ValueError("reuse-unsupported-command: Python pytest required")
    resolved = shutil.which(argv[0])
    if resolved is None or Path(resolved).resolve() != Path(sys.executable).resolve():
        raise ValueError("reuse-unknown-interpreter")
    # Preserve all Python flags, pytest selectors, options and their order.
    return [str(Path(resolved).resolve()), *argv[1:]]


def semantic_identity(bundle):
    # These top-level provenance fields are not semantic inputs. All other
    # fields, including the complete frozen contracts and dependencies, remain.
    return sha256_value({k: v for k, v in bundle.items()
                         if k not in {"source_commit", "baseline_commit"}})


def slice_identity(bundle, slice_id):
    row = next(s for s in bundle["slices"] if s["slice_id"] == slice_id)
    return sha256_value({"slice": row, "contract": semantic_identity(bundle)})


def input_manifest(workspace, bundle, descriptor):
    root = workspace.resolve()
    command_identity(descriptor["argv"])
    proc = subprocess.run(["git", "ls-files", "-z", "--cached", "--others"],
                          cwd=root, capture_output=True, check=False, timeout=30)
    if proc.returncode or not (root / ".git").exists():
        raise ValueError("reuse-dependency-scope-unknown: Git inventory required")
    paths = {p for p in proc.stdout.decode("utf-8").split("\0") if p
             and Path(p).parts[0] not in EXCLUDED and not {"__pycache__", ".pytest_cache", ".venv", "venv"} & set(Path(p).parts)
             and Path(p).suffix not in {".pyc", ".pyo"}}
    # Plans/evidence are excluded from automatic inventory to avoid self-invalidating
    # execution. Explicit production/test/fixture dependencies there are still bound.
    for row in bundle.get("slices", []):
        for key in ("production_owners", "allowed_write_paths", "execution_snapshot_paths"):
            paths.update(row.get(key, []))
    paths.update(descriptor["target_refs"])
    paths.update(descriptor["fixture_refs"])
    hashes, size = {}, 0
    if len(paths) > 50000:
        raise ValueError("reuse-dependency-budget-exceeded: file count")
    for relative in sorted(paths):
        path = root / relative
        if path.is_symlink():
            raise ValueError("reuse-dependency-unsafe: " + relative)
        if not path.exists():
            hashes[relative] = None
            continue
        if not path.is_file():
            raise ValueError("reuse-dependency-scope-unknown: " + relative)
        path = resolve_file(root, relative)
        size += path.stat().st_size
        if size > 512 * 1024 * 1024:
            raise ValueError("reuse-dependency-budget-exceeded: bytes")
        hashes[relative] = {"sha256": sha256_bytes(path.read_bytes()), "executable": bool(path.stat().st_mode & 0o111)}
    engine = {p.name: sha256_bytes(p.read_bytes()) for p in Path(__file__).parent.glob("*.py")}
    engine["workflow_unit_budget.py"] = sha256_bytes((Path(__file__).resolve().parents[4] / "scripts/workflow_unit_budget.py").read_bytes())
    return {"schema": SCHEMA, "files": hashes, "engine": engine,
            "environment": environment_identity(), "contract": semantic_identity(bundle),
            "argv": command_identity(descriptor["argv"]), "cwd": descriptor["cwd"]}


def invalidation_reason(original, current):
    # Aggregate-only historical hashes cannot be converted to the new filter.
    # Compare the rule before accepting even an accidentally equal digest.
    for manifest in (original, current):
        environment = manifest.get("environment")
        if not isinstance(environment, dict) or environment.get("schema") != ENVIRONMENT_SCHEMA:
            return "reuse-environment-schema-incompatible"
    for key in ("argv", "cwd", "contract", "engine", "environment"):
        if original.get(key) != current.get(key):
            if key == "environment":
                old, new = original.get(key, {}), current.get(key, {})
                changed = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
                return "reuse-environment-changed:" + ",".join(changed)
            return "reuse-" + key + "-changed"
    old, new = original.get("files", {}), current.get("files", {})
    changed = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
    if changed:
        return "reuse-dependency-content-changed:" + ",".join(changed[:10])
    return None


def admissible(receipt):
    report = receipt.get("case_report")
    if (receipt.get("schema") != "quick-dev.process-receipt.v2"
            or receipt.get("exit_code") != 0 or receipt.get("timed_out") is not False
            or receipt.get("pre_execution_error_code") or receipt.get("repo_noise_paths")
            or receipt.get("output_budget_exhausted") or receipt.get("case_report_error")
            or not isinstance(report, dict) or not report.get("selected")
            or report.get("complete") is not True or report.get("errors") != []
            or report.get("exit_code") != 0
            or receipt.get("case_report_sha256") != sha256_value(report)):
        raise ValueError("reuse-unsuccessful-or-incomplete-execution")
    selected = report["selected"]
    if len(set(selected)) != len(selected) or not set(selected) <= set(report.get("collected", {})):
        raise ValueError("reuse-selection-invalid")
    events = report.get("events", [])
    phases = {(e["node_id"], e["phase"]): e for e in events}
    if len(phases) != len(events):
        raise ValueError("reuse-ambiguous-case-attempt")
    for node in selected:
        for phase in ("setup", "call", "teardown"):
            e = phases.get((node, phase), {})
            if e.get("outcome") != "passed" or e.get("xfail") is not False:
                raise ValueError("reuse-case-not-passed: " + node)


def validate_observed_dependencies(workspace, manifest, receipt):
    errors = receipt.get("case_report", {}).get("dependency_errors")
    if errors != []:
        raise ValueError("reuse-dependency-observation-incomplete:" + str(errors))
    observed = receipt.get("case_report", {}).get("dependency_files")
    if not isinstance(observed, dict) or not observed:
        raise ValueError("reuse-observed-dependencies-missing")
    root = workspace.resolve()
    for raw, digest in observed.items():
        path = Path(raw)
        expected = manifest["environment"]["files"].get(raw)
        try:
            relative = path.relative_to(root).as_posix()
            expected = (manifest["files"].get(relative) or {}).get("sha256")
        except ValueError:
            if path.parent == Path(__file__).resolve().parent:
                expected = manifest["engine"].get(path.name)
        if expected != digest:
            raise ValueError("reuse-unbound-read-or-import:" + raw)


def _read_original(reference):
    """Validate immutable original bytes without rewriting any execution identity."""
    root = Path(reference["workspace"])
    index = load_json(resolve_file(root, reference["index_ref"]))
    if sha256_value(index) != reference["index_sha256"] or index.get("schema") != SCHEMA:
        raise ValueError("reuse-original-index-tampered")
    original = {}
    for name, binding in index["artifacts"].items():
        path = resolve_file(root, binding["path"])
        if sha256_bytes(path.read_bytes()) != binding["sha256"]:
            raise ValueError("reuse-original-tampered: " + name)
        original[name] = path
    receipt = load_json(original["receipt"])
    descriptor = load_json(original["descriptor"])
    if receipt.get("descriptor_sha256") != sha256_value(descriptor):
        raise ValueError("reuse-original-descriptor-mismatch")
    report = receipt.get("case_report", {})
    if any(report.get(k) != v for k, v in {
        "descriptor_sha256": sha256_value(descriptor), "run_id": descriptor["run_id"],
        "stage": descriptor["stage"]}.items()):
        raise ValueError("reuse-original-report-identity-mismatch")
    for name in ("stdout", "stderr"):
        if sha256_bytes(original[name].read_bytes()) != receipt[name + "_sha256"]:
            raise ValueError("reuse-original-output-mismatch")
    if receipt.get("process_attempts") != 1 or receipt.get("execution_reference") is not None:
        raise ValueError("reuse-original-is-not-an-execution")
    admissible(receipt)
    validate_observed_dependencies(root, index["input"], receipt)
    return index, receipt, descriptor


def read_original(reference):
    try:
        return _read_original(reference)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("reuse-original-invalid: " + str(exc)) from exc


def _consumption_reason(before, after, bundle, descriptor, *, historical_green=False):
    if historical_green:
        if descriptor.get("stage") != "green":
            raise ValueError("reuse-historical-predecessor-must-be-green")
        selected = [s for s in bundle["slices"] if s["slice_id"] == descriptor["slice_id"]]
        if len(selected) != 1:
            raise ValueError("reuse-historical-predecessor-slice-invalid")
        after = deepcopy(after)
        # GREEN is an immutable TDD predecessor, not a claim that its old
        # production bytes are the final candidate. Only declared production
        # owners may differ; engine, environment, tests, dependencies and
        # semantic inputs retain ordinary fail-closed freshness checks.
        for path in selected[0].get("production_owners", []):
            old = before.get("files", {}).get(path)
            new = after.get("files", {}).get(path)
            if isinstance(old, dict) and isinstance(new, dict):
                after["files"][path] = {**new, "sha256": old["sha256"]}
    return invalidation_reason(before, after)


def validate_use(descriptor, receipt, *, current=True, historical_green=False):
    reference = receipt["execution_reference"]
    index, original, original_descriptor = read_original(reference)
    if receipt.get("process_attempts") != 0 or receipt.get("execution_kind") != "reference":
        raise ValueError("reuse-reference-is-not-an-execution")
    for key in ("case_report", "case_report_sha256", "stdout_sha256", "stderr_sha256",
                "exit_code", "timed_out", "cases", "test_executions", "elapsed_seconds"):
        if receipt.get(key) != original.get(key):
            raise ValueError("reuse-reference-projection-tampered: " + key)
    if command_identity(descriptor["argv"]) != index["input"]["argv"] or descriptor["cwd"] != index["input"]["cwd"]:
        raise ValueError("reuse-selector-not-covered")
    if original.get("elapsed_seconds") is None or original["elapsed_seconds"] > descriptor["timeout_seconds"]:
        raise ValueError("reuse-exceeds-requested-budget")
    root = Path(reference["workspace"])
    bundle = load_json(resolve_file(root, reference["semantic_plan"]))
    if slice_identity(bundle, descriptor["slice_id"]) != reference["slice_semantic_sha256"]:
        raise ValueError("reuse-slice-semantics-changed")
    if current:
        reason = _consumption_reason(index["input"], input_manifest(root, bundle, descriptor),
                                     bundle, descriptor, historical_green=historical_green)
        if reason:
            raise ValueError(reason)
    for key, refs in (("target_hashes", "target_refs"), ("fixture_hashes", "fixture_refs")):
        if receipt.get(key) != hash_refs(root, descriptor[refs]):
            raise ValueError("reuse-current-target-or-fixture-changed")
    return original_descriptor


def _reference(root, path, index, semantic_plan, bundle, descriptor):
    return {"workspace": str(root), "index_ref": path.relative_to(root).as_posix(),
            "index_sha256": sha256_value(index),
            "semantic_plan": semantic_plan.resolve().relative_to(root).as_posix(),
            "slice_semantic_sha256": slice_identity(bundle, descriptor["slice_id"])}


def execute_with_reuse(*, workspace, bundle, semantic_plan, run_dir, descriptor, profile):
    from process_executor_v2 import execute_process
    root = workspace.resolve()
    evidence = run_dir / "canonical-evidence" / descriptor["stage"]
    reason = "reuse-stage-ineligible"
    manifest = None
    if descriptor["stage"] in {"green", "refactor", "regression", "terminal"}:
        try:
            manifest = input_manifest(root, bundle, descriptor)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            reason = str(exc)
    request = {"descriptor_sha256": sha256_value(descriptor), "input": manifest, "profile": profile,
               "semantic_plan": semantic_plan.resolve().relative_to(root).as_posix()}
    request_path = evidence / "reuse-request.v1.json"
    complete_path = evidence / "reuse-complete.v1.json"
    receipt_path = evidence / "process-receipt.v2.json"
    if receipt_path.exists() or request_path.exists():
        if manifest is None:
            raise ValueError("reuse-reentry-unbound: use explicit recovery")
        if load_json(request_path) != request:
            raise ValueError("reuse-reentry-input-changed")
        receipt = load_json(receipt_path)
        if load_json(complete_path) != {"receipt_sha256": sha256_value(receipt), "request_sha256": sha256_value(request)}:
            raise ValueError("reuse-reentry-incomplete-or-tampered")
        for name in ("stdout", "stderr"):
            if sha256_bytes((evidence / (name + ".bin")).read_bytes()) != receipt[name + "_sha256"]:
                raise ValueError("reuse-reentry-output-changed")
        if receipt.get("execution_reference"):
            validate_use(descriptor, receipt)
        return receipt
    create_json(request_path, request)
    def finish(receipt):
        create_json(complete_path, {"receipt_sha256": sha256_value(receipt), "request_sha256": sha256_value(request)})
        return receipt
    if manifest is not None:
        key = sha256_value(manifest)[7:]
        path = root / "logs/quick-dev-shared-executions" / (key + ".json")
        if path.exists():
            index = load_json(path)
            reference = _reference(root, path, index, semantic_plan, bundle, descriptor)
            _, original, _ = read_original(reference)
            receipt = deepcopy(original)
            receipt.update(stage=descriptor["stage"], descriptor_sha256=sha256_value(descriptor),
                           candidate_hash=descriptor["candidate_hash"], argv=descriptor["argv"],
                           cwd=descriptor["cwd"], process_attempts=0, execution_kind="reference",
                           execution_reference=reference, target_hashes=hash_refs(root, descriptor["target_refs"]),
                           fixture_hashes=hash_refs(root, descriptor["fixture_refs"]), profile_identity=profile)
            validate_use(descriptor, receipt)
            # Actual collected/selected case coverage is checked again by the judge.
            for name in ("stdout", "stderr"):
                source = resolve_file(root, index["artifacts"][name]["path"])
                create_immutable(evidence / (name + ".bin"), source.read_bytes())
            create_json(evidence / "process-receipt.v2.json", receipt)
            return finish(receipt)
        reason = "reuse-no-matching-content-key"
    receipt = execute_process(workspace, run_dir, descriptor["stage"], descriptor, profile_identity=profile)
    create_json(evidence / "reuse-decision.v1.json", {"reason": reason, "execution_kind": "executed"})
    if manifest is not None:
        try:
            admissible(receipt)
            validate_observed_dependencies(root, manifest, receipt)
            after = input_manifest(root, bundle, descriptor)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            create_json(evidence / "reuse-publication.v1.json", {"published": False, "reason": str(exc)})
            return finish(receipt)
        if after != manifest:
            create_json(evidence / "reuse-publication.v1.json", {"published": False, "reason": invalidation_reason(manifest, after)})
            return finish(receipt)
        original_descriptor = evidence / "original-descriptor.json"
        create_json(original_descriptor, descriptor)
        artifacts = {}
        for name, item in (("descriptor", original_descriptor), ("receipt", evidence / "process-receipt.v2.json"),
                           ("stdout", evidence / "stdout.bin"), ("stderr", evidence / "stderr.bin")):
            artifacts[name] = {"path": item.resolve().relative_to(root).as_posix(),
                               "sha256": sha256_bytes(item.read_bytes())}
        create_json(path, {"schema": SCHEMA, "input": manifest, "artifacts": artifacts})
    return finish(receipt)


def validate_saved_request(workspace, evidence, descriptor, receipt, *, historical_green=False):
    """Validate new original/use input seals at reentry and Q7/Q8 consumption."""
    path = evidence / "reuse-request.v1.json"
    if not path.exists():
        if receipt.get("execution_reference"):
            raise ValueError("reuse-request-missing")
        return  # Historical non-shared evidence retains its existing gates.
    request = load_json(path)
    if (request.get("descriptor_sha256") != sha256_value(descriptor)
            or request.get("profile") != receipt.get("profile_identity")):
        raise ValueError("reuse-request-identity-changed")
    if load_json(evidence / "reuse-complete.v1.json") != {
            "receipt_sha256": sha256_value(receipt), "request_sha256": sha256_value(request)}:
        raise ValueError("reuse-request-incomplete-or-tampered")
    if request.get("input") is not None:
        bundle = load_json(resolve_file(workspace, request["semantic_plan"]))
        reason = _consumption_reason(request["input"], input_manifest(workspace, bundle, descriptor),
                                     bundle, descriptor, historical_green=historical_green)
        if reason:
            raise ValueError(reason)
    if receipt.get("execution_reference"):
        validate_use(descriptor, receipt, historical_green=historical_green)
