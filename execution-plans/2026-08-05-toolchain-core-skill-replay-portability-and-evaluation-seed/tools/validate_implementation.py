from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
HISTORICAL_PATH = "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd"
HISTORICAL_COMMIT = "8c47a52fc8f241f76da9ccb5d936b0fafe807f0f"
HISTORICAL_TREE = "95a7e396db70ef425e30d553e1e96976e2be7c94"
HISTORICAL_VALIDATOR_PATH = f"{HISTORICAL_PATH}/tools/validate_implementation.py"
HISTORICAL_COMMAND_EVIDENCE_PATH = f"{HISTORICAL_PATH}/95-implementation-evolution-and-completion-report.md"
HISTORICAL_COMMAND = ["py", "-3", HISTORICAL_VALIDATOR_PATH]
CURRENT_REPLAY_ENTRYPOINT = "scripts/sc/skill_package_replay.py"
CURRENT_REPLAY_TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CURRENT_REPLAY_CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
CURRENT_REPLAY_RECEIPT_PATH = (
    f"execution-plans/{PLAN_ROOT.name}/receipts/historical-8-01-skill-validation-replay.v1.json"
)
CURRENT_REPLAY_COMMAND = [
    "py",
    "-3",
    "-B",
    CURRENT_REPLAY_ENTRYPOINT,
    "replay-package",
    "--target",
    CURRENT_REPLAY_TARGET,
    "--capability",
    CURRENT_REPLAY_CAPABILITY,
    "--probe-mode",
    "detached-positive-negative",
]
MATRIX_PATH = f"execution-plans/{PLAN_ROOT.name}/stable-candidate-replay-matrix.v1.json"
MATRIX_RECEIPT_PATH = f"execution-plans/{PLAN_ROOT.name}/receipts/stable-candidate-replay-matrix.v1.json"
MATRIX_REPLAY_COMMAND = [
    "py",
    "-3",
    "-B",
    CURRENT_REPLAY_ENTRYPOINT,
    "replay-matrix",
    "--matrix",
    MATRIX_PATH,
]
MATRIX_CATEGORIES = (
    "positive",
    "negative",
    "historical_compatibility",
    "dirty_baseline",
    "knowledge_read_set",
    "closed_policy",
)
SEED_EXPECTATIONS = {
    "candidate-baseline-contamination": (
        "anchor_candidate",
        f"{HISTORICAL_PATH}/repair/round-1/repair-closure.json",
    ),
    "self-hosted-knowledge-read-set-collision": (
        "challenge_candidate",
        f"{HISTORICAL_PATH}/repair/round-2/repair-closure.json",
    ),
    "toolchain-policy-architecture-index-gap": (
        "challenge_candidate",
        f"{HISTORICAL_PATH}/repair/round-3/repair-closure.json",
    ),
}

SLICE_FILES = {
    "RMAP-S0": (
        "scripts/sc/skill_package_replay.py",
        "scripts/sc/config/skill-package-validator-capability.v1.json",
        "scripts/sc/schemas/skill-package-validation-receipt.v1.schema.json",
        "scripts/sc/schemas/toolchain-evaluation-seed-manifest.v1.schema.json",
        "scripts/sc/tests/test_skill_package_replay.py",
        "docs/adr/ADR-0058-toolchain-skill-replay-portability-and-evaluation-seeds.md",
    ),
    "RMAP-S1": (
        f"execution-plans/{PLAN_ROOT.name}/historical-compatibility-replay.v1.json",
        f"execution-plans/{PLAN_ROOT.name}/receipts/historical-8-01-skill-validation-replay.v1.json",
    ),
    "RMAP-S2": (
        f"execution-plans/{PLAN_ROOT.name}/evaluation-seeds.v1.json",
        MATRIX_PATH,
        MATRIX_RECEIPT_PATH,
    ),
    "RMAP-S3": (
        f"execution-plans/{PLAN_ROOT.name}/downstream-replay-receipt.v1.json",
    ),
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def run(command: list[str], timeout: int) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=timeout,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout_sha256": "sha256:" + hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
        "output_tail": completed.stdout[-2000:] if completed.returncode else "",
    }


def file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        return False
    try:
        int(value[7:], 16)
    except ValueError:
        return False
    return True


