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

R1_TEST = '''import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
TOOLS = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools"


def _load():
    spec = importlib.util.spec_from_file_location("loop_plan_directory_r1", TOOLS / "loop_plan_directory.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_successor_reservation_reuses_identical_lineage(tmp_path):
    module = _load()
    predecessor = tmp_path / "RUN-OLD"
    predecessor.mkdir()
    lineage = {"predecessor_run": "logs/tdd-adapter/plan/R1/RUN-OLD", "next_transition": "green", "authorizes": []}
    first = module.reserve_successor_run(predecessor, lineage)
    second = module.reserve_successor_run(predecessor, lineage)
    assert first == second
    assert (first / "successor-lineage.v1.json").is_file()
'''

R2_TEST = '''import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
SCRIPT = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/knowledge_context.py"


def _load():
    spec = importlib.util.spec_from_file_location("acceptance_knowledge_context_r2", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_same_selection_refresh_preserves_authorization_boundary():
    module = _load()
    assert hasattr(module, "refresh_context_read_set")
'''

R2_ACCEPTANCE_TEST = '''import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts/knowledge_context.py"
sys.path.insert(0, str(SCRIPT.parent))


def _load():
    spec = importlib.util.spec_from_file_location("acceptance_knowledge_context_r2", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_degraded_knowledge_context_has_controlled_refresh_api():
    module = _load()
    assert hasattr(module, "refresh_context_read_set")
'''


TEMPLATES = {
    "R0": [(".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_trust.py", R0_TEST)],
    "R1": [(".agents/skills/quick-dev-tdd-adapter/tools/tests/test_successor_crash_recovery.py", R1_TEST)],
    "R2": [
        (".agents/skills/quick-dev-tdd-adapter/tools/tests/test_authorization_refresh_chain.py", R2_TEST),
        (".agents/skills/run-refactor-implementation-acceptance/tests/test_knowledge_degraded_execution.py", R2_ACCEPTANCE_TEST),
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--snapshot-path", nargs="+", required=True)
    parser.add_argument("--materialize-only", action="store_true")
    args = parser.parse_args()
    if not args.materialize_only or args.slice_id not in TEMPLATES:
        raise SystemExit("bridge does not declare this slice's RED materialization")
    paths = []
    for relative, template in TEMPLATES[args.slice_id]:
        target = args.repository_root.resolve() / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_text(encoding="utf-8") != template:
            raise SystemExit(f"{args.slice_id} RED test conflicts with the bridge template")
        target.write_text(template, encoding="utf-8", newline="\n")
        paths.append(target.relative_to(args.repository_root.resolve()).as_posix())
    print(json.dumps({"test_paths": paths, "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
