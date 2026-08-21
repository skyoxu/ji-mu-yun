"""Materialize declared Quick Dev RED tests before invocation preparation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


R0_TEST = '''import importlib.util
import sys
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py"
sys.path.insert(0, str(SCRIPT.parent))


def _load():
    spec = importlib.util.spec_from_file_location("acceptance_cli_r0", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_coordinator_accepts_v3_before_bundle_validation(tmp_path):
    module = _load()
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "schemaVersion": "acceptance-coordinator-request.v3",
        "candidateBindingHash": "sha256:" + "0" * 64,
        "bundle": {}, "evidence": {}, "authorizes": [],
    }), encoding="utf-8")
    with pytest.raises(module.InputError, match="coordinator bundle"):
        module.run_coordinator(str(request), str(tmp_path / "result.json"))
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--snapshot-path", nargs="+", required=True)
    parser.add_argument("--materialize-only", action="store_true")
    args = parser.parse_args()
    if not args.materialize_only or args.slice_id != "R0":
        raise SystemExit("bridge supports only R0 RED materialization")
    target = args.repository_root.resolve() / ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_trust.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_text(encoding="utf-8") != R0_TEST:
        raise SystemExit("R0 RED test conflicts with the bridge template")
    target.write_text(R0_TEST, encoding="utf-8", newline="\n")
    print(json.dumps({"test_path": target.relative_to(args.repository_root.resolve()).as_posix(), "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
