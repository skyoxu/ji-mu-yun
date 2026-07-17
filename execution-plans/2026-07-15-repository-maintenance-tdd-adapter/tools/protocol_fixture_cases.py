from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from protocol_artifact_guards import bytes_hash, canonical_bytes, value_hash
from protocol_fixture_mutations import apply_protocol_mutations
from protocol_fixture_support import hydrate_protocol_fixture
from protocol_validation_guards import _finding, validate_protocol_bundle


def evaluate_protocol_fixture(plan_root: Path, fixture_id: str, fixtures: dict[str, Any]) -> list[dict[str, str]]:
    case = next((item for item in fixtures.get("cases", []) if item.get("id") == fixture_id), None)
    if case is None:
        return [_finding("RMAP-STRUCT-FIXTURE", fixture_id, "unknown protocol fixture")]
    bundle, store, file_versions = hydrate_protocol_fixture(fixtures["valid_bundle"])
    mutations = copy.deepcopy(case.get("mutations", []))
    for mutation in mutations:
        if mutation["path"].startswith("/context_manifest/"):
            mutation["path"] = mutation["path"].replace("/context_manifest/", "/contexts/0/context_manifest/", 1)
        elif mutation["path"].startswith("/slice_capsule/"):
            mutation["path"] = mutation["path"].replace("/slice_capsule/", "/contexts/0/slice_capsule/", 1)
    if fixture_id == "attempt-duplicate-accepted-stage":
        mutated = copy.deepcopy(bundle)
        mutated["attempts"].append(copy.deepcopy(mutated["attempts"][0]))
    elif fixture_id == "capsule-reference-duplicate-role-path":
        mutated = copy.deepcopy(bundle)
        mutated["contexts"][0]["context_manifest"]["artifact_refs"].append(
            copy.deepcopy(mutated["contexts"][0]["context_manifest"]["artifact_refs"][0])
        )
    elif fixture_id == "attempt-event-lifecycle-missing":
        mutated = copy.deepcopy(bundle)
        del mutated["events"][2]
        previous_hash: str | None = None
        for sequence, event in enumerate(mutated["events"], start=1):
            event["sequence"] = sequence
            event["previous_event_hash"] = previous_hash
            previous_hash = value_hash(event)
        event_bytes = b"".join(canonical_bytes(event) + b"\n" for event in mutated["events"])
        store[("run_path", "run-events.jsonl")] = event_bytes
        ledger = mutated["attempt_ledger_manifest"]
        ledger["run_events_hash"] = bytes_hash(event_bytes)
        ledger["final_event_hash"] = value_hash(mutated["events"][-1])
        core = {key: value for key, value in ledger.items() if key != "root_hash"}
        ledger["root_hash"] = value_hash(core)
    else:
        mutated = apply_protocol_mutations(bundle, mutations)
    return validate_protocol_bundle(plan_root, mutated, artifact_store=store, file_versions=file_versions, require_complete=True)


def validate_protocol_fixture_suite(plan_root: Path, fixtures: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    bundle, store, file_versions = hydrate_protocol_fixture(fixtures.get("valid_bundle", {}))
    if validate_protocol_bundle(plan_root, bundle, artifact_store=store, file_versions=file_versions, require_complete=True):
        return [_finding("RMAP-STRUCT-FIXTURE", "valid-protocol-bundle", "valid capsule and attempt fixture failed")]
    for case in fixtures.get("cases", []):
        rules = sorted({item["rule_id"] for item in evaluate_protocol_fixture(plan_root, case.get("id", "fixture"), fixtures)})
        if rules != [case.get("expected_rule")]:
            findings.append(_finding("RMAP-STRUCT-FIXTURE", str(case.get("id")), f"expected {[case.get('expected_rule')]}, observed {rules}"))
    return findings
