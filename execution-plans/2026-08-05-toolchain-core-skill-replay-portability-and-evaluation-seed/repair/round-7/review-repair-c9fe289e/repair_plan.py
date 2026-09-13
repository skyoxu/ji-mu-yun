"""ADR-0041/ADR-0058: bounded direct plan repair, never compiler authorization.

Uses the archived input on subsequent runs. It preserves old bytes, derives
all changed projections, and invalidates prior compiler/semantic PASS claims.
It does not run a model, VDD, Quick Dev, Acceptance, or production replay.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PLAN = HERE.parent / "current-plan"
ROOT = next(p for p in HERE.parents if (p / "AGENTS.md").is_file())
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-execution-plan/scripts"))
from semantic_plan_contract import validate_semantic_bundle
from semantic_chain_audit import audit_bundle
from semantic_behavior_contract import project_intents, validate_routing_intent

BASE = "sha256:2640e323be47c3da553c6edee5489a3076b750e794e81e5dc07b581185f8333c"
AUTH = "O-C1E267D7452D"
REPLAY = "O-B9EAA8169232"
OWNER = "scripts/sc/skill_package_replay.py"
TEST = "scripts/sc/tests/test_skill_package_replay.py"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(encoded(value)).hexdigest()


def stable_id(prefix, value, keys):
    return prefix + digest({k: value.get(k) for k in keys})[7:19].upper()


def replace_ids(value, mapping):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [replace_ids(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: replace_ids(v, mapping) for k, v in value.items()}
    return value


def repaired_bundle(original):
    if digest(original) != BASE:
        raise ValueError("repair input is not the reviewed c9fe289e bundle")
    b = copy.deepcopy(original)
    obligations = {o["obligation_id"]: o for o in b["obligations"]}
    obligations[AUTH].update(
        subject="FR-13 derived-evidence empty authorization set",
        trigger="A replay, seed, matrix, review, or Quick Dev derived artifact is emitted or consumed.",
        state_before="An otherwise valid derived artifact has an explicit empty set, a non-empty set, or a missing/malformed authorizes field.",
        state_after="Only an explicit JSON array authorizes=[] passes this invariant; every other value is rejected without foreign lifecycle advancement.",
        expected_behavior="Require authorizes=[] on every derived artifact. Reject every non-empty set, including apparently genuine or approved grants, and missing or malformed fields. Lifecycle-owner approval is separate and cannot be carried by derived evidence.",
        observable_result="The empty-array control passes this invariant; forged and apparently valid non-empty grants, missing fields, null, objects, and strings all fail with no foreign state transition.",
        forbidden_result=["Accepting a non-empty authorization set because its grant is genuine", "Treating a missing or malformed field as an empty set", "Derived evidence advancing another owner's lifecycle"],
    )
    obligations[REPLAY].update(
        trigger="Historical replay is requested using a frozen original binding identity.",
        state_before="The original binding and its referenced input bytes are available, or one reference is missing or mismatched.",
        state_after="The original identity is reconstructed and verified before a fresh same-identity replay; missing or mismatched inputs reject before launch.",
        expected_behavior="Rebuild the original binding identity from its referenced bytes, compare it with the frozen original binding, and then actually execute a fresh replay bound to that same identity. Reject missing or mismatched originals; never silently rebind to changed inputs.",
        observable_result="A valid control records reconstruction verification before a fresh process invocation, with equal original/reconstructed/executed identities and newly captured output. Mutation and missing-input controls reject before launch.",
        forbidden_result=["Always rejecting without a successful same-identity control", "Echoing an identity without reconstructing referenced bytes", "Silently rebinding to changed inputs", "Reusing historical output as fresh process evidence", "Launching a mismatched or unreconstructable replay"],
    )
    acceptance_by_oid = {o: a for a in b["acceptances"] for o in a["obligation_ids"]}
    auth = acceptance_by_oid[AUTH]
    replay = acceptance_by_oid[REPLAY]
    auth.update(
        given="For each derived artifact kind (replay, seed, matrix, review, Quick Dev), hold all other inputs constant and independently vary authorizes: [], a forged non-empty grant, an apparently genuine non-empty grant, missing, null, object, and string.",
        when="The real Toolchain emission/consumption boundary evaluates the explicit authorization-set invariant.",
        then="Only [] passes this invariant; every non-empty or missing/malformed field rejects without another owner's state transition. Separate lifecycle-owner approval neither changes this rule nor belongs in derived evidence.",
        oracle={"observable": "Per-kind control and mutation outcomes from the real Toolchain boundary, the serialized authorizes field, and before/after lifecycle state.", "expected": "Explicit [] passes the authorization-set invariant; all non-empty values reject regardless of authenticity, and missing/malformed fields reject. Passing this invariant alone does not imply overall Acceptance.", "forbidden": obligations[AUTH]["forbidden_result"]},
        assertion_ids=["AO-17a-empty-array-control", "AO-17a-any-nonempty-rejected", "AO-17a-missing-malformed-rejected", "AO-17a-lifecycle-authority-separated"],
    )
    replay.update(
        given="A frozen historical binding points to reconstructable original bytes. Independently prepare valid, mutated-original, missing-original, echoed-identity-with-wrong-bytes, and no-launch controls; retain historical evidence unchanged.",
        when="Reconstruct and verify the original binding identity first, then launch a fresh wrapper replay using that same verified identity.",
        then="The valid control actually executes and captures new process/output evidence bound to the original identity. Missing or mismatched originals reject before launch. Skipping execution, using changed inputs, or reusing old output fails the positive control.",
        oracle={"observable": "Ordered reconstruction/verification and fresh process observations; original, reconstructed, and execution-bound identities; captured command/output; launch absence for invalid controls.", "expected": "Original identity is rebuilt from referenced bytes, all three identities match, verification precedes actual replay, and a fresh successful valid control exists. Missing/mismatched inputs reject without launch or silent rebinding.", "forbidden": obligations[REPLAY]["forbidden_result"]},
        assertion_ids=["AO-09e-original-bytes-reconstructed", "AO-09e-verify-before-launch", "AO-09e-same-identity-real-replay", "AO-09e-mismatch-missing-no-launch", "AO-09e-no-output-reuse"],
    )
    ids = {}
    for a in (auth, replay):
        old = a["acceptance_id"]
        a["acceptance_id"] = stable_id("A-", a, ("obligation_ids", "given", "when", "then", "oracle", "assertion_ids"))
        ids[old] = a["acceptance_id"]
    b = replace_ids(b, ids)
    auth_id, replay_id = auth["acceptance_id"], replay["acceptance_id"]
    failure_ids = {}
    for f in b["failure_intents"]:
        if auth_id in f["acceptance_ids"]:
            f["selector_intent"] = "For each derived artifact kind, run the [] control and independently forged/non-forged non-empty and missing/malformed authorizes controls against the real boundary. Fail if [] is rejected by this invariant, any other value is accepted, or foreign lifecycle state advances."
            f["failure_id"] = "AO17A-EMPTY-AUTHORIZATION-SET"
        elif replay_id in f["acceptance_ids"]:
            f["selector_intent"] = "Run the valid original-binding reconstruction and fresh same-identity replay control, then independently mutate/delete referenced bytes, echo the original identity with wrong bytes, suppress launch, and reuse old output. Fail on absent valid execution, silent rebinding, identity mismatch, or execution before verification."
            f["failure_id"] = "AO09E-ORIGINAL-BINDING-REAL-REPLAY"
        else:
            continue
        old = f["failure_intent_id"]
        f["failure_intent_id"] = stable_id("FI-", f, ("acceptance_ids", "failure_family", "selector_intent"))
        failure_ids[old] = f["failure_intent_id"]
    b = replace_ids(b, failure_ids)
    slices = {s["slice_id"]: s for s in b["slices"]}
    s = slices["S14"]
    s.update(
        behavior_change=obligations[AUTH]["expected_behavior"],
        terminal_predicate=auth["oracle"]["expected"] + " No foreign lifecycle advancement occurs for any control.",
        state_transition="Derived artifact -> explicit empty-set check -> invariant satisfied for [] only, otherwise reject; lifecycle-owner approval remains separate.",
        affected_subjects=["Derived replay/seed/matrix/review/Quick Dev evidence authorization"],
        production_owners=[OWNER], allowed_write_paths=[OWNER, TEST], execution_snapshot_paths=[TEST],
        rollback_scope={"production_paths": [OWNER], "state_or_schema_compatibility": "Preserve authorizes=[] and lifecycle ownership; no knowledge-publication authorization or schema change."},
    )
    s = slices["S19"]
    s["behavior_change"] = s["behavior_change"].replace("Bind replay validation to artifact identity and reject any mismatch before replay execution.", obligations[REPLAY]["expected_behavior"])
    s["terminal_predicate"] = s["terminal_predicate"].replace("The binding-mutation fixture returns reject, records the mismatch diagnostic, and confirms no replay process or accepted result was produced.", replay["oracle"]["expected"])
    s["state_transition"] = s["state_transition"].replace("Mismatched replay transitions from submitted to rejected before execution or evidence publication.", "Valid originals -> reconstruct original identity -> verify equality -> fresh same-identity replay; missing/mismatched originals -> reject before launch.")
    s["rollback_scope"]["state_or_schema_compatibility"] = s["rollback_scope"]["state_or_schema_compatibility"].replace("Maintain replay artifact schema and reject only identity mismatches; no migration is needed.", "Preserve historical identities and bytes; revert replay implementation only, without accepting unreconstructable inputs or promoting historical evidence.")
    for field, paths in (("production_owners", [OWNER]), ("allowed_write_paths", [OWNER, TEST]), ("execution_snapshot_paths", [TEST])):
        s[field] = sorted(set(s[field]) | set(paths))
    s["rollback_scope"]["production_paths"] = sorted(set(s["rollback_scope"]["production_paths"]) | {OWNER})
    for s in b["slices"]:
        if s["slice_id"] not in {"S14", "S19"}:
            continue
        related = [a for a in b["acceptances"] if a["acceptance_id"] in s["acceptance_ids"]]
        failures = [f for f in b["failure_intents"] if set(f["acceptance_ids"]) & set(s["acceptance_ids"])]
        s["proof"] = {"acceptance_ids": sorted(s["acceptance_ids"]), "assertion_ids": sorted({x for a in related for x in a["assertion_ids"]}), "selector_intents": sorted({f["selector_intent"] for f in failures})}
        # Explicit direct-repair identity, not a fabricated compiler bucket hash.
        s["slice_input_hash"] = digest({"direct_repair": "c9fe289e", "slice": {k: v for k, v in s.items() if k != "slice_input_hash"}, "acceptances": related})
    for edge in b["final_plan_coverage"]:
        edge["terminal_predicate"] = slices[edge["slice_id"]]["terminal_predicate"]
    for c in b["agent_contexts"]:
        if c["slice_id"] not in {"S14", "S19"}:
            continue
        s = slices[c["slice_id"]]
        c["contracts"] = ["vdd.semantic-plan-bundle.v1", s["terminal_predicate"]]
        c["allowed_paths"] = s["allowed_write_paths"]
        c["selector_intents"] = s["proof"]["selector_intents"]
        c["forbidden_paths"] = sorted(set(c["forbidden_paths"]) | {"PhaseA.Platform", "runtime/phase-a", "_bmad", ".agents/skills/bmad-*", ".agents/skills/gds-*"})
        command = ["python", "-m", "pytest", TEST]
        c["validation_commands"] = [command] if c["slice_id"] == "S14" else c["validation_commands"] + ([command] if command not in c["validation_commands"] else [])
    b["behavior_routing"]["intents"] = project_intents(b)
    return b


def validate(b):
    valid, findings = validate_semantic_bundle(b)
    audit = audit_bundle(b)
    errors = findings + audit["findings"] + validate_routing_intent(b)
    if not valid or not audit["valid"] or errors:
        raise ValueError(";".join(errors))
    return audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    before = HERE / "before"
    original_path = before / "semantic-plan-bundle.v1.json"
    original = json.loads((original_path if original_path.exists() else PLAN / "semantic-plan-bundle.v1.json").read_text(encoding="utf-8"))
    b = repaired_bundle(original)
    audit = validate(b)
    outputs = {"semantic-plan-bundle.v1.json": b, "semantic-chain-audit.v1.json": audit}
    for field, name in (("obligations", "obligations"), ("acceptances", "acceptances"), ("failure_intents", "failure-intents"), ("slices", "slices"), ("pre_slice_coverage", "pre-slice-coverage"), ("final_plan_coverage", "final-plan-coverage")):
        outputs[name + ".v1.json"] = b[field]
    for c in b["agent_contexts"]:
        if c["slice_id"] in {"S14", "S19"}:
            outputs[f"agent-context/{c['slice_id']}/agent-context.json"] = c
    outputs["compiler-state.v1.json"] = {"schema": "vdd.compiler-state.v1", "plan_id": b["plan_id"], "state": "repair-vdd", "completed_stages": [], "semantic_plan_sha256": digest(b), "reason": "Direct review repair; prior compiler and semantic-worker passes are stale. Current independent semantic review and canonical validation are pending.", "authorizes": []}
    for name in ("semantic-alignment.v1.json", "atomic-recall-alignment.v1.json", "feasibility.v1.json"):
        outputs[name] = {"valid": False, "findings": ["stale-after-direct-review-repair"], "recommended_action": "repair-vdd", "semantic_plan_sha256": digest(b), "authorizes": []}
    changed = []
    for name, value in outputs.items():
        target, saved = PLAN / name, before / name
        payload = encoded(value)
        if args.check:
            if not target.is_file() or target.read_bytes() != payload:
                raise ValueError("projection drift: " + name)
        else:
            if not saved.exists():
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(target.read_bytes())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        changed.append(name)
    result = {"status": "direct-plan-repair-validated", "base_commit": "c9fe289edb01011a9810f5473e3a0574f0525d00", "semantic_plan_sha256": digest(b), "structural_validation": "pass", "semantic_chain_audit": audit, "changed_projections": changed, "compiler_run": False, "runtime_replay_run": False, "windows_verification_pending": True, "authorizes": []}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
