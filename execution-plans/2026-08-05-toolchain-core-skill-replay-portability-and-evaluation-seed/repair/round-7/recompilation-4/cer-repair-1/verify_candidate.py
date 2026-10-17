"""Verify the unpublished CER repair candidate; grant no execution authority."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "current-plan"

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def digest(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return "sha256:" + hashlib.sha256(data.encode("utf-8")).hexdigest()

def main():
    old = read(HERE.parent / "current-plan" / "semantic-plan-bundle.v1.json")
    new = read(PLAN / "semantic-plan-bundle.v1.json")
    summary = read(HERE / "repair-summary.json")
    findings = []
    def check(ok, message):
        if not ok:
            findings.append(message)
    check(digest(old) == summary["base_bundle_sha256"], "Base bundle identity mismatch")
    check(digest(new) == summary["bundle_sha256"], "Candidate bundle identity mismatch")
    check(new["obligations"] == old["obligations"], "Obligations changed")
    def semantics(items):
        return [{k: v for k, v in a.items() if k != "red_intent_ids"} for a in items]
    check(semantics(new["acceptances"]) == semantics(old["acceptances"]), "Acceptance semantics changed")
    check(all(f in new["failure_intents"] for f in old["failure_intents"]), "Historical failure intent changed")
    check(new["slices"][0] == old["slices"][0], "S1 changed")
    obs = {o["obligation_id"]: o for o in new["obligations"]}
    acc = {a["acceptance_id"]: a for a in new["acceptances"]}
    fis = {f["failure_intent_id"]: f for f in new["failure_intents"]}
    contexts = {c["slice_id"]: c for c in new["agent_contexts"]}
    for fid in summary["additions"]:
        f = fis[fid]
        check(f["failure_family"] == "expected-red", fid + ": wrong family")
        for aid in f["acceptance_ids"]:
            for oid in acc[aid]["obligation_ids"]:
                ob = obs[oid]
                check(ob["obligation_kind"] in ("behavior", "quality") and ob["requirement_type"] != "Governance", fid + ": ineligible RED")
    for s in new["slices"]:
        sid = s["slice_id"]
        check(not set(s["production_owners"]) & set(s["execution_snapshot_paths"]), sid + ": production frozen as test snapshot")
        check(all(fid in fis for fid in s["failure_intent_ids"]), sid + ": unresolved failure")
        if sid != "S1":
            test = "scripts/sc/tests/tc_d1_cer/test_" + sid.lower() + ".py"
            for key in ("planned_new_files", "allowed_write_paths", "execution_snapshot_paths"):
                check(test in s[key], sid + ": test entry missing from " + key)
        ctx = contexts[sid]
        check(read(PLAN / "agent-context" / sid / "agent-context.json") == ctx, sid + ": context copy drift")
        for path in s["allowed_write_paths"]:
            check(not any(path == p or path.startswith(p.rstrip("/") + "/") for p in ctx["forbidden_paths"]), sid + ": forbidden write path")
    for filename, key in {
        "obligations": "obligations", "acceptances": "acceptances",
        "failure-intents": "failure_intents", "slices": "slices",
        "pre-slice-coverage": "pre_slice_coverage", "final-plan-coverage": "final_plan_coverage",
        "behavior-routing": "behavior_routing",
    }.items():
        check(read(PLAN / (filename + ".v1.json")) == new[key], filename + ": projection drift")
    state = read(PLAN / "compiler-state.v1.json")
    check(state["state"] == "repair-vdd" and state["completed_stages"] == [] and state["authorizes"] == [], "Candidate incorrectly claims readiness or authority")
    print(json.dumps({
        "status": "structural-pass" if not findings else "fail",
        "findings": findings,
        "semantic_plan_sha256": digest(new),
        "authorizes": [],
        "runtime_behavior_verified": False,
        "compiler_readiness_granted": False,
    }, ensure_ascii=False, indent=2))
    return 1 if findings else 0

if __name__ == "__main__":
    raise SystemExit(main())
