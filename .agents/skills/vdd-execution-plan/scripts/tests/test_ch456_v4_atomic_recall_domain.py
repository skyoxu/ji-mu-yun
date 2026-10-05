from __future__ import annotations

from pathlib import Path
import sys
import pytest

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
    assert "uniqueItems" not in schema["properties"]["supported_obligation_ids"]
    assert "uniqueItems" not in schema["properties"]["invented_obligation_ids"]


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


def test_duplicate_ids_remain_a_deterministic_domain_failure() -> None:
    findings = v4_domain._domain_findings(
        "v4-atomic-recall",
        _payload(),
        {
            "supported_obligation_ids": ["O-1", "O-1", "O-2"],
            "invented_obligation_ids": [],
            "source_gap_claims": [],
        },
    )
    assert findings == ["supported_obligation_ids:duplicate-frozen-id:O-1"]


def test_overlapping_partition_routes_through_existing_single_repair(tmp_path: Path) -> None:
    result = gate.normative_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v4-atomic-recall",
        payload=_payload(),
        prompt="Classify only frozen obligation ids.",
        worker_cache={
            "v4-atomic-recall": {
                "supported_obligation_ids": ["O-1", "O-2"],
                "invented_obligation_ids": ["O-2"],
                "source_gap_claims": [],
            },
            "v4-atomic-recall-schema-repair": {
                "supported_obligation_ids": ["O-1", "O-2"],
                "invented_obligation_ids": [],
                "source_gap_claims": [],
            },
        },
    )
    assert result == {
        "supported_obligation_ids": ["O-1", "O-2"],
        "invented_obligation_ids": [],
        "source_gap_claims": [],
    }


def test_incomplete_frozen_partition_requires_repair() -> None:
    findings = v4_domain._domain_findings(
        "v4-atomic-recall",
        _payload(),
        {"supported_obligation_ids": ["O-1"], "invented_obligation_ids": [], "source_gap_claims": []},
    )
    assert findings == ["obligation-partition-incomplete:O-2"]


def test_partition_completion_merges_only_the_missing_frozen_id() -> None:
    merged = v4_domain._merge_partition_completion(
        _payload(),
        {
            "supported_obligation_ids": ["O-1"],
            "invented_obligation_ids": [],
            "source_gap_claims": [
                {
                    "source_ref": "req.md#FR-1",
                    "subject": "compiler",
                    "behavior": "emits plan",
                    "reason": "missing obligation",
                }
            ],
        },
        {
            "supported_obligation_ids": [],
            "invented_obligation_ids": ["O-2"],
        },
    )
    assert merged == {
        "supported_obligation_ids": ["O-1"],
        "invented_obligation_ids": ["O-2"],
        "source_gap_claims": [
            {
                "source_ref": "req.md#FR-1",
                "subject": "compiler",
                "behavior": "emits plan",
                "reason": "missing obligation",
            }
        ],
    }


def test_incomplete_partition_repairs_only_missing_id_through_transport(tmp_path: Path) -> None:
    result = gate.normative_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v4-atomic-recall",
        payload=_payload(),
        prompt="Classify only frozen obligation ids.",
        worker_cache={
            "v4-atomic-recall": {
                "supported_obligation_ids": ["O-1"],
                "invented_obligation_ids": [],
                "source_gap_claims": [],
            },
            "v4-atomic-recall-partition-repair": {
                "supported_obligation_ids": [],
                "invented_obligation_ids": ["O-2"],
            },
        },
    )
    assert result == {
        "supported_obligation_ids": ["O-1"],
        "invented_obligation_ids": ["O-2"],
        "source_gap_claims": [],
    }


