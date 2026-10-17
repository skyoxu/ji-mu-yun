"""Recover explicit 08-05 predecessors through native Quick Dev APIs and CLI.

ADR-0041/ADR-0058. This driver selects inputs and captures commands only.
The runtime owns descriptors, observations, Q6, Q7 and Q8 publication.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
TOOLS = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools"
sys.path.insert(0, str(TOOLS))
from runtime_evidence import create_json, load_json, sha256_value, sha256_bytes
from coverage_predicates import _replay_snapshot, validate_slice_ready, _reread_edge, _semantic_index
from behavior_routing import read_route, current_result, verify_stage
from current_router import materialize_descriptor
from stable_runner import candidate_identity, _descriptor_inputs

PLAN = ROOT / "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/recompilation-4/cer-repair-1/quick-dev-ready/current-plan"
SEMANTIC = PLAN / "semantic-plan-bundle.v1.json"
PRIOR = HERE / "q8-attempt/predecessors.json"
RUNS = HERE / "current-run-q8-recovery-r2"
OUT = HERE / "current-run-q8-recovery-r4"
SELECTION = HERE / "explicit-recovery-selection.json"


def relative(path):
    return path.resolve().relative_to(ROOT).as_posix()


def record(path, value):
    if isinstance(value, dict):
        create_json(path, value)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, indent=2) + "\n")


def command(slice_id, action, capture, *extra):
    capture.mkdir(parents=True, exist_ok=False)
    argv = [sys.executable, "-X", "utf8", "-B", "scripts/quick_dev/run.py",
            "--plan", relative(PLAN), "--slice", slice_id, "--profile", "standard",
            "--action", action, *extra]
    start = time.monotonic()
    with (capture / "stdout.txt").open("xb") as stdout, (capture / "stderr.txt").open("xb") as stderr:
        result = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr, check=False)
    text = (capture / "stdout.txt").read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except ValueError:
        payload = {"unparsed_output": text[-2000:]}
    record(capture / "command-result.json", {"argv": argv, "exit_code": result.returncode,
           "elapsed_seconds": time.monotonic() - start, "result": payload, "authorizes": []})
    print(json.dumps({"slice": slice_id, "action": action, "exit": result.returncode,
                      "status": payload.get("status"), "predicate": payload.get("predicate_result")}), flush=True)
    if result.returncode or payload.get("predicate_result") is False or payload.get("status") in {"blocked", "repair-vdd", "environment-blocked"}:
        raise ValueError(f"{slice_id} {action} failed; see {relative(capture)}")
    return payload


def prepare():
    OUT.mkdir(exist_ok=False)
    bundle = load_json(SEMANTIC)
    previous = json.loads(PRIOR.read_text(encoding="utf-8"))
    impact = load_json(HERE / "q8-attempt/input-impact.json")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    audit = []
    reusable = []
    pending = []
    for predecessor in previous:
        sid = predecessor["slice_id"]
        ready = load_json(ROOT / predecessor["result_ref"])
        run = ROOT / predecessor["run_root"]
        try:
            if sha256_value(ready) != predecessor["result_sha256"] or ready["plan_sha256"] != sha256_bytes(SEMANTIC.read_bytes()):
                raise ValueError("explicit predecessor identity changed")
            _replay_snapshot(ROOT, ready["snapshot_roots"], ready["source_commit"], ready.get("base_commit"), {"snapshot_manifest": ready["snapshot_manifest"]})
            checked = validate_slice_ready(workspace=ROOT, semantic_plan=SEMANTIC, run_root=run,
                slice_id=sid, snapshot_roots=ready["snapshot_roots"], source_commit=ready["source_commit"],
                base_commit=ready.get("base_commit"), out=OUT / "reuse-audit" / sid / "q7-revalidation.json")
            route = read_route(ROOT, bundle, run, sid)
            if checked["behavior_route_sha256"] != ready["behavior_route_sha256"]:
                raise ValueError("original route differs")
            terminal = load_json(run / "canonical-evidence/terminal/stage-result.v2.json")
            descriptor = load_json(run / "descriptors/terminal.json")
            verify_stage(ROOT, bundle, run, descriptor)
            current_result(ROOT, bundle, sid, terminal)
            if terminal.get("predicate_result") is not True or terminal.get("candidate_hash") != ready["candidate_hash"]:
                raise ValueError("terminal not admissible")
            _, expected = _semantic_index(bundle, sid)
            actual = {}
            for ref in terminal["runtime_edges"]:
                edge = _reread_edge(ROOT, run, ref, slice_id=sid, stage="terminal", selector_identity=terminal["selector_identity"])
                actual.setdefault(edge["acceptance_id"], []).append(edge["assertion_id"])
            if {aid: set(ids) for aid, ids in actual.items()} != expected or any(len(ids) != len(set(ids)) for ids in actual.values()):
                raise ValueError("terminal exact cover differs")
            reusable.append(predecessor)
            audit.append({"slice_id": sid, "status": "reuse-original-predecessor", "original": predecessor,
                          "meaning": "current read-only native proof revalidation; original receipt unchanged"})
        except (ValueError, OSError, KeyError) as exc:
            pending.append(predecessor)
            observed = next(row for row in impact["slices"] if row["slice_id"] == sid)
            audit.append({"slice_id": sid, "status": "fresh-characterization-required", "reason": str(exc),
                          "observed_input_changes": observed["observed_input_changes"]})
    # The frozen bundle declares no inter-obligation dependencies. Preserve the
    # explicit predecessor order; no fresh implementation scheduling is inferred.
    if any(item.get("depends_on") for item in bundle["obligations"]):
        raise ValueError("nonempty dependencies require explicit topological recovery order")
    record(OUT / "recovery-inputs.json", {"head": head, "plan": relative(PLAN),
        "plan_sha256": sha256_bytes(SEMANTIC.read_bytes()), "prior_predecessors": relative(PRIOR),
        "reusable": reusable, "pending": pending, "audit": audit, "stage_timeout_seconds": 600,
        "product_budgets_changed": False, "authorizes": []})
    print(json.dumps({"reusable": len(reusable), "pending": len(pending), "pending_slices": [p["slice_id"] for p in pending]}), flush=True)


def selected_runs():
    selection = load_json(SELECTION)
    pending = load_json(OUT / "recovery-inputs.json")["pending"]
    if set(selection["runs"]) != {row["slice_id"] for row in pending}:
        raise ValueError("explicit run selection must cover exactly the pending slices")
    runs = {}
    for sid, name in selection["runs"].items():
        if Path(name).name != name or not name.startswith(sid + "-current-r"):
            raise ValueError("invalid explicit run name")
        runs[sid] = RUNS / name
    return runs


def selected_predecessor(sid, run):
    predecessor = load_json(run / "new-predecessor.json")
    if predecessor["slice_id"] != sid or predecessor["run_root"] != relative(run):
        raise ValueError("selected predecessor points outside its explicit slice/run")
    if predecessor["result_ref"] != relative(run / "slice-ready-result.v2.json"):
        raise ValueError("selected predecessor result points outside its explicit run")
    if predecessor["result_sha256"] != sha256_value(load_json(ROOT / predecessor["result_ref"])):
        raise ValueError("selected predecessor result identity changed")
    return predecessor


def run_slice(sid):
    inputs = load_json(OUT / "recovery-inputs.json")
    predecessor = next(p for p in inputs["pending"] if p["slice_id"] == sid)
    bundle = load_json(SEMANTIC)
    if sha256_bytes(SEMANTIC.read_bytes()) != inputs["plan_sha256"]:
        raise ValueError("active plan changed")
    run = selected_runs()[sid]
    if (run / "new-predecessor.json").is_file():
        selected_predecessor(sid, run)
        print(sid + " selected completed predecessor retained; no tests launched", flush=True)
        return
    if run.exists():
        raise ValueError(f"explicit run {relative(run)} is partial or failed; inspect before selecting a successor")
    run.mkdir(exist_ok=False)
    record(run / "explicit-predecessor.json", {"predecessor": predecessor, "authorizes": []})
    failures = load_json(SELECTION).get("prior_failures", {}).get(sid, [])
    if failures:
        record(run / "failure-history.json", [load_json(ROOT / path) for path in failures])
    previous_ready = load_json(ROOT / predecessor["result_ref"])
    # Older slice-ready predecessors kept the immutable baseline only inside
    # their snapshot manifest.  Preserve that explicit predecessor binding
    # instead of passing a null base revision to the stable runner.
    previous_base_commit = previous_ready.get("base_commit") or previous_ready.get("snapshot_manifest", {}).get("git_delta", {}).get("base_commit")
    if not isinstance(previous_base_commit, str) or not previous_base_commit:
        raise ValueError(f"{sid} predecessor has no explicit base commit")
    roots = []
    for row in previous_ready["snapshot_roots"]:
        item = {k: v for k, v in row.items() if k in {"root_kind", "repository_relative_posix_path", "repository_relative_posix_paths", "inclusion_reason"}}
        if item["root_kind"] in {"descriptor", "plan_state_transition"}:
            item.pop("repository_relative_posix_paths", None)
            item["repository_relative_posix_path"] = relative(run / "descriptors" if item["root_kind"] == "descriptor" else run)
        if item["root_kind"] == "candidate_tree":
            paths = item.pop("repository_relative_posix_paths", [item.pop("repository_relative_posix_path", "")])
            paths = [p for p in paths if p]
            if "scripts/sc/skill_package_replay.py" in paths:
                paths += ["scripts/sc/skill_replay_runtime.py"]
            item["repository_relative_posix_paths"] = sorted(set(paths))
        if item["root_kind"] == "fixture":
            paths = item.pop("repository_relative_posix_paths", [item.pop("repository_relative_posix_path", "")])
            item["repository_relative_posix_paths"] = sorted(set([p for p in paths if p] + ["scripts/sc/tests/tc_d1_cer/conftest.py"]))
        roots.append(item)
    record(run / "snapshot-roots.json", roots)
    # Recommendation is read-only; descriptors must already exist for its root.
    command(sid, "preflight", run / "commands/01-preflight")
    authored = command(sid, "author-red", run / "commands/02-materialize-probe",
                       "--run-dir", relative(run), "--worker-timeout-seconds", "600")
    if authored.get("worker", {}).get("status") != "worker-not-required":
        raise ValueError("unexpected model-backed authoring during proof recovery")
    command(sid, "recommendation", run / "commands/03-recommendation",
            "--snapshot-roots", relative(run / "snapshot-roots.json"), "--source-commit", inputs["head"],
            "--base-commit", previous_base_commit)
    command(sid, "run-probe", run / "commands/04-probe", "--run-dir", relative(run))
    route = read_route(ROOT, bundle, run, sid)
    if any(row["disposition"] != "present" for row in route["behavior_dispositions"]):
        raise ValueError("not all behavior is present; retain probe and inspect before implementation")
    argv, targets, fixtures = _descriptor_inputs(bundle, PLAN, sid)
    identity = candidate_identity(ROOT, bundle, sid)
    for stage in ("regression", "terminal"):
        descriptor = materialize_descriptor(bundle=bundle, slice_id=sid, stage=stage, run_id=run.name,
            candidate_hash=identity["candidate_hash"], argv=argv, cwd=".", timeout_seconds=600,
            target_refs=targets, fixture_refs=fixtures, routing_result=route)
        record(run / "descriptors" / (stage + ".json"), descriptor)
    command(sid, "execute-stage", run / "commands/05-regression", "--run-dir", relative(run),
            "--descriptor", relative(run / "descriptors/regression.json"))
    command(sid, "validate-slice", run / "commands/06-q7", "--run-dir", relative(run),
            "--snapshot-roots", relative(run / "snapshot-roots.json"), "--source-commit", inputs["head"],
            "--base-commit", previous_base_commit, "--out", relative(run / "slice-ready-result.v2.json"))
    command(sid, "execute-stage", run / "commands/07-terminal", "--run-dir", relative(run),
            "--descriptor", relative(run / "descriptors/terminal.json"))
    ready = load_json(run / "slice-ready-result.v2.json")
    record(run / "new-predecessor.json", {"slice_id": sid, "run_root": relative(run),
           "result_ref": relative(run / "slice-ready-result.v2.json"), "result_sha256": sha256_value(ready)})
    print(sid + " current regression/Q6/Q7/terminal completed", flush=True)


def finish():
    inputs = load_json(OUT / "recovery-inputs.json")
    predecessors = {row["slice_id"]: row for row in inputs["reusable"]}
    for row in inputs["pending"]:
        sid = row["slice_id"]
        predecessors[sid] = selected_predecessor(sid, selected_runs()[sid])
    ordered = [predecessors[row["slice_id"]] for row in json.loads(PRIOR.read_text(encoding="utf-8"))]
    record(OUT / "predecessors.json", ordered)
    roots = json.loads((HERE / "q8-attempt/snapshot-roots.json").read_text(encoding="utf-8"))
    # Whole-plan candidate includes the new transitive replay runtime. The
    # prior explicit root set is retained, not replaced with a narrower scope.
    for row in roots:
        if row["root_kind"] == "candidate_tree":
            row["repository_relative_posix_paths"] = sorted(set(row["repository_relative_posix_paths"] + ["scripts/sc/skill_replay_runtime.py"]))
        elif row["root_kind"] == "fixture":
            row["repository_relative_posix_paths"] = sorted(set(row["repository_relative_posix_paths"] + ["scripts/sc/tests/tc_d1_cer/conftest.py", "scripts/sc/tests/test_skill_replay_review2_regressions.py"]))
    record(OUT / "whole-plan-snapshot-roots.json", roots)
    prior_input = load_json(ROOT / load_json(HERE / "q8-attempt/summary.json")["prior_terminal_input"])
    command("S45", "implementation-complete", OUT / "q8-command",
            "--snapshot-roots", relative(OUT / "whole-plan-snapshot-roots.json"),
            "--predecessors", relative(OUT / "predecessors.json"), "--source-commit", inputs["head"],
            "--base-commit", prior_input["snapshot_manifest"]["git_delta"]["base_commit"],
            "--out", relative(OUT / "implementation-complete-result.v2.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["prepare", "slice", "all", "finish"])
    parser.add_argument("--slice")
    args = parser.parse_args()
    try:
        if args.operation == "prepare":
            prepare()
        elif args.operation == "slice":
            run_slice(args.slice)
        elif args.operation == "finish":
            finish()
        else:
            for predecessor in load_json(OUT / "recovery-inputs.json")["pending"]:
                run_slice(predecessor["slice_id"])
            finish()
    except (ValueError, OSError, KeyError) as exc:
        print("STOP: " + str(exc), flush=True)
        raise SystemExit(1)
