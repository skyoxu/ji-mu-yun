from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
PLAN_DIRECTORY = PLAN_ROOT.name
PLAN_ID = "toolchain-core-skill-replay-portability-and-evaluation-seed"
ROUND3_REPAIR_EVIDENCE_PATH = "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-4/implementation-authorization.v1.json"

REQUIRED_FILES = (
    "00-index.md",
    "95-implementation-evolution-and-completion-report.md",
    "authority-manifest.v1.json",
    "baseline-and-scope.v1.json",
    "command-registry.v1.json",
    "implementation-contract.v1.json",
    "model-route-decision.v1.json",
    "plan-state.v1.json",
    "requirements.v1.json",
    "resume-state.v1.json",
    "tools/validate_implementation.py",
    "tools/validate_plan.py",
    "tools/tests/test_validate_plan.py",
    "tools/tests/test_validate_implementation.py",
)

REQUIRED_HEADINGS = (
    "## First-Class Directory Boundary",
    "## Historical Evidence Preservation",
    "## Skill Delta Plus Evaluation Delta",
    "## No Autonomous SkillOS Or RL",
)

FORBIDDEN_ALLOWED_PREFIXES = (
    "PhaseA.Platform/",
    "PhaseA.Platform.Tests/",
    "runtime/phase-a/",
    "logs/phase-a-innernet/",
    "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/",
    "execution-plans/2026-07-31-toolchain-workflow-evidence-catalog-v1/",
    "_bmad/",
    ".agents/skills/bmad-",
    ".agents/skills/gds-",
)


class ValidationError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"JSON root must be an object: {path}")
    return value


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def has_forbidden_allowed_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in FORBIDDEN_ALLOWED_PREFIXES)


def validate_headings(text: str) -> list[str]:
    return [heading for heading in REQUIRED_HEADINGS if heading not in text]


def validate_historical_candidate(
    manifest: dict[str, Any], errors: list[str]
) -> None:
    baseline_commit = manifest.get("git", {}).get("commit")
    for item in manifest.get("historical_trees", []):
        path = item.get("path")
        if not isinstance(path, str) or not path:
            errors.append("historical tree path must be a nonempty string")
            continue
        completed = run(["git", "rev-parse", f"refs/heads/main:{path}"])
        if completed.returncode or completed.stdout.strip() != item.get("git_tree_oid"):
            errors.append(f"historical tree drift: {path}")

        listing = run(["git", "ls-tree", "-r", "--name-only", str(baseline_commit), "--", path])
        if listing.returncode:
            errors.append(f"historical baseline file manifest is unavailable: {path}")
            continue
        expected = {line.strip() for line in listing.stdout.splitlines() if line.strip()}
        root = REPOSITORY_ROOT / path
        actual = (
            {
                candidate.relative_to(REPOSITORY_ROOT).as_posix()
                for candidate in root.rglob("*")
                if candidate.is_file()
            }
            if root.is_dir()
            else set()
        )
        if actual != expected:
            errors.append(f"historical candidate file set drift: {path}")
        for relative in sorted(expected & actual):
            baseline = subprocess.run(
                ["git", "show", f"{baseline_commit}:{relative}"],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                check=False,
            )
            if baseline.returncode or baseline.stdout != (REPOSITORY_ROOT / relative).read_bytes():
                errors.append(f"historical candidate byte drift: {relative}")


