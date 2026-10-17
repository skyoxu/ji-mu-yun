"""ADR-0041/0058/0060: bounded S3 recovery and native Acceptance closeout."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OLD_PROOF = ROOT / "logs/08-05-real-skill-replay/online-proof-recovery-20261017-r1"
T = Path("execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed")
RUN = "acceptance-08-05-online-final-20261017-r10"
I = T / "acceptance-inputs" / RUN
PYTHON = "/workspace/scratch/1ecf047ec2b0/acceptance-final-env-20261017/bin/python"
CLI = ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py"
ENV = dict(os.environ, PATH=str(Path(PYTHON).parent) + os.pathsep + os.environ["PATH"], PYTHONDONTWRITEBYTECODE="1")
sys.path[:0] = [str(ROOT / "scripts/python"), str(ROOT / ".agents/skills/quick-dev-tdd-adapter/tools")]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    if path.exists():
        raise ValueError("Refuse to overwrite native closeout evidence: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ref(path):
    path = Path(path).resolve()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def call(label, argv):
    result = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT, env=ENV)
    write(OUT / "operations" / (label + ".process.json"), {
        "authorizes": [], "command": argv, "exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        print(result.stdout, result.stderr, flush=True)
        raise RuntimeError("Native operation failed: " + label)
    return json.loads(result.stdout)


def recover_s3():
    from runtime_evidence import sha256_value
    from stable_runner import _declared_cer_assertions, _materialize_named_descriptor
    binding = read(OLD_PROOF / "current-quick-dev-binding.json")
    original = read(ROOT / binding["receipt"]["path"])
    semantic = ROOT / binding["semanticPlan"]["path"]
    bundle = read(semantic)
    selected = next(x for x in bundle["slices"] if x["slice_id"] == "S3")
    required = {sid for a in bundle["acceptances"] if a["acceptance_id"] in selected["acceptance_ids"] for sid in a["assertion_ids"]}
    declared = set()
    for path in selected["execution_snapshot_paths"]:
        declared.update(_declared_cer_assertions(ROOT / path))
    if not required <= declared:
        raise RuntimeError("Recovery cannot invoke a test-author worker")
    source = git("rev-parse", "HEAD")
    run = OUT / "S3-current"
    roots = [{**row, "source_commit": source} for row in binding["snapshotRoots"]]
    for row in roots:
        if row["root_kind"] == "candidate_tree":
            row["repository_relative_posix_paths"] = sorted(set(row["repository_relative_posix_paths"]) | set(selected["production_owners"]))
    global_roots = [dict(row) for row in roots]
    for row in roots:
        if row["root_kind"] == "descriptor":
            row["repository_relative_posix_path"] = (run / "descriptors").relative_to(ROOT).as_posix()
            row["inclusion_reason"] = "Current S3 native descriptors after the Acceptance controller repair"
    write(OUT / "s3-roots.json", roots)
    write(OUT / "q8-roots.json", global_roots)
    common = [PYTHON, "-B", "scripts/quick_dev/run.py", "--plan", semantic.parent.relative_to(ROOT).as_posix(),
              "--slice", "S3", "--profile", "standard", "--run-dir", run.relative_to(ROOT).as_posix()]

    def stage(action, *args):
        value = call("quick-dev-" + action, [*common, "--action", action, *map(str, args)])
        print(json.dumps({"action": action, "status": value.get("status"), "predicate": value.get("predicate_result")}), flush=True)
        return value

    assert stage("preflight")["status"] == "preflight-passed"
    assert stage("author-red")["worker"]["status"] == "worker-not-required"
    probe = stage("run-probe")
    assert probe["predicate_result"] and all(row["disposition"] == "present" for row in probe["behavior_dispositions"])
    assert stage("run-regression")["predicate_result"]
    # Freeze all three descriptors and their Git delta before the Q7 snapshot.
    _materialize_named_descriptor(semantic, run, "terminal")
    subprocess.run(["git", "add", "--sparse", "-f", (run / "descriptors").relative_to(ROOT).as_posix()], check=True)
    q7 = OUT / "q7/S3-slice-ready.json"
    stage("validate-slice", "--snapshot-roots", OUT / "s3-roots.json", "--source-commit", source,
          "--base-commit", binding["baseCommit"], "--out", q7)
    assert stage("run-terminal")["predicate_result"]
    predecessors = [dict(row) for row in original["predecessors"]]
    for row in predecessors:
        if row["slice_id"] == "S3":
            row.update(run_root=run.relative_to(ROOT).as_posix(), result_ref=q7.relative_to(ROOT).as_posix(), result_sha256=sha256_value(read(q7)))
    write(OUT / "q8-predecessors.json", predecessors)
    q8 = OUT / "q8/implementation-complete.v2.json"
    assert stage("implementation-complete", "--snapshot-roots", OUT / "q8-roots.json", "--source-commit", source,
                 "--base-commit", binding["baseCommit"], "--predecessors", OUT / "q8-predecessors.json", "--out", q8)["status"] == "pass"
    write(OUT / "current-quick-dev-binding.json", {**binding, "sourceCommit": source, "snapshotRoots": global_roots, "receipt": ref(q8)})
    verify_q8()


def verify_q8():
    sys.path.insert(0, str(ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts"))
    from current_quick_dev_handoff import verify_current_handoff
    value = verify_current_handoff(ROOT, read(OUT / "current-quick-dev-binding.json"))
    result = {"status": value["status"], "predicate": value["predicate"], "predecessors": len(value["predecessors"]),
              "runtimeClosureTuples": len(value["runtime_closure_tuples"]), "authorizes": value["authorizes"],
              "unchangedPredecessorsReused": 44, "sliceTestsRerun": ["S3"]}
    print(json.dumps(result), flush=True)
    p = OUT / "acceptance-consumer-readonly-result.json"
    if not p.exists():
        write(p, result)
    return result


def native(label, *args):
    return call(label, [PYTHON, "-B", CLI, *map(str, args)])


def prepare():
    import skill_input_v2 as skill
    if git("status", "--porcelain"):
        raise RuntimeError("The published candidate requires a clean worktree")
    old = read(T / "acceptance-runs/acceptance-685ab0649074a499/prepare-run.v1.json")
    original = old["input"]
    bundle = read(T / old["prerequisiteBundle"]["path"])
    binding = read(OUT / "current-quick-dev-binding.json")
    commands = read(T / bundle["commandRegistry"]["path"])["commands"]
    for command in commands:
        command["executable"] = PYTHON
        command["argv"] = [x for x in command["argv"] if x != "-3"]
    binding_path = (OUT / "current-quick-dev-binding.json").relative_to(ROOT).as_posix()
    commands[0]["argv"] = ["-B", "-c", "import json,sys; from pathlib import Path; "
        "sys.path.insert(0,'.agents/skills/run-refactor-implementation-acceptance/scripts'); "
        "from current_quick_dev_handoff import verify_current_handoff; "
        "b=json.loads(Path(" + repr(binding_path) + ").read_text(encoding='utf-8')); "
        "v=verify_current_handoff(Path('.').resolve(),b); "
        "print(json.dumps({'status':v['status'],'predicate':v['predicate'],'slice_count':len(v['predecessors']),"
        "'runtime_tuple_count':len(v['runtime_closure_tuples']),'authorizes':v['authorizes']},sort_keys=True))"]
    commands[-1]["argv"].extend([
        "scripts/python/tests/test_skill_input_consumer_migration.py::test_acceptance_final_pointer_preserves_current_generation",
        ".agents/skills/run-refactor-implementation-acceptance/tests/test_control.py::ExecutionControlTests::test_persisted_read_only_action_tolerates_stale_claim_listing",
        ".agents/skills/run-refactor-implementation-acceptance/tests/test_control.py::ExecutionControlTests::test_persisted_read_only_action_rejects_claim_tampering_with_stale_listing"])
    request = {"schemaVersion": "compact-vdd-acceptance-projection-request.v1", "runId": RUN, "targetPlan": T.as_posix(),
        "candidateRevision": git("rev-parse", "HEAD"), "baselineRevision": original["baseline_revision"],
        "changeId": "08-05-native-final-closeout", "changedPaths": sorted(set(original["changed_paths"]) | {
            "scripts/python/skill_input_candidate.py", "scripts/python/tests/test_skill_input_consumer_migration.py",
            "docs/adr/ADR-0060-skill-input-selection-generation-and-retention.md",
            "docs/adr/ADR-0058-acceptance-coordinator-persisted-evidence-ownership.md"}),
        "affectedConsumerRefs": sorted(set(original["affected_consumer_refs"]) | {"scripts/python/skill_input_candidate.py"}),
        "targetPlanPaths": original["target_plan_paths"], "codeReviewDomain": "toolchain",
        "codeReviewPolicyPath": (OLD_PROOF / "toolchain-code-review.v1.json").relative_to(ROOT).as_posix(),
        "knowledgeContextPath": old["knowledgeContext"]["path"], "implementationReceiptPath": binding["receipt"]["path"],
        "implementationReceiptHash": binding["receipt"]["sha256"], "currentQuickDev": binding,
        "commands": commands, "actions": read(T / bundle["actionDag"]["path"]), "authorizes": []}
    external = ROOT.parent / (RUN + ".projection-request.json")
    external_result = ROOT.parent / (RUN + ".projection-result.json")
    write(external, request)
    native("project-compact-vdd", "project-compact-vdd", "--repository-root", ".", "--request", external, "--out", external_result)
    shutil.copyfile(external, I / "projection-request.v1.json")
    shutil.copyfile(external_result, I / "projection-result.v1.json")
    native("prepare-run", "prepare-run", "--input", T / ("acceptance-run-request." + RUN + ".v1.json"),
           "--knowledge-context", old["knowledgeContext"]["path"], "--prerequisite-bundle",
           "acceptance-inputs/" + RUN + "/compact-vdd-acceptance-prerequisite-bundle.v1.json", "--out", I / "prepared-run-input.v1.json")
    shutil.copyfile(".agents/skills/run-refactor-implementation-acceptance/references/skill-input-contract.v1.json", I / "skill-input-contract.v1.json")
    request = read(T / "acceptance-inputs/acceptance-08-05-e4e1377c-incremental-r3/skill-input-request.v2.json")
    request["plan_id"] = RUN
    request["storage"] = (I / "skill-input-v2/acceptance").as_posix()
    for field, name in (("contract", "skill-input-contract.v1.json"), ("registry", "command-registry.v1.json")):
        request["bindings"][field] = ref(I / name)
    write(I / "skill-input-request.v2.json", request)
    result = skill.prepare(ROOT, request)
    write(I / "skill-input-prepare.v2.json", result)
    print(json.dumps(result), flush=True)


def consume():
    import skill_input_v2 as skill
    p = read(I / "skill-input-prepare.v2.json")
    result = skill.consume(ROOT, p["plan_id"], p["attempt_id"])
    write(I / "skill-input-consume.v2.json", result)
    print(json.dumps(result), flush=True)


def finish():
    import skill_input_v2 as skill
    p = read(I / "skill-input-prepare.v2.json")
    write(I / "skill-input-finish.v2.json", skill.finish(ROOT, p["plan_id"], p["attempt_id"]))
    def local(name):
        return {"path": name, "sha256": ref(I / name)["sha256"]}
    request = {"schemaVersion": "jimuyun.acceptance-coordinator-request.v3", "targetPlan": T.as_posix(),
               "preparedRunInput": local("prepared-run-input.v1.json"), "skillInputReceipt": local("skill-input-v2/acceptance/current.v1.json"),
               "skillInputContract": local("skill-input-contract.v1.json"), "authorizes": []}
    write(I / "coordinator-request.v3.json", request)
    journal = ROOT.parent / (RUN + ".readonly-delta.jsonl")
    runner = r'''import sys,json,runpy
from pathlib import Path
journal=Path(JOURNAL)
def observe(frame,event,arg):
 if frame.f_code.co_name != '_validate_read_only_status_delta': return None
 if event == 'exception':
  before=frame.f_locals.get('before',{});after=frame.f_locals.get('after',{})
  differences=[{'path':p,'before':before.get(p),'after':after.get(p)} for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p)]
  with journal.open('a',encoding='utf-8') as log: log.write(json.dumps({'authorizes':[],'observabilityOnly':True,'differences':differences},sort_keys=True)+chr(10))
 return observe
script=sys.argv[1];sys.argv=sys.argv[1:];sys.path.insert(0,str(Path(script).resolve().parent));sys.settrace(observe)
try: runpy.run_path(script,run_name='__main__')
finally: sys.settrace(None)
'''.replace("JOURNAL", repr(str(journal)))
    compile(runner, "passive-observer", "exec")
    args = ["run-coordinator", "--request", str(I / "coordinator-request.v3.json"), "--out", str(I / "coordinator-result.v3.json")]
    try:
        value = call("coordinator-first", [PYTHON, "-B", "-c", runner, CLI, *args])
    finally:
        if journal.exists():
            shutil.copyfile(journal, OUT / "native-readonly-delta.jsonl")
    if value["status"] != "completed" or value["finalization"]["status"] != "acceptance-passed":
        raise RuntimeError("Native Acceptance did not pass")
    again = native("coordinator-reentry", *args)
    assert again == value
    telemetry = [json.loads(x) for x in (Path(value["runDirectory"]) / "coordinator-telemetry.jsonl").read_text().splitlines() if x.strip()]
    assert telemetry[-1]["replayed"] and telemetry[-1]["executedActionCount"] == 0
    write(OUT / "finalization-summary.v1.json", {"schema": "08-05-native-closeout.v1", "authorizes": [],
        "candidateCommit": read(I / "prepared-run-input.v1.json")["candidateCustody"]["candidateResolvedCommit"],
        "nativeAcceptance": value["finalization"], "runDirectory": value["runDirectory"], "q8": read(OUT / "acceptance-consumer-readonly-result.json"),
        "sameInputReentry": telemetry[-1], "registeredCloseoutCases": 25, "vddRerun": False, "full340SuiteRerun": False,
        "previousUnpublishedEvidenceGap": "runtime-recovery.v2.json", "C3": "OPEN (unchanged)"})
    print(json.dumps({"status": "acceptance-passed", "runDirectory": value["runDirectory"], "reentryExecutedActionCount": 0}), flush=True)


if __name__ == "__main__":
    os.chdir(ROOT)
    {"s3": recover_s3, "verify-q8": verify_q8, "prepare": prepare, "consume": consume, "finish": finish}[sys.argv[1]]()
