from __future__ import annotations

import json
from pathlib import Path
import sys


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_compiler as sc
import semantic_compiler_gate as gate
import semantic_feasibility_patch
from semantic_compiler_authority import _strict_worker_schema_findings


def _obligation() -> dict:
    return {
        "source_refs": ["req.md#FR-1"],
        "subject": "ledger",
        "trigger": "a claim is requested",
        "state_before": "key is inactive",
        "state_after": "key is active",
        "expected_behavior": "reserve the key",
        "observable_result": "claim returns accepted",
        "forbidden_result": ["duplicate active reservation"],
        "requirement_type": "Product",
        "obligation_kind": "behavior",
        "unresolved_fragments": [],
        "status": "active",
        "depends_on": [],
    }


def test_stable_authority_installs_planned_red_feasibility_rule() -> None:
    assert sc.feasibility is semantic_feasibility_patch.feasibility_with_planned_red_files


def test_v1_worker_contract_catches_late_normalizer_failures() -> None:
    invalid = _obligation()
    invalid["depends_on"] = "none"
    invalid["unresolved_fragments"] = ["implementation detail is unknown"]
    findings = _strict_worker_schema_findings("v1-FR-1", {"obligations": [invalid]})
    assert any("depends_on:string-list-required" in item for item in findings)
    assert any("active-unresolved" in item for item in findings)


def test_v1_worker_contract_routes_invalid_live_shape_through_one_repair(tmp_path: Path) -> None:
    stage = "v1-FR-1"
    invalid = _obligation()
    invalid["depends_on"] = None
    invalid["unresolved_fragments"] = ["not a source ambiguity"]
    repaired = _obligation()
    worker_cache = {
        stage: {"obligations": [invalid]},
        f"{stage}-schema-repair": {"obligations": [repaired]},
    }

    result = gate.normative_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage=stage,
        payload={"source": {"source_ref": "req.md#FR-1"}},
        prompt="Extract one active obligation.",
        worker_cache=worker_cache,
    )

    assert result == {"obligations": [repaired]}
    receipts = list((tmp_path / "plan" / ".compiler-work" / "worker-receipts").glob("*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["exit_status"] == "ok"
    assert receipt["schema_valid"] is True
    assert receipt["schema_repair_attempted"] is True
