from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _fixture_support() -> Any:
    core = Path(__file__).with_name("protocol_fixture_support.py")
    spec = importlib.util.spec_from_file_location("rmap_protocol_fixture_support", core)
    if spec is None or spec.loader is None:
        raise RuntimeError("protocol fixture support is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_fixture_bundle(
    base: dict[str, Any],
    stage_documents: dict[str, dict[str, Any]] | None = None,
    external_artifacts: dict[str, bytes] | None = None,
    initial_bytes: bytes | None = b"baseline\n",
) -> tuple[dict[str, Any], dict[tuple[str, str], bytes], dict[tuple[str, str, str], bytes | None]]:
    """Build deterministic protocol fixture artifacts through the current guarded implementation."""
    return _fixture_support().hydrate_protocol_fixture(base, stage_documents, external_artifacts, initial_bytes)