def directory_manifest_sha256(root: Path) -> str:
    entries = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": file_sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def validate_file_binding(
    binding: Any,
    errors: list[str],
    *,
    label: str,
    repository_root: Path = REPOSITORY_ROOT,
    expected_path: str | None = None,
) -> None:
    if not isinstance(binding, dict):
        errors.append(f"{label} binding must be an object")
        return
    relative = binding.get("path")
    digest = binding.get("sha256")
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        errors.append(f"{label} path must be repository-relative")
        return
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or relative != pure.as_posix():
        errors.append(f"{label} path must be normalized and repository-relative")
        return
    if expected_path is not None and relative != expected_path:
        errors.append(f"{label} path does not match the frozen contract")
    if not is_sha256(digest):
        errors.append(f"{label} SHA-256 is missing or malformed")
        return
    source = repository_root.joinpath(*pure.parts)
    if not source.is_file() or file_sha256(source) != digest:
        errors.append(f"{label} evidence is missing or drifted: {relative}")


def validate_historical_replay(
    record: dict[str, Any],
    receipt: dict[str, Any],
    errors: list[str],
    *,
    repository_root: Path = REPOSITORY_ROOT,
) -> None:
    if record.get("historical_portability") != "machine-bound" or record.get("authorizes") != []:
        errors.append("historical compatibility record overclaims portability or authority")
    if receipt.get("authorizes") != [] or receipt.get("status") != "pass" or receipt.get("exit_code") != 0:
        errors.append("historical replay receipt must be a passing non-authorizing result")

    record_validator = record.get("historical_validator")
    record_command = record.get("historical_command_evidence")
    receipt_validator = receipt.get("historical_validator")
    receipt_command = receipt.get("historical_command_evidence")
    validate_file_binding(
        record_validator,
        errors,
        label="historical validator",
        repository_root=repository_root,
        expected_path=HISTORICAL_VALIDATOR_PATH,
    )
    validate_file_binding(
        record_command,
        errors,
        label="historical command evidence",
        repository_root=repository_root,
        expected_path=HISTORICAL_COMMAND_EVIDENCE_PATH,
    )
    if receipt_validator != record_validator or receipt_command != record_command:
        errors.append("historical replay receipt does not bind the record's historical evidence")
    if not isinstance(record_command, dict) or record_command.get("command") != HISTORICAL_COMMAND or record_command.get("recorded_result") != "pass":
        errors.append("historical command evidence does not identify the frozen passing command")

    replay_binding = record.get("current_wrapper_replay")
    validate_file_binding(
        {
            "path": replay_binding.get("receipt_path") if isinstance(replay_binding, dict) else None,
            "sha256": replay_binding.get("receipt_sha256") if isinstance(replay_binding, dict) else None,
        },
        errors,
        label="current wrapper replay receipt",
        repository_root=repository_root,
        expected_path=CURRENT_REPLAY_RECEIPT_PATH,
    )
    if not isinstance(replay_binding, dict) or replay_binding.get("entrypoint") != CURRENT_REPLAY_ENTRYPOINT:
        errors.append("compatibility record does not bind the current wrapper entrypoint")

    replay = receipt.get("current_wrapper_replay")
    command = replay.get("command") if isinstance(replay, dict) else None
    if (
        not isinstance(replay, dict)
        or replay.get("entrypoint") != CURRENT_REPLAY_ENTRYPOINT
        or replay.get("status") != "pass"
        or replay.get("exit_code") != 0
        or command != CURRENT_REPLAY_COMMAND
    ):
        errors.append("historical replay receipt does not prove a passing current wrapper replay")
    target = replay.get("target_package") if isinstance(replay, dict) else None
    target_root = repository_root / CURRENT_REPLAY_TARGET
    if (
        not isinstance(target, dict)
        or target.get("path") != CURRENT_REPLAY_TARGET
        or not target_root.is_dir()
        or target.get("manifest_sha256") != directory_manifest_sha256(target_root)
    ):
        errors.append("historical replay receipt does not bind the intended target package manifest")
    validate_file_binding(
        replay.get("capability") if isinstance(replay, dict) else None,
        errors,
        label="current wrapper capability",
        repository_root=repository_root,
        expected_path=CURRENT_REPLAY_CAPABILITY,
    )
    resolved = replay.get("resolved_validator") if isinstance(replay, dict) else None
    if (
        not isinstance(resolved, dict)
        or not isinstance(resolved.get("path"), str)
        or not resolved["path"].strip()
        or not isinstance(resolved.get("version"), str)
        or not resolved["version"].strip()
        or not is_sha256(resolved.get("sha256"))
        or not isinstance(resolved.get("package_identity"), str)
        or not resolved["package_identity"].strip()
    ):
        errors.append("historical replay receipt does not bind the resolved validator identity")
    probes = replay.get("probes") if isinstance(replay, dict) else None
    expected_probes = {
        "detached-positive": ("pass", 0),
        "detached-negative": ("expected-failure", 1),
    }
    actual_probes = {
        item.get("probe_id"): (item.get("status"), item.get("exit_code"))
        for item in probes
        if isinstance(item, dict)
    } if isinstance(probes, list) else {}
    if actual_probes != expected_probes or len(probes) != 2:
        errors.append("historical replay receipt does not bind both detached probe outcomes")


