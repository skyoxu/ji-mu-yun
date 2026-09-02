"""Narrow V7 compatibility patch for explicitly planned new RED files.

The canonical Chapter 4/5/6 protocol permits a selector/test/fixture path to be
absent at plan-ready only when that exact path is declared in
`planned_new_files`; Q2 then owns its materialization. Existing production
owners must still resolve to a real entry and every other missing snapshot path
remains fail-closed.

Importing this stable compatibility layer also installs the semantic-worker
transport and contract patches so every stable compiler authority caller uses
the same live V1/V3 structured transport, field, relational, domain, grouped
repair, repaired owner/write-set projection, execution-contract, atomic-gap
repair, and bounded independent V4 alignment semantics.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import semantic_compiler as sc
import semantic_worker_transport_patch  # noqa: F401  # structured JSON + bounded repair transport
import semantic_worker_v3_domain_patch  # noqa: F401  # frozen obligation/source domain for V3
import semantic_worker_v3_group_repair_patch  # noqa: F401  # relation-safe one-shot V3 repair
import semantic_worker_v3_group_prompt_patch  # noqa: F401  # explicit grouped repair invariants
import semantic_worker_v3_write_set_projection_patch  # noqa: F401  # owner/write-set identity in repaired groups
import semantic_worker_v3_execution_contract_patch  # noqa: F401  # V3A/V7 facts at worker boundary
import semantic_worker_contract_patch  # noqa: F401  # stable live worker field contract
import semantic_worker_relational_patch  # noqa: F401  # stable live V3 relational contract
import semantic_worker_v4_domain_patch  # noqa: F401  # frozen-id V4 atomic-recall contract
import semantic_atomic_recall_result_patch  # noqa: F401  # exact V4 partition diagnostics
import semantic_obligation_gap_repair_patch  # noqa: F401  # one bounded V1 repair for proven source gaps
import semantic_alignment_repair_patch  # noqa: F401  # bounded Acceptance-only repair + independent recheck

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
