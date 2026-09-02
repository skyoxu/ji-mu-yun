"""Validate V3 semantic coverage and executable hint contracts before normalization.

The canonical compiler already rejects these defects later in V3A/V7.  This
patch moves the same deterministic facts to the live worker boundary so the
existing single schema-repair attempt can correct the candidate once.  It never
fills paths, merges semantics, or drops obligations locally.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import semantic_compiler_gate as gate
import semantic_worker_v3_group_repair_patch  # noqa: F401  # relation-safe repair first

_BASE_TRANSPORT = gate._ORIGINAL_INVOKE_WORKER


def _input_payload(stage: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if stage.startswith("v3-schema-repair"):
        value = payload.get("input")
        return value if isinstance(value, Mapping) else {}
    return payload


def _obligations(stage: str, payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = _input_payload(stage, payload).get("obligations")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def _string_list(value: Any, *, nonempty: bool = False) -> list[str] | None:
    if not isinstance(value, list) or (nonempty and not value):
        return None
    if any(not isinstance(item, str) or not item.strip() for item in value):
        return None
    return [item.strip() for item in value]


def _safe_path(root: Path, raw: str) -> Path | None:
    try:
        path = (root / raw).resolve()
        path.relative_to(root.resolve())
        return path
    except (OSError, ValueError):
        return None


def _findings(root: Path, stage: str, payload: Mapping[str, Any], value: Mapping[str, Any]) -> list[str]:
    if stage != "v3" and not stage.startswith("v3-schema-repair"):
        return []
    obligations = _obligations(stage, payload)
    by_id = {
        str(item.get("obligation_id")): item
        for item in obligations
        if isinstance(item.get("obligation_id"), str) and str(item.get("obligation_id"))
    }
    active = {
        oid for oid, item in by_id.items()
        if item.get("status") == "active"
    }
    findings: list[str] = []

    acceptances = value.get("acceptances")
    covered: set[str] = set()
    if isinstance(acceptances, list):
        for index, raw in enumerate(acceptances):
            if not isinstance(raw, Mapping):
                continue
            ids = _string_list(raw.get("obligation_ids"), nonempty=True)
            if ids is None:
                continue
            covered.update(oid for oid in ids if oid in by_id)
            subjects = {
                str(by_id[oid].get("subject"))
                for oid in ids
                if oid in by_id and isinstance(by_id[oid].get("subject"), str)
            }
            if len(ids) > 1 and len(subjects) > 1:
                findings.append(
                    f"v3-contract:acceptances[{index}]:overbroad-subject:" + ",".join(sorted(subjects))
                )
    missing = active - covered
    if missing:
        findings.append("v3-contract:hard-uncovered:" + ",".join(sorted(missing)))

    hints = value.get("slice_hints")
    if isinstance(hints, list):
        for index, raw in enumerate(hints):
            if not isinstance(raw, Mapping):
                continue
            owners = _string_list(raw.get("production_owners"), nonempty=True)
            allowed = _string_list(raw.get("allowed_write_paths"))
            planned = _string_list(raw.get("planned_new_files"))
            snapshots = _string_list(raw.get("execution_snapshot_paths"), nonempty=True)
            if owners is None or allowed is None or planned is None or snapshots is None:
                continue
            allowed_set = set(allowed)
            planned_set = set(planned)
            existing_owner = False
            for owner in owners:
                path = _safe_path(root, owner)
                if path is not None and path.is_file() and not path.is_symlink():
                    existing_owner = True
                    if owner not in allowed_set:
                        findings.append(
                            f"v3-contract:slice_hints[{index}]:owner-outside-write-set:{owner}"
                        )
            if not existing_owner:
                findings.append(f"v3-contract:slice_hints[{index}]:no-real-production-entry")
            for snapshot in snapshots:
                path = _safe_path(root, snapshot)
                exists = path is not None and path.is_file() and not path.is_symlink()
                if not exists and snapshot not in planned_set:
                    findings.append(
                        f"v3-contract:slice_hints[{index}]:selector-target-missing-not-planned:{snapshot}"
                    )
            commands = raw.get("validation_commands")
            if isinstance(commands, list) and snapshots:
                flat = [str(part) for command in commands if isinstance(command, list) for part in command]
                if not any(snapshot in flat for snapshot in snapshots):
                    findings.append(
                        f"v3-contract:slice_hints[{index}]:validation-command-unbound-to-snapshot"
                    )
    return findings


def execution_contract_transport(
    *,
    root,
    out_dir,
    stage: str,
    payload: Mapping[str, Any],
    prompt: str,
    worker_cache: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    value = _BASE_TRANSPORT(
        root=root,
        out_dir=out_dir,
        stage=stage,
        payload=payload,
        prompt=prompt,
        worker_cache=worker_cache,
    )
    findings = _findings(Path(root), stage, payload, value)
    if findings:
        raise ValueError("V3 execution-contract validation failed: " + "; ".join(findings))
    return value


def install() -> None:
    gate._ORIGINAL_INVOKE_WORKER = execution_contract_transport


install()
