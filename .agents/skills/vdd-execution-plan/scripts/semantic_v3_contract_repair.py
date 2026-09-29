"""ADR-0041: explicit V3 candidate repairs, never worker or readiness evidence."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import semantic_worker_v3_group_repair_patch as group


def load_repair(path: Path, requirements: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {
        "schema", "requirements_sha256", "authorizes", "obligation_contracts"
    }:
        raise ValueError("V3 candidate repair fields are invalid")
    if value["schema"] != "vdd.v3-candidate-repair.v1" or value["authorizes"] != []:
        raise ValueError("V3 candidate repair is non-authorizing input only")
    digest = "sha256:" + hashlib.sha256(requirements.read_bytes()).hexdigest()
    if value["requirements_sha256"] != digest:
        raise ValueError("V3 candidate repair requirements identity is stale")
    contracts = value["obligation_contracts"]
    if not isinstance(contracts, dict) or not contracts:
        raise ValueError("V3 candidate repair has no contracts")
    # Validate the existing inline contract shape; no alternate compiler schema.
    group._project_current_output({"obligation_contracts": contracts}, {
        oid: contract.get("acceptance", {}).get("source_refs", [])
        for oid, contract in contracts.items() if isinstance(contract, Mapping)
    })
    return value


def apply_repair(value: Mapping[str, Any], payload: Mapping[str, Any],
                 repair: Mapping[str, Any], root: Path) -> dict[str, Any]:
    refs = group._obligation_refs(payload)
    targets = set(refs) & set(repair["obligation_contracts"])
    if not targets:
        return deepcopy(dict(value))
    replacements = {oid: repair["obligation_contracts"][oid] for oid in sorted(targets)}
    for oid, contract in replacements.items():
        if sorted(contract["acceptance"]["source_refs"]) != sorted(refs[oid]):
            raise ValueError("V3 candidate repair source binding mismatch: " + oid)
    projected = group._project_current_output(
        {"obligation_contracts": replacements}, {oid: refs[oid] for oid in targets})
    merged = deepcopy(dict(value))
    for field in ("acceptances", "failure_intents", "slice_hints"):
        kept = []
        observed = set()
        for item in merged[field]:
            ids = set(item.get("obligation_ids", []))
            if ids & targets:
                if len(ids) != 1:
                    raise ValueError("V3 candidate repair cannot split a shared contract")
                observed.update(ids)
            else:
                kept.append(item)
        if observed != targets:
            raise ValueError("V3 candidate repair target missing from " + field)
        merged[field] = kept + projected[field]
    findings = group.v3_domain._domain_findings("v3-schema-repair", payload, merged)
    if findings or group.sc._v3_cache_requires_contract_refresh(merged, root, payload):
        raise ValueError("V3 repaired candidate fails contract validation: " + "; ".join(findings))
    return merged


def install(repair: Mapping[str, Any]) -> None:
    """Install only from the canonical CLI, before compilation starts.

    Raw caches remain untouched. Repaired candidates pass the normal V3 gates,
    deterministic ID construction, V4 independent review and downstream gates.
    Source-gap expansion may revisit V3; the same bounded overlay is idempotent.
    """
    original_invoke = group.sc.invoke_worker
    original_align = group.sc.semantic_align

    def repaired_worker(*, root, out_dir, stage, payload, prompt, worker_cache=None):
        value = original_invoke(root=root, out_dir=out_dir, stage=stage, payload=payload,
                                prompt=prompt, worker_cache=worker_cache)
        if stage != "v3":
            return value
        payload = {"original_stage": "v3", "input": payload}
        merged = apply_repair(value, payload, repair, Path(root))
        receipt = {
            "schema": "vdd.v3-candidate-repair-projection.v1",
            "authorizes": [], "candidate_sha256": group.sc.sha256_value(merged),
            "input_sha256": group.sc.sha256_value(payload),
            "repair": repair,
            "applied_obligation_ids": sorted(set(group._obligation_refs(payload)) &
                                             set(repair["obligation_contracts"])),
        }
        digest = group.sc.sha256_value(receipt).removeprefix("sha256:")
        target = Path(out_dir) / ".compiler-work" / "candidate-repairs" / (digest + ".json")
        if target.exists():
            if json.loads(target.read_text(encoding="utf-8")) != receipt:
                raise ValueError("V3 candidate repair projection is not append-only")
        else:
            group.sc.atomic_json(target, receipt)
        return merged

    def checked_alignment(**kwargs):
        targets = set(repair["obligation_contracts"])
        active = {o["obligation_id"] for o in kwargs["obligations"] if o.get("status") == "active"}
        if not targets <= active:
            raise ValueError("V3 candidate repair targets absent from final active domain")
        for oid, contract in repair["obligation_contracts"].items():
            matches = [a for a in kwargs["acceptances"] if a.get("obligation_ids") == [oid]]
            if len(matches) != 1 or sorted(matches[0]["assertion_ids"]) != sorted(contract["acceptance"]["assertion_ids"]):
                raise ValueError("V3 candidate repair was not consumed: " + oid)
        return original_align(**kwargs)

    group.sc.invoke_worker = repaired_worker
    group.sc.semantic_align = checked_alignment
