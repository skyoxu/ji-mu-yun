"""Narrow V7 compatibility patch for explicitly planned new RED files.

The canonical Chapter 4/5/6 protocol permits a selector/test/fixture path to be
absent at plan-ready only when that exact path is declared in
`planned_new_files`; Q2 then owns its materialization. Existing production
owners must still resolve to a real entry and every other missing snapshot path
remains fail-closed.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import semantic_compiler as sc

_ORIGINAL_FEASIBILITY = sc.feasibility


def feasibility_with_planned_red_files(
    root,
    slices: Sequence[Mapping[str, Any]],
    acceptances: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    hints_by_acceptance: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    result = dict(_ORIGINAL_FEASIBILITY(root, slices, acceptances, failures, hints_by_acceptance))
    planned_by_slice = {
        str(item.get("slice_id")): {str(path) for path in item.get("planned_new_files", [])}
        for item in slices
        if isinstance(item, Mapping)
    }
    findings: list[str] = []
    for raw in result.get("findings", []):
        finding = str(raw)
        parts = finding.split(":", 2)
        if len(parts) == 3 and parts[1] == "selector-target-missing":
            slice_id, missing_path = parts[0], parts[2]
            if missing_path in planned_by_slice.get(slice_id, set()):
                continue
        findings.append(finding)
    return {
        **result,
        "valid": not findings,
        "recommended_action": "plan-ready" if not findings else "repair-vdd",
        "findings": findings,
    }


def install() -> None:
    sc.feasibility = feasibility_with_planned_red_files


install()