def validate_evaluation_artifacts(
    seeds: dict[str, Any],
    matrix: dict[str, Any],
    errors: list[str],
    *,
    repository_root: Path = REPOSITORY_ROOT,
) -> None:
    seed_items = seeds.get("seeds")
    if not isinstance(seed_items, list):
        errors.append("evaluation seeds must be a list")
        seed_items = []
    actual: dict[str, str] = {}
    if len(seed_items) != len(SEED_EXPECTATIONS):
        errors.append("evaluation seeds must contain each frozen failure family exactly once")
    for index, item in enumerate(seed_items):
        if not isinstance(item, dict):
            errors.append(f"evaluation seed {index} must be an object")
            continue
        family = item.get("failure_family")
        candidate_class = item.get("candidate_class")
        if not isinstance(family, str) or family in actual:
            errors.append("evaluation seed failure families must be unique strings")
        else:
            actual[family] = candidate_class
        evidence_items = item.get("native_evidence")
        if not isinstance(evidence_items, list) or not evidence_items:
            errors.append(f"evaluation seed requires native evidence: {family}")
            continue
        evidence_paths: set[str] = set()
        for evidence_index, evidence in enumerate(evidence_items):
            validate_file_binding(
                evidence,
                errors,
                label=f"seed native evidence {family}[{evidence_index}]",
                repository_root=repository_root,
            )
            if isinstance(evidence, dict) and isinstance(evidence.get("path"), str):
                if evidence["path"] in evidence_paths:
                    errors.append(f"seed native evidence paths must be unique: {family}")
                evidence_paths.add(evidence["path"])
        expectation = SEED_EXPECTATIONS.get(family)
        if expectation is not None and expectation[1] not in evidence_paths:
            errors.append(f"evaluation seed does not bind its native repair closure: {family}")
    if actual != {key: value[0] for key, value in SEED_EXPECTATIONS.items()}:
        errors.append("evaluation seeds do not exactly match the frozen candidate classes")
    if seeds.get("baseline_status") != "non-authorizing-candidates" or seeds.get("authorizes") != []:
        errors.append("evaluation seeds must not publish a quality baseline")

    cases = matrix.get("cases")
    if matrix.get("authorizes") != [] or not isinstance(cases, list):
        errors.append("stable-candidate replay matrix must be a non-authorizing case list")
        cases = []
    categories: list[str] = []
    case_ids: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"stable-candidate matrix case {index} must be an object")
            continue
        category = case.get("category")
        if not isinstance(category, str):
            errors.append(f"stable-candidate matrix case {index} has an invalid category")
            continue
        categories.append(category)
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append(f"stable-candidate matrix case lacks a case identifier: {category}")
        else:
            case_ids.append(case_id)
        if not isinstance(case.get("validation_surface"), str) or not case["validation_surface"].strip():
            errors.append(f"stable-candidate matrix case lacks a validation surface: {category}")
        if not isinstance(case.get("expected_observation"), str) or not case["expected_observation"].strip():
            errors.append(f"stable-candidate matrix case lacks an expected observation: {category}")
    if len(categories) != len(MATRIX_CATEGORIES) or set(categories) != set(MATRIX_CATEGORIES):
        errors.append("stable-candidate replay matrix must cover each frozen category exactly once")
    if len(case_ids) != len(MATRIX_CATEGORIES) or len(set(case_ids)) != len(MATRIX_CATEGORIES):
        errors.append("stable-candidate replay matrix case identifiers must be unique")


