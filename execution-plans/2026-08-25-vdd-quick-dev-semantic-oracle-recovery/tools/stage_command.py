"""Small stateless command dispatcher used by the plan registry.

It executes the slice's real behavior tests; it never writes pass state or
terminal evidence. The adapter owns lifecycle evidence and the terminal
predicate only validates run-local artifacts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", required=True, choices=[f"S{i}" for i in range(1, 7)])
    parser.add_argument("--stage", required=True, choices=("green", "refactor", "terminal"))
    parser.add_argument("--plan-dir", required=True)
    parser.add_argument("--run-root")
    parser.add_argument("--resolve-selectors", action="store_true")
    args = parser.parse_args()
    if args.stage == "terminal":
        if not args.run_root:
            return 2
        if args.slice == "S6":
            from terminal_validator import prepare_terminal_observation
            prepare_terminal_observation(Path(args.plan_dir), Path(args.run_root))
            owner = Path(args.plan_dir) / "tools" / "artifact_owners.py"
            produced = subprocess.run([sys.executable, str(owner), "--plan-dir", args.plan_dir, "--slice", "S6", "--stage", "terminal", "--run-root", args.run_root], cwd=Path(args.plan_dir).parents[1], check=False)
            if produced.returncode != 0:
                return produced.returncode
        out_name = "implementation-complete-result.json" if args.slice == "S6" else "slice-ready-result.json"
        predicate = "terminal_predicate.py" if args.slice == "S6" else "slice_ready_predicate.py"
        command = [sys.executable, str(Path(args.plan_dir) / "tools" / predicate),
                   "--repository-root", str(Path(args.plan_dir).parents[1]),
                   "--plan-dir", args.plan_dir, "--slice", args.slice,
                   "--run-root", args.run_root, "--out", str(Path(args.run_root) / out_name)]
        return subprocess.call(command, cwd=Path(args.plan_dir).parents[1])
    contract = json.loads((Path(args.plan_dir) / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next(item for item in contract["slices"] if item["slice_id"] == args.slice)
    repository_root = Path(args.plan_dir).parents[1]
    red_selector = str(Path(args.plan_dir).parents[1] / selected["tdd"]["red"]["test_selector"])
    regression = selected.get("tdd", {}).get("regression", {}).get("test_selectors", [])
    if args.resolve_selectors:
        print(json.dumps({"slice_id": args.slice, "stage": args.stage, "red_selector": selected["tdd"]["red"]["test_selector"], "pytest_selectors": [selected["tdd"]["red"]["test_selector"], *regression]}, sort_keys=True))
        return 0
    # GREEN and REFACTOR must rerun the exact RED selector, plus regressions.
    selectors = [red_selector, *[str(Path(args.plan_dir).parents[1] / path) for path in regression]]
    red_env = None
    if args.run_root:
        red_env = {**__import__("os").environ, "QD_RUN_ROOT": str(Path(args.run_root).resolve())}
    if args.run_root and args.slice != "S6":
        builder = Path(args.plan_dir) / "tools" / "build_run_inputs.py"
        built = subprocess.run([sys.executable, str(builder), "--plan-dir", args.plan_dir, "--run-root", args.run_root, "--slice", args.slice], cwd=Path(args.plan_dir).parents[1], check=False)
        if built.returncode != 0:
            return built.returncode
        materializer = Path(args.plan_dir) / "tools" / "run_input_materializer.py"
        materialized = subprocess.run([sys.executable, str(materializer), "--run-root", args.run_root, "--slice", args.slice], cwd=Path(args.plan_dir).parents[1], check=False)
        if materialized.returncode != 0:
            return materialized.returncode
    owner = Path(args.plan_dir) / "tools" / "artifact_owners.py"
    command = [sys.executable, str(owner), "--plan-dir", args.plan_dir, "--slice", args.slice, "--stage", args.stage]
    run_root = args.run_root
    if not run_root and args.stage == "terminal":
        plan_id = Path(args.plan_dir).name
        candidates = sorted((Path(args.plan_dir).parents[1] / "logs" / "tdd-adapter" / plan_id / args.slice).glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            run_root = str(candidates[0])
    if run_root:
        command.extend(["--run-root", run_root])
    regression_result = subprocess.run([sys.executable, "-m", "pytest", *selectors], cwd=repository_root, env=red_env, check=False)
    if regression_result.returncode != 0:
        return regression_result.returncode
    owner_result = subprocess.run(command, cwd=repository_root.parent, check=False)
    return owner_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
