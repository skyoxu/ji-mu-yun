"""ADR-0053/0058/0060: native, explicitly bound online Acceptance recovery."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
T = Path("execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed")
RUN = "acceptance-08-05-online-proof-recovery-20261017-r1"
I = T / "acceptance-inputs" / RUN
OLD = T / "acceptance-inputs/acceptance-08-05-e4e1377c-incremental-r3"
CLI = ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py"
PYTEST_PYTHON = "/workspace/scratch/1ecf047ec2b0/acceptance-env-20261017/bin/python"
sys.path.insert(0, str(ROOT / "scripts/python"))
import skill_input_v2 as skill


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    if path.exists():
        raise ValueError("Refuse to overwrite recovery input: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def cli(*args):
    cmd = [sys.executable, "-B", CLI, *map(str, args)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        print(result.stdout, flush=True)
        print(result.stderr, flush=True)
        raise RuntimeError("Native CLI failed: " + args[0])
    value = json.loads(result.stdout)
    print(json.dumps({"nativeOperation": args[0], "status": value.get("status"),
                      "finalization": value.get("finalization", {}).get("status")
                      if value.get("finalization") else None}), flush=True)
    return value


def prepare():
    if git("status", "--porcelain"):
        raise ValueError("Commit candidate requires a clean worktree")
    prepared = read(T / "acceptance-runs/acceptance-685ab0649074a499/prepare-run.v1.json")
    original = prepared["input"]
    bundle = read(T / prepared["prerequisiteBundle"]["path"])
    binding = read(OUT / "current-quick-dev-binding.json")
    commands = read(T / bundle["commandRegistry"]["path"])["commands"]
    for command in commands:
        command["executable"] = PYTEST_PYTHON
        command["argv"] = [x for x in command["argv"] if x != "-3"]
    binding_path = (OUT / "current-quick-dev-binding.json").relative_to(ROOT).as_posix()
    commands[0]["argv"] = ["-B", "-c",
        "import json,sys; from pathlib import Path; "
        "sys.path.insert(0,'.agents/skills/run-refactor-implementation-acceptance/scripts'); "
        "from current_quick_dev_handoff import verify_current_handoff; "
        "b=json.loads(Path(" + repr(binding_path) + ").read_text(encoding='utf-8')); "
        "v=verify_current_handoff(Path('.').resolve(),b); "
        "print(json.dumps({'status':v['status'],'predicate':v['predicate'],"
        "'slice_count':len(v['predecessors']),'runtime_tuple_count':len(v['runtime_closure_tuples']),"
        "'authorizes':v['authorizes']},sort_keys=True))"]
    commands[-1]["argv"].append("scripts/python/tests/test_skill_input_consumer_migration.py::test_acceptance_final_pointer_preserves_current_generation")
    request = {
        "schemaVersion": "compact-vdd-acceptance-projection-request.v1",
        "runId": RUN, "targetPlan": T.as_posix(),
        "candidateRevision": git("rev-parse", "HEAD"), "baselineRevision": original["baseline_revision"],
        "changeId": "08-05-owner-proof-and-live-generation-recovery",
        "changedPaths": sorted(set(original["changed_paths"]) | {
            "scripts/python/skill_input_candidate.py",
            "scripts/python/tests/test_skill_input_consumer_migration.py",
            "docs/adr/ADR-0060-skill-input-selection-generation-and-retention.md"}),
        "affectedConsumerRefs": sorted(set(original["affected_consumer_refs"]) | {"scripts/python/skill_input_candidate.py"}),
        "targetPlanPaths": original["target_plan_paths"], "codeReviewDomain": "toolchain",
        "codeReviewPolicyPath": (OUT / "toolchain-code-review.v1.json").relative_to(ROOT).as_posix(),
        "knowledgeContextPath": prepared["knowledgeContext"]["path"],
        "implementationReceiptPath": binding["receipt"]["path"],
        "implementationReceiptHash": binding["receipt"]["sha256"],
        "commands": commands, "actions": read(T / bundle["actionDag"]["path"]),
        "currentQuickDev": binding, "authorizes": []}
    external = ROOT.parent / "online-acceptance-projection-20261017.request.json"
    external_result = ROOT.parent / "online-acceptance-projection-20261017.result.json"
    write(external, request)
    cli("project-compact-vdd", "--repository-root", ".", "--request", external, "--out", external_result)
    shutil.copyfile(external, I / "projection-request.v1.json")
    shutil.copyfile(external_result, I / "projection-result.v1.json")
    cli("prepare-run", "--input", T / ("acceptance-run-request." + RUN + ".v1.json"),
        "--knowledge-context", prepared["knowledgeContext"]["path"],
        "--prerequisite-bundle", "acceptance-inputs/" + RUN + "/compact-vdd-acceptance-prerequisite-bundle.v1.json",
        "--out", I / "prepared-run-input.v1.json")
    source = ".agents/skills/run-refactor-implementation-acceptance/references/skill-input-contract.v1.json"
    shutil.copyfile(source, I / "skill-input-contract.v1.json")
    request = read(OLD / "skill-input-request.v2.json")
    request["plan_id"] = RUN
    request["storage"] = (I / "skill-input-v2/acceptance").as_posix()
    for field, name in (("contract", "skill-input-contract.v1.json"), ("registry", "command-registry.v1.json")):
        request["bindings"][field] = {"path": (I / name).as_posix(), "sha256": sha(I / name)}
    write(I / "skill-input-request.v2.json", request)
    result = skill.prepare(ROOT, request)
    write(I / "skill-input-prepare.v2.json", result)
    print(json.dumps(result), flush=True)


def consume():
    prepared = read(I / "skill-input-prepare.v2.json")
    result = skill.consume(ROOT, prepared["plan_id"], prepared["attempt_id"])
    write(I / "skill-input-consume.v2.json", result)
    print(json.dumps(result), flush=True)


def finish():
    prepared = read(I / "skill-input-prepare.v2.json")
    result = skill.finish(ROOT, prepared["plan_id"], prepared["attempt_id"])
    write(I / "skill-input-finish.v2.json", result)
    def ref(path):
        return {"path": path, "sha256": sha(I / path)}
    request = {"schemaVersion": "jimuyun.acceptance-coordinator-request.v3", "targetPlan": T.as_posix(),
        "preparedRunInput": ref("prepared-run-input.v1.json"),
        "skillInputReceipt": ref("skill-input-v2/acceptance/current.v1.json"),
        "skillInputContract": ref("skill-input-contract.v1.json"), "authorizes": []}
    write(I / "coordinator-request.v3.json", request)
    result = cli("run-coordinator", "--request", I / "coordinator-request.v3.json", "--out", I / "coordinator-result.v3.json")
    if result["status"] != "completed" or result["finalization"]["status"] != "acceptance-passed":
        raise RuntimeError("Native Acceptance did not pass")
    again = cli("run-coordinator", "--request", I / "coordinator-request.v3.json", "--out", I / "coordinator-result.v3.json")
    assert result == again
    run = Path(result["runDirectory"])
    telemetry = [json.loads(x) for x in (run / "coordinator-telemetry.jsonl").read_text().splitlines() if x.strip()]
    assert telemetry[-1]["replayed"] and telemetry[-1]["executedActionCount"] == 0
    write(OUT / "finalization-summary.v1.json", {
        "schema": "08-05-online-repair-closeout.v1", "authorizes": [],
        "candidateCommit": read(I / "prepared-run-input.v1.json")["candidateCustody"]["candidateResolvedCommit"],
        "nativeAcceptance": result["finalization"], "runDirectory": run.as_posix(),
        "q8Readonly": read(OUT / "acceptance-consumer-readonly-result.json"),
        "regressions": {"skillInput": 96, "registeredAcceptanceCloseout": 23},
        "sameInputReentry": telemetry[-1], "originalRuntimeEvidenceReused": True,
        "full340SuiteRerun": False, "vddRerun": False, "C3": "OPEN (unchanged)"})
    print(json.dumps({"status": "acceptance-passed", "reentryExecutedActionCount": 0, "runDirectory": run.as_posix()}), flush=True)


if __name__ == "__main__":
    os.chdir(ROOT)
    {"prepare": prepare, "consume": consume, "finish": finish}[sys.argv[1]]()
