"""ADR-0041: CER-R4--R6 planning intent, never runtime disposition authority."""
from __future__ import annotations

SCHEMA = "vdd.behavior-routing-intent.v1"


def project_intents(bundle):
    intents = []
    for obligation in bundle["obligations"]:
        if obligation.get("status") == "not_applicable":
            continue
        oid = obligation["obligation_id"]
        acceptances = [a for a in bundle["acceptances"] if oid in a.get("obligation_ids", [])]
        aids = sorted(a["acceptance_id"] for a in acceptances)
        slices = [s for s in bundle["slices"] if set(aids) & set(s["acceptance_ids"])]
        intents.append({
            "obligation_id": oid, "acceptance_ids": aids,
            "assertion_ids": sorted({x for a in acceptances for x in a["assertion_ids"]}),
            "production_owners": sorted({p for s in slices for p in s.get("production_owners", [])}),
            "allowed_write_paths": sorted({p for s in slices for p in s.get("allowed_write_paths", [])}),
            "selector_intents": sorted({p for c in bundle.get("agent_contexts", [])
                if c["slice_id"] in {s["slice_id"] for s in slices} for p in c.get("selector_intents", [])}),
            "observable": obligation.get("observable_result"),
            "expected_result": obligation.get("expected_behavior"),
            "depends_on": list(obligation.get("depends_on", [])),
        })
    return sorted(intents, key=lambda x: x["obligation_id"])


def validate_routing_intent(bundle):
    contract = bundle.get("behavior_routing")
    if "behavior_routing" not in bundle:
        return []  # Historical plans keep their existing mandatory TDD route.
    if not isinstance(contract, dict) or set(contract) != {"schema", "intents", "deferred"} or contract.get("schema") != SCHEMA:
        return ["behavior-routing:contract-shape"]
    expected = project_intents(bundle)
    if contract.get("intents") != expected:
        return ["behavior-routing:intent-universe-or-binding"]
    findings = []
    for row in expected:
        if any(not row.get(key) for key in ("acceptance_ids", "assertion_ids", "production_owners", "selector_intents", "observable", "expected_result")):
            findings.append("behavior-routing:unverifiable-intent:" + row["obligation_id"])
        # Each Acceptance must retain one atomic obligation; no mixed disposition cloning.
        for aid in row["acceptance_ids"]:
            item = next(a for a in bundle["acceptances"] if a["acceptance_id"] == aid)
            if item.get("obligation_ids") != [row["obligation_id"]]:
                findings.append("behavior-routing:non-atomic-acceptance:" + aid)
    rows = contract.get("deferred")
    if not isinstance(rows, list):
        return findings + ["deferred:shape"]
    index = {x["obligation_id"]: x for x in expected}
    recorded = set()
    for row in rows:
        if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k].strip()
                for k in ("type", "reason", "resolution_owner", "resolution_stage")):
            findings.append("deferred:required-fields")
            continue
        affected = row.get("affected_obligation_ids")
        if not isinstance(affected, list) or not affected or any(not isinstance(x, str) or x not in index for x in affected) or len(affected) != len(set(affected)):
            findings.append("deferred:affected-universe")
            continue
        recorded.update(affected)
        if row["type"] not in {"implementation-resolvable", "external-owner", "blocking"}:
            findings.append("deferred:unknown-type")
        elif row["type"] == "implementation-resolvable":
            if row["resolution_stage"] != "implementation" or any(not index[x]["allowed_write_paths"] for x in affected):
                findings.append("deferred:proof-or-write-contract-unresolved")
        else:
            # Every row refers to the current scope; author-supplied blocking=False
            # cannot move its proof or prerequisite to an external stage.
            findings.append("deferred:blocks-current-scope:" + ",".join(sorted(affected)))
    for o in bundle["obligations"]:
        if o.get("status") == "deferred" and o["obligation_id"] not in recorded:
            findings.append("deferred:missing-record:" + o["obligation_id"])
    return findings
