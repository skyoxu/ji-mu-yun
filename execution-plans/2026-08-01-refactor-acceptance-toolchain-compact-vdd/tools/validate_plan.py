from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REQ_IDS = {f"RA-TC-{index:03d}" for index in range(1, 9)}
ACC_IDS = {f"RA-TC-A{index:02d}" for index in range(1, 14)}
SLICE_IDS = [f"RA-TC-S{index}" for index in range(3)]


def load(name: str) -> dict:
    value = json.loads((PLAN_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain an object")
    return value


def validate() -> dict:
    required = {
        "00-index.md", "95-implementation-evolution-and-completion-report.md",
        "baseline-and-scope.v1.json", "knowledge-context.v1.json",
        "knowledge-context.freeze.v1.json", "plan-state.v1.json",
        "requirements.v1.json", "tools/validate_plan.py", "tools/validate_implementation.py",
        "repair/round-1/repair-plan.md", "repair/round-1/repair-closure.json",
        "repair/round-2/repair-plan.md", "repair/round-2/repair-closure.json",
        "repair/round-3/repair-plan.md", "repair/round-3/repair-closure.json",
    }
    missing = sorted(name for name in required if not (PLAN_ROOT / name).is_file())
    if missing:
        raise ValueError(f"missing plan files: {missing}")
    state = load("plan-state.v1.json")
    allowed = {"plan-ready", "implementation-authorized", "implementation-complete"}
    if state.get("profile") != "self-hosted" or state.get("state") not in allowed:
        raise ValueError("plan state is invalid")
    if state.get("authorizes") != [state["state"]]:
        raise ValueError("plan state authority is invalid")
    state_slices = state.get("slices")
    if not isinstance(state_slices, list) or [row.get("id") for row in state_slices] != SLICE_IDS:
        raise ValueError("plan state slices are invalid")
    if state["state"] == "implementation-complete" and any(row.get("status") != "completed" for row in state_slices):
        raise ValueError("completed state requires completed slices")

    requirements = load("requirements.v1.json")
    rows, acceptance, slices = requirements.get("requirements"), requirements.get("acceptance"), requirements.get("slices")
    if not all(isinstance(value, list) for value in (rows, acceptance, slices)):
        raise ValueError("requirements collections are invalid")
    if {row.get("id") for row in rows} != REQ_IDS or {row.get("id") for row in acceptance} != ACC_IDS:
        raise ValueError("requirements or acceptance coverage is incomplete")
    if [row.get("id") for row in slices] != SLICE_IDS:
        raise ValueError("slice order is invalid")
    completed: set[str] = set()
    for row in slices:
        if not set(row.get("depends_on", [])).issubset(completed):
            raise ValueError("slice dependencies are invalid")
        for field in ("red_commands", "green_commands"):
            commands = row.get(field)
            if not isinstance(commands, list) or not commands or any(not isinstance(command, str) or not command or ";" in command or "&&" in command for command in commands):
                raise ValueError("slice command is invalid")
        completed.add(row["id"])

    baseline = load("baseline-and-scope.v1.json")
    git = baseline.get("git", {})
    head = git.get("head")
    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True).strip()
    if current_head != head:
        raise ValueError("baseline HEAD drifted")
    roots = baseline.get("scope_roots")
    if not isinstance(roots, list) or not roots:
        raise ValueError("scope roots are invalid")
    tracked = subprocess.check_output(["git", "diff", "--binary", head, "--", *roots], cwd=REPOSITORY_ROOT)
    index = subprocess.check_output(["git", "diff", "--binary", "--cached", head, "--", *roots], cwd=REPOSITORY_ROOT)
    started = state["state"] != "plan-ready"
    if not started and "sha256:" + hashlib.sha256(tracked).hexdigest() != git.get("scoped_tracked_diff_sha256"):
        raise ValueError("scoped tracked baseline drifted")
    if "sha256:" + hashlib.sha256(index).hexdigest() != git.get("scoped_index_diff_sha256"):
        raise ValueError("scoped index baseline drifted")
    for row in baseline.get("preexisting_dirty_paths", []):
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ValueError("dirty path inventory is invalid")
        if started and row.get("disposition") in {"incorporate-current-bytes", "append-one-entry"}:
            continue
        path = REPOSITORY_ROOT / row["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row.get("sha256"):
            raise ValueError(f"bound dirty path drifted: {row['path']}")

    context_path = PLAN_ROOT / "knowledge-context.v1.json"
    context = load("knowledge-context.v1.json")
    freeze = load("knowledge-context.freeze.v1.json")
    if freeze.get("context_sha256") != "sha256:" + hashlib.sha256(context_path.read_bytes()).hexdigest() or freeze.get("authorizes") != []:
        raise ValueError("knowledge freeze is invalid")

    closure = load("repair/round-1/repair-closure.json")
    binding = closure.get("binding")
    if closure.get("status") != "closed" or closure.get("authorizes") != [] or not isinstance(binding, dict):
        raise ValueError("repair closure is invalid")
    binding_bytes = json.dumps(binding, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if closure.get("binding_sha256") != "sha256:" + hashlib.sha256(binding_bytes).hexdigest():
        raise ValueError("repair closure binding drifted")
    repair_plan = PLAN_ROOT / "repair/round-1/repair-plan.md"
    if binding.get("repair_plan_sha256") != "sha256:" + hashlib.sha256(repair_plan.read_bytes()).hexdigest():
        raise ValueError("repair plan binding drifted")
    validator = PLAN_ROOT / "tools/validate_implementation.py"
    if binding.get("terminal_validator_sha256") != "sha256:" + hashlib.sha256(validator.read_bytes()).hexdigest():
        raise ValueError("terminal validator binding drifted")
    for row in binding.get("repaired_files", []):
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ValueError("repaired file binding is invalid")
        repaired_path = REPOSITORY_ROOT / row["path"]
        if not repaired_path.is_file() or row.get("sha256") != "sha256:" + hashlib.sha256(repaired_path.read_bytes()).hexdigest():
            raise ValueError(f"repaired file binding drifted: {row['path']}")

    closure2 = load("repair/round-2/repair-closure.json")
    binding2 = closure2.get("binding")
    if closure2.get("status") != "closed" or closure2.get("authorizes") != [] or not isinstance(binding2, dict):
        raise ValueError("repair round 2 closure is invalid")
    binding2_bytes = json.dumps(binding2, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if closure2.get("binding_sha256") != "sha256:" + hashlib.sha256(binding2_bytes).hexdigest():
        raise ValueError("repair round 2 closure binding drifted")
    repair_plan2 = PLAN_ROOT / "repair/round-2/repair-plan.md"
    if binding2.get("repair_plan_sha256") != "sha256:" + hashlib.sha256(repair_plan2.read_bytes()).hexdigest():
        raise ValueError("repair round 2 plan binding drifted")
    if binding2.get("terminal_validator_sha256") != "sha256:" + hashlib.sha256(validator.read_bytes()).hexdigest():
        raise ValueError("repair round 2 terminal validator binding drifted")
    for row in binding2.get("repaired_files", []):
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ValueError("repair round 2 file binding is invalid")
        repaired_path = REPOSITORY_ROOT / row["path"]
        if not repaired_path.is_file() or row.get("sha256") != "sha256:" + hashlib.sha256(repaired_path.read_bytes()).hexdigest():
            raise ValueError(f"repair round 2 file binding drifted: {row['path']}")

    closure3 = load("repair/round-3/repair-closure.json")
    binding3 = closure3.get("binding")
    if closure3.get("status") != "closed" or closure3.get("authorizes") != [] or not isinstance(binding3, dict):
        raise ValueError("repair round 3 closure is invalid")
    binding3_bytes = json.dumps(binding3, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if closure3.get("binding_sha256") != "sha256:" + hashlib.sha256(binding3_bytes).hexdigest():
        raise ValueError("repair round 3 closure binding drifted")
    repair_plan3 = PLAN_ROOT / "repair/round-3/repair-plan.md"
    if binding3.get("repair_plan_sha256") != "sha256:" + hashlib.sha256(repair_plan3.read_bytes()).hexdigest():
        raise ValueError("repair round 3 plan binding drifted")
    if binding3.get("terminal_validator_sha256") != "sha256:" + hashlib.sha256(validator.read_bytes()).hexdigest():
        raise ValueError("repair round 3 terminal validator binding drifted")
    for row in binding3.get("repaired_files", []):
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ValueError("repair round 3 file binding is invalid")
        repaired_path = REPOSITORY_ROOT / row["path"]
        if not repaired_path.is_file() or row.get("sha256") != "sha256:" + hashlib.sha256(repaired_path.read_bytes()).hexdigest():
            raise ValueError(f"repair round 3 file binding drifted: {row['path']}")

    preflight = subprocess.run([
        "py", "-3", str(REPOSITORY_ROOT / ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py"),
        "--input", str(context_path), "--repository-root", str(REPOSITORY_ROOT),
    ], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
    if preflight.returncode != 0 or json.loads(preflight.stdout).get("status") != "ready":
        raise ValueError("knowledge preflight is not ready")

    report_index = json.loads((REPOSITORY_ROOT / "execution-plans/95-implementation-report-index.v1.json").read_text(encoding="utf-8"))
    expected = {"plan_directory": PLAN_ROOT.name, "report_filename": "95-implementation-evolution-and-completion-report.md"}
    if list(report_index.get("entries", [])).count(expected) != 1:
        raise ValueError("95 report index entry is missing or duplicated")
    return {"schema_version":"jimuyun.refactor-acceptance-toolchain-plan-validation.v1","status":"pass","validated_state":state["state"],"requirements":len(REQ_IDS),"acceptance":len(ACC_IDS),"slices":len(SLICE_IDS),"authorizes":["plan-ready"] if state["state"] == "plan-ready" else []}


def main() -> int:
    try:
        result = validate()
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(json.dumps({"status":"fail","error":str(exc),"authorizes":[]}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
