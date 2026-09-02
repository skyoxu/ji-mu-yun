#!/usr/bin/env python3
"""Evaluate real VDD semantic-worker quality against a curated Chapter 4/5/6 fixture.

This evaluator never converts an unavailable LLM backend into a PASS. When the
backend is unavailable it records environment-blocked and exits successfully so
hosted CI can preserve the distinction between implementation readiness and real
model-quality evidence. When the backend is runnable, recall/precision must meet
the normative 95% threshold and the atomic obligation count must not collapse the
human-curated independent behavior floor.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SC = ROOT / "scripts" / "sc"
VDD = ROOT / ".agents" / "skills" / "vdd-execution-plan" / "scripts"
for path in (SC, VDD):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from _llm_backend import inspect_llm_backend, resolve_llm_backend
from semantic_compiler_authority import compile_plan

FIXTURE = ROOT / ".agents" / "skills" / "vdd-execution-plan" / "scripts" / "fixtures" / "ch456-curated-semantic-quality.md"
MIN_ACTIVE_OBLIGATIONS = 23
REQUIRED_SCORE = 0.95


def _source_head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def evaluate(backend: str | None) -> dict:
    backend_name = resolve_llm_backend(backend)
    info = inspect_llm_backend(backend_name)
    result = {
        "schema": "vdd.real-semantic-quality-metric.v1",
        "fixture": FIXTURE.relative_to(ROOT).as_posix(),
        "source_head": _source_head(),
        "backend": backend_name,
        "availability": info,
        "required_precision": REQUIRED_SCORE,
        "required_recall": REQUIRED_SCORE,
        "minimum_active_obligations": MIN_ACTIVE_OBLIGATIONS,
        "status": "environment-blocked",
        "execution_attempted": False,
        "execution_succeeded": False,
        "atomic_quality_metrics": None,
        "compiler_status": None,
        "compiler_stage": None,
        "compiler_findings": [],
        "authorizes": [],
    }
    if info.get("available") is not True:
        return result

    previous = __import__("os").environ.get("SC_LLM_BACKEND")
    __import__("os").environ["SC_LLM_BACKEND"] = backend_name
    tmp_parent = ROOT / ".tmp-ch456-semantic-quality"
    tmp_parent.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="run-", dir=tmp_parent) as raw:
            result["execution_attempted"] = True
            compiled = compile_plan(
                requirements=FIXTURE,
                out_dir=Path(raw) / "plan",
                profile="standard",
            )
            metrics = compiled.get("atomic_quality_metrics")
            result["compiler_status"] = compiled.get("status")
            result["compiler_stage"] = compiled.get("stage")
            findings = compiled.get("findings")
            result["compiler_findings"] = [str(item) for item in findings] if isinstance(findings, list) else []
            result["atomic_quality_metrics"] = metrics
            if not isinstance(metrics, dict):
                result["status"] = "metric-unavailable"
                return result
            precision = metrics.get("precision")
            recall = metrics.get("recall")
            active = metrics.get("active_obligation_count")
            score_ok = (
                isinstance(precision, (int, float))
                and isinstance(recall, (int, float))
                and precision >= REQUIRED_SCORE
                and recall >= REQUIRED_SCORE
            )
            floor_ok = isinstance(active, int) and active >= MIN_ACTIVE_OBLIGATIONS
            result["precision_threshold_passed"] = score_ok and precision >= REQUIRED_SCORE
            result["recall_threshold_passed"] = score_ok and recall >= REQUIRED_SCORE
            result["atomic_behavior_floor_passed"] = floor_ok
            result["execution_succeeded"] = bool(score_ok and floor_ok)
            result["status"] = "pass" if result["execution_succeeded"] else "quality-threshold-failed"
            return result
    except (OSError, UnicodeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        result["status"] = "worker-failed"
        result["error"] = str(exc)
        return result
    finally:
        if previous is None:
            __import__("os").environ.pop("SC_LLM_BACKEND", None)
        else:
            __import__("os").environ["SC_LLM_BACKEND"] = previous
        try:
            if tmp_parent.is_dir() and not any(tmp_parent.iterdir()):
                tmp_parent.rmdir()
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = evaluate(args.backend)
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    # environment-blocked is an evidence state, not a false failure for hosted CI.
    return 0 if result["status"] in {"pass", "environment-blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
