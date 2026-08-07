from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


PLAN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PLAN_DIR.parents[1]
SLICE_ORDER = ["RMAP-S0", "RMAP-S1", "RMAP-S2"]
SLICE_FILES = {
    "RMAP-S0": [
        ".agents/skills/quick-dev-tdd-adapter/schemas/regression-repair-contract.v1.schema.json",
        ".agents/skills/quick-dev-tdd-adapter/tools/regression_repair_contract.py",
        "docs/adr/ADR-0060-quick-dev-phase-regression-repair-mode.md",
    ],
    "RMAP-S1": [
        ".agents/skills/quick-dev-tdd-adapter/tools/stage_observation_runner.py",
        ".agents/skills/quick-dev-tdd-adapter/tools/run_slice_lifecycle.py",
        ".agents/skills/quick-dev-tdd-adapter/tools/route_plan_directory.py",
    ],
    "RMAP-S2": [
        ".agents/skills/quick-dev-tdd-adapter/tools/repair_investigation.py",
        ".agents/skills/quick-dev-tdd-adapter/SKILL.md",
        "docs/standards/phase-service.md",
        "docs/architecture/ADR_INDEX_PHASE.md",
    ],
}


def run(command: list[str], timeout: int = 600) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
        check=False,
    )
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def check_required_files(slice_id: str | None = None) -> list[str]:
    errors: list[str] = []
    selected = SLICE_ORDER if slice_id is None else SLICE_ORDER[: SLICE_ORDER.index(slice_id) + 1]
    for current in selected:
        for relative in SLICE_FILES[current]:
            if relative in {
                ".agents/skills/quick-dev-tdd-adapter/tools/regression_repair_contract.py",
                ".agents/skills/quick-dev-tdd-adapter/tools/repair_investigation.py",
            }:
                continue
            if not (REPO_ROOT / relative).is_file():
                errors.append(f"missing:{relative}")
    return errors


def require_tokens(relative: str, tokens: list[str], errors: list[str]) -> None:
    path = REPO_ROOT / relative
    if not path.is_file():
        errors.append(f"missing:{relative}")
        return
    text = path.read_text(encoding="utf-8")
    for token in tokens:
        if token not in text:
            errors.append(f"token-missing:{relative}:{token}")


