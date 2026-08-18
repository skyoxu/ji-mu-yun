from __future__ import annotations

import argparse
import json
from pathlib import Path


W0_TEST = '''import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import skill_input_consumption as consumption


def test_typed_selection_keeps_selection_and_content_identity_separate():
    source = [{"role": "normative_source", "path": "docs/input.md", "module": "plan", "resource_set": "core", "sha256": "sha256:a"}]
    result = consumption.build_typed_source_selection_v2(source)
    assert result["sourceSelectionHash"].startswith("sha256:")
    assert result["sourceContentHash"].startswith("sha256:")
    assert result["sourceSelectionHash"] != result["sourceContentHash"]
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--snapshot-path", nargs="+", required=True)
    parser.add_argument("--materialize-only", action="store_true")
    args = parser.parse_args()
    root = args.repository_root.resolve()
    plan = args.plan_dir.resolve()
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next(item for item in contract["slices"] if item["slice_id"] == args.slice_id)
    selector = selected["tdd"]["red"]["test_selector"].split("::", 1)[0]
    if selector not in selected.get("planned_new_files", []):
        raise ValueError("bridge may materialize only the current slice planned RED test")
    target = (root / selector).resolve()
    target.relative_to(root)
    if args.slice_id != "W0":
        raise ValueError("current bridge requires a slice-specific test template before RED")
    if target.exists():
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(W0_TEST, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
