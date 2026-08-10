from __future__ import annotations

import importlib.util
from pathlib import Path


ROUND_DIR = Path(__file__).resolve().parents[1]
ROOT_BRIDGE = ROUND_DIR.parents[1] / "tools" / "single_maintainer_tdd_bridge.py"
SPEC = importlib.util.spec_from_file_location("broh_root_single_maintainer_tdd_bridge", ROOT_BRIDGE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("root plan single-maintainer TDD bridge is unavailable")
BRIDGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BRIDGE)
BRIDGE.PLAN_DIR = ROUND_DIR
BRIDGE.REPOSITORY_ROOT = ROUND_DIR.parents[3]
BRIDGE.stage_projection_builder.PLAN_DIR = ROUND_DIR
if hasattr(BRIDGE.stage_projection_builder, "_MODULE"):
    BRIDGE.stage_projection_builder._MODULE.PLAN_DIR = ROUND_DIR

_ROOT_COMPLETE_TERMINAL_ONLY = BRIDGE._complete_terminal_only


def _complete_terminal_only(state, state_path, selected):
    if state.get("protocol_identity") != BRIDGE._protocol_identity():
        contract = BRIDGE._json(ROUND_DIR / "implementation-contract.v1.json")
        return BRIDGE._prepare(
            contract,
            selected,
            state_path,
            state_path.parent.parent,
            predecessor_run_id=state.get("run_id"),
        )
    run_dir = BRIDGE.REPOSITORY_ROOT / state["run_dir"]
    projection_path = run_dir / "stage-evidence-projection.v1.json"
    if not projection_path.is_file():
        BRIDGE._write(
            projection_path,
            BRIDGE.stage_projection_builder.build(
                BRIDGE.REPOSITORY_ROOT,
                run_dir,
                state["slice_id"],
                state["snapshot_paths"],
            ),
        )
    return _ROOT_COMPLETE_TERMINAL_ONLY(state, state_path, selected)


BRIDGE._complete_terminal_only = _complete_terminal_only


def main() -> int:
    return BRIDGE.main()


if __name__ == "__main__":
    raise SystemExit(main())
