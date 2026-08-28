"""Create a manifest-bound cross-slice terminal lineage without mtime selection."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_terminal_observation(plan_dir: Path, s6_run: Path) -> dict[str, object]:
    """Validate terminal inputs and record the observed S6 terminal probe."""
    if not s6_run.name.startswith("RUN-") or "DIAGNOSTIC" in s6_run.name.upper():
        raise ValueError("terminal run identity is invalid")
    root = plan_dir.resolve().parents[1]
    contract = plan_dir / "implementation-contract.v1.json"
    registry = plan_dir / "command-registry.v1.json"
    authority = plan_dir / "knowledge-context.freeze.v1.json"
    for required in (contract, registry, authority):
        if not required.is_file():
            raise ValueError("terminal authority input is missing")
    lineage_input = s6_run / "terminal-lineage-input.v1.json"
    if not lineage_input.is_file():
        raise ValueError("explicit terminal lineage input is missing")
    lineage = json.loads(lineage_input.read_text(encoding="utf-8"))
    expected_plan_id = json.loads(contract.read_text(encoding="utf-8"))["plan_id"]
    if lineage.get("schema_version") != "quick-dev-tdd-adapter.terminal-lineage-input.v1" or lineage.get("plan_id") != expected_plan_id or lineage.get("slice_id") != "S6" or lineage.get("run_id") != s6_run.name:
        raise ValueError("terminal lineage input identity is invalid")
    supplied = lineage.get("entries")
    if not isinstance(supplied, list) or {item.get("slice_id") for item in supplied if isinstance(item, dict)} != {f"S{index}" for index in range(1, 6)}:
        raise ValueError("terminal lineage input must name S1-S5 exactly")
    entries = []
    for item in supplied:
        if not isinstance(item, dict) or not isinstance(item.get("result_path"), str) or not isinstance(item.get("result_sha256"), str):
            raise ValueError("terminal lineage entry is invalid")
        result = (root / item["result_path"]).resolve()
        result.relative_to(root / "logs" / "tdd-adapter")
        if not result.is_file() or _sha(result) != item["result_sha256"]:
            raise ValueError(f"terminal lineage result is stale: {item.get('slice_id')}")
        candidates = [result.parent]
        value = json.loads(result.read_text(encoding="utf-8"))
        if value.get("status") != "pass" or value.get("predicate") != "slice-ready" or value.get("slice_id") != item.get("slice_id") or value.get("run_id") != item.get("run_id") or value.get("run_id") != candidates[0].name:
            raise ValueError(f"slice-ready result for {item.get('slice_id')} is invalid")
        entries.append({"slice_id": item["slice_id"], "run_id": item["run_id"], "result_sha256": _sha(result)})
    payload = {"plan_id": json.loads(contract.read_text(encoding="utf-8"))["plan_id"], "slice_id": "S6", "run_id": s6_run.name, "entries": entries, "contract_hash": _sha(contract), "registry_hash": _sha(registry), "authority_hash": _sha(authority)}
    fingerprint = "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    observation = {"stage": "terminal", "run_id": s6_run.name, "command_id": "s6-terminal", "exit_code": 0, "execution_fingerprint": fingerprint, "inputs_hash": fingerprint}
    destination = s6_run / "observations" / "terminal-observed.json"
    _create(destination, (json.dumps(observation, sort_keys=True) + "\n").encode("utf-8"))
    return observation


def _create(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError(f"terminal evidence already exists: {path.name}")
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
        os.replace(temporary, path)
    except FileExistsError as exc:
        raise ValueError("terminal evidence write raced") from exc
    finally:
        if temporary.exists():
            temporary.unlink()


def write_manifest(plan_dir: Path, s6_run: Path) -> Path:
    root = plan_dir.resolve().parents[1]
    plan_id = json.loads((plan_dir / "implementation-contract.v1.json").read_text(encoding="utf-8"))["plan_id"]
    entries = []
    for index in range(1, 7):
        slice_id = f"S{index}"
        if slice_id == "S6":
            run = s6_run.resolve()
        else:
            base = root / "logs" / "tdd-adapter" / plan_id / slice_id
            candidates = [
                path for path in base.glob("RUN-*") if path.is_dir() and "DIAGNOSTIC" not in path.name.upper()
                and (path / "slice-ready-result.json").is_file()
            ]
            if len(candidates) != 1:
                raise ValueError(f"terminal lineage for {slice_id} is ambiguous or missing")
            run = candidates[0]
        result = run / ("implementation-complete-result.json" if slice_id == "S6" else "slice-ready-result.json")
        entries.append({"slice_id": slice_id, "run_id": run.name, "run_path": run.relative_to(root).as_posix(), "result_path": result.relative_to(root).as_posix(), "result_sha256": _sha(result) if result.is_file() else None})
    value = {"schema_version": "quick-dev-tdd-adapter.terminal-lineage-manifest.v1", "plan_id": plan_id, "entries": entries, "authorizes": []}
    value["manifest_sha256"] = "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    output = s6_run / "terminal-lineage-manifest.v1.json"
    _create(output, (json.dumps(value, sort_keys=True) + "\n").encode("utf-8"))
    return output


def _write(path: Path, value: dict[str, object]) -> None:
    body = {key: item for key, item in value.items() if key != "evidence_sha256"}
    value["evidence_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    _create(path, (json.dumps(value, sort_keys=True) + "\n").encode("utf-8"))


def publish_terminal_evidence(plan_dir: Path, s6_run: Path) -> None:
    """Append terminal replay evidence derived from explicit lifecycle facts."""
    terminal_observation = s6_run / "observations" / "terminal-observed.json"
    if not terminal_observation.is_file():
        raise ValueError("terminal observation is missing")
    try:
        observed = json.loads(terminal_observation.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("terminal observation is invalid") from exc
    if (
        not isinstance(observed, dict)
        or observed.get("stage") != "terminal"
        or observed.get("run_id") != s6_run.name
        or observed.get("exit_code") != 0
        or not isinstance(observed.get("command_id"), str)
        or observed.get("command_id") != "s6-terminal"
        or not isinstance(observed.get("execution_fingerprint"), str)
        or not observed.get("execution_fingerprint")
    ):
        raise ValueError("terminal observation is not a successful S6 terminal command")
    manifest_path = write_manifest(plan_dir, s6_run)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = plan_dir.resolve().parents[1]
    import importlib.util
    spec = importlib.util.spec_from_file_location("terminal_identity", plan_dir / "tools" / "validate_all.py")
    if spec is None or spec.loader is None:
        raise ValueError("terminal identity validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    identity = module.current_candidate_identity("S6")
    contract_hash = _sha(plan_dir / "implementation-contract.v1.json")
    registry_path = plan_dir / "command-registry.v1.json"
    if not registry_path.is_file():
        raise ValueError("terminal command registry is missing")
    registry_hash = _sha(registry_path)
    acceptance = {
        "S1": ["A-SEMANTIC"], "S2": ["A-DESCRIPTOR"], "S3": ["A-JUDGE"],
        "S4": ["A-COVER"], "S5": ["A-PROMOTION"], "S6": ["A-TERMINAL", "A-BOUNDARY"],
    }
    prepared = []
    for entry in manifest["entries"]:
        run = (root / entry["run_path"]).resolve()
        observation = run / "observations" / "refactor-observed.json"
        receipt = run / "implementation-successor.v1.json"
        receipt_ref = "implementation-successor.v1.json"
        if not receipt.is_file():
            prior = run / "prior-implementation-successor.v1.json"
            try:
                reference = json.loads(prior.read_text(encoding="utf-8"))["receipt"]
                candidate = (root / reference["path"]).resolve()
                candidate.relative_to(root)
                if not candidate.is_file() or _sha(candidate) != reference["sha256"]:
                    raise ValueError("prior implementation successor is stale")
                receipt = prior
                receipt_ref = "prior-implementation-successor.v1.json"
            except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                raise ValueError("terminal replay predecessor receipt is invalid")
        if not observation.is_file():
            raise ValueError("terminal replay source is missing")
        observation_value = json.loads(observation.read_text(encoding="utf-8"))
        if observation_value.get("stage") != "refactor" or observation_value.get("exit_code") != 0 or observation_value.get("run_id") != entry["run_id"]:
            raise ValueError("terminal replay observation is not a successful refactor")
        slice_id = entry["slice_id"]
        evidence = {
            "status": "pass", "producer": "terminal-validator", "plan_id": manifest["plan_id"],
            "slice_id": slice_id, "run_id": entry["run_id"], "candidate_hash": identity["candidate_hash"],
            "contract_hash": contract_hash, "registry_hash": registry_hash,
            "authority_hash": identity["authority_root"], "observation_ref": "observations/refactor-observed.json",
            "receipt_ref": receipt_ref, "acceptance_ids": acceptance[slice_id],
        }
        prepared.append((run, evidence, {"status": "pass", "producer": "terminal-validator", "plan_id": manifest["plan_id"], "slice_id": slice_id, "run_id": entry["run_id"], "evidence_ref": "terminal-evidence.json"}))
    for run, evidence, replay in prepared:
        _write(run / "terminal-evidence.json", evidence)
        _write(run / "terminal-replay-report.json", replay)
