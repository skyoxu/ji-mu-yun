#!/usr/bin/env python3
"""Measure self-hosted detached-promotion false-green rejection.

The corpus is independent of the validator implementation. It proves both
structural trust-boundary rejection and exact coverage of the normative Quick
Dev failure taxonomy. A valid baseline must pass, at least 95% of general
structural mutations must be rejected, and failure-family leakage must be zero.
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

from detached_promotion import FAILURE_FAMILIES, validate_detached_bundle

REQUIRED_REJECTION_RATE = 0.95
REQUIRED_FAILURE_FAMILY_LEAKAGE_RATE = 0.0


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(
    role: str,
    path: Path,
    *,
    fixture_kind: str | None = None,
    failure_family: str | None = None,
) -> dict:
    item = {"role": role, "path": str(path.resolve()), "sha256": _sha(path), "read_only": True}
    if fixture_kind is not None:
        item["fixture_kind"] = fixture_kind
    if failure_family is not None:
        item["failure_family"] = failure_family
    return item


def _valid_bundle(root: Path) -> tuple[dict, Path, dict[str, Path]]:
    candidate = root / "candidate"
    detached = root / "detached"
    candidate.mkdir()
    detached.mkdir()
    files: dict[str, Path] = {
        "judge": detached / "judge.py",
        "oracle": detached / "oracle.py",
        "positive": detached / "positive.json",
    }
    files["judge"].write_text("def judge(value):\n    return bool(value)\n", encoding="utf-8")
    files["oracle"].write_text("EXPECTED = {'status': 'pass'}\n", encoding="utf-8")
    files["positive"].write_text('{"case":"positive"}\n', encoding="utf-8")

    artifacts = [
        _artifact("judge", files["judge"]),
        _artifact("oracle", files["oracle"]),
        _artifact("fixture", files["positive"], fixture_kind="positive"),
    ]
    for index, family in enumerate(sorted(FAILURE_FAMILIES)):
        key = "family-" + family
        path = detached / f"{key}.json"
        path.write_text(json.dumps({"failure_family": family}) + "\n", encoding="utf-8")
        files[key] = path
        fixture_kind = "negative" if index % 2 == 0 else "mutation"
        artifacts.append(
            _artifact("fixture", path, fixture_kind=fixture_kind, failure_family=family)
        )

    bundle = {
        "schema": "detached-judge-bundle.v1",
        "source_commit": "fixture-commit",
        "source_tree": "fixture-tree",
        "judge_identity": "detached-fixture-judge",
        "judge_version": "1",
        "read_only_open_result": True,
        "promotion_revalidation_result": True,
        "artifacts": artifacts,
    }
    return bundle, candidate, files


def _general_mutations(bundle: dict, candidate: Path, files: dict[str, Path]) -> list[tuple[str, dict]]:
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

    first_fixture = next(i for i, item in enumerate(bundle["artifacts"]) if item.get("role") == "fixture")
    first_family = next(i for i, item in enumerate(bundle["artifacts"]) if item.get("failure_family"))
    add("fixture-kind-invalid", lambda b: b["artifacts"][first_fixture].__setitem__("fixture_kind", "happy"))
    add("fixture-kind-on-judge", lambda b: b["artifacts"][0].__setitem__("fixture_kind", "positive"))
    add("failure-family-on-judge", lambda b: b["artifacts"][0].__setitem__("failure_family", "artifact-integrity"))
    add("negative-family-missing", lambda b: b["artifacts"][first_family].pop("failure_family", None))
    add("unknown-failure-family", lambda b: b["artifacts"][first_family].__setitem__("failure_family", "self-reported-pass"))
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
    add("role-cover-missing-oracle", lambda b: b.__setitem__("artifacts", [x for x in b["artifacts"] if isinstance(x, dict) and x.get("role") != "oracle"]))
    add("fixture-cover-missing-positive", lambda b: b.__setitem__("artifacts", [x for x in b["artifacts"] if not (isinstance(x, dict) and x.get("fixture_kind") == "positive")]))
    add("fixture-cover-missing-negative", lambda b: b.__setitem__("artifacts", [x for x in b["artifacts"] if not (isinstance(x, dict) and x.get("fixture_kind") == "negative")]))
    add("fixture-cover-missing-mutation", lambda b: b.__setitem__("artifacts", [x for x in b["artifacts"] if not (isinstance(x, dict) and x.get("fixture_kind") == "mutation")]))
    return cases


def _family_omission_mutations(bundle: dict) -> list[tuple[str, dict]]:
    rows: list[tuple[str, dict]] = []
    for family in sorted(FAILURE_FAMILIES):
        mutated = copy.deepcopy(bundle)
        mutated["artifacts"] = [
            item
            for item in mutated["artifacts"]
            if not (isinstance(item, dict) and item.get("failure_family") == family)
        ]
        rows.append((f"missing-family-{family}", mutated))
    return rows


def evaluate() -> dict:
    with tempfile.TemporaryDirectory(prefix="ch456-detached-") as raw:
        root = Path(raw)
        bundle, candidate, files = _valid_bundle(root)
        baseline_valid, baseline_findings = validate_detached_bundle(bundle, candidate_root=candidate)

        structural_rows = []
        structural_rejected = 0
        for name, mutated in _general_mutations(bundle, candidate, files):
            valid, findings = validate_detached_bundle(mutated, candidate_root=candidate)
            did_reject = not valid
            structural_rejected += int(did_reject)
            structural_rows.append({"case": name, "rejected": did_reject, "findings": findings})
        structural_total = len(structural_rows)
        structural_rate = structural_rejected / structural_total if structural_total else 0.0

        family_rows = []
        family_rejected = 0
        for name, mutated in _family_omission_mutations(bundle):
            valid, findings = validate_detached_bundle(mutated, candidate_root=candidate)
            did_reject = not valid
            family_rejected += int(did_reject)
            family_rows.append({"case": name, "rejected": did_reject, "findings": findings})
        family_total = len(family_rows)
        family_leaks = family_total - family_rejected
        family_leakage_rate = family_leaks / family_total if family_total else 1.0

        threshold = (
            baseline_valid
            and structural_rate >= REQUIRED_REJECTION_RATE
            and family_leakage_rate == REQUIRED_FAILURE_FAMILY_LEAKAGE_RATE
        )
        return {
            "schema": "quick-dev.detached-mutation-metric.v2",
            "baseline_valid": baseline_valid,
            "baseline_findings": baseline_findings,
            "fixture_kind_cover": sorted({item.get("fixture_kind") for item in bundle["artifacts"] if isinstance(item, dict) and item.get("fixture_kind")}),
            "failure_family_cover": sorted({item.get("failure_family") for item in bundle["artifacts"] if isinstance(item, dict) and item.get("failure_family")}),
            "expected_failure_families": sorted(FAILURE_FAMILIES),
            "structural_mutation_cases": structural_total,
            "structural_rejected_cases": structural_rejected,
            "structural_rejection_rate": round(structural_rate, 6),
            "required_structural_rejection_rate": REQUIRED_REJECTION_RATE,
            "failure_family_omission_cases": family_total,
            "failure_family_rejected_cases": family_rejected,
            "failure_family_leaks": family_leaks,
            "failure_family_leakage_rate": round(family_leakage_rate, 6),
            "required_failure_family_leakage_rate": REQUIRED_FAILURE_FAMILY_LEAKAGE_RATE,
            "threshold_passed": threshold,
            "structural_cases": structural_rows,
            "failure_family_cases": family_rows,
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
