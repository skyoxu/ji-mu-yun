from __future__ import annotations

import hashlib
from pathlib import Path
import json
import subprocess
import os


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

def _workspace_closure(root: Path) -> str:
    status = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=root, capture_output=True, text=True, check=True).stdout
    tracked = subprocess.run(["git", "ls-files", "-s"], cwd=root, capture_output=True, text=True, check=True).stdout
    payload = (tracked + "\nSTATUS\n" + status).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()

def _workspace_manifest(root: Path) -> dict[str, str]:
    result = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "logs", "__pycache__"}]
        for name in files:
            path = Path(base) / name
            rel = path.relative_to(root).as_posix()
            try:
                result[rel] = _sha(path)
            except FileNotFoundError:
                # A concurrent cache/snapshot cleanup must not produce a
                # partially trusted identity. Recompute on the next call.
                continue
    return dict(sorted(result.items()))


def current_candidate_identity(slice_id: str) -> dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    contract = root / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/implementation-contract.v1.json"
    registry = root / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/command-registry.v1.json"
    document = json.loads(contract.read_text(encoding="utf-8"))
    selected = next(item for item in document["slices"] if item["slice_id"] == slice_id)
    tracked = [selected["tdd"]["red"]["test_selector"], *selected.get("allowed_changes", {}).get("production", []), *selected.get("allowed_changes", {}).get("tests", []), *selected.get("planned_new_files", [])]
    tracked.extend(["execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/stage_command.py", "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/artifact_owners.py", "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/semantic_oracle.py", "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/validate_all.py", ".agents/skills/vdd-execution-plan/scripts/validate_plan.py"])
    for dependency_id in selected.get("dependency_closure", []):
        dependency = next(item for item in document["slices"] if item["slice_id"] == dependency_id)
        tracked.extend(dependency.get("allowed_changes", {}).get("production", []))
        tracked.extend(dependency.get("planned_new_files", []))
    file_state = {}
    for raw in tracked:
        path = root / raw
        if path.is_file():
            file_state[raw] = _sha(path)
        else:
            file_state[raw] = None
    semantic_closure = {
        "slice_id": slice_id,
        "contract": _sha(contract),
        "registry": _sha(registry),
        "authority": _sha(root / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/knowledge-context.freeze.v1.json"),
        "red_test": _sha(root / selected["tdd"]["red"]["test_selector"]),
        "allowed_production": selected["allowed_changes"].get("production", []),
        "planned_files": file_state,
        "dependency_closure": {
            dependency_id: {
                path: file_state.get(path)
                for path in next(item for item in document["slices"] if item["slice_id"] == dependency_id).get("allowed_changes", {}).get("production", [])
            }
            for dependency_id in selected.get("dependency_closure", [])
        },
    }
    semantic_hash = "sha256:" + hashlib.sha256(json.dumps(semantic_closure, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "candidate_hash": _sha(contract),
        "predicate_input_root": _sha(registry),
        "authority_root": _sha(root / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/knowledge-context.freeze.v1.json"),
        "validator_root": _sha(Path(__file__).resolve()),
        "validator_version": "plan-local-bootstrap-v1",
        "closure_definition_hash": _sha(contract),
        "validator_hash": _sha(Path(__file__).resolve()),
        "workspace_closure_hash": _workspace_closure(root),
        "workspace_manifest": _workspace_manifest(root),
        "semantic_closure_hash": semantic_hash,
        "candidate_manifest": file_state,
    }


def validation_snapshot(slice_id: str | None = None) -> dict[str, str]:
    return current_candidate_identity(slice_id or "S6")


def slice_validation_snapshot(slice_id: str | None = None) -> dict[str, str]:
    return validation_snapshot(slice_id)


def validate_terminal(plan_dir: Path, run_root: Path | None = None) -> dict[str, object]:
    """Validate one append-only run-local evidence envelope fail-closed."""
    evidence_roots = []
    if run_root is not None:
        lineage_root = run_root.parent.parent
        try:
            selected_slice = int(run_root.parent.name[1:])
        except (ValueError, IndexError):
            return {"status": "blocked", "predicate": "implementation-complete", "reason": "invalid-run-root"}
        # Each slice owns its own run ID. A terminal invocation may provide one
        # slice root; resolve the other slices from their latest run-local roots.
        for i in range(1, 7):
            slice_root = lineage_root / f"S{i}"
            candidates = sorted([p for p in slice_root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True) if slice_root.is_dir() else []
            evidence_roots.append(run_root if i == selected_slice else (candidates[0] if candidates else slice_root / "MISSING"))
    required_names = ["terminal-evidence.json", "terminal-replay-report.json"]
    required = [root / name for root in evidence_roots for name in required_names]
    fixtures = next((root / "false-green-fixtures.json" for root in reversed(evidence_roots) if (root / "false-green-fixtures.json").is_file()), plan_dir / "false-green-fixtures" / "nine-fixtures.json")
    missing = [path.as_posix() for path in [*required, fixtures] if not path.is_file()]
    if missing:
        return {"status": "blocked", "predicate": "implementation-complete", "missing": missing}
    try:
        records = [json.loads(path.read_text(encoding="utf-8")) for path in required]
        fixture_doc = json.loads(fixtures.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "blocked", "predicate": "implementation-complete", "reason": "invalid-evidence-json"}
    expected_acceptance = {"A-SEMANTIC", "A-DESCRIPTOR", "A-JUDGE", "A-COVER", "A-PROMOTION", "A-TERMINAL", "A-BOUNDARY"}
    identity = current_candidate_identity("S6")
    observed_acceptance: set[str] = set()
    for i, item in enumerate(records[::2]):
        if item.get("status") != "pass" or item.get("slice_id") != f"S{i+1}" or item.get("producer") not in {"quick-dev-adapter", "independent-judge", "coverage-gate", "terminal-validator"}:
            return {"status": "blocked", "predicate": "implementation-complete", "reason": "slice-evidence-not-closed"}
        required_fields = {"plan_id", "slice_id", "run_id", "candidate_hash", "contract_hash", "registry_hash", "authority_hash", "observation_ref", "receipt_ref", "acceptance_ids"}
        if not required_fields.issubset(item) or not isinstance(item.get("acceptance_ids"), list) or not set(item["acceptance_ids"]).issubset(expected_acceptance):
            return {"status": "blocked", "predicate": "implementation-complete", "reason": "evidence-lineage-incomplete"}
        if any(item.get(field) != identity[key] for field, key in (("candidate_hash", "candidate_hash"), ("contract_hash", "candidate_hash"), ("registry_hash", "predicate_input_root"), ("authority_hash", "authority_root"))):
            return {"status": "blocked", "predicate": "implementation-complete", "reason": "candidate-binding-invalid"}
        observed_acceptance.update(item["acceptance_ids"])
        body = {key: value for key, value in item.items() if key != "evidence_sha256"}
        expected = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if item.get("evidence_sha256") != expected:
            return {"status": "blocked", "predicate": "implementation-complete", "reason": "slice-evidence-hash-invalid"}
        observation = evidence_roots[i] / item["observation_ref"]
        receipt = evidence_roots[i] / item["receipt_ref"]
        if not observation.is_file() or not receipt.is_file():
            return {"status": "blocked", "predicate": "implementation-complete", "reason": "referenced-evidence-missing"}
        try:
            observation_value = json.loads(observation.read_text(encoding="utf-8"))
            receipt_value = json.loads(receipt.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {"status": "blocked", "predicate": "implementation-complete", "reason": "referenced-evidence-invalid"}
        if observation_value.get("stage") not in {"green", "refactor", "terminal"} or receipt_value.get("authorizes") != []:
            return {"status": "blocked", "predicate": "implementation-complete", "reason": "referenced-evidence-untrusted"}
    if observed_acceptance != expected_acceptance:
        return {"status": "blocked", "predicate": "implementation-complete", "reason": "acceptance-cover-incomplete"}
    expected_ids = [f"FG-{i:02d}" for i in range(1, 10)]
    if not isinstance(fixture_doc, dict) or fixture_doc.get("status") != "pass" or fixture_doc.get("producer") != "coverage-gate" or fixture_doc.get("fixture_ids") != expected_ids or fixture_doc.get("blocked_ids") != expected_ids or fixture_doc.get("corrected_pair_ids") != expected_ids:
        return {"status": "blocked", "predicate": "implementation-complete", "reason": "false-green-fixtures-not-closed"}
    if fixture_doc.get("predecessor_judge_hash", "").startswith("sha256:") is False or fixture_doc.get("corrected_pairs_executed") is not True:
        return {"status": "blocked", "predicate": "implementation-complete", "reason": "promotion-lineage-incomplete"}
    body = {key: value for key, value in fixture_doc.items() if key != "evidence_sha256"}
    expected = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if fixture_doc.get("evidence_sha256") != expected:
        return {"status": "blocked", "predicate": "implementation-complete", "reason": "fixture-evidence-hash-invalid"}
    return {"status": "pass", "predicate": "implementation-complete", "slice_count": 6, "false_green_fixture_count": 9}
