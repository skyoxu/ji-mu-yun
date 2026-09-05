"""Validate and narrow-repair V3 semantics before the expensive global repair lane.

The canonical compiler still owns every truth gate. This wrapper only performs
two deterministic/bounded normalizations before emitting V3 execution-contract
findings:

* one-obligation contracts remain unchanged; shared multi-obligation oracles
  are rejected for the existing schema-repair lane rather than cloned;
* genuinely uncovered obligations use the existing missing-only semantic
  completion lane.

If the candidate is relationally ambiguous, references unknown obligations, or
still violates owner/path/semantic contracts after those steps, it is left to
the existing fail-closed schema-repair path. No finding is suppressed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import semantic_compiler_gate as gate
import semantic_worker_v3_group_repair_patch  # noqa: F401  # relation-safe repair first
import semantic_worker_v3_total_coverage_patch as total_coverage

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


def _atomicize_initial_candidate(stage: str, payload: Mapping[str, Any], value: Mapping[str, Any]) -> Mapping[str, Any]:
    """ADR-0041: preserve worker semantics; never clone a group oracle into atomic proof.

    Multi-obligation candidates are rejected by _findings and use the existing
    one-shot schema repair. Singleton candidates need no semantic projection.
    """
    return value


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
    active = {oid for oid, item in by_id.items() if item.get("status") == "active"}
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
            if len(ids) != 1:
                findings.append(f"v3-contract:acceptances[{index}]:per-obligation-contract-required")
            covered.update(oid for oid in ids if oid in by_id)
            known = [oid for oid in ids if oid in by_id]
            subjects = {
                str(by_id[oid].get("subject"))
                for oid in known
                if isinstance(by_id[oid].get("subject"), str)
            }
            if len(ids) > 1 and len(subjects) > 1:
                findings.append(f"v3-contract:acceptances[{index}]:overbroad-subject:" + ",".join(sorted(subjects)))
            semantic_shapes = {
                (str(by_id[oid].get("subject")), str(by_id[oid].get("state_before")), str(by_id[oid].get("state_after")))
                for oid in known
            }
            if len(semantic_shapes) > 1:
                findings.append(f"v3-contract:acceptances[{index}]:overbroad-independent-behavior")
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
                        findings.append(f"v3-contract:slice_hints[{index}]:owner-outside-write-set:{owner}")
            if not existing_owner:
                findings.append(f"v3-contract:slice_hints[{index}]:no-real-production-entry")
            for snapshot in snapshots:
                path = _safe_path(root, snapshot)
                exists = path is not None and path.is_file() and not path.is_symlink()
                if not exists and snapshot not in planned_set:
                    findings.append(f"v3-contract:slice_hints[{index}]:selector-target-missing-not-planned:{snapshot}")
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
    value = _atomicize_initial_candidate(stage, payload, value)
    if stage == "v3" or stage.startswith("v3-schema-repair"):
        value = total_coverage.complete_total_coverage(
            root=root,
            out_dir=out_dir,
            stage=stage,
            payload=payload,
            value=value,
            worker_cache=worker_cache,
        )
    findings = _findings(Path(root), stage, payload, value)
    if findings:
        raise ValueError("V3 execution-contract validation failed: " + "; ".join(findings))
    return value


def install() -> None:
    gate._ORIGINAL_INVOKE_WORKER = execution_contract_transport


install()
