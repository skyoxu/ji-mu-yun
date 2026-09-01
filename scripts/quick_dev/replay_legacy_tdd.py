#!/usr/bin/env python3
"""Replay a legacy TDD plan at one RED baseline and the current checkout.

This is a regression harness only. It never promotes legacy artifacts to current
evidence authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

FAILURE_RE = re.compile(r"FAILURE_ID:([A-Z0-9][A-Z0-9._-]*)")


def _run(argv: list[str], cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, shell=False, text=True, capture_output=True, timeout=timeout, check=False)


def _selectors(root: Path, plan_rel: str) -> list[dict[str, object]]:
    contract = json.loads((root / plan_rel / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    rows = []
    for item in contract.get("slices", []):
        red = item.get("tdd", {}).get("red", {})
        selector = red.get("test_selector")
        expected = red.get("expected_failure_ids")
        if not isinstance(selector, str) or not selector or not isinstance(expected, list) or not expected:
            raise ValueError(f"legacy slice {item.get('slice_id')} has invalid RED contract")
        rows.append({"slice_id": item.get("slice_id"), "selector": selector, "expected_failure_ids": expected})
    if not rows:
        raise ValueError("legacy plan contains no RED selectors")
    return rows


def _probe_red(root: Path, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    results = []
    for row in rows:
        proc = _run([sys.executable, "-m", "pytest", str(row["selector"]), "-q"], root)
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        observed = sorted(set(FAILURE_RE.findall(output)))
        expected = sorted(set(str(x) for x in row["expected_failure_ids"]))
        results.append({"slice_id": row["slice_id"], "selector": row["selector"], "exit_code": proc.returncode, "observed_failure_ids": observed, "expected_failure_ids": expected, "valid_red": proc.returncode != 0 and observed == expected})
    return results


def _probe_green(root: Path, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    results = []
    for row in rows:
        proc = _run([sys.executable, "-m", "pytest", str(row["selector"]), "-q"], root)
        results.append({"slice_id": row["slice_id"], "selector": row["selector"], "exit_code": proc.returncode, "green": proc.returncode == 0})
    return results


def replay(*, root: Path, plan_rel: str, red_baseline: str) -> dict[str, object]:
    root = root.resolve()
    rows = _selectors(root, plan_rel)
    static_script = root / plan_rel / "tools" / "validate_red_green_contract.py"
    static = _run([sys.executable, str(static_script), str(root / plan_rel)], root)
    current = _probe_green(root, rows)

    fetch = _run(["git", "fetch", "--no-tags", "origin", red_baseline], root, timeout=600)
    if fetch.returncode != 0:
        raise RuntimeError("cannot fetch legacy RED baseline: " + (fetch.stdout + fetch.stderr)[-1000:])
    temp_parent = Path(tempfile.mkdtemp(prefix="ch456-legacy-replay-"))
    baseline_root = temp_parent / "baseline"
    add = _run(["git", "worktree", "add", "--detach", str(baseline_root), red_baseline], root, timeout=600)
    if add.returncode != 0:
        shutil.rmtree(temp_parent, ignore_errors=True)
        raise RuntimeError("cannot materialize legacy RED baseline: " + (add.stdout + add.stderr)[-1000:])
    try:
        baseline_rows = _selectors(baseline_root, plan_rel)
        current_ids = [(r["slice_id"], r["selector"], tuple(r["expected_failure_ids"])) for r in rows]
        baseline_ids = [(r["slice_id"], r["selector"], tuple(r["expected_failure_ids"])) for r in baseline_rows]
        if baseline_ids != current_ids:
            raise ValueError("legacy replay contract drifted between RED baseline and current checkout")
        baseline = _probe_red(baseline_root, baseline_rows)
    finally:
        _run(["git", "worktree", "remove", "--force", str(baseline_root)], root, timeout=600)
        shutil.rmtree(temp_parent, ignore_errors=True)

    valid = static.returncode == 0 and all(item["valid_red"] for item in baseline) and all(item["green"] for item in current)
    return {
        "schema": "quick-dev.legacy-tdd-replay.v1",
        "plan": plan_rel,
        "red_baseline": red_baseline,
        "static_contract_exit_code": static.returncode,
        "baseline": baseline,
        "current": current,
        "status": "pass" if valid else "fail",
        "authorizes_current_evidence": False,
        "authorizes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--red-baseline", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        result = replay(root=root, plan_rel=args.plan.replace("\\", "/"), red_baseline=args.red_baseline)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result = {"schema":"quick-dev.legacy-tdd-replay.v1","status":"fail","reason":str(exc),"authorizes_current_evidence":False,"authorizes":[]}
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
