"""Materialize the narrowly approved S20 assertion-identity repair.

This is deliberately not a VDD compilation entry point.  It changes only the
two accepted S20 assertion projections already corrected in rebuild-inputs,
then proves that all other JSON content is semantically unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


PLAN = Path(__file__).resolve().parents[1]
REPAIRS = {
    "A-CF92BC5766FF": "SM-W10.ProjectSoftDelete_RetainsDataForProtectedCleanup",
    "A-F0C098EA789B": "SM-W10.ProjectSoftDelete_RetainsOwnershipForProtectedCleanup",
}
OLD = "SM-W10.ProjectSoftDelete_ReleasesLogicalQuota"
S20_ASSERTIONS = [
    "A-O-0D256558EC1D-1",
    OLD,
    *REPAIRS.values(),
]
S20_HASH = "sha256:be6cc6aa5614a7f6cdd2025af652df5d04774e328dd23b8dc21e2c5dbb905989"


def read(name: str):
    return json.loads((PLAN / name).read_text(encoding="utf-8"))


def encode(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write(name: str, value) -> None:
    (PLAN / name).write_bytes(encode(value))


def record_changes(before, after, path="$"):
    """Return semantic changed paths; list order is part of the contract."""
    if type(before) is not type(after):
        return [path]
    if isinstance(before, dict):
        changed = []
        for key in sorted(set(before) | set(after)):
            if key not in before or key not in after:
                changed.append(f"{path}.{key}")
            else:
                changed.extend(record_changes(before[key], after[key], f"{path}.{key}"))
        return changed
    if isinstance(before, list):
        if len(before) != len(after):
            return [path]
        changed = []
        for index, (left, right) in enumerate(zip(before, after)):
            changed.extend(record_changes(left, right, f"{path}[{index}]"))
        return changed
    return [] if before == after else [path]


def repair_acceptances(rows) -> None:
    selected = {row["acceptance_id"]: row for row in rows if row["acceptance_id"] in REPAIRS}
    assert set(selected) == set(REPAIRS)
    for acceptance_id, assertion_id in REPAIRS.items():
        assert selected[acceptance_id]["assertion_ids"] == [OLD]
        selected[acceptance_id]["assertion_ids"] = [assertion_id]


def repair_slice(rows) -> None:
    selected = next(row for row in rows if row["slice_id"] == "S20")
    assert selected["proof"]["assertion_ids"] == S20_ASSERTIONS[:2]
    assert selected["slice_input_hash"] != S20_HASH
    selected["proof"]["assertion_ids"] = S20_ASSERTIONS
    selected["slice_input_hash"] = S20_HASH


def repair_case_map(case_map) -> None:
    selected = {row["acceptance_id"]: row for row in case_map["case_maps"] if row["acceptance_id"] in REPAIRS}
    assert set(selected) == set(REPAIRS)
    for acceptance_id, assertion_id in REPAIRS.items():
        assert selected[acceptance_id]["assertion_ids"] == [OLD]
        selected[acceptance_id]["assertion_ids"] = [assertion_id]


def repair_behavior_intents(bundle) -> None:
    selected = {}
    for intent in bundle["behavior_routing"]["intents"]:
        ids = intent.get("acceptance_ids", [])
        if len(ids) == 1 and ids[0] in REPAIRS:
            selected[ids[0]] = intent
    assert set(selected) == set(REPAIRS)
    for acceptance_id, assertion_id in REPAIRS.items():
        assert selected[acceptance_id]["assertion_ids"] == [OLD]
        selected[acceptance_id]["assertion_ids"] = [assertion_id]


def check_rebuild_inputs() -> None:
    rows = read("rebuild-inputs/acceptances.v1.json")
    selected = {row["acceptance_id"]: row for row in rows if row["acceptance_id"] in REPAIRS}
    assert {key: row["assertion_ids"] for key, row in selected.items()} == {
        key: [value] for key, value in REPAIRS.items()
    }
    slices = read("rebuild-inputs/slices.v1.json")
    selected_slice = next(row for row in slices if row["slice_id"] == "S20")
    assert selected_slice["proof"]["assertion_ids"] == S20_ASSERTIONS
    assert selected_slice["slice_input_hash"] == S20_HASH


def main() -> None:
    check_rebuild_inputs()
    names = ["acceptances.v1.json", "slices.v1.json", "implementation-case-map.v1.json", "semantic-plan-bundle.v1.json"]
    before = {name: read(name) for name in names}
    after = copy.deepcopy(before)

    repair_acceptances(after["acceptances.v1.json"])
    repair_slice(after["slices.v1.json"])
    repair_case_map(after["implementation-case-map.v1.json"])
    repair_acceptances(after["semantic-plan-bundle.v1.json"]["acceptances"])
    repair_slice(after["semantic-plan-bundle.v1.json"]["slices"])
    repair_behavior_intents(after["semantic-plan-bundle.v1.json"])

    allowed = {
        "acceptances.v1.json": {
            "$[283].assertion_ids[0]", "$[325].assertion_ids[0]",
        },
        "slices.v1.json": {
            "$[35].proof.assertion_ids", "$[35].slice_input_hash",
        },
        "implementation-case-map.v1.json": {
            "$.case_maps[176].assertion_ids[0]", "$.case_maps[177].assertion_ids[0]",
        },
        "semantic-plan-bundle.v1.json": {
            "$.acceptances[283].assertion_ids[0]", "$.acceptances[325].assertion_ids[0]",
            "$.behavior_routing.intents[329].assertion_ids[0]", "$.behavior_routing.intents[348].assertion_ids[0]",
            "$.slices[35].proof.assertion_ids", "$.slices[35].slice_input_hash",
        },
    }
    for name in names:
        changed = set(record_changes(before[name], after[name]))
        assert changed == allowed[name], (name, changed)
        write(name, after[name])

    bundle = after["semantic-plan-bundle.v1.json"]
    assert len(bundle["obligations"]) == len(bundle["acceptances"]) == 351
    assert len(bundle["slices"]) == 73
    print(json.dumps({
        "status": "s20-assertion-projection-materialized",
        "files": names,
        "semantic_changes": {name: sorted(allowed[name]) for name in names},
        "bundle_sha256": "sha256:" + hashlib.sha256(encode(bundle)).hexdigest(),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
