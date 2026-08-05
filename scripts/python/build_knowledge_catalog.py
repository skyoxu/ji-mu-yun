"""Read-only comparison of main-pinned repository knowledge layers."""

from __future__ import annotations

import argparse
import json
import hashlib
from pathlib import Path
from typing import Any

from _knowledge_catalog_builder import build_layers
from knowledge_context_validation import validate_catalog_freshness


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _semantic_layer_errors(
    root: Path,
    outputs: tuple[tuple[Path, dict[str, Any]], ...],
) -> list[str]:
    if any(not path.is_file() for path, _ in outputs):
        return [str(path.relative_to(root)) for path, _ in outputs if not path.is_file()]
    actual_snapshot, actual_catalog, actual_projections, actual_legacy = (
        _load(path) for path, _ in outputs
    )
    expected_snapshot, expected_catalog, expected_projections, expected_legacy = (
        value for _, value in outputs
    )
    errors: list[str] = []
    if validate_catalog_freshness(root) is not None:
        errors.append(str(outputs[1][0].relative_to(root)))
    snapshot_fields = {"schema_version", "ref", "exclusion_policy_revision", "sources"}
    if {key: actual_snapshot.get(key) for key in snapshot_fields} != {
        key: expected_snapshot.get(key) for key in snapshot_fields
    }:
        errors.append(str(outputs[0][0].relative_to(root)))
    if actual_catalog.get("source_snapshot") != actual_snapshot:
        errors.append(str(outputs[1][0].relative_to(root)))
    actual_catalog_semantic = dict(actual_catalog)
    expected_catalog_semantic = dict(expected_catalog)
    actual_catalog_semantic.pop("source_snapshot", None)
    expected_catalog_semantic.pop("source_snapshot", None)
    if actual_catalog_semantic != expected_catalog_semantic:
        errors.append(str(outputs[1][0].relative_to(root)))
    actual_projection_semantic = dict(actual_projections)
    expected_projection_semantic = dict(expected_projections)
    for value in (actual_projection_semantic, expected_projection_semantic):
        value.pop("source_snapshot_id", None)
        value.pop("catalog_sha256", None)
    if (
        actual_projection_semantic != expected_projection_semantic
        or actual_projections.get("source_snapshot_id") != actual_snapshot.get("snapshot_id")
        or actual_projections.get("catalog_sha256") != _canonical_hash(actual_catalog)
    ):
        errors.append(str(outputs[2][0].relative_to(root)))
    actual_legacy_semantic = dict(actual_legacy)
    expected_legacy_semantic = dict(expected_legacy)
    actual_legacy_semantic.pop("source_snapshot", None)
    expected_legacy_semantic.pop("source_snapshot", None)
    if actual_legacy.get("source_snapshot") != actual_snapshot or actual_legacy_semantic != expected_legacy_semantic:
        errors.append(str(outputs[3][0].relative_to(root)))
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--authority-ref", default="refs/heads/main")
    parser.add_argument("--policy", type=Path, default=Path("knowledge/policies/consumer-policies.v2.json"))
    parser.add_argument("--exclusions", type=Path, default=Path("knowledge/policies/source-exclusions.v1.json"))
    parser.add_argument("--snapshot-output", type=Path, default=Path("knowledge/snapshots/repository-source-snapshot.v1.json"))
    parser.add_argument("--catalog-output", type=Path, default=Path("knowledge/catalogs/repository-knowledge-catalog.v2.json"))
    parser.add_argument("--projection-output", type=Path, default=Path("knowledge/projections/consumer-projections.v1.json"))
    parser.add_argument("--legacy-output", type=Path, default=Path("knowledge/catalogs/repository-knowledge-catalog.v1.json"))
    parser.add_argument("--check", action="store_true", help="Deprecated compatibility flag; this CLI is always read-only.")
    args = parser.parse_args()

    root = args.repository_root.resolve()

    def rooted(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    snapshot, catalog, projections, legacy = build_layers(
        root,
        policy=_load(rooted(args.policy)),
        exclusions=_load(rooted(args.exclusions)),
        authority_ref=args.authority_ref,
    )
    outputs = (
        (rooted(args.snapshot_output), snapshot),
        (rooted(args.catalog_output), catalog),
        (rooted(args.projection_output), projections),
        (rooted(args.legacy_output), legacy),
    )
    stale = _semantic_layer_errors(root, outputs)
    print(json.dumps({"status": "current" if not stale else "stale", "stale_outputs": stale}, sort_keys=True))
    return 0 if not stale else 2


if __name__ == "__main__":
    raise SystemExit(main())
