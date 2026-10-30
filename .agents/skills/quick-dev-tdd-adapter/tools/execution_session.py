"""ADR-0041: deterministic wiring of explicit native runs, without model calls."""
from pathlib import Path
import json
import re
import subprocess

from runtime_evidence import ROOT_KINDS, create_json, load_json, safe_relative, sha256_bytes, sha256_value

SCHEMA = "quick-dev.execution-session.v1"


def _failure_history(root, path):
    value = json.loads(_path(root, path).read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("session failure history must be an ordered list of objects")
    return value


def _path(root, value, *, output=False):
    if not isinstance(value, str):
        raise ValueError("session path must be a repository-relative string")
    relative = safe_relative(value)
    path = root / relative
    path.resolve().relative_to(root.resolve())
    for parent in (path, *path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("session path contains a symlink")
    if output and not relative.startswith("logs/"):
        raise ValueError("session output must be under logs/")
    return path


def _roots(root, rows):
    if not isinstance(rows, list) or len(rows) != len(ROOT_KINDS):
        raise ValueError("session requires all eight snapshot root kinds")
    kinds = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("inclusion_reason"), str) or not row["inclusion_reason"]:
            raise ValueError("invalid session snapshot root")
        if row.get("root_kind") not in ROOT_KINDS:
            raise ValueError("invalid session snapshot root kind")
        kinds.append(row["root_kind"])
        one, many = row.get("repository_relative_posix_path"), row.get("repository_relative_posix_paths")
        if one is not None and many is None:
            paths = [one]
        elif one is None and isinstance(many, list) and many:
            paths = many
        else:
            raise ValueError("invalid session snapshot paths")
        for path in paths:
            _path(root, path)
    if set(kinds) != set(ROOT_KINDS):
        raise ValueError("session snapshot root kinds must be unique")


def preflight_session(api, semantic, request):
    """Read-only admission. Future tests remain Q2-owned planned inputs."""
    root, bundle = api.ROOT, load_json(semantic)
    required = {"schema", "plan_sha256", "profile", "source_commit", "base_commit", "slices",
                "snapshot_roots", "out", "targeted_timeout_seconds"}
    if not isinstance(request, dict) or not required <= set(request) or set(request) - required - {"detached_bundle", "failure_history"}:
        raise ValueError("session request fields missing or unknown")
    if request["schema"] != SCHEMA or request["plan_sha256"] != sha256_bytes(semantic.read_bytes()):
        raise ValueError("session plan identity mismatch")
    if "behavior_routing" not in bundle:
        raise ValueError("session requires a current CER-capable plan")
    if not isinstance(request["profile"], str):
        raise ValueError("session profile must be a string")
    api.profile_contract(request["profile"])
    budget = request["targeted_timeout_seconds"]
    if type(budget) is not int or not 1 <= budget <= 1800:
        raise ValueError("session targeted timeout must be 1..1800 seconds")
    for key in ("source_commit", "base_commit"):
        commit = request[key]
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("session requires explicit full " + key)
        check = subprocess.run(["git", "cat-file", "-e", commit + "^{commit}"], cwd=root, capture_output=True, shell=False)
        if check.returncode:
            raise ValueError("session commit unavailable: " + key)
    check = subprocess.run(["git", "merge-base", "--is-ancestor", request["base_commit"], request["source_commit"]], cwd=root, capture_output=True, shell=False)
    if check.returncode:
        raise ValueError("session baseline is not an ancestor of source")
    if request["profile"] == "self-hosted":
        if not isinstance(request.get("detached_bundle"), str):
            raise ValueError("self-hosted session requires detached_bundle before execution")
        api._detached_promotion_binding(_path(root, request["detached_bundle"]), request["profile"])
    elif request.get("detached_bundle") is not None:
        raise ValueError("detached_bundle requires self-hosted execution profile")
    if "failure_history" in request:
        _failure_history(root, request["failure_history"])
    slices = request["slices"]
    if not isinstance(slices, list) or not slices or any(not isinstance(s, dict) for s in slices):
        raise ValueError("session slices must be explicit")
    ids = [s.get("slice_id") for s in slices]
    if any(not isinstance(s, str) for s in ids) or len(set(ids)) != len(ids) or set(ids) != {s["slice_id"] for s in bundle["slices"]}:
        raise ValueError("session must name every current slice exactly once")
    owners = {}
    for edge in bundle["final_plan_coverage"]:
        owners.setdefault(edge["obligation_id"], set()).add(edge["slice_id"])
    dependencies = {sid: set() for sid in ids}
    for intent in bundle["behavior_routing"]["intents"]:
        for sid in owners.get(intent["obligation_id"], set()):
            for oid in intent["depends_on"]:
                dependencies[sid].update(owners.get(oid, set()) - {sid})
    seen, runs, outputs, checks = set(), [], [], []
    from q1_planned_preflight import validate_planned_preflight
    for item in slices:
        if set(item) != {"slice_id", "run_dir", "snapshot_roots", "ready_path"}:
            raise ValueError("invalid session slice fields")
        sid = item["slice_id"]
        if not dependencies[sid] <= seen:
            raise ValueError("session dependency order invalid: " + sid)
        seen.add(sid)
        runs.append(_path(root, item["run_dir"], output=True))
        outputs.append(_path(root, item["ready_path"], output=True))
        _roots(root, item["snapshot_roots"])
        validate_planned_preflight(workspace=root, bundle=bundle, slice_id=sid, timeout_seconds=budget)
        check = api.q1_preflight(semantic=semantic, slice_id=sid, profile=request["profile"])
        checks.append({"slice_id": sid, "status": check["status"], "errors": check.get("errors", [])})
    if any(a == b or a.is_relative_to(b) or b.is_relative_to(a) for n, a in enumerate(runs) for b in runs[n+1:]):
        raise ValueError("session run directories overlap")
    out = _path(root, request["out"], output=True)
    outputs.extend([out, out.with_name("terminal-input.v2.json"), out.with_name("acceptance-current-quick-dev-binding.json"), out.with_name("session-input.v1.json")])
    if len(outputs) != len(set(outputs)) or any(p.is_relative_to(run) for p in outputs for run in runs):
        raise ValueError("session output paths collide")
    _roots(root, request["snapshot_roots"])
    planned = {p for item in bundle["slices"] for p in item.get("planned_new_files", [])}
    future_descriptors = {run / "descriptors" for run in runs}
    for rows in [request["snapshot_roots"], *[s["snapshot_roots"] for s in slices]]:
        for row in rows:
            refs = row.get("repository_relative_posix_paths", [row.get("repository_relative_posix_path")])
            for ref in refs:
                path = _path(root, ref)
                if not path.exists() and ref not in planned and not (row["root_kind"] == "descriptor" and path in future_descriptors):
                    raise ValueError("session snapshot input missing: " + ref)
    return {"schema": "quick-dev.session-preflight.v1", "status": "preflight-passed" if all(c["status"] == "preflight-passed" for c in checks) else "blocked",
            "request_sha256": sha256_value(request), "checks": checks, "authorizes": []}


def advance_session(api, semantic, request, *, max_steps=8):
    """Use native reentry and Q7/Q8; stop before model-backed work."""
    if type(max_steps) is not int or not 1 <= max_steps <= 100:
        raise ValueError("session max_steps must be 1..100")
    admission = preflight_session(api, semantic, request)
    if admission["status"] != "preflight-passed":
        return admission
    root, bundle = api.ROOT, load_json(semantic)
    # A different profile, baseline, history or scope needs an explicit successor.
    create_json(_path(root, request["out"]).with_name("session-input.v1.json"), request)
    history = _failure_history(root, request["failure_history"]) if request.get("failure_history") else None
    steps, predecessors, used = [], [], 0
    def result(status, sid=None, action=None, **extra):
        return {"schema": "quick-dev.session-progress.v1", "status": status, "slice_id": sid,
                "required_next_action": action, "steps": steps, "request_sha256": sha256_value(request), "authorizes": [], **extra}
    def run_stage(item, stage):
        nonlocal used
        run = _path(root, item["run_dir"])
        replay = (run / "canonical-evidence" / stage / "stage-result.v2.json").exists()
        if not replay and used >= max_steps:
            return result("paused", item["slice_id"], "advance-session")
        value = api._execute_named_stage(semantic, run, stage, request["profile"], history)
        used += int(not replay)
        steps.append({"slice_id": item["slice_id"], "stage": stage, "reused": replay, "predicate_result": value.get("predicate_result")})
        if value.get("predicate_result") is not True:
            return result("blocked", item["slice_id"], value.get("required_next_action", "recover"), stage_result=value)
        return None
    from behavior_routing import read_route
    for item in request["slices"]:
        sid, run = item["slice_id"], _path(root, item["run_dir"])
        if not (run / "descriptors/probe.json").exists():
            if used >= max_steps:
                return result("paused", sid, "advance-session")
            authored = api.q2_author_red(semantic=semantic, slice_id=sid, run_dir=run, profile=request["profile"],
                            timeout_seconds=request["targeted_timeout_seconds"], backend=None, allow_worker=False)
            if authored.get("status") == "worker-required":
                return result("worker-required", sid, "author-red", detail=authored)
            if authored.get("required_next_action") != "run-probe":
                return result("blocked", sid, authored.get("required_next_action", "recover"), detail=authored)
            used += 1
            steps.append({"slice_id": sid, "stage": "materialize-probe"})
        if not (run / "canonical-evidence/probe/stage-result.v2.json").exists():
            stopped = run_stage(item, "probe")
            if stopped: return stopped
        route = read_route(root, bundle, run, sid)
        dispositions = {row["disposition"] for row in route["behavior_dispositions"]}
        if "missing" in dispositions:
            if not (run / "canonical-evidence/red/stage-result.v2.json").exists():
                stopped = run_stage(item, "red")
                if stopped: return stopped
            red = load_json(run / "canonical-evidence/red/stage-result.v2.json")
            if red.get("predicate_result") is not True:
                return result("blocked", sid, "recover", stage_result=red)
            if not (run / "descriptors/green.json").exists():
                return result("worker-required", sid, "implement")
            if not (run / "canonical-evidence/green/stage-result.v2.json").exists():
                stopped = run_stage(item, "green")
                if stopped: return stopped
            if not (run / "canonical-evidence/refactor/stage-result.v2.json").exists():
                return result("worker-required", sid, "run-refactor")
        if "present" in dispositions and not (run / "canonical-evidence/regression/stage-result.v2.json").exists():
            stopped = run_stage(item, "regression")
            if stopped: return stopped
        if used >= max_steps and not (run / "canonical-evidence/terminal/stage-result.v2.json").exists():
            return result("paused", sid, "advance-session")
        api._materialize_named_descriptor(semantic, run, "terminal")
        ready = api.validate_slice_ready(workspace=root, semantic_plan=semantic, run_root=run, slice_id=sid,
                    snapshot_roots=item["snapshot_roots"], source_commit=request["source_commit"], base_commit=request["base_commit"],
                    out=_path(root, item["ready_path"]))
        stopped = run_stage(item, "terminal")
        if stopped: return stopped
        predecessors.append({"slice_id": sid, "run_root": item["run_dir"], "result_ref": item["ready_path"], "result_sha256": sha256_value(ready)})
    out = _path(root, request["out"])
    detached = api._detached_promotion_binding(_path(root, request["detached_bundle"]), request["profile"]) if request.get("detached_bundle") else None
    completion = api.publish_implementation_complete(workspace=root, semantic_plan=semantic, predecessors=predecessors,
                    snapshot_roots=request["snapshot_roots"], source_commit=request["source_commit"], base_commit=request["base_commit"],
                    out=out, detached_promotion_binding=detached, profile=request["profile"], verify_existing=out.exists())
    binding = {"semanticPlan": {"path": semantic.relative_to(root).as_posix(), "sha256": sha256_bytes(semantic.read_bytes())},
               "receipt": {"path": out.relative_to(root).as_posix(), "sha256": sha256_bytes(out.read_bytes())},
               "snapshotRoots": request["snapshot_roots"], "sourceCommit": request["source_commit"], "baseCommit": request["base_commit"]}
    create_json(out.with_name("acceptance-current-quick-dev-binding.json"), binding)
    return result("implementation-complete", completion=completion,
                  acceptance_binding=out.with_name("acceptance-current-quick-dev-binding.json").relative_to(root).as_posix())
