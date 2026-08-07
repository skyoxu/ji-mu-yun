from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


PLAN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PLAN_DIR.parents[1]
SKILL_ROOT = REPO_ROOT / ".agents/skills/orchestrate-plan-delivery"
ADR_PATH = REPO_ROOT / "docs/adr/ADR-0059-opt-in-plan-delivery-coordinator.md"
SLICE_ORDER = ["RMAP-S0", "RMAP-S1", "RMAP-S2", "RMAP-S3"]
SLICE_FILES = {
    "RMAP-S0": [
        ".agents/skills/orchestrate-plan-delivery/SKILL.md",
        ".agents/skills/orchestrate-plan-delivery/agents/openai.yaml",
        ".agents/skills/orchestrate-plan-delivery/schemas/delivery-checkpoint.v1.schema.json",
        ".agents/skills/orchestrate-plan-delivery/tests/test_delivery_loop.py",
        "docs/adr/ADR-0059-opt-in-plan-delivery-coordinator.md",
    ],
    "RMAP-S1": [
        ".agents/skills/orchestrate-plan-delivery/scripts/delivery_core.py",
        ".agents/skills/orchestrate-plan-delivery/scripts/plan_delivery.py",
        ".agents/skills/orchestrate-plan-delivery/references/recovery-and-ownership.md",
    ],
    "RMAP-S2": [
        ".agents/skills/orchestrate-plan-delivery/tests/fixtures/state-matrix.v1.json",
        ".agents/skills/orchestrate-plan-delivery/tests/fixtures/confirmation-boundaries.v1.json",
    ],
    "RMAP-S3": [
        ".agents/skills/orchestrate-plan-delivery/tests/fixtures/recovery-matrix.v1.json",
        ".agents/skills/orchestrate-plan-delivery/tests/fixtures/composition-matrix.v1.json",
    ],
}


def run(command: list[str], timeout: int = 300) -> tuple[int, str]:
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
            if not (REPO_ROOT / relative).is_file():
                errors.append(f"missing:{relative}")
    return errors


def check_package_static() -> list[str]:
    errors = check_required_files()
    if errors:
        return errors
    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    for token in [
        "run-phase-bootstrap-review",
        "quick-dev-tdd-adapter",
        "run-refactor-implementation-acceptance",
        "vdd-execution-plan",
        "high-cost",
        "protected",
        "manual_pause",
        "authorizes",
    ]:
        if token not in skill_text:
            errors.append(f"skill-contract-token-missing:{token}")
    forbidden = ["Start-Process", "schtasks", "Register-ScheduledTask", "process name"]
    package_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SKILL_ROOT.rglob("*")
        if path.is_file() and path.suffix in {".md", ".py", ".json", ".yaml"}
    )
    for token in forbidden:
        if token in package_text:
            errors.append(f"forbidden-background-token:{token}")
    windows_profile_patterns = ("C:/" + "Users/", "C:" + "\\Users\\")
    if any(pattern in package_text for pattern in windows_profile_patterns):
        errors.append("machine-specific-path-in-skill")
    if (SKILL_ROOT / "README.md").exists():
        errors.append("auxiliary-readme-forbidden")
    adr_text = ADR_PATH.read_text(encoding="utf-8")
    if "Status: Accepted" not in adr_text:
        errors.append("adr-0059-not-accepted")
    adr_index = (REPO_ROOT / "docs/architecture/ADR_INDEX_PHASE.md").read_text(encoding="utf-8")
    if "ADR-0059" not in adr_index:
        errors.append("adr-0059-not-indexed")
    return errors


def quick_validate_command() -> list[str] | None:
    configured = os.environ.get("CODEX_HOME")
    codex_root = Path(configured) if configured else Path.home() / ".codex"
    validator = codex_root / "skills/.system/skill-creator/scripts/quick_validate.py"
    if not validator.is_file():
        return None
    return [sys.executable, str(validator), str(SKILL_ROOT)]


def validate_package() -> list[str]:
    errors = check_package_static()
    if errors:
        return errors
    command = quick_validate_command()
    if command is None:
        return ["skill-creator-quick-validate-capability-missing"]
    code, output = run(command)
    if code != 0:
        errors.append(f"skill-creator-quick-validate-failed:{output}")
    return errors


def validate_slice(slice_id: str) -> list[str]:
    errors = check_required_files(slice_id)
    if errors:
        return errors
    code, output = run(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            ".agents/skills/orchestrate-plan-delivery/tests",
            "-p",
            "test_*.py",
        ]
    )
    if code != 0:
        errors.append(f"coordinator-tests-failed:{output}")
    if slice_id in {"RMAP-S1", "RMAP-S2", "RMAP-S3"}:
        code, output = run(
            [sys.executable, "-B", ".agents/skills/orchestrate-plan-delivery/scripts/plan_delivery.py", "self-check"]
        )
        if code != 0:
            errors.append(f"coordinator-self-check-failed:{output}")
    if slice_id == "RMAP-S3":
        errors.extend(validate_package())
    return sorted(set(errors))


def check_lifecycle_entry(plan_dir: Path = PLAN_DIR) -> list[str]:
    """Require the maintainer-owned implementation entry before terminal validation."""
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
    return []


def validate_full() -> list[str]:
    entry_errors = check_lifecycle_entry()
    if entry_errors:
        return entry_errors
    errors = validate_slice("RMAP-S3")
    if errors:
        return errors
    commands = [
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
    parser.add_argument("--package-only", action="store_true")
    args = parser.parse_args()
    if args.package_only:
        errors = validate_package()
    elif args.slice:
        errors = validate_slice(args.slice)
    else:
        errors = validate_full()
    result = {
        "schema_version": "jimuyun.toolchain-plan-delivery-loop-implementation-validation.v1",
        "status": "pass" if not errors else "fail",
        "slice": args.slice,
        "package_only": args.package_only,
        "errors": errors,
        "authorizes": ["implementation-complete"] if not errors and not args.slice and not args.package_only else [],
    }
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
