from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROUND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROUND_DIR.parents[3]
PLAN_ID = "bootstrap-review-operability-hardening-round-4-repair"
SLICE_ID = "BROH-R4-S1"
BASELINE_RUN = (
    REPOSITORY_ROOT / "logs/tdd-adapter" / PLAN_ID / SLICE_ID
    / "RUN-20260808T192238-406431Z"
)
TARGET_PATHS = [
    ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-artifact-view-segment-receipt.v1.schema.json",
    ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py",
    ".agents/skills/run-phase-bootstrap-review/SKILL.md",
    ".agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py",
    "docs/standards/bootstrap-review-control-plane.md",
]


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise ValueError(f"immutable closure artifact conflicts: {path}")
        return
    path.write_text(payload, encoding="utf-8", newline="\n")


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _canonical_hash(value: Any) -> str:
    return _sha_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module is unavailable: {path}")
    module = importlib.util.module_from_spec(spec)
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(path.parent))
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_path
    return module


def _baseline_bytes() -> dict[str, bytes | None]:
    observation = _read(BASELINE_RUN / "observations/red-observed.json")
    changes = {
        item["path"]: item
        for item in observation.get("changed_files", [])
        if isinstance(item, dict) and item.get("path") in TARGET_PATHS
    }
    if set(changes) != set(TARGET_PATHS):
        raise ValueError("baseline RED observation does not cover the repair write set")
    result: dict[str, bytes | None] = {}
    for path in TARGET_PATHS:
        encoded = changes[path].get("before_bytes_base64")
        result[path] = None if encoded is None else base64.b64decode(encoded, validate=True)
    return result


def _current_run() -> Path:
    state = _read(
        REPOSITORY_ROOT / "logs/tdd-adapter" / PLAN_ID / "controller"
        / f"{SLICE_ID}-single-maintainer-state.v1.json"
    )
    run_dir = REPOSITORY_ROOT / str(state.get("run_dir", ""))
    if state.get("phase") != "completed" or not (run_dir / "slice-ready-result.json").is_file():
        raise ValueError("current Quick Dev slice result is unavailable")
    return run_dir


def _build_content_manifests() -> tuple[dict[str, Any], dict[str, Any]]:
    baseline_state = _baseline_bytes()
    baseline_files = []
    candidate_files = []
    for relative in TARGET_PATHS:
        current = (REPOSITORY_ROOT / relative).read_bytes()
        before = baseline_state[relative]
        if before is None:
            candidate_files.append({
                "change_type": "untracked", "roles": ["implementation"],
                "baseline_path": None, "baseline_sha256": None,
                "candidate_path": relative, "candidate_sha256": _sha_bytes(current),
                "inclusion_reason": "Round 4 repair candidate",
            })
            continue
        baseline_files.append({
            "path": relative, "sha256": _sha_bytes(before),
            "roles": ["implementation"], "inclusion_reason": "Round 4 repair baseline",
        })
        candidate_files.append({
            "change_type": "modified", "roles": ["implementation"],
            "baseline_path": relative, "baseline_sha256": _sha_bytes(before),
            "candidate_path": relative, "candidate_sha256": _sha_bytes(current),
            "inclusion_reason": "Round 4 repair candidate",
        })
    return (
        {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "files": baseline_files, "authorizes": []},
        {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "files": candidate_files, "authorizes": []},
    )


def _run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"controlled closure command failed: {command[0]}")


