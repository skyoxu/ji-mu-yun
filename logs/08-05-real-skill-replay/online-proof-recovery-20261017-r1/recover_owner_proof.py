"""ADR-0058/0060: append native-owner proof successors without rerunning slices."""
from pathlib import Path
import hashlib
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = "d0a6c80727cc21c2d6009e1de5fae4bbbc34d93d"
TARGET = ROOT / "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed"
sys.path.insert(0, str(ROOT / ".agents/skills/quick-dev-tdd-adapter/tools"))
sys.path.insert(0, str(ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts"))
from coverage_predicates import validate_slice_ready, publish_implementation_complete
from runtime_evidence import sha256_value, create_json
from current_quick_dev_handoff import verify_current_handoff


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def byte_ref(path):
    return {"path": path.relative_to(ROOT).as_posix(),
            "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    prepared = read(TARGET / "acceptance-runs/acceptance-685ab0649074a499/prepare-run.v1.json")
    bundle = read(TARGET / prepared["prerequisiteBundle"]["path"])
    original_binding = bundle["currentQuickDev"]
    original_path = ROOT / original_binding["receipt"]["path"]
    assert byte_ref(original_path) == original_binding["receipt"]
    try:
        verify_current_handoff(ROOT, original_binding)
    except ValueError as exc:
        create_json(OUT / "original-consumer-result.v1.json", {
            "status": "blocked", "reason": str(exc),
            "originalReceipt": original_binding["receipt"], "authorizes": []})
    else:
        raise RuntimeError("Original proof is already current; reassess recovery")
    original = read(original_path)
    roots = [{**row, "source_commit": SOURCE} for row in original_binding["snapshotRoots"]]
    semantic = ROOT / original_binding["semanticPlan"]["path"]
    base = original_binding["baseCommit"]
    predecessors = []
    started = time.monotonic()
    for number, previous in enumerate(original["predecessors"], 1):
        if previous.get("budget_compatibility") is not None:
            raise RuntimeError("Unexpected compatibility envelope; reassess explicit owner inputs")
        sid = previous["slice_id"]
        path = OUT / "q7" / (sid + "-slice-ready.json")
        current = validate_slice_ready(workspace=ROOT, semantic_plan=semantic,
            run_root=ROOT / previous["run_root"], slice_id=sid,
            snapshot_roots=roots, source_commit=SOURCE, base_commit=base, out=path)
        predecessors.append({**previous, "result_ref": path.relative_to(ROOT).as_posix(),
                             "result_sha256": sha256_value(current)})
        print(json.dumps({"q7": sid, "completed": number, "total": len(original["predecessors"])}), flush=True)
    request = {"sourceCommit": SOURCE, "baseCommit": base, "semanticPlan": original_binding["semanticPlan"],
               "snapshotRoots": roots, "predecessors": predecessors, "authorizes": []}
    create_json(OUT / "q8-owner-request.json", request)
    result_path = OUT / "q8/implementation-complete.v2.json"
    result = publish_implementation_complete(workspace=ROOT, semantic_plan=semantic,
        predecessors=predecessors, snapshot_roots=roots, source_commit=SOURCE,
        base_commit=base, out=result_path, profile=original.get("profile", "standard"))
    binding = {**original_binding, "sourceCommit": SOURCE, "snapshotRoots": roots,
               "receipt": byte_ref(result_path)}
    create_json(OUT / "current-quick-dev-binding.json", binding)
    check_started = time.monotonic()
    verified = verify_current_handoff(ROOT, binding)
    checked = {"status": verified["status"], "predicate": verified["predicate"],
               "predecessors": len(verified["predecessors"]),
               "runtimeClosureTuples": len(verified["runtime_closure_tuples"]),
               "elapsedSeconds": round(time.monotonic()-check_started,3), "authorizes": verified["authorizes"]}
    create_json(OUT / "acceptance-consumer-readonly-result.json", checked)
    create_json(OUT / "recovery-summary.v1.json", {
        "schema": "08-05-online-proof-recovery.v1", "adr": "ADR-0058", "authorizes": [],
        "sourceCommit": SOURCE, "originalReceipt": original_binding["receipt"],
        "successorReceipt": byte_ref(result_path), "originalFilesRewritten": False,
        "nativeProcessEvidenceReused": True, "sliceTestProcessesExecuted": 0,
        "consumerReadonly": checked, "elapsedSeconds": round(time.monotonic()-started,3)})
    print(json.dumps(checked), flush=True)


if __name__ == "__main__":
    main()
