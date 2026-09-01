"""Detached judge/oracle/fixture bundle validator for self-hosted promotion.

`detached-judge-bundle.v1` is the canonical closed schema from the Chapter 4/5/6
implementation contract.  The older implementation-only `artifacts[]` envelope
is retained only as an explicitly versioned v2 compatibility input; it can no
longer masquerade as v1.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Mapping

FORBIDDEN_IMPORT_TOKENS = ("runtime_evidence", "stage_pipeline", "coverage_predicates", "current_router")
FIXTURE_KINDS = {"positive", "negative", "mutation"}
FAILURE_FAMILIES = {
    "semantic-contract-gap",
    "expected-red",
    "unexpected-green",
    "task-implementation-failure",
    "test-harness-failure",
    "target-binding-failure",
    "repo-noise",
    "timeout-no-observation",
    "repeated-deterministic-failure",
    "artifact-integrity",
}
_V1_KEYS = {
    "schema", "source_commit", "source_tree", "judge", "oracle", "fixtures",
    "read_only_open", "revalidated_at_promotion",
}
_V1_JUDGE_KEYS = {"path", "sha256", "identity"}
_V1_ARTIFACT_KEYS = {"path", "sha256"}
_V2_KEYS = {
    "schema", "source_commit", "source_tree", "judge_identity", "judge_version",
    "read_only_open_result", "promotion_revalidation_result", "artifacts",
}


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 71 and value.startswith("sha256:") and all(
        c in "0123456789abcdef" for c in value[7:]
    )


def _relative_posix(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("detached artifact path must be relative POSIX")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("detached artifact path escapes bundle root")
    return path.as_posix()


def _is_os_read_only(path: Path) -> bool:
    return (path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)) == 0


def _resolve_v1_artifact(
    raw: Any,
    *,
    bundle_root: Path | None,
    candidate_root: Path,
    label: str,
    findings: list[str],
) -> Path | None:
    if bundle_root is None:
        findings.append(f"{label}:bundle-root-required")
        return None
    try:
        relative = _relative_posix(raw)
    except ValueError:
        findings.append(f"{label}:path")
        return None
    root = bundle_root.resolve()
    candidate = candidate_root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        findings.append(f"{label}:outside-bundle-root")
        return None
    try:
        path.relative_to(candidate)
        findings.append(f"{label}:inside-candidate")
    except ValueError:
        pass
    if not path.is_file() or path.is_symlink():
        findings.append(f"{label}:missing-or-symlink")
        return None
    if not _is_os_read_only(path):
        findings.append(f"{label}:not-read-only")
    return path


def _fixture_metadata(path: Path, *, label: str, findings: list[str]) -> tuple[str | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        findings.append(f"{label}:fixture-json")
        return None, None
    if not isinstance(value, Mapping):
        findings.append(f"{label}:fixture-shape")
        return None, None
    kind = value.get("fixture_kind")
    family = value.get("failure_family")
    if kind not in FIXTURE_KINDS:
        findings.append(f"{label}:fixture-kind")
        kind = None
    if family is not None and family not in FAILURE_FAMILIES:
        findings.append(f"{label}:failure-family")
        family = None
    if kind in {"negative", "mutation"} and family is None:
        findings.append(f"{label}:failure-family-missing")
    return str(kind) if kind else None, str(family) if family else None


def _validate_v1(
    bundle: Mapping[str, Any],
    *,
    candidate_root: Path,
    bundle_root: Path | None,
) -> tuple[bool, list[str]]:
    findings: list[str] = []
    if set(bundle) != _V1_KEYS:
        findings.append("bundle:closed-schema")
    for field in ("source_commit", "source_tree"):
        if not isinstance(bundle.get(field), str) or not bundle[field]:
            findings.append(f"bundle:{field}")
    if bundle.get("read_only_open") is not True:
        findings.append("bundle:read-only-open")
    if bundle.get("revalidated_at_promotion") is not True:
        findings.append("bundle:promotion-revalidation")

    judge = bundle.get("judge")
    oracle = bundle.get("oracle")
    fixtures = bundle.get("fixtures")
    if not isinstance(judge, Mapping) or set(judge) != _V1_JUDGE_KEYS:
        findings.append("bundle:judge")
        judge = {}
    if not isinstance(oracle, Mapping) or set(oracle) != _V1_ARTIFACT_KEYS:
        findings.append("bundle:oracle")
        oracle = {}
    if not isinstance(fixtures, list) or not fixtures:
        findings.append("bundle:fixtures")
        fixtures = []
    if isinstance(judge, Mapping) and (not isinstance(judge.get("identity"), str) or not judge.get("identity")):
        findings.append("bundle:judge-identity")

    fixture_kinds: set[str] = set()
    fixture_failure_families: set[str] = set()
    artifacts: list[tuple[str, Mapping[str, Any]]] = [("judge", judge), ("oracle", oracle)]
    for index, item in enumerate(fixtures):
        if not isinstance(item, Mapping) or set(item) != _V1_ARTIFACT_KEYS:
            findings.append(f"fixture[{index}]:shape")
            continue
        artifacts.append((f"fixture[{index}]", item))

    for label, item in artifacts:
        raw = item.get("path") if isinstance(item, Mapping) else None
        expected = item.get("sha256") if isinstance(item, Mapping) else None
        if not _is_sha256(expected):
            findings.append(f"{label}:hash-shape")
        path = _resolve_v1_artifact(
            raw,
            bundle_root=bundle_root,
            candidate_root=candidate_root,
            label=label,
            findings=findings,
        )
        if path is None:
            continue
        if _is_sha256(expected) and sha256_file(path) != expected:
            findings.append(f"{label}:hash")
        if label in {"judge", "oracle"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(token in text for token in FORBIDDEN_IMPORT_TOKENS):
                findings.append(f"{label}:imports-current-writer")
        else:
            kind, family = _fixture_metadata(path, label=label, findings=findings)
            if kind:
                fixture_kinds.add(kind)
            if family:
                fixture_failure_families.add(family)

    if fixture_kinds != FIXTURE_KINDS:
        missing = ",".join(sorted(FIXTURE_KINDS - fixture_kinds))
        findings.append("bundle:fixture-kind-cover" + (":" + missing if missing else ""))
    if fixture_failure_families != FAILURE_FAMILIES:
        missing = ",".join(sorted(FAILURE_FAMILIES - fixture_failure_families))
        unexpected = ",".join(sorted(fixture_failure_families - FAILURE_FAMILIES))
        detail = ":" + missing if missing else ""
        if unexpected:
            detail += ":unexpected=" + unexpected
        findings.append("bundle:failure-family-cover" + detail)
    return not findings, findings


def _resolve_v2_path(raw: Any, *, bundle_root: Path | None) -> Path | None:
    if not isinstance(raw, str) or not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        if bundle_root is None:
            return None
        path = bundle_root / path
    return path.resolve()


def _validate_v2(
    bundle: Mapping[str, Any],
    *,
    candidate_root: Path,
    bundle_root: Path | None,
) -> tuple[bool, list[str]]:
    """Validate the former implementation-only envelope under an explicit v2."""
    findings: list[str] = []
    if set(bundle) != _V2_KEYS:
        findings.append("bundle:closed-schema")
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
    fixture_failure_families: set[str] = set()
    candidate = candidate_root.resolve()
    for index, item in enumerate(artifacts):
        if not isinstance(item, Mapping):
            findings.append(f"artifact[{index}]:shape")
            continue
        allowed = {"role", "path", "sha256", "read_only", "fixture_kind", "failure_family"}
        if set(item) - allowed:
            findings.append(f"artifact[{index}]:unknown-field")
        role, raw, expected = item.get("role"), item.get("path"), item.get("sha256")
        if role not in {"judge", "oracle", "fixture"}:
            findings.append(f"artifact[{index}]:role")
            continue
        roles.add(str(role))
        if role == "fixture":
            fixture_kind = item.get("fixture_kind")
            if fixture_kind not in FIXTURE_KINDS:
                findings.append(f"artifact[{index}]:fixture-kind")
            else:
                fixture_kinds.add(str(fixture_kind))
            family = item.get("failure_family")
            if family is not None:
                if family not in FAILURE_FAMILIES:
                    findings.append(f"artifact[{index}]:failure-family")
                else:
                    fixture_failure_families.add(str(family))
            elif fixture_kind in {"negative", "mutation"}:
                findings.append(f"artifact[{index}]:failure-family-missing")
        elif "fixture_kind" in item or "failure_family" in item:
            findings.append(f"artifact[{index}]:unexpected-fixture-metadata")
        path = _resolve_v2_path(raw, bundle_root=bundle_root)
        if path is None:
            findings.append(f"artifact[{index}]:path")
            continue
        try:
            path.relative_to(candidate)
            findings.append(f"artifact[{index}]:inside-candidate")
        except ValueError:
            pass
        if not path.is_file() or path.is_symlink():
            findings.append(f"artifact[{index}]:missing-or-symlink")
            continue
        if not _is_sha256(expected) or sha256_file(path) != expected:
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
        findings.append("bundle:fixture-kind-cover")
    if fixture_failure_families != FAILURE_FAMILIES:
        findings.append("bundle:failure-family-cover")
    return not findings, findings


def validate_detached_bundle(
    bundle: Mapping[str, Any],
    *,
    candidate_root: Path,
    bundle_root: Path | None = None,
    allow_v2: bool = True,
) -> tuple[bool, list[str]]:
    schema = bundle.get("schema")
    if schema == "detached-judge-bundle.v1":
        return _validate_v1(bundle, candidate_root=candidate_root, bundle_root=bundle_root)
    if schema == "detached-judge-bundle.v2" and allow_v2:
        return _validate_v2(bundle, candidate_root=candidate_root, bundle_root=bundle_root)
    return False, ["bundle:schema"]


def detached_bundle_metadata(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Return normalized metadata after validation without granting authority."""
    schema = bundle.get("schema")
    if schema == "detached-judge-bundle.v1":
        judge = bundle.get("judge") if isinstance(bundle.get("judge"), Mapping) else {}
        fixtures = bundle.get("fixtures") if isinstance(bundle.get("fixtures"), list) else []
        return {
            "judge_identity": judge.get("identity"),
            "judge_version": judge.get("sha256"),
            "artifact_count": 2 + len(fixtures),
        }
    if schema == "detached-judge-bundle.v2":
        artifacts = bundle.get("artifacts") if isinstance(bundle.get("artifacts"), list) else []
        return {
            "judge_identity": bundle.get("judge_identity"),
            "judge_version": bundle.get("judge_version"),
            "artifact_count": len(artifacts),
        }
    raise ValueError("unsupported detached bundle schema")