def main() -> int:
    baseline, candidate = _build_content_manifests()
    baseline_path = ROUND_DIR / "baseline-content-manifest.v2.json"
    candidate_path = ROUND_DIR / "candidate-content-manifest.v2.json"
    _write(baseline_path, baseline)
    _write(candidate_path, candidate)

    command_id = "broh-r4-segment-composition"
    command_without_hash = {
        "id": command_id,
        "executable": "py",
        "argv": ["-3", "-B", "execution-plans/2026-08-07-bootstrap-review-operability-hardening/repair/round-4/tools/validate_segment_composition.py"],
        "cwd": ".", "timeout_seconds": 240, "shell": False,
        "allowed_write_roots": [], "forbidden_write_roots": [],
        "environment_allowlist": [
            "HOMEDRIVE", "HOMEPATH", "PATH", "PATHEXT", "SYSTEMROOT",
            "TEMP", "TMP", "USERNAME", "USERPROFILE", "WINDIR",
        ],
        "typed_placeholders": {}, "placeholder_values": {},
    }
    registry_material = {
        "schemaVersion": "acceptance-command-registry.v1",
        "commands": [command_without_hash],
    }
    registry_hash = _canonical_hash(registry_material)
    registry = {
        **registry_material,
        "commands": [{**command_without_hash, "registry_hash": registry_hash}],
        "registryHash": registry_hash,
    }
    registry_path = ROUND_DIR / "acceptance-composition-command-registry.v5.json"
    _write(registry_path, registry)

    receipt_path = ROUND_DIR / "composition-receipt.v7.json"
    if not receipt_path.is_file():
        _run([
            sys.executable,
            ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py",
            "run-command", "--repository-root", str(REPOSITORY_ROOT),
            "--command-registry", str(registry_path.relative_to(REPOSITORY_ROOT)),
            "--command-id", command_id,
            "--input-path", TARGET_PATHS[1],
            "--input-path", "execution-plans/2026-08-07-bootstrap-review-operability-hardening/repair/round-4/tools/validate_segment_composition.py",
            "--out", str(receipt_path),
        ])
    if _read(receipt_path).get("exitCode") != 0:
        raise RuntimeError("composition command receipt is not successful")

    repair_module = _load_module(
        "broh_round4_repair_completeness",
        REPOSITORY_ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts/repair_completeness.py",
    )
    predecessor = None
    novel, authority_paths, high_risk_paths = repair_module._derive_review_escalation(
        REPOSITORY_ROOT,
        "ria-1dd445581b0a69b5a1432c671bd99844",
        0,
        predecessor,
        sorted(TARGET_PATHS),
    )
    handoff_input = {
        "schemaVersion": "quick-dev-repair-review-handoff-input.v1",
        "repositoryRoot": str(REPOSITORY_ROOT),
        "acceptanceTarget": "execution-plans/2026-08-07-bootstrap-review-operability-hardening",
        "lineageFamilyId": "ria-1dd445581b0a69b5a1432c671bd99844",
        "semanticRoundsConsumed": 0,
        "predecessorRun": predecessor,
        "baselineManifestPath": baseline_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "baselineManifestHash": _sha_file(baseline_path),
        "candidateManifestPath": candidate_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "candidateManifestHash": _sha_file(candidate_path),
        "changedFiles": sorted(TARGET_PATHS),
        "directConsumers": ["execution-plans/2026-08-07-bootstrap-review-operability-hardening/repair/round-4/tools/validate_segment_composition.py"],
        "targetedTests": ["execution-plans/2026-08-07-bootstrap-review-operability-hardening/repair/round-4/tools/validate_segment_composition.py"],
        "validationRefs": [
            receipt_path.relative_to(REPOSITORY_ROOT).as_posix(),
            (_current_run() / "slice-ready-result.json").relative_to(REPOSITORY_ROOT).as_posix(),
        ],
        "rootCauseInventories": [{
            "inventoryId": "bootstrap-artifact-view-segment-callsites",
            "searchTerm": "artifact_view_segment",
            "searchRoots": [".agents/skills/run-phase-bootstrap-review"],
            "addressedPaths": sorted([TARGET_PATHS[1], TARGET_PATHS[3]]),
            "exclusions": [],
        }],
        "compositionChecks": [{
            "checkId": command_id,
            "producerPaths": [TARGET_PATHS[1]],
            "consumerPaths": ["execution-plans/2026-08-07-bootstrap-review-operability-hardening/repair/round-4/tools/validate_segment_composition.py"],
            "receiptPath": receipt_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "commandRegistryPath": registry_path.relative_to(REPOSITORY_ROOT).as_posix(),
        }],
        "novelP0P1FindingIds": novel,
        "authorityGraphChanged": bool(authority_paths),
        "highRiskBoundaryChanged": bool(high_risk_paths),
        "authorizes": [],
    }
    handoff_input_path = ROUND_DIR / "acceptance-repair-completeness-input.v3.json"
    request_path = ROUND_DIR / "acceptance-repair-completeness-request.v3.json"
    audit_path = ROUND_DIR / "repair-completeness.v3.json"
    _write(handoff_input_path, handoff_input)
    if not request_path.is_file():
        _run([
            sys.executable,
            ".agents/skills/quick-dev-tdd-adapter/tools/build_repair_review_handoff.py",
            "--request", str(handoff_input_path), "--out", str(request_path),
        ])
    if not audit_path.is_file():
        _run([
            sys.executable,
            ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py",
            "audit-repair-completeness", "--request", str(request_path),
            "--out", str(audit_path),
        ])
    audit = _read(audit_path)
    if audit.get("status") != "passed":
        raise ValueError("Acceptance repair completeness did not pass")

    inventory_path = ROUND_DIR / "root-cause-callsite-inventory.v2.json"
    changed_set_path = ROUND_DIR / "changed-set-manifest.v2.json"
    review_scope_path = ROUND_DIR / "review-scope.v2.json"
    _write(inventory_path, {
        "schema_version": "jimuyun.root-cause-callsite-inventory.v1",
        "inventories": audit["rootCauseInventories"], "request_hash": audit["requestHash"],
        "authorizes": [],
    })
    _write(changed_set_path, {
        "schema_version": "jimuyun.repair-changed-set-manifest.v1",
        "baseline_manifest": audit["baselineManifest"],
        "candidate_manifest": audit["candidateManifest"],
        "changed_path_bindings": audit["changedPathBindings"], "authorizes": [],
    })
    scope_paths = sorted(set(
        TARGET_PATHS
        + [item["path"] for item in audit["directConsumers"]]
        + [item["path"] for item in audit["targetedTests"]]
        + [item["path"] for item in audit["validationRefs"]]
        + [
            registry_path.relative_to(REPOSITORY_ROOT).as_posix(),
            inventory_path.relative_to(REPOSITORY_ROOT).as_posix(),
            changed_set_path.relative_to(REPOSITORY_ROOT).as_posix(),
            audit_path.relative_to(REPOSITORY_ROOT).as_posix(),
        ]
    ))
    _write(review_scope_path, {
        "schema_version": "jimuyun.repair-review-scope.v1",
        "acceptance_target": audit["acceptanceTarget"],
        "paths": [{"path": path, "sha256": _sha_file(REPOSITORY_ROOT / path)} for path in scope_paths],
        "authorizes": [],
    })
    closure_bindings = [
        inventory_path, receipt_path, changed_set_path, review_scope_path,
        registry_path, request_path, audit_path,
    ]
    closure_path = ROUND_DIR / "repair-closure.v2.json"
    _write(closure_path, {
        "schema_version": "jimuyun.vdd-repair-closure.v1",
        "status": "pass", "contract_sha256": _sha_file(ROUND_DIR / "implementation-contract.v1.json"),
        "artifacts": [
            {"path": path.relative_to(REPOSITORY_ROOT).as_posix(), "sha256": _sha_file(path)}
            for path in closure_bindings
        ],
        "acceptance_repair_completeness": {
            "path": audit_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha_file(audit_path), "status": audit["status"],
        },
        "authorizes": [],
    })
    print(json.dumps({"status": "pass", "closure": str(closure_path), "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
