from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    plan = args.plan_dir.resolve()
    manifest = json.loads((plan / "authority-manifest.v1.json").read_text(encoding="utf-8"))
    sources: list[dict[str, str]] = []
    for section, role in (("authority_sources", "authority_source"), ("candidate_inputs", "implementation_input")):
        for item in manifest.get(section, []):
            path = item.get("path") if isinstance(item, dict) else None
            if not isinstance(path, str) or not path:
                raise ValueError(f"invalid {section} source")
            source = root / path
            if not source.is_file():
                raise ValueError(f"declared source is missing: {path}")
            sources.append({"path": path.replace("\\", "/"), "role": role, "sha256": sha256(source.read_bytes())})
    selection = [{"path": item["path"], "role": item["role"]} for item in sources]
    payload = {
        "schema_version": "skill-input-plan-receipt.v2",
        "target": plan.relative_to(root).as_posix(),
        "source_selection": selection,
        "source_selection_hash": sha256(canonical(selection)),
        "source_content_hash": sha256(canonical(sources)),
        "sources": sources,
        "authorizes": [],
        "scope": "plan-ready-only",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical(payload))
    print(json.dumps({"status": "pass", "out": args.out.as_posix(), "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
