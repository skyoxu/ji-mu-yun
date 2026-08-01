from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_REQUIREMENTS = {f"RMR-{index:03d}" for index in range(1, 11)}
EXPECTED_ACCEPTANCE = {f"RMR-A{index:02d}" for index in range(1, 18)}
EXPECTED_SLICES = [f"RMR-S{index}" for index in range(5)]

sys.path.insert(0, str(REPOSITORY_ROOT / "scripts/python"))
from knowledge_context_validation import canonical_hash, validate_worktree_sources  # noqa: E402


def load_json(name: str) -> dict[str, object]:
    value = json.loads((PLAN_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return value


def validate() -> dict[str, object]:
    required_files = {
        "00-index.md",
        "95-implementation-evolution-and-completion-report.md",
        "baseline-and-scope.v1.json",
        "knowledge-context.freeze.v1.json",
        "knowledge-context.v1.json",
        "plan-state.v1.json",
        "requirements.v1.json",
        "tools/validate_plan.py",
        "tools/validate_implementation.py",
    }
    missing = sorted(path for path in required_files if not (PLAN_ROOT / path).is_file())
    if missing:
        raise ValueError(f"missing plan files: {missing}")

    state = load_json("plan-state.v1.json")
    allowed_states = {
        "plan-ready": ["plan-ready"],
        "implementation-authorized": ["implementation-authorized"],
        "implementation-complete": ["implementation-complete"],
    }
    if state.get("profile") != "self-hosted" or state.get("state") not in allowed_states:
        raise ValueError("plan state or profile is invalid")
    if state.get("authorizes") != allowed_states[state["state"]]:
        raise ValueError("plan state authority is invalid")
    state_slices = state.get("slices")
    if not isinstance(state_slices, list) or [
        row.get("id") for row in state_slices if isinstance(row, dict)
    ] != EXPECTED_SLICES:
        raise ValueError("plan state slice inventory is invalid")
    if state["state"] == "implementation-complete" and any(
        not isinstance(row, dict) or row.get("status") != "completed"
        for row in state_slices
    ):
        raise ValueError("implementation-complete requires every slice to be completed")

    requirements = load_json("requirements.v1.json")
    requirement_rows = requirements.get("requirements")
    acceptance_rows = requirements.get("acceptance")
    slice_rows = requirements.get("slices")
    if not all(isinstance(value, list) for value in (requirement_rows, acceptance_rows, slice_rows)):
        raise ValueError("requirements collections are invalid")
    if {row.get("id") for row in requirement_rows if isinstance(row, dict)} != EXPECTED_REQUIREMENTS:
        raise ValueError("requirement coverage is incomplete")
    if {row.get("id") for row in acceptance_rows if isinstance(row, dict)} != EXPECTED_ACCEPTANCE:
        raise ValueError("acceptance coverage is incomplete")
    if [row.get("id") for row in slice_rows if isinstance(row, dict)] != EXPECTED_SLICES:
        raise ValueError("slice order is invalid")
    known_acceptance = EXPECTED_ACCEPTANCE
    known_slices = set(EXPECTED_SLICES)
    for row in requirement_rows:
        if not isinstance(row, dict):
            raise ValueError("requirement row is invalid")
        if not set(row.get("acceptance_ids") or []).issubset(known_acceptance):
            raise ValueError(f"unknown acceptance mapping: {row.get('id')}")
        if not set(row.get("slice_ids") or []).issubset(known_slices):
            raise ValueError(f"unknown slice mapping: {row.get('id')}")
    completed: set[str] = set()
    for row in slice_rows:
        if not isinstance(row, dict):
            raise ValueError("slice row is invalid")
        if not set(row.get("depends_on") or []).issubset(completed):
            raise ValueError(f"slice dependency order is invalid: {row.get('id')}")
        for field in ("red_commands", "green_commands"):
            commands = row.get(field)
            if not isinstance(commands, list) or not commands or not all(
                isinstance(command, str) and command.strip() for command in commands
            ):
                raise ValueError(f"slice command list is missing: {row.get('id')}:{field}")
            if any("&&" in command or ";" in command for command in commands):
                raise ValueError(f"slice commands must not use shell chaining: {row.get('id')}:{field}")
        if not isinstance(row.get("recovery"), str) or not str(row["recovery"]).strip():
            raise ValueError(f"slice recovery is missing: {row.get('id')}")
        completed.add(str(row["id"]))

    baseline = load_json("baseline-and-scope.v1.json")
    head = str((baseline.get("git") or {}).get("head") or "")
    if len(head) != 40:
        raise ValueError("baseline Git identity is invalid")
    subprocess.run(
        ["git", "cat-file", "-e", f"{head}^{{commit}}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    if current_head != head:
        raise ValueError("baseline HEAD drifted")
    scope_roots = baseline.get("scope_roots")
    if not isinstance(scope_roots, list) or not scope_roots or not all(
        isinstance(path, str) and path for path in scope_roots
    ):
        raise ValueError("baseline scope roots are invalid")
    tracked_diff = subprocess.run(
        ["git", "diff", "--binary", head, "--", *scope_roots],
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    index_diff = subprocess.run(
        ["git", "diff", "--binary", "--cached", head, "--", *scope_roots],
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    git_identity = baseline.get("git") or {}
    implementation_started = state["state"] in {
        "implementation-authorized", "implementation-complete"
    }
    if not implementation_started and (
        "sha256:" + hashlib.sha256(tracked_diff).hexdigest()
        != git_identity.get("scoped_tracked_diff_sha256")
    ):
        raise ValueError("scoped tracked worktree identity drifted")
    if "sha256:" + hashlib.sha256(index_diff).hexdigest() != git_identity.get("scoped_index_diff_sha256"):
        raise ValueError("scoped index identity drifted")
    dirty_paths = baseline.get("preexisting_dirty_paths")
    if not isinstance(dirty_paths, list):
        raise ValueError("preexisting dirty path inventory is invalid")
    for row in dirty_paths:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ValueError("preexisting dirty path row is invalid")
        path = REPOSITORY_ROOT / str(row["path"])
        if not path.is_file():
            raise ValueError(f"bound dirty path is missing: {row['path']}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row.get("sha256"):
            overlay = (
                PLAN_ROOT / "repair/round-1/baseline-overlays/acceptance_core.py"
                if row.get("path") == ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_core.py"
                and row.get("disposition") == "preserve-and-refreeze-before-overlap"
                else None
            )
            if (
                implementation_started
                and overlay is not None
                and overlay.is_file()
                and hashlib.sha256(overlay.read_bytes()).hexdigest() == row.get("sha256")
            ):
                continue
            raise ValueError(f"bound dirty path drifted: {row['path']}")

    knowledge_context = load_json("knowledge-context.v1.json")
    preflight = subprocess.run(
        [
            "py",
            "-3",
            str(REPOSITORY_ROOT / ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py"),
            "--input",
            str(PLAN_ROOT / "knowledge-context.v1.json"),
            "--repository-root",
            str(REPOSITORY_ROOT),
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if preflight.returncode != 0:
        raise ValueError(f"knowledge preflight failed: {preflight.stderr.strip()}")
    preflight_value = json.loads(preflight.stdout)
    if preflight_value.get("status") != "ready" or preflight_value.get("missing_required_modules") != []:
        raise ValueError("knowledge preflight is not ready")

    if not implementation_started:
        worktree_error = validate_worktree_sources(knowledge_context, REPOSITORY_ROOT)
        if worktree_error:
            raise ValueError(f"knowledge candidate worktree sources are stale: {worktree_error}")

    context_bytes = (PLAN_ROOT / "knowledge-context.v1.json").read_bytes()
    freeze = load_json("knowledge-context.freeze.v1.json")
    accepted = [
        {
            "path": row["candidate"]["path"],
            "source_sha256": row["candidate"]["source_sha256"],
            "satisfies": sorted(row["satisfies"]),
        }
        for row in knowledge_context.get("decisions", [])
        if isinstance(row, dict) and row.get("decision") == "accepted"
    ]
    expected_context_hash = "sha256:" + hashlib.sha256(context_bytes).hexdigest()
    if (
        freeze.get("schema_version") != "jimuyun.vdd-knowledge-freeze.v1"
        or freeze.get("context_path") != "knowledge-context.v1.json"
        or freeze.get("context_sha256") != expected_context_hash
        or freeze.get("canonical_context_sha256") != canonical_hash(knowledge_context)
        or freeze.get("request_sha256") != knowledge_context.get("request_sha256")
        or freeze.get("result_sha256") != knowledge_context.get("result_sha256")
        or freeze.get("snapshot") != (knowledge_context.get("locator_request") or {}).get("snapshot")
        or freeze.get("source_snapshot_id") != (knowledge_context.get("locator_result") or {}).get("source_snapshot_id")
        or freeze.get("policy_revision") != (knowledge_context.get("locator_request") or {}).get("policy_revision")
        or freeze.get("accepted") != accepted
        or freeze.get("authorizes") != []
    ):
        raise ValueError("knowledge context freeze receipt is invalid")

    index = json.loads(
        (REPOSITORY_ROOT / "execution-plans/95-implementation-report-index.v1.json").read_text(encoding="utf-8")
    )
    expected_entry = {
        "plan_directory": PLAN_ROOT.name,
        "report_filename": "95-implementation-evolution-and-completion-report.md",
    }
    if list(index.get("entries") or []).count(expected_entry) != 1:
        raise ValueError("95 report index must contain exactly one plan entry")

    source_hashes = {}
    for name in sorted(required_files):
        source_hashes[name] = "sha256:" + hashlib.sha256((PLAN_ROOT / name).read_bytes()).hexdigest()
    return {
        "schema_version": "jimuyun.workflow-model-routing-plan-validation.v1",
        "status": "pass",
        "predicate": "plan-ready" if state["state"] == "plan-ready" else "plan-structure-valid",
        "validated_state": state["state"],
        "plan_id": "workflow-model-routing-control-plane",
        "requirements": len(EXPECTED_REQUIREMENTS),
        "acceptance": len(EXPECTED_ACCEPTANCE),
        "slices": len(EXPECTED_SLICES),
        "source_hashes": source_hashes,
        "authorizes": ["plan-ready"] if state["state"] == "plan-ready" else [],
        "does_not_authorize": ["acceptance-passed", "release", "archived"],
    }


def main() -> int:
    try:
        result = validate()
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc), "authorizes": []}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
