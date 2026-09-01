#!/usr/bin/env python3
"""Measure self-hosted detached-promotion false-green rejection.

The mutation corpus is independent of the validator implementation: each case
represents one normative trust-boundary failure that must be rejected. A valid
baseline must pass, and at least 95% of invalid mutations must be rejected.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from detached_promotion import validate_detached_bundle

REQUIRED_REJECTION_RATE = 0.95


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(role: str, path: Path, *, fixture_kind: str | None = None) -> dict:
    item = {"role": role, "path": str(path.resolve()), "sha256": _sha(path), "read_only": True}
    if fixture_kind is not None:
        item["fixture_kind"] = fixture_kind
    return item


def _valid_bundle(root: Path) -> tuple[dict, Path, dict[str, Path]]:
    candidate = root / "candidate"
    detached = root / "detached"
    candidate.mkdir()
    detached.mkdir()
    files = {
        "judge": detached / "judge.py",
        "oracle": detached / "oracle.py",
        "positive": detached / "positive.json",
        "negative": detached / "negative.json",
        "mutation": detached / "mutation.json",
    }
    files["judge"].write_text("def judge(value):\n    return bool(value)\n", encoding="utf-8")
    files["oracle"].write_text("EXPECTED = {'status': 'pass'}\n", encoding="utf-8")
    files["positive"].write_text('{"case":"positive"}\n', encoding="utf-8")
    files["negative"].write_text('{"case":"negative"}\n', encoding="utf-8")
    files["mutation"].write_text('{"case":"mutation"}\n', encoding="utf-8")
    bundle = {
        "schema": "detached-judge-bundle.v1",
        "source_commit": "fixture-commit",
        "source_tree": "fixture-tree",
        "judge_identity": "detached-fixture-judge",
        "judge_version": "1",
        "read_only_open_result": True,
        "promotion_revalidation_result": True,
        "artifacts": [
            _artifact("judge", files["judge"]),
            _artifact("oracle", files["oracle"]),
            _artifact("fixture", files["positive"], fixture_kind="positive"),
            _artifact("fixture", files["negative"], fixture_kind="negative"),
            _artifact("fixture", files["mutation"], fixture_kind="mutation"),
        ],
    }
    return bundle, candidate, files


def _mutations(bundle: dict, candidate: Path, files: dict[str, Path]) -> list[tuple[str, dict]]:
    cases: list[tuple[str, dict]] = []

    def add(name: str, mutate) -> None:
        value = copy.deepcopy(bundle)
        mutate(value)
        cases.append((name, value))

    add("schema-drift", lambda b: b.__setitem__("schema", "detached-judge-bundle.v0"))
    for field in ("source_commit", "source_tree", "judge_identity", "judge_version"):
        add(f"missing-{field}", lambda b, field=field: b.__setitem__(field, ""))
    add("read-only-open-false", lambda b: b.__setitem__("read_only_open_result", False))
    add("promotion-revalidation-false", lambda b: b.__setitem__("promotion_revalidation_result", False))
    add("artifacts-empty", lambda b: b.__setitem__("artifacts", []))
    add("artifact-not-object", lambda b: b["artifacts"].__setitem__(0, "not-an-object"))
    add("unknown-role", lambda b: b["artifacts"][0].__setitem__("role", "executor"))
    add("fixture-kind-invalid", lambda b: b["artifacts"][2].__setitem__("fixture_kind", "happy"))
    add("fixture-kind-on-judge", lambda b: b["artifacts"][0].__setitem__("fixture_kind", "positive"))
    add("artifact-path-empty", lambda b: b["artifacts"][0].__setitem__("path", ""))
    add("artifact-missing", lambda b: b["artifacts"][0].__setitem__("path", str((files["judge"].parent / "missing.py").resolve())))
    add("artifact-hash-mismatch", lambda b: b["artifacts"][0].__setitem__("sha256", "sha256:" + "0" * 64))
    add("artifact-not-read-only", lambda b: b["artifacts"][0].__setitem__("read_only", False))

    inside = candidate / "judge.py"
    shutil.copyfile(files["judge"], inside)
    def inside_candidate(b: dict) -> None:
        b["artifacts"][0]["path"] = str(inside.resolve())
        b["artifacts"][0]["sha256"] = _sha(inside)
    add("artifact-inside-candidate", inside_candidate)

    tainted = files["judge"].parent / "tainted-judge.py"
    tainted.write_text("import runtime_evidence\n", encoding="utf-8")
    def current_writer_import(b: dict) -> None:
        b["artifacts"][0]["path"] = str(tainted.resolve())
        b["artifacts"][0]["sha256"] = _sha(tainted)
    add("judge-imports-current-writer", current_writer_import)

    add("role-cover-missing-oracle", lambda b: b.__setitem__("artifacts", [x for x in b["artifacts"] if x.get("role") != "oracle"]))
    add("fixture-cover-missing-mutation", lambda b: b.__setitem__("artifacts", [x for x in b["artifacts"] if x.get("fixture_kind") != "mutation"]))
    return cases


def evaluate() -> dict:
    with tempfile.TemporaryDirectory(prefix="ch456-detached-") as raw:
        root = Path(raw)
        bundle, candidate, files = _valid_bundle(root)
        baseline_valid, baseline_findings = validate_detached_bundle(bundle, candidate_root=candidate)
        rows = []
        rejected = 0
        for name, mutated in _mutations(bundle, candidate, files):
            valid, findings = validate_detached_bundle(mutated, candidate_root=candidate)
            did_reject = not valid
            rejected += int(did_reject)
            rows.append({"case": name, "rejected": did_reject, "findings": findings})
        total = len(rows)
        rate = rejected / total if total else 0.0
        threshold = baseline_valid and rate >= REQUIRED_REJECTION_RATE
        return {
            "schema": "quick-dev.detached-mutation-metric.v1",
            "baseline_valid": baseline_valid,
            "baseline_findings": baseline_findings,
            "mutation_cases": total,
            "rejected_cases": rejected,
            "rejection_rate": round(rate, 6),
            "required_rejection_rate": REQUIRED_REJECTION_RATE,
            "threshold_passed": threshold,
            "cases": rows,
            "authorizes": [],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = evaluate()
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["threshold_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
