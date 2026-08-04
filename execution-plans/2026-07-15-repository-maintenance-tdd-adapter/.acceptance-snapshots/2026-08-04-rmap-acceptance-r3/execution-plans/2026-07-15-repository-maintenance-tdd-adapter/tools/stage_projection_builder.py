from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_all import current_candidate_identity


def _hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _value_hash(value: Any) -> str:
    return _hash(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _head_bytes(root: Path, path: str) -> bytes | None:
    result = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=root, capture_output=True, check=False)
    return result.stdout if result.returncode == 0 else None


def build(root: Path, run_dir: Path, slice_id: str, paths: list[str], baseline_paths: list[str] | None = None) -> dict[str, Any]:
    """Build an explicit standard-slice projection from immutable Git bytes."""
    contract = json.loads((root / "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/implementation-contract.v1.json").read_text(encoding="utf-8"))
    slice_contract = next(item for item in contract["slices"] if item["slice_id"] == slice_id)
    allowed = {path.replace("\\", "/") for group in slice_contract["allowed_changes"].values() for path in group}
    if not paths or any(not any(path == pattern or pattern.endswith("/**") and path.startswith(pattern[:-2]) for pattern in allowed) for path in paths):
        raise ValueError("projection paths must be explicit members of the slice write set")
    effects, baseline = [], []
    for path in sorted(set(baseline_paths or paths), key=str.casefold):
        before = _head_bytes(root, path)
        if before is not None:
            baseline.append({"path": path, "sha256": _hash(before)})
    for path in sorted(set(paths), key=str.casefold):
        before, current = _head_bytes(root, path), (root / path).read_bytes() if (root / path).is_file() else None
        if before is None and current is None:
            raise ValueError(f"projection path is absent from both baseline and worktree: {path}")
        if before == current:
            continue
        change = "add" if before is None else "delete" if current is None else "modify"
        effects.append({"change_type": change, "baseline_path": None if change == "add" else path, "candidate_path": None if change == "delete" else path, "before_sha256": None if before is None else _hash(before), "after_sha256": None if current is None else _hash(current)})
    stage_hashes = {stage: _hash((run_dir / f"{stage}-result.json").read_bytes()) for stage in ("red", "green", "refactor")}
    document = {"schema_version": "jimuyun.stage-evidence-projection.v1", "plan_id": "repository-maintenance-tdd-adapter", "slice_id": slice_id, "run_id": run_dir.name, "baseline_files": baseline, "effects": effects, "stage_result_hashes": stage_hashes, "final_event_hash": stage_hashes["refactor"]}
    document["root_hash"] = _value_hash(document)
    return document


def _validate_protocol_binding(stage: str, binding: dict[str, Any] | None) -> dict[str, str] | None:
    if binding is None:
        return None
    required = {"stage_binding_id", "attempt_id", "decision_hash", "capsule_hash", "context_hash"}
    if set(binding) != required or binding.get("stage_binding_id") != f"STAGE-{stage.upper()}" or not isinstance(binding.get("attempt_id"), str):
        raise ValueError("protocol binding is invalid for the stage")
    hashes = ("decision_hash", "capsule_hash", "context_hash")
    if any(not isinstance(binding.get(key), str) or not binding[key].startswith("sha256:") or len(binding[key]) != 71 for key in hashes):
        raise ValueError("protocol binding hashes are invalid")
    return {key: binding[key] for key in sorted(required)}


