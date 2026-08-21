from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def publish_canonical_receipt(root: Path, plan: Path, result: dict[str, object]) -> Path:
    """Publish the immutable Quick Dev completion handoff for a passed terminal."""
    repair = plan / "repair" / "round-2"
    repair.mkdir(parents=True, exist_ok=True)
    manifest = build_candidate_source_manifest(root, _candidate_source_entries())
    binding = str(manifest["candidate_source_root"]).split(":", 1)[1][:16]
    manifest_path = repair / f"candidate-source-manifest.{binding}.v1.json"
    manifest_encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != manifest_encoded:
        raise RuntimeError("candidate source manifest successor conflicts")
    if not manifest_path.exists():
        manifest_path.write_text(manifest_encoded, encoding="utf-8", newline="\n")
    receipt = {
        "schema_version": "quick-dev-implementation-complete.v2",
        "plan_id": result["plan_id"],
        "repair_round": 2,
        "predicate": "implementation-complete",
        "status": "pass",
        "implementation_contract": {"path": "implementation-contract.v1.json", "sha256": result["contract_hash"]},
        "command_registry": {"path": "command-registry.v1.json", "sha256": result["command_registry_hash"]},
        "candidate_source_manifest": {"path": manifest_path.relative_to(plan).as_posix(), "sha256": _sha256(manifest_path.read_bytes()), "candidate_source_root": manifest["candidate_source_root"]},
        "terminal_result": {"path": "terminal-results/terminal-full.json", "sha256": result["terminal_result_hash"]},
        "validated_command_ids": result["validated_command_ids"],
        "authorizes": ["acceptance-handoff"],
    }
    destination = repair / f"quick-dev-implementation-complete.{binding}.v2.json"
    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if destination.is_file() and destination.read_text(encoding="utf-8") != encoded:
        raise RuntimeError("canonical implementation receipt successor conflicts")
    if not destination.is_file():
        destination.write_text(encoded, encoding="utf-8", newline="\n")
    return destination


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=False, capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git identity command failed")
    return result.stdout.strip()


def _is_generated_candidate_path(relative: str) -> bool:
    parts = relative.split("/")
    name = parts[-1]
    if parts[0] == "logs":
        return True
    if any(part.startswith(("skill-input", "semantic-input", "knowledge-context")) for part in parts):
        return True
    if name.startswith("95-") or name.startswith(("skill-input", "semantic-input", "knowledge-context")):
        return True
    if name in {"plan-state.v1.json", "resume-state.v1.json", "repair-closure.json"} or name.startswith("quick-dev-implementation-complete"):
        return True
    if name.startswith(("changed-set", "root-cause", "sibling-disposition", "composition", "producer-consumer-composition")):
        return True
    generated_dirs = {"terminal-results", "attempts", "pages", "sidecars", "knowledge-context.history", "knowledge-context.freeze.history"}
    return any(part in generated_dirs for part in parts)


def build_candidate_source_manifest(root: Path, entries: list[dict[str, object]]) -> dict[str, object]:
    """Build the portable candidate identity from declared source bytes only."""
    normalized: list[dict[str, object]] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "role", "slice_ids"}:
            raise ValueError("candidate source manifest entry is invalid")
        relative, role, slice_ids = entry["path"], entry["role"], entry["slice_ids"]
        if (not isinstance(relative, str) or not relative or _is_generated_candidate_path(relative)
                or not isinstance(role, str) or not role
                or not isinstance(slice_ids, list) or not slice_ids or any(not isinstance(value, str) or not value for value in slice_ids)):
            raise ValueError("candidate source manifest entry is invalid")
        source = (root / relative).resolve()
        try:
            source.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError("candidate source manifest path escapes root") from exc
        if not source.is_file():
            raise ValueError("candidate source manifest source is missing")
        normalized.append({"path": relative.replace("\\", "/"), "role": role, "slice_ids": sorted(slice_ids), "sha256": _sha256(source.read_bytes())})
    normalized.sort(key=lambda item: (str(item["path"]), str(item["role"]), tuple(item["slice_ids"])))
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"schema_version": "jimuyun.candidate-source-manifest.v1", "entries": normalized, "candidate_source_root": _sha256(payload)}


