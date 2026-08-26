from __future__ import annotations

import hashlib
from pathlib import Path
import json


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def current_candidate_identity(slice_id: str) -> dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    contract = root / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/implementation-contract.v1.json"
    registry = root / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/command-registry.v1.json"
    document = json.loads(contract.read_text(encoding="utf-8"))
    selected = next(item for item in document["slices"] if item["slice_id"] == slice_id)
    tracked = [selected["tdd"]["red"]["test_selector"], *selected.get("allowed_changes", {}).get("production", []), *selected.get("planned_new_files", [])]
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
        plan_logs = run_root.parents[1]
        evidence_roots = [plan_logs / f"S{i}" / run_root.name for i in range(1, 7)]
    required_names = ["terminal-evidence.json", "terminal-replay-report.json"]
    required = [root / name for root in evidence_roots for name in required_names]
    fixtures = (evidence_roots[-1] / "false-green-fixtures.json") if evidence_roots else plan_dir / "false-green-fixtures" / "nine-fixtures.json"
    missing = [path.as_posix() for path in [*required, fixtures] if not path.is_file()]
    if missing:
        return {"status": "blocked", "predicate": "implementation-complete", "missing": missing}
    try:
        records = [json.loads(path.read_text(encoding="utf-8")) for path in required]
        fixture_doc = json.loads(fixtures.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "blocked", "predicate": "implementation-complete", "reason": "invalid-evidence-json"}
    expected_acceptance = {"A-SEMANTIC", "A-DESCRIPTOR", "A-JUDGE", "A-COVER", "A-PROMOTION", "A-TERMINAL", "A-BOUNDARY"}
    for i, item in enumerate(records[::2]):
        if item.get("status") != "pass" or item.get("slice_id") != f"S{i+1}" or item.get("producer") not in {"quick-dev-adapter", "independent-judge", "coverage-gate", "terminal-validator"}:
            return {"status": "blocked", "predicate": "implementation-complete", "reason": "slice-evidence-not-closed"}
        required_fields = {"plan_id", "slice_id", "run_id", "candidate_hash", "contract_hash", "registry_hash", "authority_hash", "observation_ref", "receipt_ref", "acceptance_ids"}
        if not required_fields.issubset(item) or not isinstance(item.get("acceptance_ids"), list) or not set(item["acceptance_ids"]).issubset(expected_acceptance):
            return {"status": "blocked", "predicate": "implementation-complete", "reason": "evidence-lineage-incomplete"}
        body = {key: value for key, value in item.items() if key != "evidence_sha256"}
        expected = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if item.get("evidence_sha256") != expected:
            return {"status": "blocked", "predicate": "implementation-complete", "reason": "slice-evidence-hash-invalid"}
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
