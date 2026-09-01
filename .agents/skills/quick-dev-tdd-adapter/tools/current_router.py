"""Current Q0-Q8 routing and deterministic lifecycle predicates."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
from typing import Any, Mapping, Sequence

TOOLS = Path(__file__).resolve().parent
import sys
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from runtime_evidence import HASH_RE, load_json, safe_relative, sha256_bytes, sha256_value

ACTIONS = (
    "run-preflight", "author-red", "run-red", "implement", "run-green",
    "run-refactor", "validate-slice", "run-terminal", "repair-vdd", "stop",
    "environment-blocked",
)
PROFILES = ("fast-ship", "standard", "self-hosted")


def _read_object(path: Path) -> dict[str, Any]:
    return load_json(path)


def _assert_hash(value: str, label: str) -> None:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise ValueError(f"{label} must be sha256")


def _slice(bundle: Mapping[str, Any], slice_id: str) -> Mapping[str, Any]:
    slices = bundle.get("slices")
    if not isinstance(slices, list):
        raise ValueError("semantic plan slices are missing")
    found = [item for item in slices if isinstance(item, Mapping) and item.get("slice_id") == slice_id]
    if len(found) != 1:
        raise ValueError("slice identity is missing or ambiguous")
    return found[0]


def probe_environment(workspace: Path) -> dict[str, Any]:
    root = workspace.resolve()
    py = shutil.which("py") or shutil.which("python")
    result: dict[str, Any] = {"repository_root": str(root), "launcher": py or "", "available": False}
    if not py:
        result["reason"] = "python launcher unavailable"
        return result
    commands = [[py, "-3", "--version"] if Path(py).name.lower().startswith("py") else [py, "--version"]]
    commands.append([py, "-3", "-m", "pytest", "--version"] if Path(py).name.lower().startswith("py") else [py, "-m", "pytest", "--version"])
    traces = []
    for argv in commands:
        try:
            proc = subprocess.run(argv, cwd=root, shell=False, text=True, capture_output=True, timeout=20, check=False)
        except OSError as exc:
            result["reason"] = str(exc)
            return result
        traces.append({"argv": argv, "exit_code": proc.returncode, "output": (proc.stdout or proc.stderr).strip()[:300]})
        if proc.returncode != 0:
            result["traces"] = traces
            result["reason"] = "python/pytest probe failed"
            return result
    result["available"] = True
    result["traces"] = traces
    return result


def validate_profile(profile: str) -> None:
    if profile not in PROFILES:
        raise ValueError("execution profile is invalid")


def recommendation(*, semantic_plan: Mapping[str, Any], slice_id: str, current_state: Mapping[str, Any], changed_paths: Sequence[str], profile: str) -> dict[str, Any]:
    validate_profile(profile)
    selected = _slice(semantic_plan, slice_id)
    for path in changed_paths:
        safe_relative(path)
    state = str(current_state.get("state") or "planned-only")
    invalidated = current_state.get("invalidated_observations", [])
    if not isinstance(invalidated, list):
        invalidated = []
    if any(path in set(selected.get("execution_snapshot_paths", [])) for path in changed_paths):
        action, reason = "run-red", "selector-or-fixture-changed"
    elif state == "planned-only":
        action, reason = "run-preflight", "plan-not-preflighted"
    elif state == "preflight-passed" and not current_state.get("red_descriptor_ref"):
        action, reason = "author-red", "red-not-materialized"
    elif state == "red-materialized":
        action, reason = "run-red", "red-not-observed"
    elif state == "red-observed":
        action, reason = "implement", "expected-red-required"
    elif state == "implementation-successor":
        action, reason = "run-green", "green-not-observed"
    elif state == "green-observed":
        action, reason = "run-refactor", "refactor-not-observed"
    elif state == "refactor-observed":
        action, reason = "validate-slice", "slice-not-ready"
    elif state == "slice-ready":
        action, reason = "run-terminal", "whole-plan-terminal-pending"
    elif state == "whole-plan-terminal":
        action, reason = "stop", "implementation-complete"
    else:
        action, reason = "repair-vdd", "unknown-or-invalid-lifecycle-state"
    return {
        "schema": "quick-dev.recommendation.v1",
        "plan_id": semantic_plan.get("plan_id"),
        "plan_hash": sha256_value(dict(semantic_plan)),
        "slice_id": slice_id,
        "profile": profile,
        "recommended_action": action,
        "forbidden_actions": [item for item in ACTIONS if item != action],
        "reason_code": reason,
        "blocked_by": [],
        "reusable_observations": list(current_state.get("reusable_observations", [])) if isinstance(current_state.get("reusable_observations", []), list) else [],
        "invalidated_observations": invalidated,
    }


def validate_preflight(*, workspace: Path, semantic_plan_path: Path, slice_id: str, candidate_hash: str, descriptor: Mapping[str, Any] | None, profile: str) -> dict[str, Any]:
    validate_profile(profile)
    _assert_hash(candidate_hash, "candidate_hash")
    bundle = _read_object(semantic_plan_path)
    selected = _slice(bundle, slice_id)
    errors: list[str] = []
    required_slice = ("acceptance_ids", "failure_intent_ids", "allowed_write_paths", "execution_snapshot_paths", "terminal_predicate")
    for key in required_slice:
        if key not in selected:
            errors.append(f"slice:{key}:missing")
    if descriptor is not None:
        if descriptor.get("shell") is not False:
            errors.append("descriptor:shell")
        argv = descriptor.get("argv")
        if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x for x in argv):
            errors.append("descriptor:argv")
        timeout = descriptor.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout <= 0:
            errors.append("descriptor:timeout")
        if descriptor.get("plan_id") != bundle.get("plan_id") or descriptor.get("slice_id") != slice_id:
            errors.append("descriptor:plan-slice-binding")
        if descriptor.get("candidate_hash") != candidate_hash:
            errors.append("descriptor:candidate-binding")
    environment = probe_environment(workspace)
    if not environment.get("available"):
        return {"status": "environment-blocked", "errors": errors, "environment": environment}
    return {"status": "preflight-passed" if not errors else "repair-vdd", "errors": errors, "environment": environment}


def failure_fingerprint(observation: Mapping[str, Any], selector_identity: str) -> str:
    material = {
        "selector_identity": selector_identity,
        "stage": observation.get("stage"),
        "verification_outcome": observation.get("verification_outcome"),
        "failure_family": observation.get("failure_family"),
        "failure_id": observation.get("failure_id"),
        "exit_code": observation.get("exit_code"),
        "timed_out": observation.get("timed_out"),
        "observed_failure_ids": observation.get("observed_failure_ids", []),
    }
    return sha256_value(material)


def stop_loss(previous_fingerprints: Sequence[str], current_fingerprint: str) -> dict[str, Any]:
    matches = 0
    for item in reversed(list(previous_fingerprints)):
        if item == current_fingerprint:
            matches += 1
        else:
            break
    if matches >= 1:
        return {"stop": True, "failure_family": "repeated-deterministic-failure", "action": "stop"}
    return {"stop": False, "failure_family": None, "action": "retry-after-input-change"}


def validate_write_delta(changed_paths: Sequence[str], allowed_paths: Sequence[str], forbidden_paths: Sequence[str] = ()) -> None:
    allowed = set(allowed_paths)
    forbidden = set(forbidden_paths)
    if not allowed:
        raise ValueError("production write set is empty")
    for path in changed_paths:
        normalized = safe_relative(path)
        if normalized in forbidden or normalized not in allowed:
            raise ValueError(f"write-set violation: {normalized}")


def recovered_run(prior: Mapping[str, Any], *, current_slice_id: str, current_hashes: Mapping[str, str]) -> dict[str, Any]:
    required = ("run_id", "slice_id", "receipt_ref", "receipt_sha256", "observation_ref", "observation_sha256", "runtime_edge_refs")
    if any(key not in prior for key in required):
        raise ValueError("recovery predecessor is incomplete")
    if prior.get("slice_id") != current_slice_id:
        raise ValueError("recovery slice mismatch")
    for key in ("receipt_sha256", "observation_sha256"):
        _assert_hash(str(prior.get(key) or ""), key)
    if not isinstance(prior.get("runtime_edge_refs"), list) or not prior["runtime_edge_refs"]:
        raise ValueError("recovery runtime edges are missing")
    for key, expected in current_hashes.items():
        if prior.get(key) != expected:
            raise ValueError(f"recovery stale identity: {key}")
    return {
        "schema": "quick-dev.recovered-run.v1",
        "evidence_state": "recovered-run",
        "source_run_id": prior["run_id"],
        "slice_id": current_slice_id,
        "receipt_ref": prior["receipt_ref"],
        "receipt_sha256": prior["receipt_sha256"],
        "observation_ref": prior["observation_ref"],
        "observation_sha256": prior["observation_sha256"],
        "runtime_edge_refs": list(prior["runtime_edge_refs"]),
        "verification_outcome": prior.get("verification_outcome", "incomplete"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--slice", dest="slice_id", required=True)
    parser.add_argument("--profile", default="standard", choices=PROFILES)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument("--recommendation-only", action="store_true")
    args = parser.parse_args()
    try:
        bundle = _read_object(args.plan / "semantic-plan-bundle.v1.json")
        state = _read_object(args.state) if args.state else {"state": "planned-only"}
        result = recommendation(semantic_plan=bundle, slice_id=args.slice_id, current_state=state, changed_paths=args.changed_path, profile=args.profile)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"recommended_action": "repair-vdd", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
