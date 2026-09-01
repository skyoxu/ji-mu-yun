#!/usr/bin/env python3
"""Run the strict Chapter 4/5/6 implementation work-package closure locally.

This is a convenience orchestrator for an environment that actually has a live
LLM backend (the user's Windows/Codex workstation is the primary intended host).
It does not create `acceptance-passed` and has no release/merge authority. It
only reproduces the same deterministic + live evidence denominator used by the
Chapter 4/5/6 capability workflow and then invokes the strict final completion
predicate.

Each invocation refreshes only this runner's declared evidence files under
`logs/`. After all producers run, one candidate-sealing step binds every final
evidence object to the current HEAD, then a SHA-256 manifest freezes the exact
bytes. The final predicate consumes only that sealed set; unrelated repository
files are never recursively deleted.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "ch456.local-final-acceptance-run.v1"


def _run(argv: Sequence[str], *, env: dict[str, str], label: str) -> dict[str, Any]:
    proc = subprocess.run(
        list(argv),
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "label": label,
        "argv": list(argv),
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "passed": proc.returncode == 0,
    }


def _python(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def _refresh_owned_files(paths: dict[str, Path]) -> None:
    for path in paths.values():
        if not path.exists():
            continue
        if not path.is_file():
            raise SystemExit(f"refusing to replace non-file evidence path: {path}")
        path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="codex-cli", choices=("codex-cli", "openai-api"))
    parser.add_argument("--evidence-dir", type=Path, default=Path("logs/ch456-final-acceptance"))
    args = parser.parse_args()

    evidence_dir = (ROOT / args.evidence_dir).resolve() if not args.evidence_dir.is_absolute() else args.evidence_dir.resolve()
    logs_root = (ROOT / "logs").resolve()
    try:
        relative = evidence_dir.relative_to(logs_root)
    except ValueError as exc:
        raise SystemExit("--evidence-dir must remain under repository logs/") from exc
    if relative == Path("."):
        raise SystemExit("--evidence-dir must be a child directory under logs/")
    evidence_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["SC_LLM_BACKEND"] = args.backend

    paths = {
        "architecture": evidence_dir / "ch456-architecture-reconcile.json",
        "curated": evidence_dir / "ch456-curated-semantic-quality.json",
        "semantic_mutations": evidence_dir / "ch456-semantic-chain-mutations.json",
        "agent_context": evidence_dir / "ch456-agent-context-mutations.json",
        "real_semantic": evidence_dir / "ch456-real-semantic-quality.json",
        "stable": evidence_dir / "ch456-stable-facade.json",
        "detached": evidence_dir / "ch456-detached-mutations.json",
        "replay": evidence_dir / "ch456-selective-replay.json",
        "live_blind": evidence_dir / "ch456-live-blind-benchmark.json",
        "legacy": evidence_dir / "ch456-8-25-replay.json",
        "seal": evidence_dir / "ch456-final-evidence-candidate-seal.json",
        "manifest": evidence_dir / "ch456-final-evidence-manifest.json",
        "final": evidence_dir / "ch456-final-completion.json",
        "summary": evidence_dir / "ch456-local-final-acceptance-run.json",
    }
    _refresh_owned_files(paths)

    steps: list[tuple[str, list[str]]] = [
        ("architecture-reconcile", _python("scripts/vdd/evaluate_architecture_reconcile.py", "--out", str(paths["architecture"]))),
        ("curated-semantic", _python("scripts/vdd/evaluate_semantic_quality.py", "--out", str(paths["curated"]))),
        ("semantic-chain-mutations", _python("scripts/vdd/evaluate_semantic_chain_mutations.py", "--out", str(paths["semantic_mutations"]))),
        ("agent-context-mutations", _python("scripts/vdd/evaluate_agent_context_mutations.py", "--out", str(paths["agent_context"]))),
        ("real-semantic", _python("scripts/vdd/evaluate_real_semantic_quality.py", "--backend", args.backend, "--out", str(paths["real_semantic"]))),
        ("stable-facade", _python("scripts/quick_dev/evaluate_stable_facade.py", "--out", str(paths["stable"]))),
        ("detached-mutations", _python("scripts/quick_dev/evaluate_detached_mutations.py", "--out", str(paths["detached"]))),
        ("selective-replay", _python("scripts/quick_dev/evaluate_replay_matrix.py", "--out", str(paths["replay"]))),
        ("fresh-medium-deterministic", _python("-m", "pytest", "-q", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_ch456_fresh_medium_task.py")),
        ("live-blind-medium", _python("scripts/quick_dev/run_live_blind_benchmark.py", "--backend", args.backend, "--require-live", "--out", str(paths["live_blind"]))),
        ("full-vdd-regression", _python("-m", "pytest", "-q", ".agents/skills/vdd-execution-plan/scripts/tests")),
        ("full-quick-dev-regression", _python("-m", "pytest", "-q", ".agents/skills/quick-dev-tdd-adapter/tools/tests")),
        (
            "8-25-replay",
            _python(
                "scripts/quick_dev/replay_legacy_tdd.py",
                "--plan",
                "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery",
                "--red-baseline",
                "7890d90cd9a9183159742bacc5575a07ad061dc7",
                "--out",
                str(paths["legacy"]),
            ),
        ),
    ]

    results: list[dict[str, Any]] = []
    for label, argv in steps:
        result = _run(argv, env=env, label=label)
        results.append(result)
        print(json.dumps({"label": label, "exit_code": result["exit_code"], "passed": result["passed"]}, sort_keys=True), flush=True)

    denominator = [
        paths["architecture"], paths["curated"], paths["semantic_mutations"], paths["agent_context"],
        paths["real_semantic"], paths["stable"], paths["detached"], paths["replay"],
        paths["live_blind"], paths["legacy"],
    ]
    seal_argv = _python("scripts/quick_dev/seal_final_evidence_candidate.py")
    for path in denominator:
        seal_argv.extend(["--evidence", str(path)])
    seal_argv.extend(["--out", str(paths["seal"])])
    seal_result = _run(seal_argv, env=env, label="seal-final-evidence-candidate")
    results.append(seal_result)
    print(json.dumps({"label": seal_result["label"], "exit_code": seal_result["exit_code"], "passed": seal_result["passed"]}, sort_keys=True), flush=True)

    manifest_argv = _python(
        "scripts/quick_dev/build_final_evidence_manifest.py",
        "--architecture-reconcile", str(paths["architecture"]),
        "--curated-semantic", str(paths["curated"]),
        "--semantic-chain-mutations", str(paths["semantic_mutations"]),
        "--agent-context-mutations", str(paths["agent_context"]),
        "--real-semantic", str(paths["real_semantic"]),
        "--stable-facade", str(paths["stable"]),
        "--detached-mutations", str(paths["detached"]),
        "--selective-replay", str(paths["replay"]),
        "--live-blind", str(paths["live_blind"]),
        "--legacy-replay", str(paths["legacy"]),
        "--out", str(paths["manifest"]),
    )
    manifest_result = _run(manifest_argv, env=env, label="freeze-final-evidence-manifest")
    results.append(manifest_result)
    print(json.dumps({"label": manifest_result["label"], "exit_code": manifest_result["exit_code"], "passed": manifest_result["passed"]}, sort_keys=True), flush=True)

    final_argv = _python(
        "scripts/quick_dev/evaluate_final_completion.py",
        "--manifest", str(paths["manifest"]),
        "--architecture-reconcile", str(paths["architecture"]),
        "--curated-semantic", str(paths["curated"]),
        "--semantic-chain-mutations", str(paths["semantic_mutations"]),
        "--agent-context-mutations", str(paths["agent_context"]),
        "--real-semantic", str(paths["real_semantic"]),
        "--stable-facade", str(paths["stable"]),
        "--detached-mutations", str(paths["detached"]),
        "--selective-replay", str(paths["replay"]),
        "--live-blind", str(paths["live_blind"]),
        "--legacy-replay", str(paths["legacy"]),
        "--out", str(paths["final"]),
    )
    final_result = _run(final_argv, env=env, label="strict-final-completion")
    results.append(final_result)

    failed_steps = [item["label"] for item in results if not item["passed"]]
    summary = {
        "schema": SCHEMA,
        "backend": args.backend,
        "evidence_dir": evidence_dir.relative_to(ROOT).as_posix(),
        "status": "pass" if not failed_steps else "blocked",
        "failed_steps": failed_steps,
        "steps": results,
        "candidate_seal_ref": paths["seal"].relative_to(ROOT).as_posix(),
        "manifest_ref": paths["manifest"].relative_to(ROOT).as_posix(),
        "final_evidence_ref": paths["final"].relative_to(ROOT).as_posix(),
        "authorizes": [],
    }
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "failed_steps": failed_steps, "summary": paths["summary"].relative_to(ROOT).as_posix()}, sort_keys=True))
    return 0 if not failed_steps else 1


if __name__ == "__main__":
    raise SystemExit(main())
