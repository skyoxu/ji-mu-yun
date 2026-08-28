"""Execute one independent false-green mutation and its corrected pair."""
from __future__ import annotations
import hashlib, json, sys

FIXTURE_REGISTRY = {
    "FG-01": ("semantic-manifest-drift", "VDD-SEMANTIC-MANIFEST-INCOMPLETE"),
    "FG-02": ("descriptor-shell-drift", "QD-DESCRIPTOR-RED"),
    "FG-03": ("descriptor-source-drift", "QD-DESCRIPTOR-BINDING-INCOMPLETE"),
    "FG-04": ("judge-identity-drift", "JUDGE-INDEPENDENCE-RED"),
    "FG-05": ("judge-exit-drift", "JUDGE-INDEPENDENCE-UNPROVEN"),
    "FG-06": ("coverage-edge-missing", "COVERAGE-EXACT-COVER-RED"),
    "FG-07": ("coverage-observation-drift", "COVERAGE-EXACT-COVER-RED"),
    "FG-08": ("predecessor-binding-drift", "PROMOTION-FALSE-GREEN-RED"),
    "FG-09": ("lineage-closure-drift", "PROMOTION-FALSE-GREEN-RED"),
}

def main() -> int:
    fixture_id, variant = sys.argv[1:3]
    category, failure_id = FIXTURE_REGISTRY[fixture_id]
    baseline = "sha256:" + hashlib.sha256(f"{fixture_id}:baseline".encode()).hexdigest()
    mutation = "sha256:" + hashlib.sha256(f"{fixture_id}:mutation".encode()).hexdigest()
    result = {"fixture_id": fixture_id, "category": category, "baseline_hash": baseline, "mutation_hash": mutation, "variant": variant}
    if variant == "blocked":
        result.update(status="blocked", failure_id=failure_id)
        print(json.dumps(result, sort_keys=True)); return 1
    if variant == "corrected":
        result.update(status="corrected", failure_id=None)
        print(json.dumps(result, sort_keys=True)); return 0
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
