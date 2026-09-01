#!/usr/bin/env python3
"""Verify the append-only R19 review reconciles every Architecture Deferred item exactly once."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SPINE = ROOT / "_bmad-output/planning-artifacts/architecture/architecture-jimuyun-2026-08-31/ARCHITECTURE-SPINE.md"
R19 = ROOT / "_bmad-output/planning-artifacts/architecture/architecture-jimuyun-2026-08-31/reviews/review-implementation-reconcile-20260901-r19.md"
ALLOWED = {
    "resolved-by-implementation",
    "still-deferred-outside-v1",
    "trigger-based-future-decision",
    "acceptance-blocked",
}


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"missing section: {heading}")
    rest = text[start + len(marker):]
    match = re.search(r"^##\s+", rest, flags=re.M)
    return rest[: match.start()] if match else rest


def _table_rows(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in cells):
            continue
        rows.append(cells)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("ch456-architecture-reconcile.json"))
    args = parser.parse_args()
    findings: list[str] = []
    spine_text = SPINE.read_text(encoding="utf-8")
    review_text = R19.read_text(encoding="utf-8")
    deferred_rows = _table_rows(_section(spine_text, "Deferred"))
    deferred = [row[0] for row in deferred_rows if row and row[0] != "Decision"]
    reconcile_rows = _table_rows(_section(review_text, "Deferred decision reconciliation"))
    entries = [row for row in reconcile_rows if row and row[0] != "Architecture Deferred item"]
    names = [row[0] for row in entries]
    if len(deferred) != len(set(deferred)):
        findings.append("architecture-deferred-duplicate")
    if len(names) != len(set(names)):
        findings.append("r19-deferred-duplicate")
    if set(names) != set(deferred):
        findings.append("r19-deferred-set-mismatch")
    dispositions: dict[str, str] = {}
    for row in entries:
        if len(row) < 3:
            findings.append(f"r19-row-incomplete:{row[0] if row else '?'}")
            continue
        disposition = row[1].strip("`")
        dispositions[row[0]] = disposition
        if disposition not in ALLOWED:
            findings.append(f"r19-disposition-invalid:{row[0]}:{disposition}")
    if "does **not** amend" not in review_text:
        findings.append("r19-append-only-boundary-missing")
    if "authorizes: []" not in review_text:
        findings.append("r19-authority-boundary-missing")
    if dispositions.get("60-minute task measurement") != "acceptance-blocked":
        findings.append("r19-60-minute-must-remain-acceptance-blocked-until-live-pass")
    result = {
        "schema": "ch456.architecture-deferred-reconcile-check.v1",
        "status": "pass" if not findings else "fail",
        "deferred_count": len(deferred),
        "reconciled_count": len(entries),
        "dispositions": {key: dispositions[key] for key in sorted(dispositions)},
        "findings": findings,
        "frozen_authority_modified": False,
        "authorizes": [],
    }
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
