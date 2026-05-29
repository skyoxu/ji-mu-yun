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

    def test_dotnet_build_hygiene_removes_target_project_generated_dirs_only(self) -> None:
        module = _load_module("run_prototype_tdd_hygiene_test_module", "scripts/python/run_prototype_tdd.py")
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            project_dir = repo_root / "Game.Core"
            test_project_dir = repo_root / "Game.Core.Tests"
            other_dir = repo_root / "Other.Project"
            (project_dir / "obj").mkdir(parents=True)
            (project_dir / "bin").mkdir(parents=True)
            (project_dir / "buildcache").mkdir(parents=True)
            (project_dir / "Game.Core.csproj").write_text("<Project />", encoding="utf-8")
            (test_project_dir / "obj").mkdir(parents=True)
            (test_project_dir / "bin").mkdir(parents=True)
            (test_project_dir / "Game.Core.Tests.csproj").write_text(
                '<Project><ItemGroup><ProjectReference Include="..\\Game.Core\\Game.Core.csproj" /></ItemGroup></Project>',
                encoding="utf-8",
            )
            (other_dir / "obj").mkdir(parents=True)
            (other_dir / "buildcache").mkdir(parents=True)
            (other_dir / "Other.Project.csproj").write_text("<Project />", encoding="utf-8")

            result = module._dotnet_build_hygiene(repo_root, ["Game.Core.Tests/Game.Core.Tests.csproj"])

            self.assertTrue(result["enabled"])
            self.assertEqual(
                sorted(result["cleaned_paths"]),
                [
                    "Game.Core.Tests/bin",
                    "Game.Core.Tests/obj",
                    "Game.Core/bin",
                    "Game.Core/buildcache",
                    "Game.Core/obj",
                ],
            )
            self.assertFalse((project_dir / "obj").exists())
            self.assertFalse((project_dir / "bin").exists())
            self.assertFalse((project_dir / "buildcache").exists())
            self.assertFalse((test_project_dir / "obj").exists())
            self.assertFalse((test_project_dir / "bin").exists())
            self.assertTrue((other_dir / "obj").exists())
            self.assertTrue((other_dir / "buildcache").exists())

    def test_main_accepts_relative_out_dir(self) -> None:
        module = _load_module("run_prototype_tdd_relative_out_test_module", "scripts/python/run_prototype_tdd.py")
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            with mock.patch.object(module, "repo_root", return_value=repo_root):
                rc = module.main([
                    "--slug",
                    "demo",
                    "--stage",
                    "green",
                    "--create-record-only",
                    "--skip-record",
                    "--out-dir",
                    "logs/ci/demo-out",
                ])

            self.assertEqual(rc, 0)
            self.assertTrue((repo_root / "logs" / "ci" / "demo-out" / "summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
