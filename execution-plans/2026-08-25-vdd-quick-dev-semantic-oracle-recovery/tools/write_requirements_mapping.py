"""Write the current requirements mapping from repository-owned source inventory."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import (  # noqa: E402
    _REQUIREMENT_PREFIXES,
    _expanded_ids,
    build_obligation_inventory,
)


def write_mapping(template: Path, freeze: Path, output: Path) -> None:
    source = json.loads(template.read_text(encoding="utf-8"))
    manifest = json.loads(freeze.read_text(encoding="utf-8"))
    requirements = []
    for row in source["requirements"]:
        copied = dict(row)
        copied["obligation_ids"] = []
        requirements.append(copied)
    by_id = {row["id"]: row for row in requirements}
    inventory = build_obligation_inventory(ROOT, manifest)
    for item in inventory:
        ids = sorted({
            identifier
            for prefix in _REQUIREMENT_PREFIXES
            for identifier in _expanded_ids(item["anchor"]["quote"], prefix)
            if identifier in by_id
        })
        if item["status"] == "active" and ids:
            item["requirement_ids"] = ids
            item["acceptance_ids"] = sorted({aid for rid in ids for aid in by_id[rid].get("acceptance_ids", [])})
            item["mapping_kind"] = "identity"
            item["merge_reason"] = "Current source anchor contains canonical requirement identifiers."
            for rid in ids:
                by_id[rid]["obligation_ids"].append(item["obligation_id"])
        else:
            item["requirement_ids"] = []
            item["acceptance_ids"] = []
            item["mapping_kind"] = "disposition"
            item["merge_reason"] = (item.get("disposition") or {}).get("reason") or "No canonical requirement identifier is present in the current source anchor."
    reverse = {aid: [] for aid in source["acceptance_ids"]}
    for row in requirements:
        row["obligation_ids"] = sorted(set(row["obligation_ids"]))
        for aid in row.get("acceptance_ids", []):
            reverse.setdefault(aid, []).append(row["id"])
    for aid in reverse:
        reverse[aid] = sorted(set(reverse[aid]))
    payload = {
        "schema_version": "vdd-requirements-acceptance-mapping.v1",
        "plan_id": source["plan_id"],
        "selection_hash": source["selection_hash"],
        "acceptance_ids": source["acceptance_ids"],
        "requirements": requirements,
        "reverse_mapping": reverse,
        "obligations": inventory,
        "semantic_review": [],
        "authorizes": [],
    }
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if output.exists():
        if output.read_bytes() != encoded:
            raise FileExistsError(f"mapping output already exists with different bytes: {output}")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)


if __name__ == "__main__":
    plan = ROOT / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery"
    write_mapping(plan / "governance/requirements-acceptance-mapping.v1.json", plan / "governance/vdd-source-freeze-manifest.v1.current.json", plan / "governance/requirements-acceptance-mapping.v1.current.json")
