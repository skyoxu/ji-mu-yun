"""S6 RED: explicit predecessor refs are required when history has duplicates."""
import json
import hashlib
import shutil
from pathlib import Path
from terminal_validator import prepare_terminal_observation

def test_terminal_requires_explicit_lineage_selection(tmp_path: Path) -> None:
    source_plan = Path(__file__).resolve().parents[1]
    repo = tmp_path / "repo"
    plan = repo / "execution-plans" / source_plan.name
    plan.parent.mkdir(parents=True)
    plan.mkdir(parents=True, exist_ok=True)
    for name in ("implementation-contract.v1.json", "command-registry.v1.json", "knowledge-context.freeze.v1.json"):
        shutil.copy2(source_plan / name, plan / name)
    for index in range(1, 6):
        for suffix in ("A", "B"):
            run = repo / "logs" / "tdd-adapter" / "vdd-quick-dev-semantic-oracle-recovery" / f"S{index}" / f"RUN-{suffix}-{index}"
            run.mkdir(parents=True)
            (run / "slice-ready-result.json").write_text(json.dumps({"status":"pass","predicate":"slice-ready","slice_id":f"S{index}","run_id":run.name}), encoding="utf-8")
    s6_run = repo / "logs" / "tdd-adapter" / "vdd-quick-dev-semantic-oracle-recovery" / "S6" / "RUN-S6"
    s6_run.mkdir(parents=True)
    entries = []
    for index in range(1, 6):
        selected_run = repo / "logs" / "tdd-adapter" / "vdd-quick-dev-semantic-oracle-recovery" / f"S{index}" / f"RUN-A-{index}"
        result = selected_run / "slice-ready-result.json"
        entries.append({"slice_id": f"S{index}", "run_id": selected_run.name, "result_path": result.relative_to(repo).as_posix(), "result_sha256": "sha256:" + hashlib.sha256(result.read_bytes()).hexdigest()})
    entries.append(dict(entries[0]))
    (s6_run / "terminal-lineage-input.v1.json").write_text(json.dumps({
        "schema_version": "quick-dev-tdd-adapter.terminal-lineage-input.v1",
        "plan_id": "vdd-quick-dev-semantic-oracle-recovery",
        "slice_id": "S6", "run_id": s6_run.name, "entries": entries
    }, sort_keys=True), encoding="utf-8")
    try:
        prepare_terminal_observation(plan, s6_run)
    except ValueError:
        return
    raise AssertionError("FAILURE_ID:TERMINAL-LINEAGE-NOT-CLOSED")
