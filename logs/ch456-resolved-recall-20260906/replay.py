"""ADR-0041: offline protocol replay, not a fresh semantic judgment."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-execution-plan/scripts"))
import semantic_compiler_gate as gate

archive = ROOT / "logs/ch456-semantic-plan-archive-3c79066f-r1200-retry1/plan/.compiler-work"
files = [archive / "v4-atomic-recall-schema-repair-last-message.json", archive / "v4-atomic-recall-last-message.json"]
bodies = [p.read_bytes() for p in files]
repair, later = map(json.loads, bodies)
assert repair["supported_obligation_ids"] == later["supported_obligation_ids"]
assert repair["source_gap_claims"] == [] and len(later["source_gap_claims"]) == 1
# Only the exact ID/ref domain is needed for this worker lifecycle replay.
# This is not a reconstruction of the original full semantic input.
payload = {"source_index": {"entries": [{"source_ref": later["source_gap_claims"][0]["source_ref"]}]},
           "obligations": [{"obligation_id": oid, "status": "active"} for oid in repair["supported_obligation_ids"]]}
calls = []
def transport(**kw):
    calls.append(kw["stage"])
    if len(calls) == 1:
        raise RuntimeError("codex exec timeout")
    if len(calls) == 2:
        return repair
    raise AssertionError("duplicate judgment was requested")

with tempfile.TemporaryDirectory() as temporary, \
        patch.object(gate, "_ORIGINAL_INVOKE_WORKER", transport), \
        patch.object(gate.sc, "invoke_worker", gate.normative_invoke_worker), \
        patch.object(gate, "_write_worker_receipt", lambda **kw: None):
    args = {"root": ROOT, "out_dir": Path(temporary), "payload": payload, "prompt": "protocol replay", "worker_cache": None}
    first = gate._resolved_atomic_recall_worker(**args)
    second = gate._resolved_atomic_recall_worker(**args)
    assert first == second == repair
assert calls == ["v4-atomic-recall", "v4-atomic-recall-schema-repair"]
assert all(p.read_bytes() == b for p, b in zip(files, bodies))
result = {"scope": "Completed-worker lifecycle replay with captured outputs and ID/ref-only payload",
          "source_artifacts": [{"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(b).hexdigest()} for p, b in zip(files, bodies)],
          "simulated_transport_calls": calls, "duplicate_judgment_calls": 0, "live_backend_calls": 0,
          "historical_evidence_unchanged": True, "full_semantic_replay": False, "final_acceptance": "not-run"}
(Path(__file__).parent / "replay-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
