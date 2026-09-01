"""Detached judge/oracle/fixture bundle validator for self-hosted promotion."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

FORBIDDEN_IMPORT_TOKENS = ("runtime_evidence", "stage_pipeline", "coverage_predicates", "current_router")
FIXTURE_KINDS = {"positive", "negative", "mutation"}


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate_detached_bundle(bundle: Mapping[str, Any], *, candidate_root: Path) -> tuple[bool, list[str]]:
    findings: list[str] = []
    if bundle.get("schema") != "detached-judge-bundle.v1":
        findings.append("bundle:schema")
    for field in ("source_commit", "source_tree", "judge_identity", "judge_version"):
        if not isinstance(bundle.get(field), str) or not bundle[field]:
            findings.append(f"bundle:{field}")
    if bundle.get("read_only_open_result") is not True:
        findings.append("bundle:read-only-open")
    if bundle.get("promotion_revalidation_result") is not True:
        findings.append("bundle:promotion-revalidation")
    artifacts = bundle.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return False, findings + ["bundle:artifacts"]
    roles: set[str] = set()
    fixture_kinds: set[str] = set()
    candidate = candidate_root.resolve()
    for index, item in enumerate(artifacts):
        if not isinstance(item, Mapping):
            findings.append(f"artifact[{index}]:shape")
            continue
        role, raw, expected = item.get("role"), item.get("path"), item.get("sha256")
        if role not in {"judge", "oracle", "fixture"}:
            findings.append(f"artifact[{index}]:role")
            continue
        roles.add(role)
        if role == "fixture":
            fixture_kind = item.get("fixture_kind")
            if fixture_kind not in FIXTURE_KINDS:
                findings.append(f"artifact[{index}]:fixture-kind")
            else:
                fixture_kinds.add(str(fixture_kind))
        elif "fixture_kind" in item:
            findings.append(f"artifact[{index}]:unexpected-fixture-kind")
        if not isinstance(raw, str) or not raw:
            findings.append(f"artifact[{index}]:path")
            continue
        path = Path(raw).resolve()
        try:
            path.relative_to(candidate)
            findings.append(f"artifact[{index}]:inside-candidate")
        except ValueError:
            pass
        if not path.is_file() or path.is_symlink():
            findings.append(f"artifact[{index}]:missing-or-symlink")
            continue
        if sha256_file(path) != expected:
            findings.append(f"artifact[{index}]:hash")
        if item.get("read_only") is not True:
            findings.append(f"artifact[{index}]:not-read-only")
        if role in {"judge", "oracle"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(token in text for token in FORBIDDEN_IMPORT_TOKENS):
                findings.append(f"artifact[{index}]:imports-current-writer")
    if roles != {"judge", "oracle", "fixture"}:
        findings.append("bundle:role-cover")
    if fixture_kinds != FIXTURE_KINDS:
        missing = ",".join(sorted(FIXTURE_KINDS - fixture_kinds))
        findings.append("bundle:fixture-kind-cover" + (":" + missing if missing else ""))
    return not findings, findings
