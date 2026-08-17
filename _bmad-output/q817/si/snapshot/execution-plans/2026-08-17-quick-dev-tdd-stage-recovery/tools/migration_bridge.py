from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys


TEST_TEMPLATES = {
    ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_lifecycle.py": '''import importlib.util
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_red_only_stage_runner_is_available():
    driver = _load("loop_plan_directory")
    assert callable(driver.run_red_only)
''',
    ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_recovery.py": '''import importlib.util
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_router_recognizes_a_current_red_handoff():
    router = _load("route_plan_directory")
    assert callable(router.current_red_handoff)
''',
    ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_migration_cutover.py": '''import importlib.util
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_staged_cutover_guard_is_available():
    driver = _load("loop_plan_directory")
    assert callable(driver.staged_cutover_guard)
''',
}


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_slice(plan: Path, slice_id: str) -> tuple[dict[str, object], dict[str, object]]:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    if contract.get("red_execution_owner") != "quick-dev-tdd-adapter":
        raise ValueError("migration bridge requires Quick Dev-owned RED")
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        raise ValueError("declared slice is missing")
    return contract, selected


def materialize_red_test(root: Path, selected: dict[str, object]) -> Path:
    planned = selected.get("planned_new_files")
    red = selected.get("tdd", {}).get("red") if isinstance(selected.get("tdd"), dict) else None
    if not isinstance(planned, list) or len(planned) != 1 or not all(isinstance(item, str) for item in planned):
        raise ValueError("bridge requires exactly one slice-local planned test file")
    if not isinstance(red, dict) or red.get("test_selector") != planned[0]:
        raise ValueError("RED selector must equal the declared planned test file")
    relative = Path(planned[0])
    if relative.is_absolute() or ".." in relative.parts or relative.as_posix() not in TEST_TEMPLATES:
        raise ValueError("planned test is not an approved migration bridge target")
    target = (root / relative).resolve()
    target.relative_to(root.resolve())
    template = TEST_TEMPLATES[relative.as_posix()]
    if target.exists():
        if target.read_text(encoding="utf-8") != template:
            raise ValueError("existing planned RED test does not match the bridge template")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template, encoding="utf-8", newline="\n")
    return target


def run_red(root: Path, plan: Path, slice_id: str) -> Path:
    contract, selected = _load_slice(plan, slice_id)
    test_path = materialize_red_test(root, selected)
    run_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%dT%H%M%S-%fZ")
    run_dir = root / "logs" / "tdd-adapter" / str(contract["plan_id"]) / slice_id / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", os.path.relpath(test_path, root), "-q"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode == 0:
        raise RuntimeError("RED command unexpectedly passed")
    contract_path = plan / "implementation-contract.v1.json"
    output = {
        "schema_version": "quick-dev-tdd-adapter.red-handoff.v1",
        "plan_id": contract["plan_id"],
        "slice_id": slice_id,
        "run_id": run_id,
        "predicate": "implementation-needed",
        "status": "pass",
        "contract_hash": _sha(contract_path),
        "test_selector": selected["tdd"]["red"]["test_selector"],
        "expected_failure_ids": selected["tdd"]["red"]["expected_failure_ids"],
        "stage": "red",
        "exit_code": completed.returncode,
        "commands_attempted": [f"quick-dev-generated-red-{slice_id}"],
        "test_hash": _sha(test_path),
        "authorizes": [],
    }
    (run_dir / "implementation-needed-result.json").write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (run_dir / "red-output.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8", newline="\n")
    return run_dir


def materialize_only(root: Path, plan: Path, slice_id: str) -> Path:
    _contract, selected = _load_slice(plan, slice_id)
    return materialize_red_test(root, selected)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--snapshot-path", action="append", required=True)
    parser.add_argument("--materialize-only", action="store_true")
    args = parser.parse_args()
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    if args.materialize_only:
        test_path = materialize_only(root, plan, args.slice_id)
        print(json.dumps({"test_path": str(test_path), "next_action": "prepare-skill-input", "authorizes": []}, sort_keys=True))
        return 0
    run_dir = run_red(root, plan, args.slice_id)
    print(json.dumps({"run_dir": str(run_dir), "next_action": "implement", "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