def validate_matrix_receipt(
    matrix: dict[str, Any],
    receipt: dict[str, Any],
    errors: list[str],
    *,
    repository_root: Path = REPOSITORY_ROOT,
) -> None:
    matrix_path = repository_root / MATRIX_PATH
    if (
        receipt.get("status") != "pass"
        or receipt.get("exit_code") != 0
        or receipt.get("authorizes") != []
        or receipt.get("runner_entrypoint") != CURRENT_REPLAY_ENTRYPOINT
        or receipt.get("command") != MATRIX_REPLAY_COMMAND
        or receipt.get("matrix_path") != MATRIX_PATH
        or not matrix_path.is_file()
        or receipt.get("matrix_sha256") != file_sha256(matrix_path)
    ):
        errors.append("matrix replay receipt is failed, authorizing, or not bound to the executed matrix")
    cases = matrix.get("cases") if isinstance(matrix.get("cases"), list) else []
    expected_cases = {
        item.get("case_id"): (
            item.get("category"),
            item.get("validation_surface"),
            item.get("expected_observation"),
        )
        for item in cases
        if isinstance(item, dict) and isinstance(item.get("case_id"), str)
    }
    if len(expected_cases) != len(MATRIX_CATEGORIES) or any(
        not isinstance(item, dict) or not isinstance(item.get("case_id"), str)
        for item in cases
    ):
        errors.append("matrix cases must have unique case identifiers")
    results = receipt.get("case_results")
    if not isinstance(results, list) or len(results) != len(MATRIX_CATEGORIES):
        errors.append("matrix replay receipt must contain one result per case")
        results = []
    actual_cases: dict[str, tuple[Any, Any, Any]] = {}
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            errors.append(f"matrix replay result {index} must be an object")
            continue
        case_id = result.get("case_id")
        if not isinstance(case_id, str) or case_id in actual_cases:
            errors.append("matrix replay result case identifiers must be unique strings")
            continue
        actual_cases[case_id] = (
            result.get("category"),
            result.get("validation_surface"),
            result.get("observed_result"),
        )
        if result.get("status") != "pass" or not isinstance(result.get("observed_result"), str) or not result["observed_result"].strip():
            errors.append(f"matrix replay result is missing a passing observation: {case_id}")
        evidence = result.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"matrix replay result requires evidence: {case_id}")
            continue
        for evidence_index, binding in enumerate(evidence):
            validate_file_binding(
                binding,
                errors,
                label=f"matrix replay evidence {case_id}[{evidence_index}]",
                repository_root=repository_root,
            )
    if actual_cases != expected_cases:
        errors.append("matrix replay results do not exactly match the declared surfaces and expected observations")


def run_json_receipt(command: list[str], receipt_path: Path, timeout: int) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=timeout,
    )
    matches = False
    if completed.returncode == 0 and receipt_path.is_file():
        try:
            matches = json.loads(completed.stdout) == load_json(receipt_path)
        except (json.JSONDecodeError, ValueError):
            matches = False
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout_sha256": "sha256:" + hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
        "receipt_path": receipt_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "receipt_match": matches,
        "output_tail": completed.stdout[-2000:] if completed.returncode or not matches else "",
    }


def check_skill_routes(errors: list[str]) -> None:
    routes = {
        ".agents/skills/vdd-execution-plan/SKILL.md": (
            "py -3 -B scripts/sc/skill_package_replay.py validate-package "
            "--target .agents/skills/vdd-execution-plan "
            "--capability scripts/sc/config/skill-package-validator-capability.v1.json"
        ),
        ".agents/skills/run-refactor-implementation-acceptance/SKILL.md": (
            "py -3 -B scripts/sc/skill_package_replay.py validate-package "
            "--target .agents/skills/run-refactor-implementation-acceptance "
            "--capability scripts/sc/config/skill-package-validator-capability.v1.json"
        ),
    }
    for relative, command in routes.items():
        path = REPOSITORY_ROOT / relative
        required_block = (
            "## Repository-Owned Package Validation\n\n"
            "Use this repository-owned command for Skill package validation:\n\n"
            "```text\n"
            f"{command}\n"
            "```"
        )
        if not path.is_file() or required_block not in path.read_text(encoding="utf-8"):
            errors.append(f"core Skill does not route package validation through the repository wrapper: {relative}")


