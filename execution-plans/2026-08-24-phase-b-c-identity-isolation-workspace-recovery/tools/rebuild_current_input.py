"""ADR-0041: deterministic 8-24 input repair; no VDD, model or Phase behavior writes.

Transport is split into reviewable files because remote large-blob publication
was interrupted. This assembles the ordinary current bundle, then invokes the
existing validators and public Q1. It creates no compiler or runtime success.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
PLAN = Path(__file__).resolve().parents[1]
BASE = "9cd87d3ab780f7087b9fd470dc2843968b208eca"
TOOLS = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools"
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-execution-plan/scripts"))
sys.path.insert(0, str(TOOLS))
from semantic_plan_contract import validate_semantic_bundle
from semantic_behavior_contract import project_intents
from behavior_routing import production_hashes, validate_plan
from q1_planned_preflight import validate_planned_preflight
from current_router import materialize_descriptor

MARKER = PLAN / "input-repair-materialization.v1.json"


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")


def digest(value):
    return "sha256:"+hashlib.sha256(encoded(value)).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    text=value if isinstance(value,str) else encoded(value).decode("utf-8")
    path.write_text(text,encoding="utf-8",newline="\n")


def command(argv):
    result=subprocess.run(argv,cwd=ROOT,shell=False,capture_output=True,encoding="utf-8",errors="strict")
    if result.returncode:
        raise RuntimeError(json.dumps({"command":argv,"stdout":result.stdout,"stderr":result.stderr}))
    return result.stdout


def guard_tests():
    print(command([sys.executable,"-B","-m","pytest",
        str(TOOLS/"tests/test_dotnet_production_entry.py"),
        str(TOOLS/"tests/test_ch456_red_production_entry_guard.py"),"-q","-p","no:cacheprovider"]),end="")


def validate(bundle):
    ok,findings=validate_semantic_bundle(bundle)
    if not ok:
        raise ValueError(findings)
    validate_plan(bundle)
    order=[s["slice_id"] for s in bundle["slices"]]
    assert len(order)==len(set(order))==73 and order[0]=="S12"
    assert len(bundle["acceptances"])==len(bundle["obligations"])==351
    for selected in bundle["slices"]:
        sid=selected["slice_id"]
        assert all(order.index(dep)<order.index(sid) for dep in selected["depends_on"])
        raw=dict(selected)
        expected=raw.pop("slice_input_hash")
        assert digest(raw)==expected
        snapshots=set(selected["execution_snapshot_paths"])
        assert snapshots==set(selected["planned_new_files"])
        assert snapshots<=set(selected["allowed_write_paths"])
        assert not snapshots & set(selected["production_owners"])
        for ref in selected["production_owners"]:
            path=ROOT/ref
            assert path.is_file() and not path.is_symlink(),ref
        pre=validate_planned_preflight(workspace=ROOT,bundle=bundle,slice_id=sid,timeout_seconds=600)
        descriptor=materialize_descriptor(bundle=bundle,slice_id=sid,stage="probe",run_id="input-check-only",
            candidate_hash=pre["candidate_hash"],argv=pre["argv"],cwd=".",timeout_seconds=600,
            target_refs=pre["target_refs"],fixture_refs=pre["fixture_refs"])
        assert all(x["expected_failure_ids"] for x in descriptor["case_contract"]["bindings"])
        assert production_hashes(ROOT,bundle,sid)
    for mutation in ("planned-path","acceptance-projection"):
        bad=copy.deepcopy(bundle)
        if mutation=="planned-path":
            bad["slices"][0]["planned_new_files"]=[]
        else:
            bad["agent_contexts"][0]["acceptance_ids"]=[]
        try:
            validate_planned_preflight(workspace=ROOT,bundle=bad,slice_id="S12",timeout_seconds=600)
        except ValueError:
            pass
        else:
            raise ValueError("Invalid-input mutation admitted: "+mutation)


def assemble():
    dirty=command(["git","status","--porcelain","--",str(PLAN.relative_to(ROOT))])
    if dirty.strip():
        raise ValueError("Preserve or commit local plan changes before materialization.")
    baseline=command(["git","show",BASE+":"+str((PLAN/"semantic-plan-bundle.v1.json").relative_to(ROOT)).replace("\\","/")])
    original=json.loads(baseline)
    bundle=copy.deepcopy(original)
    slices=read(PLAN/"rebuild-inputs/slices.v1.json")
    acceptances=read(PLAN/"rebuild-inputs/acceptances.v1.json")
    for item in slices:
        raw=dict(item)
        expected=raw.pop("slice_input_hash")
        assert digest(raw)==expected,"Recovered slice transport changed"
    expected_ids={oid for a in acceptances for oid in a["obligation_ids"]}
    old_o={o["obligation_id"]:o for o in original["obligations"]}
    old_a={a["acceptance_id"]:a for a in original["acceptances"]}
    removed=[o for o in original["obligations"] if o["obligation_id"] not in expected_ids]
    assert len(removed)==14 and all(o["requirement_id"]=="SM-REPAIR-CONSTRAINTS" for o in removed)
    obligations=[copy.deepcopy(o) for o in original["obligations"] if o["obligation_id"] in expected_ids]
    omap={o["obligation_id"]:o for o in obligations}
    added={
        "O-824-ACCOUNT-ROOT-ENUMERATION":("SM-R02","Per-Project Windows Runner identity"),
        "O-824-SNAPSHOT-PLAN-CONTENT":("SM-W06","Supported persistent project work files"),
        "O-824-SNAPSHOT-APPROVED-ASSETS":("SM-W06","Approved supported persistent assets"),
        "O-824-LAST-PUBLISHED-RPO":("SM-W03","Last successfully published verified Snapshot"),
    }
    for a in acceptances:
        oid=a["obligation_ids"][0]
        if oid not in omap:
            req,subject=added[oid]
            o={"obligation_id":oid,"requirement_id":req,"source_refs":a["source_refs"],
               "subject":subject,"trigger":a["when"],"state_before":a["given"],"state_after":a["then"],
               "expected_behavior":a["oracle"]["expected"],"observable_result":a["oracle"]["observable"],
               "forbidden_result":a["oracle"]["forbidden"],"requirement_type":"Platform",
               "obligation_kind":"behavior","unresolved_fragments":[],"status":"active","depends_on":[]}
            obligations.append(o)
            omap[oid]=o
        else:
            o=omap[oid]
            if oid=="O-08BA4578BEC0":
                o["requirement_id"]="SM-A09"
            if oid=="O-F54FDFC116B0":
                o["requirement_id"]="SM-T11"
            o["source_refs"]=a["source_refs"]
            prev=old_a[a["acceptance_id"]]
            assert prev["assertion_ids"]==a["assertion_ids"],"Original assertion identity changed"
            if prev["oracle"]!=a["oracle"]:
                o["expected_behavior"]=a["oracle"]["expected"]
                o["observable_result"]=a["oracle"]["observable"]
                o["forbidden_result"]=a["oracle"]["forbidden"]
    assert len(set(old_o)&set(omap))==347
    bundle.update(obligations=obligations,acceptances=acceptances,slices=slices)
    amap={a["acceptance_id"]:a for a in acceptances}
    smap={s["slice_id"]:s for s in slices}
    common=[
        "Maintainer-authorized direct input repair; do not rerun VDD or Bootstrap. Historical compiler/lifecycle artifacts are not current proof.",
        "Read LOCAL-HANDOFF.md Q2 contract and implementation-case-map.v1.json. Use current Quick Dev standard profile with governance off.",
        "Probe real atomic boundaries: present -> regression; missing -> causal RED/GREEN/REFACTOR; mixed -> both; unverifiable -> repair harness/environment. Never invent RED or roll back correct behavior.",
        "Use one pytest case per atomic obligation with exact cer_assertion markers. Invoke mapped real C# tests with literal subprocess.run argv, shell=False, exact FullyQualifiedName filter and fresh per-invocation TRX.",
        "Build, discovery, timeout, privilege and setup failures are harness errors, not product AssertionError. Missing/stale/skipped/inconclusive results cannot pass or supply RED.",
        "Freeze wrappers, C# tests, helpers, fixtures and selectors before RED; declare every test dependency before freezing. GREEN/REFACTOR reuse identical inputs.",
        "After causal RED, change only declared production owners; Program.cs edits remain narrow. Respect protected-path authority. No live workspace/runtime/Caddy, shared Skill, Taskmaster, backend authority or historical evidence writes during Phase implementation.",
        "Use disposable roots/SQLite and actual Windows restricted processes, NTFS denial, Job Objects, restart, authenticated operations and retained content. Harmless workloads may isolate unrelated model behavior, not the required boundary.",
        "Preserve every bound assertion in real Q7/Q8 evidence; counts, markers, field presence or historical results alone cannot establish completion.",
    ]
    contexts=[]
    cases=[]
    for s in slices:
        sid=s["slice_id"]
        rows=[omap[x] for x in s["obligation_ids"]]
        py=next(p for p in s["execution_snapshot_paths"] if "/test_" in p and p.endswith(".py"))
        for o in rows:
            o["depends_on"]=[smap[d]["obligation_ids"][0] for d in s["depends_on"]]
            a=next(a for a in acceptances if a["obligation_ids"]==[o["obligation_id"]])
            method=o["obligation_id"].replace("-","_")
            cases.append({"slice_id":sid,"obligation_id":o["obligation_id"],"acceptance_id":a["acceptance_id"],
                "assertion_ids":a["assertion_ids"],"pytest_node":py+"::test_"+method.lower(),
                "dotnet_fully_qualified_name":"PhaseA.Platform.Tests.PhaseB.Repair."+sid+"BoundaryTests."+method,
                "failure_intent_ids":a["red_intent_ids"],"source_refs":a["source_refs"],
                "materialization_owner":"Quick Dev Q2","status":"planned-not-executed"})
        contracts=common+[s["terminal_predicate"]]
        if sid in {"S25","S46","S53"}:
            contracts+=["A18 independent verification is test-owned: Q2 authors an independent-process evidence reader in the declared helper. Verify explicit current isolation, permissions, Snapshot round-trip, fault, migration and redaction artifacts; fix product evidence at its producer. No Taskmaster, --help evidence or generic scoring system."]
        if sid=="S46":
            contracts+=["Run the entire PhaseA.Platform.Tests project and verify all terminal categories against explicit current predecessors. Missing or skipped OS/restart evidence blocks closure."]
        if sid=="S66":
            contracts+=["Resolve distinct principal/tenant/member records correctly; do not impose cross-namespace global identifier inequality."]
        if sid=="S69":
            contracts+=["Former S70 issuance-before-inspection remains test preparation in S69."]
        contexts.append({"slice_id":sid,"requirement_ids":sorted({o["requirement_id"] for o in rows}),
            "obligation_ids":s["obligation_ids"],"acceptance_ids":s["acceptance_ids"],
            "source_refs":sorted({ref for o in rows for ref in o["source_refs"]}),"contracts":contracts,
            "allowed_paths":s["allowed_write_paths"],"forbidden_paths":["logs/phase-a-innernet","runtime/phase-a",".agents/skills",".taskmaster",str(PLAN.relative_to(ROOT)).replace("\\","/")],
            "selector_intents":s["proof"]["selector_intents"],
            "validation_commands":[["python","-m","pytest",py,"-q","-p","no:cacheprovider"]],
            "depends_on":s["depends_on"],"downstream_dependents":s["downstream_dependents"],"recovery":s["recovery"]})
    bundle["agent_contexts"]=contexts
    bundle["failure_intents"]=[{"failure_intent_id":a["red_intent_ids"][0],"failure_id":"FAILURE-"+a["obligation_ids"][0],
        "failure_family":"expected-red","acceptance_ids":[a["acceptance_id"]],"expected_outcome":"fail",
        "selector_intent":next(c["pytest_node"] for c in cases if c["acceptance_id"]==a["acceptance_id"])+"; "+a["oracle"]["expected"]}
        for a in acceptances]
    bundle["pre_slice_coverage"]=[]
    bundle["final_plan_coverage"]=[]
    for s in slices:
        for aid in s["acceptance_ids"]:
            a=amap[aid]
            o=omap[a["obligation_ids"][0]]
            for fid in a["red_intent_ids"]:
                for source in a["source_refs"]:
                    edge={"requirement_id":o["requirement_id"],"obligation_id":o["obligation_id"],
                        "acceptance_id":aid,"source_ref":source,"failure_intent_id":fid}
                    bundle["pre_slice_coverage"].append(edge)
                    bundle["final_plan_coverage"].append(dict(edge,slice_id=s["slice_id"],verification_lane=s["verification_lane"],
                        terminal_predicate=s["terminal_predicate"],stage_scope=["red","green","refactor","terminal"]))
    bundle["behavior_routing"]={"schema":"vdd.behavior-routing-intent.v1","intents":project_intents(bundle),"deferred":[]}
    validate(bundle)
    outputs={"semantic-plan-bundle.v1.json":bundle}
    for key,name in [("obligations","obligations"),("acceptances","acceptances"),("slices","slices"),
                     ("failure_intents","failure-intents"),("pre_slice_coverage","pre-slice-coverage"),
                     ("final_plan_coverage","final-plan-coverage")]:
        outputs[name+".v1.json"]=bundle[key]
    for c in contexts:
        outputs["agent-context/"+c["slice_id"]+"/agent-context.json"]=c
    outputs["implementation-case-map.v1.json"]={"schema":"phase-b-c.implementation-case-map.v1","case_maps":cases,"all_cases":"planned-not-executed"}
    outputs["implementation-order.v1.json"]={"schema":"phase-b-c.implementation-order.v1","order":[s["slice_id"] for s in slices],
        "dependencies":{s["slice_id"]:s["depends_on"] for s in slices},"first_slice":"S12"}
    outputs["input-repair-dispositions.v1.json"]={"schema":"phase-b-c.input-repair-dispositions.v1","baseline_commit":BASE,
        "relocated":[dict(o,disposition="explicit-source-non-goal" if o["status"]=="deferred" else "execution-or-planning-instruction",
                          destination="LOCAL-HANDOFF.md and agent-context.contracts") for o in removed],
        "product_obligations_dropped":[],"retained_product_obligations":347,"added_source_grounded_obligations":list(added),
        "merged_test_setup":{"from_slice":"S70","into_slice":"S69","obligation_ids":next(s["obligation_ids"] for s in original["slices"] if s["slice_id"]=="S70")},
        "compiler_invoked":False,"target_production_modified":False}
    outputs["input-repair-failure-intents.v1.json"]={"schema":"phase-b-c.input-repair-failure-intents.v1",
        "original_failure_intents":original["failure_intents"],
        "bindings":{a["acceptance_id"]:a["red_intent_ids"] for a in original["acceptances"]},
        "reason":"Conditional product RED intents do not infer runtime disposition; harness failures remain blocked."}
    sources=sorted({r.split("#")[0] for o in obligations for r in o["source_refs"]})
    outputs["input-repair-source-index.v1.json"]={"schema":"phase-b-c.input-repair-source-index.v1",
        "sources":[{"path":p,"sha256":"sha256:"+hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in sources]}
    # The plan was clean on entry. Write only current input/projection files.
    for name,value in outputs.items():
        write(PLAN/name,value)
    for sid in ("S7","S36","S41","S70","S71","S72","S77"):
        (PLAN/"agent-context"/sid/"agent-context.json").unlink(missing_ok=True)
    write(MARKER,{"schema":"phase-b-c.input-repair-materialization.v1","baseline_commit":BASE,
        "status":"materialized-checks-pending","output_hashes":{name:"sha256:"+hashlib.sha256((PLAN/name).read_bytes()).hexdigest() for name in outputs},
        "authorizes":[]})
    return bundle


def verify_materialization():
    marker=read(MARKER)
    for name,expected in marker["output_hashes"].items():
        actual="sha256:"+hashlib.sha256((PLAN/name).read_bytes()).hexdigest()
        if actual!=expected:
            raise ValueError("Materialized input changed; refusing to overwrite: "+name)
    bundle=read(PLAN/"semantic-plan-bundle.v1.json")
    validate(bundle)
    for key,name in [("obligations","obligations"),("acceptances","acceptances"),("slices","slices"),
                     ("failure_intents","failure-intents"),("pre_slice_coverage","pre-slice-coverage"),("final_plan_coverage","final-plan-coverage")]:
        assert read(PLAN/(name+".v1.json"))==bundle[key]
    for c in bundle["agent_contexts"]:
        assert read(PLAN/"agent-context"/c["slice_id"]/"agent-context.json")==c
    checked=[]
    for s in bundle["slices"]:
        argv=[sys.executable,"-B","scripts/quick_dev/run.py","--plan",str(PLAN.relative_to(ROOT)),"--slice",s["slice_id"],"--profile","standard"]
        result=json.loads(command(argv))
        if result["status"]!="preflight-passed" or result["authorizes"] or result["errors"]:
            raise ValueError(result)
        checked.append({"slice_id":s["slice_id"],"status":result["status"]})
    source=PLAN/"implementation-repair-input.md"
    for o in bundle["obligations"]:
        for ref in o["source_refs"]:
            path,_,anchor=ref.partition("#")
            text=(ROOT/path).read_text(encoding="utf-8")
            if anchor:
                anchors=set(re.findall(r'id="([^"]+)"',text))
                for line in text.splitlines():
                    if line.startswith("#"):
                        title=re.sub(r"^#+\s*","",line).strip().lower()
                        anchors.add(re.sub(r"[^\w\- ]","",title).replace(" ","-"))
                assert anchor in anchors,ref
    evidence={"schema":"phase-b-c.rebuilt-input-validation.v1","status":"input-checks-passed",
        "bundle_sha256":digest(bundle),"slices":73,"obligations":351,"acceptances":351,
        "public_preflights":checked,"guard_regression":"passed in this invocation",
        "compiler_invoked":False,"model_called":False,"phase_tests_executed":False,"authorizes":[]}
    folder=ROOT/"logs/phase-b-c-input-repair/local-rebuild"
    folder.mkdir(parents=True,exist_ok=True)
    import uuid
    write(folder/(uuid.uuid4().hex+".json"),evidence)
    print(json.dumps({"status":"input-checks-passed","first_slice":"S12","slices":73,
                      "phase_implementation_complete":False,"vdd_required":False}))


def main():
    guard_tests()
    if not MARKER.exists():
        assemble()
    verify_materialization()


if __name__=="__main__":
    main()
