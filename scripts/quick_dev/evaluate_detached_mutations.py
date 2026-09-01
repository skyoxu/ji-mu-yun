#!/usr/bin/env python3
"""Measure canonical self-hosted detached-promotion false-green rejection.

The corpus deliberately uses the closed `detached-judge-bundle.v1` schema from
the canonical implementation contract. Fixture kind and failure-family cover
are recomputed from detached fixture bytes, so the bundle cannot self-report
coverage. The former implementation-only `artifacts[]` shape is not used as the
promotion happy path.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
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


def _read_only(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _read_only(path)


def _ref(root: Path, path: Path) -> dict:
    return {"path": path.relative_to(root).as_posix(), "sha256": _sha(path)}


def _valid_bundle(root: Path) -> tuple[dict, Path, Path, dict[str, Path], dict[str, str]]:
    candidate = root / "candidate"
    detached = root / "detached"
    candidate.mkdir()
    detached.mkdir()
    files: dict[str, Path] = {
        "judge": detached / "judge.py",
        "oracle": detached / "oracle.py",
        "positive": detached / "fixtures" / "positive.json",
    }
    _write(files["judge"], "def judge(value):\n    return bool(value)\n")
    _write(files["oracle"], "EXPECTED = {'status': 'pass'}\n")
    _write(files["positive"], json.dumps({"fixture_kind": "positive", "case": "positive"}) + "\n")

    fixture_meta: dict[str, str] = {files["positive"].relative_to(detached).as_posix(): "positive"}
    fixtures = [_ref(detached, files["positive"])]
    for index, family in enumerate(sorted(FAILURE_FAMILIES)):
        key = "family-" + family
        path = detached / "fixtures" / f"{key}.json"
        kind = "negative" if index % 2 == 0 else "mutation"
        _write(path, json.dumps({"fixture_kind": kind, "failure_family": family, "case": key}, sort_keys=True) + "\n")
        files[key] = path
        relative = path.relative_to(detached).as_posix()
        fixture_meta[relative] = kind
        fixtures.append(_ref(detached, path))

    # Alternative invalid bytes used by structural mutations. They are outside
    # the canonical fixture list and cannot influence a valid baseline.
    bad_kind = detached / "invalid" / "bad-kind.json"
    bad_family = detached / "invalid" / "bad-family.json"
    missing_family = detached / "invalid" / "missing-family.json"
    mutable_judge = detached / "invalid" / "mutable-judge.py"
    _write(bad_kind, json.dumps({"fixture_kind": "happy"}) + "\n")
    _write(bad_family, json.dumps({"fixture_kind": "negative", "failure_family": "self-reported-pass"}) + "\n")
    _write(missing_family, json.dumps({"fixture_kind": "negative"}) + "\n")
    mutable_judge.parent.mkdir(parents=True, exist_ok=True)
    mutable_judge.write_text("def judge(value):\n    return bool(value)\n", encoding="utf-8")
    files.update({"bad-kind": bad_kind, "bad-family": bad_family, "missing-family": missing_family, "mutable-judge": mutable_judge})

    bundle = {
        "schema": "detached-judge-bundle.v1",
        "source_commit": "fixture-commit",
        "source_tree": "sha256:" + "1" * 64,
        "judge": {**_ref(detached, files["judge"]), "identity": "detached-fixture-judge"},
        "oracle": _ref(detached, files["oracle"]),
        "fixtures": fixtures,
        "read_only_open": True,
        "revalidated_at_promotion": True,
    }
    return bundle, candidate, detached, files, fixture_meta


def _replace_fixture(bundle: dict, detached: Path, path: Path) -> None:
    bundle["fixtures"][0] = _ref(detached, path)


def _general_mutations(bundle: dict, candidate: Path, detached: Path, files: dict[str, Path], fixture_meta: dict[str, str]) -> list[tuple[str, dict]]:
    cases: list[tuple[str, dict]] = []

    def add(name: str, mutate) -> None:
        value = copy.deepcopy(bundle)
        mutate(value)
        cases.append((name, value))

    add("schema-drift", lambda b: b.__setitem__("schema", "detached-judge-bundle.v0"))
    add("unknown-top-level-field", lambda b: b.__setitem__("artifacts", []))
    for field in ("source_commit", "source_tree"):
        add(f"missing-{field}", lambda b, field=field: b.__setitem__(field, ""))
    add("read-only-open-false", lambda b: b.__setitem__("read_only_open", False))
    add("promotion-revalidation-false", lambda b: b.__setitem__("revalidated_at_promotion", False))
    add("fixtures-empty", lambda b: b.__setitem__("fixtures", []))
    add("judge-identity-empty", lambda b: b["judge"].__setitem__("identity", ""))
    add("judge-extra-field", lambda b: b["judge"].__setitem__("version", "1"))
    add("oracle-extra-field", lambda b: b["oracle"].__setitem__("identity", "oracle"))
    add("fixture-extra-field", lambda b: b["fixtures"][0].__setitem__("fixture_kind", "positive"))
    add("artifact-path-empty", lambda b: b["judge"].__setitem__("path", ""))
    add("artifact-path-absolute", lambda b: b["judge"].__setitem__("path", str(files["judge"].resolve())))
    add("artifact-path-parent", lambda b: b["judge"].__setitem__("path", "../judge.py"))
    add("artifact-missing", lambda b: b["judge"].__setitem__("path", "missing.py"))
    add("artifact-hash-shape", lambda b: b["judge"].__setitem__("sha256", "not-a-hash"))
    add("artifact-hash-mismatch", lambda b: b["judge"].__setitem__("sha256", "sha256:" + "0" * 64))

    mutable_rel = files["mutable-judge"].relative_to(detached).as_posix()
    add("artifact-not-read-only", lambda b: b.__setitem__("judge", {"path": mutable_rel, "sha256": _sha(files["mutable-judge"]), "identity": "mutable"}))

    inside = candidate / "judge.py"
    shutil.copyfile(files["judge"], inside)
    _read_only(inside)
    # Canonical v1 cannot express an absolute or parent-traversal path to the
    # candidate tree; trying to do so is itself rejected by the path grammar.
    add("candidate-traversal", lambda b: b["judge"].__setitem__("path", "../candidate/judge.py"))

    tainted = detached / "invalid" / "tainted-judge.py"
    _write(tainted, "import runtime_evidence\n")
    tainted_ref = _ref(detached, tainted)
    add("judge-imports-current-writer", lambda b: b.__setitem__("judge", {**tainted_ref, "identity": "tainted"}))

    add("fixture-kind-invalid", lambda b: _replace_fixture(b, detached, files["bad-kind"]))
    add("unknown-failure-family", lambda b: _replace_fixture(b, detached, files["bad-family"]))
    add("negative-family-missing", lambda b: _replace_fixture(b, detached, files["missing-family"]))

    positive_paths = {path for path, kind in fixture_meta.items() if kind == "positive"}
    negative_paths = {path for path, kind in fixture_meta.items() if kind == "negative"}
    mutation_paths = {path for path, kind in fixture_meta.items() if kind == "mutation"}
    add("fixture-cover-missing-positive", lambda b: b.__setitem__("fixtures", [x for x in b["fixtures"] if x.get("path") not in positive_paths]))
    add("fixture-cover-missing-negative", lambda b: b.__setitem__("fixtures", [x for x in b["fixtures"] if x.get("path") not in negative_paths]))
    add("fixture-cover-missing-mutation", lambda b: b.__setitem__("fixtures", [x for x in b["fixtures"] if x.get("path") not in mutation_paths]))
    return cases


def _family_for_fixture(detached: Path, item: dict) -> str | None:
    try:
        value = json.loads((detached / item["path"]).read_text(encoding="utf-8"))
    except Exception:
        return None
    return value.get("failure_family") if isinstance(value, dict) else None


def _family_omission_mutations(bundle: dict, detached: Path) -> list[tuple[str, dict]]:
    rows: list[tuple[str, dict]] = []
    for family in sorted(FAILURE_FAMILIES):
        mutated = copy.deepcopy(bundle)
        mutated["fixtures"] = [item for item in mutated["fixtures"] if _family_for_fixture(detached, item) != family]
        rows.append((f"missing-family-{family}", mutated))
    return rows


def _coverage_from_fixture_bytes(bundle: dict, detached: Path) -> tuple[list[str], list[str]]:
    kinds: set[str] = set()
    families: set[str] = set()
    for item in bundle["fixtures"]:
        value = json.loads((detached / item["path"]).read_text(encoding="utf-8"))
        if isinstance(value, dict):
            if value.get("fixture_kind"):
                kinds.add(str(value["fixture_kind"]))
            if value.get("failure_family"):
                families.add(str(value["failure_family"]))
    return sorted(kinds), sorted(families)


def evaluate() -> dict:
    with tempfile.TemporaryDirectory(prefix="ch456-detached-") as raw:
        root = Path(raw)
        bundle, candidate, detached, files, fixture_meta = _valid_bundle(root)
        baseline_valid, baseline_findings = validate_detached_bundle(
            bundle, candidate_root=candidate, bundle_root=detached, allow_v2=False
        )

        structural_rows = []
        structural_rejected = 0
        for name, mutated in _general_mutations(bundle, candidate, detached, files, fixture_meta):
            valid, findings = validate_detached_bundle(
                mutated, candidate_root=candidate, bundle_root=detached, allow_v2=False
            )
            did_reject = not valid
            structural_rejected += int(did_reject)
            structural_rows.append({"case": name, "rejected": did_reject, "findings": findings})
        structural_total = len(structural_rows)
        structural_rate = structural_rejected / structural_total if structural_total else 0.0

        family_rows = []
        family_rejected = 0
        for name, mutated in _family_omission_mutations(bundle, detached):
            valid, findings = validate_detached_bundle(
                mutated, candidate_root=candidate, bundle_root=detached, allow_v2=False
            )
            did_reject = not valid
            family_rejected += int(did_reject)
            family_rows.append({"case": name, "rejected": did_reject, "findings": findings})
        family_total = len(family_rows)
        family_leaks = family_total - family_rejected
        family_leakage_rate = family_leaks / family_total if family_total else 1.0
        fixture_kind_cover, failure_family_cover = _coverage_from_fixture_bytes(bundle, detached)

        threshold = (
            baseline_valid
            and structural_rate >= REQUIRED_REJECTION_RATE
            and family_leakage_rate == REQUIRED_FAILURE_FAMILY_LEAKAGE_RATE
        )
        return {
            "schema": "quick-dev.detached-mutation-metric.v3",
            "canonical_bundle_schema": bundle["schema"],
            "baseline_valid": baseline_valid,
            "baseline_findings": baseline_findings,
            "fixture_kind_cover": fixture_kind_cover,
            "failure_family_cover": failure_family_cover,
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