def validate_authority(errors: list[str], *, allow_mutable_source_drift: bool = False) -> dict[str, str]:
    manifest = load_json(PLAN_ROOT / "authority-manifest.v1.json")
    git = manifest.get("git", {})
    baseline_commit = git.get("commit")
    baseline = run(["git", "cat-file", "-e", f"{baseline_commit}^{{commit}}"])
    tree = run(["git", "rev-parse", f"{baseline_commit}^{{tree}}"])
    ancestry = run(["git", "merge-base", "--is-ancestor", str(baseline_commit), "refs/heads/main"])
    if baseline.returncode:
        errors.append("authority baseline commit is unavailable")
    if tree.returncode or tree.stdout.strip() != git.get("tree"):
        errors.append("authority manifest does not bind its baseline tree")
    if ancestry.returncode:
        errors.append("authority baseline is not an ancestor of current main")
    mutable_paths = set(manifest.get("mutable_source_paths", []))
    declared_paths = {
        path
        for slice_item in load_json(PLAN_ROOT / "implementation-contract.v1.json").get("slices", [])
        for area in ("production", "tests", "documentation")
        for path in slice_item.get("allowed_changes", {}).get(area, [])
        if isinstance(path, str) and not path.endswith("/**")
    }
    if not mutable_paths.issubset(declared_paths):
        errors.append("mutable authority sources must be declared implementation paths")
    seen: set[str] = set()
    mutable_hashes: dict[str, str] = {}
    for item in manifest.get("source_files", []):
        path = item.get("path")
        if not isinstance(path, str) or path in seen:
            errors.append("authority source paths must be unique strings")
            continue
        seen.add(path)
        source = REPOSITORY_ROOT / path
        if not source.is_file():
            errors.append(f"authority source drift: {path}")
        elif path in mutable_paths and allow_mutable_source_drift:
            mutable_hashes[path] = sha256(source)
        elif sha256(source) != item.get("sha256"):
            errors.append(f"authority source drift: {path}")
    validate_historical_candidate(manifest, errors)
    if manifest.get("authorizes") != []:
        errors.append("authority manifest must be non-authorizing")
    if allow_mutable_source_drift and set(mutable_hashes) != mutable_paths:
        errors.append("all mutable authority sources must be present and hash-bound")
    return mutable_hashes


