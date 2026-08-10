from __future__ import annotations

import importlib.util
from pathlib import Path


_ROOT_HELPER = Path(__file__).resolve().parents[2] / "tools" / "stage_projection_builder.py"
_SPEC = importlib.util.spec_from_file_location("broh_root_stage_projection_builder", _ROOT_HELPER)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("root plan stage projection helper is unavailable")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
_MODULE.PLAN_DIR = Path(__file__).resolve().parents[1]


def build(root: Path, run_dir: Path, slice_id: str, paths: list[str], baseline_paths: list[str] | None = None):
    return _MODULE.build(root, run_dir, slice_id, paths, baseline_paths)
