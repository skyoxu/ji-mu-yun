from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _load_module(name: str, relative_path: str):
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class PrototypeTddTests(unittest.TestCase):
    def test_resolve_dotnet_prefers_phasea_repository_root_bundle(self) -> None:
        module = _load_module("run_prototype_tdd_test_module", "scripts/python/run_prototype_tdd.py")
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            dotnet_dir = repo_root / ".dotnet"
            dotnet_dir.mkdir(parents=True, exist_ok=True)
            dotnet_path = dotnet_dir / ("dotnet.exe" if os.name == "nt" else "dotnet")
            dotnet_path.write_text("", encoding="utf-8")
            workspace_root = repo_root / "logs" / "phase-a-innernet" / "workspaces" / "demo" / "repo"
            workspace_root.mkdir(parents=True, exist_ok=True)

            with mock.patch.dict(os.environ, {"PHASEA_REPOSITORY_ROOT": str(repo_root)}, clear=False):
                resolved = module._resolve_dotnet(workspace_root)

        self.assertTrue(Path(resolved).is_file())
        self.assertTrue(
            str(resolved).lower().endswith(("dotnet.exe", "dotnet")),
            resolved,
        )


if __name__ == "__main__":
    unittest.main()
