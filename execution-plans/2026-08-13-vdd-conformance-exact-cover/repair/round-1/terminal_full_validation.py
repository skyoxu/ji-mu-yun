"""Current deterministic validation for VDD repair round 1."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def validate_mapping() -> None:
    payload = json.loads((PLAN / "repair/round-1/requirements-acceptance-slice-command.v1.json").read_text(encoding="utf-8"))
    rows = payload["requirements"]
    ids = {row["id"] for row in rows}
    if ids != {f"VCEC-{index:03d}" for index in range(1, 37)}:
        raise SystemExit("requirement universe is not exactly VCEC-001..VCEC-036")
    acceptance = {item for row in rows for item in row["acceptance_ids"]}
    if acceptance != {f"VCEC-A{index:02d}" for index in range(1, 44)}:
        raise SystemExit("acceptance universe is not exactly VCEC-A01..VCEC-A43")
    if any(not row.get("slice") or not row.get("command") for row in rows):
        raise SystemExit("mapping row lacks slice or command")
    reverse = payload.get("reverse_mapping", {})
    expected = {}
    for row in rows:
        for acceptance in row["acceptance_ids"]:
            expected.setdefault(acceptance, []).append(row["id"])
    if reverse != expected:
        raise SystemExit("reverse requirement/acceptance mapping does not match forward mapping")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["source-freeze", "exact-cover-negative", "recovery-context", "composition"])
    args = parser.parse_args()
    validate_mapping()
    run([sys.executable, ".agents/skills/bmad-spec/scripts/tests/test_canonical_package.py"])
    run([sys.executable, "-m", "unittest", "scripts.python.tests.test_skill_input_consumption", "scripts.python.tests.test_knowledge_context_validation", "scripts.python.tests.test_knowledge_workflow_migration", "scripts.python.tests.test_knowledge_adapter_handoff"])
    run([sys.executable, ".agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py", "--skill-root", ".agents/skills/vdd-execution-plan"])
    run(["git", "diff", "--check"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
