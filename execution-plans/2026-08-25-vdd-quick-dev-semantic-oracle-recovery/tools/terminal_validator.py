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
    expected_slice_ids = {f"S{index}" for index in range(1, 6)}
    supplied_slice_ids = [item.get("slice_id") for item in supplied if isinstance(item, dict)] if isinstance(supplied, list) else []
    if (
        not isinstance(supplied, list)
        or len(supplied) != len(expected_slice_ids)
        or set(supplied_slice_ids) != expected_slice_ids
        or len(set(supplied_slice_ids)) != len(supplied_slice_ids)
    ):
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
    if destination.is_file():
        try:
            existing = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("existing terminal observation is invalid") from exc
        if existing != observation:
            raise ValueError("existing terminal observation is stale")
        return observation
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
    # The lifecycle runner freezes the exact predecessor results in this
    # run-local input.  Never infer lineage by scanning RUN-* directories:
    # historical retries are valid evidence but must not make selection
    # ambiguous or silently change the terminal candidate.
    lineage_path = s6_run / "terminal-lineage-input.v1.json"
    try:
        lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("explicit terminal lineage input is missing or invalid") from exc
    expected_ids = [f"S{index}" for index in range(1, 6)]
    supplied = lineage.get("entries") if isinstance(lineage, dict) else None
    if (
        lineage.get("schema_version") != "quick-dev-tdd-adapter.terminal-lineage-input.v1"
        or lineage.get("plan_id") != plan_id
        or lineage.get("slice_id") != "S6"
        or lineage.get("run_id") != s6_run.name
        or not isinstance(supplied, list)
        or [item.get("slice_id") for item in supplied if isinstance(item, dict)] != expected_ids
    ):
        raise ValueError("terminal lineage input identity is invalid")
    entries = []
    for item in supplied:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("run_id"), str)
            or not isinstance(item.get("result_path"), str)
            or not isinstance(item.get("result_sha256"), str)
        ):
            raise ValueError("terminal lineage entry is invalid")
        result = (root / item["result_path"]).resolve()
        try:
            result.relative_to(root / "logs" / "tdd-adapter")
        except ValueError as exc:
            raise ValueError("terminal lineage result escapes logs") from exc
        run = result.parent
        if (
            run.name != item["run_id"]
            or not run.name.startswith("RUN-")
            or "DIAGNOSTIC" in run.name.upper()
            or not result.is_file()
            or _sha(result) != item["result_sha256"]
        ):
            raise ValueError(f"terminal lineage result is stale: {item.get('slice_id')}")
        value = json.loads(result.read_text(encoding="utf-8"))
        if (
            value.get("status") != "pass"
            or value.get("predicate") != "slice-ready"
            or value.get("slice_id") != item["slice_id"]
            or value.get("run_id") != item["run_id"]
        ):
            raise ValueError(f"slice-ready result for {item.get('slice_id')} is invalid")
        entries.append({"slice_id": item["slice_id"], "run_id": run.name, "run_path": run.relative_to(root).as_posix(), "result_path": result.relative_to(root).as_posix(), "result_sha256": item["result_sha256"]})
    run = s6_run.resolve()
    result = run / "implementation-complete-result.json"
    # The terminal predicate writes this result after the manifest is frozen.
    # Hashing it here would make a replay change its own manifest and create a
    # circular, non-idempotent terminal contract. Validation binds the S6 run
    # path and independently validates the result instead.
    entries.append({"slice_id": "S6", "run_id": run.name, "run_path": run.relative_to(root).as_posix(), "result_path": result.relative_to(root).as_posix(), "result_sha256": None})
    value = {"schema_version": "quick-dev-tdd-adapter.terminal-lineage-manifest.v1", "plan_id": plan_id, "entries": entries, "authorizes": []}
    value["manifest_sha256"] = "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    output = s6_run / "terminal-lineage-manifest.v1.json"
    if output.is_file():
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("existing terminal lineage manifest is invalid") from exc
        if existing != value:
            raise ValueError("existing terminal lineage manifest is stale")
        return output
    _create(output, (json.dumps(value, sort_keys=True) + "\n").encode("utf-8"))
    return output


def _write(path: Path, value: dict[str, object]) -> None:
    body = {key: item for key, item in value.items() if key != "evidence_sha256"}
    value["evidence_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"existing evidence is invalid: {path.name}") from exc
        if existing != value:
            raise ValueError(f"existing evidence is stale: {path.name}")
        return
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
            # A preserved slice may have been resumed through prior-red
            # handoff. Resolve the immutable predecessor successor instead of
            # guessing from other RUN-* directories.
            prior = run / "prior-implementation-successor.v1.json"
            try:
                if prior.is_file():
                    reference = json.loads(prior.read_text(encoding="utf-8"))["receipt"]
                    candidate = (root / reference["path"]).resolve()
                    candidate.relative_to(root)
                    if not candidate.is_file() or _sha(candidate) != reference["sha256"]:
                        raise ValueError("prior implementation successor is stale")
                    receipt = candidate
                    receipt_ref = "prior-implementation-successor.v1.json"
                else:
                    handoff = json.loads((run / "prior-red-handoff.v2.json").read_text(encoding="utf-8"))
                    basis_ref = handoff["red_basis"]
                    basis = (root / basis_ref["path"]).resolve()
                    basis.relative_to(root)
                    predecessor = basis.parent
                    candidate = predecessor / "implementation-successor.v1.json"
                    if not candidate.is_file():
                        raise ValueError("predecessor implementation successor is missing")
                    # Materialize only a pointer in the continuation run;
                    # the immutable predecessor receipt remains the authority.
                    pointer = {
                        "schema_version": "quick-dev-tdd-adapter.prior-implementation-successor.v1",
                        "receipt": {"path": candidate.relative_to(root).as_posix(), "sha256": _sha(candidate)},
                    }
                    pointer_path = run / "prior-implementation-successor.v1.json"
                    if pointer_path.is_file():
                        existing = json.loads(pointer_path.read_text(encoding="utf-8"))
                        if existing != pointer:
                            raise ValueError("prior implementation successor pointer is stale")
                    else:
                        _create(pointer_path, (json.dumps(pointer, sort_keys=True) + "\n").encode("utf-8"))
                    receipt = candidate
                    receipt_ref = "prior-implementation-successor.v1.json"
            except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                raise ValueError("terminal replay predecessor receipt is invalid")
        if not observation.is_file():
            raise ValueError("terminal replay source is missing")
        observation_value = json.loads(observation.read_text(encoding="utf-8"))
        if (
            observation_value.get("stage") != "refactor"
            or observation_value.get("exit_code") != 0
            # Older lifecycle observations omitted run_id; the immutable
            # manifest already binds this file to the run directory. New
            # observations must still agree when the field is present.
            or observation_value.get("run_id") not in (None, entry["run_id"])
        ):
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
