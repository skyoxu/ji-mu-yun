"""ADR-0041: offline replay of the captured contract; does not invoke a worker."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-execution-plan/scripts"))
from semantic_selector_path_projection import project_selector_paths
from semantic_worker_v3_group_repair_patch import _project
from semantic_worker_v3_execution_contract_patch import _findings

cache = ROOT / "logs/ch456-real-semantic-45a9a21d-r1200/retained-run/plan/.compiler-cache/v3-schema-repair-group-v5-inline-context-a0fd5aeecfe0b031416e3d05.json"
data = cache.read_bytes()
value = _project(json.loads(data))
original = deepcopy(value)
projected, changes = project_selector_paths(ROOT, {}, value)
assert len(changes) == 1, changes
assert changes[0]["obligation_ids"] == ["O-CE3FDF37FD6D"]
index = changes[0]["hint_index"]
payload = {"obligations": [{"obligation_id": "O-CE3FDF37FD6D", "status": "active"}]}
def selected(candidate):
    return {"acceptances": [a for a in candidate["acceptances"] if a["obligation_ids"] == ["O-CE3FDF37FD6D"]],
            "slice_hints": [candidate["slice_hints"][index]]}
before = _findings(ROOT, "v3", payload, selected(value))
after = _findings(ROOT, "v3", payload, selected(projected))
assert len(before) == 1 and "selector-target-missing-not-planned" in before[0], before
assert after == [], after
assert value == original and data == cache.read_bytes()
restored = deepcopy(projected)
restored["slice_hints"][index]["execution_snapshot_paths"] = original["slice_hints"][index]["execution_snapshot_paths"]
assert restored == original
result = {"schema": "ch456.selector-path-offline-replay.v1", "cache_sha256": hashlib.sha256(data).hexdigest(),
          "changes": changes, "before_findings": before, "after_findings": after,
          "scope": "Affected hint execution-contract only; not full semantic or final acceptance",
          "cache_unchanged": True, "unrelated_fields_unchanged": True, "live_backend_calls": 0}
(Path(__file__).parent / "replay-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