def load_protocol_binding(bundle_path: Path, stage: str) -> dict[str, str]:
    """Load an explicit protocol bundle and derive one stage binding through the Skill adapter."""
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if not isinstance(bundle, dict):
        raise ValueError("protocol bundle file must contain a JSON object")
    root = Path(__file__).resolve().parents[3]
    adapter_path = root / ".agents/skills/quick-dev-tdd-adapter/tools/adapter.py"
    spec = importlib.util.spec_from_file_location("rmap_stage_adapter", adapter_path)
    if spec is None or spec.loader is None:
        raise ValueError("Skill adapter is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.compose_stage_binding(bundle, stage)


def write_stage_result(root: Path, run_dir: Path, slice_id: str, stage: str, command_ids: list[str], exit_code: int, observed_at: str, *, protocol_binding: dict[str, Any] | None = None) -> Path:
    """Append one contract-derived stage result after its registered command ran."""
    if stage not in {"red", "green", "refactor"}:
        raise ValueError("stage must be red, green, or refactor")
    try:
        timestamp = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be an ISO-8601 timestamp") from exc
    if timestamp.tzinfo is None:
        raise ValueError("observed_at must include a timezone")
    contract = json.loads((root / "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/implementation-contract.v1.json").read_text(encoding="utf-8"))
    slice_contract = next((item for item in contract["slices"] if item["slice_id"] == slice_id), None)
    if slice_contract is None:
        raise ValueError(f"unknown slice: {slice_id}")
    tdd = slice_contract["tdd"]
    if stage == "red":
        expected_commands = [tdd["red"]["command_id"]]
        if exit_code == 0:
            raise ValueError("RED evidence requires a nonzero exit")
    elif stage == "green":
        expected_commands = [tdd["green"]["command_id"]]
        if exit_code != 0:
            raise ValueError("GREEN evidence requires a zero exit")
    else:
        expected_commands = [item["command_id"] for item in tdd["refactor"]["invocations"]]
        if exit_code != 0:
            raise ValueError("REFACTOR evidence requires a zero exit")
    if command_ids != expected_commands:
        raise ValueError("stage command IDs do not match the slice contract")
    registry = json.loads((root / "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/command-registry.v1.json").read_text(encoding="utf-8"))
    registered = {item["id"] for item in registry["commands"]}
    if any(command_id not in registered for command_id in command_ids):
        raise ValueError("stage command is not registered")
    output = run_dir / f"{stage}-result.json"
    if output.exists():
        raise ValueError(f"stage result already exists: {output}")
    binding = _validate_protocol_binding(stage, protocol_binding)
    stages = ("red", "green", "refactor")
    index = stages.index(stage)
    predecessor = None
    if index:
        predecessor_path = run_dir / f"{stages[index - 1]}-result.json"
        if not predecessor_path.is_file():
            raise ValueError("prior stage result is required")
        predecessor = _hash(predecessor_path.read_bytes())
    identity = current_candidate_identity(slice_id)
    recovery_path = run_dir / "recovery-state.json"
    if stage == "red" and not recovery_path.exists():
        run_dir.mkdir(parents=True, exist_ok=True)
        recovery = {
            "schema_version": "rmap.recovery-state.v1", "run_id": run_dir.name, "state": "active",
            "contract_hash": identity["contract_hash"], "validator_hash": identity["validator_hash"],
            "predecessor_run_id": None, "supersedes_run_id": None,
        }
        recovery_path.write_text(json.dumps(recovery, indent=2) + "\n", encoding="utf-8", newline="\n")
    if not recovery_path.is_file():
        raise ValueError("recovery state is required before recording a non-RED stage")
    document: dict[str, Any] = {
        "schema_version": "rmap.tdd-stage-result.v1", "plan_id": "repository-maintenance-tdd-adapter",
        "slice_id": slice_id, "run_id": run_dir.name, "stage": stage,
        "status": {"red": "red-observed", "green": "green-observed", "refactor": "refactor-verified"}[stage],
        "command_id": command_ids[0], "exit_code": exit_code,
        "contract_hash": identity["contract_hash"], "validator_hash": identity["validator_hash"],
        "observed_at": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "predecessor_stage_hash": predecessor,
    }
    if stage == "red":
        document["test_selector"] = tdd["red"]["test_selector"]
        document["expected_failure_ids"] = tdd["red"]["expected_failure_ids"]
    if stage == "refactor":
        document["command_ids"] = command_ids
    if binding is not None:
        document.update(binding)
    run_dir.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--path", action="append")
    parser.add_argument("--baseline-path", action="append")
    parser.add_argument("--write-stage-result", action="store_true")
    parser.add_argument("--stage", choices=("red", "green", "refactor"))
    parser.add_argument("--command-id", action="append")
    parser.add_argument("--exit-code", type=int)
    parser.add_argument("--observed-at")
    parser.add_argument("--protocol-binding-file", type=Path)
    parser.add_argument("--protocol-bundle-file", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    if args.write_stage_result:
        if not args.stage or not args.command_id or args.exit_code is None or not args.observed_at:
            parser.error("--write-stage-result requires --stage, --command-id, --exit-code, and --observed-at")
        if args.protocol_binding_file is not None and args.protocol_bundle_file is not None:
            parser.error("protocol binding file and protocol bundle file are mutually exclusive")
        binding = None
        if args.protocol_bundle_file is not None:
            binding = load_protocol_binding(args.protocol_bundle_file, args.stage)
        elif args.protocol_binding_file is not None:
            value = json.loads(args.protocol_binding_file.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                parser.error("--protocol-binding-file must contain a JSON object")
            binding = value
        write_stage_result(root, args.run_dir, args.slice_id, args.stage, args.command_id, args.exit_code, args.observed_at, protocol_binding=binding)
        return 0
    if not args.path:
        parser.error("--path is required unless --write-stage-result is used")
    output = args.run_dir / "stage-evidence-projection.v1.json"
    output.write_text(json.dumps(build(root, args.run_dir, args.slice_id, args.path, args.baseline_path), indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