def test_schema_repair_partial_partition_repairs_only_missing_id(tmp_path: Path) -> None:
    result = v4_domain.v4_transport_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v4-atomic-recall-schema-repair",
        payload={"input": _payload(), "validator_findings": ["worker-call:RuntimeError:timeout"]},
        prompt="Return a corrected JSON object only.",
        worker_cache={
            "v4-atomic-recall-schema-repair": {
                "supported_obligation_ids": ["O-1"],
                "invented_obligation_ids": [],
                "source_gap_claims": [],
            },
            "v4-atomic-recall-partition-repair": {
                "supported_obligation_ids": [],
                "invented_obligation_ids": ["O-2"],
            },
        },
    )
    assert result == {
        "supported_obligation_ids": ["O-1"],
        "invented_obligation_ids": ["O-2"],
        "source_gap_claims": [],
    }


def test_large_atomic_recall_is_split_and_merged_deterministically(tmp_path: Path) -> None:
    payload = {
        "source_index": {"entries": [{"source_ref": "req.md#FR-1"}]},
        "obligations": [
            {"obligation_id": f"O-{index:02d}", "status": "active"}
            for index in range(25)
        ],
    }
    worker_cache = {
        "v4-atomic-recall-source-001": {"source_gap_claims": []},
        "v4-atomic-recall-chunk-001": {
            "supported_obligation_ids": [f"O-{index:02d}" for index in range(20)],
            "invented_obligation_ids": [],
            "source_gap_claims": [],
        },
        "v4-atomic-recall-chunk-002": {
            "supported_obligation_ids": [f"O-{index:02d}" for index in range(20, 25)],
            "invented_obligation_ids": [],
            "source_gap_claims": [],
        },
    }
    result = v4_domain.v4_transport_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v4-atomic-recall",
        payload=payload,
        prompt="Classify the frozen obligations.",
        worker_cache=worker_cache,
    )
    assert result["supported_obligation_ids"] == [f"O-{index:02d}" for index in range(25)]
    assert result["invented_obligation_ids"] == []


def test_chunk_merge_rejects_duplicate_or_cross_classified_ids() -> None:
    payload = {
        "source_index": {"entries": [{"source_ref": "req.md#FR-1"}]},
        "obligations": [
            {"obligation_id": "O-1", "status": "active"},
            {"obligation_id": "O-2", "status": "active"},
        ],
    }
    try:
        v4_domain._merge_atomic_recall_chunks(payload, [
            {"supported_obligation_ids": ["O-1"], "invented_obligation_ids": [], "source_gap_claims": []},
            {"supported_obligation_ids": ["O-1"], "invented_obligation_ids": ["O-2"], "source_gap_claims": []},
        ])
    except ValueError as exc:
        assert "duplicate" in str(exc) or "overlap" in str(exc)
    else:
        raise AssertionError("chunk merge accepted an invalid partition")


def test_source_gap_chunk_sees_cross_source_obligations() -> None:
    payload = {
        "source_index": {"entries": [
            {"source_ref": "req#FR-1"}, {"source_ref": "req#FR-2"},
        ]},
        "obligations": [
            {"obligation_id": "O-1", "source_refs": ["req#FR-1"], "status": "active"},
            {"obligation_id": "O-2", "source_refs": ["req#FR-1", "req#FR-2"], "status": "active"},
            {"obligation_id": "O-3", "source_refs": ["req#FR-2"], "status": "active"},
        ],
    }
    selected = v4_domain._source_recall_payload(payload, ["req#FR-1"])
    assert [item["obligation_id"] for item in selected["obligations"]] == ["O-1", "O-2", "O-3"]
    assert [item["source_ref"] for item in selected["source_index"]["entries"]] == ["req#FR-1"]


def test_chunk_merge_rejects_missing_and_unknown_ids() -> None:
    payload = {
        "source_index": {"entries": [{"source_ref": "req#FR-1"}]},
        "obligations": [
            {"obligation_id": "O-1", "status": "active"},
            {"obligation_id": "O-2", "status": "active"},
        ],
    }
    for ids in (["O-1"], ["O-1", "O-2", "O-X"]):
        with pytest.raises(ValueError, match="partition mismatch"):
            v4_domain._merge_atomic_recall_chunks(payload, [{
                "supported_obligation_ids": ids,
                "invented_obligation_ids": [], "source_gap_claims": [],
            }])
