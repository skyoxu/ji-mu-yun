#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = REPO_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))


def _load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"failed to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


run_gdunit = _load_module("run_gdunit_test_module", "scripts/python/run_gdunit.py")


class RunGdUnitTests(unittest.TestCase):
    def test_copy_reports_best_effort_should_collect_failures_and_continue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            src_root = Path(tmpdir) / "src"
            dest_root = Path(tmpdir) / "dest"
            (src_root / "report_1" / "test_suites").mkdir(parents=True, exist_ok=True)
            good = src_root / "report_1" / "results.xml"
            bad = src_root / "report_1" / "test_suites" / "deep.html"
            good.write_text("<testsuites />", encoding="utf-8")
            bad.write_text("<html></html>", encoding="utf-8")

            original_copy2 = run_gdunit.shutil.copy2

            def fake_copy2(src: str, dst: str):
                if src.endswith("deep.html"):
                    raise OSError(3, "path not found")
                return original_copy2(src, dst)

            with mock.patch.object(run_gdunit.shutil, "copy2", side_effect=fake_copy2):
                failures = run_gdunit._copy_reports_best_effort(str(src_root), str(dest_root))

            self.assertEqual(1, len(failures))
            self.assertTrue((dest_root / "report_1" / "results.xml").exists())
            self.assertFalse((dest_root / "report_1" / "test_suites" / "deep.html").exists())


if __name__ == "__main__":
    unittest.main()
