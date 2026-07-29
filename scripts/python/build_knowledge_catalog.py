"""Generate the main-pinned repository knowledge layers."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from _knowledge_catalog_builder import build_layers


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _render(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = _render(value)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(rendered)
        temporary = Path(handle.name)
    os.replace(temporary, path)


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
    parser.add_argument("--check", action="store_true")
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
    if args.check:
        stale = [str(path.relative_to(root)) for path, value in outputs if not path.is_file() or path.read_text(encoding="utf-8") != _render(value)]
        print(json.dumps({"status": "current" if not stale else "stale", "stale_outputs": stale}, sort_keys=True))
        return 0 if not stale else 2
    for path, value in outputs:
        _atomic_write(path, value)
    print(
        json.dumps(
            {
                "status": "generated",
                "main_commit": snapshot["commit"],
                "snapshot_id": snapshot["snapshot_id"],
                "source_count": len(snapshot["sources"]),
                "module_count": len(catalog["modules"]),
                "projection_count": len(projections["projections"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