def check_historical_tree(errors: list[str]) -> None:
    completed = subprocess.run(
        ["git", "rev-parse", f"refs/heads/main:{HISTORICAL_PATH}"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode or completed.stdout.strip() != HISTORICAL_TREE:
        errors.append("historical 8-01 Git tree changed")
        return
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", HISTORICAL_COMMIT, "--", HISTORICAL_PATH],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if listing.returncode:
        errors.append("historical 8-01 baseline file manifest is unavailable")
        return
    expected = {line.strip() for line in listing.stdout.splitlines() if line.strip()}
    root = REPOSITORY_ROOT / HISTORICAL_PATH
    actual = {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    } if root.is_dir() else set()
    if actual != expected:
        errors.append("historical 8-01 candidate file set changed")
    for relative in sorted(expected & actual):
        current = REPOSITORY_ROOT / relative
        baseline = subprocess.run(
            ["git", "show", f"{HISTORICAL_COMMIT}:{relative}"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
        )
        if baseline.returncode or baseline.stdout != current.read_bytes():
            errors.append(f"historical 8-01 candidate bytes changed: {relative}")


def check_json_artifacts(slice_id: str, errors: list[str]) -> None:
    for relative in SLICE_FILES[slice_id]:
        path = REPOSITORY_ROOT / relative
        if not path.is_file():
            errors.append(f"required implementation artifact is missing: {relative}")
    if slice_id == "RMAP-S1" and not errors:
        record = load_json(PLAN_ROOT / "historical-compatibility-replay.v1.json")
        receipt = load_json(PLAN_ROOT / "receipts/historical-8-01-skill-validation-replay.v1.json")
        validate_historical_replay(record, receipt, errors)
    if slice_id == "RMAP-S2" and not errors:
        seeds = load_json(PLAN_ROOT / "evaluation-seeds.v1.json")
        matrix = load_json(PLAN_ROOT / "stable-candidate-replay-matrix.v1.json")
        matrix_receipt = load_json(PLAN_ROOT / "receipts/stable-candidate-replay-matrix.v1.json")
        validate_evaluation_artifacts(seeds, matrix, errors)
        validate_matrix_receipt(matrix, matrix_receipt, errors)
    if slice_id == "RMAP-S3" and not errors:
        receipt = load_json(PLAN_ROOT / "downstream-replay-receipt.v1.json")
        if receipt.get("authorizes") != [] or receipt.get("status") != "pass":
            errors.append("downstream replay receipt is absent, failed or authorizing")
        check_skill_routes(errors)


def current_mutable_authority_hashes() -> dict[str, str]:
    manifest = load_json(PLAN_ROOT / "authority-manifest.v1.json")
    mutable_paths = set(manifest.get("mutable_source_paths", []))
    return {
        item["path"]: "sha256:" + hashlib.sha256((REPOSITORY_ROOT / item["path"]).read_bytes()).hexdigest()
        for item in manifest.get("source_files", [])
        if item.get("path") in mutable_paths and (REPOSITORY_ROOT / item["path"]).is_file()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", choices=tuple(SLICE_FILES))
    args = parser.parse_args()
    selected = [args.slice] if args.slice else list(SLICE_FILES)
    errors: list[str] = []
    results: list[dict[str, Any]] = []
    check_historical_tree(errors)
    for slice_id in selected:
        check_json_artifacts(slice_id, errors)

    if not errors and "RMAP-S0" in selected:
        results.append(run([sys.executable, "-B", "scripts/sc/tests/test_skill_package_replay.py"], 300))
        results.append(run([sys.executable, "-B", ".agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py", "--skill-root", ".agents/skills/vdd-execution-plan"], 180))
        results.append(run([sys.executable, "-B", "-m", "unittest", "discover", "-s", ".agents/skills/vdd-execution-plan/scripts/tests", "-p", "test_*.py"], 300))
    if not errors and "RMAP-S1" in selected:
        results.append(run_json_receipt(CURRENT_REPLAY_COMMAND, REPOSITORY_ROOT / CURRENT_REPLAY_RECEIPT_PATH, 300))
    if not errors and "RMAP-S2" in selected:
        results.append(run_json_receipt(MATRIX_REPLAY_COMMAND, REPOSITORY_ROOT / MATRIX_RECEIPT_PATH, 300))
    if not errors and "RMAP-S3" in selected:
        results.append(run([sys.executable, "-B", "-m", "unittest", "discover", "-s", ".agents/skills/run-refactor-implementation-acceptance/tests", "-p", "test_*skill*replay*.py"], 300))
        results.append(run([sys.executable, "-B", ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py", "validate-package"], 300))
        results.append(run([sys.executable, "-B", "execution-plans/2026-08-01-workflow-model-routing-control-plane/tools/validate_implementation.py"], 1200))
    if not errors and args.slice is None:
        results.append(run([sys.executable, "-B", str(PLAN_ROOT / "tools/validate_plan.py"), "--implementation-state"], 180))
        results.append(run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(PLAN_ROOT / "tools/tests"), "-p", "test_*.py"], 180))
    for item in results:
        if item["exit_code"] != 0 or item.get("receipt_match") is False:
            errors.append(f"registered command failed: {' '.join(item['command'])}")
    full = args.slice is None
    payload = {
        "schema_version": "jimuyun.tc-d1-implementation-validation.v1",
        "status": "pass" if not errors else "fail",
        "predicate": "implementation-complete" if full else "slice-ready",
        "selected_slices": selected,
        "errors": errors,
        "results": results,
        "mutable_authority_source_hashes": current_mutable_authority_hashes(),
        "authorizes": ["implementation-complete"] if full and not errors else [],
        "does_not_authorize": ["acceptance-passed", "release", "archived"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
