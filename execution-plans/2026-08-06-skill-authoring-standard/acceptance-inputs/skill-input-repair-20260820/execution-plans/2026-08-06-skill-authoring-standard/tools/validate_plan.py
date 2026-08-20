"""Validate the Skill Authoring Standard VDD plan before implementation."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
PLAN_ID = "skill-authoring-standard"
REQUIRED_FILES = (
    "00-index.md",
    "95-implementation-evolution-and-completion-report.md",
    "authority-manifest.v1.json",
    "baseline-and-scope.v1.json",
    "command-registry.v1.json",
    "implementation-contract.v1.json",
    "model-route-decision.v1.json",
    "plan-state.v1.json",
    "requirements.v1.json",
    "resume-state.v1.json",
    "tools/validate_plan.py",
    "tools/validate_implementation.py",
    "tools/tests/test_validate_plan.py",
    "tools/tests/test_validate_implementation.py",
)
FORBIDDEN = (
    ".agents/skills/",
    ".agents/skills/bmad-",
    ".agents/skills/gds-",
    ".agents/skills/workflow-chapter",
    "PhaseA.Platform/",
    "PhaseA.Platform.Tests/",
    "runtime/phase-a/",
    "logs/phase-a-innernet/",
    "execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/",
)
ROUND3_ROOT = PLAN_ROOT / "repair" / "round-3"
ROUND3_CLOSURE = ROUND3_ROOT / "repair-closure.json"
ROUND3_BASELINE_MANIFEST = ROUND3_ROOT / "baseline-content-manifest.v1.json"
ROUND3_CANDIDATE_MANIFEST = ROUND3_ROOT / "candidate-content-manifest.v1.json"
ROUND3_CALLSITE_INVENTORY = ROUND3_ROOT / "callsite-inventory.v1.json"
ROUND3_COMPOSITION_RECEIPT = REPOSITORY_ROOT / "logs" / "tdd-adapter" / "skill-authoring-standard" / "repair-round-2" / "plan-validator-composition-receipt.v3.json"
ROUND3_RECEIPT_ROOT = ROUND3_COMPOSITION_RECEIPT.parent
ROUND3_REPAIR_PATHS = (
    "tools/validate_plan.py",
    "tools/validate_implementation.py",
    "tools/tests/test_validate_plan.py",
    "tools/tests/test_validate_implementation.py",
)
ROUND4_ROOT = PLAN_ROOT / "repair" / "round-4"
ROUND4_CLOSURE = ROUND4_ROOT / "repair-closure.json"
ROUND4_BASELINE_MANIFEST = ROUND4_ROOT / "baseline-content-manifest.v1.json"
ROUND4_CANDIDATE_MANIFEST = ROUND4_ROOT / "candidate-content-manifest.v1.json"
ROUND4_CALLSITE_INVENTORY = ROUND4_ROOT / "callsite-inventory.v1.json"
ROUND4_COMPOSITION_RECEIPT = REPOSITORY_ROOT / "logs" / "tdd-adapter" / "skill-authoring-standard" / "repair-round-4" / "plan-validator-composition-receipt.v2.json"
ROUND4_INVENTORY_PATHS = ROUND3_REPAIR_PATHS
ROUND4_REPAIR_PATHS = (
    *ROUND4_INVENTORY_PATHS,
    "00-index.md",
    "authority-manifest.v1.json",
    "implementation-contract.v1.json",
    "resume-state.v1.json",
)
ROUND4_FINDING_IDS = (
    "BSR-1ADE171397A5118E", "BSR-1F6D75E80E1DC954", "BSR-21391CAB524855E5",
    "BSR-3C5D8A6233470C7B", "BSR-6553788757B886B5", "BSR-7C1C402CE370CF0B",
    "BSR-8B63B524ED53376F", "BSR-929B06CA6870720F", "BSR-B7CCBCB583CBA4F7",
    "BSR-D631C746D61600DF", "BSR-DB3124C18B728E7C", "BSR-DD90EC54AC523D2C",
    "BSR-E6D64A04D3575134", "BSR-FE5426B30C6AA6B5",
)
ROUND5_ROOT = PLAN_ROOT / "repair" / "round-5"
ROUND5_CLOSURE = ROUND5_ROOT / "repair-closure.json"
ROUND5_BASELINE_MANIFEST = ROUND5_ROOT / "baseline-content-manifest.v1.json"
ROUND5_CANDIDATE_MANIFEST = ROUND5_ROOT / "candidate-content-manifest.v1.json"
ROUND5_CALLSITE_INVENTORY = ROUND5_ROOT / "callsite-inventory.v1.json"
ROUND5_COMPOSITION_RECEIPT = REPOSITORY_ROOT / "logs" / "tdd-adapter" / "skill-authoring-standard" / "repair-round-5" / "plan-validator-composition-receipt.v1.json"
ROUND5_REPAIR_PATHS = (
    "tools/validate_plan.py", "tools/validate_implementation.py",
    "tools/tests/test_validate_plan.py", "tools/tests/test_validate_implementation.py",
    "00-index.md", "authority-manifest.v1.json", "baseline-and-scope.v1.json",
    "implementation-contract.v1.json", "requirements.v1.json", "resume-state.v1.json",
)
ROUND4_INVENTORY_ARGV = [
    "-l", "FORBIDDEN|terminal_replay_command_ids|authority.*source_files|validate_round4_repair|run_terminal_replay",
    "execution-plans/2026-08-06-skill-authoring-standard/tools",
]
ROUND3_FINDING_IDS = (
    "BSR-3C76AD52587A942F",
    "BSR-809547CB18AB176F",
    "BSR-98BBC8C293706327",
    "BSR-A3AC745EF56E05A2",
    "BSR-BEE19337EB199E40",
    "BSR-F86E17F0A6F2F9A2",
)
REQUIRED_VALIDATOR_BINDINGS = (
    ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py",
    ".agents/skills/quick-dev-tdd-adapter/tools/validate_adapter_contract.py",
)


def load(relative: str) -> Any:
    return json.loads((PLAN_ROOT / relative).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_repository_relative(raw: str) -> str | None:
    """Resolve a declared write path without permitting absolute or escaping paths."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        return None
    root = REPOSITORY_ROOT.resolve()
    try:
        resolved = (root / candidate).resolve()
        relative = resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    value = relative.as_posix()
    return None if value in {"", "."} else value


