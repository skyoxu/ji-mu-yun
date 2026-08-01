"""Deterministic sibling-callsite and producer/consumer repair closure."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from acceptance_core import (
    InputError,
    candidate_changed_paths,
    canonical_hash,
    validate_candidate_manifest,
)
from execution_control import ControlError, resolve_registered_command, resolve_typed_argv
from review_cycle_policy import HARD_FULL_REVIEW_ROUND_LIMIT, NOVEL_FINDING_COMPARISON_ROUND


_HASH = re.compile(r"sha256:[a-f0-9]{64}$")
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{2,95}$")
_LINEAGE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{2,63}$")
_FINDING_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{2,95}$")
_TEXT_SUFFIXES = {
    ".cs", ".cshtml", ".gd", ".gdshader", ".js", ".json", ".jsx", ".md",
    ".ps1", ".psm1", ".py", ".razor", ".sh", ".ts", ".tsx", ".yaml", ".yml",
}
_SOURCE_SUFFIXES = {
    ".cs", ".cshtml", ".gd", ".gdshader", ".js", ".jsx", ".ps1", ".psm1",
    ".py", ".razor", ".sh", ".ts", ".tsx",
}
_AUTHORITY_PREFIXES = (
    "AGENTS.md", "docs/adr/", "docs/architecture/", "docs/standards/",
    ".agents/skills/",
    ".agents/skills/run-phase-bootstrap-review/references/",
    ".agents/skills/vdd-execution-plan/scripts/skill-contract.json",
)
_HIGH_RISK_PREFIXES = (
    "PhaseA.Platform/Security/", "PhaseA.Platform/Data/", "runtime/phase-a/",
    "PhaseA.Platform/Llm/LlmRouteEngine.cs",
    "PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs",
    "scripts/sc/_llm_backend.py", "docs/adr/", "docs/standards/",
)


def _relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{label} is invalid")
    normalized = value.strip().replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if (
        normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise InputError(f"{label} must be repository-relative")
    return PurePosixPath(normalized).as_posix()


def _resolve(root: Path, relative: str, label: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise InputError(f"{label} escapes the repository root") from exc
    return candidate


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_bound_json(
    root: Path, relative: Any, expected_hash: Any, label: str
) -> tuple[str, dict[str, Any]]:
    normalized = _relative_path(relative, label)
    path = _resolve(root, normalized, label)
    if not path.is_file() or _HASH.fullmatch(str(expected_hash)) is None:
        raise InputError(f"{label} binding is invalid")
    if _file_hash(path) != expected_hash:
        raise InputError(f"{label} binding is stale")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"{label} is unreadable") from exc
    if not isinstance(value, dict):
        raise InputError(f"{label} is invalid")
    return normalized, value


def _candidate_path_bindings(candidate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    bindings: dict[str, dict[str, Any]] = {}
    for item in candidate["files"]:
        if item["change_type"] == "unchanged":
            continue
        old_path = item.get("baseline_path")
        new_path = item.get("candidate_path")
        if item["change_type"] in {"deleted", "renamed"} and isinstance(old_path, str):
            bindings[_relative_path(old_path, "candidate baseline path")] = {
                "state": "deleted", "sha256": item["baseline_sha256"],
            }
        elif item["change_type"] == "copied" and isinstance(old_path, str):
            bindings[_relative_path(old_path, "candidate baseline path")] = {
                "state": "present", "sha256": item["baseline_sha256"],
            }
        if isinstance(new_path, str):
            bindings[_relative_path(new_path, "candidate path")] = {
                "state": "present", "sha256": item["candidate_sha256"],
            }
    return bindings


def _bootstrap_module(root: Path) -> Any:
    module_path = root / ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py"
    module_directory = str(module_path.parent)
    spec = importlib.util.spec_from_file_location("repair_bootstrap_review", module_path)
    if spec is None or spec.loader is None:
        raise InputError("Bootstrap control plane is unavailable")
    module = importlib.util.module_from_spec(spec)
    original_path = list(sys.path)
    displaced = {
        name: sys.modules.pop(name)
        for name in ("_control_plane", "knowledge_context")
        if name in sys.modules
    }
    try:
        sys.path[:] = [module_directory, *[item for item in sys.path if item != module_directory]]
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_path
        for name in ("_control_plane", "knowledge_context"):
            sys.modules.pop(name, None)
        sys.modules.update(displaced)
    return module


def _derive_review_escalation(
    root: Path,
    family: str,
    rounds: int,
    predecessor_run: str | None,
    changed_paths: list[str],
) -> tuple[list[str], list[str], list[str]]:
    authority_paths = sorted(
        path
        for path in changed_paths
        if path.endswith(".schema.json")
        or path.endswith("implementation-contract.v1.json")
        or PurePosixPath(path).name == "AGENTS.md"
        or any(path == prefix or path.startswith(prefix) for prefix in _AUTHORITY_PREFIXES)
    )
    high_risk_paths = sorted(
        path
        for path in changed_paths
        if path.endswith(".schema.json")
        or "contract" in PurePosixPath(path).name.lower()
        or any(path == prefix or path.startswith(prefix) for prefix in _HIGH_RISK_PREFIXES)
    )
    if rounds == 0:
        if predecessor_run is not None:
            raise InputError("zero-round repair authority cannot declare a predecessor")
        return [], authority_paths, high_risk_paths
    if not isinstance(predecessor_run, str) or not predecessor_run:
        raise InputError("repair completeness requires the current finalized predecessor run")
    module = _bootstrap_module(root)
    try:
        lineage = module.build_lineage_state(root, family)
        predecessor_dir = module.ensure_within(
            root / predecessor_run, root, "Repair predecessor run"
        )
        manifest = module.read_json(predecessor_dir / "review-input.json")
        if (
            lineage.get("semanticRoundsConsumed") != rounds
            or module.effective_lineage_family(manifest) != family
            or manifest.get("fullReviewRound") != rounds
        ):
            raise InputError("repair predecessor does not match current lineage state")
        predecessor_lineage = module.blocker_finding_lineage(predecessor_dir, manifest)
        prior_lineage: dict[str, str] = {}
        prior_run = manifest.get("predecessorRun")
        if rounds >= NOVEL_FINDING_COMPARISON_ROUND and isinstance(prior_run, str) and prior_run:
            prior_dir = module.ensure_within(root / prior_run, root, "Prior review run")
            prior_manifest = module.read_json(prior_dir / "review-input.json")
            prior_lineage = module.blocker_finding_lineage(prior_dir, prior_manifest)
    except (OSError, ValueError, module.BootstrapError) as exc:
        raise InputError("repair review escalation cannot be reconstructed") from exc
    novel = (
        sorted(
            finding_id
            for identity, finding_id in predecessor_lineage.items()
            if identity not in prior_lineage
        )
        if rounds >= NOVEL_FINDING_COMPARISON_ROUND
        else []
    )
    return novel, authority_paths, high_risk_paths


def _bind_files(root: Path, values: Any, label: str) -> list[dict[str, str]]:
    if not isinstance(values, list) or not values:
        raise InputError(f"{label} must be a non-empty list")
    normalized = sorted({_relative_path(value, label) for value in values})
    bindings: list[dict[str, str]] = []
    for relative in normalized:
        path = _resolve(root, relative, label)
        if not path.is_file():
            raise InputError(f"{label} does not exist: {relative}")
        bindings.append({"path": relative, "sha256": _file_hash(path)})
    return bindings


def _bind_changed_paths(
    root: Path,
    values: Any,
    manifest_bindings: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    if not isinstance(values, list) or not values:
        raise InputError("repair completeness requires changed paths")
    normalized = sorted({_relative_path(value, "changed path") for value in values})
    bindings: list[dict[str, Any]] = []
    for relative in normalized:
        authority = manifest_bindings.get(relative)
        if not isinstance(authority, dict):
            raise InputError(f"changed path is absent from candidate authority: {relative}")
        path = _resolve(root, relative, "changed path")
        expected_state = authority["state"]
        expected_hash = authority["sha256"]
        if expected_state == "present" and path.is_file():
            actual_hash = _file_hash(path)
            if actual_hash != expected_hash:
                raise InputError(f"changed path differs from candidate authority: {relative}")
            bindings.append({"path": relative, "state": "present", "sha256": actual_hash})
        elif expected_state == "present":
            raise InputError(f"candidate changed path is missing: {relative}")
        elif path.exists():
            raise InputError(f"changed path is not a file: {relative}")
        else:
            bindings.append({"path": relative, "state": "deleted", "sha256": expected_hash})
    return normalized, bindings


def discover_callsites(root: Path, search_term: str, search_roots: list[str]) -> list[dict[str, Any]]:
    if not isinstance(search_term, str) or len(search_term.strip()) < 3:
        raise InputError("inventory searchTerm is invalid")
    roots: list[str] = []
    for relative in search_roots:
        candidate = _resolve(root, relative, "inventory search root")
        if not candidate.is_dir():
            raise InputError("inventory search roots must be existing directories")
        roots.append(relative)
    command = ["rg", "--json", "--fixed-strings", "--", search_term, *roots]
    try:
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, encoding="utf-8",
            errors="strict", check=False, timeout=30,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise InputError("ripgrep callsite inventory is unavailable") from exc
    if result.returncode not in {0, 1}:
        raise InputError("ripgrep callsite inventory failed")
    grouped: dict[str, set[int]] = {}
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InputError("ripgrep callsite inventory returned malformed JSON") from exc
        if event.get("type") != "match":
            continue
        try:
            data = event["data"]
            relative = PurePosixPath(data["path"]["text"].replace("\\", "/")).as_posix()
            line_number = int(data["line_number"])
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise InputError("ripgrep callsite inventory returned an invalid match") from exc
        if Path(relative).suffix.lower() not in _TEXT_SUFFIXES:
            continue
        grouped.setdefault(relative, set()).add(line_number)
    return [
        {
            "path": relative,
            "sha256": _file_hash(_resolve(root, relative, "inventory match")),
            "lineNumbers": sorted(grouped[relative]),
        }
        for relative in sorted(grouped)
    ]


def _validate_receipt(
    root: Path,
    relative: str,
    command_id: str,
    registry_relative: str,
    expected_input_paths: list[str],
    required_command_paths: list[str],
) -> tuple[dict[str, str], dict[str, str]]:
    registry_path = _resolve(root, registry_relative, "composition command registry")
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        descriptor = resolve_registered_command(registry, command_id)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ControlError) as exc:
        raise InputError("composition command registry is invalid") from exc
    path = _resolve(root, relative, "composition receipt")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError("composition receipt is unreadable") from exc
    if not isinstance(receipt, dict):
        raise InputError("composition receipt is invalid or failed")
    expected_invocation = {
        "commandId": descriptor["id"],
        "executable": descriptor["executable"],
        "argv": resolve_typed_argv(
            descriptor["argv"],
            descriptor["typed_placeholders"],
            descriptor["placeholder_values"],
            root,
            descriptor["allowed_write_roots"],
        ),
        "cwd": descriptor["cwd"],
        "timeoutSeconds": descriptor["timeout_seconds"],
        "shell": False,
        "environmentAllowlist": descriptor["environment_allowlist"],
    }
    environment_identity = receipt.get("environmentIdentity")
    environment_names = (
        environment_identity.get("names")
        if isinstance(environment_identity, dict)
        else None
    )
    process_result = receipt.get("processResult")
    write_delta = receipt.get("writeManifestDelta")
    valid_write_delta = (
        isinstance(write_delta, dict)
        and set(write_delta) == {"added", "deleted", "modified", "changedPaths"}
        and all(
            isinstance(write_delta.get(field), list)
            and write_delta[field] == sorted(set(write_delta[field]))
            and all(isinstance(item, str) for item in write_delta[field])
            for field in ("added", "deleted", "modified")
        )
        and write_delta.get("changedPaths")
        == write_delta.get("added", [])
        + write_delta.get("deleted", [])
        + write_delta.get("modified", [])
    )
    expected_input_bindings = [
        {"path": item, "sha256": _file_hash(_resolve(root, item, "composition input"))}
        for item in sorted(expected_input_paths)
    ]
    normalized_argv = {
        str(item).replace("\\", "/")
        for item in expected_invocation["argv"]
    }
    command_paths_bound = all(
        relative_path in normalized_argv
        or str((root / relative_path).resolve()).replace("\\", "/") in normalized_argv
        for relative_path in required_command_paths
    )
    if (
        set(receipt) != {
            "schemaVersion", "commandId", "commandRegistryHash",
            "environmentIdentity", "invocation", "invocationHash",
            "processResult", "processResultHash", "exitCode", "authorizes",
            "writeManifestDelta", "writeManifestDeltaHash",
            "inputBindings", "inputBindingsHash",
        }
        or receipt.get("schemaVersion") != "acceptance-controlled-command-receipt.v1"
        or receipt.get("commandId") != command_id
        or receipt.get("exitCode") != 0
        or receipt.get("authorizes") != []
        or receipt.get("commandRegistryHash") != descriptor["registry_hash"]
        or receipt.get("invocation") != expected_invocation
        or receipt.get("invocationHash") != canonical_hash(expected_invocation)
        or not isinstance(environment_names, list)
        or environment_names != sorted(environment_names)
        or any(name not in descriptor["environment_allowlist"] for name in environment_names)
        or environment_identity.get("hash") != canonical_hash(environment_names)
        or not isinstance(process_result, dict)
        or set(process_result)
        != {"commandId", "exitCode", "stdoutSha256", "stderrSha256", "stdout"}
        or process_result.get("commandId") != command_id
        or process_result.get("exitCode") != 0
        or _HASH.fullmatch(str(process_result.get("stdoutSha256"))) is None
        or _HASH.fullmatch(str(process_result.get("stderrSha256"))) is None
        or not isinstance(process_result.get("stdout"), str)
        or receipt.get("processResultHash") != canonical_hash(process_result)
        or not valid_write_delta
        or receipt.get("writeManifestDeltaHash") != canonical_hash(write_delta)
        or receipt.get("inputBindings") != expected_input_bindings
        or receipt.get("inputBindingsHash") != canonical_hash(expected_input_bindings)
        or not command_paths_bound
    ):
        raise InputError("composition receipt is invalid or failed")
    return (
        {"path": relative, "sha256": _file_hash(path)},
        {"path": registry_relative, "sha256": _file_hash(registry_path)},
    )


def _validate_projection_path_list(value: Any, label: str, *, required: bool) -> list[str]:
    if not isinstance(value, list) or (required and not value):
        raise InputError(f"{label} is invalid")
    normalized = [_relative_path(item, label) for item in value]
    if normalized != sorted(set(normalized)):
        raise InputError(f"{label} must be sorted and unique")
    return normalized


def _validate_projection_file_binding(value: Any, label: str) -> str:
    if (
        not isinstance(value, dict)
        or set(value) != {"path", "sha256"}
        or _HASH.fullmatch(str(value.get("sha256"))) is None
    ):
        raise InputError(f"{label} binding is invalid")
    return _relative_path(value.get("path"), label)


def _validate_projection_file_bindings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise InputError(f"{label} bindings are invalid")
    paths = [_validate_projection_file_binding(item, label) for item in value]
    if paths != sorted(set(paths)):
        raise InputError(f"{label} bindings must be sorted and unique")
    return paths


def validate_repair_completeness_projection(value: Any) -> None:
    required = {
        "schemaVersion", "status", "acceptanceTarget", "lineageFamilyId",
        "semanticRoundsConsumed", "predecessorRun", "baselineManifest",
        "candidateManifest", "changedPaths", "changedPathBindings",
        "directConsumers", "targetedTests", "validationRefs",
        "rootCauseInventories", "compositionChecks", "novelP0P1FindingIds",
        "authorityGraphChanged", "authorityGraphArtifacts",
        "highRiskBoundaryChanged", "highRiskBoundaryArtifacts", "requestHash",
        "authorizes",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("schemaVersion") != "acceptance-repair-completeness.v1"
        or value.get("status") != "passed"
        or value.get("authorizes") != []
        or _HASH.fullmatch(str(value.get("requestHash"))) is None
    ):
        raise InputError("repair completeness projection fields are invalid")
    target = _relative_path(value.get("acceptanceTarget"), "acceptance target")
    if not target.startswith("execution-plans/"):
        raise InputError("repair completeness acceptance target is invalid")
    if not isinstance(value.get("lineageFamilyId"), str) or _LINEAGE_ID.fullmatch(value["lineageFamilyId"]) is None:
        raise InputError("repair completeness lineage family is invalid")
    rounds = value.get("semanticRoundsConsumed")
    if (
        not isinstance(rounds, int)
        or isinstance(rounds, bool)
        or not 0 <= rounds <= HARD_FULL_REVIEW_ROUND_LIMIT
    ):
        raise InputError("repair completeness semantic rounds are invalid")
    if not all(
        isinstance(value.get(field), bool)
        for field in ("authorityGraphChanged", "highRiskBoundaryChanged")
    ):
        raise InputError("repair completeness escalation flags are invalid")
    predecessor = value.get("predecessorRun")
    if predecessor is not None:
        _relative_path(predecessor, "repair predecessor")
    _validate_projection_file_binding(value.get("baselineManifest"), "baseline manifest")
    _validate_projection_file_binding(value.get("candidateManifest"), "candidate manifest")
    for field, label in (
        ("authorityGraphArtifacts", "authority graph artifacts"),
        ("highRiskBoundaryArtifacts", "high-risk boundary artifacts"),
    ):
        paths = _validate_projection_path_list(value.get(field), label, required=False)
        expected_flag = "authorityGraphChanged" if field.startswith("authority") else "highRiskBoundaryChanged"
        if value[expected_flag] != bool(paths):
            raise InputError("repair completeness escalation artifacts are inconsistent")

    changed = _validate_projection_path_list(
        value.get("changedPaths"), "changed paths", required=True
    )
    bindings = value.get("changedPathBindings")
    if not isinstance(bindings, list) or len(bindings) != len(changed):
        raise InputError("changed path bindings are invalid")
    bound_paths: list[str] = []
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != {"path", "state", "sha256"}:
            raise InputError("changed path binding fields are invalid")
        bound_paths.append(_relative_path(binding.get("path"), "changed path binding"))
        state, digest = binding.get("state"), binding.get("sha256")
        if state not in {"present", "deleted"} or _HASH.fullmatch(str(digest)) is None:
            raise InputError("changed path binding state is invalid")
    if bound_paths != changed:
        raise InputError("changed path bindings do not match changed paths")

    bound_file_paths: dict[str, list[str]] = {}
    for field, label in (
        ("directConsumers", "direct consumer"),
        ("targetedTests", "targeted test"),
        ("validationRefs", "validation reference"),
    ):
        bound_file_paths[field] = _validate_projection_file_bindings(value.get(field), label)

    inventories = value.get("rootCauseInventories")
    if not isinstance(inventories, list) or not inventories:
        raise InputError("repair completeness inventories are invalid")
    inventory_ids: set[str] = set()
    for inventory in inventories:
        fields = {
            "inventoryId", "searchTerm", "searchRoots", "matches",
            "addressedPaths", "exclusions",
        }
        if not isinstance(inventory, dict) or set(inventory) != fields:
            raise InputError("repair completeness inventory fields are invalid")
        inventory_id = inventory.get("inventoryId")
        if (
            not isinstance(inventory_id, str)
            or _ID.fullmatch(inventory_id) is None
            or inventory_id in inventory_ids
            or not isinstance(inventory.get("searchTerm"), str)
            or not inventory["searchTerm"]
        ):
            raise InputError("repair completeness inventory identity is invalid")
        inventory_ids.add(inventory_id)
        _validate_projection_path_list(
            inventory.get("searchRoots"), "inventory search roots", required=True
        )
        addressed = _validate_projection_path_list(
            inventory.get("addressedPaths"), "addressed paths", required=False
        )
        matches = inventory.get("matches")
        if not isinstance(matches, list):
            raise InputError("repair completeness inventory matches are invalid")
        match_paths: list[str] = []
        for match in matches:
            if (
                not isinstance(match, dict)
                or set(match) != {"path", "sha256", "lineNumbers"}
                or _HASH.fullmatch(str(match.get("sha256"))) is None
                or not isinstance(match.get("lineNumbers"), list)
                or not match["lineNumbers"]
                or any(
                    not isinstance(number, int) or isinstance(number, bool) or number < 1
                    for number in match["lineNumbers"]
                )
                or match["lineNumbers"] != sorted(set(match["lineNumbers"]))
            ):
                raise InputError("repair completeness inventory match is invalid")
            match_paths.append(_relative_path(match.get("path"), "inventory match"))
        if match_paths != sorted(set(match_paths)):
            raise InputError("repair completeness inventory matches are duplicated")
        exclusions = inventory.get("exclusions")
        if not isinstance(exclusions, list):
            raise InputError("repair completeness inventory exclusions are invalid")
        exclusion_paths: list[str] = []
        for exclusion in exclusions:
            if (
                not isinstance(exclusion, dict)
                or set(exclusion) != {"path", "reason"}
                or not isinstance(exclusion.get("reason"), str)
                or not exclusion["reason"].strip()
            ):
                raise InputError("repair completeness inventory exclusion is invalid")
            exclusion_paths.append(
                _relative_path(exclusion.get("path"), "inventory exclusion")
            )
        if exclusion_paths != sorted(set(exclusion_paths)):
            raise InputError("repair completeness inventory exclusions are duplicated")
        if set(match_paths) != set(addressed) | set(exclusion_paths) or set(addressed) & set(exclusion_paths):
            raise InputError("repair completeness inventory disposition is invalid")

    checks = value.get("compositionChecks")
    if not isinstance(checks, list) or not checks:
        raise InputError("repair completeness composition checks are invalid")
    check_ids: set[str] = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) != {
            "checkId", "bindings", "commandRegistry", "receipt"
        }:
            raise InputError("repair completeness composition check fields are invalid")
        check_id = check.get("checkId")
        if not isinstance(check_id, str) or _ID.fullmatch(check_id) is None or check_id in check_ids:
            raise InputError("repair completeness composition check identity is invalid")
        check_ids.add(check_id)
        role_bindings = check.get("bindings")
        if not isinstance(role_bindings, list) or len(role_bindings) < 2:
            raise InputError("repair completeness composition bindings are invalid")
        roles: set[str] = set()
        identities: set[tuple[str, str]] = set()
        role_paths: dict[str, set[str]] = {"producer": set(), "consumer": set()}
        for binding in role_bindings:
            if (
                not isinstance(binding, dict)
                or set(binding) != {"role", "path", "sha256"}
                or binding.get("role") not in {"producer", "consumer"}
                or _HASH.fullmatch(str(binding.get("sha256"))) is None
            ):
                raise InputError("repair completeness composition binding is invalid")
            path = _relative_path(binding.get("path"), "composition binding")
            identity = (binding["role"], path)
            if identity in identities:
                raise InputError("repair completeness composition binding is duplicated")
            identities.add(identity)
            roles.add(binding["role"])
            role_paths[binding["role"]].add(path)
        if roles != {"producer", "consumer"}:
            raise InputError("repair completeness composition roles are incomplete")
        if not (role_paths["producer"] | role_paths["consumer"]) & set(changed):
            raise InputError("repair completeness composition does not cover a changed path")
        if not role_paths["consumer"].issubset(set(bound_file_paths["directConsumers"])):
            raise InputError("repair completeness composition consumers are not declared direct consumers")
        _validate_projection_file_binding(check.get("commandRegistry"), "command registry")
        receipt_path = _validate_projection_file_binding(
            check.get("receipt"), "composition receipt"
        )
        if receipt_path not in bound_file_paths["validationRefs"]:
            raise InputError("repair completeness composition receipt is not a validation reference")

    novel = value.get("novelP0P1FindingIds")
    if (
        not isinstance(novel, list)
        or any(not isinstance(item, str) or _FINDING_ID.fullmatch(item) is None for item in novel)
        or novel != sorted(set(novel))
    ):
        raise InputError("repair completeness novel finding identities are invalid")


def audit_repair_completeness(request: Any) -> dict[str, Any]:
    required = {
        "schemaVersion", "repositoryRoot", "lineageFamilyId", "semanticRoundsConsumed",
        "acceptanceTarget", "predecessorRun", "baselineManifestPath", "baselineManifestHash",
        "candidateManifestPath", "candidateManifestHash", "changedPaths",
        "directConsumers", "targetedTests", "validationRefs",
        "rootCauseInventories", "compositionChecks",
        "novelP0P1FindingIds", "authorityGraphChanged", "highRiskBoundaryChanged",
        "authorizes",
    }
    if not isinstance(request, dict) or set(request) != required:
        raise InputError("repair completeness request fields are invalid")
    root_value = request.get("repositoryRoot")
    if not isinstance(root_value, str) or not root_value.strip():
        raise InputError("repair completeness repository root is invalid")
    root = Path(root_value).resolve()
    if not root.is_dir() or request.get("schemaVersion") != "acceptance-repair-completeness-request.v1":
        raise InputError("repair completeness request root or schema is invalid")
    acceptance_target = _relative_path(request.get("acceptanceTarget"), "acceptance target")
    if not acceptance_target.startswith("execution-plans/"):
        raise InputError("acceptance target must be under execution-plans")
    if not _resolve(root, acceptance_target, "acceptance target").exists():
        raise InputError("acceptance target does not exist")
    baseline_path, baseline = _load_bound_json(
        root,
        request.get("baselineManifestPath"),
        request.get("baselineManifestHash"),
        "baseline manifest",
    )
    candidate_path, candidate = _load_bound_json(
        root,
        request.get("candidateManifestPath"),
        request.get("candidateManifestHash"),
        "candidate manifest",
    )
    validate_candidate_manifest(candidate, baseline)
    if candidate.get("status") != "complete" or candidate.get("coverageGaps") != []:
        raise InputError("repair candidate manifest must be complete")
    authoritative_changed = candidate_changed_paths(candidate)
    requested_changed = sorted(
        {_relative_path(path, "changed path") for path in request.get("changedPaths", [])}
    )
    if requested_changed != authoritative_changed:
        raise InputError("changed paths do not match the complete candidate manifest")
    candidate_bindings = _candidate_path_bindings(candidate)
    family = request.get("lineageFamilyId")
    rounds = request.get("semanticRoundsConsumed")
    if not isinstance(family, str) or _LINEAGE_ID.fullmatch(family) is None:
        raise InputError("repair completeness lineageFamilyId is invalid")
    if (
        not isinstance(rounds, int)
        or isinstance(rounds, bool)
        or not 0 <= rounds <= HARD_FULL_REVIEW_ROUND_LIMIT
    ):
        raise InputError("repair completeness semantic round count is invalid")
    if request.get("authorizes") != [] or not all(
        isinstance(request.get(field), bool)
        for field in ("authorityGraphChanged", "highRiskBoundaryChanged")
    ):
        raise InputError("repair completeness authority boundary is invalid")
    novel_findings = request.get("novelP0P1FindingIds")
    if (
        not isinstance(novel_findings, list)
        or any(not isinstance(item, str) or _FINDING_ID.fullmatch(item) is None for item in novel_findings)
        or len(novel_findings) != len(set(novel_findings))
    ):
        raise InputError("novel P0/P1 finding identities are invalid")
    predecessor_run_value = request.get("predecessorRun")
    predecessor_run = (
        _relative_path(predecessor_run_value, "repair predecessor")
        if predecessor_run_value is not None
        else None
    )
    derived_novel, authority_artifacts, high_risk_artifacts = _derive_review_escalation(
        root, family, rounds, predecessor_run, authoritative_changed
    )
    if sorted(novel_findings) != derived_novel:
        raise InputError("novel P0/P1 finding identities are not repository-derived")
    if request["authorityGraphChanged"] != bool(authority_artifacts):
        raise InputError("authority graph escalation flag is not repository-derived")
    if request["highRiskBoundaryChanged"] != bool(high_risk_artifacts):
        raise InputError("high-risk escalation flag is not repository-derived")
    changed, changed_bindings = _bind_changed_paths(
        root, authoritative_changed, candidate_bindings
    )
    direct_consumers = _bind_files(root, request.get("directConsumers"), "direct consumer")
    targeted_tests = _bind_files(root, request.get("targetedTests"), "targeted test")
    targeted_test_paths = {item["path"] for item in targeted_tests}
    validation_refs = _bind_files(root, request.get("validationRefs"), "validation reference")
    direct_consumer_paths = {item["path"] for item in direct_consumers}
    validation_ref_paths = {item["path"] for item in validation_refs}
    inventories = request.get("rootCauseInventories")
    if not isinstance(inventories, list) or not inventories:
        raise InputError("repair completeness requires a root-cause inventory")
    inventory_results: list[dict[str, Any]] = []
    seen_inventory_ids: set[str] = set()
    covered_changed_sources: set[str] = set()
    for inventory in inventories:
        fields = {"inventoryId", "searchTerm", "searchRoots", "addressedPaths", "exclusions"}
        if not isinstance(inventory, dict) or set(inventory) != fields:
            raise InputError("root-cause inventory fields are invalid")
        inventory_id = inventory.get("inventoryId")
        if not isinstance(inventory_id, str) or _ID.fullmatch(inventory_id) is None or inventory_id in seen_inventory_ids:
            raise InputError("root-cause inventory identity is invalid")
        seen_inventory_ids.add(inventory_id)
        search_roots = sorted({_relative_path(path, "inventory search root") for path in inventory.get("searchRoots", [])})
        addressed = sorted({_relative_path(path, "addressed callsite") for path in inventory.get("addressedPaths", [])})
        if not search_roots or any(path not in changed for path in addressed):
            raise InputError("addressed callsites must be changed paths")
        exclusions_value = inventory.get("exclusions")
        if not isinstance(exclusions_value, list):
            raise InputError("root-cause exclusions are invalid")
        exclusions: dict[str, str] = {}
        for exclusion in exclusions_value:
            if not isinstance(exclusion, dict) or set(exclusion) != {"path", "reason"}:
                raise InputError("root-cause exclusion fields are invalid")
            path = _relative_path(exclusion.get("path"), "excluded callsite")
            reason = exclusion.get("reason")
            if not isinstance(reason, str) or not reason.strip() or path in exclusions:
                raise InputError("root-cause exclusion is incomplete or duplicated")
            exclusions[path] = reason.strip()
        matches = discover_callsites(root, inventory.get("searchTerm"), search_roots)
        matched_paths = {item["path"] for item in matches}
        if not matches or not (matched_paths & set(changed)):
            raise InputError("root-cause inventory must match at least one changed path")
        if matched_paths != set(addressed) | set(exclusions):
            raise InputError("root-cause inventory does not dispose every discovered callsite")
        covered_changed_sources.update(matched_paths & set(changed))
        inventory_results.append(
            {
                "inventoryId": inventory_id,
                "searchTerm": inventory["searchTerm"],
                "searchRoots": search_roots,
                "matches": matches,
                "addressedPaths": addressed,
                "exclusions": [
                    {"path": path, "reason": exclusions[path]} for path in sorted(exclusions)
                ],
            }
        )
    required_changed_sources = {
        path
        for path, binding in candidate_bindings.items()
        if binding["state"] == "present" and Path(path).suffix.lower() in _SOURCE_SUFFIXES
    }
    if not required_changed_sources.issubset(covered_changed_sources):
        missing = sorted(required_changed_sources - covered_changed_sources)
        raise InputError(
            "root-cause inventories do not cover every changed source path: "
            + ", ".join(missing)
        )
    checks = request.get("compositionChecks")
    if not isinstance(checks, list) or not checks:
        raise InputError("repair completeness requires producer/consumer composition checks")
    check_results: list[dict[str, Any]] = []
    seen_check_ids: set[str] = set()
    for check in checks:
        fields = {
            "checkId", "producerPaths", "consumerPaths", "receiptPath",
            "commandRegistryPath",
        }
        if not isinstance(check, dict) or set(check) != fields:
            raise InputError("composition check fields are invalid")
        check_id = check.get("checkId")
        if not isinstance(check_id, str) or _ID.fullmatch(check_id) is None or check_id in seen_check_ids:
            raise InputError("composition check identity is invalid")
        seen_check_ids.add(check_id)
        producers = sorted({_relative_path(path, "producer path") for path in check.get("producerPaths", [])})
        consumers = sorted({_relative_path(path, "consumer path") for path in check.get("consumerPaths", [])})
        if not producers or not consumers:
            raise InputError("composition check requires producers and consumers")
        if not (set(producers) | set(consumers)) & set(changed):
            raise InputError("composition check does not cover a changed path")
        if not set(consumers).issubset(direct_consumer_paths):
            raise InputError("composition consumers must be declared direct consumers")
        bindings = []
        for role, paths in (("producer", producers), ("consumer", consumers)):
            for relative in paths:
                path = _resolve(root, relative, f"composition {role}")
                if not path.is_file():
                    raise InputError(f"composition {role} does not exist: {relative}")
                bindings.append({"role": role, "path": relative, "sha256": _file_hash(path)})
        receipt_path = _relative_path(check.get("receiptPath"), "composition receipt")
        if receipt_path not in validation_ref_paths:
            raise InputError("composition receipt must be a validation reference")
        registry_path = _relative_path(
            check.get("commandRegistryPath"), "composition command registry"
        )
        receipt_binding, registry_binding = _validate_receipt(
            root,
            receipt_path,
            check_id,
            registry_path,
            sorted(set(producers) | set(consumers) | targeted_test_paths),
            sorted(targeted_test_paths),
        )
        check_results.append(
            {
                "checkId": check_id,
                "bindings": bindings,
                "commandRegistry": registry_binding,
                "receipt": receipt_binding,
            }
        )
    result = {
        "schemaVersion": "acceptance-repair-completeness.v1",
        "status": "passed",
        "acceptanceTarget": acceptance_target,
        "lineageFamilyId": family,
        "semanticRoundsConsumed": rounds,
        "predecessorRun": predecessor_run,
        "baselineManifest": {"path": baseline_path, "sha256": request["baselineManifestHash"]},
        "candidateManifest": {"path": candidate_path, "sha256": request["candidateManifestHash"]},
        "changedPaths": changed,
        "changedPathBindings": changed_bindings,
        "directConsumers": direct_consumers,
        "targetedTests": targeted_tests,
        "validationRefs": validation_refs,
        "rootCauseInventories": inventory_results,
        "compositionChecks": check_results,
        "novelP0P1FindingIds": sorted(novel_findings),
        "authorityGraphChanged": request["authorityGraphChanged"],
        "authorityGraphArtifacts": authority_artifacts,
        "highRiskBoundaryChanged": request["highRiskBoundaryChanged"],
        "highRiskBoundaryArtifacts": high_risk_artifacts,
        "requestHash": canonical_hash(request),
        "authorizes": [],
    }
    validate_repair_completeness_projection(result)
    return result