def validate_requirements_and_contract(errors: list[str]) -> None:
    requirements = load_json(PLAN_ROOT / "requirements.v1.json")
    contract = load_json(PLAN_ROOT / "implementation-contract.v1.json")
    registry = load_json(PLAN_ROOT / "command-registry.v1.json")
    if requirements.get("plan_id") != PLAN_ID or contract.get("plan_id") != PLAN_ID:
        errors.append("plan identifiers do not match")
    if requirements.get("profile") != "self-hosted" or contract.get("profile") != "self-hosted":
        errors.append("TC-D1 must use the self-hosted profile")
    artifact_contracts = contract.get("artifact_contracts", {})
    historical = artifact_contracts.get("historical_compatibility_replay", {})
    seed = artifact_contracts.get("evaluation_seed", {})
    matrix = artifact_contracts.get("stable_candidate_matrix", {})
    if historical.get("required_bindings") != [
        "historical_validator",
        "historical_command_evidence",
        "current_wrapper_replay",
    ]:
        errors.append("historical replay contract must freeze all three evidence bindings")
    expected_wrapper_command = [
        "py", "-3", "-B", "scripts/sc/skill_package_replay.py", "replay-package",
        "--target", ".agents/skills/run-refactor-implementation-acceptance",
        "--capability", "scripts/sc/config/skill-package-validator-capability.v1.json",
        "--probe-mode", "detached-positive-negative",
    ]
    if (
        historical.get("historical_validator_path") != "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/tools/validate_implementation.py"
        or historical.get("historical_command_evidence_path") != "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/95-implementation-evolution-and-completion-report.md"
        or historical.get("historical_command") != ["py", "-3", "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/tools/validate_implementation.py"]
        or historical.get("current_wrapper_entrypoint") != "scripts/sc/skill_package_replay.py"
        or historical.get("current_wrapper_command") != expected_wrapper_command
        or historical.get("target_package") != ".agents/skills/run-refactor-implementation-acceptance"
        or historical.get("target_manifest_algorithm") != "sorted-relative-path-and-sha256-json-v1"
        or historical.get("capability_path") != "scripts/sc/config/skill-package-validator-capability.v1.json"
        or historical.get("required_probes") != {
            "detached-positive": {"status": "pass", "exit_code": 0},
            "detached-negative": {"status": "expected-failure", "exit_code": 1},
        }
        or historical.get("required_result") != {"status": "pass", "exit_code": 0, "authorizes": []}
        or historical.get("terminal_replay") != "execute-command-and-require-stdout-json-equals-receipt"
    ):
        errors.append("historical replay contract does not bind the frozen command and current wrapper")
    if seed.get("native_evidence_min_items") != 1 or seed.get("required_binding_fields") != [
        "path",
        "sha256",
    ]:
        errors.append("evaluation seed contract must require native evidence")
    if seed.get("required_native_repair_closures") != {
        "candidate-baseline-contamination": "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/repair/round-1/repair-closure.json",
        "self-hosted-knowledge-read-set-collision": "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/repair/round-2/repair-closure.json",
        "toolchain-policy-architecture-index-gap": "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/repair/round-3/repair-closure.json",
    }:
        errors.append("evaluation seed contract must bind the three native repair closures")
    if matrix.get("required_categories") != [
        "positive",
        "negative",
        "historical_compatibility",
        "dirty_baseline",
        "knowledge_read_set",
        "closed_policy",
    ] or matrix.get("required_case_fields") != [
        "case_id",
        "category",
        "validation_surface",
        "expected_observation",
    ] or matrix.get("exactly_once") is not True or matrix.get("replay_command") != [
        "py", "-3", "-B", "scripts/sc/skill_package_replay.py", "replay-matrix",
        "--matrix", "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/stable-candidate-replay-matrix.v1.json",
    ] or matrix.get("required_result_fields") != [
        "case_id", "category", "validation_surface", "status", "observed_result", "evidence",
    ] or matrix.get("terminal_replay") != "execute-command-and-require-stdout-json-equals-receipt" or matrix.get("authorizes") != []:
        errors.append("stable-candidate matrix contract must freeze six explicit observation cases")
    if artifact_contracts.get("core_skill_routes") != {
        "required_heading": "## Repository-Owned Package Validation",
        "required_directive": "Use this repository-owned command for Skill package validation:",
        "commands": {
            ".agents/skills/vdd-execution-plan/SKILL.md": "py -3 -B scripts/sc/skill_package_replay.py validate-package --target .agents/skills/vdd-execution-plan --capability scripts/sc/config/skill-package-validator-capability.v1.json",
            ".agents/skills/run-refactor-implementation-acceptance/SKILL.md": "py -3 -B scripts/sc/skill_package_replay.py validate-package --target .agents/skills/run-refactor-implementation-acceptance --capability scripts/sc/config/skill-package-validator-capability.v1.json",
        },
    }:
        errors.append("core Skill route contract is missing or drifted")
    if artifact_contracts.get("implementation_lifecycle") != {
        "implementation-authorized": {
            "state_owner": "maintainer",
            "authorizes": ["implementation-authorized"],
            "does_not_authorize": ["implementation-complete", "acceptance-passed", "release", "archived"],
        },
        "implementation-complete": {
            "state_owner": "quick-dev-tdd-adapter",
            "authorizes": ["implementation-complete"],
            "does_not_authorize": ["acceptance-passed", "release", "archived"],
        },
    }:
        errors.append("implementation lifecycle authority contract is missing or drifted")
    if artifact_contracts.get("manual_disposition_evidence") != {
        "path": ROUND3_REPAIR_EVIDENCE_PATH,
        "decision": "accepted-deterministic-round3-repair-evidence",
        "authorizes": ["implementation-authorized"],
    }:
        errors.append("manual disposition evidence contract is missing or drifted")

    reqs = requirements.get("requirements", [])
    acceptance = requirements.get("acceptance", [])
    slices = contract.get("slices", [])
    req_ids = [item.get("id") for item in reqs]
    acceptance_ids = [item.get("id") for item in acceptance]
    slice_ids = [item.get("slice_id") for item in slices]
    if len(req_ids) != len(set(req_ids)) or len(acceptance_ids) != len(set(acceptance_ids)):
        errors.append("requirement and acceptance IDs must be unique")
    if slice_ids != ["RMAP-S0", "RMAP-S1", "RMAP-S2", "RMAP-S3"]:
        errors.append("TC-D1 must have the frozen four-slice order")
    outside_tc_d1 = ("TC-E0", "TC-D2", "TC-D3", "TC-D4", "TC-D5", "TC-D6")
    for value in req_ids + slice_ids:
        if any(str(value).startswith(prefix) for prefix in outside_tc_d1):
            errors.append(f"outside TC-D1 scope identifier: {value}")
    excluded_features = {
        "miner",
        "curator",
        "autonomous skill modification",
        "learned ranking",
        "reinforcement learning",
    }
    for feature in requirements.get("proposed_features", []):
        if isinstance(feature, str) and feature.lower() in excluded_features:
            errors.append(f"excluded feature outside TC-D1 scope: {feature}")

    known_requirements = set(req_ids)
    known_acceptance = set(acceptance_ids)
    known_slices = set(slice_ids)
    covered_requirements: set[str] = set()
    covered_acceptance: set[str] = set()
    for item in reqs:
        if not set(item.get("acceptance_ids", [])).issubset(known_acceptance):
            errors.append(f"unknown acceptance ID in {item.get('id')}")
        if not set(item.get("slice_ids", [])).issubset(known_slices):
            errors.append(f"unknown slice ID in {item.get('id')}")
    command_ids = [item.get("id") for item in registry.get("commands", [])]
    if len(command_ids) != len(set(command_ids)):
        errors.append("command IDs must be unique")
    known_commands = set(command_ids)
    command_map = {
        item.get("id"): item
        for item in registry.get("commands", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    expected_replay_commands = {
        "historical-skill-package-replay": [
            "-3", "-B", "scripts/sc/skill_package_replay.py", "replay-package",
            "--target", ".agents/skills/run-refactor-implementation-acceptance",
            "--capability", "scripts/sc/config/skill-package-validator-capability.v1.json",
            "--probe-mode", "detached-positive-negative",
        ],
        "stable-candidate-matrix-replay": [
            "-3", "-B", "scripts/sc/skill_package_replay.py", "replay-matrix",
            "--matrix", "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/stable-candidate-replay-matrix.v1.json",
        ],
    }
    for command_id, argv in expected_replay_commands.items():
        descriptor = command_map.get(command_id, {})
        if descriptor.get("executable") != "py" or descriptor.get("argv") != argv or descriptor.get("shell") is not False:
            errors.append(f"registered replay command is missing or drifted: {command_id}")

    completed: set[str] = set()
    for item in slices:
        slice_id = item.get("slice_id")
        dependencies = set(item.get("depends_on", []))
        if not dependencies.issubset(completed):
            errors.append(f"slice dependency is missing or out of order: {slice_id}")
        completed.add(slice_id)
        current_requirements = set(item.get("requirement_ids", []))
        current_acceptance = set(item.get("acceptance_ids", []))
        if not current_requirements.issubset(known_requirements):
            errors.append(f"slice has unknown requirement: {slice_id}")
        if not current_acceptance.issubset(known_acceptance):
            errors.append(f"slice has unknown acceptance: {slice_id}")
        covered_requirements.update(current_requirements)
        covered_acceptance.update(current_acceptance)
        tdd = item.get("tdd", {})
        used_commands = [
            tdd.get("red", {}).get("command_id"),
            tdd.get("green", {}).get("command_id"),
            item.get("post_refactor_command_id"),
        ] + [entry.get("command_id") for entry in tdd.get("refactor", {}).get("invocations", [])]
        if not set(used_commands).issubset(known_commands):
            errors.append(f"slice references an unknown command: {slice_id}")
        for area in ("production", "tests", "documentation"):
            for path in item.get("allowed_changes", {}).get(area, []):
                if has_forbidden_allowed_path(path):
                    errors.append(f"forbidden allowed-change path in {slice_id}: {path}")
        if not item.get("execution_snapshot_paths"):
            errors.append(f"slice has no execution snapshot path: {slice_id}")
        for path in item.get("execution_snapshot_paths", []):
            if not (REPOSITORY_ROOT / path).exists():
                errors.append(f"execution snapshot path does not exist: {path}")
    if covered_requirements != known_requirements or covered_acceptance != known_acceptance:
        errors.append("contract does not cover every requirement and acceptance ID")
    for item in registry.get("commands", []):
        if item.get("shell") is not False:
            errors.append(f"command must use shell=false: {item.get('id')}")
        serialized = json.dumps(item, ensure_ascii=False).lower()
        if "c:/users/" in serialized or "\\users\\" in serialized or "quick_validate.py" in serialized:
            errors.append(f"command embeds a machine-specific validator path: {item.get('id')}")
    adapter = run([
        sys.executable,
        "-B",
        ".agents/skills/quick-dev-tdd-adapter/tools/validate_adapter_contract.py",
        str(PLAN_ROOT / "implementation-contract.v1.json"),
    ])
    if adapter.returncode:
        errors.append("Quick Dev rejected the plan-owned implementation contract")


def validate_implementation_lifecycle_state(state: dict[str, Any], errors: list[str]) -> None:
    implementation_contracts = {
        "implementation-authorized": {
            "state_owner": "maintainer",
            "authorizes": ["implementation-authorized"],
            "does_not_authorize": [
                "implementation-complete",
                "acceptance-passed",
                "release",
                "archived",
            ],
        },
        "implementation-complete": {
            "state_owner": "quick-dev-tdd-adapter",
            "authorizes": ["implementation-complete"],
            "does_not_authorize": ["acceptance-passed", "release", "archived"],
        },
    }
    expected = implementation_contracts.get(state.get("state"))
    if expected is None:
        errors.append("implementation-state validation requires an implementation lifecycle state")
    elif any(state.get(key) != value for key, value in expected.items()):
        errors.append("implementation lifecycle authority fields do not match the state owner contract")
    if state.get("state") == "implementation-authorized":
        authorization = state.get("implementation_authorization")
        evidence = REPOSITORY_ROOT / ROUND3_REPAIR_EVIDENCE_PATH
        evidence_hash = authorization.get("evidence_sha256") if isinstance(authorization, dict) else None
        predecessor = None
        if evidence.is_file():
            try:
                predecessor = load_json(evidence).get("predecessor_evidence")
            except (OSError, ValueError, TypeError):
                predecessor = None
        if (
            not isinstance(authorization, dict)
            or authorization.get("decision") != "accepted-deterministic-round3-repair-evidence"
            or authorization.get("evidence_path") != ROUND3_REPAIR_EVIDENCE_PATH
            or not isinstance(evidence_hash, str)
            or len(evidence_hash) != 71
            or not evidence_hash.startswith("sha256:")
            or authorization.get("next_slice") != "RMAP-S0"
            or authorization.get("authorizes") != ["implementation-authorized"]
            or not evidence.is_file()
            or sha256(evidence) != evidence_hash
            or not isinstance(predecessor, dict)
            or predecessor.get("sha256") != "sha256:300cb35a94e935dcf0e25ecf05c1924765d1efa780090bbbf642de89e974eac6"
        ):
            errors.append("implementation authorization does not bind the accepted Round 3 repair evidence")


def validate_state_and_knowledge(
    errors: list[str], *, allow_draft: bool, implementation_state: bool = False
) -> None:
    state = load_json(PLAN_ROOT / "plan-state.v1.json")
    resume = load_json(PLAN_ROOT / "resume-state.v1.json")
    context_path = PLAN_ROOT / "knowledge-context.v1.json"
    freeze_path = PLAN_ROOT / "knowledge-context.freeze.v1.json"
    if state.get("profile") != "self-hosted" or resume.get("profile") != "self-hosted":
        errors.append("state profiles must be self-hosted")
    if context_path.exists() != freeze_path.exists():
        errors.append("knowledge context and freeze receipt must exist together")
        return
    if not context_path.exists():
        if not allow_draft or state.get("state") != "draft" or not state.get("blocking_conditions"):
            errors.append("ready knowledge context and freeze receipt are required")
        if state.get("authorizes") != []:
            errors.append("draft state must authorize nothing")
        return
    context = load_json(context_path)
    freeze = load_json(freeze_path)
    if context.get("preflight", {}).get("status") != "ready":
        errors.append("knowledge preflight is not ready")
    if freeze.get("context_sha256") != sha256(context_path):
        errors.append("knowledge freeze does not bind context bytes")
    if freeze.get("authorizes") != []:
        errors.append("knowledge freeze must be non-authorizing")
    if implementation_state:
        validate_implementation_lifecycle_state(state, errors)
    else:
        if state.get("state") != "plan-ready" or state.get("authorizes") != ["plan-ready"]:
            errors.append("knowledge-ready VDD state must publish only plan-ready")
        if state.get("blocking_conditions"):
            errors.append("plan-ready state cannot retain blocking conditions")
    preflight = run([
        sys.executable,
        "-B",
        ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py",
        "--input",
        str(context_path),
        "--repository-root",
        str(REPOSITORY_ROOT),
        "--skill-input-receipt",
        str(
            PLAN_ROOT
            / "repair/round-7/recompilation-4/cer-repair-1/s8-authority-v2-repair"
            / "skill-input-v2/repair/current.v1.json"
        ),
        "--skill-input-contract",
        str(REPOSITORY_ROOT / ".agents/skills/vdd-execution-plan/references/skill-input-contract.v1.json"),
        "--skill-input-operation",
        "repair",
    ])
    if preflight.returncode:
        errors.append("current VDD knowledge preflight failed")


def validate_report_index(errors: list[str]) -> None:
    path = REPOSITORY_ROOT / "execution-plans/95-implementation-report-index.v1.json"
    value = load_json(path)
    expected = {
        "plan_directory": PLAN_DIRECTORY,
        "report_filename": "95-implementation-evolution-and-completion-report.md",
    }
    entries = value.get("entries", [])
    if entries.count(expected) != 1:
        errors.append("95 report index must contain exactly one TC-D1 entry")
    check = run([sys.executable, "-B", "scripts/python/validate_execution_plan_report_index.py"])
    if check.returncode:
        errors.append("repository 95 report index validation failed")


def validate_route(errors: list[str]) -> None:
    route = load_json(PLAN_ROOT / "model-route-decision.v1.json")
    requested = route.get("requestedExecution", {})
    if route.get("classification") != "self-hosted" or route.get("status") != "observe_only":
        errors.append("model route must preserve the self-hosted observe-only decision")
    if requested.get("model") != "gpt-5.6-sol" or requested.get("effort") != "high":
        errors.append("current VDD self-hosted route must request gpt-5.6-sol/high")
    if route.get("authorizes") != [] or route.get("actualExecution") is not None:
        errors.append("model route decision must remain non-authorizing and no-launch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-draft", action="store_true")
    parser.add_argument(
        "--implementation-state",
        action="store_true",
        help="Validate the implementation lifecycle state and permit declared mutable authority sources to drift",
    )
    args = parser.parse_args()
    errors: list[str] = []
    mutable_hashes: dict[str, str] = {}
    for relative in REQUIRED_FILES:
        if not (PLAN_ROOT / relative).is_file():
            errors.append(f"required plan file is missing: {relative}")
    index_text = (PLAN_ROOT / "00-index.md").read_text(encoding="utf-8")
    for heading in validate_headings(index_text):
        errors.append(f"required first-class heading is missing: {heading}")
    try:
        mutable_hashes = validate_authority(errors, allow_mutable_source_drift=args.implementation_state)
        validate_requirements_and_contract(errors)
        validate_state_and_knowledge(
            errors,
            allow_draft=args.allow_draft,
            implementation_state=args.implementation_state,
        )
        validate_report_index(errors)
        validate_route(errors)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError, KeyError) as exc:
        errors.append(str(exc))
    current_state = load_json(PLAN_ROOT / "plan-state.v1.json").get("state")
    if args.allow_draft:
        predicate = "draft-structurally-valid"
        authorizes: list[str] = []
        does_not_authorize = [
            "implementation-authorized",
            "implementation-complete",
            "acceptance-passed",
            "release",
            "archived",
        ]
    elif args.implementation_state:
        predicate = f"{current_state}-valid"
        authorizes = [current_state] if not errors and isinstance(current_state, str) else []
        does_not_authorize = (
            ["implementation-complete", "acceptance-passed", "release", "archived"]
            if current_state == "implementation-authorized"
            else ["acceptance-passed", "release", "archived"]
        )
    else:
        predicate = "plan-ready"
        authorizes = [] if errors else ["plan-ready"]
        does_not_authorize = [
            "implementation-authorized",
            "implementation-complete",
            "acceptance-passed",
            "release",
            "archived",
        ]
    payload = {
        "schema_version": "jimuyun.tc-d1-plan-validation.v1",
        "status": "pass" if not errors else "fail",
        "predicate": predicate,
        "errors": errors,
        "authorizes": authorizes,
        "mutable_authority_source_hashes": mutable_hashes,
        "does_not_authorize": does_not_authorize,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
