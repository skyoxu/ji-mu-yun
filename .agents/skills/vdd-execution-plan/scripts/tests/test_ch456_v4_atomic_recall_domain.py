from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_feasibility_patch  # noqa: F401  # installs stable V4 patches
import semantic_compiler_gate as gate
import semantic_worker_v4_domain_patch as v4_domain
from semantic_atomic_recall_result_patch import _normalize_result


def _payload() -> dict:
    return {
        "source_index": {
            "entries": [
                {"source_ref": "req.md#FR-1"},
                {"source_ref": "req.md#FR-2"},
            ]
        },
        "obligations": [
            {"obligation_id": "O-1", "status": "active"},
            {"obligation_id": "O-2", "status": "active"},
            {"obligation_id": "O-DEFERRED", "status": "deferred"},
        ],
    }


def test_v4_structured_schema_is_closed_over_frozen_active_ids_and_source_refs() -> None:
    schema = v4_domain._output_schema("v4-atomic-recall", _payload())
    supported = schema["properties"]["supported_obligation_ids"]["items"]["enum"]
    invented = schema["properties"]["invented_obligation_ids"]["items"]["enum"]
    source_ref = schema["properties"]["source_gap_claims"]["items"]["properties"]["source_ref"]["enum"]
    assert supported == ["O-1", "O-2"]
    assert invented == ["O-1", "O-2"]
    assert source_ref == ["req.md#FR-1", "req.md#FR-2"]


def test_unknown_supported_id_routes_through_existing_single_repair(tmp_path: Path) -> None:
    payload = _payload()
    invalid = {
        "supported_obligation_ids": ["O-1", "O-2", "O-UNKNOWN"],
        "invented_obligation_ids": [],
        "source_gap_claims": [],
    }
    repaired = {
        "supported_obligation_ids": ["O-1", "O-2"],
        "invented_obligation_ids": [],
        "source_gap_claims": [],
    }
    result = gate.normative_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v4-atomic-recall",
        payload=payload,
        prompt="Classify only frozen obligation ids.",
        worker_cache={
            "v4-atomic-recall": invalid,
            "v4-atomic-recall-schema-repair": repaired,
        },
    )
    assert result == repaired


def test_empty_partition_diagnostic_is_removed_but_unknown_id_stays_blocking() -> None:
    result = _normalize_result({
        "valid": False,
        "findings": [
            "atomic-recall:unknown-supported:O-UNKNOWN",
            "atomic-recall:obligation-partition-incomplete:",
        ],
        "worker": {"supported_obligation_ids": ["O-1", "O-UNKNOWN"]},
    })
    assert result["valid"] is False
    assert result["findings"] == ["atomic-recall:unknown-supported:O-UNKNOWN"]
    assert result["protocol_metrics"]["unknown_supported_finding_count"] == 1
