from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_feasibility_patch  # noqa: F401  # installs full stable patch chain
import semantic_worker_v3_execution_contract_patch as execution_contract
import semantic_worker_v3_group_repair_patch as grouped
import semantic_worker_v3_group_safety_patch as safety
import semantic_worker_v4_domain_patch as v4_domain


def test_final_transport_composition_preserves_group_safety_before_v3_execution_contract() -> None:
    assert safety._BASE_GROUP_TRANSPORT is grouped.group_repair_transport
    assert execution_contract._BASE_TRANSPORT is safety.group_safety_transport
    assert v4_domain._BASE_TRANSPORT is execution_contract.execution_contract_transport
