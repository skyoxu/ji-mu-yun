from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback

WORKTREE = Path(r"C:/ch456-semantic-diagnostic-cd7933f8")
OUT = Path(r"C:/ch456-semantic-diagnostic-output-cd7933f8")
REQ = WORKTREE / "logs" / "ch456-q3-debug-r2-3abb26ac" / "idempotency-ledger-v1" / "requirements.md"
SCRIPTS = WORKTREE / ".agents" / "skills" / "vdd-execution-plan" / "scripts"
OUT_PLAN = OUT / "plan"

sys.path.insert(0, str(SCRIPTS))
os.environ["SC_LLM_BACKEND"] = "codex-cli"

import semantic_compiler_authority as authority  # noqa: E402,F401
import semantic_compiler_gate as gate  # noqa: E402


def write(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    import semantic_worker_transport_patch as transport

    transport._REPAIR_TIMEOUT_SECONDS = 600
    source_index = gate.sc.build_source_index(WORKTREE, REQ)
    write("source-index-input.json", source_index)
    preflight = gate.sc.source_preflight(WORKTREE, source_index)
    write("source-preflight.json", preflight)
    if not preflight["valid"]:
        write("diagnostic-result.json", {"status": "source-preflight-failed", "source_preflight": preflight})
        return 1

    v1_payload = {"source": source_index["entries"][0]}
    write("v1-input-payload.json", v1_payload)
    obligations = gate.sc.compile_obligations(root=WORKTREE, out_dir=OUT_PLAN, source_index=source_index, worker_cache=None)
    write("v1-obligations.json", obligations)
    v1_guard = gate.sc.guard_obligations(source_index, obligations)
    write("v1-guard.json", v1_guard)

    v4_payload = {"source_index": source_index, "obligations": list(obligations)}
    write("atomic-recall-input-payload.json", v4_payload)
    recall = gate.atomic_recall_alignment(
        root=WORKTREE,
        out_dir=OUT_PLAN,
        source_index=source_index,
        obligations=obligations,
        worker_cache=None,
    )
    write("atomic-recall-result.json", recall)

    baseline_terms = ("skeleton", "always returns success", "returns success for every operation", "descriptive")
    suspicious = []
    for item in obligations:
        haystack = json.dumps(item, ensure_ascii=False).casefold()
        if any(term in haystack for term in baseline_terms):
            suspicious.append(item)
    write("skeleton-baseline-analysis.json", {
        "skeleton_baseline_detected_in_obligation_text": bool(suspicious),
        "suspicious_obligation_ids": [item.get("obligation_id") for item in suspicious],
        "interpretation": "descriptive baseline is not treated as a product target" if not suspicious else "review required",
    })

    receipts = sorted((OUT_PLAN / ".compiler-work" / "worker-receipts").glob("*.json"))
    write("call-summary.json", {
        "v1_worker_calls": len([p for p in receipts if p.name.startswith("v1-")]),
        "atomic_recall_worker_calls": len([p for p in receipts if p.name.startswith("v4-atomic-recall")]),
        "total_receipts": len(receipts),
        "receipt_paths": [str(p.relative_to(OUT)).replace("\\", "/") for p in receipts],
        "exit_code": 0,
    })
    write("diagnostic-result.json", {
        "status": "pass" if recall.get("valid") and v1_guard.get("valid") else "findings",
        "source_head": "cd7933f8f92891b8840a3c9ff2c5965f97020a1d",
        "v1_guard": v1_guard,
        "atomic_recall_metrics": recall.get("metrics"),
        "atomic_recall_findings": recall.get("findings", []),
        "source_gap_claims": recall.get("source_gap_claims", []),
        "invented_obligation_ids": [x for x in (recall.get("worker") or {}).get("invented_obligation_ids", []) if isinstance(x, str)],
    })
    return 0 if recall.get("valid") and v1_guard.get("valid") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        (OUT / "diagnostic-traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