def check_s0_static() -> list[str]:
    errors = check_required_files("RMAP-S0")
    if errors:
        return errors
    require_tokens(
        ".agents/skills/quick-dev-tdd-adapter/schemas/regression-repair-contract.v1.schema.json",
        ["regression_repair", "failure_ids", "test_selector", "source_implementation", "callsites", "historical_log_search"],
        errors,
    )
    if (REPO_ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/regression_repair_contract.py").is_file():
        require_tokens(
            ".agents/skills/quick-dev-tdd-adapter/tools/regression_repair_contract.py",
            ["regression_repair", "repair_callsite_missing", "historical_log_search_missing", "speculative_repair_blocked", "validate_contract_case"],
            errors,
        )
    require_tokens(
        ".agents/skills/bmad-quick-dev/scripts/quick_dev_input_router.py",
        ["maintenanceMode", "regression_repair", "regression-repair-contract.v1.schema.json"],
        errors,
    )
    require_tokens(
        ".agents/skills/bmad-quick-dev/tests/test_quick_dev_input_router.py",
        ["regression_repair", "maintenanceMode"],
        errors,
    )
    return sorted(set(errors))


def check_s1_static() -> list[str]:
    errors = check_s0_static()
    if errors:
        return errors
    require_tokens(
        ".agents/skills/quick-dev-tdd-adapter/tools/stage_observation_runner.py",
        ["stdout", "stderr", "truncated", "sha256"],
        errors,
    )
    require_tokens(
        ".agents/skills/quick-dev-tdd-adapter/tools/run_slice_lifecycle.py",
        ["expected_failure_ids", "test_selector", "failure_class", "failure_fingerprint"],
        errors,
    )
    require_tokens(
        ".agents/skills/quick-dev-tdd-adapter/tools/route_plan_directory.py",
        ["failure_fingerprint", "repeat_count", "repeated-failure-fingerprint"],
        errors,
    )
    require_tokens(
        ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_adapter.py",
        ["expected_failure_ids", "test_selector"],
        errors,
    )
    require_tokens(
        ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_plan_directory_loop.py",
        ["failure_fingerprint", "repeat_count"],
        errors,
    )
    return sorted(set(errors))


def check_s2_static() -> list[str]:
    errors = check_s1_static()
    if errors:
        return errors
    if (REPO_ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/repair_investigation.py").is_file():
        require_tokens(
            ".agents/skills/quick-dev-tdd-adapter/tools/repair_investigation.py",
        [
            "source_implementation",
            "callsites",
            "direct_consumers",
            "existing_tests",
            "dependency_closure",
            "historical_log_search",
            "error_evidence_reads",
            "protected_path_approval",
            "phase_validation_commands",
        ],
            errors,
        )
    require_tokens(
        ".agents/skills/quick-dev-tdd-adapter/SKILL.md",
        ["regression_repair", "historical log", "real callsite", "existing test", "speculative"],
        errors,
    )
    require_tokens(
        "docs/standards/phase-service.md",
        ["regression_repair", "protected", "smoke"],
        errors,
    )
    require_tokens(
        "docs/adr/ADR-0060-quick-dev-phase-regression-repair-mode.md",
        ["Status: Accepted", "regression_repair", "ADR-0041", "ADR-0051"],
        errors,
    )
    require_tokens("docs/architecture/ADR_INDEX_PHASE.md", ["ADR-0060"], errors)
    return sorted(set(errors))


def validate_slice(slice_id: str, test_selector: str | None = None, expected_failure_ids: list[str] | None = None) -> list[str]:
    if slice_id == "RMAP-S1":
        if test_selector != "RMAP-S1-RED" or not expected_failure_ids:
            return ["red-identity-selector-binding-missing"]
        if set(expected_failure_ids) != {"QDRR-A06", "QDRR-A10"}:
            return ["red-identity-failure-id-binding-mismatch"]
    static = {
        "RMAP-S0": check_s0_static,
        "RMAP-S1": check_s1_static,
        "RMAP-S2": check_s2_static,
    }[slice_id]()
    if static:
        return static
    commands = [
        [sys.executable, "-B", ".agents/skills/bmad-quick-dev/tests/test_quick_dev_input_router.py"],
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            ".agents/skills/quick-dev-tdd-adapter/tools/tests",
            "-p",
            "test_*.py",
        ],
    ]
    if slice_id == "RMAP-S2":
        commands.append(
            [
                sys.executable,
                "-B",
                ".agents/skills/quick-dev-tdd-adapter/tools/validate_adapter_contract.py",
                str(PLAN_DIR / "implementation-contract.v1.json"),
            ]
        )
    if slice_id == "RMAP-S0":
        commands.append([
            sys.executable,
            "-B",
            ".agents/skills/quick-dev-tdd-adapter/tools/regression_repair_contract.py",
            "--fixture",
            str(PLAN_DIR / "fixtures/regression-repair-contract-cases.v1.json"),
        ])
    if slice_id == "RMAP-S2":
        commands.append([
            sys.executable,
            "-B",
            ".agents/skills/quick-dev-tdd-adapter/tools/repair_investigation.py",
            "--fixture",
            str(PLAN_DIR / "fixtures/regression-repair-contract-cases.v1.json"),
        ])
    errors: list[str] = []
    for command in commands:
        code, output = run(command)
        if code != 0:
            errors.append(f"targeted-command-failed:{' '.join(command)}:{output}")
    return sorted(set(errors))


def check_lifecycle_entry(plan_dir: Path = PLAN_DIR) -> list[str]:
    try:
        state = json.loads((plan_dir / "plan-state.v1.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ["implementation-state-invalid"]
    lifecycle_state = state.get("state")
    owner = state.get("state_owner")
    if lifecycle_state not in {"implementation-authorized", "implementation-complete"}:
        return [f"implementation-authorization-required:{lifecycle_state}"]
    expected_owner = {
        "implementation-authorized": "maintainer",
        "implementation-complete": "quick-dev-tdd-adapter",
    }[lifecycle_state]
    if owner != expected_owner:
        return [f"implementation-state-owner-invalid:{lifecycle_state}"]
    required_authority = ["implementation-authorized" if lifecycle_state == "implementation-authorized" else "implementation-complete"]
    if state.get("authorizes") != required_authority:
        return [f"implementation-state-authority-invalid:{lifecycle_state}"]
    return []


def validate_full() -> list[str]:
    errors = check_lifecycle_entry()
    if errors:
        return errors
    errors.extend(validate_slice("RMAP-S2"))
    if errors:
        return sorted(set(errors))
    commands = [
        [sys.executable, "-B", str(PLAN_DIR / "tools/validate_implementation.py"), "--slice", "RMAP-S1", "--test-selector", "RMAP-S1-RED", "--expected-failure-id", "QDRR-A06", "--expected-failure-id", "QDRR-A10"],
        [sys.executable, "-B", str(PLAN_DIR / "tools/validate_plan.py"), "--implementation-state"],
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            str(PLAN_DIR / "tools/tests"),
            "-p",
            "test_*.py",
        ],
    ]
    for command in commands:
        code, output = run(command)
        if code != 0:
            errors.append(f"terminal-command-failed:{' '.join(command)}:{output}")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", choices=SLICE_ORDER)
    parser.add_argument("--test-selector")
    parser.add_argument("--expected-failure-id", action="append", default=[])
    args = parser.parse_args()
    errors = validate_slice(args.slice, args.test_selector, args.expected_failure_id) if args.slice else validate_full()
    result = {
        "schema_version": "jimuyun.quick-dev-phase-regression-repair-implementation-validation.v1",
        "status": "pass" if not errors else "fail",
        "slice": args.slice,
        "errors": errors,
        "predicate": "slice-ready" if args.slice else "implementation-complete",
        "authorizes": ["implementation-complete"] if not errors and not args.slice else [],
    }
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