def _candidate_source_entries() -> list[dict[str, object]]:
    return [
        {"path": ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py", "role": "production", "slice_ids": ["R0"]},
        {"path": ".agents/skills/quick-dev-tdd-adapter/tools/loop_plan_directory.py", "role": "production", "slice_ids": ["R1"]},
        {"path": ".agents/skills/quick-dev-tdd-adapter/tools/knowledge_context.py", "role": "production", "slice_ids": ["R2"]},
        {"path": ".agents/skills/run-refactor-implementation-acceptance/scripts/knowledge_context.py", "role": "contract-consumer", "slice_ids": ["R2"]},
        {"path": ".agents/skills/run-refactor-implementation-acceptance/scripts/compact_vdd_projection.py", "role": "contract-consumer", "slice_ids": ["R5"]},
        {"path": "execution-plans/2026-08-18-acceptance-coordinator-trust-recovery/tools/terminal_full.py", "role": "validator", "slice_ids": ["R5"]},
        {"path": "execution-plans/2026-08-18-acceptance-coordinator-trust-recovery/tools/validate_all.py", "role": "validator", "slice_ids": ["R5"]},
        {"path": "execution-plans/2026-08-18-acceptance-coordinator-trust-recovery/tools/tests/test_completion_handoff_integrity.py", "role": "test", "slice_ids": ["R5"]},
        {"path": ".agents/skills/run-refactor-implementation-acceptance/tests/test_deterministic_finalization.py", "role": "test", "slice_ids": ["R5"]},
        {"path": "execution-plans/2026-08-18-acceptance-coordinator-trust-recovery/implementation-contract.v1.json", "role": "contract-consumer", "slice_ids": ["R0", "R1", "R2", "R3", "R4", "R5"]},
        {"path": "execution-plans/2026-08-18-acceptance-coordinator-trust-recovery/command-registry.v1.json", "role": "contract-consumer", "slice_ids": ["R0", "R1", "R2", "R3", "R4", "R5"]},
    ]


def _candidate_binding(root: Path, plan: Path | None = None) -> str:
    if plan is None:
        raise ValueError("candidate source manifest requires the target plan")
    return str(build_candidate_source_manifest(root, _candidate_source_entries())["candidate_source_root"])


def _run_registered_command(root: Path, registry: dict, command_id: str) -> int:
    command = next((item for item in registry.get("commands", []) if item.get("id") == command_id), None)
    if not isinstance(command, dict):
        return 127
    executable = command.get("executable")
    argv = command.get("argv")
    if not isinstance(executable, str) or not isinstance(argv, list) or any(not isinstance(value, str) for value in argv):
        return 127
    cwd_value = command.get("cwd", {"type": "repo_path", "value": "."})
    if isinstance(cwd_value, dict) and cwd_value.get("type") == "repo_path":
        cwd = (root / str(cwd_value.get("value", "."))).resolve()
    elif isinstance(cwd_value, str):
        cwd = (root / cwd_value).resolve()
    else:
        return 127
    try:
        cwd.relative_to(root)
    except ValueError:
        return 127
    completed = subprocess.run([executable, *argv], cwd=cwd, check=False)
    return completed.returncode


_SLICE_TESTS = {
    "R0": [".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_trust.py"],
    "R1": [".agents/skills/quick-dev-tdd-adapter/tools/tests/test_successor_crash_recovery.py"],
    "R2": [
        ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_authorization_refresh_chain.py",
        ".agents/skills/run-refactor-implementation-acceptance/tests/test_knowledge_degraded_execution.py",
    ],
    "R3": [".agents/skills/quick-dev-tdd-adapter/tools/tests/test_plan_directory_loop.py"],
    "R4": [".agents/skills/run-refactor-implementation-acceptance/tests/test_deterministic_finalization.py"],
    "R5": ["execution-plans/2026-08-18-acceptance-coordinator-trust-recovery/tools/tests/test_completion_handoff_integrity.py"],
}


def _selectors(slice_id: str | None) -> tuple[list[str], list[str]]:
    if slice_id is not None and slice_id not in _SLICE_TESTS:
        raise ValueError(f"unknown slice: {slice_id}")
    if slice_id:
        return list(_SLICE_TESTS[slice_id]), [f"{slice_id.lower()}-green"]
    selected = [selector for slice_tests in _SLICE_TESTS.values() for selector in slice_tests]
    return selected, [*(f"{slice_id.lower()}-green" for slice_id in _SLICE_TESTS), "quick-dev-suite", "acceptance-suite"]


def _final_bindings(root: Path, plan: Path) -> tuple[dict[str, str], list[str]]:
    required = (
        "implementation-contract.v1.json",
        "command-registry.v1.json",
        "authority-manifest.v1.json",
        "knowledge-context.v1.json",
        "knowledge-context.freeze.v1.json",
    )
    hashes: dict[str, str] = {}
    missing: list[str] = []
    for name in required:
        path = plan / name
        if not path.is_file():
            missing.append(name)
        else:
            hashes[name] = _sha256(path.read_bytes())
    receipt = _find_skill_input_receipt(plan, root)
    if receipt is None:
        missing.append("skill-input-receipt(.successor).v1.json")
    else:
        hashes[str(receipt.relative_to(root)).replace("\\", "/")] = _sha256(receipt.read_bytes())
        try:
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            if payload.get("ready") is not True or payload.get("authorizes") != []:
                missing.append("skill-input-receipt-not-ready-or-authorizing")
            expected_target = str(plan.relative_to(root)).replace("\\", "/")
            if payload.get("target") != expected_target:
                missing.append("skill-input-receipt-target-mismatch")
        except (OSError, ValueError):
            missing.append("skill-input-receipt-invalid-json")
    return hashes, missing


def _find_skill_input_receipt(plan: Path, root: Path | None = None) -> Path | None:
    resume = plan / "resume-state.v1.json"
    if root is not None and resume.is_file():
        try:
            pointer = json.loads(resume.read_text(encoding="utf-8")).get("skill_input_receipt")
            if isinstance(pointer, dict) and set(pointer) == {"path", "sha256"} and isinstance(pointer["path"], str):
                candidate = (root / pointer["path"]).resolve()
                candidate.relative_to(root.resolve())
                if candidate.is_file() and _sha256(candidate.read_bytes()) == pointer["sha256"]:
                    return candidate
        except (OSError, ValueError, json.JSONDecodeError):
            return None
    candidates: list[Path] = []
    for path in sorted(plan.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if payload.get("schema_version") == "skill-input-consumption.v1":
            candidates.append(path)
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: (path.stat().st_mtime_ns, path.as_posix()), reverse=True)[0]


def _skill_input_validation_failures(root: Path, plan: Path) -> list[str]:
    receipt = _find_skill_input_receipt(plan, root)
    if receipt is None:
        return ["skill-input-receipt-not-found"]
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["skill-input-receipt-invalid-json"]
    contracts = {
        "quick-dev-tdd-adapter": root / ".agents/skills/quick-dev-tdd-adapter/references/skill-input-contract.v1.json",
    }
    contract = contracts.get(payload.get("consumer"), receipt.parent / "contract.json")
    validator = root / "scripts/python/validate_skill_input_consumption.py"
    if not contract.is_file() or not validator.is_file():
        return ["skill-input-validator-or-contract-not-found"]
    completed = subprocess.run(
        [
            sys.executable,
            str(validator),
            str(receipt),
            "--repository-root",
            str(root),
            "--contract",
            str(contract),
            "--require-ready",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return [] if completed.returncode == 0 else ["skill-input-current-validation-failed"]


def _authorization_failures(root: Path, plan: Path) -> list[str]:
    candidates = sorted(plan.rglob("*authorization-receipt*.json"))
    if not candidates:
        return ["maintainer-authorization-receipt-required"]
    receipt = next((path for path in reversed(candidates) if "/repair/round-2/" in path.as_posix() and path.name.endswith(".v2.json")), candidates[-1])
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["maintainer-authorization-receipt-invalid"]
    failures: list[str] = []
    if payload.get("plan_id") != "acceptance-coordinator-trust-recovery":
        failures.append("maintainer-authorization-plan-mismatch")
    if payload.get("authorizes") != ["implementation-authorized"]:
        failures.append("maintainer-authorization-transition-mismatch")
    expected = {
        "implementation_contract": plan / "implementation-contract.v1.json",
        "authority_manifest": plan / "authority-manifest.v1.json",
        "knowledge_context_freeze": plan / "knowledge-context.freeze.v1.json",
    }
    for field, path in expected.items():
        descriptor = payload.get(field)
        if not isinstance(descriptor, dict) or descriptor.get("path") != str(path.relative_to(root)).replace("\\", "/"):
            failures.append(f"maintainer-authorization-{field}-path-mismatch")
        elif not path.is_file() or descriptor.get("sha256") != _sha256(path.read_bytes()):
            failures.append(f"maintainer-authorization-{field}-hash-mismatch")
    if payload.get("schema_version") == "jimuyun.quick-dev-implementation-authorization.v2":
        for field, path in {
            "command_registry": plan / "command-registry.v1.json",
            "skill_input_contract": root / ".agents/skills/quick-dev-tdd-adapter/references/skill-input-contract.v1.json",
        }.items():
            descriptor = payload.get(field)
            if not isinstance(descriptor, dict) or not path.is_file() or descriptor.get("sha256") != _sha256(path.read_bytes()):
                failures.append(f"maintainer-authorization-{field}-hash-mismatch")
    return failures


def _terminal_receipt_failures(plan: Path, *, full: bool) -> list[str]:
    if not full:
        return []
    failures: list[str] = []
    for slice_id in _SLICE_TESTS:
        path = plan / "terminal-results" / f"{slice_id}.json"
        if not path.is_file():
            failures.append(f"missing-terminal-receipt:{slice_id}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            failures.append(f"invalid-terminal-receipt:{slice_id}")
            continue
        if payload.get("predicate") != "slice-ready" or payload.get("authorizes") != []:
            failures.append(f"terminal-receipt-not-non-authorizing:{slice_id}")
    resume = plan / "resume-state.v1.json"
    if not resume.is_file():
        failures.append("resume-state-required")
    else:
        try:
            state = json.loads(resume.read_text(encoding="utf-8"))
            if state.get("plan_id") != "acceptance-coordinator-trust-recovery" or state.get("authorizes") != []:
                failures.append("resume-state-binding-invalid")
        except (OSError, ValueError):
            failures.append("resume-state-invalid")
    return failures


def _knowledge_failures(plan: Path) -> list[str]:
    context_path = plan / "knowledge-context.v1.json"
    if not context_path.is_file():
        return ["knowledge-context-missing"]
    try:
        context = json.loads(context_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["knowledge-context-invalid"]
    preflight = context.get("preflight", {})
    if not isinstance(preflight, dict):
        return ["knowledge-preflight-invalid"]
    failure_code = preflight.get("failure_code")
    catalog_failure = preflight.get("catalog_failure_code")
    source_refresh = context.get("source_refresh")
    failures: list[str] = []
    if failure_code and failure_code != "catalog_stale":
        failures.append("knowledge-semantic-review-required")
    if catalog_failure and catalog_failure != "catalog_stale":
        failures.append("knowledge-selection-drift-requires-review")
    if catalog_failure == "catalog_stale" and not isinstance(source_refresh, dict):
        failures.append("knowledge-successor-refresh-missing")
    return failures


def _authority_failures(plan: Path) -> list[str]:
    failures: list[str] = []
    state_path = plan / "plan-state.v1.json"
    if not state_path.is_file():
        return ["missing-plan-state"]
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["invalid-plan-state"]
    if state.get("status") == "implementation-authorized":
        if "implementation-authorized" not in state.get("authorizes", []):
            failures.append("implementation-authorization-not-published")
    elif state.get("status") == "implementation-complete":
        # A completed Quick Dev plan may be revalidated without reverting its
        # lifecycle owner to the maintainer authorization stage.
        if state.get("authorizes") != ["implementation-complete"]:
            failures.append("implementation-completion-state-invalid")
    else:
        failures.append("maintainer-implementation-authorization-required")
    freeze_path = plan / "knowledge-context.freeze.v1.json"
    context_path = plan / "knowledge-context.v1.json"
    if not freeze_path.is_file() or not context_path.is_file():
        failures.append("knowledge-freeze-or-context-missing")
    else:
        try:
            freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
            expected = freeze.get("context_sha256", "")
            actual = _sha256(context_path.read_bytes())
            if expected != actual:
                failures.append("knowledge-freeze-context-mismatch")
        except (OSError, ValueError):
            failures.append("knowledge-freeze-invalid-json")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--slice")
    args = parser.parse_args()

    root = args.repository_root.resolve()
    plan = args.plan_dir.resolve()
    if not root.is_dir() or not plan.is_dir():
        print(json.dumps({"status": "fail", "failures": ["repository-or-plan-directory-missing"]}))
        return 1
    contract_bytes = (plan / "implementation-contract.v1.json").read_bytes()
    registry_bytes = (plan / "command-registry.v1.json").read_bytes()
    contract = json.loads(contract_bytes.decode("utf-8"))
    registry = json.loads(registry_bytes.decode("utf-8"))
    try:
        selectors, command_ids = _selectors(args.slice)
    except ValueError as exc:
        print(json.dumps({"status": "fail", "failures": [str(exc)]}))
        return 1
    failures: list[str] = []
    binding_hashes: dict[str, str] = {}
    failures.extend(_authority_failures(plan))
    failures.extend(_authorization_failures(root, plan))
    failures.extend(_knowledge_failures(plan))
    failures.extend(_terminal_receipt_failures(plan, full=not args.slice))
    failures.extend(_skill_input_validation_failures(root, plan))
    if not args.slice:
        binding_hashes, missing = _final_bindings(root, plan)
        failures.extend(f"missing-binding:{name}" for name in missing)
    for command_id in command_ids:
        completed = _run_registered_command(root, registry, command_id)
        if completed:
            failures.append(f"command:{command_id}")

    passed = not failures
    predicate = "slice-ready" if args.slice else "implementation-complete"
    terminal_command_id = (
        f"{args.slice.lower()}-terminal" if args.slice else "terminal-full"
    )
    result = {
        "schema_version": "quick-dev-tdd-adapter.terminal-result.v1",
        "plan_id": contract["plan_id"],
        "predicate": predicate,
        "status": "pass" if passed else "fail",
        "terminal_command_id": terminal_command_id,
        "contract_hash": _sha256(contract_bytes),
        "command_registry_hash": _sha256(registry_bytes),
        "candidate_binding_hash": _candidate_binding(root, plan),
        "validated_command_ids": command_ids,
        "validated_selectors": selectors,
        "failures": failures,
        "binding_hashes": binding_hashes,
        "authorizes": [],
        "lifecycle_transition": "none",
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8", newline="\n")
    if passed and args.slice is None:
        result["terminal_result_hash"] = _sha256(encoded.encode("utf-8"))
        receipt_path = publish_canonical_receipt(root, plan, result)
        resume_path = plan / "resume-state.v1.json"
        resume = json.loads(resume_path.read_text(encoding="utf-8"))
        resume["status"] = "implementation-complete"
        resume["next_action"] = "acceptance-handoff"
        resume["current_slice"] = None
        resume["implementation_receipt"] = {"path": receipt_path.relative_to(plan).as_posix(), "sha256": _sha256(receipt_path.read_bytes()), "candidate_source_root": result["candidate_binding_hash"]}
        resume["slice_status"] = {slice_id: "slice-ready" for slice_id in _SLICE_TESTS}
        resume_path.write_text(json.dumps(resume, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        plan_state_path = plan / "plan-state.v1.json"
        plan_state = json.loads(plan_state_path.read_text(encoding="utf-8"))
        plan_state.update({"status": "implementation-complete", "owner": "quick-dev-tdd-adapter", "authorizes": ["implementation-complete"], "repair_round": "repair/round-2"})
        plan_state_path.write_text(json.dumps(plan_state, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(encoded, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
