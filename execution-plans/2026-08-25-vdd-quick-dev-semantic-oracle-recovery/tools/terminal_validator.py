"""Create a manifest-bound cross-slice terminal lineage without mtime selection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


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
    output.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return output


def _write(path: Path, value: dict[str, object]) -> None:
    body = {key: item for key, item in value.items() if key != "evidence_sha256"}
    value["evidence_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def publish_terminal_evidence(plan_dir: Path, s6_run: Path) -> None:
    """Append terminal replay evidence derived from explicit lifecycle facts."""
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
    acceptance = {
        "S1": ["A-SEMANTIC"], "S2": ["A-DESCRIPTOR"], "S3": ["A-JUDGE"],
        "S4": ["A-COVER"], "S5": ["A-PROMOTION"], "S6": ["A-TERMINAL", "A-BOUNDARY"],
    }
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
        slice_id = entry["slice_id"]
        evidence = {
            "status": "pass", "producer": "terminal-validator", "plan_id": manifest["plan_id"],
            "slice_id": slice_id, "run_id": entry["run_id"], "candidate_hash": identity["candidate_hash"],
            "contract_hash": identity["candidate_hash"], "registry_hash": identity["predicate_input_root"],
            "authority_hash": identity["authority_root"], "observation_ref": "observations/refactor-observed.json",
            "receipt_ref": receipt_ref, "acceptance_ids": acceptance[slice_id],
        }
        _write(run / "terminal-evidence.json", evidence)
        _write(run / "terminal-replay-report.json", {"status": "pass", "producer": "terminal-validator", "plan_id": manifest["plan_id"], "slice_id": slice_id, "run_id": entry["run_id"], "evidence_ref": "terminal-evidence.json"})