def validator_binding_errors(authority: dict[str, Any]) -> list[str]:
    bindings = authority.get("validator_bindings")
    if not isinstance(bindings, list):
        return [f"validator-binding-missing:{path}" for path in REQUIRED_VALIDATOR_BINDINGS]
    by_path = {item.get("path"): item for item in bindings if isinstance(item, dict)}
    errors: list[str] = []
    for path in REQUIRED_VALIDATOR_BINDINGS:
        item = by_path.get(path)
        target = REPOSITORY_ROOT / path
        if not isinstance(item, dict) or not target.is_file():
            errors.append(f"validator-binding-missing:{path}")
        elif item.get("sha256") != sha256(target):
            errors.append(f"validator-binding-drift:{path}")
    return errors


def round3_path_hashes() -> dict[str, str]:
    return {
        path: sha256(PLAN_ROOT / path)
        for path in ROUND3_REPAIR_PATHS
        if (PLAN_ROOT / path).is_file()
    }


def resolve_repair_reference(raw: Any) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = Path(raw.replace("\\", "/"))
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    base = REPOSITORY_ROOT if raw.replace("\\", "/").startswith(("logs/", "execution-plans/")) else PLAN_ROOT
    try:
        resolved = (base / candidate).resolve()
        resolved.relative_to(REPOSITORY_ROOT.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def validate_round3_repair() -> list[str]:
    """Replay the VDD repair evidence required before another Bootstrap round."""
    errors: list[str] = []
    required = (ROUND3_CLOSURE, ROUND3_BASELINE_MANIFEST, ROUND3_CANDIDATE_MANIFEST, ROUND3_CALLSITE_INVENTORY, ROUND3_COMPOSITION_RECEIPT)
    for path in required:
        if not path.is_file():
            errors.append(f"round3-repair-missing:{path.relative_to(REPOSITORY_ROOT).as_posix()}")
    if errors:
        return errors
    try:
        closure = json.loads(ROUND3_CLOSURE.read_text(encoding="utf-8"))
        baseline = json.loads(ROUND3_BASELINE_MANIFEST.read_text(encoding="utf-8"))
        candidate = json.loads(ROUND3_CANDIDATE_MANIFEST.read_text(encoding="utf-8"))
        inventory = json.loads(ROUND3_CALLSITE_INVENTORY.read_text(encoding="utf-8"))
        receipt = json.loads(ROUND3_COMPOSITION_RECEIPT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"round3-repair-invalid-json:{exc}"]
    if closure.get("schemaVersion") != "vdd-repair-closure.v1":
        errors.append("round3-repair-closure-schema-invalid")
    if tuple(closure.get("findingIds", [])) != ROUND3_FINDING_IDS:
        errors.append("round3-repair-finding-set-mismatch")
    if tuple(closure.get("repairPaths", [])) != ROUND3_REPAIR_PATHS:
        errors.append("round3-repair-path-set-mismatch")
    if closure.get("authorizes") != []:
        errors.append("round3-repair-closure-must-be-non-authorizing")
    item_ids = tuple(item.get("findingId") for item in closure.get("items", []) if isinstance(item, dict))
    if item_ids != ROUND3_FINDING_IDS:
        errors.append("round3-repair-items-mismatch")
    if any(item.get("disposition") not in {"fixed", "refuted"} for item in closure.get("items", []) if isinstance(item, dict)):
        errors.append("round3-repair-open-disposition")
    predecessor = closure.get("predecessorValidationEnvelope", {})
    predecessor_path = resolve_repair_reference(predecessor.get("path"))
    if predecessor_path is None or not predecessor_path.is_file() or sha256(predecessor_path) != predecessor.get("sha256"):
        errors.append("round3-predecessor-envelope-binding-drift")
    for item in closure.get("items", []):
        if not isinstance(item, dict):
            errors.append("round3-repair-item-invalid")
            continue
        for raw in item.get("fixRefs", []):
            if resolve_repair_reference(raw) is None:
                errors.append(f"round3-fix-reference-unsafe:{raw}")
        for evidence in item.get("evidence", []):
            if not isinstance(evidence, dict):
                errors.append("round3-evidence-invalid")
                continue
            evidence_path = resolve_repair_reference(evidence.get("path"))
            if evidence_path is None or not evidence_path.is_file() or (not ROUND4_ROOT.exists() and sha256(evidence_path) != evidence.get("sha256")):
                errors.append(f"round3-evidence-binding-drift:{evidence.get('path')}")
    for manifest, label in ((baseline, "baseline"), (candidate, "candidate")):
        entries = manifest.get("files")
        if not isinstance(entries, list):
            errors.append(f"round3-{label}-manifest-invalid")
            continue
        actual = {item.get("path"): item.get("sha256") for item in entries if isinstance(item, dict)}
        if set(actual) != set(ROUND3_REPAIR_PATHS):
            errors.append(f"round3-{label}-manifest-paths-mismatch")
        if any(not isinstance(path, str) or canonical_repository_relative(f"execution-plans/2026-08-06-skill-authoring-standard/{path}") is None for path in actual):
            errors.append(f"round3-{label}-manifest-path-unsafe")
    inventory_entries = inventory.get("callSites")
    if inventory.get("schemaVersion") != "vdd-root-cause-callsite-inventory.v1" or not isinstance(inventory_entries, list):
        errors.append("round3-callsite-inventory-invalid")
    else:
        dispositions = {item.get("path"): item.get("disposition") for item in inventory_entries if isinstance(item, dict)}
        if set(dispositions) != set(ROUND3_REPAIR_PATHS) or any(value != "changed" for value in dispositions.values()):
            errors.append("round3-callsite-inventory-incomplete")
    receipt_path = ROUND3_COMPOSITION_RECEIPT.relative_to(REPOSITORY_ROOT).as_posix()
    receipt_binding = closure.get("compositionReceipt", {})
    if receipt_binding.get("path") != receipt_path or receipt_binding.get("sha256") != sha256(ROUND3_COMPOSITION_RECEIPT):
        errors.append("round3-composition-receipt-binding-drift")
    producer_paths = set(receipt.get("producerPaths", []))
    consumer_paths = set(receipt.get("consumerPaths", []))
    if receipt.get("schemaVersion") != "vdd-producer-consumer-composition-receipt.v1" or receipt.get("status") != "passed":
        errors.append("round3-composition-receipt-not-passed")
    if not producer_paths or not consumer_paths or producer_paths & consumer_paths:
        errors.append("round3-composition-receipt-path-partition-invalid")
    if producer_paths | consumer_paths != set(ROUND3_REPAIR_PATHS):
        errors.append("round3-composition-receipt-paths-mismatch")
    stdout_path = resolve_repair_reference(receipt.get("stdoutPath"))
    if stdout_path is None or not stdout_path.is_file() or sha256(stdout_path) != receipt.get("stdoutSha256"):
        errors.append("round3-composition-receipt-output-binding-drift")
    if receipt.get("shell") is not False or receipt.get("exitCode") != 0 or receipt.get("timeoutSeconds") != 180:
        errors.append("round3-composition-receipt-command-contract-invalid")
    for key, path in (("baselineManifest", ROUND3_BASELINE_MANIFEST), ("candidateManifest", ROUND3_CANDIDATE_MANIFEST), ("callsiteInventory", ROUND3_CALLSITE_INVENTORY)):
        binding = closure.get(key, {})
        expected_path = path.relative_to(PLAN_ROOT).as_posix()
        if binding.get("path") != expected_path or binding.get("sha256") != sha256(path):
            errors.append(f"round3-{key}-binding-drift")
    return errors


def round4_path_hashes() -> dict[str, str]:
    return {
        path: sha256(PLAN_ROOT / path)
        for path in ROUND4_REPAIR_PATHS
        if (PLAN_ROOT / path).is_file()
    }


def _manifest_map(manifest: dict[str, Any]) -> dict[str, str]:
    entries = manifest.get("files")
    if not isinstance(entries, list):
        return {}
    return {item.get("path"): item.get("sha256") for item in entries if isinstance(item, dict)}


def _strip_fragment(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    return raw.split("#", 1)[0]


def _registered_command_argv(command_id: str, registry: dict[str, Any]) -> tuple[list[str], int] | None:
    commands = registry.get("commands")
    by_id = {item.get("id"): item for item in commands if isinstance(item, dict)} if isinstance(commands, list) else {}
    descriptor = by_id.get(command_id)
    if not isinstance(descriptor, dict) or descriptor.get("shell") is not False or descriptor.get("executable") != "py":
        return None
    raw_argv = descriptor.get("argv")
    timeout = descriptor.get("timeout_seconds")
    if not isinstance(raw_argv, list):
        return None
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 0 < timeout <= 3600:
        return None
    resolved_argv: list[str] = []
    for item in raw_argv:
        if isinstance(item, dict) and item.get("type") == "plan_path" and isinstance(item.get("value"), str):
            value = item["value"].replace("\\", "/")
            if Path(value).is_absolute() or ".." in Path(value).parts:
                return None
            resolved_argv.append((PLAN_ROOT / value).resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix())
            continue
        if not isinstance(item, str):
            return None
        if "\x00" in item or Path(item).is_absolute() or ".." in Path(item).parts:
            return None
        resolved_argv.append(item)
    return ["py", *resolved_argv], timeout


def validate_round4_repair() -> list[str]:
    """Replay the post-Round-3 deterministic repair closure."""
    errors: list[str] = []
    required = (ROUND4_CLOSURE, ROUND4_BASELINE_MANIFEST, ROUND4_CANDIDATE_MANIFEST, ROUND4_CALLSITE_INVENTORY, ROUND4_COMPOSITION_RECEIPT)
    for path in required:
        if not path.is_file():
            errors.append(f"round4-repair-missing:{path.relative_to(REPOSITORY_ROOT).as_posix()}")
    if errors:
        return errors
    try:
        closure = json.loads(ROUND4_CLOSURE.read_text(encoding="utf-8"))
        baseline = json.loads(ROUND4_BASELINE_MANIFEST.read_text(encoding="utf-8"))
        candidate = json.loads(ROUND4_CANDIDATE_MANIFEST.read_text(encoding="utf-8"))
        inventory = json.loads(ROUND4_CALLSITE_INVENTORY.read_text(encoding="utf-8"))
        receipt = json.loads(ROUND4_COMPOSITION_RECEIPT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"round4-repair-invalid-json:{exc}"]
    if closure.get("schemaVersion") != "vdd-repair-closure.v1":
        errors.append("round4-repair-closure-schema-invalid")
    if tuple(closure.get("findingIds", [])) != ROUND4_FINDING_IDS:
        errors.append("round4-repair-finding-set-mismatch")
    if tuple(closure.get("repairPaths", [])) != ROUND4_REPAIR_PATHS:
        errors.append("round4-repair-path-set-mismatch")
    if closure.get("authorizes") != []:
        errors.append("round4-repair-closure-must-be-non-authorizing")
    items = closure.get("items", [])
    if tuple(item.get("findingId") for item in items if isinstance(item, dict)) != ROUND4_FINDING_IDS:
        errors.append("round4-repair-items-mismatch")
    if any(not isinstance(item, dict) or item.get("disposition") not in {"fixed", "refuted"} for item in items):
        errors.append("round4-repair-open-disposition")
    for item in items:
        if not isinstance(item, dict):
            continue
        if not item.get("fixRefs") or not item.get("evidence"):
            errors.append(f"round4-repair-proof-missing:{item.get('findingId')}")
        for raw in item.get("fixRefs", []):
            if resolve_repair_reference(raw) is None:
                errors.append(f"round4-fix-reference-unsafe:{raw}")
        for evidence in item.get("evidence", []):
            path = resolve_repair_reference(evidence.get("path")) if isinstance(evidence, dict) else None
            if path is None or not path.is_file() or sha256(path) != evidence.get("sha256"):
                errors.append(f"round4-evidence-binding-drift:{evidence.get('path') if isinstance(evidence, dict) else None}")
    predecessor = closure.get("predecessorValidationEnvelope", {})
    predecessor_path = resolve_repair_reference(predecessor.get("path"))
    if predecessor_path is None or not predecessor_path.is_file() or sha256(predecessor_path) != predecessor.get("sha256"):
        errors.append("round4-predecessor-envelope-binding-drift")
    else:
        try:
            envelope = json.loads(predecessor_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            envelope = {}
        if (
            envelope.get("schemaVersion") != "bootstrap-finalized-run-validation.v3"
            or envelope.get("reviewId") != "skill-authoring-standard-bootstrap-r3"
            or envelope.get("lineageFamilyId") != "skill-authoring-standard"
            or envelope.get("fullReviewRound") != 3
            or envelope.get("finalStatus") != "blocked"
            or envelope.get("authorizes") != []
        ):
            errors.append("round4-predecessor-envelope-identity-invalid")
    current = round4_path_hashes()
    baseline_map = _manifest_map(baseline)
    candidate_map = _manifest_map(candidate)
    if set(candidate_map) != set(ROUND4_REPAIR_PATHS) or candidate_map != current:
        errors.append("round4-candidate-manifest-drift")
    predecessor_candidate = PLAN_ROOT / "repair" / "round-3" / "candidate-content-manifest.v1.json"
    try:
        predecessor_map = _manifest_map(json.loads(predecessor_candidate.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        predecessor_map = {}
    if {path: baseline_map.get(path) for path in ROUND4_INVENTORY_PATHS} != predecessor_map:
        errors.append("round4-baseline-not-bound-to-predecessor")
    if set(baseline_map) != set(ROUND4_REPAIR_PATHS):
        errors.append("round4-baseline-manifest-paths-mismatch")
    if baseline.get("sourceManifest", {}).get("path") != "repair/round-3/candidate-content-manifest.v1.json" or baseline.get("sourceManifest", {}).get("sha256") != sha256(predecessor_candidate):
        errors.append("round4-baseline-source-binding-drift")
    snapshot_sources = baseline.get("snapshotSources", [])
    expected_snapshot_paths = set(ROUND4_REPAIR_PATHS) - set(ROUND4_INVENTORY_PATHS)
    snapshot_by_path = {item.get("path"): item for item in snapshot_sources if isinstance(item, dict)} if isinstance(snapshot_sources, list) else {}
    if set(snapshot_by_path) != expected_snapshot_paths:
        errors.append("round4-baseline-snapshot-set-mismatch")
    for path in expected_snapshot_paths:
        source = snapshot_by_path.get(path, {})
        snapshot_path = resolve_repair_reference(source.get("snapshotPath")) if isinstance(source, dict) else None
        if snapshot_path is None or not snapshot_path.is_file() or sha256(snapshot_path) != source.get("sha256") or baseline_map.get(path) != source.get("sha256"):
            errors.append(f"round4-baseline-snapshot-drift:{path}")
    if inventory.get("schemaVersion") != "vdd-root-cause-callsite-inventory.v1" or inventory.get("inventoryCommand", {}).get("argv") != ROUND4_INVENTORY_ARGV:
        errors.append("round4-inventory-command-binding-invalid")
    else:
        command = ["rg", *ROUND4_INVENTORY_ARGV]
        try:
            result = subprocess.run(command, cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, shell=False)
            if result.returncode not in {0, 1}:
                errors.append("round4-inventory-command-failed")
            discovered = set()
            for raw in result.stdout.splitlines():
                path = Path(raw.strip()).resolve().relative_to(PLAN_ROOT.resolve()).as_posix()
                discovered.add(path)
            listed = {item.get("path") for item in inventory.get("callSites", []) if isinstance(item, dict)}
            if discovered != listed or listed != set(ROUND4_INVENTORY_PATHS):
                errors.append("round4-callsite-inventory-drift")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            errors.append("round4-inventory-command-unavailable")
    receipt_binding = closure.get("compositionReceipt", {})
    if receipt_binding.get("path") != ROUND4_COMPOSITION_RECEIPT.relative_to(REPOSITORY_ROOT).as_posix() or receipt_binding.get("sha256") != sha256(ROUND4_COMPOSITION_RECEIPT):
        errors.append("round4-composition-receipt-binding-drift")
    registry = load("command-registry.v1.json")
    registered = _registered_command_argv(receipt.get("commandId"), registry)
    if registered is None or receipt.get("argv") != registered[0] or receipt.get("shell") is not False or receipt.get("timeoutSeconds") != registered[1]:
        errors.append("round4-composition-command-binding-invalid")
    elif receipt.get("inputHashes") != current:
        errors.append("round4-composition-input-drift")
    else:
        stdout_path = resolve_repair_reference(receipt.get("stdoutPath"))
        if stdout_path is None or not stdout_path.is_file() or sha256(stdout_path) != receipt.get("stdoutSha256"):
            errors.append("round4-composition-output-binding-drift")
        if os.environ.get("VDD_COMPOSITION_REPLAY") != "1":
            try:
                env = os.environ.copy()
                env["VDD_COMPOSITION_REPLAY"] = "1"
                completed = subprocess.run(registered[0], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=registered[1], shell=False, env=env)
                if completed.returncode != 0 or receipt.get("exitCode") != completed.returncode:
                    errors.append("round4-composition-replay-failed")
            except (OSError, subprocess.TimeoutExpired):
                errors.append("round4-composition-replay-timeout")
    return errors


def validate_round5_repair() -> list[str]:
    errors: list[str] = []
    required = (ROUND5_CLOSURE, ROUND5_BASELINE_MANIFEST, ROUND5_CANDIDATE_MANIFEST, ROUND5_CALLSITE_INVENTORY, ROUND5_COMPOSITION_RECEIPT)
    for path in required:
        if not path.is_file():
            errors.append(f"round5-repair-missing:{path.relative_to(REPOSITORY_ROOT).as_posix()}")
    if errors:
        return errors
    try:
        closure = json.loads(ROUND5_CLOSURE.read_text(encoding="utf-8"))
        baseline = json.loads(ROUND5_BASELINE_MANIFEST.read_text(encoding="utf-8"))
        candidate = json.loads(ROUND5_CANDIDATE_MANIFEST.read_text(encoding="utf-8"))
        inventory = json.loads(ROUND5_CALLSITE_INVENTORY.read_text(encoding="utf-8"))
        receipt = json.loads(ROUND5_COMPOSITION_RECEIPT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"round5-repair-invalid-json:{exc}"]
    if closure.get("schemaVersion") != "vdd-repair-closure.v1" or closure.get("authorizes") != []:
        errors.append("round5-repair-closure-invalid")
    if tuple(closure.get("repairPaths", [])) != ROUND5_REPAIR_PATHS:
        errors.append("round5-repair-path-set-mismatch")
    for manifest, label in ((baseline, "baseline"), (candidate, "candidate")):
        entries = manifest.get("files")
        if not isinstance(entries, list) or {item.get("path") for item in entries if isinstance(item, dict)} != set(ROUND5_REPAIR_PATHS):
            errors.append(f"round5-{label}-manifest-path-set-mismatch")
    candidate_map = _manifest_map(candidate)
    for path in ROUND5_REPAIR_PATHS:
        actual = sha256(PLAN_ROOT / path)
        if candidate_map.get(path) != actual:
            errors.append(f"round5-candidate-drift:{path}")
    if inventory.get("schemaVersion") != "vdd-root-cause-callsite-inventory.v1" or {item.get("path") for item in inventory.get("callSites", []) if isinstance(item, dict)} != set(ROUND5_REPAIR_PATHS):
        errors.append("round5-callsite-inventory-invalid")
    if receipt.get("schemaVersion") != "vdd-producer-consumer-composition-receipt.v1" or receipt.get("status") != "passed" or receipt.get("authorizes") != []:
        errors.append("round5-composition-receipt-invalid")
    if closure.get("compositionReceipt", {}).get("path") != ROUND5_COMPOSITION_RECEIPT.relative_to(REPOSITORY_ROOT).as_posix() or closure.get("compositionReceipt", {}).get("sha256") != sha256(ROUND5_COMPOSITION_RECEIPT):
        errors.append("round5-composition-receipt-binding-drift")
    return errors


def receipt_output_path(raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        raise ValueError("receipt output must be repository-relative")
    try:
        resolved = (REPOSITORY_ROOT / candidate).resolve()
        resolved.relative_to(ROUND3_RECEIPT_ROOT.resolve())
    except (OSError, ValueError) as exc:
        raise ValueError("receipt output escapes the controlled repair evidence root") from exc
    if resolved.suffix != ".json" or resolved.exists():
        raise ValueError("receipt output must be a new JSON file")
    return resolved


def write_round3_composition_receipt(raw_output: str) -> dict[str, Any]:
    """Run the producer/consumer test composition and append its receipt under logs/."""
    output = receipt_output_path(raw_output)
    command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(PLAN_ROOT / "tools" / "tests"), "-p", "test_*.py"]
    before = round3_path_hashes()
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, shell=False)
    after = round3_path_hashes()
    if before != after:
        raise RuntimeError("composition command changed repair inputs")
    if completed.returncode != 0:
        raise RuntimeError("composition command failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    stdout_path = output.with_suffix(".stdout.log")
    stdout_path.write_text(completed.stdout + completed.stderr, encoding="utf-8", newline="\n")
    receipt = {
        "schemaVersion": "vdd-producer-consumer-composition-receipt.v1",
        "generatedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "commandId": "package-a-plan-tests",
        "argv": command,
        "shell": False,
        "timeoutSeconds": 180,
        "status": "passed",
        "exitCode": completed.returncode,
        "producerPaths": ["tools/validate_plan.py", "tools/validate_implementation.py"],
        "consumerPaths": ["tools/tests/test_validate_plan.py", "tools/tests/test_validate_implementation.py"],
        "inputHashes": after,
        "stdoutPath": stdout_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "stdoutSha256": sha256(stdout_path),
        "authorizes": [],
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    return receipt


def write_round4_composition_receipt(raw_output: str) -> dict[str, Any]:
    """Run the non-recursive repair composition command and append its receipt."""
    output = Path(raw_output)
    if output.is_absolute() or ".." in output.parts:
        raise ValueError("receipt output must be repository-relative")
    output = (REPOSITORY_ROOT / output).resolve()
    output.relative_to(ROUND4_COMPOSITION_RECEIPT.parent.resolve())
    if output != ROUND4_COMPOSITION_RECEIPT.resolve() or output.exists():
        raise ValueError("round4 receipt output must be the new controlled evidence path")
    registry = load("command-registry.v1.json")
    registered = _registered_command_argv("plan-validator-tests", registry)
    if registered is None:
        raise RuntimeError("registered composition command is invalid")
    command, timeout = registered
    before = round4_path_hashes()
    env = os.environ.copy()
    env["VDD_COMPOSITION_REPLAY"] = "1"
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, shell=False, env=env)
    after = round4_path_hashes()
    if before != after:
        raise RuntimeError("composition command changed repair inputs")
    if completed.returncode != 0:
        raise RuntimeError("composition command failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    stdout_path = output.with_suffix(".stdout.log")
    stdout_path.write_text(completed.stdout + completed.stderr, encoding="utf-8", newline="\n")
    receipt = {
        "schemaVersion": "vdd-producer-consumer-composition-receipt.v1",
        "generatedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "commandId": "plan-validator-tests",
        "argv": command,
        "shell": False,
        "timeoutSeconds": timeout,
        "status": "passed",
        "exitCode": completed.returncode,
        "producerPaths": ["tools/validate_plan.py", "tools/validate_implementation.py"],
        "consumerPaths": ["tools/tests/test_validate_plan.py", "tools/tests/test_validate_implementation.py"],
        "inputHashes": after,
        "stdoutPath": stdout_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "stdoutSha256": sha256(stdout_path),
        "authorizes": [],
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    return receipt


def validate(*, allow_draft: bool = False) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (PLAN_ROOT / relative).is_file():
            errors.append(f"missing:{relative}")
    if errors:
        return errors
    requirements = load("requirements.v1.json")
    contract = load("implementation-contract.v1.json")
    registry = load("command-registry.v1.json")
    state = load("plan-state.v1.json")
    resume = load("resume-state.v1.json")
    if requirements.get("plan_id") != PLAN_ID or contract.get("plan_id") != PLAN_ID:
        errors.append("plan-id-mismatch")
    if requirements.get("profile") != "self-hosted" or contract.get("profile") != "self-hosted":
        errors.append("profile-must-be-self-hosted")
    if state.get("plan_id") != PLAN_ID or resume.get("plan_id") != PLAN_ID:
        errors.append("state-plan-id-mismatch")
    if state.get("profile") != "self-hosted" or resume.get("profile") != "self-hosted":
        errors.append("state-profile-mismatch")
    expected_state_authority = ["plan-ready"] if state.get("state") == "plan-ready" else []
    if state.get("authorizes") != expected_state_authority or resume.get("authorizes") != []:
        errors.append("state-authority-mismatch")
    if resume.get("state") != state.get("state"):
        errors.append("resume-state-plan-state-mismatch")
    if state.get("state") not in {"draft", "plan-ready"}:
        errors.append("invalid-vdd-state")
    if state.get("state") == "draft" and not allow_draft:
        errors.append("knowledge-ready-plan-required")
    if state.get("state") == "plan-ready" and state.get("blocking_conditions"):
        errors.append("plan-ready-cannot-have-blockers")
    if contract.get("backend", {}).get("hidden_state") is not False:
        errors.append("backend-hidden-state-must-be-false")
    authority_binding = contract.get("authority", {})
    if authority_binding.get("authority_manifest") != "authority-manifest.v1.json":
        errors.append("authority-manifest-binding-mismatch")
    protocol = contract.get("protocol_artifacts", {})
    if protocol.get("context_layout") != "context/<capsule-id>" or protocol.get("attempt_layout") != "attempts/<attempt-id>":
        errors.append("adapter-protocol-layout-mismatch")
    required_actions = {"prepare", "red", "green", "refactor", "finalize-candidate", "status", "resume"}
    if not required_actions.issubset(set(contract.get("adapter_actions", []))):
        errors.append("adapter-actions-incomplete")
    requirement_ids = [x.get("id") for x in requirements.get("requirements", [])]
    acceptance_ids = [x.get("id") for x in requirements.get("acceptance", [])]
    if len(requirement_ids) != len(set(requirement_ids)) or len(acceptance_ids) != len(set(acceptance_ids)):
        errors.append("duplicate-requirement-or-acceptance-id")
    known_req = set(requirement_ids)
    known_acc = set(acceptance_ids)
    slices = contract.get("slices", [])
    expected_order = ["SAS-S0", "SAS-S1", "SAS-S2", "SAS-S3"]
    if [x.get("slice_id") for x in slices] != expected_order:
        errors.append("slice-order-mismatch")
    completed: set[str] = set()
    covered_req: set[str] = set()
    covered_acc: set[str] = set()
    for item in slices:
        sid = item.get("slice_id")
        if not isinstance(item.get("forbidden_changes"), list):
            errors.append(f"slice-forbidden-changes-missing:{sid}")
        deps = set(item.get("depends_on", []))
        if not deps.issubset(completed):
            errors.append(f"slice-dependency-order:{sid}")
        completed.add(sid)
        reqs = set(item.get("requirement_ids", []))
        accs = set(item.get("acceptance_ids", []))
        if not reqs.issubset(known_req):
            errors.append(f"unknown-requirement:{sid}")
        if not accs.issubset(known_acc):
            errors.append(f"unknown-acceptance:{sid}")
        covered_req.update(reqs)
        covered_acc.update(accs)
        for area in ("production", "tests", "documentation"):
            for path in item.get("allowed_changes", {}).get(area, []):
                normalized = str(path).replace("\\", "/")
                canonical = canonical_repository_relative(normalized)
                comparable = (canonical or normalized).casefold()
                if canonical is None or any(comparable.startswith(prefix.casefold()) for prefix in FORBIDDEN):
                    errors.append(f"forbidden-write:{sid}:{normalized}")
        if not item.get("execution_snapshot_paths"):
            errors.append(f"missing-snapshot-path:{sid}")
        for path in item.get("execution_snapshot_paths", []):
            if not (REPOSITORY_ROOT / path).exists():
                errors.append(f"missing-snapshot:{sid}:{path}")
    if covered_req != known_req or covered_acc != known_acc:
        errors.append("requirements-or-acceptance-not-covered")
    commands = registry.get("commands", [])
    command_ids = [x.get("id") for x in commands]
    if len(command_ids) != len(set(command_ids)):
        errors.append("duplicate-command-id")
    if any(x.get("shell") is not False for x in commands):
        errors.append("all-commands-must-use-shell-false")
    if contract.get("command_registry") != "command-registry.v1.json":
        errors.append("command-registry-binding-mismatch")
    for path in ("authority-manifest.v1.json", "baseline-and-scope.v1.json"):
        data = load(path)
        if data.get("plan_id") != PLAN_ID or data.get("authorizes") != []:
            errors.append(f"invalid-non-authorizing-manifest:{path}")
    authority = load("authority-manifest.v1.json")
    binding_errors = validator_binding_errors(authority)
    errors.extend(binding_errors)
    authority_paths: list[str] = []
    for item in authority.get("source_files", []):
        raw_path = item.get("path", "")
        canonical = canonical_repository_relative(raw_path)
        path = REPOSITORY_ROOT / canonical if canonical else None
        if path is None or not path.is_file() or sha256(path) != item.get("sha256"):
            errors.append(f"authority-source-drift:{item.get('path')}")
        elif canonical in authority_paths:
            errors.append(f"authority-source-duplicate:{canonical}")
        else:
            authority_paths.append(canonical)
    expected_authority_paths = {canonical_repository_relative(_strip_fragment(raw) or "") for raw in contract.get("source_authority", [])}
    expected_authority_paths.update({
        "execution-plans/2026-08-06-skill-authoring-standard/requirements.v1.json",
        "execution-plans/2026-08-06-skill-authoring-standard/implementation-contract.v1.json",
    })
    if None in expected_authority_paths or set(authority_paths) != expected_authority_paths:
        errors.append("authority-source-set-mismatch")
    baseline = load("baseline-and-scope.v1.json")
    commit = baseline.get("git", {}).get("commit")
    tree = subprocess.run(["git", "rev-parse", f"{commit}^{{tree}}"], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
    if tree.returncode or tree.stdout.strip() != baseline.get("git", {}).get("tree"):
        errors.append("baseline-git-tree-drift")
    scope = baseline.get("scope", {})
    declared_untracked = {canonical_repository_relative(str(raw)) for raw in scope.get("untracked_paths", [])}
    manifest_untracked: set[str] = set()
    for item in scope.get("untracked_manifest", []):
        raw_path = item.get("path", "") if isinstance(item, dict) else ""
        canonical = canonical_repository_relative(raw_path)
        path = REPOSITORY_ROOT / canonical if canonical else None
        if canonical is None or canonical in manifest_untracked or path is None or not path.is_file() or sha256(path) != item.get("sha256"):
            errors.append(f"baseline-untracked-drift:{raw_path}")
        elif canonical:
            manifest_untracked.add(canonical)
    if None in declared_untracked or declared_untracked != manifest_untracked:
        errors.append("baseline-untracked-set-mismatch")
    context = PLAN_ROOT / "knowledge-context.v1.json"
    freeze = PLAN_ROOT / "knowledge-context.freeze.v1.json"
    if context.exists() != freeze.exists():
        errors.append("knowledge-context-freeze-pair-mismatch")
    if state.get("state") == "plan-ready" and not context.exists():
        errors.append("plan-ready-requires-knowledge-context")
    if context.exists() and freeze.exists():
        context_data = load("knowledge-context.v1.json")
        freeze_data = load("knowledge-context.freeze.v1.json")
        if context_data.get("preflight", {}).get("status") != "ready":
            errors.append("knowledge-preflight-not-ready")
        if freeze_data.get("authorizes") != []:
            errors.append("knowledge-freeze-must-be-non-authorizing")
        if freeze_data.get("context_sha256") != sha256(context):
            errors.append("knowledge-freeze-context-hash-drift")
        if not binding_errors:
            try:
                preflight = subprocess.run([sys.executable, "-B", ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py", "--input", str(context), "--repository-root", str(REPOSITORY_ROOT)], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", check=False, timeout=180)
                if preflight.returncode:
                    errors.append("current-knowledge-preflight-failed")
            except (OSError, subprocess.TimeoutExpired):
                errors.append("current-knowledge-preflight-timeout")
    if not binding_errors:
        try:
            result = subprocess.run([sys.executable, "-B", ".agents/skills/quick-dev-tdd-adapter/tools/validate_adapter_contract.py", str(PLAN_ROOT / "implementation-contract.v1.json")], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", check=False, timeout=180)
            if result.returncode:
                errors.append("quick-dev-adapter-contract-rejected")
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"adapter-validator-unavailable:{exc}")
    errors.extend(validate_round3_repair())
    errors.extend(validate_round5_repair() if ROUND5_CLOSURE.is_file() else validate_round4_repair())
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-draft", action="store_true")
    parser.add_argument("--write-round3-composition-receipt")
    parser.add_argument("--write-round4-composition-receipt")
    args = parser.parse_args()
    if args.write_round3_composition_receipt:
        try:
            receipt = write_round3_composition_receipt(args.write_round3_composition_receipt)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            print(json.dumps({"ok": False, "error": str(exc), "authorizes": []}, indent=2))
            return 1
        print(json.dumps({"ok": True, "receipt": receipt, "authorizes": []}, indent=2))
        return 0
    if args.write_round4_composition_receipt:
        try:
            receipt = write_round4_composition_receipt(args.write_round4_composition_receipt)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            print(json.dumps({"ok": False, "error": str(exc), "authorizes": []}, indent=2))
            return 1
        print(json.dumps({"ok": True, "receipt": receipt, "authorizes": []}, indent=2))
        return 0
    errors = validate(allow_draft=args.allow_draft)
    print(json.dumps({"ok": not errors, "errors": errors, "authorizes": []}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
