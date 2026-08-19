from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


PLAN_ID = "toolchain-workflow-repair"
SLICES = {"W0", "W1", "W2", "W3", "W4", "W5", "W6"}
REQUIRED_FILES = {
    "requirements-and-acceptance.md",
    "implementation-contract.v1.json",
    "command-registry.v1.json",
    "authority-manifest.v1.json",
    "resume-state.v1.json",
    "architecture-acceptance-request.v1.json",
    "pre-existing-candidate-delta.v1.json",
    "canonical-skill-input-plan-receipt.v2.json",
    "knowledge-context.v1.json",
    "knowledge-context.freeze.v1.json",
    "tools/publish_implementation_authorization.py",
    "tools/migration_bridge.py",
    "tools/terminal_full.py",
}


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def git_bytes(root: Path, revision: str, relative: str) -> bytes:
    result = subprocess.run(["git", "show", f"{revision}:{relative}"], cwd=root, check=False, capture_output=True)
    if result.returncode:
        raise ValueError(f"git object missing: {revision}:{relative}")
    return result.stdout


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--mode", choices=("initial-plan-ready", "authorized-repair-revalidate"), default="initial-plan-ready")
    parser.add_argument("--skill-input-receipt", type=Path)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    plan = args.plan_dir.resolve()
    out_path = args.out.resolve() if args.out else None
    failures: list[str] = []
    if not plan.is_dir() or not plan.is_relative_to(root / "execution-plans"):
        failures.append("plan-directory-invalid")
    for relative in REQUIRED_FILES:
        if not (plan / relative).is_file():
            failures.append(f"missing:{relative}")
    if not failures:
        try:
            contract = read_json(plan / "implementation-contract.v1.json")
            registry = read_json(plan / "command-registry.v1.json")
            authority = read_json(plan / "authority-manifest.v1.json")
            state = read_json(plan / "plan-state.v1.json")
            resume = read_json(plan / "resume-state.v1.json")
            architecture = read_json(plan / "architecture-acceptance-request.v1.json")
            delta = read_json(plan / "pre-existing-candidate-delta.v1.json")
            context = read_json(plan / "knowledge-context.v1.json")
            freeze = read_json(plan / "knowledge-context.freeze.v1.json")
            if contract.get("plan_id") != PLAN_ID or contract.get("profile") != "self-hosted":
                failures.append("contract-plan-or-profile-invalid")
            slice_ids = {item.get("slice_id") for item in contract.get("slices", []) if isinstance(item, dict)}
            if slice_ids != SLICES:
                failures.append("contract-slice-set-invalid")
            for item in contract.get("slices", []):
                if not isinstance(item, dict) or item.get("execution_mode", "tdd") != "tdd" or not isinstance(item.get("tdd"), dict):
                    failures.append("contract-tdd-intent-invalid")
                    break
            command_ids = {item.get("id") for item in registry.get("commands", []) if isinstance(item, dict)}
            required_commands = {"plan-ready", "terminal-full", *(f"w{index}-{stage}" for index in range(7) for stage in ("green", "terminal"))}
            if not required_commands.issubset(command_ids):
                failures.append("command-registry-incomplete")
            if not authority.get("authority_sources") or not authority.get("candidate_inputs") or not authority.get("lifecycle_projections"):
                failures.append("authority-manifest-partition-invalid")
            if args.mode == "authorized-repair-revalidate":
                repair_state = plan / "repair" / "round-1" / "repair-state.v1.json"
                repair_value = read_json(repair_state) if repair_state.is_file() else {}
                if state.get("status") != "implementation-authorized" or repair_value.get("status") != "validating" or repair_value.get("blocks_execution") is not True or repair_value.get("authorizes") != []:
                    failures.append("authorized-repair-state-invalid")
            elif state.get("status") == "draft" and state.get("authorizes") != []:
                failures.append("draft-plan-state-authorizes")
            elif state.get("status") == "plan-ready":
                publication = plan / "repair" / "plan-ready-publication-receipt.v1.json"
                if not publication.is_file():
                    failures.append("plan-ready-publication-receipt-missing")
                else:
                    published = read_json(publication)
                    validation_path = plan / "repair" / "plan-validation-receipt.v1.json"
                    validation_binding = published.get("validation")
                    if (
                        published.get("owner") != "vdd"
                        or published.get("authorizes") != ["plan-ready"]
                        or not isinstance(validation_binding, dict)
                        or validation_binding.get("path") != "repair/plan-validation-receipt.v1.json"
                        or validation_binding.get("sha256") != sha256(validation_path.read_bytes())
                    ):
                        failures.append("plan-ready-publication-receipt-invalid")
            elif state.get("status") != "draft" and args.mode != "authorized-repair-revalidate":
                failures.append("plan-state-invalid")
            if resume.get("authorizes") != [] or set(resume.get("slice_status", {})) != SLICES:
                failures.append("resume-state-invalid")
            if architecture.get("status") != "accepted" or not architecture.get("decisions"):
                failures.append("architecture-acceptance-invalid")
            if delta.get("baseline_commit") != "2556ea78f41657e5a740016ff97da0b0614631ea" or delta.get("candidate_commit") != "a2ded39b0f67dcbe5f27acedb56c0bafbd3f3fc5":
                failures.append("pre-existing-delta-baseline-invalid")
            if not delta.get("paths") or delta.get("authorizes") != []:
                failures.append("pre-existing-delta-invalid")
            skill_input = args.skill_input_receipt.resolve() if args.skill_input_receipt else None
            if skill_input is None:
                failures.append("canonical-skill-input-receipt-required")
                skill_validation = None
            else:
                try:
                    skill_input.relative_to(plan / "skill-input")
                except ValueError:
                    failures.append("canonical-skill-input-receipt-outside-plan")
                    skill_validation = None
                else:
                    skill_validation = subprocess.run(
                        ["python", "scripts/python/validate_skill_input_consumption.py", str(skill_input),
                         "--repository-root", str(root), "--contract",
                         ".agents/skills/quick-dev-tdd-adapter/references/skill-input-contract.v1.json", "--require-ready"],
                        cwd=root, capture_output=True, text=True, check=False,
                    )
            if skill_validation is not None and skill_validation.returncode:
                failures.append("canonical-skill-input-not-ready")
            expected_delta_paths = {
                ".agents/skills/quick-dev-tdd-adapter/schemas/plan-owned-implementation-contract.v1.schema.json",
                ".agents/skills/quick-dev-tdd-adapter/tools/loop_plan_directory.py",
                ".agents/skills/quick-dev-tdd-adapter/tools/route_plan_directory.py",
                "scripts/python/skill_input_consumption.py",
                "scripts/python/tests/test_skill_input_consumption.py",
                "execution-plans/2026-08-18-acceptance-coordinator-trust-recovery/tools/terminal_full.py",
            }
            delta_entries = delta.get("paths", [])
            if {item.get("path") for item in delta_entries if isinstance(item, dict)} != expected_delta_paths:
                failures.append("pre-existing-delta-paths-invalid")
            else:
                for item in delta_entries:
                    relative = item["path"]
                    if (
                        item.get("baseline_sha256") != sha256(git_bytes(root, delta["baseline_commit"], relative))
                        or item.get("candidate_sha256") != sha256(git_bytes(root, delta["candidate_commit"], relative))
                        or item.get("disposition") != "pre-existing-regression-or-repair-input"
                    ):
                        failures.append("pre-existing-delta-binding-invalid")
                        break
            if context.get("preflight", {}).get("status") != "ready" or freeze.get("authorizes") != []:
                failures.append("knowledge-preflight-or-freeze-invalid")
            accepted_modules = {
                module
                for decision in context.get("decisions", [])
                if isinstance(decision, dict) and decision.get("decision") == "accepted"
                for module in decision.get("satisfies", [])
                if isinstance(module, str)
            }
            required_modules = {"skill-input-execution", "knowledge-execution-gates"}
            if not required_modules.issubset(accepted_modules):
                failures.append("knowledge-required-modules-unresolved")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"invalid-plan-artifact:{exc}")
    result = {
        "schema_version": "toolchain-workflow-repair.plan-validation.v2" if args.mode == "authorized-repair-revalidate" else "toolchain-workflow-repair.plan-validation.v1",
        "plan_id": PLAN_ID,
        "predicate": "plan-valid",
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "authorizes": [],
        "lifecycle_transition": "none",
    }
    if out_path:
        input_manifest = {
            "schema_version": "toolchain-workflow-repair.validator-input-manifest.v1",
            "plan_id": PLAN_ID,
            "mode": args.mode,
            "inputs": [
                {"path": name, "sha256": sha256((plan / name).read_bytes())}
                for name in ("implementation-contract.v1.json", "command-registry.v1.json", "authority-manifest.v1.json", "knowledge-context.v1.json", "knowledge-context.freeze.v1.json")
                if (plan / name).is_file()
            ],
            "skill_input_receipt": str(args.skill_input_receipt.resolve().relative_to(root).as_posix()) if args.skill_input_receipt else None,
            "authorizes": [],
        }
        manifest_path = out_path.parent / "validator-input-manifest.v1.json"
        manifest_path.write_text(json.dumps(input_manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        result["validator_input_manifest"] = {"path": manifest_path.relative_to(plan).as_posix(), "sha256": sha256(manifest_path.read_bytes())}
    encoded = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
