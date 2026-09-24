"""ADR-0041: bounded S25 direct-input repair; never publishes lifecycle state."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[3]
PLAN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-execution-plan/scripts"))
sys.path.insert(0, str(ROOT / ".agents/skills/quick-dev-tdd-adapter/tools"))

from semantic_plan_contract import validate_semantic_bundle
from behavior_routing import validate_plan
from q1_planned_preflight import validate_planned_preflight
from runtime_evidence import sha256_value

OLD = [
    "PhaseA.Platform/Data/PhaseAMetadataStore.cs",
    "PhaseA.Platform/Program.cs",
    "PhaseA.Platform/Readback/ArtifactReadbackService.cs",
]
ADDED = [
    "PhaseA.Platform/Workspaces/WorkspaceStorageService.cs",
    "PhaseA.Platform/Workspaces/RestoreService.cs",
    "PhaseA.Platform/Security/RunnerIsolationPolicy.cs",
]
SOURCE = "execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery/implementation-repair-input.md"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_atomic(path: Path, value) -> None:
    data = encoded(value)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".s25-repair-", delete=False) as item:
        item.write(data)
        temporary = Path(item.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    bundle_path = PLAN / "semantic-plan-bundle.v1.json"
    slices_path = PLAN / "slices.v1.json"
    context_path = PLAN / "agent-context/S25/agent-context.json"
    index_path = PLAN / "input-repair-source-index.v1.json"
    original = read(bundle_path)
    assert read(slices_path) == original["slices"]
    current = next(s for s in original["slices"] if s["slice_id"] == "S25")
    context = next(c for c in original["agent_contexts"] if c["slice_id"] == "S25")
    assert read(context_path) == context
    assert len(original["slices"]) == 73
    assert len(original["obligations"]) == len(original["acceptances"]) == 351
    assert current["production_owners"] == OLD
    assert current["rollback_scope"]["production_paths"] == OLD
    assert current["allowed_write_paths"][:len(OLD)] == OLD
    assert context["allowed_paths"] == current["allowed_write_paths"]
    assert all((ROOT / path).is_file() for path in ADDED)
    assert all(Path(path).name in (ROOT / SOURCE).read_text(encoding="utf-8") for path in ADDED)

    repaired = copy.deepcopy(original)
    selected = next(s for s in repaired["slices"] if s["slice_id"] == "S25")
    owners = OLD + ADDED
    selected["production_owners"] = owners
    selected["allowed_write_paths"] = owners + current["allowed_write_paths"][len(OLD):]
    selected["rollback_scope"]["production_paths"] = owners
    unhashed = dict(selected)
    unhashed.pop("slice_input_hash")
    selected["slice_input_hash"] = sha256_value(unhashed)
    repaired_context = next(c for c in repaired["agent_contexts"] if c["slice_id"] == "S25")
    repaired_context["allowed_paths"] = selected["allowed_write_paths"]
    s25_ids = set(selected["obligation_ids"])
    changed_intents = []
    for intent in repaired["behavior_routing"]["intents"]:
        if intent["obligation_id"] in s25_ids:
            assert intent["production_owners"] == OLD
            assert set(intent["allowed_write_paths"]) == set(current["allowed_write_paths"])
            intent["production_owners"] = sorted(owners)
            intent["allowed_write_paths"] = sorted(selected["allowed_write_paths"])
            changed_intents.append(intent["obligation_id"])
    assert set(changed_intents) == s25_ids

    assert [s for s in repaired["slices"] if s["slice_id"] != "S25"] == [s for s in original["slices"] if s["slice_id"] != "S25"]
    assert [c for c in repaired["agent_contexts"] if c["slice_id"] != "S25"] == [c for c in original["agent_contexts"] if c["slice_id"] != "S25"]
    for key in ("obligations", "acceptances", "failure_intents", "pre_slice_coverage", "final_plan_coverage"):
        assert repaired[key] == original[key], key
    ok, findings = validate_semantic_bundle(repaired)
    assert ok, findings
    validate_plan(repaired)
    validate_planned_preflight(workspace=ROOT, bundle=repaired, slice_id="S25", timeout_seconds=600)

    index = read(index_path)
    source_rows = [row for row in index["sources"] if row["path"] == SOURCE]
    assert len(source_rows) == 1
    source_rows[0]["sha256"] = "sha256:" + hashlib.sha256((ROOT / SOURCE).read_bytes()).hexdigest()
    outputs = {
        bundle_path: repaired,
        slices_path: repaired["slices"],
        context_path: repaired_context,
        index_path: index,
    }
    for path, value in outputs.items():
        write_atomic(path, value)
    assert read(slices_path) == read(bundle_path)["slices"]
    assert read(context_path) == next(c for c in read(bundle_path)["agent_contexts"] if c["slice_id"] == "S25")
    evidence = {
        "schema": "phase-b-c.s25-direct-input-repair.v1",
        "status": "input-checks-passed",
        "slice_id": "S25",
        "slices": 73,
        "obligations": 351,
        "acceptances": 351,
        "added_production_owners": ADDED,
        "changed_intent_obligation_ids": sorted(changed_intents),
        "before_bundle_sha256": sha256_value(original),
        "after_bundle_sha256": sha256_value(repaired),
        "output_sha256": {path.relative_to(ROOT).as_posix(): "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() for path in outputs},
        "compiler_invoked": False,
        "tests_executed": False,
        "authorizes": [],
    }
    folder = ROOT / "logs/phase-b-c-input-repair/s25-producer-scope"
    folder.mkdir(parents=True, exist_ok=True)
    write_atomic(folder / (uuid.uuid4().hex + ".json"), evidence)
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
